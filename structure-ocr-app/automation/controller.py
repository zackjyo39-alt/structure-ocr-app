from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.adapters.factory import get_adapter


AUTOMATION_DIR = ROOT / "automation"
CONFIG_PATH = ROOT / "config" / "tool-routing.yaml"
TASKS_PATH = AUTOMATION_DIR / "tasks.json"
STATE_PATH = AUTOMATION_DIR / "state.json"
OUTBOX_DIR = AUTOMATION_DIR / "outbox"
HANDOFF_DIR = AUTOMATION_DIR / "handoffs"
INBOX_DIR = AUTOMATION_DIR / "inbox"
RESULTS_DIR = AUTOMATION_DIR / "results"

NormalizedResult = Literal[
    "done",
    "blocked",
    "reassign",
    "waiting",
    "quota_exhausted",
    "timeout",
    "unknown",
]

RunOnceOutcome = Literal[
    "idle",
    "dispatched",
    "completed",
    "reassigned",
    "waiting",
    "blocked_state",
]


def normalize_result_status(payload: dict[str, Any]) -> NormalizedResult:
    raw = payload.get("result")
    if raw is None:
        return "waiting"
    if not isinstance(raw, str):
        return "unknown"
    key = raw.strip().lower().replace("-", "_")
    key = "_".join(part for part in key.split() if part)
    synonyms: dict[str, NormalizedResult] = {
        "pending": "waiting",
        "in_progress": "waiting",
        "complete": "done",
        "completed": "done",
        "success": "done",
        "block": "blocked",
        "quota": "quota_exhausted",
        "quotaexhausted": "quota_exhausted",
        "timed_out": "timeout",
        "time_out": "timeout",
    }
    key = synonyms.get(key, key)
    if key in {"done", "blocked", "reassign", "waiting", "quota_exhausted", "timeout"}:
        return key
    return "unknown"


def result_status_triggers_reassign(status: NormalizedResult) -> bool:
    return status in {"blocked", "reassign", "quota_exhausted", "timeout"}


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        key, _, remainder = line.partition(":")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if remainder.strip() == "":
            new_dict: dict[str, Any] = {}
            current[key] = new_dict
            stack.append((indent, new_dict))
        else:
            current[key] = parse_scalar(remainder)
    return root


@dataclass
class ControllerContext:
    routing: dict[str, Any]
    tasks: dict[str, Any]
    state: dict[str, Any]


def load_context() -> ControllerContext:
    OUTBOX_DIR.mkdir(exist_ok=True)
    HANDOFF_DIR.mkdir(exist_ok=True)
    INBOX_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    routing = parse_simple_yaml(CONFIG_PATH)
    tasks = load_json(TASKS_PATH)
    state = load_json(STATE_PATH)
    return ControllerContext(routing=routing, tasks=tasks, state=state)


