from __future__ import annotations

from .file_adapter import FileAdapter
from .opencode_adapter import OpenCodeAdapter


def get_adapter(tool_name: str) -> FileAdapter:
    if tool_name == "opencode":
        return OpenCodeAdapter()
    return FileAdapter(tool_name)
