from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AdapterResult:
    tool: str
    task_id: str
    packet_path: Path | None = None
    result_path: Path | None = None


class ToolAdapter:
    tool_name: str

    def dispatch(self, task_id: str, packet_text: str, inbox_dir: Path) -> AdapterResult:
        raise NotImplementedError

    def collect(self, task_id: str, results_dir: Path) -> AdapterResult:
        raise NotImplementedError

