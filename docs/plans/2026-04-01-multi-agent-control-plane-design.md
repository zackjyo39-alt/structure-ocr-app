# Multi-Agent Control Plane Design

## Goal

Create a practical orchestration model for `Structure-OCR` that uses:

- OpenCode + oh-my-opencode as the primary control plane
- Codex as the deep implementation worker
- Cursor as the review and tactical patch tool
- GitHub Actions as the merge and release gate

The design goal is not "use every tool at once". The goal is to maximize progress while minimizing duplicated context loading, conflicting edits, and wasted token budget.

## Recommended Architecture

### Primary Control Plane

OpenCode with oh-my-opencode is the default orchestrator.

Reasons:

- it is best suited for long-running task execution
- it already supports agent-oriented workflow patterns
- it can keep work focused on project documents and phase boundaries
- it is the cleanest place to run persistent execution loops

### Secondary Worker

Codex is used only when the current slice requires one or more of:

- multi-file implementation
- deeper codebase reasoning
- iterative fix-and-verify loops
- cross-layer refactors

Codex is not the product planner. It is the specialist implementation lane.

### Tactical Tool

Cursor is used only for:

- visual inspection
- tactical patching
- quick diff review
- fallback edits when human supervision is useful

Cursor should not be the main orchestrator for this project.

### Gatekeeper

GitHub Actions is the objective quality gate.

It should be responsible for:

- backend syntax and tests
- frontend build
- lint and type checks when added
- merge readiness

## Tool Boundaries

Only one tool should actively edit the same implementation slice at a time.

Allowed pattern:

- OpenCode plans and delegates
- Codex edits one bounded slice
- Cursor reviews or applies a tiny follow-up patch

Avoid this pattern:

- OpenCode, Codex, and Cursor all modifying the same files in parallel

That pattern increases token burn, merge conflict risk, and regression risk.

## Work Queue Model

Every task should move through these states:

`queued -> selected -> implementing -> verifying -> done`

Optional failure states:

`blocked -> fallback`

Each task must define:

- scope
- files expected to change
- verification method
- done condition

## Session Strategy

Each working session should target one implementation slice only.

For this project, examples of good slices are:

- backend upload endpoint
- frontend workspace shell
- OCR result contract alignment
- graceful fallback path

Bad slices are:

- "build the whole product"
- "finish the entire platform"

## Quota Strategy

To avoid burning through model usage too quickly:

- keep `product.md`, `requirements.md`, `architecture.md`, `ui-spec.md`, and `task-orchestration.md` as the only source of truth
- avoid pasting long repeated context into every tool
- use OpenCode as the only always-on orchestrator
- only invoke Codex for difficult slices
- use Cursor only after implementation or when a small visual patch is faster than another full agent run
- do not run duplicate full-repo scans across tools unless a real blocker exists

## Handoff Protocol

When one tool finishes a slice, the handoff should include:

- what changed
- which files changed
- what verification ran
- what failed or remains
- the exact next task

This keeps the next tool from re-solving the entire problem.

## Phase 1 Execution Model

For `Structure-OCR`, the recommended Phase 1 flow is:

1. OpenCode loads project docs and selects the current smallest slice.
2. OpenCode implements directly if the change is small.
3. OpenCode invokes Codex only if the slice becomes multi-file or repair-heavy.
4. Codex returns a bounded change and verification summary.
5. Cursor is used only for fast UI polish or narrow review.
6. GitHub Actions becomes the merge gate once CI is added.

## Failure Handling

If a tool gets stuck:

- do not switch all tools on at once
- write down the blocker
- assign the blocker to the best-suited tool
- preserve the same scope boundary

Examples:

- dependency issue -> OpenCode or Codex repair
- visual mismatch -> Cursor patch
- unclear product behavior -> return to project docs, not improvisation

## Decision

Use OpenCode + oh-my-opencode as the control plane for all product work, with Codex and Cursor treated as bounded specialists rather than peer orchestrators.

## Next Step

Implement this design by adding:

- role prompts for each tool
- a lightweight handoff template
- CI gates for backend and frontend validation

