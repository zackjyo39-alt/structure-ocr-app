from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
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


class PageBlock(BaseModel):
    page: int
    type: str
    text: str
    bbox: list[float] | None = None
    confidence: float | None = None


class ExtractResponse(BaseModel):
    filename: str
    mime_type: str
    checksum: str
    pages: int
    text: str
    blocks: list[PageBlock]
    notes: list[str]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract", response_model=ExtractResponse)
async def extract(file: UploadFile = File(...)) -> ExtractResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    checksum = hashlib.sha256(raw).hexdigest()
    suffix = Path(file.filename or "upload").suffix.lower()
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
    )

