# ADR-0001: Use OpenCode Plus oh-my-opencode as the Primary Control Plane

## Status

Accepted

## Context

`Structure-OCR` is being built with access to several AI-assisted tools:

- OpenCode
- oh-my-opencode
- Codex
- Cursor

Using all of them as simultaneous top-level executors would create several problems:

- duplicated context loading
- overlapping edits
- higher token usage
- poor task ownership
- harder verification and handoff

The project needs a single primary orchestrator that can keep execution focused on product documents, task boundaries, and verification loops.

## Decision Drivers

- minimize duplicated token usage
- keep one source of truth for orchestration
- support long-running task execution
- keep specialist tools available without allowing role confusion
- preserve clean handoffs between planning, implementation, and review

## Considered Options

### Option A

Use OpenCode + oh-my-opencode as the control plane, Codex as the heavy implementation worker, Cursor as tactical review.

### Option B

Use Codex as the control plane and call the other tools ad hoc.

### Option C

Use all tools as peer executors and manually reconcile results.

## Decision

Choose Option A.

OpenCode + oh-my-opencode will own:

- task selection
- execution sequencing
- phase boundaries
- persistent loops
- final handoff summaries

Codex will own:

- bounded implementation slices
- deeper repair loops
- heavier cross-file changes

Cursor will own:

- quick inspection
- narrow UI patches
- tactical review

GitHub Actions will own:

- objective validation
- merge readiness gates

## Consequences

### Positive

- clearer ownership
- lower duplicate token spend
- cleaner project-state continuity
- easier to resume work

### Negative

- requires discipline not to overuse secondary tools
- some tasks may feel slower if the team is tempted to parallelize prematurely
- needs clear prompts and handoff conventions

## Follow-Up

- add role prompts
- add orchestration guide
- add CI validation for merge gates

