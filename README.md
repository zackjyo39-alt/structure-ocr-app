# Structure-OCR

独立的前后端分离文档 OCR 产品项目，底层利用 PaddleOCR 做文本与结构提取。

## 目标

- 上传文本、拍照、图片或 PDF
- 提取文字
- 尽量恢复版面结构、表格和段落关系

## 现实边界

PaddleOCR 可以显著提升结构提取能力，但无法对所有低清、倾斜、遮挡、复杂版式场景做“百分百还原”承诺。这个项目会尽量保留：

- 页码
- 文本块
- 坐标框
- 结构类型
- 置信度

## 启动

- 项目根目录：`/Users/rock.xu/github/projects/ai-ml/structure-ocr-app`
- 后端：`backend`
- 前端：`frontend`
- OpenCode 启动提示：`opencode-ultrawork-prompt.md`

### 快速启动

```bash
# 终端 1 - 启动后端
cd backend
pip install -e ".[ocr]"  # 安装 OCR 依赖
uvicorn app.main:app --reload --port 8000

# 终端 2 - 启动前端
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

## OCR 引擎选择（Mac M1 / CPU 优化）

后端支持三种几何 OCR 引擎，通过 `STRUCTURE_OCR_ENGINE` 环境变量切换，**无需修改代码**：

| 值 | 引擎 | 适用场景 | 安装 |
|---|---|---|---|
| `paddle`（默认） | PaddleOCR 3.x | 扫描件、倾斜稿、复杂版面 | 已内置 |
| `rapidocr` | RapidOCR ONNX | Mac/Linux 无 Paddle 框架、速度优先 | `pip install ".[rapidocr]"` |
| `apple_vision` | Apple Vision (Neural Engine) | M 系列 Mac 截图识别 | `pip install ".[apple-vision]"` |
| `auto` | 自动选最快可用引擎 | 本地开发 Mac | `pip install ".[auto]"` |
| `cross_validate` | 双引擎并行 + 交叉验证 | **法律/医疗级精度要求** | `pip install ".[auto]"` |

### RapidOCR（推荐扫描件场景）

直接加载 PaddleOCR V4-Server 级 ONNX 模型，去掉 Paddle 框架开销，在 CPU 上通常比原版快 **2～4 倍**：

```bash
pip install ".[rapidocr]"
export STRUCTURE_OCR_ENGINE=rapidocr
uvicorn app.main:app --reload --port 8000
```

### Apple Vision（推荐截图识别场景）

调用 macOS 神经网络引擎（Neural Engine）原生 OCR，中英文混排准确率极高，速度最快且不占 CPU：

```bash
pip install ".[apple-vision]"
export STRUCTURE_OCR_ENGINE=apple_vision
uvicorn app.main:app --reload --port 8000
```

### 自动模式（开发便利）

```bash
pip install ".[auto]"
export STRUCTURE_OCR_ENGINE=auto   # rapidocr > apple_vision > paddle
```

### 交叉验证模式（法律/医疗级精度）

同时运行两个引擎，逐块对比；一致则置信度提升，不一致则标红并输出详细对照表：

```bash
pip install ".[auto]"
export STRUCTURE_OCR_ENGINE=cross_validate
# 可选：指定主/副引擎（默认 rapidocr 主 + apple_vision 副，微信/聊天截图上中文更稳）
export STRUCTURE_OCR_CV_PRIMARY=rapidocr
export STRUCTURE_OCR_CV_SECONDARY=apple_vision
# 若仍坚持 Apple 主引擎但不一致时想用副引擎文字写回块与全文：
# export STRUCTURE_OCR_CV_ON_MISMATCH=secondary
# 可选：调整对齐阈值
export STRUCTURE_OCR_CV_IOU_THRESHOLD=0.35    # 默认：同区域判定 IoU 阈值
export STRUCTURE_OCR_CV_TEXT_THRESHOLD=0.80   # 默认：文本一致性 bigram Jaccard 阈值
uvicorn app.main:app --reload --port 8000
```

前端会自动显示：
- **「双引擎交叉验证报告」面板**：一致率、不一致明细表
- **每个文字块的角标**：绿色「双引擎一致」/ 红色「不一致·需复核」/ 黄色「仅主引擎」
- 不一致块自动加红色左边框

### PaddleOCR 性能调节（Paddle 引擎专用）

Apple Silicon 上 Paddle 为 **CPU 推理**，可用以下变量在速度与精度间权衡：

| 变量 | 作用 |
|------|------|
| `STRUCTURE_OCR_FAST=1` | 一键快模式：关闭行方向分类、检测长边约 **736**（默认 960）。 |
| `STRUCTURE_OCR_TEXTLINE_ORIENTATION=0` | 仅关闭行方向分类（省一段小模型）。 |
| `STRUCTURE_OCR_DET_LIMIT_SIDE_LEN=640` | 检测输入更短边上限，更快，极小字可能漏检。 |
| `STRUCTURE_OCR_PDF_ZOOM=1.5` | PDF 栅格倍率（默认 **2.0**）；降到 1.25～1.5 通常明显加速。 |
| `STRUCTURE_OCR_REC_BATCH_SIZE=8` | 识别批大小（视内存可调大）。 |

### 用 NVIDIA GPU 跑 Paddle（CUDA 机器）

**Mac M 系列**：官方 Paddle macOS 轮子无 CUDA，**推荐改用 RapidOCR 或 Apple Vision**。

**Linux / Windows + NVIDIA**：安装匹配 CUDA 版本的 `paddlepaddle-gpu`，然后：

```bash
export STRUCTURE_OCR_PADDLE_DEVICE=gpu:0
```

### 示例（Mac M1 快速启动）

```bash
# 方案 A：Apple Vision（截图为主）
pip install ".[apple-vision]"
export STRUCTURE_OCR_ENGINE=apple_vision

