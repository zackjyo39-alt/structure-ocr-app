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

- **Idle**: no queued work and nothing to dispatch.
- **Waiting**: the active tool result normalizes to `waiting` or `unknown`, or the task is already `in_progress` but the expected result JSON is still missing.
- **Blocked state**: the task pointed to by `state.json` has `status: "blocked"`.
- **Max steps**: default `50`; override with `--max-steps N`.

The command prints one JSON event per step and ends with a summary like:

```bash
python3 automation/controller.py run-until-idle --max-steps 10
```

### Result status normalization

Tool result JSON uses a `result` string. The controller maps it to a canonical status before deciding what to do:

| Canonical status | Behavior |
| --- | --- |
| `done` | Complete task |
| `blocked` | Reassign to fallback tool |
| `reassign` | Reassign to fallback tool |
| `quota_exhausted` | Reassign to fallback tool |
| `timeout` | Reassign to fallback tool |
| `waiting` | No state change; loop stops |
| `unknown` | No state change; loop stops |

Supported synonyms include `pending` / `in_progress` -> `waiting`, `complete` / `completed` / `success` -> `done`, `block` -> `blocked`, `quota` -> `quota_exhausted`, and `timed_out` / `time_out` -> `timeout`.

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
7. `run-once` executes one controller loop:
   - if there is a result JSON, it normalizes `result`, then auto-completes, reassigns, or waits
   - if the current task is already `in_progress` but has no result JSON yet, it waits instead of re-dispatching
   - otherwise it selects and dispatches the next task
8. `run-until-idle` repeats that loop until idle, waiting/blocked-state stop, or `--max-steps`.

`complete` and `reassign` are the preferred path once a tool has written a result JSON.
Manual `handoff` remains available as a fallback for exceptional cases.

`run-once` is the preferred operator entrypoint for a single step. `run-until-idle` is preferred when you want the controller to drain work until it must wait or stop.

## OpenCode Entry

Use this prompt when OpenCode is the active tool:

- `prompts/opencode-automation-runner.md`
