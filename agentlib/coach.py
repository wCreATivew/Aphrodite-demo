from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence


@dataclass
class SkillProfile:
    name: str
    operation_difficulty: float
    learning_cost: float
    success_rate: float = 0.8
    avg_cost: float = 1.0


@dataclass
class CoachDecision:
    mode: str  # ONESHOT | BUDGETED
    action: str  # EXECUTE_LIGHT | EXECUTE_HEAVY | TOOL_LIGHT
    budget_initial: float
    complexity: float
    capability: float
    gap: float
    learning_gap: List[str] = field(default_factory=list)


class Coach:
    """Core decision module for execute flow."""

    def __init__(self) -> None:
        self.skill_inventory: Dict[str, SkillProfile] = {
            "code_expert": SkillProfile("code_expert", 0.8, 0.3, success_rate=0.82, avg_cost=0.9),
            "planner": SkillProfile("planner", 0.4, 0.2, success_rate=0.9, avg_cost=0.5),
            "gui_operator": SkillProfile("gui_operator", 0.7, 0.6, success_rate=0.7, avg_cost=1.3),
            "filesystem": SkillProfile("filesystem", 0.5, 0.2, success_rate=0.88, avg_cost=0.6),
            "env_manager": SkillProfile("env_manager", 0.8, 0.5, success_rate=0.72, avg_cost=1.1),
        }

    def decide(self, user_message: str, action_hint: str, required_tools: Sequence[str]) -> CoachDecision:
        complexity = self.compute_complexity(required_tools)
        capability = self.compute_capability(required_tools)
        gap = capability - complexity
        mode = "ONESHOT" if gap >= 0.25 else "BUDGETED"
        budget = self.initial_budget(gap)
        learning_gap = self.learning_gap(required_tools)
        return CoachDecision(
            mode=mode,
            action=action_hint,
            budget_initial=budget,
            complexity=complexity,
            capability=capability,
            gap=gap,
            learning_gap=learning_gap,
        )

    def compute_complexity(self, required_tools: Sequence[str]) -> float:
        if not required_tools:
            return 0.4
        total = 0.0
        for tool in required_tools:
            p = self.skill_inventory.get(tool)
            if p is None:
                total += 1.2
            else:
                total += p.operation_difficulty * 0.7 + p.learning_cost * 0.3
        return total

    def compute_capability(self, required_tools: Sequence[str]) -> float:
        if not required_tools:
            return 0.9
        total = 0.0
        for tool in required_tools:
            p = self.skill_inventory.get(tool)
            if p is None:
                total += 0.2
            else:
                total += p.success_rate * 0.8 + (1.0 / (1.0 + p.avg_cost)) * 0.2
        return total

    @staticmethod
    def initial_budget(gap: float) -> float:
        if gap >= 0.25:
            return 1.2
        if gap >= 0.0:
            return 1.0
        return 0.75

    def learning_gap(self, required_tools: Sequence[str]) -> List[str]:
        missing: List[str] = []
        for tool in required_tools:
            if tool not in self.skill_inventory:
                missing.append(tool)
        return missing
