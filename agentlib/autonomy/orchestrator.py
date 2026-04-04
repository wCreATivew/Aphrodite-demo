from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from agent_kernel.circuit_breaker import CircuitBreaker
from agent_kernel.compile_check import plan_compile_check
from agent_kernel.failure_router import classify_failure
from agent_kernel.local_replan import action_fingerprint
from agent_kernel.schemas import ExecutableSubgoal, RetryPolicy

from .interfaces import Evaluator, Executor, Planner, Reflector, ToolRegistry
from .models import Goal, ReflectionRecord, Task
from .state import AgentState
from .store import InMemoryStateStore
from .tracing import TraceEvent, TraceHook


class Orchestrator:
    def __init__(
        self,
        *,
        planner: Planner,
        executor: Executor,
        evaluator: Evaluator,
        reflector: Reflector,
        tools: ToolRegistry,
        store: Optional[InMemoryStateStore] = None,
        trace_hooks: Optional[List[TraceHook]] = None,
        emotion_state_provider: Optional[Callable[[InMemoryStateStore], Dict[str, Any]]] = None,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.evaluator = evaluator
        self.reflector = reflector
        self.tools = tools
        self.store = store or InMemoryStateStore()
        self.trace_hooks = list(trace_hooks or [])
        self.emotion_state_provider = emotion_state_provider
        self.circuit_breaker = CircuitBreaker(
            same_error_limit=2,
            same_action_replan_limit=3,
            stagnation_cycle_limit=10,
            stagnation_seconds=120,
        )

    def pause(self) -> None:
        self.store.pause_requested = True

    def resume(self) -> None:
        self.store.pause_requested = False

    def stop(self) -> None:
        self.store.stop_requested = True

    def _trace(self, stage: str, message: str, payload: Optional[Dict] = None) -> None:
        evt = TraceEvent(stage=stage, message=message, payload=dict(payload or {}))
        self.store.add_trace(evt)
        for hook in self.trace_hooks:
            hook(evt)

    def _read_perception(self, goal: Goal, cycle: int) -> Dict[str, Any]:
        emotion_state: Dict[str, Any] = {}
        if callable(self.emotion_state_provider):
            try:
                emotion_state = dict(self.emotion_state_provider(self.store) or {})
            except Exception as ex:
                self._trace("emotion", "emotion provider failed", {"error": str(ex)})
                emotion_state = {}
        perception = {"goal_id": goal.id, "cycle": int(cycle), "emotion_state": emotion_state}
        self._trace("perception", "perception fused", {"goal_id": goal.id, "cycle": cycle, "emotion": emotion_state})
        return perception

    def _update_state_from_perception(self, perception: Dict[str, Any]) -> None:
        emotion_state = dict(perception.get("emotion_state") or {})
        if emotion_state:
            self._trace("state", "emotion state merged", {"emotion_keys": sorted(emotion_state.keys())})

    def tick(self, goal: Goal, cycle: int) -> Optional[Task]:
        perception = self._read_perception(goal=goal, cycle=cycle)
        self._update_state_from_perception(perception)
        task = self.store.next_pending_task(goal.id)
        if task is None:
            self._trace("action_planner", "no pending task", {"goal_id": goal.id, "cycle": cycle})
            return None
        self._trace("action_planner", "next action selected", {"task_id": task.id, "cycle": cycle})
        return task

    def run_goal(self, goal: Goal, max_cycles: int = 30) -> Dict[str, int]:
        self.store.add_goal(goal)
        self.store.set_state(AgentState.PLANNING)
        self._trace("planning", "initial planning started", {"goal_id": goal.id})

        initial_tasks = self.planner.plan(goal, self.store)
        self.store.add_tasks(goal.id, initial_tasks)
        self._trace("planning", "initial plan ready", {"task_count": len(initial_tasks)})

        cycles = 0
        while cycles < max_cycles:
            cycles += 1

            if self.store.stop_requested:
                self.store.set_state(AgentState.STOPPED)
                self._trace("control", "stop requested")
                break

            if self.store.pause_requested:
                self.store.set_state(AgentState.PAUSED)
                self._trace("control", "paused")
                break

            perception_snapshot = self._run_perception_cycle()
            self.store.set_latest_perception(perception_snapshot)
            self._trace(
                "perception",
                "fusion completed",
                {
                    "aligned_events": len(perception_snapshot.get("aligned_events", [])),
                    "conflicts": len(perception_snapshot.get("conflicts", [])),
                    "degraded": int(bool(perception_snapshot.get("degraded"))),
                },
            )

            stagnation = self.circuit_breaker.check_stagnation(cycle=cycles, now_ts=time.time())
            if stagnation.triggered:
                self.store.set_state(AgentState.FAILED)
                self._trace("circuit_break", "no progress", {"reason": stagnation.reason, "details": stagnation.details})
                break

            compile_issues = plan_compile_check(
                subgoals=[self._to_subgoal(t) for t in self.store.list_tasks(goal.id)],
                tools=_ToolRegistryBridge(self.tools),
            )
            issues_by_task: Dict[str, List[str]] = {}
            for issue in compile_issues:
                issues_by_task.setdefault(str(issue.subgoal_id), []).append(str(issue.code))

            task = self.tick(goal=goal, cycle=cycles)
            if task is None:
                terminal = [t for t in self.store.list_tasks(goal.id) if t.status in {"done", "failed", "blocked"}]
                has_done = any(t.status == "done" for t in terminal)
                has_blocked = any(t.status == "blocked" for t in terminal)
                if has_done and (not has_blocked):
                    self.store.set_state(AgentState.COMPLETED)
                else:
                    self.store.set_state(AgentState.FAILED)
                break

            if issues_by_task.get(str(task.id)):
                task.status = "blocked"
                self._trace(
                    "compile",
                    "task blocked by compile check",
                    {"task_id": task.id, "issues": issues_by_task.get(str(task.id))},
                )
                continue

            task.status = "running"
            task.attempt_count += 1

            actor = str((task.input_payload or {}).get("actor") or "agent")
            perception = self.store.get_scene_perception(actor=actor)
            task.input_payload = dict(task.input_payload or {})
            task.input_payload["scene_perception"] = {
                "actor": perception.actor,
                "tick": perception.tick,
                "objects": perception.objects,
                "positions": perception.positions,
                "interactable_points": perception.interactable_points,
                "environment": perception.environment,
                "recent_deltas": perception.recent_deltas,
            }

            self.store.set_state(AgentState.EXECUTING)
            self._trace(
                "executing",
                "task execution started",
                {"task_id": task.id, "tool": task.tool_name, "scene_tick": perception.tick},
            )
            exec_rec = self.executor.execute(goal, task, self.tools, self.store)
            self.store.add_execution(exec_rec)

            self.store.set_state(AgentState.EVALUATING)
            passed, note = self.evaluator.evaluate(goal, task, exec_rec, self.store)
            self._trace("evaluating", "evaluation done", {"task_id": task.id, "passed": int(passed), "note": note})

            self.store.set_state(AgentState.REFLECTING)
            reflection: ReflectionRecord = self.reflector.reflect(
                goal, task, exec_rec, passed, note, self.store
            )
            self.store.add_reflection(reflection)
            self._trace("reflecting", "reflection produced", {"task_id": task.id, "action": reflection.action})

            if passed:
                task.status = "done"
                self.store.mark_done_progress(cycles, time.time())
                self.circuit_breaker.mark_done_progress(cycle=cycles, ts=time.time())
                continue

            if reflection.replan_required:
                self.store.set_state(AgentState.REPLANNING)
                extra_tasks = self.planner.replan(goal, self.store, reflection)
                action_fp = action_fingerprint(
                    ExecutableSubgoal(
                        id=str(task.id),
                        intent=str(task.description),
                        executor_type="replan",
                        tool_name=str(task.tool_name),
                    )
                )
                cb_replan = self.circuit_breaker.on_replan_action(
                    path_key=str(task.id),
                    action_fingerprint=action_fp,
                )
                self.store.replan_actions.append(action_fp)
                if cb_replan.triggered:
                    task.status = "failed"
                    self.store.set_state(AgentState.FAILED)
                    self._trace("circuit_break", "replan loop circuit break", {"reason": cb_replan.reason})
                    break
                self.store.add_tasks(goal.id, extra_tasks)
                task.status = "failed"
                self._trace("replanning", "new tasks appended", {"new_tasks": len(extra_tasks)})
                continue

            decision = classify_failure(
                subgoal_id=str(task.id),
                tool_name=str(task.tool_name),
                error_message=str(exec_rec.error or note or "execution_failed"),
                prior_fingerprints=self.store.failure_fingerprints,
            )
            self.store.failure_fingerprints.append(decision.fingerprint)
            self._trace(
                "failure_routed",
                "failure routed",
                {
                    "task_id": task.id,
                    "category": decision.category.value,
                    "action": decision.action.value,
                    "reason": decision.reason,
                },
            )
            cb_err = self.circuit_breaker.on_error(subgoal_id=str(task.id), fingerprint=decision.fingerprint)
            if cb_err.triggered:
                task.status = "failed"
                self.store.set_state(AgentState.FAILED)
                self._trace("circuit_break", "same error repeated", {"task_id": task.id, "reason": cb_err.reason})
                break

            if decision.action.value == "retry" and task.attempt_count < task.max_attempts:
                task.status = "pending"
                continue
            if decision.action.value in {"ask_user", "repair_auth"}:
                task.status = "blocked"
                continue
            if decision.action.value in {"local_replan", "local_replan_with_constraints"}:
                self.store.set_state(AgentState.REPLANNING)
                extra_tasks = self.planner.replan(
                    goal,
                    self.store,
                    ReflectionRecord(
                        goal_id=goal.id,
                        task_id=task.id,
                        action="replan",
                        reason=decision.reason,
                        replan_required=True,
                    ),
                )
                self.store.add_tasks(goal.id, extra_tasks)
                task.status = "failed"
                continue

            task.status = "failed"
            self.store.set_state(AgentState.FAILED)
            break

        done = len([t for t in self.store.list_tasks(goal.id) if t.status == "done"])
        failed = len([t for t in self.store.list_tasks(goal.id) if t.status in {"failed", "blocked"}])
        return {"cycles": cycles, "done": done, "failed": failed, "traces": len(self.store.traces)}

    def _run_perception_cycle(self) -> Dict[str, object]:
        frames = []
        for adapter in self._adapters:
            try:
                frame = adapter.read()
            except Exception as exc:
                self._trace(
                    "perception",
                    "adapter read failed",
                    {"modality": getattr(adapter, "modality", "unknown"), "error": str(exc)},
                )
                continue
            if frame:
                frames.append(frame)
        return self.perception_fusion.run_cycle(frames)

    @staticmethod
    def _to_subgoal(task) -> ExecutableSubgoal:
        payload = dict(getattr(task, "input_payload", {}) or {})
        return ExecutableSubgoal(
            id=str(task.id),
            intent=str(task.description or ""),
            executor_type=str(task.tool_name or ""),
            tool_name=str(task.tool_name or ""),
            inputs=payload,
            dependencies=[str(x) for x in list(getattr(task, "dependencies", []) or []) if str(x).strip()],
            preconditions=[],
            success_criteria=[],
            failure_modes=[],
            fallback=dict(getattr(task, "fallback", {}) or {}),
            retry_policy=RetryPolicy(max_attempts=max(1, int(getattr(task, "max_attempts", 2) or 2))),
        )


class _ToolRegistryBridge:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    def has_tool(self, tool_name: str) -> bool:
        return bool(self.tools.has(str(tool_name or "")))

    def get_tool_schema(self, tool_name: str) -> Dict[str, object]:
        fn = getattr(self.tools, "get_tool_schema", None)
        if callable(fn):
            try:
                out = fn(str(tool_name or ""))
                if isinstance(out, dict):
                    return out
            except Exception:
                return {"required": []}
        return {"required": []}
