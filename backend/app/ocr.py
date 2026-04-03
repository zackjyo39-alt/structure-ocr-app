from __future__ import annotations

import io
import json
import os
import re
import base64
from dataclasses import dataclass, field
from typing import Generator


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
        try:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_textline_orientation=True, lang="ch")
        except Exception:
            self._ocr = False
        return self._ocr

    def _load_structure(self):
        if self._structure is not None:
            return self._structure
        try:
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
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
        if is_vlm_enabled() and ocr is not None and image is not None:
            try:
                try:
                    result = ocr.ocr(image, cls=True)
                except TypeError:
                    result = ocr.ocr(image)
                res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                extracted_ocr_blocks, ocr_text = _reconstruct_layout(res_data)
                if ocr_text.strip():
                    ocr_hints = ocr_text
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
            from app.validation import compute_consensus_score, compute_vlm_confidence, validate_legal_fields

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

            return {
                "pages": 1,
                "text": "\n".join([b["text"] for b in blocks]),
                "blocks": blocks,
                "notes": notes,
                "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                "vlm_used": True,
                "vlm_engine": engine_str,
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
                    }
                )
        else:
            try:
                try:
                    result = ocr.ocr(image, cls=True)
                except TypeError:
                    result = ocr.ocr(image)
                res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                extracted_blocks, text = _reconstruct_layout(res_data)
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
        
        import concurrent.futures
        
        # Step 1: Pre-process pages & run sequential PaddleOCR
        # PaddleOCR is run sequentially to avoid thread-safety issues with its C++ runtime
        page_tasks = []
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                page_tasks.append({"page_index": page_index, "type": "native_text", "text": page_text})
                continue
            
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
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
                    try:
                        result = ocr.ocr(image, cls=True)
                    except TypeError:
                        result = ocr.ocr(image)
                    res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                    extracted_ocr_blocks, ocr_text = _reconstruct_layout(res_data)
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
                    })
                if ocr_hints:
                    full_text.append(ocr_hints)
            else:
                try:
                    try:
                        result = ocr.ocr(image, cls=True)
                    except TypeError:
                        result = ocr.ocr(image)
                    res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                    extracted_blocks, normalized = _reconstruct_layout(res_data)
                    full_text.append(normalized)
                    for idx, el in enumerate(extracted_blocks):
                        blocks.append({
                            "page": page_index, "type": "text", "structure_type": "text",
                            "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                            "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                            "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                        })
                except Exception as exc:
                    notes.append(f"page {page_index}: OCR failed ({exc})")

        page_infos = []
        for page_index, page in enumerate(doc, start=1):
            rect = page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
            page_infos.append({
                "page": page_index,
                "width": rect.width,
                "height": rect.height,
                "image_data": image_data,
                "columns": None,
                "layout_type": None,
            })

        return {
            "pages": len(doc),
            "text": "\n\n".join(part for part in full_text if part),
            "blocks": blocks,
            "notes": notes,
            "page_infos": page_infos,
            "vlm_used": vlm_used_any,
            "vlm_engine": vlm_engine_str if vlm_used_any else None,
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

        # VLM attempt
        if is_vlm_enabled() and image_data:
            ocr_hints = None
            if ocr is not None and image is not None:
                try:
                    try:
                        result = ocr.ocr(image, cls=True)
                    except TypeError:
                        result = ocr.ocr(image)
                    res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                    _, ocr_text = _reconstruct_layout(res_data)
                    if ocr_text.strip():
                        ocr_hints = ocr_text
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
                from app.validation import compute_consensus_score, compute_vlm_confidence, validate_legal_fields

                cfg = get_vlm_config()
                engine_str = f"{cfg.get('provider', 'unknown')} · {cfg.get('model', 'unknown')}"

                blocks = []
                for idx, el in enumerate(vlm_blocks):
                    txt = el.get("text", "")
                    bbox = el.get("bbox")
                    if not bbox or len(bbox) != 4 or bbox == [0, 0, 0, 0]:
                        bbox = None
                    blocks.append({
                        "page": 1, "type": el.get("type", "text"), "structure_type": "text",
                        "text": txt, "bbox": bbox,
                        "confidence": compute_vlm_confidence(el, [], ""),
                        "reading_order": idx, "hierarchy_level": el.get("hierarchy_level", 4),
                        "parent_id": None, "relations": [], "group_id": el.get("group_id", "single"),
                        "table_html": None,
                    })

                field_warnings = validate_legal_fields(blocks)
                notes.extend(field_warnings)

                result = {
                    "pages": 1, "text": "\n".join([b["text"] for b in blocks]),
                    "blocks": blocks, "notes": notes,
                    "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                    "vlm_used": True, "vlm_engine": engine_str,
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
                try:
                    result = ocr.ocr(image, cls=True)
                except TypeError:
                    result = ocr.ocr(image)
                res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                extracted_blocks, text = _reconstruct_layout(res_data)
                blocks = []
                for idx, el in enumerate(extracted_blocks):
                    blocks.append({
                        "page": 1, "type": "text", "structure_type": "text",
                        "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                        "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                        "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                    })
                result = {
                    "pages": 1, "text": text, "blocks": blocks, "notes": notes,
                    "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                    "vlm_used": False, "vlm_engine": None,
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

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
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
                    try:
                        result = ocr.ocr(image, cls=True)
                    except TypeError:
                        result = ocr.ocr(image)
                    res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                    extracted_ocr_blocks, ocr_text = _reconstruct_layout(res_data)
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
                    })
                if ocr_hints:
                    full_text.append(ocr_hints)
            else:
                try:
                    try:
                        result = ocr.ocr(image, cls=True)
                    except TypeError:
                        result = ocr.ocr(image)
                    res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                    extracted_blocks, normalized = _reconstruct_layout(res_data)
                    full_text.append(normalized)
                    for idx, el in enumerate(extracted_blocks):
                        blocks.append({
                            "page": page_index, "type": "text", "structure_type": "text",
                            "text": el["text"], "bbox": [float(v) for point in el["bbox"] for v in point],
                            "confidence": el["score"], "reading_order": idx, "hierarchy_level": 4,
                            "parent_id": None, "relations": [], "group_id": "single", "table_html": None,
                        })
                except Exception as exc:
                    notes.append(f"page {page_index}: OCR failed ({exc})")

        page_infos = []
        for page_index, page in enumerate(doc, start=1):
            rect = page.rect
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_data = f"data:image/png;base64,{base64.b64encode(pix.tobytes('png')).decode('utf-8')}"
            page_infos.append({
                "page": page_index, "width": rect.width, "height": rect.height,
                "image_data": image_data, "columns": None, "layout_type": None,
            })

        result = {
            "pages": len(doc),
            "text": "\n\n".join(part for part in full_text if part),
            "blocks": blocks, "notes": notes, "page_infos": page_infos,
            "vlm_used": vlm_used_any,
            "vlm_engine": vlm_engine_str if vlm_used_any else None,
        }

        yield sse_format(ProgressEvent(
            stage="complete", message=f"Extraction complete: {len(doc)} pages, {len(blocks)} blocks",
            page=total_pages, total_pages=total_pages, progress=1.0,
            extra={"result": result},
        ))
