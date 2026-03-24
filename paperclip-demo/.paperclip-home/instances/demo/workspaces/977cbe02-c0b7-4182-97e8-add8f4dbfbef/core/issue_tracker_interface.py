class IssueTrackerInterface:
    """Abstract interface for issue trackers."""

    def list_issues(self, assignee: str):
        """Return a list of issues assigned to the given assignee.
        Each issue should be a dict containing at least:
        - id: unique identifier
        - title: brief description
        - status: current status string
        - assignee: owner of the issue
        - comments: list of comment dicts or strings (optional)
        """
        raise NotImplementedError

    def update_issue_status(self, issue_id, status: str) -> bool:
        """Update the status of an issue. Return True on success."""
        raise NotImplementedError

    def post_comment(self, issue_id, text: str) -> bool:
        """Post a comment to an issue. Return True on success."""
        raise NotImplementedError