def get_task_by_id(tasks: list[dict[str, Any]], task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    return next((task for task in tasks if task["id"] == task_id), None)


def choose_tool(task: dict[str, Any], routing: dict[str, Any]) -> str:
    task_kind = task.get("kind", "implementation")
    mapped = routing.get("routing", {}).get(task_kind)
    if mapped:
        return mapped
    return routing.get("primary_implementation", "opencode")


def choose_fallback(tool: str | None, routing: dict[str, Any]) -> str | None:
    if not tool:
        return routing.get("secondary_implementation")
    return routing.get("fallback_on_quota_exhausted", {}).get(tool, routing.get("secondary_implementation"))


def render_packet(task: dict[str, Any], tool: str, routing: dict[str, Any]) -> str:
    verification = "\n".join(f"- {item}" for item in task.get("verification", []))
    files = "\n".join(f"- {item}" for item in task.get("files", []))
    return f"""# Execution Packet

Task ID: {task['id']}
Assigned Tool: {tool}
Task Kind: {task.get('kind', 'implementation')}
Scope: {task.get('scope', '')}

Title:
{task['title']}

Files Expected To Change:
{files or '- none listed'}

Verification:
{verification or '- none listed'}

Routing Notes:
- Primary control plane: {routing.get('primary_control_plane')}
- Primary implementation: {routing.get('primary_implementation')}
- Secondary implementation: {routing.get('secondary_implementation')}
- Tertiary review: {routing.get('tertiary_review')}
- One active implementation owner per slice: {routing.get('switch_rules', {}).get('one_active_implementation_owner_per_slice')}

Execution Rules:
- keep scope tight
- do not expand beyond the assigned slice
- verify after changes
- if blocked, produce a handoff note before reassigning
"""


def write_handoff(task: dict[str, Any], tool: str | None, result: str, summary: str) -> Path:
    handoff_path = HANDOFF_DIR / f"{now_stamp()}-{task['id']}.md"
    handoff_path.write_text(
        f"""# Handoff

Task ID: {task['id']}
Tool: {tool}
Result: {result}

Summary:
{summary}
"""
    )
    return handoff_path


def load_active_result(ctx: ControllerContext) -> tuple[dict[str, Any], dict[str, Any], str, Path] | None:
    tasks = ctx.tasks["tasks"]
    task = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if not task:
        return None
    tool = ctx.state.get("current_tool") or choose_tool(task, ctx.routing)
    adapter = get_adapter(tool)
    result = adapter.collect(task["id"], RESULTS_DIR / tool)
    if result.result_path is None:
        return None
    payload = load_json(result.result_path)
    return task, payload, tool, result.result_path


def select_next_task(ctx: ControllerContext) -> tuple[dict[str, Any], str, Path] | None:
    tasks = ctx.tasks["tasks"]
    current = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if current and current.get("status") == "in_progress":
        tool = ctx.state.get("current_tool") or choose_tool(current, ctx.routing)
        packet_path = OUTBOX_DIR / "current-task.md"
        return current, tool, packet_path
    next_task = next((task for task in tasks if task["status"] == "queued"), None)
    if not next_task:
        return None
    tool = choose_tool(next_task, ctx.routing)
    next_task["status"] = "in_progress"
    ctx.state["current_task_id"] = next_task["id"]
    ctx.state["current_tool"] = tool
    packet_path = OUTBOX_DIR / "current-task.md"
    packet_path.write_text(render_packet(next_task, tool, ctx.routing))
    ctx.state["last_packet_path"] = str(packet_path.relative_to(ROOT))
    save_json(TASKS_PATH, ctx.tasks)
    save_json(STATE_PATH, ctx.state)
    return next_task, tool, packet_path


def command_status(ctx: ControllerContext) -> int:
    tasks = ctx.tasks["tasks"]
    queued = sum(1 for task in tasks if task["status"] == "queued")
    in_progress = sum(1 for task in tasks if task["status"] == "in_progress")
    done = sum(1 for task in tasks if task["status"] == "done")
    blocked = sum(1 for task in tasks if task["status"] == "blocked")
    print(json.dumps(
        {
            "current_task_id": ctx.state.get("current_task_id"),
            "current_tool": ctx.state.get("current_tool"),
            "queue": {
                "queued": queued,
                "in_progress": in_progress,
                "done": done,
                "blocked": blocked,
            },
            "routing": {
                "primary_control_plane": ctx.routing.get("primary_control_plane"),
                "primary_implementation": ctx.routing.get("primary_implementation"),
                "workload_share": ctx.routing.get("workload_share", {}),
            },
        },
        indent=2,
    ))
    return 0


def command_next(ctx: ControllerContext) -> int:
    selected = select_next_task(ctx)
    if selected is None:
        print("No queued tasks.")
        return 0
    task, tool, packet_path = selected
    print(json.dumps({"selected_task": task["id"], "tool": tool, "packet": str(packet_path.relative_to(ROOT))}, indent=2))
    return 0


def command_packet(ctx: ControllerContext) -> int:
    tasks = ctx.tasks["tasks"]
    task = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if not task:
        print("No active task.")
        return 1
    tool = ctx.state.get("current_tool") or choose_tool(task, ctx.routing)
    packet_path = OUTBOX_DIR / "current-task.md"
    packet_path.write_text(render_packet(task, tool, ctx.routing))
    ctx.state["last_packet_path"] = str(packet_path.relative_to(ROOT))
    save_json(STATE_PATH, ctx.state)
    print(packet_path.read_text())
    return 0


def command_dispatch(ctx: ControllerContext) -> int:
    tasks = ctx.tasks["tasks"]
    task = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if not task:
        print("No active task to dispatch.")
        return 1
    tool = ctx.state.get("current_tool") or choose_tool(task, ctx.routing)
    adapter = get_adapter(tool)
    packet_text = render_packet(task, tool, ctx.routing)
    inbox_dir = INBOX_DIR / tool
    result = adapter.dispatch(task["id"], packet_text, inbox_dir)
    ctx.state["last_packet_path"] = str(result.packet_path.relative_to(ROOT)) if result.packet_path else None
    save_json(STATE_PATH, ctx.state)
    print(json.dumps({
        "dispatched_task": task["id"],
        "tool": tool,
        "packet": str(result.packet_path.relative_to(ROOT)) if result.packet_path else None,
    }, indent=2))
    return 0


def command_collect(ctx: ControllerContext) -> int:
    loaded = load_active_result(ctx)
    if loaded is None:
        print("No active task to collect.")
        return 1
    task, payload, tool, result_path = loaded
    print(json.dumps({"task": task["id"], "tool": tool, "result_path": str(result_path.relative_to(ROOT)), "payload": payload}, indent=2))
    return 0


def command_handoff(ctx: ControllerContext, result: str, summary: str) -> int:
    tasks = ctx.tasks["tasks"]
    task = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if not task:
        print("No active task to hand off.")
        return 1
    tool = ctx.state.get("current_tool")
    handoff_path = write_handoff(task, tool, result, summary)
    if result == "done":
        task["status"] = "done"
        ctx.state["current_task_id"] = None
        ctx.state["current_tool"] = None
    elif result == "blocked":
        task["status"] = "blocked"
        fallback_map = ctx.routing.get("fallback_on_quota_exhausted", {})
        ctx.state["current_tool"] = fallback_map.get(tool, ctx.routing.get("secondary_implementation"))
    else:
        task["status"] = "queued"
        ctx.state["current_tool"] = None
        ctx.state["current_task_id"] = None
    ctx.state["last_handoff_path"] = str(handoff_path.relative_to(ROOT))
    save_json(TASKS_PATH, ctx.tasks)
    save_json(STATE_PATH, ctx.state)
    print(json.dumps({"handoff": str(handoff_path.relative_to(ROOT)), "result": result}, indent=2))
    return 0


def command_complete(ctx: ControllerContext) -> int:
    loaded = load_active_result(ctx)
    if loaded is None:
        print("No active result available to complete.")
        return 1
    task, payload, tool, _ = loaded
    summary = payload.get("summary", "task completed")
    handoff_path = write_handoff(task, tool, "done", summary)
    task["status"] = "done"
    ctx.state["current_task_id"] = None
    ctx.state["current_tool"] = None
    ctx.state["last_handoff_path"] = str(handoff_path.relative_to(ROOT))
    save_json(TASKS_PATH, ctx.tasks)
    save_json(STATE_PATH, ctx.state)
    print(json.dumps({
        "completed_task": task["id"],
        "tool": tool,
        "handoff": str(handoff_path.relative_to(ROOT)),
        "summary": summary,
    }, indent=2))
    return 0


def command_reassign(ctx: ControllerContext, reason: str | None) -> int:
    loaded = load_active_result(ctx)
    if loaded is None:
        print("No active result available to reassign.")
        return 1
    task, payload, tool, _ = loaded
    summary = reason or payload.get("summary", "task blocked and reassigned")
    fallback_tool = choose_fallback(tool, ctx.routing)
    handoff_path = write_handoff(task, tool, "blocked", summary)
    task["status"] = "queued"
    ctx.state["current_task_id"] = task["id"]
    ctx.state["current_tool"] = fallback_tool
    ctx.state["last_handoff_path"] = str(handoff_path.relative_to(ROOT))
    save_json(TASKS_PATH, ctx.tasks)
    save_json(STATE_PATH, ctx.state)
    print(json.dumps({
        "reassigned_task": task["id"],
        "from_tool": tool,
        "to_tool": fallback_tool,
        "handoff": str(handoff_path.relative_to(ROOT)),
        "summary": summary,
    }, indent=2))
    return 0


def run_once_step(ctx: ControllerContext) -> RunOnceOutcome:
    tasks = ctx.tasks["tasks"]
    current = get_task_by_id(tasks, ctx.state.get("current_task_id"))
    if current and current.get("status") == "blocked":
        print(json.dumps(
            {
                "action": "blocked_state",
                "task": current["id"],
                "reason": "active task is blocked; clear or hand off before continuing",
            },
            indent=2,
        ))
        return "blocked_state"

    loaded = load_active_result(ctx)
    if loaded is not None:
        task, payload, tool, _ = loaded
        status = normalize_result_status(payload)
        if status == "done":
            command_complete(ctx)
            return "completed"
        if result_status_triggers_reassign(status):
            reason = payload.get("summary", "tool requested reassignment")
            command_reassign(ctx, reason)
            return "reassigned"
        print(json.dumps({
            "task": task["id"],
            "tool": tool,
            "action": "waiting",
            "normalized": status,
            "reason": (
                "tool reports not finished"
                if status == "waiting"
                else f"unsupported result value: {payload.get('result')!r}"
            ),
        }, indent=2))
        return "waiting"

    if current and current.get("status") == "in_progress":
        tool = ctx.state.get("current_tool") or choose_tool(current, ctx.routing)
        expected = RESULTS_DIR / tool / f"{current['id']}.json"
        print(json.dumps({
            "action": "waiting",
            "task": current["id"],
            "tool": tool,
            "reason": "task in progress but no result JSON yet; write when ready",
            "expected_result": str(expected.relative_to(ROOT)),
        }, indent=2))
        return "waiting"

    selected = select_next_task(ctx)
    if selected is None:
        print(json.dumps({"action": "idle", "reason": "no queued tasks"}, indent=2))
        return "idle"
    task, tool, _ = selected
    adapter = get_adapter(tool)
    packet_text = render_packet(task, tool, ctx.routing)
    inbox_dir = INBOX_DIR / tool
    result = adapter.dispatch(task["id"], packet_text, inbox_dir)
    ctx.state["last_packet_path"] = str(result.packet_path.relative_to(ROOT)) if result.packet_path else None
    save_json(STATE_PATH, ctx.state)
    print(json.dumps({
        "action": "dispatched",
        "task": task["id"],
        "tool": tool,
        "packet": str(result.packet_path.relative_to(ROOT)) if result.packet_path else None,
    }, indent=2))
    return "dispatched"


def command_run_once(ctx: ControllerContext) -> int:
    run_once_step(ctx)
    return 0


def command_run_until_idle(ctx: ControllerContext, max_steps: int) -> int:
    if max_steps < 1:
        print(json.dumps({"error": "max_steps must be >= 1", "max_steps": max_steps}, indent=2))
        return 1
    stop_outcomes: frozenset[RunOnceOutcome] = frozenset({"idle", "waiting", "blocked_state"})
    steps = 0
    last: RunOnceOutcome | None = None
    while steps < max_steps:
        steps += 1
        last = run_once_step(ctx)
        if last in stop_outcomes:
            break
    print(json.dumps({
        "action": "run_until_idle_finished",
        "steps": steps,
        "last_outcome": last,
        "max_steps": max_steps,
        "stopped_by_max_steps": steps >= max_steps and last not in stop_outcomes,
    }, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structure-OCR automation controller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("next")
    subparsers.add_parser("packet")
    subparsers.add_parser("dispatch")
    subparsers.add_parser("collect")
    subparsers.add_parser("complete")
    subparsers.add_parser("run-once")
    run_until_idle = subparsers.add_parser("run-until-idle")
    run_until_idle.add_argument("--max-steps", type=int, default=50, metavar="N", help="max controller iterations (default: 50)")
    reassign = subparsers.add_parser("reassign")
    reassign.add_argument("--reason", required=False)
    handoff = subparsers.add_parser("handoff")
    handoff.add_argument("--result", choices=["done", "blocked", "requeue"], required=True)
    handoff.add_argument("--summary", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    ctx = load_context()
    if args.command == "status":
        return command_status(ctx)
    if args.command == "next":
        return command_next(ctx)
    if args.command == "packet":
        return command_packet(ctx)
    if args.command == "dispatch":
        return command_dispatch(ctx)
    if args.command == "collect":
        return command_collect(ctx)
    if args.command == "complete":
        return command_complete(ctx)
    if args.command == "run-once":
        return command_run_once(ctx)
    if args.command == "run-until-idle":
        return command_run_until_idle(ctx, args.max_steps)
    if args.command == "reassign":
        return command_reassign(ctx, args.reason)
    if args.command == "handoff":
        return command_handoff(ctx, args.result, args.summary)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
