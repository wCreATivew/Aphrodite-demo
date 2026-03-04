from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MemorySlice:
    goal_hint: str
    retrieved: List[str]
    notes: str = ""


def arbitrate_memory(
    user_text: str,
    retrieved: List[str],
    goal_hint: Optional[str] = None,
) -> MemorySlice:
    """
    Minimal arbiter:
    - keep retrieved memory as-is (but cap count)
    - attach a goal hint
    """
    hint = (goal_hint or "").strip()
    max_items = 3
    return MemorySlice(goal_hint=hint, retrieved=list(retrieved)[:max_items], notes="")
