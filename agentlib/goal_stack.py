from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Goal:
    text: str
    priority: int = 0
    done: bool = False
    notes: str = ""


@dataclass
class GoalStack:
    goals: List[Goal] = field(default_factory=list)

    def push(self, text: str, priority: int = 0, notes: str = "") -> Goal:
        g = Goal(text=text, priority=int(priority), done=False, notes=str(notes))
        self.goals.append(g)
        self._sort()
        return g

    def _sort(self) -> None:
        self.goals.sort(key=lambda g: (g.done, -g.priority))

    def current(self) -> Optional[Goal]:
        for g in self.goals:
            if not g.done:
                return g
        return None

    def mark_done(self, idx: int) -> None:
        if 0 <= idx < len(self.goals):
            self.goals[idx].done = True
            self._sort()

    def clear_done(self) -> None:
        self.goals = [g for g in self.goals if not g.done]
