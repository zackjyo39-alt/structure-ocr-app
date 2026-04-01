# Overnight Run Prompt

```text
ultrawork

You are running an overnight implementation session for Structure-OCR.
Workspace:
 /Users/rock.xu/github/projects/ai-ml/structure-ocr-app

Load and follow:
- product.md
- requirements.md
- architecture.md
- ui-spec.md
- workflow.md
- task-orchestration.md
- docs/plans/2026-04-01-multi-agent-control-plane-design.md
- docs/plans/2026-04-01-quota-aware-routing-design.md
- config/tool-routing.yaml
- prompts/handoff-template.md

Operator intent:
- do not interrupt unless blocked by an irreversible destructive action or external credential decision
- optimize for maximum autonomous progress overnight
- aim to deliver the strongest possible Phase 1 product by morning

Routing:
- OpenCode remains the orchestrator
- Cursor is the primary implementation tool and should carry most of the execution load
- Codex should be used sparingly for narrow review, architecture checks, or small high-value repairs
- if Cursor becomes quota-limited or degraded, hand off the same slice to OpenCode

Execution policy:
- work slice by slice
- keep one active implementation owner per slice
- verify after every meaningful change
- if verification fails, repair and rerun
- keep changes aligned to the docs
- do not expand scope beyond Phase 1

Morning handoff format:
- what is fully working
- what was verified
- what remains incomplete
- exact next step if Phase 1 is not fully done
```
