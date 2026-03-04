from __future__ import annotations

from typing import Callable, Dict, List


class InMemoryToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[[str], str]] = {}
        self._schemas: Dict[str, Dict[str, object]] = {}

    def register(self, name: str, fn: Callable[[str], str], schema: Dict[str, object] | None = None) -> None:
        k = str(name)
        self._tools[k] = fn
        self._schemas[k] = dict(schema or {"required": []})

    def has(self, name: str) -> bool:
        return str(name) in self._tools

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def run(self, name: str, payload: str) -> str:
        tool = self._tools.get(str(name))
        if tool is None:
            raise KeyError(f"tool_not_found: {name}")
        # TODO: enforce policy guards/sandbox contracts here for real tools.
        return str(tool(str(payload)))

    def get_tool_schema(self, name: str) -> Dict[str, object]:
        return dict(self._schemas.get(str(name), {"required": []}))
