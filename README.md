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
