from __future__ import annotations

import io
import json
import logging
import os
import re
import base64
import time
import functools
from dataclasses import dataclass, field
from typing import Generator, Callable, Any


# ---------------------------------------------------------------------------
# Retry Configuration and Error Handling
# ---------------------------------------------------------------------------

@dataclass
class RetryConfig:
    max_retries: int = 3
    initial_backoff: float = 0.5
    max_backoff: float = 10.0
    backoff_multiplier: float = 2.0
    timeout: float = 30.0


class ResourceLimitError(Exception):
    pass


def with_retry(config: RetryConfig | None = None):
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            backoff = config.initial_backoff
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except ResourceLimitError:
                    raise
                except Exception as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        _logger.warning(
                            "Retry attempt %d/%d for %s after error: %s",
                            attempt + 1, config.max_retries, func.__name__, e
                        )
                        time.sleep(backoff)
                        backoff = min(backoff * config.backoff_multiplier, config.max_backoff)
                    else:
                        _logger.error("All retries exhausted for %s: %s", func.__name__, e)
            
            raise last_exception if last_exception else Exception("Unknown error")
        
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# SSE Progress Events
# ---------------------------------------------------------------------------

@dataclass
class ProgressEvent:
    stage: str
    message: str
    page: int | None = None
    total_pages: int | None = None
    progress: float = 0.0
    engine: str | None = None
    extra: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "stage": self.stage,
            "message": self.message,
            "progress": round(self.progress, 4),
        }
        if self.page is not None:
            d["page"] = self.page
        if self.total_pages is not None:
            d["total_pages"] = self.total_pages
        if self.engine is not None:
            d["engine"] = self.engine
        if self.extra is not None:
            d["extra"] = self.extra
        return d


def sse_format(event: ProgressEvent) -> str:
    """Format a ProgressEvent as an SSE message line."""
    data = json.dumps(event.to_dict(), ensure_ascii=False)
    return f"event: {event.stage}\ndata: {data}\n\n"


def _legal_diff_for_vlm_page(vlm_blocks: list, ocr_text: str | None, page: int) -> dict:
    from app.validation import compute_legal_field_diffs_for_page

    vlm_text = "\n".join(el.get("text", "") for el in vlm_blocks)
    return compute_legal_field_diffs_for_page(vlm_text, ocr_text, page)


# ---------------------------------------------------------------------------
# PaddleOCR performance (Mac M1 等通常为 CPU 推理，默认偏质量；可用环境变量加速)
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)


def _configure_paddle_device() -> None:
    """在 **装有 NVIDIA CUDA** 的环境用 GPU 跑 Paddle（需 paddlepaddle-gpu）。

    设置环境变量 ``STRUCTURE_OCR_PADDLE_DEVICE=gpu:0``（或 ``gpu:1``）。
    **Apple Silicon Mac 上 pip 版 Paddle 一般没有 CUDA，设了会报错或无效**，请留空走 CPU。

    文档: https://www.paddlepaddle.org.cn/install/quick
    """
    dev = (os.environ.get("STRUCTURE_OCR_PADDLE_DEVICE") or "").strip()
    if not dev:
        return
    try:
        import paddle

        paddle.device.set_device(dev)
        _logger.info("Paddle device set to %s (STRUCTURE_OCR_PADDLE_DEVICE)", dev)
    except Exception as e:
        _logger.warning(
            "STRUCTURE_OCR_PADDLE_DEVICE=%r ignored: %s — falling back to Paddle default device",
            dev,
            e,
        )


