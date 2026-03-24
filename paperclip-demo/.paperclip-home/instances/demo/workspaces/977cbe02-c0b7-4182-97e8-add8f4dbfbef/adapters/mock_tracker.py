import json
from pathlib import Path
from typing import List, Dict, Any

from core.issue_tracker_interface import IssueTrackerInterface


class MockTracker(IssueTrackerInterface):
    def __init__(self, seed_path: str = "mock_issues.json"):
        self.seed_path = Path(seed_path)
        if not self.seed_path.exists():
            # create a minimal seed if missing
            self.seed_path.write_text(json.dumps({"issues": []}, indent=2))
        self._load()

    def _load(self):
        with self.seed_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.issues: List[Dict[str, Any]] = data.get("issues", [])

    def _save(self):
        with self.seed_path.open("w", encoding="utf-8") as f:
            json.dump({"issues": self.issues}, f, indent=2, ensure_ascii=True)

    # Implementation of the interface
    def list_issues(self, assignee: str):
        return [
            {**issue}
            for issue in self.issues
            if issue.get("assignee") == assignee
        ]

    def update_issue_status(self, issue_id, status: str) -> bool:
        updated = False
        for issue in self.issues:
            if issue.get("id") == issue_id:
                issue["status"] = status
                updated = True
                break
        if updated:
            self._save()
        return updated

    def post_comment(self, issue_id, text: str) -> bool:
        for issue in self.issues:
            if issue.get("id") == issue_id:
                comments = issue.setdefault("comments", [])
                comments.append({"author": "system", "text": text})
                self._save()
                return True
        return False

    # Convenience: seed data helpers (used by heartbeat tests)
    def add_issue(self, issue: Dict[str, Any]):
        self.issues.append(issue)
        self._save()
