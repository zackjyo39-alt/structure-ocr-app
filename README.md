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

## AI 协作控制面

- 总控设计：[docs/plans/2026-04-01-multi-agent-control-plane-design.md](docs/plans/2026-04-01-multi-agent-control-plane-design.md)
- 配额路由设计：[docs/plans/2026-04-01-quota-aware-routing-design.md](docs/plans/2026-04-01-quota-aware-routing-design.md)
- 架构决策：[docs/adr/0001-use-opencode-as-control-plane.md](docs/adr/0001-use-opencode-as-control-plane.md)
- OpenCode 提示：[prompts/opencode-control-plane.md](prompts/opencode-control-plane.md)
- OpenCode 配额提示：[prompts/opencode-quota-aware-control-plane.md](prompts/opencode-quota-aware-control-plane.md)
- Codex 提示：[prompts/codex-worker.md](prompts/codex-worker.md)
- Cursor 提示：[prompts/cursor-reviewer.md](prompts/cursor-reviewer.md)
- 交接模板：[prompts/handoff-template.md](prompts/handoff-template.md)
- 路由配置模板：[config/tool-routing.example.yaml](config/tool-routing.example.yaml)

## GitHub Actions 门禁

- 工作流文件：`.github/workflows/ci.yml`
- 后端门禁：源码编译 + API smoke tests
- 前端门禁：依赖安装 + `vite build`
