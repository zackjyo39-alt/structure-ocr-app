from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image


@dataclass
class OCRBlock:
    page: int
    type: str
    text: str
    bbox: list[float] | None = None
    confidence: float | None = None


class DocumentExtractor:
    def __init__(self) -> None:
        self._ocr = None
        self._structure = None

    def _load_ocr(self):
        if self._ocr is not None:
            return self._ocr
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        except Exception:
            self._ocr = False
        return self._ocr

    def _load_structure(self):
        if self._structure is not None:
            return self._structure
        try:
            from paddleocr import PPStructure

            self._structure = PPStructure(show_log=False, lang="ch")
        except Exception:
            self._structure = False
        return self._structure

    def extract(self, raw: bytes, filename: str, suffix: str, mime_type: str) -> dict:
        notes: list[str] = []
        if suffix == ".pdf" or mime_type == "application/pdf":
            return self._extract_pdf(raw, notes)
        return self._extract_image(raw, notes)

    def _extract_image(self, raw: bytes, notes: list[str]) -> dict:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        ocr = self._load_ocr()
        blocks: list[dict] = []
        text = ""
        if not ocr:
            notes.append("PaddleOCR is not installed; returning image metadata only.")
            return {"pages": 1, "text": "", "blocks": blocks, "notes": notes}
        result = ocr.ocr(image, cls=True)
        page_text = []
        for line in result[0] if result and len(result) > 0 else []:
            bbox, (txt, score) = line
            page_text.append(txt)
            blocks.append(
                {
                    "page": 1,
                    "type": "text",
                    "text": txt,
                    "bbox": [float(v) for point in bbox for v in point],
                    "confidence": float(score),
                }
            )
        text = "\n".join(page_text)
        return {"pages": 1, "text": text, "blocks": blocks, "notes": notes}

    def _extract_pdf(self, raw: bytes, notes: list[str]) -> dict:
        doc = fitz.open(stream=raw, filetype="pdf")
        blocks: list[dict] = []
        full_text: list[str] = []
        ocr = self._load_ocr()
        structure = self._load_structure()
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text").strip()
            if page_text:
                full_text.append(page_text)
                blocks.append({"page": page_index, "type": "native_text", "text": page_text})
                continue

            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            if structure:
                try:
                    structure_result = structure(image)
                    structured_text = []
                    for item in structure_result or []:
                        item_type = item.get("type", "structure")
                        res = item.get("res") or {}
                        if isinstance(res, dict):
                            content = res.get("text") or res.get("html") or str(res)
                        else:
                            content = str(res)
                        structured_text.append(content)
                        blocks.append(
                            {
                                "page": page_index,
                                "type": item_type,
                                "text": content,
                                "bbox": item.get("bbox"),
                            }
                        )
                    if structured_text:
                        full_text.append("\n".join(structured_text))
                        continue
                except Exception:
                    notes.append(f"structure parse failed on page {page_index}; fell back to OCR")

            if not ocr:
                notes.append(f"page {page_index}: PaddleOCR unavailable")
                continue

            try:
                result = ocr.ocr(image, cls=True)
                page_lines = []
                for line in result[0] if result and len(result) > 0 else []:
                    bbox, (txt, score) = line
                    page_lines.append(txt)
                    blocks.append(
                        {
                            "page": page_index,
                            "type": "text",
                            "text": txt,
                            "bbox": [float(v) for point in bbox for v in point],
                            "confidence": float(score),
                        }
                    )
                full_text.append("\n".join(page_lines))
            except Exception as exc:
                notes.append(f"page {page_index}: OCR failed ({exc})")
        return {
            "pages": len(doc),
            "text": "\n\n".join(part for part in full_text if part),
            "blocks": blocks,
            "notes": notes,
        }

