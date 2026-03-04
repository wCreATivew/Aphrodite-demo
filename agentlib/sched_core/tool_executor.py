from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class ToolResult:
    ok: bool
    tool_name: str
    output: str
    error: str = ""


class ToolExecutor:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[[str], str]] = {}

    def register(self, name: str, fn: Callable[[str], str]) -> None:
        self._tools[str(name)] = fn

    def run(self, name: str, query: str) -> ToolResult:
        tool_name = str(name)
        if tool_name not in self._tools:
            return ToolResult(ok=False, tool_name=tool_name, output="", error="tool_not_found")
        try:
            out = self._tools[tool_name](query)
            return ToolResult(ok=True, tool_name=tool_name, output=str(out))
        except Exception as e:
            return ToolResult(ok=False, tool_name=tool_name, output="", error=f"{type(e).__name__}: {e}")
