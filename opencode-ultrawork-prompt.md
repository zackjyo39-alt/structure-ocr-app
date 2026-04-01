# OpenCode Ultrawork Prompt

```text
ultrawork

You are the execution engine for this project.
Workspace:
 /Users/rock.xu/github/projects/ai-ml/structure-ocr-app

Load these files first and treat them as the only product truth:
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/product.md
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/requirements.md
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/architecture.md
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/workflow.md
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/task-orchestration.md
- /Users/rock.xu/github/projects/ai-ml/structure-ocr-app/ui-spec.md

Mission:
Implement Phase 1 completely and only Phase 1:
a minimal frontend/backend separated PaddleOCR document upload and extraction web app.

Required product outcomes:
- dark workspace UI matching ui-spec.md
- fixed left sidebar
- top header
- left-side upload and document preview area
- right-side structured result panel
- upload support for PDF and image files at minimum
- backend extraction endpoint
- frontend rendering of structured JSON/text result
- graceful fallback if PaddleOCR or related OCR dependencies are unavailable
- local run instructions updated if implementation changes them

Hard constraints:
- do not expand scope beyond Phase 1
- do not add auth
- do not add persistence
- do not add batch upload
- do not add background workers
- do not add multi-user or collaboration features
- do not invent new product requirements
- do not replace the architecture unless the docs are internally inconsistent
- preserve the design direction from ui-spec.md
- prefer the smallest direct implementation over abstractions

Execution behavior:
- do not ask for confirmation unless blocked by an irreversible, destructive, or external-access decision
- make reasonable assumptions and continue
- inspect the repo before editing
- break the work into the smallest meaningful steps
- after each meaningful step, run the relevant verification
- if verification fails, debug, patch, and re-run until it passes
- if an external dependency is missing, continue implementing everything else and add a graceful fallback instead of stopping
- do not stop at analysis, partial scaffolding, or TODOs
- continue until Phase 1 is actually usable locally

Verification rules:
- run backend syntax validation
- run frontend build or the closest available validation
- verify the API contract is coherent with the frontend
- verify the UI reflects the workspace layout direction from ui-spec.md
- if a check cannot run, state exactly why and choose the next strongest validation

Definition of done:
- a user can start the frontend and backend locally
- a user can upload a file from the frontend
- the backend returns structured JSON for the frontend to render
- the UI matches the intended split-view dark workspace direction
- the implementation is narrower than the full product and clearly stays within Phase 1
- relevant checks pass, or exact blockers are documented with a fallback path

Output format at the end:
- what was implemented
- what was verified
- what remains outside Phase 1
- exact commands to run locally
```
