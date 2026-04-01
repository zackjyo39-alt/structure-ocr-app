from __future__ import annotations

from pathlib import Path

from .base import AdapterResult, ToolAdapter


class FileAdapter(ToolAdapter):
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name

    def dispatch(self, task_id: str, packet_text: str, inbox_dir: Path) -> AdapterResult:
        inbox_dir.mkdir(parents=True, exist_ok=True)
        packet_path = inbox_dir / f"{task_id}.md"
        packet_path.write_text(packet_text)
        return AdapterResult(tool=self.tool_name, task_id=task_id, packet_path=packet_path)

    def collect(self, task_id: str, results_dir: Path) -> AdapterResult:
        result_path = results_dir / f"{task_id}.json"
        if not result_path.exists():
            return AdapterResult(tool=self.tool_name, task_id=task_id, result_path=None)
        return AdapterResult(tool=self.tool_name, task_id=task_id, result_path=result_path)

