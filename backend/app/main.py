from __future__ import annotations

import hashlib
import io
import json
import os
import re
import base64
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .ocr import DocumentExtractor, compute_cross_validation_summary, sse_format, ProgressEvent
from .vlm import get_vlm_config, normalize_gemini_base_url, set_vlm_config

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

MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "50"))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", "100"))
OCR_TIMEOUT_SECONDS = float(os.environ.get("OCR_TIMEOUT_SECONDS", "60.0"))
VLM_TIMEOUT_SECONDS = float(os.environ.get("VLM_TIMEOUT_SECONDS", "120.0"))


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
    # 双引擎交叉验证结果（仅 cross_validate 模式下存在）
    cross_validation: dict | None = None


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
    # OCR vs VLM 案号/金额结构化对照（仅 VLM 路径且存在 OCR hint 时）
    legal_field_diffs: dict | None = None
    # 双引擎 OCR 交叉验证汇总（仅 cross_validate 模式）
    cross_validation_summary: dict | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/vlm-config")
def read_vlm_config() -> dict:
    return get_vlm_config()


@app.post("/api/vlm-config")
def update_vlm_config(data: dict) -> dict:
    return set_vlm_config(data)


@app.post("/api/vlm-test")
def test_vlm_connection(data: dict | None = None) -> dict:
    """Test connectivity to the currently configured (or provided) VLM provider."""
    from .vlm import get_vlm_config

    if data:
        cfg = {
            "provider": data.get("provider", "ollama"),
            "model": data.get("model", ""),
            "base_url": data.get("base_url", ""),
            "api_key": data.get("api_key", ""),
        }
    else:
        saved = get_vlm_config()
        cfg = {k: saved.get(k, "") for k in ("provider", "model", "base_url", "api_key")}

    provider = cfg["provider"].lower()
    timeout = 10

    # ── Ollama ──────────────────────────────────────────────────────────────
    if provider == "ollama":
        root = re.sub(r"/api/.*$", "", (cfg["base_url"] or "http://localhost:11434/api/chat").rstrip("/"))
        if not root.startswith("http"):
            root = "http://localhost:11434"
        try:
            req = urllib.request.Request(f"{root}/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in body.get("models", [])]
                model_requested = cfg["model"]
                available = model_requested in models if model_requested else True
                return {
                    "status": "ok" if available else "warning",
                    "message": f"Ollama 连接成功。{len(models)} 个可用模型。" + (f" 模型 '{model_requested}' {'已安装' if available else '未安装，请先 ollama pull'}" if model_requested else ""),
                    "models": models,
                }
        except Exception as e:
            return {"status": "error", "error": f"无法连接 Ollama ({root}): {e}"}

    # ── OpenAI-compatible (OpenAI, NVIDIA NIM, vLLM, etc.) ─────────────────
    if provider in ("openai", "nim"):
        url = cfg["base_url"] or "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1,
        }
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if "choices" in body:
                    return {"status": "ok", "message": f"{provider.upper()} 连接成功，模型 '{cfg['model']}' 可用。"}
                return {"status": "warning", "message": f"收到响应但格式异常: {str(body)[:200]}"}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")[:300]
            return {"status": "error", "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"status": "error", "error": f"无法连接 {provider.upper()} ({url}): {e}"}

    # ── Gemini ──────────────────────────────────────────────────────────────
    if provider == "gemini":
        model = cfg["model"] or "gemini-2.5-flash"
        api_key = cfg["api_key"]
        base_url = normalize_gemini_base_url(cfg.get("base_url", ""))
        url = f"{base_url}/models/{model}?key={api_key}"
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if "error" in body:
                    return {"status": "error", "error": f"Gemini API 错误: {body['error'].get('message', str(body))}"}
                return {"status": "ok", "message": f"Gemini 连接成功，模型 '{model}' 可用。"}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")[:300]
            return {"status": "error", "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            return {"status": "error", "error": f"无法连接 Gemini ({base_url}): {e}"}

    return {"status": "error", "error": f"不支持的 provider: {provider}"}


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
    # AI 去噪后的可读全文（与结构化字段同次 VLM 调用生成）
    readable_transcript: str | None = None


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

    file_size_mb = len(raw) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f}MB exceeds maximum {MAX_FILE_SIZE_MB}MB",
        )

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file type '{suffix}'; supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
        )

    if suffix == ".pdf" and MAX_PDF_PAGES > 0:
        try:
            import fitz
            doc = fitz.open(stream=raw, filetype="pdf")
            page_count = len(doc)
            doc.close()
            if page_count > MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=413,
                    detail=f"PDF has {page_count} pages, exceeds maximum {MAX_PDF_PAGES} pages",
                )
        except Exception:
            pass

    checksum = hashlib.sha256(raw).hexdigest()
    mime_type = file.content_type or "application/octet-stream"

    result = extractor.extract(
        raw=raw,
        filename=file.filename or "upload",
        suffix=suffix,
        mime_type=mime_type,
    )

    blocks_raw = result["blocks"]
    # Prefer pre-computed summary (set by ocr.py when VLM path used OCR hint blocks).
    # Fall back to block-level computation for pure OCR paths.
    cv_summary = result.get("cross_validation_summary") or compute_cross_validation_summary(blocks_raw)
    return ExtractResponse(
        filename=file.filename or "upload",
        mime_type=mime_type,
        checksum=checksum,
        pages=result["pages"],
        text=result["text"],
        blocks=[PageBlock(**block) for block in blocks_raw],
        notes=result["notes"],
        page_infos=[PageInfo(**info) for info in result.get("page_infos", [])],
        vlm_used=result.get("vlm_used"),
        vlm_engine=result.get("vlm_engine"),
        legal_field_diffs=result.get("legal_field_diffs"),
        cross_validation_summary=cv_summary,
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
