from __future__ import annotations

from pathlib import Path

from .base import AdapterResult
from .file_adapter import FileAdapter


class OpenCodeAdapter(FileAdapter):
    def __init__(self) -> None:
        super().__init__("opencode")

    def dispatch(self, task_id: str, packet_text: str, inbox_dir: Path) -> AdapterResult:
        opencode_packet = (
            "# OpenCode Runner Packet\n\n"
            "Use this packet inside OpenCode as the current active slice.\n\n"
            "Execution contract:\n"
            "- read the full packet below\n"
            "- execute only the assigned slice\n"
            "- run the listed verification\n"
            "- write a JSON result file to automation/results/opencode/<task_id>.json\n"
            "- JSON keys required: task_id, tool, result, summary, verification\n\n"
            f"{packet_text}"
        )
        return super().dispatch(task_id, opencode_packet, inbox_dir)

