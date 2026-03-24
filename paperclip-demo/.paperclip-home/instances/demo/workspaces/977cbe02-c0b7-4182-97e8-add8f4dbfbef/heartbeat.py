import time
import argparse
from typing import List, Dict, Any

from adapters.mock_tracker import MockTracker
from core.issue_tracker_interface import IssueTrackerInterface


class HeartbeatAgent:
    def __init__(self, assignee: str = "principal_architect", tracker: IssueTrackerInterface = None, loop: bool = False, interval: int = 10):
        self.assignee = assignee
        self.tracker = tracker or MockTracker()
        self.loop = loop
        self.interval = interval

    def _takeover(self, issue: Dict[str, Any]) -> bool:
        issue_id = issue.get("id")
        if not issue_id:
            return False
        # Takeover: assign to self and move to In Progress
        if issue.get("assignee") != self.assignee:
            issue["assignee"] = self.assignee
        if issue.get("status") != "In Progress":
            self.tracker.update_issue_status(issue_id, "In Progress")
        return True

    def _work_on_issue(self, issue: Dict[str, Any]) -> bool:
        # Simulate work by directly transitioning to In Review
        issue_id = issue.get("id")
        if not issue_id:
            return False
        self.tracker.update_issue_status(issue_id, "In Review")
        # Notify Architect for audit
        self.tracker.post_comment(issue_id, f"Audit requested by {self.assignee}: please review this issue: {issue.get('title')}")
        return True

    def heartbeat_once(self):
        issues = self.tracker.list_issues(self.assignee)
        # filter for To Do items assigned to me
        to_do_issues = [i for i in issues if i.get("status") in ("To Do", "ToDo", "Todo")]
        if not to_do_issues:
            # No work to do this heartbeat
            print("Heartbeat: no To Do issues. Staying Ready.")
            return
        # Take the first To Do item and takeover
        target = to_do_issues[0]
        self._takeover(target)
        # Immediately perform work and mark as In Review with audit comment
        self._work_on_issue(target)

    def run(self):
        if self.loop:
            while True:
                self.heartbeat_once()
                time.sleep(self.interval)
        else:
            self.heartbeat_once()


def main():
    parser = argparse.ArgumentParser(description="Heartbeat-driven Issue Handler (Mock)")
    parser.add_argument("--loop", action="store_true", help="Run heartbeat in a loop")
    parser.add_argument("--interval", type=int, default=10, help="Interval between heartbeats in seconds (if looping)")
    parser.add_argument("--assignee", default="principal_architect", help="Assignee username/id to operate on")
    args = parser.parse_args()

    agent = HeartbeatAgent(loop=args.loop, interval=args.interval, assignee=args.assignee)
    agent.run()


if __name__ == "__main__":
    main()
