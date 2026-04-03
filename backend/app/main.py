from __future__ import annotations

import hashlib
import io
import json
import re
import base64
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .ocr import DocumentExtractor, sse_format, ProgressEvent
from .vlm import get_vlm_config, set_vlm_config

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
    image_data: str | None = None
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
    vlm_used: bool | None = None
    vlm_engine: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/vlm-config")
def read_vlm_config() -> dict:
    return get_vlm_config()


@app.post("/api/vlm-config")
def update_vlm_config(data: dict) -> dict:
    return set_vlm_config(data)


@app.get("/api/health/ollama")
def check_ollama(base_url: str = Query(default="http://localhost:11434/api/chat")) -> dict:
    """Probe whether the Ollama service is reachable at base_url."""
    # Derive Ollama root URL by stripping /api/* path
    root = re.sub(r"/api/.*$", "", base_url.rstrip("/"))
    if not root.startswith("http"):
        root = "http://localhost:11434"
    try:
        req = urllib.request.Request(
            f"{root}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in body.get("models", [])]
                return {"running": True, "models": models}
    except Exception as e:
        return {"running": False, "error": str(e)}
    return {"running": False}


class SummarizeResponse(BaseModel):
    court: str | None = None
    case_number: str | None = None
    plaintiff_defendant: list[str] = []
    main_ruling: str | None = None
    word_count_estimate: int | None = None


@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize_document(file: UploadFile = File(...)) -> SummarizeResponse:
    """Use the configured VLM to generate a structured document summary."""
    from .vlm import is_vlm_enabled, summarize_via_vlm

    if not is_vlm_enabled():
        raise HTTPException(
            status_code=400,
            detail="VLM is not enabled — go to VLM Config and enable it first.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(
            status_code=400,
            detail="Summarization currently supports image files only (PNG, JPG, WebP).",
        )

    try:
        from PIL import Image
        img_pil = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        img_pil.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read image: {e}")

    result = summarize_via_vlm(b64)
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="VLM summarization failed — check whether the VLM service is running.",
        )

    safe = {k: result.get(k) for k in SummarizeResponse.model_fields}
    return SummarizeResponse(**safe)


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
        vlm_used=result.get("vlm_used"),
        vlm_engine=result.get("vlm_engine"),
    )


@app.post("/api/extract-stream")
async def extract_stream(file: UploadFile = File(...)) -> StreamingResponse:
    raw = await file.read()
    if not raw:
        error_event = sse_format(ProgressEvent(
            stage="error", message="empty file", progress=0.0,
        ))
        return StreamingResponse(iter([error_event]), media_type="text/event-stream")

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        error_event = sse_format(ProgressEvent(
            stage="error",
            message=f"unsupported file type '{suffix}'; supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
            progress=0.0,
        ))
        return StreamingResponse(iter([error_event]), media_type="text/event-stream")

    def event_generator():
        yield sse_format(ProgressEvent(
            stage="upload_received",
            message=f"File received: {file.filename or 'upload'}",
            progress=0.01,
        ))
        yield from extractor.extract_stream(
            raw=raw,
            filename=file.filename or "upload",
            suffix=suffix,
            mime_type=file.content_type or "application/octet-stream",
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
