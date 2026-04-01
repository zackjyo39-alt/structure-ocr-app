# OpenCode Automation Runner

```text
You are consuming a task from the Structure-OCR automation controller.

Workspace:
 /Users/rock.xu/github/projects/ai-ml/structure-ocr-app

Read:
- automation/inbox/opencode/<task-id>.md
- product.md
- requirements.md
- architecture.md
- ui-spec.md
- workflow.md
- task-orchestration.md

Rules:
- execute only the assigned slice
- do not expand scope
- run the listed verification
- summarize the result honestly
- write a JSON result payload to:
  automation/results/opencode/<task-id>.json

Required JSON keys:
- task_id
- tool
- result
- summary
- verification
```

