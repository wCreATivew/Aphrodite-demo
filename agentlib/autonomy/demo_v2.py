from __future__ import annotations

# Allow direct execution: python agentlib/autonomy/demo_v2.py
if __package__ in {None, ""}:
    import types as _types
    import os as _os
    import sys as _sys

    _pkg_dir = _os.path.dirname(_os.path.abspath(__file__))
    _repo_root = _os.path.dirname(_os.path.dirname(_pkg_dir))
    if _repo_root not in _sys.path:
        _sys.path.insert(0, _repo_root)
    if "agentlib" not in _sys.modules:
        _pkg = _types.ModuleType("agentlib")
        _pkg.__path__ = [_os.path.join(_repo_root, "agentlib")]
        _sys.modules["agentlib"] = _pkg
    if "agentlib.autonomy" not in _sys.modules:
        _apkg = _types.ModuleType("agentlib.autonomy")
        _apkg.__path__ = [_pkg_dir]
        _sys.modules["agentlib.autonomy"] = _apkg
    __package__ = "agentlib.autonomy"

import json
from collections import defaultdict
from typing import List, Tuple

from .interfaces import Evaluator, Executor, Planner, Reflector, ToolRegistry
from .models import ExecutionRecord, Goal, ReflectionRecord, Task
from .orchestrator import Orchestrator
from .store import InMemoryStateStore
from .tool_registry import InMemoryToolRegistry
from .tracing import console_trace_hook


_CALLS = defaultdict(int)


class DemoPlanner(Planner):
    def plan(self, goal: Goal, store: InMemoryStateStore) -> List[Task]:
        return [
            Task(
                goal_id=goal.id,
                title="fetch",
                description="fetch context",
                tool_name="tool.fetch_context",
                input_payload={"query": "project-x"},
                max_attempts=2,
            ),
            Task(
                goal_id=goal.id,
                title="exec",
                description="exec code",
                tool_name="tool.exec_code",
                input_payload={"code_ref": "patch-001"},
                max_attempts=3,
            ),
            Task(
                goal_id=goal.id,
                title="auth",
                description="call auth api",
                tool_name="tool.auth_api",
                input_payload={"endpoint": "/secure"},
                max_attempts=2,
            ),
        ]

    def replan(self, goal: Goal, store: InMemoryStateStore, reflection: ReflectionRecord) -> List[Task]:
        return [
            Task(
                goal_id=goal.id,
                title="replan-fallback",
                description=f"fallback for {reflection.task_id}",
                tool_name="tool.exec_code",
                input_payload={"code_ref": "fallback"},
                max_attempts=2,
            )
        ]


class DemoExecutor(Executor):
    def execute(self, goal: Goal, task: Task, tools: ToolRegistry, store: InMemoryStateStore) -> ExecutionRecord:
        payload = json.dumps(dict(task.input_payload or {}), ensure_ascii=False)
        try:
            out = tools.run(task.tool_name, payload)
            return ExecutionRecord(
                goal_id=goal.id,
                task_id=task.id,
                tool_name=task.tool_name,
                input_payload=payload,
                success=True,
                output=str(out),
            )
        except Exception as e:
            return ExecutionRecord(
                goal_id=goal.id,
                task_id=task.id,
                tool_name=task.tool_name,
                input_payload=payload,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )


class DemoEvaluator(Evaluator):
    def evaluate(
        self, goal: Goal, task: Task, execution: ExecutionRecord, store: InMemoryStateStore
    ) -> Tuple[bool, str]:
        ok = bool(execution.success and "ok" in str(execution.output).lower())
        return ok, ("accepted" if ok else "rejected")


class DemoReflector(Reflector):
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
                reason="passed",
                replan_required=False,
            )
        # Leave replan decision to failure router in v2 flow.
        return ReflectionRecord(
            goal_id=goal.id,
            task_id=task.id,
            action="retry",
            reason=str(execution.error or evaluation_note),
            replan_required=False,
        )


def _tool_fetch_context(payload: str) -> str:
    _CALLS["tool.fetch_context"] += 1
    return f"ok:context:{payload}"


def _tool_exec_code(payload: str) -> str:
    _CALLS["tool.exec_code"] += 1
    if _CALLS["tool.exec_code"] <= 2:
        raise RuntimeError("TimeoutError: transient backend timeout")
    return f"ok:exec:{payload}"


def _tool_auth_api(payload: str) -> str:
    _CALLS["tool.auth_api"] += 1
    raise PermissionError("401 Unauthorized: missing token")


def main() -> None:
    store = InMemoryStateStore()
    tools = InMemoryToolRegistry()
    tools.register("tool.fetch_context", _tool_fetch_context, schema={"required": ["query"]})
    tools.register("tool.exec_code", _tool_exec_code, schema={"required": ["code_ref"]})
    tools.register("tool.auth_api", _tool_auth_api, schema={"required": ["endpoint"]})

    orch = Orchestrator(
        planner=DemoPlanner(),
        executor=DemoExecutor(),
        evaluator=DemoEvaluator(),
        reflector=DemoReflector(),
        tools=tools,
        store=store,
        trace_hooks=[console_trace_hook],
    )
    summary = orch.run_goal(
        Goal(objective="demo_v2: classify failures and avoid infinite fallback"),
        max_cycles=20,
    )
    print("\n=== SUMMARY V2 ===")
    print(summary)
    print("state:", store.state)
    print("tasks:", [(t.title, t.status, t.attempt_count, t.tool_name) for t in store.list_tasks(next(iter(store.goals)))])


if __name__ == "__main__":
    main()
