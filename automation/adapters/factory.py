from __future__ import annotations

from .file_adapter import FileAdapter


def get_adapter(tool_name: str) -> FileAdapter:
    return FileAdapter(tool_name)

