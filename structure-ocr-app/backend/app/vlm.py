"""
Pluggable Vision-Language Model (VLM) extraction layer.

Supports:
  - Ollama (local, e.g. llava, llama3.2-vision)
  - OpenAI-compatible (OpenAI, NVIDIA NIM, vLLM, DeepSeek)
  - Google Gemini

Runtime configuration is stored in-memory and can be changed via the
/api/vlm-config REST endpoint without restarting the server.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def normalize_gemini_base_url(base_url: str) -> str:
    """Normalize stored base_url to Generative Language API root (v1 / v1beta / custom host)."""
    u = (base_url or "").strip().rstrip("/")
    if not u:
        return "https://generativelanguage.googleapis.com/v1beta"
    # User pasted a full resource URL by mistake
    if "/models/" in u:
        u = u.split("/models/", 1)[0].rstrip("/")
    return u or "https://generativelanguage.googleapis.com/v1beta"


# ---------------------------------------------------------------------------
# Runtime configuration (thread-safe singleton)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "vlm_config.json")

def _load_config_from_disk() -> dict:
    default_cfg = {
        "enabled": os.getenv("VLM_ENABLED", "false").lower() == "true",
        "provider": os.getenv("VLM_PROVIDER", "ollama"),
        "model": os.getenv("VLM_MODEL", "llava"),
        "base_url": os.getenv("VLM_BASE_URL", "http://localhost:11434/api/chat"),
        "api_key": os.getenv("VLM_API_KEY", ""),
    }
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception as e:
            logger.error(f"Failed to load {_CONFIG_FILE}: {e}")
    return default_cfg

def _save_config_to_disk(cfg: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save {_CONFIG_FILE}: {e}")

_config: dict = _load_config_from_disk()

PROVIDER_PRESETS: dict[str, dict] = {
    # ── Ollama (local) ─────────────────────────────────────────────────────
    "ollama-llava": {
        "provider": "ollama",
        "model": "llava",
        "base_url": "http://localhost:11434/api/chat",
        "api_key": "",
        "label": "Ollama · LLaVA (Local)",
        "description": "经典多模态模型，适合快速本地测试。需先运行 ollama pull llava",
    },
    "ollama-llama-vision": {
        "provider": "ollama",
        "model": "llama3.2-vision",
        "base_url": "http://localhost:11434/api/chat",
        "api_key": "",
        "label": "Ollama · Llama 3.2 Vision (Local)",
        "description": "Meta 官方视觉模型，OCR 质量优于 LLaVA。需先运行 ollama pull llama3.2-vision",
    },
    # ── NVIDIA NIM (cloud, OpenAI-compatible) ──────────────────────────────
    # Endpoint: https://integrate.api.nvidia.com/v1/chat/completions
    # 需要在 build.nvidia.com 申请 API Key
    "nim-llama32-11b": {
        "provider": "openai",
        "model": "meta/llama-3.2-11b-vision-instruct",
        "base_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "api_key": "",
        "label": "NVIDIA NIM · Llama 3.2 Vision 11B",
        "description": "轻量云端推理，适合高并发实时应用。免费额度可在 build.nvidia.com 申请",
    },
    "nim-llama32-90b": {
        "provider": "openai",
        "model": "meta/llama-3.2-90b-vision-instruct",
        "base_url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "api_key": "",
        "label": "NVIDIA NIM · Llama 3.2 Vision 90B",
        "description": "高精度大模型，推荐用于复杂文档和知识库 RAG 场景",
    },
    # ── OpenAI ─────────────────────────────────────────────────────────────
    "openai-gpt4o": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "api_key": "",
        "label": "OpenAI · GPT-4o Mini",
        "description": "成本效益最优的 OpenAI 视觉模型，支持高分辨率图片输入",
    },
    "openai-gpt4o-full": {
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "api_key": "",
        "label": "OpenAI · GPT-4o",
        "description": "最高精度，适合高价值文档。价格约为 mini 的 5 倍",
    },
    # ── Google Gemini ──────────────────────────────────────────────────────
    "gemini-25-flash": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "",
        "label": "Google · Gemini 2.5 Flash",
        "description": "当前推荐的 Gemini 主力模型，高吞吐低延迟，支持 100 万 token 上下文",
    },
    "gemini-3-flash": {
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": "",
        "label": "Google · Gemini 3 Flash (Preview)",
        "description": "官方 model code 为 gemini-3-flash-preview；若 404 可尝试将 Base URL 改为 …/v1 或核对 AI Studio 模型列表",
    },
}


def get_vlm_config() -> dict:
    with _lock:
        return {**_config, "presets": PROVIDER_PRESETS}


def set_vlm_config(updates: dict) -> dict:
    with _lock:
        for key in ("enabled", "provider", "model", "base_url", "api_key"):
            if key in updates:
                _config[key] = updates[key]
        _save_config_to_disk(_config)
        return {**_config}


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

def get_vlm_prompt(ocr_hints: str | None = None) -> str:
    base = """You are an ultra-precise Legal Document Structure Extraction AI.
