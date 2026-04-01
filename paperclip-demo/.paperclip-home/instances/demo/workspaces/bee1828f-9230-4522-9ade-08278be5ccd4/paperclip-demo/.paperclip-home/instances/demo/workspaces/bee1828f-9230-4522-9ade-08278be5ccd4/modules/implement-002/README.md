# Module 002 · refined take_over

Builds on Module-001: same `tool_call("list_issues", {"project_id": "current"})` entry point,
with stricter normalization and richer payloads for logging and dashboards.

## Behavior vs Module-001

| Aspect | Module-001 | Module-002 |
|--------|------------|------------|
| To Do match | Exact `status == "To Do"` | Case-insensitive, trimmed, internal whitespace collapsed to match `to do` |
| Non-dict rows | Included in `len(issues)` if in list | Skipped for `count` / `counts.total` |
| Extra fields | `take_over` / `idle` only | Always includes `counts: { total, todo }` |

## Response shapes

- **take_over:** `{"action": "take_over", "issues": [...], "counts": {"total": N, "todo": M}}`
- **idle:** `{"action": "idle", "count": N, "counts": {"total": N, "todo": 0}}`  
  (`count` mirrors Module-001 idle semantics but counts **dict** issues only.)

## Testing

```bash
python3 modules/implement-002/test_main.py
```

## Helpers

`partition_issues(raw_list)` is pure and testable; use it from a harness if you need the
same rules outside `run_module`.
