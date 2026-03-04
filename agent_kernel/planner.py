from __future__ import annotations

from typing import Optional

from .schemas import TASK_KIND_PLAN_GOAL, AgentState, Task


class SimplePlanner:
    def bootstrap(self, state: AgentState) -> None:
        if state.tasks:
            return
        task_id = f"t{state.next_task_seq:04d}"
        state.next_task_seq += 1
        state.tasks.append(
            Task(
                task_id=task_id,
                kind="bootstrap",
                description=f"Start toward goal: {state.goal}",
                input_payload={"goal": state.goal},
                priority=10,
                status="draft",
                retries=0,
            )
        )

    def select_next_task(self, state: AgentState) -> Optional[Task]:
        pending = [
            t
            for t in state.tasks
            if str(t.status or "").lower() in {"pending", "draft", "ready", "failed_retryable"}
        ]
        if not pending:
            return None
        pending.sort(key=lambda t: (int(t.priority), t.task_id))
        return pending[0]


class V15Planner(SimplePlanner):
    def bootstrap(self, state: AgentState) -> None:
        if state.tasks:
            return
        task_id = f"t{state.next_task_seq:04d}"
        state.next_task_seq += 1
        state.tasks.append(
            Task(
                task_id=task_id,
                kind=TASK_KIND_PLAN_GOAL,
                description=f"Plan decomposition for goal: {state.goal}",
                input_payload={"goal": state.goal},
                priority=5,
                status="draft",
                retries=0,
            )
        )