Your ONLY objective is to reconstruct the spatial and semantic layout of the provided image into JSON.

CRITICAL ZERO-HALLUCINATION RULES:
1. Extract ALL visible text with 100.00% accuracy. DO NOT guess, infer, fix typos, or hallucinate characters.
2. In legal contexts (e.g. amounts, dates, IDs, case numbers), changing one character is a catastrophic failure. Copy exactly as seen.
3. Preserve the exact reading order (top-to-bottom, left-to-right within visual boundaries).
4. For `group_id`, use legal-specific classifications if applicable:
   - "court_name" (法院名称)
   - "case_number" (案号)
   - "parties_info" (原被告当事人信息)
   - "cause_of_action" (案由)
   - "fact_and_reasons" (事实与理由)
   - "court_ruling" (法院判决结果/裁定结果)
   - "stamp_signature" (公章/签名/指纹)
   - "heading" / "paragraph" / "table_cell" (general fallback)
5. For bbox, provide approximate pixel coordinates [x1, y1, x2, y2]. If unknown, use [0,0,0,0].

Output ONLY this JSON (no markdown wrappers, no extra commentary):
{
  "blocks": [
    {
      "text": "exact extracted text",
      "type": "text",
      "group_id": "semantic_group",
      "hierarchy_level": 4,
      "bbox": [x1, y1, x2, y2]
    }
  ]
}
"""
    if ocr_hints:
        base += f"\n\n[OCR HINTS]\nThe following text has been extracted by a geometric OCR engine. Use this strictly as a reference to avoid hallucinating complex legal characters, but fix layout ordering based on the image.\n\n<OCR_TEXT>\n{ocr_hints}\n</OCR_TEXT>\n"
    
    return base


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def _parse_vlm_json_response(text: str) -> list[dict] | None:
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```json"):
        text = text[len("```json"):]
    elif text.startswith("```"):
        text = text[len("```"):]
    if text.endswith("```"):
        text = text[:-len("```")]

    try:
        data = json.loads(text.strip())
        if isinstance(data, list):
            return data
        return data.get("blocks", [])
    except Exception as e:
        logger.error(f"Failed to parse VLM JSON response: {e}\nResponse snippet: {text[:500]}")
        return None


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _call_ollama(base64_image: str, cfg: dict, ocr_hints: str | None = None) -> list[dict] | None:
    url = cfg["base_url"] or "http://localhost:11434/api/chat"
    prompt = get_vlm_prompt(ocr_hints)
    payload = {
        "model": cfg["model"],
        "format": "json",
        "stream": False,
        "messages": [
            {"role": "user", "content": prompt, "images": [base64_image]}
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return _parse_vlm_json_response(body.get("message", {}).get("content", ""))
    except Exception as e:
        logger.error(f"Ollama VLM error: {e}")
        return None


def _call_openai(base64_image: str, cfg: dict, ocr_hints: str | None = None) -> list[dict] | None:
    url = cfg["base_url"] or "https://api.openai.com/v1/chat/completions"
    prompt = get_vlm_prompt(ocr_hints)
    payload = {
        "model": cfg["model"],
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ],
            }
        ],
    }
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return _parse_vlm_json_response(body["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"OpenAI-compatible VLM error: {e}")
        return None


def _call_gemini(base64_image: str, cfg: dict, ocr_hints: str | None = None) -> list[dict] | None:
    model = cfg["model"] or "gemini-2.5-flash"
    api_key = cfg["api_key"]
    base_url = normalize_gemini_base_url(cfg.get("base_url", ""))
    prompt = get_vlm_prompt(ocr_hints)
    url = f"{base_url}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inlineData": {"mimeType": "image/png", "data": base64_image}},
                ]
            }
        ],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return _parse_vlm_json_response(body["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:
        logger.error(f"Gemini VLM error: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_vlm_enabled() -> bool:
    with _lock:
        return _config["enabled"]


def extract_via_vlm(base64_image: str, ocr_hints: str | None = None) -> list[dict] | None:
    with _lock:
        cfg = {**_config}

    provider = cfg["provider"].lower()
    if provider == "ollama":
        return _call_ollama(base64_image, cfg, ocr_hints)
    elif provider in ("openai", "nim"):
        return _call_openai(base64_image, cfg, ocr_hints)
    elif provider == "gemini":
        return _call_gemini(base64_image, cfg, ocr_hints)
    else:
        logger.warning(f"Unknown VLM provider: {provider}")
        return None


# ---------------------------------------------------------------------------
# Summary prompt & public API
# ---------------------------------------------------------------------------

VLM_SUMMARY_PROMPT = """You are an expert document analyst. The image may be a legal judgment, a contract, a chat screenshot (e.g. WeChat), or other scans.

