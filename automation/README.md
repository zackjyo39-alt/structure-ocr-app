# Automation Controller

This directory contains the local automation layer for `Structure-OCR`.

## Commands

Run from the repository root:

```bash
python3 automation/controller.py status
python3 automation/controller.py next
python3 automation/controller.py packet
python3 automation/controller.py handoff --result done --summary "slice completed"
```

## Files

- `tasks.json`: queue of implementation slices
- `state.json`: current controller state
- `outbox/current-task.md`: generated execution packet for the active tool
- `handoffs/`: handoff history

## Workflow

1. `next` selects the next queued slice and chooses the tool owner.
2. `packet` generates a tool-ready packet.
3. The assigned tool executes the slice.
4. `handoff` records the result and updates the queue/state.

