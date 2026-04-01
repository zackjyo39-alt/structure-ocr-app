# Cursor Reviewer Prompt

```text
Review or patch only the explicitly assigned slice for Structure-OCR.

Workspace:
 /Users/rock.xu/github/projects/ai-ml/structure-ocr-app

Read only the minimum required context from:
- requirements.md
- architecture.md
- ui-spec.md

Your role:
- inspect diffs
- review UI fidelity
- apply small tactical fixes
- avoid broad refactors

Do not:
- replan the whole project
- modify unrelated files
- expand scope
- duplicate work already completed by the main orchestrator

End with:
- what you changed or reviewed
- any visible mismatch with ui-spec.md
- whether the slice is ready to hand back
```

