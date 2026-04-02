from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .ocr import DocumentExtractor

app = FastAPI(title="PaddleOCR Web App")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = DocumentExtractor()
SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}


class PageBlock(BaseModel):
    page: int
    type: str
    text: str
    bbox: list[float] | None = None
    confidence: float | None = None
    structure_type: str | None = None
    reading_order: int | None = None
    hierarchy_level: int | None = None
    parent_id: str | None = None
    relations: list[str] | None = None
    group_id: str | None = None
    table_html: str | None = None


class PageInfo(BaseModel):
    page: int
    width: float | None = None
    height: float | None = None
    columns: int | None = None
    layout_type: str | None = None


class ExtractResponse(BaseModel):
    filename: str
    mime_type: str
    checksum: str
    pages: int
    text: str
    blocks: list[PageBlock]
    notes: list[str]
    page_infos: list[PageInfo] = []


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type '{suffix}'; supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
        )

    checksum = hashlib.sha256(raw).hexdigest()
    mime_type = file.content_type or "application/octet-stream"

    result = extractor.extract(
        raw=raw,
        filename=file.filename or "upload",
        suffix=suffix,
        mime_type=mime_type,
    )

    return ExtractResponse(
        filename=file.filename or "upload",
        mime_type=mime_type,
        checksum=checksum,
        pages=result["pages"],
        text=result["text"],
        blocks=[PageBlock(**block) for block in result["blocks"]],
        notes=result["notes"],
        page_infos=[PageInfo(**info) for info in result.get("page_infos", [])],
    )
