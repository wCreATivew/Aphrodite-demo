from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import ExecutionRecord, Goal, ReflectionRecord, Task
from .state import AgentState
from .tracing import TraceEvent


@dataclass
class InMemoryStateStore:
    state: AgentState = AgentState.IDLE
    goals: Dict[str, Goal] = field(default_factory=dict)
    tasks_by_goal: Dict[str, List[Task]] = field(default_factory=dict)
    executions: List[ExecutionRecord] = field(default_factory=list)
    reflections: List[ReflectionRecord] = field(default_factory=list)
    traces: List[TraceEvent] = field(default_factory=list)
    failure_fingerprints: List[str] = field(default_factory=list)
    replan_actions: List[str] = field(default_factory=list)
    last_done_ts: float = 0.0
    last_done_cycle: int = 0
    pause_requested: bool = False
    stop_requested: bool = False

    def add_goal(self, goal: Goal) -> None:
        self.goals[goal.id] = goal
        self.tasks_by_goal.setdefault(goal.id, [])

    def add_tasks(self, goal_id: str, tasks: List[Task]) -> None:
        self.tasks_by_goal.setdefault(goal_id, []).extend(tasks)

    def list_tasks(self, goal_id: str) -> List[Task]:
        return list(self.tasks_by_goal.get(goal_id, []))

    def next_pending_task(self, goal_id: str) -> Optional[Task]:
        for task in self.tasks_by_goal.get(goal_id, []):
            if str(task.status or "").lower() in {"pending", "draft", "ready", "failed_retryable"}:
                return task
        return None

    def add_execution(self, rec: ExecutionRecord) -> None:
        self.executions.append(rec)

    def add_reflection(self, rec: ReflectionRecord) -> None:
        self.reflections.append(rec)

    def add_trace(self, evt: TraceEvent) -> None:
        self.traces.append(evt)

    def set_state(self, state: AgentState) -> None:
        self.state = state

    def mark_done_progress(self, cycle: int, ts: float) -> None:
        self.last_done_cycle = max(int(self.last_done_cycle), int(cycle))
        self.last_done_ts = max(float(self.last_done_ts), float(ts))
