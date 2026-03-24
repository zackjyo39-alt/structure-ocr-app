Heartbeat-driven Issue Handler (Mock)

Overview:
- On every heartbeat, the agent lists issues assigned to the configured assignee.
- If there are any issues in To Do status, it takes over one and starts work, otherwise it stays idle.
- On completion, the issue is moved to In Review and a review audit comment is posted for the Architect.

- Usage:
- Install Python 3.x, then run: python heartbeat.py
- By default, it runs once. For continuous operation, run: python heartbeat.py --loop --interval 10
- You can customize the assignee with: python heartbeat.py --assignee principal_architect
- Install Python 3.x, then run: python heartbeat.py
- By default, it runs once. For continuous operation, run: python heartbeat.py --loop --interval 10

Data:
- The mock data lives in mock_issues.json. Edit to seed or adjust test scenarios.
