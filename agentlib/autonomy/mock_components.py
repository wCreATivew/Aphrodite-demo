from __future__ import annotations

import time
from typing import List, Tuple

from .interfaces import Evaluator, Executor, Planner, Reflector, ToolRegistry
from .models import ExecutionRecord, Goal, ReflectionRecord, Task
from .store import InMemoryStateStore


class MockPlanner(Planner):
    def plan(self, goal: Goal, store: InMemoryStateStore) -> List[Task]:
        return [
            Task(
                goal_id=goal.id,
                title="Try first tool path",
                description=f"Initial attempt for: {goal.objective}",
                tool_name="mock.fail",
                acceptance_criteria=["output contains ok"],
            )
        ]

    def replan(self, goal: Goal, store: InMemoryStateStore, reflection: ReflectionRecord) -> List[Task]:
        if reflection.next_task_hint == "use_success_tool":
            return [
                Task(
                    goal_id=goal.id,
                    title="Fallback success path",
                    description=f"Fallback for: {goal.objective}",
                    tool_name="mock.success",
                    acceptance_criteria=["output contains ok"],
                )
            ]
        return []


class MockExecutor(Executor):
    def execute(self, goal: Goal, task: Task, tools: ToolRegistry, store: InMemoryStateStore) -> ExecutionRecord:
        t0 = time.time()
        try:
            output = tools.run(task.tool_name, task.description)
            return ExecutionRecord(
                goal_id=goal.id,
                task_id=task.id,
                tool_name=task.tool_name,
                input_payload=task.description,
                success=True,
                output=output,
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as e:
            return ExecutionRecord(
                goal_id=goal.id,
                task_id=task.id,
                tool_name=task.tool_name,
                input_payload=task.description,
                success=False,
                error=f"{type(e).__name__}: {e}",
                latency_ms=int((time.time() - t0) * 1000),
            )
        # TODO: real executor should support async jobs, tool timeouts, retries, and policy checks.


class MockEvaluator(Evaluator):
    def evaluate(
        self, goal: Goal, task: Task, execution: ExecutionRecord, store: InMemoryStateStore
    ) -> Tuple[bool, str]:
        passed = bool(execution.success and ("ok" in execution.output.lower()))
        note = "accepted" if passed else "not accepted"
        return passed, note
        # TODO: replace with LLM/criteria evaluator when real acceptance checks are wired.


class MockReflector(Reflector):
    def reflect(
        self,
        goal: Goal,
        task: Task,
        execution: ExecutionRecord,
        passed: bool,
        evaluation_note: str,
        store: InMemoryStateStore,
    ) -> ReflectionRecord:
        if passed:
            return ReflectionRecord(
                goal_id=goal.id,
                task_id=task.id,
                action="none",
                reason=evaluation_note,
                replan_required=False,
            )
        if task.attempt_count >= 1:
            return ReflectionRecord(
                goal_id=goal.id,
                task_id=task.id,
                action="replan",
                reason="switch tool path after failure",
                replan_required=True,
                next_task_hint="use_success_tool",
            )
        return ReflectionRecord(
            goal_id=goal.id,
            task_id=task.id,
            action="retry",
            reason="first failure",
            replan_required=False,
        )

