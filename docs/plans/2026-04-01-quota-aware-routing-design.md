# Quota-Aware Routing Design

## Goal

Allow `Structure-OCR` to continue progressing when one AI platform approaches its quota limit or becomes the less efficient choice for the current task.

The system should:

- let the user choose which platform does most of the work
- route tasks by tool strengths
- fall back automatically when a platform becomes unavailable, exhausted, or inefficient
- preserve clear handoff between tools

## Core Principle

Do not run all tools on the same slice at once.

Instead:

- pick one active owner for the current slice
- route based on workload share and task type
- switch only when there is a real reason

This keeps token usage lower and prevents duplicated work.

## Routing Inputs

The controller should use three input classes:

### 1. User Preference

The user may specify:

- primary platform
- secondary platform
- tertiary platform
- desired workload share

Example:

- Codex: 70
- OpenCode: 20
- Cursor: 10

### 2. Task Type

Typical routing:

- planning -> OpenCode
- orchestration -> OpenCode
- deep implementation -> Codex
- repair loop -> Codex
- UI polish -> Cursor
- review of narrow diff -> Cursor

### 3. Runtime State

Switch triggers include:

- quota exhausted
- repeated timeout
- tool unavailable
- tool not suitable for the current slice
- user override

## Routing Rules

### Default

Use the primary platform whenever it is healthy and suitable.

### Fallback

If the primary platform hits a quota or health issue:

- hand off the slice using the handoff template
- move to the configured fallback tool
- keep the slice scope unchanged

### Rebalance

If the primary platform is still available but becoming expensive:

- keep planning on OpenCode
- move implementation-heavy slices to the highest-share platform
- reserve low-value review work for the cheapest remaining tool

## Health Signals

For now, health is determined operationally rather than by API telemetry.

A tool should be treated as degraded when:

- it reports quota exhaustion
- it repeatedly times out
- it cannot complete verification within a reasonable loop
- the user marks it as low-budget for the current day

## Practical Policy for This Project

Recommended default:

- OpenCode + oh-my-opencode owns orchestration
- the user-selected high-budget platform owns most implementation
- Cursor remains tactical

This means the project always has one stable control plane while still allowing implementation work to shift across tools.

## Example Flow

1. OpenCode selects the next smallest slice.
2. The routing policy checks which platform has the largest budget share.
3. If that platform is Codex and the slice is implementation-heavy, Codex receives the task.
4. If Codex quota is exhausted, the same slice moves to OpenCode with a handoff note.
5. Cursor only joins for review or a small patch.

## Safety Rule

Do not switch tools in the middle of an uncommitted implementation without writing a handoff summary first.

## Decision

Adopt a quota-aware routing model with:

- fixed orchestration owner
- configurable implementation owner
- explicit fallback chain
- mandatory handoff on reassignment

