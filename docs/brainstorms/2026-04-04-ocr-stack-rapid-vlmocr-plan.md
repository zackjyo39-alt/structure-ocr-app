---
date: 2026-04-04
topic: ocr-stack-rapid-vlmocr
parent: 2026-04-04-ocr-stack-rapid-vlmocr-requirements.md
---

# Implementation plan（接续需求文档）

## Goal

在 **Ollama** 上接入可作为 **文档/视觉理解** 使用的 **GLM-OCR / DeepSeek-OCR**（或兼容多模态 `chat` 的本地模型），与现有 **RapidOCR 默认几何 OCR** 组合；**不**把二者做成第二套 IoU 框级 cross_validate，而是走现有 **VLM 路径** + **OCR hint** + **法律字段对照**。

## Preconditions

- 本机 `ollama pull <model>` 后，`/api/chat` 多模态请求可用（与当前 `vlm.py` Ollama 分支一致）。
- 确认模型在 Ollama 库的**准确模型名**（可能为 `deepseek-ocr` 变种或社区 tag；GLM-OCR 需核实是否已进 Ollama library）。

## Work units

1. **Preset / 配置**（`backend/app/vlm.py`，前端 `frontend/src/main.jsx` 若有 preset 列表）
   - 新增 Ollama preset：**DeepSeek-OCR**、**GLM-OCR**（占位名以拉取验证为准）。
   - `base_url` 默认 `http://localhost:11434/api/chat`；说明需 vision 模型。

2. **调用契约**
   - 复用 `_call_ollama`（或等价）：`images` base64 + `messages`；若某模型要求 **不同 message schema**，在 `vlm.py` 做 **per-model 小分支**（避免污染通用路径）。

3. **抽取提示词**（`extract_via_vlm` 所用 system/user）
   - 评估是否需要 **OCR 专用** prompt 变体（表格/Markdown/JSON 块），与现有法律 JSON schema 对齐；必要时 `provider==ollama && model in OCR_MODELS` 切换 prompt id。

4. **默认 OCR 栈**（已与需求对齐的部分）
   - 保持 **Rapid 主**、`README` / `Makefile` 已反映；文档中明确 **Apple 可选**、**Paddle 兜底**。

5. **验收**
   - 同一张聊天长截图：Rapid 有块；Ollama+VLM-OCR 模型 `vlm_used=true`；无 500。
   - `backend/tests/test_api.py`：如有纯 mock 的 VLM 测试，增一条「ollama preset 配置解析」级别的轻量测试（不强制真推理）。

## Out of scope（本轮）

- 块级 Rapid × VLM-OCR 的 IoU 交叉验证新产品线。
- 删除 Paddle 代码路径。

## Risk

- Ollama 上 **GLM-OCR 可能尚未官方发布**；规划实施时若缺失，则 **先 DeepSeek-OCR（或已有 vision 模型）**，GLM 预设保留为「待模型可用」。