def _env_truthy(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_opt_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_opt_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _ocr_fast_mode() -> bool:
    return _env_truthy("STRUCTURE_OCR_FAST", False)


def _pdf_pixmap_matrix(fitz_mod):
    """PDF 栅格倍率：默认 2.0；降到 1.25～1.5 可明显加速 OCR（略损小字）。"""
    z = _env_opt_float("STRUCTURE_OCR_PDF_ZOOM", 2.0)
    return fitz_mod.Matrix(z, z) if z > 0 else fitz_mod.Matrix(2, 2)


def _paddle_ocr_init_kwargs() -> dict:
    """PaddleOCR 3.x 构造参数。STRUCTURE_OCR_FAST=1：关行方向 + 缩短检测边。"""
    fast = _ocr_fast_mode()
    raw_orient = os.environ.get("STRUCTURE_OCR_TEXTLINE_ORIENTATION")
    if raw_orient is not None:
        use_textline_orientation = _env_truthy("STRUCTURE_OCR_TEXTLINE_ORIENTATION", True)
    else:
        use_textline_orientation = not fast

    kw: dict = {"lang": "ch", "use_textline_orientation": use_textline_orientation}

    det = _env_opt_int("STRUCTURE_OCR_DET_LIMIT_SIDE_LEN")
    if det is not None:
        kw["text_det_limit_side_len"] = max(320, det)
    elif fast:
        kw["text_det_limit_side_len"] = 736

    rb = _env_opt_int("STRUCTURE_OCR_REC_BATCH_SIZE")
    if rb is not None and rb > 0:
        kw["text_recognition_batch_size"] = rb

    return kw


def _paddle_ocr_predict(ocr, image_np):
    """PaddleOCR 3.x：使用 predict（勿传已废弃的 cls=）。"""
    kw = {}
    det = _env_opt_int("STRUCTURE_OCR_PREDICT_DET_LIMIT_SIDE_LEN")
    if det is not None:
        kw["text_det_limit_side_len"] = max(320, det)
    if _env_truthy("STRUCTURE_OCR_PREDICT_NO_ORIENTATION", False):
        kw["use_textline_orientation"] = False
    if kw:
        return ocr.predict(image_np, **kw)
    return ocr.predict(image_np)


# ---------------------------------------------------------------------------
# Multi-engine OCR support
# STRUCTURE_OCR_ENGINE=paddle (default) | rapidocr | apple_vision | auto
#                      | cross_validate
# Cross-validation: STRUCTURE_OCR_CV_PRIMARY=apple_vision (default)
#                   STRUCTURE_OCR_CV_SECONDARY=rapidocr   (default)
# ---------------------------------------------------------------------------

_VALID_ENGINES = ("paddle", "rapidocr", "apple_vision", "auto", "cross_validate")

def _get_ocr_engine_name() -> str:
    """Read STRUCTURE_OCR_ENGINE env var; default to 'paddle'."""
    v = os.environ.get("STRUCTURE_OCR_ENGINE", "").strip().lower()
    if v in _VALID_ENGINES:
        return v
    if v:
        _logger.warning("Unknown STRUCTURE_OCR_ENGINE=%r, falling back to 'paddle'", v)
    return "paddle"


def _rapidocr_seq(attr):
    """Normalize RapidOCR list fields (often numpy) — never use `x or []` on ndarrays."""
    if attr is None:
        return []
    if hasattr(attr, "tolist") and not isinstance(attr, (list, tuple)):
        return attr.tolist()
    return list(attr)


def _rapidocr_raw_list(result) -> list:
    """Convert RapidOCR result → [[bbox_polygon, (text, score)], ...] for _reconstruct_layout."""
    if result is None:
        return []
    boxes = _rapidocr_seq(getattr(result, "boxes", None))
    txts = _rapidocr_seq(getattr(result, "txts", None))
    scores = _rapidocr_seq(getattr(result, "scores", None))
    rows = []
    for i, bbox in enumerate(boxes):
        txt = txts[i] if i < len(txts) else ""
        score = float(scores[i]) if i < len(scores) else 0.5
        rows.append([bbox, (txt, score)])
    return rows


def _apple_vision_raw_list(ocr_items, img_w: int, img_h: int) -> list:
    """Convert ocrmac result → [[bbox_polygon, (text, score)], ...] for _reconstruct_layout.

    ocrmac returns: [(text, confidence, [x_norm, y_bl_norm, w_norm, h_norm]), ...]
    Apple Vision uses bottom-left origin; we flip to top-left.
    """
    if not ocr_items:
        return []
    rows = []
    for item in ocr_items:
        if len(item) < 3:
            continue
        text, conf, box = str(item[0]), float(item[1]), item[2]
        if len(box) < 4:
            continue
        x_n, y_bl, w_n, h_n = float(box[0]), float(box[1]), float(box[2]), float(box[3])
        # Flip y-axis: Apple Vision y=0 is bottom; screen y=0 is top
        x1 = x_n * img_w
        y1 = (1.0 - y_bl - h_n) * img_h
        x2 = x1 + w_n * img_w
        y2 = y1 + h_n * img_h
        bbox_polygon = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        rows.append([bbox_polygon, (text, conf)])
    return rows


# ---------------------------------------------------------------------------
# Cross-Validation helpers
# ---------------------------------------------------------------------------

def _poly_bounds(bbox: list) -> tuple[float, float, float, float]:
    """Return (x1, y1, x2, y2) axis-aligned bounds of a polygon."""
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_iou(a: list | None, b: list | None) -> float:
    """IoU between two bbox polygons; returns 0 if either is None/empty."""
    if not a or not b:
        return 0.0
    ax1, ay1, ax2, ay2 = _poly_bounds(a)
    bx1, by1, bx2, by2 = _poly_bounds(b)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max((ax2 - ax1) * (ay2 - ay1), 1e-6)
    area_b = max((bx2 - bx1) * (by2 - by1), 1e-6)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _text_sim_cv(a: str, b: str) -> float:
    """Character-bigram Jaccard similarity; ignores spaces for CJK robustness."""
    a, b = (a or "").strip(), (b or "").strip()
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    ca, cb = a.replace(" ", ""), b.replace(" ", "")
    # Exact match after space removal
    if ca == cb:
        return 1.0
    # Single-character strings: exact or nothing
    if len(ca) <= 1 or len(cb) <= 1:
        return 1.0 if ca == cb else 0.0
    bg_a = {ca[i : i + 2] for i in range(len(ca) - 1)}
    bg_b = {cb[i : i + 2] for i in range(len(cb) - 1)}
    inter = len(bg_a & bg_b)
    union = len(bg_a | bg_b)
    return inter / union if union > 0 else 0.0


# IoU threshold: blocks with overlap >= this are considered "same region"
_CV_IOU_THRESHOLD: float = float(os.environ.get("STRUCTURE_OCR_CV_IOU_THRESHOLD", "0.35"))
# Text similarity threshold: >= this → "match"; below → "mismatch"
_CV_TEXT_MATCH_THRESHOLD: float = float(
    os.environ.get("STRUCTURE_OCR_CV_TEXT_THRESHOLD", "0.80")
)
# On mismatch: "primary" (default) keeps primary block text; "secondary" uses secondary OCR text in the block + merged fulltext
_CV_ON_MISMATCH: str = os.environ.get("STRUCTURE_OCR_CV_ON_MISMATCH", "primary").strip().lower()


def _merge_cross_validate(
    blocks_a: list,
    text_a: str,
    blocks_b: list,
    text_b: str,
    primary_label: str = "engine_a",
    secondary_label: str = "engine_b",
) -> tuple[list, str]:
    """Align two OCR block lists by IoU and annotate each with cross-validation status.

    Returns (annotated_blocks, merged_fulltext) — fulltext 由最终块 spatial 拼接，含仅副引擎检出行。
    Each block gains a 'cross_validation' sub-dict:
        {
          "status": "match" | "mismatch" | "primary_only" | "secondary_only",
          "primary_text": str | None,
          "secondary_text": str | None,
          "similarity": float,       # bigram Jaccard
          "iou": float,
          "primary_engine": str,
          "secondary_engine": str,
        }
    Confidence (score) is boosted for matches, reduced for mismatches.
    """
    used_b: set[int] = set()
    annotated: list[dict] = []

    for blk_a in blocks_a:
        bbox_a = blk_a.get("bbox")
        best_j, best_iou = -1, 0.0

        for j, blk_b in enumerate(blocks_b):
            if j in used_b:
                continue
            iou = _bbox_iou(bbox_a, blk_b.get("bbox"))
            if iou > best_iou:
                best_iou, best_j = iou, j

        blk_out = dict(blk_a)
        if best_iou >= _CV_IOU_THRESHOLD and best_j >= 0:
            blk_b = blocks_b[best_j]
            used_b.add(best_j)
            sim = _text_sim_cv(blk_a.get("text", ""), blk_b.get("text", ""))
            status = "match" if sim >= _CV_TEXT_MATCH_THRESHOLD else "mismatch"
            # Adjust confidence: boost on match, penalise on mismatch
            score_a = blk_a.get("score", 0.5)
            score_b = blk_b.get("score", 0.5)
            if status == "match":
                blk_out["score"] = min(1.0, (score_a + score_b) / 2 + 0.12)
            else:
                blk_out["score"] = max(0.1, min(score_a, score_b) - 0.12)
                if _CV_ON_MISMATCH == "secondary":
                    st = (blk_b.get("text") or "").strip()
                    if st:
                        blk_out["text"] = blk_b.get("text", "")
            blk_out["cross_validation"] = {
                "status": status,
                "primary_text": blk_a.get("text"),
                "secondary_text": blk_b.get("text"),
                "similarity": round(sim, 3),
                "iou": round(best_iou, 3),
                "primary_engine": primary_label,
                "secondary_engine": secondary_label,
            }
        else:
            # No matching block in secondary → uncertain
            blk_out["score"] = max(0.1, blk_a.get("score", 0.5) - 0.15)
            blk_out["cross_validation"] = {
                "status": "primary_only",
                "primary_text": blk_a.get("text"),
                "secondary_text": None,
                "similarity": 0.0,
                "iou": 0.0,
                "primary_engine": primary_label,
                "secondary_engine": secondary_label,
            }
        annotated.append(blk_out)

    # Blocks only seen by secondary → append as uncertain
    for j, blk_b in enumerate(blocks_b):
        if j not in used_b:
            blk_out = dict(blk_b)
            blk_out["score"] = max(0.1, blk_b.get("score", 0.5) - 0.15)
            blk_out["cross_validation"] = {
                "status": "secondary_only",
                "primary_text": None,
                "secondary_text": blk_b.get("text"),
                "similarity": 0.0,
                "iou": 0.0,
                "primary_engine": primary_label,
                "secondary_engine": secondary_label,
            }
            annotated.append(blk_out)

    # Re-sort by vertical position (primary_only / secondary_only may be interleaved)
    annotated.sort(key=lambda b: b.get("center_y", 0))
    # Full OCR string from final blocks (includes secondary_only lines; matches block text after mismatch override)
    raw_lines: list = []
    for b in annotated:
        bb = b.get("bbox")
        if bb:
            raw_lines.append([bb, (b.get("text") or "", float(b.get("score", 0.5)))])
    _, merged_full = _reconstruct_layout(raw_lines)
    return annotated, merged_full


def compute_cross_validation_summary(blocks: list[dict]) -> dict | None:
    """Aggregate per-block cross_validation fields into a page/doc summary."""
    cv_blocks = [b for b in blocks if b.get("cross_validation")]
    if not cv_blocks:
        return None

    counts: dict[str, int] = {"match": 0, "mismatch": 0, "primary_only": 0, "secondary_only": 0}
    mismatches: list[dict] = []

    for b in cv_blocks:
        cv = b["cross_validation"]
        st = cv.get("status", "unknown")
        counts[st] = counts.get(st, 0) + 1
        if st == "mismatch":
            mismatches.append({
                "primary_text": cv.get("primary_text"),
                "secondary_text": cv.get("secondary_text"),
                "similarity": cv.get("similarity"),
                "bbox": b.get("bbox"),
                "page": b.get("page", 1),
            })

    total = len(cv_blocks)
    matched = counts["match"]
    agreement_rate = round(matched / total, 3) if total else 1.0

    primary_engine = cv_blocks[0]["cross_validation"].get("primary_engine", "?")
    secondary_engine = cv_blocks[0]["cross_validation"].get("secondary_engine", "?")

    return {
        "primary_engine": primary_engine,
        "secondary_engine": secondary_engine,
        "total_blocks": total,
        "matched": matched,
        "mismatched": counts["mismatch"],
        "primary_only": counts["primary_only"],
        "secondary_only": counts["secondary_only"],
        "agreement_rate": agreement_rate,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Engine wrapper and builder
# ---------------------------------------------------------------------------

class _OcrEngineWrapper:
    """Unified OCR engine interface.

    Wraps PaddleOCR / RapidOCR / Apple Vision so every call site can use:
        extracted_blocks, ocr_text = ocr.predict(image_np, image_pil)
    """

    def __init__(self, engine_type: str, engine_obj) -> None:
        self.engine_type = engine_type
        self._engine = engine_obj

    def predict(self, image_np, image_pil=None) -> tuple[list, str]:
        """Run OCR and return (extracted_blocks, ocr_text) via _reconstruct_layout."""
        try:
            raw = self._raw_predict(image_np, image_pil)
        except Exception as e:
            _logger.error("OCR engine '%s' prediction failed: %s", self.engine_type, e)
            return [], ""
        return _reconstruct_layout(raw)

    def _raw_predict(self, image_np, image_pil):
        if self.engine_type == "paddle":
            result = _paddle_ocr_predict(self._engine, image_np)
            # PaddleOCR 3.x returns a list of per-image results
            return (
                result[0]
                if result and isinstance(result, (list, tuple)) and len(result) > 0
                else result
            )

        if self.engine_type == "rapidocr":
            result = self._engine(image_np)
            return _rapidocr_raw_list(result)

        if self.engine_type == "apple_vision":
            if image_pil is None:
                from PIL import Image
                image_pil = Image.fromarray(image_np[:, :, ::-1])
            # ocrmac>=1.0: use text_from_image (module no longer exposes ocrmac.OCR)
            items = self._engine(image_pil, detail=True)
            return _apple_vision_raw_list(items, image_pil.width, image_pil.height)

        return []

    def __bool__(self) -> bool:
        return True


class _CrossValidateWrapper:
    """Run two OCR engines on the same image and cross-validate their outputs.

    Blocks are aligned by bounding-box IoU; text similarity determines match/mismatch.
    Matched blocks get a confidence boost; mismatched blocks are flagged for review.
    """

    def __init__(self, primary: _OcrEngineWrapper, secondary: _OcrEngineWrapper) -> None:
        self.primary = primary
        self.secondary = secondary
        self.engine_type = f"cross_validate({primary.engine_type}+{secondary.engine_type})"

    def predict(self, image_np, image_pil=None) -> tuple[list, str]:
        blocks_a, text_a = self.primary.predict(image_np, image_pil)
        blocks_b, text_b = self.secondary.predict(image_np, image_pil)
        return _merge_cross_validate(
            blocks_a, text_a,
            blocks_b, text_b,
            self.primary.engine_type,
            self.secondary.engine_type,
        )

    def __bool__(self) -> bool:
        return bool(self.primary) or bool(self.secondary)


def _build_single_engine_by_name(name: str) -> "_OcrEngineWrapper | bool":
    """Build one named leaf engine (not 'auto' or 'cross_validate')."""
    if name == "apple_vision":
        try:
            from ocrmac.ocrmac import text_from_image  # type: ignore
            _logger.info("OCR engine: Apple Vision (ocrmac text_from_image)")
            return _OcrEngineWrapper("apple_vision", text_from_image)
        except ImportError:
            _logger.error(
                "apple_vision engine requested but ocrmac is not installed: pip install ocrmac"
            )
            return False

    if name == "rapidocr":
        try:
            from rapidocr import RapidOCR  # type: ignore
            _logger.info("OCR engine: RapidOCR (ONNX)")
            return _OcrEngineWrapper("rapidocr", RapidOCR())
        except ImportError:
            _logger.error(
                "rapidocr engine requested but not installed: pip install rapidocr onnxruntime"
            )
            return False

    # paddle (default)
    try:
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        _configure_paddle_device()
        from paddleocr import PaddleOCR

        engine = PaddleOCR(**_paddle_ocr_init_kwargs())
        _logger.info("OCR engine: PaddleOCR")
        return _OcrEngineWrapper("paddle", engine)
    except Exception as e:
        _logger.error("Failed to load PaddleOCR: %s", e)
        return False


def _build_ocr_engine_wrapper() -> "_OcrEngineWrapper | _CrossValidateWrapper | bool":
    """Load the OCR engine configured by STRUCTURE_OCR_ENGINE; returns wrapper or False."""
    name = _get_ocr_engine_name()

    # ── cross_validate: run two engines and compare ──────────────────────────
    if name == "cross_validate":
        primary_name = os.environ.get("STRUCTURE_OCR_CV_PRIMARY", "rapidocr").strip().lower()
        secondary_name = os.environ.get("STRUCTURE_OCR_CV_SECONDARY", "apple_vision").strip().lower()
        _logger.info(
            "OCR mode: cross_validate  primary=%s  secondary=%s",
            primary_name, secondary_name,
        )
        primary = _build_single_engine_by_name(primary_name)
        secondary = _build_single_engine_by_name(secondary_name)
        if primary and secondary:
            return _CrossValidateWrapper(primary, secondary)  # type: ignore[arg-type]
        if primary or secondary:
            _logger.warning(
                "Cross-validation: only one engine loaded (%s), running single-engine mode. "
                "Install the other with: pip install '.[auto]'",
                primary_name if primary else secondary_name,
            )
            return primary or secondary  # type: ignore[return-value]
        # Neither custom engine available → fall back to PaddleOCR so VLM hints still work
        _logger.warning(
            "Cross-validation: neither '%s' nor '%s' is installed. "
            "Falling back to PaddleOCR for OCR hints. "
            "Install both with: cd backend && pip install -e '.[auto]'",
            primary_name, secondary_name,
        )
        return _build_single_engine_by_name("paddle")

    # ── auto: try rapidocr → apple_vision → paddle（与 cross_validate 默认一致）────────
    if name == "auto":
        for candidate in ("rapidocr", "apple_vision", "paddle"):
            engine = _build_single_engine_by_name(candidate)
            if engine:
                _logger.info("OCR engine (auto-selected): %s", candidate)
                return engine
        return False

    # ── explicit single engine ───────────────────────────────────────────────
    return _build_single_engine_by_name(name)


@dataclass
class OCRBlock:
    page: int
    type: str
    text: str
    bbox: list[float] | None = None
    confidence: float | None = None
    structure_type: str | None = None
    reading_order: int | None = None
    hierarchy_level: int | None = None
    parent_id: str | None = None
    relations: list[str] = field(default_factory=list)
    group_id: str | None = None
    table_html: str | None = None


_STRUCTURE_TYPE_MAP: dict[str, str] = {
    "text": "text",
    "title": "title",
    "paragraph_title": "title",
    "doc_title": "title",
    "figure_title": "caption",
    "table": "table",
    "image": "figure",
    "figure": "figure",
    "header": "header",
    "footer": "footer",
    "equation": "equation",
    "formula": "equation",
    "reference": "footnote",
    "vision_footnote": "footnote",
    "list": "list",
    "table_caption": "caption",
    "figure_caption": "caption",
}

_HIERARCHY_LEVELS: dict[str, int] = {
    "doc_title": 0,
    "title": 1,
    "paragraph_title": 2,
    "figure_title": 3,
    "table_caption": 3,
    "figure_caption": 3,
    "text": 4,
    "list": 4,
    "table": 4,
    "equation": 4,
    "formula": 4,
    "image": 5,
    "figure": 5,
    "header": 6,
    "footer": 6,
    "reference": 6,
    "vision_footnote": 6,
}


_TOC_DOTS_RE = re.compile(r"[.\u2024\u2025\u2026\uff0e\u30fb]{4,}\s*\d+\s*$")
_STRONG_BREAK_RE = re.compile(r"[。！？!?：:；;]$")


def _looks_like_toc_entry(line: str) -> bool:
    return bool(_TOC_DOTS_RE.search(line))


def _looks_like_fragment(line: str) -> bool:
    compact = re.sub(r"\s+", "", line)
    if not compact or _looks_like_toc_entry(line):
        return False
    if len(compact) <= 12:
        return True
    ascii_like = sum(ch.isascii() and (ch.isalnum() or ch in "().,/-_+[]") for ch in compact)
    return len(compact) <= 32 and ascii_like / max(len(compact), 1) >= 0.6


def _normalize_pdf_line_breaks(text: str) -> str:
    raw_lines = text.replace("\r\n", "\n").splitlines()
    normalized_lines: list[str] = []
    current = ""

    def _stripped_at(idx: int) -> str:
        if idx < 0 or idx >= len(raw_lines):
            return ""
        return re.sub(r"\s+", " ", raw_lines[idx]).strip()

    def _next_nonempty_index(start: int) -> int:
        for j in range(start, len(raw_lines)):
            if _stripped_at(j):
                return j
        return len(raw_lines)

    i = 0
    while i < len(raw_lines):
        line = _stripped_at(i)

        if not line:
            nxt = _next_nonempty_index(i + 1)
            next_line = _stripped_at(nxt) if nxt < len(raw_lines) else ""
            if (
                current
                and next_line
                and not _looks_like_toc_entry(current)
                and not _looks_like_toc_entry(next_line)
                and not _STRONG_BREAK_RE.search(current)
                and _looks_like_fragment(next_line)
            ):
                i = nxt
                continue
            if current:
                normalized_lines.append(current)
                current = ""
            i += 1
            continue

        if not current:
            current = line
            i += 1
            continue

        if _looks_like_toc_entry(current) or _looks_like_toc_entry(line):
            normalized_lines.append(current)
            current = line
            i += 1
            continue

        if not _STRONG_BREAK_RE.search(current) and (_looks_like_fragment(current) or _looks_like_fragment(line)):
            current = f"{current} {line}"
            i += 1
            continue

        normalized_lines.append(current)
        current = line
        i += 1

    if current:
        normalized_lines.append(current)

    return "\n".join(normalized_lines)


def _blocks_from_normalized_page_text(
    page_index: int, normalized: str, *, confidence: float | None
) -> list[dict]:
    lines = [ln.strip() for ln in normalized.split("\n") if ln.strip()]
    if not lines:
        return []
    out: list[dict] = []
    if len(lines) == 1:
        out.append(
            {
                "page": page_index,
                "type": "text",
                "text": lines[0],
                "bbox": None,
                "confidence": confidence,
            }
        )
        return out
    for ln in lines:
        out.append(
            {
                "page": page_index,
                "type": "text",
                "text": ln,
                "bbox": None,
                "confidence": None,
            }
        )
    return out


def _reconstruct_layout(res_data) -> tuple[list[dict], str]:
    if isinstance(res_data, dict):
        res_dict = res_data.get("res", res_data)
        dt_polys = res_dict.get("dt_polys", [])
        rec_texts = res_dict.get("rec_texts", res_dict.get("rec_text", []))
        rec_scores = res_dict.get("rec_scores", res_dict.get("rec_score", []))
        elements = []
        for i in range(len(dt_polys)):
            bbox = dt_polys[i]
            txt = rec_texts[i] if i < len(rec_texts) else ""
            score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            elements.append({
                "bbox": bbox, "text": txt, "score": score,
                "min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys),
                "center_y": (min(ys) + max(ys)) / 2, "height": max(ys) - min(ys)
            })
    else:
        elements = []
        for line in (res_data if res_data else []):
            bbox, (txt, score) = line
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            elements.append({
                "bbox": bbox, "text": txt, "score": float(score),
                "min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys),
                "center_y": (min(ys) + max(ys)) / 2, "height": max(ys) - min(ys)
            })

    if not elements:
        return [], ""

    elements.sort(key=lambda e: e["center_y"])
    lines, current_line = [], []
    for el in elements:
        if not current_line:
            current_line.append(el)
        else:
            avg_h = sum(e["height"] for e in current_line) / len(current_line)
            mean_cy = sum(e["center_y"] for e in current_line) / len(current_line)
            if abs(el["center_y"] - mean_cy) < avg_h * 0.4:
                current_line.append(el)
            else:
                lines.append(current_line)
                current_line = [el]
    if current_line:
        lines.append(current_line)
        
    extracted_blocks, formatted_rows = [], []
    for line in lines:
        line.sort(key=lambda e: e["min_x"])
        row_str = ""
        last_x = None
        for el in line:
            extracted_blocks.append(el)
            if last_x is not None:
                gap = el["min_x"] - last_x
                c_w = el["height"] * 0.5
                if c_w > 0 and gap > c_w * 1.5:
                    spaces = int(gap / c_w)
                    row_str += " " * min(spaces, 40)
                else:
                    row_str += " "
            row_str += el["text"]
            last_x = el["max_x"]
        formatted_rows.append(row_str)
        
    return extracted_blocks, "\n".join(formatted_rows)


def _extract_bbox_from_item(item: dict) -> list[float] | None:
    """Extract bounding box from a PPStructure item, normalizing to [x_min, y_min, x_max, y_max]."""
    bbox = item.get("bbox") or item.get("box") or item.get("coordinates")
    if bbox is None:
        return None
    if isinstance(bbox, list) and len(bbox) == 4:
        return [float(v) for v in bbox]
    if isinstance(bbox, list) and len(bbox) == 8:
        x_vals = [bbox[i] for i in range(0, 8, 2)]
        y_vals = [bbox[i] for i in range(1, 8, 2)]
        return [float(min(x_vals)), float(min(y_vals)), float(max(x_vals)), float(max(y_vals))]
    if isinstance(bbox, dict):
        lt = bbox.get("left_top") or bbox.get("tl") or bbox.get("top_left")
        rb = bbox.get("right_bottom") or bbox.get("br") or bbox.get("bottom_right")
        if lt and rb:
            return [float(lt[0]), float(lt[1]), float(rb[0]), float(rb[1])]
        x1 = float(bbox.get("x_min", bbox.get("xmin", 0)))
        y1 = float(bbox.get("y_min", bbox.get("ymin", 0)))
        x2 = float(bbox.get("x_max", bbox.get("xmax", 0)))
        y2 = float(bbox.get("y_max", bbox.get("ymax", 0)))
        if x2 > x1 or y2 > y1:
            return [x1, y1, x2, y2]
    return None


def _extract_text_from_item(item: dict) -> str:
    """Extract text content from a PPStructure item."""
    res = item.get("res") or {}
    if isinstance(res, dict):
        return res.get("text") or res.get("rec_text") or ""
    if isinstance(res, str):
        return res
    rec_text = item.get("rec_text") or item.get("text")
    if rec_text:
        return str(rec_text)
    return ""


def _extract_table_html_from_item(item: dict) -> str | None:
    """Extract HTML table structure from a PPStructure item."""
    res = item.get("res") or {}
    if isinstance(res, dict):
        html = res.get("html")
        if html:
            return str(html)
    html = item.get("html")
    if html:
        return str(html)
    return None


def _blocks_from_structure_result(
    page_index: int, structure_result: list[dict], image_width: float, image_height: float
) -> list[dict]:
    """Convert PPStructure output into structured blocks with full metadata."""
    blocks: list[dict] = []
    for idx, item in enumerate(structure_result or []):
        raw_type = item.get("type") or item.get("label") or "text"
        mapped_type = _STRUCTURE_TYPE_MAP.get(raw_type, "text")
        hierarchy_level = _HIERARCHY_LEVELS.get(raw_type, 4)
        bbox = _extract_bbox_from_item(item)
        text = _extract_text_from_item(item)
        confidence = item.get("score") or item.get("confidence")
        table_html = _extract_table_html_from_item(item)

        if not text and not table_html:
            continue

        block_id = f"p{page_index}_b{idx}"
        block = {
            "page": page_index,
            "type": mapped_type,
            "structure_type": raw_type,
            "text": text,
            "bbox": bbox,
            "confidence": float(confidence) if confidence is not None else None,
            "reading_order": idx,
            "hierarchy_level": hierarchy_level,
            "parent_id": None,
            "relations": [],
            "group_id": None,
            "table_html": table_html,
            "_block_id": block_id,
            "_bbox_center": ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2) if bbox else None,
        }
        blocks.append(block)
    return blocks


def _analyze_spatial_relations(blocks: list[dict], image_width: float, image_height: float) -> list[dict]:
    """Analyze spatial relationships between blocks: reading order, hierarchy, grouping."""
    if not blocks:
        return blocks

    blocks_with_bbox = [b for b in blocks if b.get("bbox")]
    blocks_without_bbox = [b for b in blocks if not b.get("bbox")]

    if blocks_with_bbox:
        blocks_with_bbox.sort(key=lambda b: (b["_bbox_center"][1], b["_bbox_center"][0]))

        for i, block in enumerate(blocks_with_bbox):
            block["reading_order"] = i

        _detect_columns(blocks_with_bbox, image_width)
        _detect_hierarchy(blocks_with_bbox)
        _detect_relations(blocks_with_bbox)

    for block in blocks_without_bbox:
        block["reading_order"] = len(blocks_with_bbox)
        block["group_id"] = None

    for block in blocks:
        block.pop("_bbox_center", None)
        block.pop("_block_id", None)

    return blocks


def _detect_columns(blocks: list[dict], image_width: float) -> None:
    """Detect column structure based on x-coordinate clustering."""
    if len(blocks) < 2:
        for b in blocks:
            b["group_id"] = "single"
        return

    x_centers = [b["_bbox_center"][0] for b in blocks]
    x_min, x_max = min(x_centers), max(x_centers)
    page_mid = image_width / 2
    gutter_threshold = image_width * 0.05

    left_blocks = [b for b in blocks if b["_bbox_center"][0] < page_mid - gutter_threshold]
    right_blocks = [b for b in blocks if b["_bbox_center"][0] > page_mid + gutter_threshold]
    center_blocks = [b for b in blocks if page_mid - gutter_threshold <= b["_bbox_center"][0] <= page_mid + gutter_threshold]

    if left_blocks and right_blocks:
        for b in left_blocks:
            b["group_id"] = "column-left"
        for b in right_blocks:
            b["group_id"] = "column-right"
        for b in center_blocks:
            b["group_id"] = "column-center"
    else:
        for b in blocks:
            b["group_id"] = "single"


def _detect_hierarchy(blocks: list[dict]) -> None:
    """Detect parent-child hierarchy based on type and vertical proximity."""
    title_stack: list[dict] = []

    for block in blocks:
        stype = block.get("structure_type", "")
        hlevel = block.get("hierarchy_level", 4)

        if hlevel <= 2:
            while title_stack and title_stack[-1].get("hierarchy_level", 4) >= hlevel:
                title_stack.pop()
            if title_stack:
                parent_id = title_stack[-1].get("_block_id")
                if parent_id:
                    block["parent_id"] = parent_id
                    title_stack[-1]["relations"].append(f"child:{block.get('_block_id', '')}")
            title_stack.append(block)
        elif title_stack:
            block["parent_id"] = title_stack[-1].get("_block_id")
            title_stack[-1]["relations"].append(f"child:{block.get('_block_id', '')}")


def _detect_relations(blocks: list[dict]) -> None:
    """Detect sibling relations between consecutive blocks at same hierarchy level."""
    for i in range(len(blocks) - 1):
        curr = blocks[i]
        nxt = blocks[i + 1]
        if curr.get("parent_id") == nxt.get("parent_id"):
            curr["relations"].append(f"sibling:{nxt.get('_block_id', '')}")
            nxt["relations"].append(f"sibling:{curr.get('_block_id', '')}")


class DocumentExtractor:
    def __init__(self) -> None:
        self._ocr = None
        self._structure = None

    def _load_ocr(self):
        if self._ocr is not None:
            return self._ocr
        self._ocr = _build_ocr_engine_wrapper()
        return self._ocr

    def _load_structure(self):
        if self._structure is not None:
            return self._structure
        try:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            _configure_paddle_device()
            try:
                from paddleocr import PPStructure
            except ImportError:
                from paddleocr import PPStructureV3 as PPStructure

            self._structure = PPStructure(lang="ch")
        except Exception:
            self._structure = False
        return self._structure

    def extract(self, raw: bytes, filename: str, suffix: str, mime_type: str) -> dict:
        notes: list[str] = []
        if suffix == ".txt" or mime_type == "text/plain":
            return self._extract_text(raw, notes)
        if suffix == ".pdf" or mime_type == "application/pdf":
            return self._extract_pdf(raw, notes)
        return self._extract_image(raw, notes)

    def _extract_text(self, raw: bytes, notes: list[str]) -> dict:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("gbk")
            except UnicodeDecodeError:
                notes.append("Could not decode text file; returning raw bytes as text.")
                text = raw.decode("utf-8", errors="replace")
        return {"pages": 1, "text": text, "blocks": [{"page": 1, "type": "text", "text": text, "structure_type": "text", "reading_order": 0, "hierarchy_level": 4, "parent_id": None, "relations": [], "group_id": "single", "table_html": None}], "notes": notes, "page_infos": [{"page": 1, "width": None, "height": None, "image_data": None, "columns": None, "layout_type": None}]}

    def _extract_image(self, raw: bytes, notes: list[str]) -> dict:
        try:
            from PIL import Image
        except ImportError:
            notes.append("Pillow is not installed; cannot process image files.")
            return {"pages": 1, "text": "", "blocks": [], "notes": notes}

        try:
            image_pil = Image.open(io.BytesIO(raw)).convert("RGB")
            buffered = io.BytesIO()
            image_pil.save(buffered, format="PNG")
            image_data = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
        except Exception:
            notes.append("Could not open image file; the file may be corrupted or invalid.")
            return {"pages": 0, "text": "", "blocks": [], "notes": notes}
            
        return self._process_image_pil(image_pil, image_data, notes)

    def _process_image_pil(
        self, image_pil: Image.Image, image_data: str | None, notes: list[str]
    ) -> dict:
        blocks: list[dict] = []
        text = ""
        w, h = image_pil.size

        ocr = self._load_ocr()
        structure = self._load_structure()
        from app.vlm import is_vlm_enabled, extract_via_vlm

        image = None
        if structure or ocr:
            try:
                import numpy as np
                image = np.array(image_pil)[:, :, ::-1].copy()
            except ImportError:
                notes.append("Numpy is not installed; OCR/Structure fallback unavailable.")

        # --- Dual-Engine Consensus: Get OCR hints first if VLM is enabled ---
        ocr_hints = None
        extracted_ocr_blocks = None
        _cv_hint_summary = None  # cross_validation from OCR hint step (used when VLM is primary)
        if is_vlm_enabled() and ocr is not None and image is not None:
            try:
                extracted_ocr_blocks, ocr_text = ocr.predict(image, image_pil)
                if ocr_text.strip():
                    ocr_hints = ocr_text
                _cv_hint_summary = compute_cross_validation_summary(extracted_ocr_blocks)
            except Exception as e:
                notes.append(f"Pre-VLM OCR extraction failed: {e}")

        # --- VLM Extraction ---
        vlm_blocks = None
        if is_vlm_enabled() and image_data:
            try:
                b64_stripped = image_data.split(",", 1)[-1] if "," in image_data else image_data
                vlm_blocks = extract_via_vlm(b64_stripped, ocr_hints=ocr_hints)
                if vlm_blocks is None:
                    notes.append("VLM 未返回结果 — 已自动回退到几何布局提取。")
            except Exception as e:
                notes.append(f"VLM 调用失败: {e}。已自动回退到几何布局提取。")

        if vlm_blocks is not None:
            from app.vlm import get_vlm_config
            from app.validation import (
                compute_consensus_score,
                compute_vlm_confidence,
                merge_legal_field_page_diffs,
                validate_legal_fields,
            )

            cfg = get_vlm_config()
            engine_str = f"{cfg.get('provider', 'unknown')} · {cfg.get('model', 'unknown')}"

            ocr_combined_text = ocr_hints or ""

            if extracted_ocr_blocks:
                consensus = compute_consensus_score(vlm_blocks, extracted_ocr_blocks, ocr_combined_text)
                notes.extend(consensus["warnings"])

            for idx, el in enumerate(vlm_blocks):
                txt = el.get("text", "")
                bbox = el.get("bbox")
                if not bbox or len(bbox) != 4 or bbox == [0,0,0,0]:
                    bbox = None
                blocks.append({
                    "page": 1,
                    "type": el.get("type", "text"),
                    "structure_type": "text",
                    "text": txt,
                    "bbox": bbox,
                    "confidence": compute_vlm_confidence(el, extracted_ocr_blocks, ocr_combined_text),
                    "reading_order": idx,
                    "hierarchy_level": el.get("hierarchy_level", 4),
                    "parent_id": None,
                    "relations": [],
                    "group_id": el.get("group_id", "single"),
                    "table_html": None,
                })

            field_warnings = validate_legal_fields(blocks)
            notes.extend(field_warnings)

            page_diff = _legal_diff_for_vlm_page(vlm_blocks, ocr_combined_text, 1)
            if page_diff.get("has_discrepancy"):
                notes.append(
                    "案号/金额：OCR 与 VLM 不一致，请查看下方「关键字段 OCR/VLM 对照」。"
                )

            return {
                "pages": 1,
                "text": "\n".join([b["text"] for b in blocks]),
                "blocks": blocks,
                "notes": notes,
                "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                "vlm_used": True,
                "vlm_engine": engine_str,
                "legal_field_diffs": merge_legal_field_page_diffs([page_diff]),
                # Cross-validation summary comes from OCR hint blocks (not VLM blocks)
                "cross_validation_summary": _cv_hint_summary,
            }
        
        # --- Fallback: Geometric Structure & OCR ---
        if image is None:
            return {"pages": 1, "text": "", "blocks": [], "notes": notes, "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}], "vlm_used": False, "vlm_engine": None}
        
        if structure:
            try:
                structure_result = structure(image)
                struct_blocks = _blocks_from_structure_result(
                    1, structure_result, float(w), float(h)
                )
                if struct_blocks:
                    _analyze_spatial_relations(struct_blocks, float(w), float(h))
                    page_texts = [b["text"] for b in struct_blocks if b["text"] and b.get("type") not in ("header", "footer")]
                    return {
                        "pages": 1,
                        "text": "\n".join(page_texts),
                        "blocks": struct_blocks,
                        "notes": notes,
                        "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                        "vlm_used": False,
                        "vlm_engine": None,
                    }
            except Exception as e:
                notes.append(f"structure parse failed; fell back to OCR ({e})")

        if not ocr:
            notes.append("PaddleOCR is not installed; returning image metadata only.")
            return {"pages": 1, "text": "", "blocks": blocks, "notes": notes, "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}], "vlm_used": False, "vlm_engine": None}
        
        # Use extracted OCR blocks if we already computed them
        if extracted_ocr_blocks is not None:
            for idx, el in enumerate(extracted_ocr_blocks):
                blocks.append(
                    {
                        "page": 1,
                        "type": "text",
                        "structure_type": "text",
                        "text": el["text"],
                        "bbox": [float(v) for point in el["bbox"] for v in point],
                        "confidence": el["score"],
                        "reading_order": idx,
                        "hierarchy_level": 4,
                        "parent_id": None,
                        "relations": [],
                        "group_id": "single",
                        "table_html": None,
                        "cross_validation": el.get("cross_validation"),
                    }
                )
        else:
            try:
                extracted_blocks, text = ocr.predict(image, image_pil)
                for idx, el in enumerate(extracted_blocks):
                    blocks.append(
                        {
                            "page": 1,
                            "type": "text",
                            "structure_type": "text",
                            "text": el["text"],
                            "bbox": [float(v) for point in el["bbox"] for v in point],
                            "confidence": el["score"],
                            "reading_order": idx,
                            "hierarchy_level": 4,
                            "parent_id": None,
                            "relations": [],
                            "group_id": "single",
                            "table_html": None,
                            "cross_validation": el.get("cross_validation"),
                        }
                    )
            except Exception as exc:
                notes.append(f"OCR failed ({exc})")
                text = ""

        return {
            "pages": 1,
            "text": text if "text" in locals() and text else "\n".join([b["text"] for b in blocks]),
            "blocks": blocks,
            "notes": notes,
            "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
            "vlm_used": False,
            "vlm_engine": None,
        }

    def _extract_pdf(self, raw: bytes, notes: list[str]) -> dict:
        try:
            import fitz
        except ImportError:
            notes.append("PyMuPDF is not installed; cannot process PDF files.")
            return {"pages": 0, "text": "", "blocks": [], "notes": notes}

        try:
            from PIL import Image
        except ImportError:
            notes.append("Pillow is not installed; cannot process PDF pages.")
            return {"pages": 0, "text": "", "blocks": [], "notes": notes}

        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception:
            notes.append("Could not open PDF file; the file may be corrupted or invalid.")
            return {"pages": 0, "text": "", "blocks": [], "notes": notes}
        blocks: list[dict] = []
        full_text: list[str] = []
        ocr = self._load_ocr()
        structure = self._load_structure()
        from app.vlm import is_vlm_enabled, extract_via_vlm, get_vlm_config
        
        vlm_used_any = False
        cfg = get_vlm_config()
        vlm_engine_str = f"{cfg.get('provider', 'unknown')} · {cfg.get('model', 'unknown')}"
        legal_diff_pages: list[dict] = []

        import concurrent.futures

        # Step 1: Pre-process pages & run sequential PaddleOCR
        # PaddleOCR is run sequentially to avoid thread-safety issues with its C++ runtime
        page_tasks = []
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                page_tasks.append({"page_index": page_index, "type": "native_text", "text": page_text})
                continue
            
            pix = page.get_pixmap(matrix=_pdf_pixmap_matrix(fitz), alpha=False)
            image_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            
            image = None
            if structure or ocr:
                try:
                    import numpy as np
                    image = np.array(image_pil)[:, :, ::-1].copy()
                except ImportError:
                    notes.append(f"page {page_index}: Numpy is unavailable")
            
            # Get OCR hints first if VLM is enabled
            ocr_hints = None
            extracted_ocr_blocks = None
            if is_vlm_enabled() and ocr is not None and image is not None:
                try:
                    extracted_ocr_blocks, ocr_text = ocr.predict(image, image_pil)
                    if ocr_text.strip():
                        ocr_hints = ocr_text
                except Exception as e:
                    notes.append(f"page {page_index}: Pre-VLM OCR extraction failed ({e})")
            
            page_tasks.append({
                "page_index": page_index, "type": "image", "image_pil": image_pil, "image": image,
                "pix_width": pix.width, "pix_height": pix.height,
                "ocr_hints": ocr_hints, "extracted_ocr_blocks": extracted_ocr_blocks,
                "vlm_blocks": None
            })

        # Step 2: Concurrent VLM Execution
        # VLM is network-bound, so thread pool gives near linear speedup
        if is_vlm_enabled():
            def _run_vlm(task):
                buffered = io.BytesIO()
                task["image_pil"].save(buffered, format="PNG")
                b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                try:
                    return extract_via_vlm(b64, ocr_hints=task["ocr_hints"])
                except Exception as e:
                    return {"_error": str(e)}
            
            vlm_futures = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                for task in page_tasks:
                    if task["type"] == "image":
                        vlm_futures[task["page_index"]] = executor.submit(_run_vlm, task)
            
            for task in page_tasks:
                if task["type"] == "image":
                    res = vlm_futures[task["page_index"]].result()
                    if isinstance(res, dict) and "_error" in res:
                        notes.append(f"page {task['page_index']}: VLM 调用失败 ({res['_error']})。已回退到几何布局提取。")
                    elif res is None:
                        notes.append(f"page {task['page_index']}: VLM 未返回结果 — 请确认 VLM 服务是否已启动。已回退到几何布局提取。")
                    else:
                        task["vlm_blocks"] = res

        # Step 3: Accumulate final layout and text
        for task in page_tasks:
            page_index = task["page_index"]
            if task["type"] == "native_text":
                normalized_text = _normalize_pdf_line_breaks(task["text"])
                full_text.append(normalized_text)
                blocks.append({"page": page_index, "type": "native_text", "text": normalized_text})
                continue
            
            vlm_blocks = task["vlm_blocks"]
            image = task["image"]
            extracted_ocr_blocks = task["extracted_ocr_blocks"]
            ocr_hints = task["ocr_hints"]
            pix_width = task["pix_width"]
            pix_height = task["pix_height"]
            
            if vlm_blocks is not None:
                vlm_used_any = True
                from app.validation import compute_consensus_score, compute_vlm_confidence, validate_legal_fields

                ocr_combined_text = ocr_hints or ""
                if extracted_ocr_blocks:
                    consensus = compute_consensus_score(vlm_blocks, extracted_ocr_blocks, ocr_combined_text)
                    notes.extend(consensus["warnings"])

                page_lines = []
                for idx, el in enumerate(vlm_blocks):
                    txt = el.get("text", "")
                    page_lines.append(txt)
                    bbox = el.get("bbox")
                    if not bbox or len(bbox) != 4 or bbox == [0,0,0,0]:
                        bbox = None
                    blocks.append({
                        "page": page_index, "type": el.get("type", "text"), "structure_type": "text",
                        "text": txt, "bbox": bbox,
                        "confidence": compute_vlm_confidence(el, extracted_ocr_blocks, ocr_combined_text),
                        "reading_order": idx, "hierarchy_level": el.get("hierarchy_level", 4),
                        "parent_id": None, "relations": [], "group_id": el.get("group_id", "single"),
                        "table_html": None,
                    })
                full_text.append(_normalize_pdf_line_breaks("\n".join(page_lines)))

                field_warnings = validate_legal_fields([b for b in blocks if b["page"] == page_index])
                notes.extend(field_warnings)

                ld = _legal_diff_for_vlm_page(vlm_blocks, ocr_combined_text, page_index)
                legal_diff_pages.append(ld)
                if ld.get("has_discrepancy"):
                    notes.append(
                        f"page {page_index}: 案号/金额在 OCR 与 VLM 间不一致（见「关键字段 OCR/VLM 对照」）"
                    )
                continue

            if image is None:
                continue

            if structure:
                try:
                    structure_result = structure(image)
                    struct_blocks = _blocks_from_structure_result(page_index, structure_result, float(pix_width), float(pix_height))
                    if struct_blocks:
                        _analyze_spatial_relations(struct_blocks, float(pix_width), float(pix_height))
                        page_texts = [b["text"] for b in struct_blocks if b["text"] and b.get("type") not in ("header", "footer")]
                        full_text.append("\n".join(page_texts))
                        blocks.extend(struct_blocks)
                        continue
                except Exception:
                    notes.append(f"structure parse failed on page {page_index}; fell back to OCR")

            if not ocr:
                notes.append(f"page {page_index}: PaddleOCR unavailable")
                continue

            if extracted_ocr_blocks is not None:
                for idx, el in enumerate(extracted_ocr_blocks):
                    blocks.append({
                        "page": page_index, "type": "text", "structure_type": "text",
                        "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                        "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                        "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                        "cross_validation": el.get("cross_validation"),
                    })
                if ocr_hints:
                    full_text.append(ocr_hints)
            else:
                try:
                    extracted_blocks, normalized = ocr.predict(image, image_pil)
                    full_text.append(normalized)
                    for idx, el in enumerate(extracted_blocks):
                        blocks.append({
                            "page": page_index, "type": "text", "structure_type": "text",
                            "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                            "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                            "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                            "cross_validation": el.get("cross_validation"),
                        })
                except Exception as exc:
                    notes.append(f"page {page_index}: OCR failed ({exc})")

        page_infos = []
        for page_index, page in enumerate(doc, start=1):
            rect = page.rect
            pix = page.get_pixmap(matrix=_pdf_pixmap_matrix(fitz), alpha=False)
            image_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
            page_infos.append({
                "page": page_index,
                "width": rect.width,
                "height": rect.height,
                "image_data": image_data,
                "columns": None,
                "layout_type": None,
            })

        from app.validation import merge_legal_field_page_diffs

        # Aggregate OCR hint blocks from all VLM-processed pages for cross-validation summary
        _pdf_ocr_hint_blocks: list[dict] = []
        for task in page_tasks:
            if task.get("type") == "image" and task.get("vlm_blocks") is not None:
                _pdf_ocr_hint_blocks.extend(task.get("extracted_ocr_blocks") or [])
        _pdf_cv_summary = compute_cross_validation_summary(_pdf_ocr_hint_blocks) if _pdf_ocr_hint_blocks else None

        return {
            "pages": len(doc),
            "text": "\n\n".join(part for part in full_text if part),
            "blocks": blocks,
            "notes": notes,
            "page_infos": page_infos,
            "vlm_used": vlm_used_any,
            "vlm_engine": vlm_engine_str if vlm_used_any else None,
            "legal_field_diffs": merge_legal_field_page_diffs(legal_diff_pages)
            if (vlm_used_any and legal_diff_pages)
            else None,
            # Cross-validation from OCR hint blocks (only relevant when VLM ran over them)
            "cross_validation_summary": _pdf_cv_summary,
        }

    def extract_stream(
        self, raw: bytes, filename: str, suffix: str, mime_type: str
    ) -> Generator[str, None, None]:
        """Generator yielding SSE-formatted progress events during extraction."""
        try:
            if suffix == ".txt" or mime_type == "text/plain":
                yield sse_format(ProgressEvent(
                    stage="upload_received", message=f"Text file detected: {filename}", progress=0.05,
                ))
                result = self._extract_text(raw, [])
                yield sse_format(ProgressEvent(
                    stage="complete", message="Text extraction complete", progress=1.0,
                    extra={"result": result},
                ))
                return

            if suffix == ".pdf" or mime_type == "application/pdf":
                yield from self._extract_pdf_stream(raw, filename)
                return

            yield from self._extract_image_stream(raw, filename)

        except Exception as exc:
            yield sse_format(ProgressEvent(
                stage="error", message=str(exc), progress=0.0,
                extra={"filename": filename},
            ))

    def _extract_image_stream(
        self, raw: bytes, filename: str
    ) -> Generator[str, None, None]:
        try:
            from PIL import Image
        except ImportError:
            yield sse_format(ProgressEvent(
                stage="error", message="Pillow is not installed", progress=0.0,
            ))
            return

        try:
            image_pil = Image.open(io.BytesIO(raw)).convert("RGB")
            buffered = io.BytesIO()
            image_pil.save(buffered, format="PNG")
            image_data = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
        except Exception:
            yield sse_format(ProgressEvent(
                stage="error", message="Could not open image file", progress=0.0,
            ))
            return

        notes: list[str] = []
        w, h = image_pil.size

        yield sse_format(ProgressEvent(
            stage="model_loading", message="Loading OCR models...", progress=0.1,
        ))

        ocr = self._load_ocr()
        structure = self._load_structure()
        from app.vlm import is_vlm_enabled, extract_via_vlm

        image = None
        if structure or ocr:
            try:
                import numpy as np
                image = np.array(image_pil)[:, :, ::-1].copy()
            except ImportError:
                notes.append("Numpy is not installed; OCR/Structure fallback unavailable.")

        # VLM attempt (same pre-OCR as sync path: hints + blocks for dual-engine consensus)
        if is_vlm_enabled() and image_data:
            ocr_hints = None
            extracted_ocr_blocks = None
            _cv_hint_summary_stream = None
            if ocr is not None and image is not None:
                try:
                    extracted_ocr_blocks, ocr_text = ocr.predict(image, image_pil)
                    if ocr_text.strip():
                        ocr_hints = ocr_text
                    _cv_hint_summary_stream = compute_cross_validation_summary(extracted_ocr_blocks)
                except Exception:
                    pass

            yield sse_format(ProgressEvent(
                stage="page_vlm_start", message="VLM analyzing image...", page=1, total_pages=1,
                progress=0.2, engine="vlm",
            ))

            try:
                b64_stripped = image_data.split(",", 1)[-1] if "," in image_data else image_data
                vlm_blocks = extract_via_vlm(b64_stripped, ocr_hints=ocr_hints)
            except Exception as e:
                vlm_blocks = None
                notes.append(f"VLM 调用失败: {e}。已自动回退到几何布局提取。")

            if vlm_blocks is not None:
                from app.vlm import get_vlm_config
                from app.validation import (
                    compute_consensus_score,
                    compute_vlm_confidence,
                    merge_legal_field_page_diffs,
                    validate_legal_fields,
                )

                cfg = get_vlm_config()
                engine_str = f"{cfg.get('provider', 'unknown')} · {cfg.get('model', 'unknown')}"

                ocr_combined_text = ocr_hints or ""
                if extracted_ocr_blocks:
                    consensus = compute_consensus_score(vlm_blocks, extracted_ocr_blocks, ocr_combined_text)
                    notes.extend(consensus["warnings"])

                blocks = []
                for idx, el in enumerate(vlm_blocks):
                    txt = el.get("text", "")
                    bbox = el.get("bbox")
                    if not bbox or len(bbox) != 4 or bbox == [0, 0, 0, 0]:
                        bbox = None
                    blocks.append({
                        "page": 1, "type": el.get("type", "text"), "structure_type": "text",
                        "text": txt, "bbox": bbox,
                        "confidence": compute_vlm_confidence(
                            el, extracted_ocr_blocks or [], ocr_combined_text
                        ),
                        "reading_order": idx, "hierarchy_level": el.get("hierarchy_level", 4),
                        "parent_id": None, "relations": [], "group_id": el.get("group_id", "single"),
                        "table_html": None,
                    })

                field_warnings = validate_legal_fields(blocks)
                notes.extend(field_warnings)

                page_diff = _legal_diff_for_vlm_page(vlm_blocks, ocr_combined_text, 1)
                if page_diff.get("has_discrepancy"):
                    notes.append(
                        "案号/金额：OCR 与 VLM 不一致，请查看下方「关键字段 OCR/VLM 对照」。"
                    )

                result = {
                    "pages": 1, "text": "\n".join([b["text"] for b in blocks]),
                    "blocks": blocks, "notes": notes,
                    "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                    "vlm_used": True, "vlm_engine": engine_str,
                    "legal_field_diffs": merge_legal_field_page_diffs([page_diff]),
                    "cross_validation_summary": _cv_hint_summary_stream,
                }

                yield sse_format(ProgressEvent(
                    stage="page_vlm_done", message="VLM extraction complete", page=1, total_pages=1,
                    progress=0.9, engine="vlm",
                ))
                yield sse_format(ProgressEvent(
                    stage="complete", message="Extraction complete", progress=1.0,
                    extra={"result": result},
                ))
                return

            yield sse_format(ProgressEvent(
                stage="ocr_fallback", message="VLM unavailable, falling back to OCR...", page=1, total_pages=1,
                progress=0.5, engine="ocr",
            ))

        # Structure fallback
        if structure and image is not None:
            yield sse_format(ProgressEvent(
                stage="structure_fallback", message="Running PPStructure layout analysis...", page=1, total_pages=1,
                progress=0.5, engine="structure",
            ))
            try:
                structure_result = structure(image)
                struct_blocks = _blocks_from_structure_result(1, structure_result, float(w), float(h))
                if struct_blocks:
                    _analyze_spatial_relations(struct_blocks, float(w), float(h))
                    page_texts = [b["text"] for b in struct_blocks if b["text"] and b.get("type") not in ("header", "footer")]
                    result = {
                        "pages": 1, "text": "\n".join(page_texts), "blocks": struct_blocks, "notes": notes,
                        "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                        "vlm_used": False, "vlm_engine": None,
                    }
                    yield sse_format(ProgressEvent(
                        stage="complete", message="Structure extraction complete", progress=1.0,
                        extra={"result": result},
                    ))
                    return
            except Exception as e:
                notes.append(f"structure parse failed; fell back to OCR ({e})")

        # Geometric OCR fallback
        if ocr is not None and image is not None:
            yield sse_format(ProgressEvent(
                stage="ocr_fallback", message="Running geometric OCR...", page=1, total_pages=1,
                progress=0.6, engine="ocr",
            ))
            try:
                extracted_blocks, text = ocr.predict(image, image_pil)
                blocks = []
                for idx, el in enumerate(extracted_blocks):
                    blocks.append({
                        "page": 1, "type": "text", "structure_type": "text",
                        "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                        "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                        "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                        "cross_validation": el.get("cross_validation"),
                    })
                result = {
                    "pages": 1, "text": text, "blocks": blocks, "notes": notes,
                    "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                    "vlm_used": False, "vlm_engine": None,
                    "cross_validation_summary": compute_cross_validation_summary(blocks),
                }
                yield sse_format(ProgressEvent(
                    stage="complete", message="OCR extraction complete", progress=1.0,
                    extra={"result": result},
                ))
                return
            except Exception as exc:
                notes.append(f"OCR failed ({exc})")

        # Empty result
        result = {
            "pages": 1, "text": "", "blocks": [], "notes": notes,
            "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
            "vlm_used": False, "vlm_engine": None,
        }
        yield sse_format(ProgressEvent(
            stage="complete", message="Extraction complete (no content extracted)", progress=1.0,
            extra={"result": result},
        ))

    def _extract_pdf_stream(self, raw: bytes, filename: str) -> Generator[str, None, None]:
        try:
            import fitz
        except ImportError:
            yield sse_format(ProgressEvent(
                stage="error", message="PyMuPDF is not installed; cannot process PDF files.", progress=0.0,
            ))
            return

        try:
            from PIL import Image
        except ImportError:
            yield sse_format(ProgressEvent(
                stage="error", message="Pillow is not installed; cannot process PDF pages.", progress=0.0,
            ))
            return

        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception:
            yield sse_format(ProgressEvent(
                stage="error", message="Could not open PDF file; the file may be corrupted or invalid.", progress=0.0,
            ))
            return

        total_pages = len(doc)
        notes: list[str] = []
        blocks: list[dict] = []
        full_text: list[str] = []

        yield sse_format(ProgressEvent(
            stage="upload_received", message=f"PDF detected: {filename} ({total_pages} pages)", progress=0.05,
            total_pages=total_pages,
        ))

        yield sse_format(ProgressEvent(
            stage="model_loading", message="Loading OCR models...", progress=0.1,
            total_pages=total_pages,
        ))

        ocr = self._load_ocr()
        structure = self._load_structure()
        from app.vlm import is_vlm_enabled, extract_via_vlm, get_vlm_config

        vlm_used_any = False
        cfg = get_vlm_config()
        vlm_engine_str = f"{cfg.get('provider', 'unknown')} · {cfg.get('model', 'unknown')}"
        legal_diff_pages: list[dict] = []

        # Step 1: Pre-process pages sequentially
        page_tasks = []
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                yield sse_format(ProgressEvent(
                    stage="page_native_text", message=f"Page {page_index}/{total_pages}: native text extracted",
                    page=page_index, total_pages=total_pages,
                    progress=0.1 + (page_index / total_pages) * 0.2, engine="native_text",
                ))
                page_tasks.append({"page_index": page_index, "type": "native_text", "text": page_text})
                continue

            pix = page.get_pixmap(matrix=_pdf_pixmap_matrix(fitz), alpha=False)
            image_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            image = None
            if structure or ocr:
                try:
                    import numpy as np
                    image = np.array(image_pil)[:, :, ::-1].copy()
                except ImportError:
                    notes.append(f"page {page_index}: Numpy is unavailable")

            ocr_hints = None
            extracted_ocr_blocks = None
            if is_vlm_enabled() and ocr is not None and image is not None:
                try:
                    extracted_ocr_blocks, ocr_text = ocr.predict(image, image_pil)
                    if ocr_text.strip():
                        ocr_hints = ocr_text
                except Exception as e:
                    notes.append(f"page {page_index}: Pre-VLM OCR extraction failed ({e})")

            yield sse_format(ProgressEvent(
                stage="page_ocr_done", message=f"Page {page_index}/{total_pages}: OCR hints extracted",
                page=page_index, total_pages=total_pages,
                progress=0.1 + (page_index / total_pages) * 0.25, engine="ocr",
            ))

            page_tasks.append({
                "page_index": page_index, "type": "image", "image_pil": image_pil, "image": image,
                "pix_width": pix.width, "pix_height": pix.height,
                "ocr_hints": ocr_hints, "extracted_ocr_blocks": extracted_ocr_blocks,
                "vlm_blocks": None,
            })

        # Step 2: Concurrent VLM
        if is_vlm_enabled():
            import concurrent.futures

            def _run_vlm(task):
                buffered = io.BytesIO()
                task["image_pil"].save(buffered, format="PNG")
                b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                try:
                    return extract_via_vlm(b64, ocr_hints=task["ocr_hints"])
                except Exception as e:
                    return {"_error": str(e)}

            vlm_futures = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                for task in page_tasks:
                    if task["type"] == "image":
                        vlm_futures[task["page_index"]] = executor.submit(_run_vlm, task)

            for task in page_tasks:
                if task["type"] == "image":
                    pi = task["page_index"]
                    yield sse_format(ProgressEvent(
                        stage="page_vlm_start", message=f"Page {pi}/{total_pages}: VLM analyzing...",
                        page=pi, total_pages=total_pages,
                        progress=0.35 + (pi / total_pages) * 0.4, engine="vlm",
                    ))
                    res = vlm_futures[pi].result()
                    if isinstance(res, dict) and "_error" in res:
                        notes.append(f"page {pi}: VLM 调用失败 ({res['_error']})。已回退到几何布局提取。")
                    elif res is None:
                        notes.append(f"page {pi}: VLM 未返回结果 — 请确认 VLM 服务是否已启动。已回退到几何布局提取。")
                    else:
                        task["vlm_blocks"] = res
                        vlm_used_any = True

                    yield sse_format(ProgressEvent(
                        stage="page_vlm_done", message=f"Page {pi}/{total_pages}: VLM analysis complete",
                        page=pi, total_pages=total_pages,
                        progress=0.35 + ((pi + 0.5) / total_pages) * 0.4, engine="vlm",
                    ))

        # Step 3: Accumulate results
        for task in page_tasks:
            page_index = task["page_index"]
            if task["type"] == "native_text":
                normalized_text = _normalize_pdf_line_breaks(task["text"])
                full_text.append(normalized_text)
                blocks.append({"page": page_index, "type": "native_text", "text": normalized_text})
                continue

            vlm_blocks = task["vlm_blocks"]
            image = task["image"]
            extracted_ocr_blocks = task["extracted_ocr_blocks"]
            ocr_hints = task["ocr_hints"]
            pix_width = task["pix_width"]
            pix_height = task["pix_height"]

            if vlm_blocks is not None:
                from app.validation import compute_consensus_score, compute_vlm_confidence, validate_legal_fields

                ocr_combined_text = ocr_hints or ""
                if extracted_ocr_blocks:
                    consensus = compute_consensus_score(vlm_blocks, extracted_ocr_blocks, ocr_combined_text)
                    notes.extend(consensus["warnings"])

                for idx, el in enumerate(vlm_blocks):
                    txt = el.get("text", "")
                    bbox = el.get("bbox")
                    if not bbox or len(bbox) != 4 or bbox == [0, 0, 0, 0]:
                        bbox = None
                    blocks.append({
                        "page": page_index, "type": el.get("type", "text"), "structure_type": "text",
                        "text": txt, "bbox": bbox,
                        "confidence": compute_vlm_confidence(el, extracted_ocr_blocks, ocr_combined_text),
                        "reading_order": idx, "hierarchy_level": el.get("hierarchy_level", 4),
                        "parent_id": None, "relations": [], "group_id": el.get("group_id", "single"),
                        "table_html": None,
                    })
                full_text.append(_normalize_pdf_line_breaks("\n".join([el.get("text", "") for el in vlm_blocks])))

                field_warnings = validate_legal_fields([b for b in blocks if b["page"] == page_index])
                notes.extend(field_warnings)

                ld = _legal_diff_for_vlm_page(vlm_blocks, ocr_combined_text, page_index)
                legal_diff_pages.append(ld)
                if ld.get("has_discrepancy"):
                    notes.append(
                        f"page {page_index}: 案号/金额在 OCR 与 VLM 间不一致（见「关键字段 OCR/VLM 对照」）"
                    )
                continue

            if image is None:
                continue

            if structure:
                try:
                    structure_result = structure(image)
                    struct_blocks = _blocks_from_structure_result(page_index, structure_result, float(pix_width), float(pix_height))
                    if struct_blocks:
                        _analyze_spatial_relations(struct_blocks, float(pix_width), float(pix_height))
                        page_texts = [b["text"] for b in struct_blocks if b["text"] and b.get("type") not in ("header", "footer")]
                        full_text.append("\n".join(page_texts))
                        blocks.extend(struct_blocks)
                        continue
                except Exception:
                    notes.append(f"structure parse failed on page {page_index}; fell back to OCR")

            if not ocr:
                notes.append(f"page {page_index}: PaddleOCR unavailable")
                continue

            if extracted_ocr_blocks is not None:
                for idx, el in enumerate(extracted_ocr_blocks):
                    blocks.append({
                        "page": page_index, "type": "text", "structure_type": "text",
                        "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                        "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                        "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                        "cross_validation": el.get("cross_validation"),
                    })
                if ocr_hints:
                    full_text.append(ocr_hints)
            else:
                try:
                    extracted_blocks, normalized = ocr.predict(image, image_pil)
                    full_text.append(normalized)
                    for idx, el in enumerate(extracted_blocks):
                        blocks.append({
                            "page": page_index, "type": "text", "structure_type": "text",
                            "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                            "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                            "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                            "cross_validation": el.get("cross_validation"),
                        })
                except Exception as exc:
                    notes.append(f"page {page_index}: OCR failed ({exc})")

        page_infos = []
        for page_index, page in enumerate(doc, start=1):
            rect = page.rect
            pix = page.get_pixmap(matrix=_pdf_pixmap_matrix(fitz), alpha=False)
            image_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
            page_infos.append({
                "page": page_index, "width": rect.width, "height": rect.height,
                "image_data": image_data, "columns": None, "layout_type": None,
            })

        from app.validation import merge_legal_field_page_diffs

        # When VLM ran, final blocks are VLM blocks (no cross_validation field).
        # Use OCR hint blocks for the summary instead.
        _stream_ocr_hint_blocks: list[dict] = []
        for _t in page_tasks:
            if _t.get("type") == "image" and _t.get("vlm_blocks") is not None:
                _stream_ocr_hint_blocks.extend(_t.get("extracted_ocr_blocks") or [])
        _stream_cv_summary = (
            compute_cross_validation_summary(_stream_ocr_hint_blocks)
            if _stream_ocr_hint_blocks
            else compute_cross_validation_summary(blocks)
        )

        result = {
            "pages": len(doc),
            "text": "\n\n".join(part for part in full_text if part),
            "blocks": blocks, "notes": notes, "page_infos": page_infos,
            "vlm_used": vlm_used_any,
            "vlm_engine": vlm_engine_str if vlm_used_any else None,
            "legal_field_diffs": merge_legal_field_page_diffs(legal_diff_pages)
            if (vlm_used_any and legal_diff_pages)
            else None,
            "cross_validation_summary": _stream_cv_summary,
        }

        yield sse_format(ProgressEvent(
            stage="complete", message=f"Extraction complete: {len(doc)} pages, {len(blocks)} blocks",
            page=total_pages, total_pages=total_pages, progress=1.0,
            extra={"result": result},
        ))
