Module 002 Plan
- Objective: Refine take_over detection and observability without changing the tool_call contract.
- Scope:
  - Normalize status strings (trim, collapse whitespace, case-insensitive match to "To Do").
  - Ignore non-dict entries when counting and filtering.
  - Always attach `counts`: `{ "total": N, "todo": M }` for idle and take_over.
- Milestones:
  1. Implement `partition_issues` and `run_module` refinements.
  2. Extend unit tests for normalization, junk rows, and count payloads.
  3. Document differences vs Module-001 in README.
- Success criteria:
  - Same take_over vs idle decisions as Module-001 for canonical `"To Do"` payloads.
  - Additional variants (`to do`, `TO DO`, extra spaces) classify as To Do.
- Commit workflow:
  - Commit with message: `feat(implement-002): refine list_issues take_over normalization`
- Blockers:
  - If runtime returns status in a non-string shape, treat as non-To Do (documented).
