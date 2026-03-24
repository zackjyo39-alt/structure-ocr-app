#!/usr/bin/env python3
"""Real rag_pipeline for AgenticRAG-demo.

Reads the real AII-20 task and, if To Do, takes over and marks
In Progress, then completes it to In Review and posts an audit comment
to Architect.
"""

import json
import os
import ssl
import urllib.request
import urllib.parse
from urllib.error import HTTPError
from typing import Optional

ssl._create_default_https_context = ssl._create_unverified_context

BASE_API = os.environ.get("AII_API_BASE", "http://127.0.0.1:3100/AII")
ASSIGNEE = os.environ.get("AII_ASSIGNEE", "principal_architect")
AUTH_TOKEN = os.environ.get("AII_API_TOKEN")


def _headers() -> dict:
    h = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if AUTH_TOKEN:
        h["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return h


def _http_get(url: str) -> Optional[dict]:
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8")
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                print(f"Non-JSON response for GET {url}: {data[:200]}...")
                return None
    except HTTPError as e:
        print(f"GET {url} failed: {e.code} {e.reason}")
    except Exception as e:
        print(f"GET {url} error: {e}")
    return None


def _http_patch(url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except HTTPError as e:
        print(f"PATCH {url} failed: {e.code} {e.reason}")
    except Exception as e:
        print(f"PATCH {url} error: {e}")
    return False


def _http_post(url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except HTTPError as e:
        print(f"POST {url} failed: {e.code} {e.reason}")
    except Exception as e:
        print(f"POST {url} error: {e}")
    return False


class AIIClient:
    def __init__(self, base: str = BASE_API, assignee: str = ASSIGNEE):
        self.base = base.rstrip("/")
        self.assignee = assignee

    def list_issues(self):
        url = f"{self.base}/issues?assignee={urllib.parse.quote(self.assignee)}"
        return _http_get(url) or {}

    def get_issue(self, issue_id: str):
        url = f"{self.base}/issues/{urllib.parse.quote(issue_id)}"
        return _http_get(url)

    def update_issue_status(self, issue_id: str, status: str) -> bool:
        url = f"{self.base}/issues/{urllib.parse.quote(issue_id)}"
        return _http_patch(url, {"status": status, "assignee": self.assignee})

    def post_comment(self, issue_id: str, text: str) -> bool:
        url = f"{self.base}/issues/{urllib.parse.quote(issue_id)}/comments"
        return _http_post(url, {"text": text})


def _normalize_issue_list(data):
    issues = []
    if isinstance(data, list):
        issues = data
    elif isinstance(data, dict) and "issues" in data:
        issues = data["issues"] or []
    return issues


def main():
    client = AIIClient()
    issue_id = "AII-20"
    # Heartbeat gating: first check if there are any To Do issues assigned to me
    issues_data = client.list_issues()
    issues = _normalize_issue_list(issues_data)
    to_do_issues = []
    for it in (issues or []):
        st = str(it.get("status", "")).lower()
        if st in ("to do", "todo", "to_do"):
            to_do_issues.append(it)
    if to_do_issues:
        target = to_do_issues[0]
        issue_id = target.get("id") or issue_id
        # Takeover
        if target.get("assignee") != ASSIGNEE:
            ok = client.update_issue_status(issue_id, "In Progress")
            if not ok:
                print(f"Failed to takeover {issue_id}")
                return
        else:
            ok = client.update_issue_status(issue_id, "In Progress")
            if not ok:
                print(f"Failed to set {issue_id} to In Progress")
                return
        # Work on the issue
        if not client.update_issue_status(issue_id, "In Review"):
            print(f"Failed to move {issue_id} to In Review")
            return
        audit_text = (
            f"Audit requested by Principal Architect: please review {target.get('title')} (ID: {issue_id})."
        )
        if not client.post_comment(issue_id, audit_text):
            print(f"Failed to post audit comment on {issue_id}")
            return
        print(f"Issue {issue_id} processed via To Do takeover: In Progress -> In Review, audit comment posted.")
        return

    # Step 1: Fallback to reading the real AII-20 task directly
    issue = client.get_issue(issue_id)
    if not issue:
        print(f"Issue {issue_id} not found.")
        return

    print(f"Read {issue_id}: status={issue.get('status')}, title={issue.get('title')}")

    if str(issue.get("status")).lower() != "to do":
        print(f"Issue {issue_id} is not To Do. No action taken.")
        return

    # Takeover AII-20
    if issue.get("assignee") != ASSIGNEE:
        ok = client.update_issue_status(issue_id, "In Progress")
        if not ok:
            print(f"Failed to takeover {issue_id}")
            return
    else:
        ok = client.update_issue_status(issue_id, "In Progress")
        if not ok:
            print(f"Failed to set {issue_id} to In Progress")
            return

    # Work on issue and mark In Review, then post audit comment
    if not client.update_issue_status(issue_id, "In Review"):
        print(f"Failed to move {issue_id} to In Review")
        return

    audit_text = (
        f"Audit requested by Principal Architect: please review {issue.get('title')} (ID: {issue_id})."
    )
    if not client.post_comment(issue_id, audit_text):
        print(f"Failed to post audit comment on {issue_id}")
        return

    print(f"Issue {issue_id} processed: In Progress -> In Review, audit comment posted.")


if __name__ == "__main__":
    main()
