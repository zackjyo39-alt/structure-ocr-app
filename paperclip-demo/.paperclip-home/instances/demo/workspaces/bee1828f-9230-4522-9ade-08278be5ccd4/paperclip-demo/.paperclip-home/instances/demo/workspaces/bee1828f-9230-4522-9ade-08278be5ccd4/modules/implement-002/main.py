#!/usr/bin/env python3
"""Module-002: refined take_over decision with normalized statuses and counts."""

from typing import Any, Dict, List, Tuple

TODO_LABEL = "to do"


def _normalize_status(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().casefold().split())


def _is_todo_status(value: object) -> bool:
    return _normalize_status(value) == TODO_LABEL


def partition_issues(raw: List[object]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Split API items into (all_dict_issues, todo_subset). Non-dicts are ignored."""
    dicts: List[Dict[str, object]] = []
    for item in raw:
        if isinstance(item, dict):
            dicts.append(item)
    todo = [issue for issue in dicts if _is_todo_status(issue.get("status"))]
    return dicts, todo


def run_module(tool_call: Any) -> Dict[str, object]:
    raw: List[object] = []
    try:
        result = tool_call("list_issues", {"project_id": "current"})
        if isinstance(result, list):
            raw = result
    except Exception:
        raw = []

    all_issues, todo_issues = partition_issues(raw)
    total = len(all_issues)
    todo_count = len(todo_issues)
    counts: Dict[str, int] = {"total": total, "todo": todo_count}

    if todo_issues:
        return {"action": "take_over", "issues": todo_issues, "counts": counts}
    return {"action": "idle", "count": total, "counts": counts}


if __name__ == "__main__":
    def dummy_tool_call(cmd: str, payload: Dict[str, object]):
        raise RuntimeError("Runtime tool_call is not provided")

    print(run_module(dummy_tool_call))