MANDATORY LANGUAGE (产品面向中文用户):
- 除非法条、案号、护照号、URL、代码等必须保持原文的片段外，JSON 内所有说明性字符串必须使用「简体中文」书写。
- main_ruling：必须用中文写 2～4 句（核心事实、争议或结论；非法务类则概括图片内容），禁止用英文写该字段。
- plaintiff_defendant：数组内每项用中文表述（人名可与图中一致）。
- readable_transcript：若界面/正文以中文为主，则用中文整理全文；人名、金额、日期、原文引语保持与图中一致，勿翻译成英文。

Goals (zero hallucination on facts; omit only clear UI/OCR junk):
1) Structured fields when applicable (courts, case numbers, parties, ruling summary).
2) readable_transcript: denoised full-body text in natural reading order.

readable_transcript rules:
- Preserve names, amounts, dates, places, and quoted speech exactly as shown; do not invent lines.
- Remove or merge: repeated timestamp-only lines, duplicate system boilerplate, stray OCR fragments (tiny isolated number+quote junk with no semantic role), duplicate avatar labels—unless they carry unique content.
- For chat logs: group by speaker or topic with blank lines between blocks; keep chronological sense.
- Use paragraphs (blank line between topics). If almost no text, use a short honest sentence or empty string.

Return ONLY this JSON object (no markdown fences, no extra text):
{
  "court": "法院全称，无法识别则 null",
  "case_number": "案号原文，无则 null",
  "plaintiff_defendant": ["当事人等，中文"],
  "main_ruling": "2～4 句中文：要点摘要",
  "word_count_estimate": 0,
  "readable_transcript": "去噪后的可读全文，以中文为主时全文中文整理"
}"""


def _summarize_raw_call(base64_image: str, cfg: dict) -> str | None:
    """Call VLM with the summary prompt; return raw response text."""
    provider = cfg["provider"].lower()

    if provider == "ollama":
        url = cfg["base_url"] or "http://localhost:11434/api/chat"
        payload = {
            "model": cfg["model"],
            "format": "json",
            "stream": False,
            "messages": [{"role": "user", "content": VLM_SUMMARY_PROMPT, "images": [base64_image]}],
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama summary error: {e}")
            return None

    elif provider in ("openai", "nim"):
        url = cfg["base_url"] or "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": cfg["model"],
            "response_format": {"type": "json_object"},
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": VLM_SUMMARY_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
                ],
            }],
        }
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"OpenAI summary error: {e}")
            return None

    elif provider == "gemini":
        model = cfg["model"] or "gemini-2.5-flash"
        api_key = cfg["api_key"]
        base_url = normalize_gemini_base_url(cfg.get("base_url", ""))
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [
                {"text": VLM_SUMMARY_PROMPT},
                {"inlineData": {"mimeType": "image/png", "data": base64_image}},
            ]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"Gemini summary error: {e}")
            return None

    return None


def summarize_via_vlm(base64_image: str) -> dict | None:
    """Return a structured summary dict from the VLM for the given image."""
    with _lock:
        cfg = {**_config}

    raw = _summarize_raw_call(base64_image, cfg)
    if raw is None:
        return None

    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    try:
        data = json.loads(raw.strip())
        if isinstance(data, dict):
            return data
        logger.error(f"VLM summary returned unexpected type: {type(data)}")
    except Exception as e:
        logger.error(f"Failed to parse VLM summary JSON: {e}\nSnippet: {raw[:300]}")
    return None
