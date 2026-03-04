from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MemoryItem:
    text: str
    tier: str  # "short" | "task" | "long" | "tool"
    source: str = ""


class MemoryGovernance:
    def __init__(self) -> None:
        self.short: List[MemoryItem] = []
        self.task: List[MemoryItem] = []
        self.long: List[MemoryItem] = []
        self.tool: List[MemoryItem] = []

    def add(self, item: MemoryItem) -> None:
        tier = item.tier
        if tier == "short":
            self.short.append(item)
        elif tier == "task":
            self.task.append(item)
        elif tier == "tool":
            self.tool.append(item)
        else:
            self.long.append(item)

    def slice_for_prompt(self, max_items: int = 8, include_tool: bool = False) -> List[str]:
        items = []
        if self.task:
            items.extend(self.task)
        if include_tool and self.tool:
            items.extend(self.tool)
        if self.long:
            items.extend(self.long)
        out = [it.text for it in items]
        return out[:max_items]