# 方案 B：RapidOCR（扫描 PDF 为主）
pip install ".[rapidocr]"
export STRUCTURE_OCR_ENGINE=rapidocr
export STRUCTURE_OCR_PDF_ZOOM=1.5

uvicorn app.main:app --reload --port 8000
```

开启 **VLM** 时，每页还会先跑一遍几何 OCR 做 hint；RapidOCR / Apple Vision 在此环节也比 Paddle 快。

## AI 协作控制面

- 总控设计：[docs/plans/2026-04-01-multi-agent-control-plane-design.md](docs/plans/2026-04-01-multi-agent-control-plane-design.md)
- 配额路由设计：[docs/plans/2026-04-01-quota-aware-routing-design.md](docs/plans/2026-04-01-quota-aware-routing-design.md)
- 架构决策：[docs/adr/0001-use-opencode-as-control-plane.md](docs/adr/0001-use-opencode-as-control-plane.md)
- OpenCode 提示：[prompts/opencode-control-plane.md](prompts/opencode-control-plane.md)
- OpenCode 配额提示：[prompts/opencode-quota-aware-control-plane.md](prompts/opencode-quota-aware-control-plane.md)
- OpenCode 自动化 runner：[prompts/opencode-automation-runner.md](prompts/opencode-automation-runner.md)
- Overnight 提示：[prompts/overnight-run.md](prompts/overnight-run.md)
- Codex 提示：[prompts/codex-worker.md](prompts/codex-worker.md)
- Cursor 提示：[prompts/cursor-reviewer.md](prompts/cursor-reviewer.md)
- 交接模板：[prompts/handoff-template.md](prompts/handoff-template.md)
- 当前路由配置：[config/tool-routing.yaml](config/tool-routing.yaml)
- 路由配置模板：[config/tool-routing.example.yaml](config/tool-routing.example.yaml)

## GitHub Actions 门禁

- 工作流文件：`.github/workflows/ci.yml`
- 后端门禁：源码编译 + API smoke tests
- 前端门禁：依赖安装 + `vite build`

## Automation Controller

- 设计文档：[docs/plans/2026-04-01-automation-controller-design.md](docs/plans/2026-04-01-automation-controller-design.md)
- 说明：[automation/README.md](automation/README.md)
- 路由配置：[config/tool-routing.yaml](config/tool-routing.yaml)
- 任务队列：[automation/tasks.json](automation/tasks.json)
- 运行状态：[automation/state.json](automation/state.json)
- 结果 schema：[automation/result-schema.example.json](automation/result-schema.example.json)
- 控制器：`python3 automation/controller.py status|next|packet|handoff`
