from __future__ import annotations

import io
import os
import re
import base64
from dataclasses import dataclass, field


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
            
        ocr = self._load_ocr()
        structure = self._load_structure()
        
        if structure or ocr:
            try:
                import numpy as np
                image = np.array(image_pil)[:, :, ::-1].copy()
            except ImportError:
                notes.append("Numpy is not installed; returning image metadata only.")
                return {"pages": 1, "text": "", "blocks": [], "notes": notes, "page_infos": [{"page": 1, "width": float(image_pil.width), "height": float(image_pil.height), "image_data": image_data, "columns": None, "layout_type": None}]}
        blocks: list[dict] = []
        text = ""
        w, h = image_pil.size
        
        if structure:
            try:
                structure_result = structure(image)
                struct_blocks = _blocks_from_structure_result(
                    1, structure_result, float(w), float(h)
                )
                if struct_blocks:
                    _analyze_spatial_relations(struct_blocks, float(w), float(h))
                    page_texts = [b["text"] for b in struct_blocks if b["text"]]
                    return {
                        "pages": 1,
                        "text": "\n".join(page_texts),
                        "blocks": struct_blocks,
                        "notes": notes,
                        "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
                    }
            except Exception as e:
                notes.append(f"structure parse failed; fell back to OCR ({e})")

        if not ocr:
            notes.append("PaddleOCR is not installed; returning image metadata only.")
            return {"pages": 1, "text": "", "blocks": blocks, "notes": notes, "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}]}
            
        try:
            try:
                result = ocr.ocr(image, cls=True)
            except TypeError:
                result = ocr.ocr(image)
            extracted_lines = []
            res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
            if isinstance(res_data, dict):
                res_dict = res_data.get("res", res_data)
                dt_polys = res_dict.get("dt_polys", [])
                rec_texts = res_dict.get("rec_texts", res_dict.get("rec_text", []))
                rec_scores = res_dict.get("rec_scores", res_dict.get("rec_score", []))
                for i in range(len(dt_polys)):
                    bbox = dt_polys[i]
                    txt = rec_texts[i] if i < len(rec_texts) else ""
                    score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                    extracted_lines.append((bbox, (txt, score)))
            else:
                extracted_lines = res_data if res_data else []

            page_text = []
            for line in extracted_lines:
                bbox, (txt, score) = line
                page_text.append(txt)
                blocks.append(
                    {
                        "page": 1,
                        "type": "text",
                        "structure_type": "text",
                        "text": txt,
                        "bbox": [float(v) for point in bbox for v in point],
                        "confidence": float(score),
                        "reading_order": len(page_text) - 1,
                        "hierarchy_level": 4,
                        "parent_id": None,
                        "relations": [],
                        "group_id": "single",
                        "table_html": None,
                    }
                )
            text = "\n".join(page_text)
        except Exception as exc:
            notes.append(f"OCR failed ({exc})")
            text = ""

        return {
            "pages": 1,
            "text": text,
            "blocks": blocks,
            "notes": notes,
            "page_infos": [{"page": 1, "width": float(w), "height": float(h), "image_data": image_data, "columns": None, "layout_type": None}],
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
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                normalized_text = _normalize_pdf_line_breaks(page_text)
                full_text.append(normalized_text)
                blocks.append({"page": page_index, "type": "native_text", "text": normalized_text})
                continue

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            
            if structure or ocr:
                try:
                    import numpy as np
                    image = np.array(image_pil)[:, :, ::-1].copy()
                except ImportError:
                    notes.append(f"page {page_index}: Numpy is unavailable")
                    continue

            if structure:
                try:
                    structure_result = structure(image)
                    struct_blocks = _blocks_from_structure_result(
                        page_index, structure_result, float(pix.width), float(pix.height)
                    )
                    if struct_blocks:
                        _analyze_spatial_relations(struct_blocks, float(pix.width), float(pix.height))
                        page_texts = [b["text"] for b in struct_blocks if b["text"]]
                        full_text.append("\n".join(page_texts))
                        blocks.extend(struct_blocks)
                        continue
                except Exception:
                    notes.append(f"structure parse failed on page {page_index}; fell back to OCR")

            if not ocr:
                notes.append(f"page {page_index}: PaddleOCR unavailable")
                continue

            try:
                try:
                    result = ocr.ocr(image, cls=True)
                except TypeError:
                    result = ocr.ocr(image)
                page_lines: list[str] = []
                scores: list[float] = []
                res_data = result[0] if result and isinstance(result, (list, tuple)) and len(result) > 0 else result
                extracted_lines = []
                if isinstance(res_data, dict):
                    res_dict = res_data.get("res", res_data)
                    dt_polys = res_dict.get("dt_polys", [])
                    rec_texts = res_dict.get("rec_texts", res_dict.get("rec_text", []))
                    rec_scores = res_dict.get("rec_scores", res_dict.get("rec_score", []))
                    for i in range(len(dt_polys)):
                        bbox = dt_polys[i]
                        txt = rec_texts[i] if i < len(rec_texts) else ""
                        score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                        extracted_lines.append((bbox, (txt, score)))
                else:
                    extracted_lines = res_data if res_data else []

                for line in extracted_lines:
                    bbox, (txt, score) = line
                    page_lines.append(txt)
                    scores.append(float(score))
                normalized = _normalize_pdf_line_breaks("\n".join(page_lines))
                avg_conf = sum(scores) / len(scores) if scores else None
                full_text.append(normalized)
                fallback_blocks = _blocks_from_normalized_page_text(page_index, normalized, confidence=avg_conf)
                for fb in fallback_blocks:
                    fb.update({
                        "structure_type": "text",
                        "reading_order": None,
                        "hierarchy_level": 4,
                        "parent_id": None,
                        "relations": [],
                        "group_id": "single",
                        "table_html": None,
                    })
                blocks.extend(fallback_blocks)
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
        }
