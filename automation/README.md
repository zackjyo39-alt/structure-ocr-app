# Automation Controller

This directory contains the local automation layer for `Structure-OCR`.

The current execution model is adapter-based and file-driven:

- the controller dispatches packets into `automation/inbox/<tool>/`
- each tool writes a result payload into `automation/results/<tool>/`
- the controller collects the result and advances state

## Commands

Run from the repository root:

```bash
python3 automation/controller.py status
python3 automation/controller.py next
python3 automation/controller.py packet
python3 automation/controller.py dispatch
python3 automation/controller.py collect
python3 automation/controller.py handoff --result done --summary "slice completed"
```

## Files

- `tasks.json`: queue of implementation slices
- `state.json`: current controller state
- `outbox/current-task.md`: generated execution packet for the active tool
- `inbox/<tool>/`: dispatched packets for each tool
- `results/<tool>/`: result payloads returned by each tool
- `handoffs/`: handoff history

## Workflow

1. `next` selects the next queued slice and chooses the tool owner.
2. `dispatch` writes the task packet into the assigned tool inbox.
3. The assigned tool executes the slice and writes a result payload into its results directory.
4. `collect` reads the result payload.
5. `handoff` records the result and updates the queue/state.
