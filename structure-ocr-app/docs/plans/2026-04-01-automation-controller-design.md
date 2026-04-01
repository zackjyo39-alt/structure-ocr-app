# Automation Controller Design

## Goal

Add a minimal automation layer that turns the existing routing policy, prompts, and handoff rules into a usable local controller.

This controller is intentionally small. It does not call external tool APIs directly. Instead, it:

- reads routing policy
- reads the task queue
- selects the next slice
- chooses the active tool
- writes execution packets
- dispatches packets into tool-specific inbox directories
- reads tool-specific result payloads
- records handoff and task state

That is enough to move the project from "manual prompt copying" to "repository-driven task automation."

## Scope

The controller should support:

- `status`: show current routing, active task, and queue counts
- `next`: pick the next queued task and assign the active tool
- `handoff`: record the result of a slice and update task status
- `packet`: generate a tool-ready execution packet for the current slice
- `dispatch`: deliver the packet into the assigned tool inbox
- `collect`: read the tool result payload from the results directory

It should not yet:

- talk directly to Cursor, OpenCode, or Codex APIs
- auto-commit code
- auto-push code
- inspect live quota telemetry

## Inputs

- `config/tool-routing.yaml`
- `automation/tasks.json`
- `automation/state.json`

## Outputs

- `automation/outbox/current-task.md`
- `automation/inbox/<tool>/*.md`
- `automation/results/<tool>/*.json`
- `automation/handoffs/*.md`
- updated `automation/state.json`
- updated `automation/tasks.json`

## Routing Logic

The controller uses:

- task kind
- routing policy
- fallback chain
- current active slice

The controller chooses one active owner per slice.

## State Model

Task statuses:

- `queued`
- `in_progress`
- `done`
- `blocked`

Run state tracks:

- current task id
- current tool
- last packet path
- last handoff path

## Decision

Use a Python controller with standard-library-only logic so the automation layer stays lightweight and easy to run locally.
