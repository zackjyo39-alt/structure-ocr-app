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
python3 automation/controller.py handoff --result done --summary "slice completed"
```

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

`complete` and `reassign` are the preferred path once a tool has written a result JSON.
Manual `handoff` remains available as a fallback for exceptional cases.

## OpenCode Entry

Use this prompt when OpenCode is the active tool:

- `prompts/opencode-automation-runner.md`
