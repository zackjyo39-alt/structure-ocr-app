"""Unit tests for Module-002 refined take_over logic."""

from importlib import util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("main.py")
_spec = util.spec_from_file_location("implement_002_main", MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("unable to load implement-002 runtime module")

_module = util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
partition_issues = _module.partition_issues
run_module = _module.run_module


class TestPartitionIssues(unittest.TestCase):
    def test_ignores_non_dicts(self):
        all_i, todo = partition_issues(
            [
                {"id": "a", "status": "To Do"},
                "not-a-dict",
                None,
                {"id": "b", "status": "Done"},
            ]
        )
        self.assertEqual(len(all_i), 2)
        self.assertEqual(len(todo), 1)
        self.assertEqual(todo[0]["id"], "a")

    def test_case_insensitive_todo(self):
        _, todo = partition_issues(
            [
                {"id": "1", "status": "TO DO"},
                {"id": "2", "status": "to do"},
                {"id": "3", "status": "  To   Do  "},
            ]
        )
        self.assertEqual({i["id"] for i in todo}, {"1", "2", "3"})


class TestRunModule(unittest.TestCase):
    def test_take_over_includes_counts(self):
        def tool_call(cmd, payload):
            self.assertEqual(cmd, "list_issues")
            self.assertEqual(payload, {"project_id": "current"})
            return [
                {"id": "ISSUE-001", "status": "to do"},
                {"id": "ISSUE-002", "status": "Done"},
            ]

        result = run_module(tool_call)
        self.assertEqual(result["action"], "take_over")
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["id"], "ISSUE-001")
        self.assertEqual(result["counts"], {"total": 2, "todo": 1})

    def test_idle_with_counts(self):
        def tool_call(cmd, payload):
            return [{"id": "x", "status": "In Review"}]

        result = run_module(tool_call)
        self.assertEqual(result["action"], "idle")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["counts"], {"total": 1, "todo": 0})

    def test_idle_non_dicts_excluded_from_count(self):
        def tool_call(cmd, payload):
            return [{"id": "x", "status": "Done"}, "skip", 42]

        result = run_module(tool_call)
        self.assertEqual(result["action"], "idle")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["counts"], {"total": 1, "todo": 0})

    def test_idle_when_tool_call_raises(self):
        def tool_call(cmd, payload):
            raise RuntimeError("runtime unavailable")

        result = run_module(tool_call)
        self.assertEqual(result, {"action": "idle", "count": 0, "counts": {"total": 0, "todo": 0}})

    def test_idle_on_non_list_response(self):
        def tool_call(cmd, payload):
            return {"error": "unexpected"}

        result = run_module(tool_call)
        self.assertEqual(result["counts"], {"total": 0, "todo": 0})


if __name__ == "__main__":
    unittest.main()
