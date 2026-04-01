# Automation Controller

This directory contains the local automation layer for `Structure-OCR`.

The current execution model is adapter-based and file-driven:

- the controller dispatches packets into `automation/inbox/<tool>/`
- each tool writes a result payload into `automation/results/<tool>/`
- the controller collects the result and advances state

OpenCode now has a dedicated adapter contract:

- dispatched packets for OpenCode include runner instructions
- OpenCode should consume `automation/inbox/opencode/<task-id>.md`
- OpenCode should write results to `automation/results/opencode/<task-id>.json`
- use `automation/result-schema.example.json` as the payload shape

## Commands

Run from the repository root:

```bash
python3 automation/controller.py status
python3 automation/controller.py next
python3 automation/controller.py packet
python3 automation/controller.py dispatch
python3 automation/controller.py collect
python3 automation/controller.py complete
python3 automation/controller.py reassign --reason "quota exhausted"
python3 automation/controller.py run-once
python3 automation/controller.py run-until-idle
python3 automation/controller.py run-until-idle --max-steps 20
python3 automation/controller.py handoff --result done --summary "slice completed"
```

### `run-until-idle`

Runs the same step as `run-once` in a loop until one of these happens:

- **Idle**: no queued work and nothing to dispatch (same `{"action": "idle", ...}` as `run-once`).
- **Waiting**: the active tool result normalizes to `waiting` or `unknown` (still in progress or unsupported `result` value), **or** the task is already `in_progress` but the expected `automation/results/<tool>/<task-id>.json` is still missing (controller will not re-dispatch the same task until that file appears).
- **Blocked state**: the task pointed to by `state.json` has `status: "blocked"` (needs a manual `handoff` or queue fix).
- **Max steps**: default `50`; override with `--max-steps N` (must be >= 1).

The final line printed is a JSON summary, for example:

```bash
python3 automation/controller.py run-until-idle --max-steps 10
# ... one JSON event per step ...
# {
#   "action": "run_until_idle_finished",
#   "steps": 3,
#   "last_outcome": "idle",
#   "max_steps": 10,
#   "stopped_by_max_steps": false
# }
```

### Result status normalization

Tool result JSON uses a `result` string. The controller maps it to a canonical status (case-insensitive; hyphens and runs of spaces become underscores) before deciding what to do:

| Canonical status   | Behavior in `run-once` / `run-until-idle`      |
|--------------------|-----------------------------------------------|
| `done`             | Complete task (same as `complete`)            |
| `blocked`          | Reassign to fallback tool                     |
| `reassign`         | Reassign to fallback tool                     |
| `quota_exhausted`  | Reassign to fallback tool                     |
| `timeout`          | Reassign to fallback tool                     |
| `waiting`          | No state change; loop stops for `run-until-idle` |
| (missing / other) | Treated like `waiting` or `unknown` (no state change; loop stops) |

Synonyms include: `pending` / `in_progress` → `waiting`; `complete` / `completed` / `success` → `done`; `block` → `blocked`; `quota` → `quota_exhausted`; `timed_out` / `time_out` → `timeout`.

## Files

- `tasks.json`: queue of implementation slices
- `state.json`: current controller state
- `outbox/current-task.md`: generated execution packet for the active tool
- `inbox/<tool>/`: dispatched packets for each tool
- `results/<tool>/`: result payloads returned by each tool
- `handoffs/`: handoff history
- `result-schema.example.json`: example result payload shape

## Workflow

1. `next` selects the next queued slice and chooses the tool owner.
2. `dispatch` writes the task packet into the assigned tool inbox.
3. The assigned tool executes the slice and writes a result payload into its results directory.
4. `collect` reads the result payload.
5. `complete` automatically writes handoff and marks the active task done.
6. `reassign` automatically writes handoff and moves the active task to the fallback tool.
7. `run-once` executes one controller loop (implemented by `run_once_step`):
   - if there is a result JSON, it normalizes `result`, then auto-completes, reassigns, or waits
   - else if the current task is already `in_progress`, it **waits** (one dispatch per task until a result file exists; avoids overwriting `inbox` in a tight loop)
   - otherwise it selects and dispatches the next queued task
8. `run-until-idle` repeats that loop until idle, waiting/blocked-state stop, or `--max-steps`.

`complete` and `reassign` are the preferred path once a tool has written a result JSON.
Manual `handoff` remains available as a fallback for exceptional cases.

`run-once` is the preferred operator entrypoint for a single step; `run-until-idle` is preferred when you want the controller to drain the queue until it must wait or stop.

## OpenCode Entry

Use this prompt when OpenCode is the active tool:

- `prompts/opencode-automation-runner.md`
