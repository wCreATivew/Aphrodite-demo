from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from .schemas import TASK_KIND_CODE_TASK, TASK_KIND_PLAN_GOAL, Task, WorkerResult


class GLM5PlannerAdapter:
    def __init__(self, client: Optional[Callable[..., Any]] = None):
        self.client = client

    def plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raw: Any = None
        if callable(self.client):
            try:
                raw = self.client(goal=goal, context=context or {})
            except TypeError:
                raw = self.client(goal)

        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {"tasks": [], "plan_summary": raw}
        if not isinstance(raw, dict):
            raw = {}

        generated_subgoals, compile_issues = self._compile_planner_output(raw=raw, goal=goal, context=context or {})
        tasks = [self._legacy_task_from_subgoal(sg, default_priority=(20 + idx)) for idx, sg in enumerate(generated_subgoals)]

        if not generated_subgoals:
            fallback_sg = self._fallback_subgoal(goal=goal)
            generated_subgoals = [fallback_sg]
            tasks = [self._legacy_task_from_subgoal(fallback_sg, default_priority=30)]
            if compile_issues:
                compile_issues.append("planner_fallback_subgoal_injected")
        return {
            "tasks": tasks,
            "generated_subgoals": generated_subgoals,
            "plan_compile_issues": compile_issues,
            "ask_user": str(raw.get("ask_user") or "").strip(),
            "plan_summary": str(raw.get("plan_summary") or "").strip(),
        }

    @staticmethod
    def _fallback_subgoal(goal: str) -> Dict[str, Any]:
        text = str(goal or "").strip()
        return {
            "subgoal_id": "sg_fallback_01",
            "intent": f"Implement minimal first milestone for goal: {text}",
            "executor_type": TASK_KIND_CODE_TASK,
            "tool_name": TASK_KIND_CODE_TASK,
            "inputs": {"instruction": f"build first runnable piece for: {text}"},
            "dependencies": [],
            "preconditions": [{"op": "tool_available", "args": {"tool": TASK_KIND_CODE_TASK}}],
            "success_criteria": [{"op": "predicate_ref", "args": {"name": "worker_ok"}}],
            "retry_policy": {"max_attempts": 2, "backoff": "exponential", "base_delay_ms": 300},
            "fallback": {},
            "budget": {"max_steps": 1},
            "risk": "low",
        }

    @staticmethod
    def _legacy_task_from_subgoal(subgoal: Dict[str, Any], default_priority: int) -> Dict[str, Any]:
        sid = str(subgoal.get("subgoal_id") or "").strip()
        intent = str(subgoal.get("intent") or "").strip()
        tool = str(subgoal.get("tool_name") or subgoal.get("executor_type") or TASK_KIND_CODE_TASK).strip()
        inputs = dict(subgoal.get("inputs") or {})
        payload = dict(inputs)
        payload["dependencies"] = [str(x) for x in (subgoal.get("dependencies") or []) if str(x).strip()]
        payload["preconditions"] = list(subgoal.get("preconditions") or [])
        payload["success_criteria"] = list(subgoal.get("success_criteria") or [])
        payload["retry_policy"] = dict(subgoal.get("retry_policy") or {})
        payload["fallback"] = dict(subgoal.get("fallback") or {})
        payload["budget"] = dict(subgoal.get("budget") or {})
        payload["risk"] = str(subgoal.get("risk") or "low")
        payload["subgoal_id"] = sid
        return {
            "kind": tool,
            "description": intent,
            "priority": int(subgoal.get("priority") or default_priority),
            "input_payload": payload,
        }

    def _compile_planner_output(
        self,
        *,
        raw: Dict[str, Any],
        goal: str,
        context: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        issues: List[str] = []
        out: List[Dict[str, Any]] = []
        source = raw.get("generated_subgoals")
        if not isinstance(source, list):
            source = raw.get("subgoals")
        if not isinstance(source, list):
            source = raw.get("tasks")
        if not isinstance(source, list):
            source = []

        supervisor_context = dict(context.get("supervisor_context") or {})
        default_risk = str(context.get("risk_level") or supervisor_context.get("risk_level") or "low")
        remaining_budget = int(context.get("remaining_budget_steps") or 0)
        if remaining_budget <= 0:
            remaining_budget = max(1, int(context.get("budget_steps_max") or 20))
        mode_hint = str(supervisor_context.get("replan_template") or "")

        for idx, item in enumerate(source):
            if not isinstance(item, dict):
                issues.append(f"item_{idx}:not_object")
                continue
            compiled, item_issues = self._compile_subgoal_item(
                item=item,
                index=idx,
                default_goal=goal,
                default_risk=default_risk,
                remaining_budget=remaining_budget,
                mode_hint=mode_hint,
            )
            issues.extend(item_issues)
            if compiled:
                out.append(compiled)
        return out, issues

    def _compile_subgoal_item(
        self,
        *,
        item: Dict[str, Any],
        index: int,
        default_goal: str,
        default_risk: str,
        remaining_budget: int,
        mode_hint: str,
    ) -> tuple[Optional[Dict[str, Any]], List[str]]:
        issues: List[str] = []
        sid = str(item.get("subgoal_id") or item.get("id") or item.get("task_id") or "").strip()
        if not sid:
            sid = f"sg_{index + 1:02d}"
        intent = str(item.get("intent") or item.get("description") or "").strip()
        executor_type = str(item.get("executor_type") or item.get("kind") or item.get("tool_name") or "").strip()
        tool_name = str(item.get("tool_name") or item.get("kind") or executor_type or "").strip()
        if not intent:
            issues.append(f"{sid}:missing_intent")
            return None, issues
        if not tool_name:
            issues.append(f"{sid}:missing_tool_name")
            return None, issues
        if not executor_type:
            executor_type = tool_name
        inputs = dict(item.get("inputs") or item.get("input_payload") or {})
        deps = [str(x) for x in (item.get("dependencies") or []) if str(x).strip()]
        preconditions = list(item.get("preconditions") or [])
        if not preconditions:
            preconditions = [{"op": "tool_available", "args": {"tool": tool_name}}]
        success_criteria = list(item.get("success_criteria") or [])
        if not success_criteria:
            issues.append(f"{sid}:missing_success_criteria")
            return None, issues
        retry_policy = dict(item.get("retry_policy") or {})
        if not retry_policy:
            retry_policy = {"max_attempts": 2, "backoff": "exponential", "base_delay_ms": 300}
        fallback = dict(item.get("fallback") or {})
        budget = dict(item.get("budget") or {})
        if not budget:
            budget = {"max_steps": max(1, min(remaining_budget, 5))}
        risk = str(item.get("risk") or default_risk or "low")
        compiled = {
            "subgoal_id": sid,
            "intent": intent,
            "executor_type": executor_type,
            "tool_name": tool_name,
            "inputs": inputs,
            "dependencies": deps,
            "preconditions": preconditions,
            "success_criteria": success_criteria,
            "retry_policy": retry_policy,
            "fallback": fallback,
            "budget": budget,
            "risk": risk,
        }
        if mode_hint:
            compiled["replan_template"] = mode_hint
        return compiled, issues

    @staticmethod
    def input_schema() -> Dict[str, Any]:
        return {
            "required": ["goal"],
            "optional": [
                "task_id",
                "task_input_payload",
                "supervisor_context",
                "autonomous",
                "capability_snapshot",
                "risk_level",
                "remaining_budget_steps",
                "completed_nodes",
                "blocked_nodes",
                "failure_router_stats",
            ],
        }


class CodexCodeAdapter:
    def __init__(self, client: Optional[Callable[..., Any]] = None):
        self.client = client

    def execute(self, task: Task) -> WorkerResult:
        payload = dict(task.input_payload or {})
        if bool(payload.get("force_wait_user")):
            return WorkerResult(ok=False, wait_user=True, error="Need user input for code task.")
        if bool(payload.get("force_fail")) and int(task.retries or 0) < 1:
            return WorkerResult(ok=False, error="forced code failure for retry")

        raw: Any = None
        if callable(self.client):
            try:
                raw = self.client(task=task)
            except TypeError:
                raw = self.client(task)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {"ok": True, "output": {"summary": raw}}
        if raw is None:
            raw = {
                "ok": True,
                "output": {
                    "summary": f"stub codex execution for {task.task_id}",
                    "changed_files": [],
                },
                "artifacts": [f"codex::{task.task_id}::stub"],
            }
        if not isinstance(raw, dict):
            return WorkerResult(ok=False, error="codex_adapter_invalid_response")

        output = dict(raw.get("output") or {})
        contract = self._build_execution_contract(task=task, payload=payload, output=output, raw=raw)
        output["execution_contract"] = contract
        contract_issues = self._validate_execution_contract(output.get("execution_contract"))
        if contract_issues:
            output["contract_issues"] = list(contract_issues)

        return WorkerResult(
            ok=bool(raw.get("ok", True)),
            output=output,
            error=str(raw.get("error") or ""),
            wait_user=bool(raw.get("wait_user") or False),
            artifacts=[str(x) for x in (raw.get("artifacts") or []) if str(x).strip()],
        )

    @staticmethod
    def _build_execution_contract(
        *,
        task: Task,
        payload: Dict[str, Any],
        output: Dict[str, Any],
        raw: Dict[str, Any],
    ) -> Dict[str, Any]:
        existing = dict(output.get("execution_contract") or raw.get("execution_contract") or {})
        changed_files = [str(x) for x in (output.get("changed_files") or []) if str(x).strip()]
        proposed_action = str(existing.get("proposed_action") or "").strip()
        if not proposed_action:
            proposed_action = str(payload.get("instruction") or task.description or f"execute {task.task_id}").strip()
        assumed_preconditions = list(existing.get("assumed_preconditions") or [])
        if not assumed_preconditions:
            assumed_preconditions = ["workspace_access", "tool_available:code_task"]
            target_path = str(payload.get("target_path") or "").strip()
            if target_path:
                assumed_preconditions.append(f"target_exists_or_creatable:{target_path}")
        expected_artifacts = list(existing.get("expected_artifacts") or [])
        if not expected_artifacts:
            expected_artifacts = changed_files[:] if changed_files else [f"codex::{task.task_id}::result"]
        self_check_plan = list(existing.get("self_check_plan") or [])
        if not self_check_plan:
            self_check_plan = [
                "validate output summary is non-empty",
                "validate changed_files format",
                "run project minimal smoke test when available",
            ]
        rollback_hint = str(existing.get("rollback_hint") or "").strip()
        if not rollback_hint:
            rollback_hint = "revert changed files from VCS and retry with smaller patch"
        return {
            "proposed_action": proposed_action,
            "assumed_preconditions": [str(x) for x in assumed_preconditions if str(x).strip()],
            "expected_artifacts": [str(x) for x in expected_artifacts if str(x).strip()],
            "self_check_plan": [str(x) for x in self_check_plan if str(x).strip()],
            "rollback_hint": rollback_hint,
        }

    @staticmethod
    def _validate_execution_contract(contract: Any) -> List[str]:
        if not isinstance(contract, dict):
            return ["contract_not_object"]
        issues: List[str] = []
        required_scalar = ["proposed_action", "rollback_hint"]
        for k in required_scalar:
            if not str(contract.get(k) or "").strip():
                issues.append(f"missing_{k}")
        required_list = ["assumed_preconditions", "expected_artifacts", "self_check_plan"]
        for k in required_list:
            v = contract.get(k)
            if not isinstance(v, list) or len([x for x in v if str(x).strip()]) <= 0:
                issues.append(f"missing_{k}")
        return issues

    @staticmethod
    def input_schema() -> Dict[str, Any]:
        return {
            "required": [],
            "optional": [
                "instruction",
                "target_path",
                "max_retries",
                "force_fail",
                "force_wait_user",
                "proposed_action",
                "assumed_preconditions",
                "expected_artifacts",
                "self_check_plan",
                "rollback_hint",
                "command",
                "risk_level",
            ],
        }
