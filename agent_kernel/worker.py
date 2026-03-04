from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from .adapters import CodexCodeAdapter, GLM5PlannerAdapter
from .compile_check import CompileIssue, action_plan_gate_check
from .schemas import TASK_KIND_ASK_USER, TASK_KIND_CODE_TASK, TASK_KIND_PLAN_GOAL
from .schemas import ExecutableSubgoal, SuccessCriterion, Task, WorkerResult


class SimpleWorker:
    def __init__(self, semantic_router: Optional[Callable[[Task], Dict[str, Any]]] = None):
        self.semantic_router = semantic_router
        self._tool_health: Dict[str, Dict[str, Any]] = {}
        self._tool_health_window = 20
        self._tool_cooldown_error_threshold = 3

    def execute(self, task: Task) -> WorkerResult:
        if callable(self.semantic_router):
            try:
                routed = self.semantic_router(task) or {}
                if bool(routed.get("wait_user")):
                    return WorkerResult(
                        ok=False,
                        output={"router": routed},
                        wait_user=True,
                        error=str(routed.get("question") or "Need user input"),
                    )
            except Exception as e:
                return WorkerResult(ok=False, error=f"semantic_router_error: {type(e).__name__}: {e}")

        payload = dict(task.input_payload or {})
        schema = self.get_tool_schema(str(task.kind or ""))
        required = [str(x) for x in list(schema.get("required") or []) if str(x).strip()]
        missing = [k for k in required if k not in payload]
        if missing:
            return WorkerResult(ok=False, error=f"missing_input: {missing}")
        if bool(payload.get("force_wait_user")):
            return WorkerResult(ok=False, wait_user=True, error="Please provide missing context.")
        if bool(payload.get("force_fail")) and int(task.retries) < 1:
            return WorkerResult(ok=False, error="Stub worker forced failure for retry path.")

        artifact = f"artifact::{task.task_id}::done"
        return WorkerResult(
            ok=True,
            output={"task_id": task.task_id, "summary": f"Executed: {task.description}"},
            artifacts=[artifact],
        )

    @staticmethod
    def has_tool(tool_name: str) -> bool:
        return str(tool_name or "").strip().lower() in {
            TASK_KIND_PLAN_GOAL,
            TASK_KIND_CODE_TASK,
            TASK_KIND_ASK_USER,
            "bootstrap",
        }

    @staticmethod
    def get_tool_schema(tool_name: str) -> Dict[str, Any]:
        t = str(tool_name or "").strip().lower()
        if t == TASK_KIND_PLAN_GOAL:
            return {"required": ["goal"]}
        if t == TASK_KIND_ASK_USER:
            return {"required": []}
        if t in {TASK_KIND_CODE_TASK, "bootstrap"}:
            return {"required": []}
        return {"required": []}

    def list_tools(self) -> list[str]:
        return [TASK_KIND_PLAN_GOAL, TASK_KIND_CODE_TASK, TASK_KIND_ASK_USER, "bootstrap"]

    @staticmethod
    def _error_signature(error: str) -> str:
        txt = str(error or "").strip().lower()
        if not txt:
            return ""
        if ":" in txt:
            return txt.split(":", 1)[0]
        return "execution_error"

    def record_tool_invocation(self, *, tool_name: str, ok: bool, latency_ms: float, error_signature: str) -> None:
        t = str(tool_name or "").strip().lower()
        if not t:
            return
        st = self._tool_health.setdefault(
            t,
            {"calls": 0, "ok": 0, "fail": 0, "lat_ms_sum": 0.0, "recent_ok": [], "recent_errors": {}, "cooldown": 0},
        )
        st["calls"] = int(st.get("calls", 0) or 0) + 1
        st["ok"] = int(st.get("ok", 0) or 0) + (1 if ok else 0)
        st["fail"] = int(st.get("fail", 0) or 0) + (0 if ok else 1)
        st["lat_ms_sum"] = float(st.get("lat_ms_sum", 0.0) or 0.0) + float(max(0.0, latency_ms))
        recent_ok = list(st.get("recent_ok") or [])
        recent_ok.append(1 if ok else 0)
        recent_ok = recent_ok[-int(self._tool_health_window):]
        st["recent_ok"] = recent_ok
        if (not ok) and error_signature:
            err_dist = dict(st.get("recent_errors") or {})
            err_dist[error_signature] = int(err_dist.get(error_signature, 0) or 0) + 1
            for k in list(err_dist.keys()):
                err_dist[k] = max(0, int(err_dist[k]) - 1)
                if err_dist[k] <= 0:
                    err_dist.pop(k, None)
            st["recent_errors"] = err_dist
        consecutive_fail = 0
        for v in reversed(recent_ok):
            if v == 1:
                break
            consecutive_fail += 1
        st["cooldown"] = 1 if consecutive_fail >= int(self._tool_cooldown_error_threshold) else 0
        self._tool_health[t] = st

    def get_tool_health(self, tool_name: str) -> Dict[str, Any]:
        t = str(tool_name or "").strip().lower()
        st = dict(self._tool_health.get(t) or {})
        calls = max(1, int(st.get("calls", 0) or 0))
        recent_ok = list(st.get("recent_ok") or [])
        recent_success = (sum(recent_ok) / float(len(recent_ok))) if recent_ok else (float(st.get("ok", 0) or 0) / float(calls))
        return {
            "success_rate_recent_n": round(float(recent_success), 4),
            "avg_latency_ms": round(float(st.get("lat_ms_sum", 0.0) or 0.0) / float(calls), 2),
            "error_distribution": dict(st.get("recent_errors") or {}),
            "cooldown": int(st.get("cooldown", 0) or 0),
            "window_n": int(self._tool_health_window),
            "calls": int(st.get("calls", 0) or 0),
        }

    def get_capability_snapshot(self) -> Dict[str, Any]:
        tools = self.list_tools()
        return {
            "tools": [{"tool_name": t, "schema": self.get_tool_schema(t), "health": self.get_tool_health(t)} for t in tools],
        }


class SpecialistRouterWorker:
    def __init__(
        self,
        planner_adapter: Optional[GLM5PlannerAdapter] = None,
        code_adapter: Optional[CodexCodeAdapter] = None,
        semantic_router: Optional[Callable[[Task], Dict[str, Any]]] = None,
    ):
        self.planner_adapter = planner_adapter or GLM5PlannerAdapter()
        self.code_adapter = code_adapter or CodexCodeAdapter()
        self.semantic_router = semantic_router
        self._expert_stats: Dict[str, Dict[str, Any]] = {
            "planner": {"calls": 0, "ok": 0, "fail": 0, "lat_ms_sum": 0.0, "recent_errors": [], "cost_sum": 0.0},
            "codex": {"calls": 0, "ok": 0, "fail": 0, "lat_ms_sum": 0.0, "recent_errors": [], "cost_sum": 0.0},
        }
        self._tool_health: Dict[str, Dict[str, Any]] = {}
        self._tool_health_window = 30
        self._tool_cooldown_error_threshold = 3

    @staticmethod
    def _serialize_issues(issues: List[CompileIssue]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for i in list(issues or []):
            out.append(
                {
                    "code": str(i.code),
                    "subgoal_id": str(i.subgoal_id),
                    "message": str(i.message),
                    "severity": str(i.severity),
                    "hint": str(i.hint),
                }
            )
        return out

    @staticmethod
    def _default_success_criteria(task: Task) -> List[SuccessCriterion]:
        kind = str(task.kind or "").strip().lower()
        if kind == TASK_KIND_PLAN_GOAL:
            return [SuccessCriterion(op="field_equals", args={"field": "planner_ok", "value": True})]
        if kind == TASK_KIND_ASK_USER:
            return [SuccessCriterion(op="predicate_ref", args={"name": "asked_user"})]
        return [SuccessCriterion(op="predicate_ref", args={"name": "worker_ok"})]

    @staticmethod
    def _clone_subgoal_for_gate(task: Task) -> ExecutableSubgoal:
        sg = ExecutableSubgoal.from_task(task)
        if not list(sg.success_criteria or []):
            sg.success_criteria = SpecialistRouterWorker._default_success_criteria(task)
        return sg

    @staticmethod
    def _risk_level(task: Task) -> str:
        payload = dict(task.input_payload or {})
        risk = str(payload.get("risk_level") or "").strip().lower()
        if risk:
            return risk
        text = f"{task.description} {payload}".lower()
        if any(k in text for k in ["autopilot", "selfdrive", "system", "batch", "批量", "系统改动"]):
            return "high"
        return "low"

    @staticmethod
    def _candidate_experts(kind: str) -> List[str]:
        if kind == TASK_KIND_PLAN_GOAL:
            return ["planner", "codex"]
        if kind == TASK_KIND_CODE_TASK:
            return ["codex", "planner"]
        return ["planner", "codex"]

    @staticmethod
    def _capability_fit(kind: str, expert: str) -> float:
        if kind == TASK_KIND_PLAN_GOAL:
            return 1.0 if expert == "planner" else 0.35
        if kind == TASK_KIND_CODE_TASK:
            return 1.0 if expert == "codex" else 0.30
        if kind == TASK_KIND_ASK_USER:
            return 0.20
        return 0.45

    @staticmethod
    def _expert_cost(expert: str) -> float:
        return 1.0 if expert == "planner" else 2.8

    def _stats_for(self, expert: str) -> Dict[str, Any]:
        return dict(self._expert_stats.get(expert) or {})

    def _record_expert_result(self, *, expert: str, ok: bool, latency_ms: float) -> None:
        stats = self._expert_stats.setdefault(
            expert, {"calls": 0, "ok": 0, "fail": 0, "lat_ms_sum": 0.0, "recent_errors": [], "cost_sum": 0.0}
        )
        stats["calls"] = int(stats.get("calls", 0) or 0) + 1
        stats["ok"] = int(stats.get("ok", 0) or 0) + (1 if ok else 0)
        stats["fail"] = int(stats.get("fail", 0) or 0) + (0 if ok else 1)
        stats["lat_ms_sum"] = float(stats.get("lat_ms_sum", 0.0) or 0.0) + float(max(0.0, latency_ms))
        stats["cost_sum"] = float(stats.get("cost_sum", 0.0) or 0.0) + self._expert_cost(expert)
        recent = list(stats.get("recent_errors") or [])
        recent.append(0 if ok else 1)
        stats["recent_errors"] = recent[-20:]
        self._expert_stats[expert] = stats

    @staticmethod
    def _error_signature(error: str) -> str:
        txt = str(error or "").strip().lower()
        if not txt:
            return ""
        if ":" in txt:
            return txt.split(":", 1)[0]
        return "execution_error"

    @staticmethod
    def _schema_version(schema: Dict[str, Any]) -> str:
        raw = str(sorted((schema or {}).items()))
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:10]

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        u = urlparse(str(value or "").strip())
        return bool(u.scheme in {"http", "https"} and u.netloc)

    def _semantic_validate_inputs(self, *, kind: str, payload: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        # Path checks.
        for key in ("target_path", "file_path", "path"):
            p = payload.get(key)
            if p is None:
                continue
            path = str(p).strip()
            if not path:
                issues.append(f"{key}:empty")
                continue
            if not (os.path.exists(path) or os.path.exists(os.path.dirname(path) or ".")):
                issues.append(f"{key}:path_not_found")
            if str(payload.get("write", "")).strip().lower() in {"1", "true", "yes", "on"}:
                parent = os.path.dirname(path) or "."
                if not os.access(parent, os.W_OK):
                    issues.append(f"{key}:path_not_writable")
        # URL checks.
        for key in ("url", "endpoint", "webhook_url"):
            v = payload.get(key)
            if v is None:
                continue
            if not self._is_valid_url(str(v)):
                issues.append(f"{key}:invalid_url")
        # ID checks.
        for key in ("id", "task_id", "subgoal_id"):
            if key not in payload:
                continue
            v = str(payload.get(key) or "").strip()
            if not v:
                issues.append(f"{key}:empty")
            elif not re.match(r"^[A-Za-z0-9_.:-]{2,128}$", v):
                issues.append(f"{key}:invalid_format")
        # Time range checks.
        start = payload.get("start") if "start" in payload else payload.get("start_time")
        end = payload.get("end") if "end" in payload else payload.get("end_time")
        if start is not None and end is not None:
            try:
                if float(start) >= float(end):
                    issues.append("time_range:invalid_start_end")
            except Exception:
                s = str(start).strip()
                e = str(end).strip()
                if s and e and s >= e:
                    issues.append("time_range:invalid_start_end")
        # Parameter conflict checks.
        if payload.get("force_wait_user") and payload.get("force_fail"):
            issues.append("params_conflict:force_wait_user_vs_force_fail")
        if str(kind or "").strip().lower() == TASK_KIND_PLAN_GOAL:
            if not str(payload.get("goal") or "").strip():
                issues.append("goal:empty")
        return issues

    def record_tool_invocation(self, *, tool_name: str, ok: bool, latency_ms: float, error_signature: str) -> None:
        t = str(tool_name or "").strip().lower()
        if not t:
            return
        st = self._tool_health.setdefault(
            t,
            {"calls": 0, "ok": 0, "fail": 0, "lat_ms_sum": 0.0, "recent_ok": [], "recent_errors": {}, "cooldown": 0},
        )
        st["calls"] = int(st.get("calls", 0) or 0) + 1
        st["ok"] = int(st.get("ok", 0) or 0) + (1 if ok else 0)
        st["fail"] = int(st.get("fail", 0) or 0) + (0 if ok else 1)
        st["lat_ms_sum"] = float(st.get("lat_ms_sum", 0.0) or 0.0) + float(max(0.0, latency_ms))
        recent_ok = list(st.get("recent_ok") or [])
        recent_ok.append(1 if ok else 0)
        recent_ok = recent_ok[-int(self._tool_health_window):]
        st["recent_ok"] = recent_ok
        if (not ok) and error_signature:
            err_dist = dict(st.get("recent_errors") or {})
            err_dist[error_signature] = int(err_dist.get(error_signature, 0) or 0) + 1
            for k in list(err_dist.keys()):
                err_dist[k] = max(0, int(err_dist[k]) - 1)
                if err_dist[k] <= 0:
                    err_dist.pop(k, None)
            st["recent_errors"] = err_dist
        consecutive_fail = 0
        for v in reversed(recent_ok):
            if v == 1:
                break
            consecutive_fail += 1
        st["cooldown"] = 1 if consecutive_fail >= int(self._tool_cooldown_error_threshold) else 0
        self._tool_health[t] = st

    def get_tool_health(self, tool_name: str) -> Dict[str, Any]:
        t = str(tool_name or "").strip().lower()
        st = dict(self._tool_health.get(t) or {})
        calls = max(1, int(st.get("calls", 0) or 0))
        recent_ok = list(st.get("recent_ok") or [])
        recent_success = (sum(recent_ok) / float(len(recent_ok))) if recent_ok else (float(st.get("ok", 0) or 0) / float(calls))
        return {
            "success_rate_recent_n": round(float(recent_success), 4),
            "avg_latency_ms": round(float(st.get("lat_ms_sum", 0.0) or 0.0) / float(calls), 2),
            "error_distribution": dict(st.get("recent_errors") or {}),
            "cooldown": int(st.get("cooldown", 0) or 0),
            "window_n": int(self._tool_health_window),
            "calls": int(st.get("calls", 0) or 0),
        }

    def get_capability_snapshot(self) -> Dict[str, Any]:
        tools = self.list_tools()
        return {
            "tools": [{"tool_name": t, "schema": self.get_tool_schema(t), "health": self.get_tool_health(t)} for t in tools],
            "experts": dict(self._expert_stats),
        }

    def _compute_route_score(self, *, expert: str, kind: str, risk_level: str) -> Dict[str, float]:
        stats = self._stats_for(expert)
        calls = max(1, int(stats.get("calls", 0) or 0))
        ok = int(stats.get("ok", 0) or 0)
        fail = int(stats.get("fail", 0) or 0)
        success_rate = float(ok) / float(calls)
        avg_latency_ms = float(stats.get("lat_ms_sum", 0.0) or 0.0) / float(calls)
        avg_cost = float(stats.get("cost_sum", 0.0) or 0.0) / float(calls)
        recent = list(stats.get("recent_errors") or [])
        recent_error_rate = (float(sum(recent)) / float(len(recent))) if recent else (float(fail) / float(calls))
        capability_fit = self._capability_fit(kind, expert)
        tool_health = self.get_tool_health(kind)
        tool_success = float(tool_health.get("success_rate_recent_n", 1.0) or 1.0)
        cooldown = int(tool_health.get("cooldown", 0) or 0)
        latency_score = 1.0 / (1.0 + (avg_latency_ms / 1200.0))
        cost_score = 1.0 / (1.0 + max(0.0, avg_cost - 1.0))
        if str(risk_level or "").lower() in {"high", "critical"}:
            risk_match = 0.90 if expert == "planner" else 0.60
        else:
            risk_match = 1.00 if expert == "codex" else 0.85
        total = (
            0.30 * capability_fit
            + 0.24 * success_rate
            + 0.14 * latency_score
            + 0.10 * cost_score
            + 0.10 * (1.0 - recent_error_rate)
            + 0.08 * risk_match
            + 0.04 * tool_success
        )
        if cooldown:
            total *= 0.70
        return {
            "capability_fit": round(capability_fit, 4),
            "historical_success_rate": round(success_rate, 4),
            "avg_latency": round(avg_latency_ms, 4),
            "avg_cost": round(avg_cost, 4),
            "recent_error_rate": round(recent_error_rate, 4),
            "risk_match": round(risk_match, 4),
            "tool_success_rate": round(tool_success, 4),
            "tool_cooldown": float(cooldown),
            "total": round(total, 4),
        }

    def _routing_meta(self, task: Task) -> Dict[str, Any]:
        kind = str(task.kind or "").strip().lower()
        risk_level = self._risk_level(task)
        candidates = self._candidate_experts(kind)
        scored: List[Dict[str, Any]] = []
        for expert in candidates:
            details = self._compute_route_score(expert=expert, kind=kind, risk_level=risk_level)
            scored.append({"expert": expert, **details})
        scored.sort(key=lambda x: float(x.get("total") or 0.0), reverse=True)
        best = scored[0] if scored else {"expert": "planner"}
        selected = str(best.get("expert") or "planner")
        why = (
            f"selected={selected}; capability_fit={best.get('capability_fit')}; "
            f"success_rate={best.get('historical_success_rate')}; risk_match={best.get('risk_match')}"
        )
        rejected: Dict[str, str] = {}
        for item in scored[1:]:
            expert = str(item.get("expert") or "")
            rejected[expert] = (
                f"lower_total={item.get('total')}; capability_fit={item.get('capability_fit')}; "
                f"recent_error_rate={item.get('recent_error_rate')}"
            )
        return {
            "selected_expert": selected,
            "why_this_expert": why,
            "candidate_experts": [str(x.get("expert") or "") for x in scored],
            "routing_scores": scored,
            "rejected_reason": rejected,
            "risk_level": risk_level,
        }

    def execute(self, task: Task) -> WorkerResult:
        if callable(self.semantic_router):
            try:
                routed = self.semantic_router(task) or {}
                if bool(routed.get("wait_user")):
                    return WorkerResult(
                        ok=False,
                        output={"router": routed},
                        wait_user=True,
                        error=str(routed.get("question") or "Need user input"),
                    )
            except Exception as e:
                return WorkerResult(ok=False, error=f"semantic_router_error: {type(e).__name__}: {e}")

        kind = str(task.kind or "").strip().lower()
        payload = dict(task.input_payload or {})
        semantic_issues = self._semantic_validate_inputs(kind=kind, payload=payload)
        if semantic_issues:
            return WorkerResult(
                ok=False,
                error=f"semantic_validation_failed:{','.join(semantic_issues)}",
                output={"semantic_issues": list(semantic_issues)},
            )
        budget_used = int(payload.get("budget_steps_used") or 0)
        budget_max = int(payload.get("budget_steps_max") or 0)
        subgoal = self._clone_subgoal_for_gate(task)
        gate_issues = action_plan_gate_check(
            subgoal=subgoal,
            tools=self,
            budget_used=budget_used,
            budget_max=budget_max if budget_max > 0 else None,
            require_success_criteria=True,
        )
        if gate_issues:
            codes = [str(i.code) for i in gate_issues]
            return WorkerResult(
                ok=False,
                error=f"plan_gate_blocked:{','.join(codes)}",
                output={"plan_gate_issues": self._serialize_issues(gate_issues), "rejected_reason": codes},
            )
        route_meta = self._routing_meta(task)
        if kind == TASK_KIND_PLAN_GOAL:
            goal = str(payload.get("goal") or task.description or "").strip()
            plan_context = {
                "task_id": task.task_id,
                "task_input_payload": payload,
                "router_meta": route_meta,
            }
            selected = str(route_meta.get("selected_expert") or "planner")
            t0 = time.time()
            if selected == "codex":
                codex_result = self.code_adapter.execute(task)
                self._record_expert_result(
                    expert="codex",
                    ok=bool(codex_result.ok),
                    latency_ms=(time.time() - t0) * 1000.0,
                )
                out = dict(codex_result.output or {})
                out.setdefault("router", route_meta)
                return WorkerResult(
                    ok=bool(codex_result.ok),
                    output=out,
                    error=str(codex_result.error or ""),
                    wait_user=bool(codex_result.wait_user),
                    artifacts=list(codex_result.artifacts or []),
                )
            plan = self.planner_adapter.plan(goal=goal, context=plan_context)
            self._record_expert_result(
                expert="planner",
                ok=True,
                latency_ms=(time.time() - t0) * 1000.0,
            )
            ask_user = str(plan.get("ask_user") or "").strip()
            if ask_user:
                return WorkerResult(
                    ok=True,
                    output={
                        "generated_tasks": list(plan.get("tasks") or []),
                        "generated_subgoals": list(plan.get("generated_subgoals") or []),
                        "plan_compile_issues": [str(x) for x in list(plan.get("plan_compile_issues") or []) if str(x).strip()],
                        "plan_summary": str(plan.get("plan_summary") or ""),
                        "planner_questions": [ask_user],
                        "router": route_meta,
                    },
                )
            return WorkerResult(
                ok=True,
                output={
                    "generated_tasks": list(plan.get("tasks") or []),
                    "generated_subgoals": list(plan.get("generated_subgoals") or []),
                    "plan_compile_issues": [str(x) for x in list(plan.get("plan_compile_issues") or []) if str(x).strip()],
                    "plan_summary": str(plan.get("plan_summary") or ""),
                    "router": route_meta,
                },
            )
        if kind == TASK_KIND_CODE_TASK:
            selected = str(route_meta.get("selected_expert") or "codex")
            t0 = time.time()
            if selected == "planner":
                goal = str(payload.get("instruction") or task.description or "").strip() or str(task.description or "").strip()
                plan = self.planner_adapter.plan(goal=goal, context={"task_id": task.task_id, "router_meta": route_meta})
                self._record_expert_result(
                    expert="planner",
                    ok=True,
                    latency_ms=(time.time() - t0) * 1000.0,
                )
                return WorkerResult(
                    ok=True,
                    output={
                        "generated_tasks": list(plan.get("tasks") or []),
                        "plan_summary": str(plan.get("plan_summary") or ""),
                        "router": route_meta,
                    },
                    artifacts=[f"planner::{task.task_id}::routed"],
                )
            result = self.code_adapter.execute(task)
            self._record_expert_result(
                expert="codex",
                ok=bool(result.ok),
                latency_ms=(time.time() - t0) * 1000.0,
            )
            out = dict(result.output or {})
            out.setdefault("router", route_meta)
            return WorkerResult(
                ok=bool(result.ok),
                output=out,
                error=str(result.error or ""),
                wait_user=bool(result.wait_user),
                artifacts=list(result.artifacts or []),
            )
        if kind == TASK_KIND_ASK_USER:
            question = str(task.input_payload.get("question") or task.description or "Need user input").strip()
            return WorkerResult(ok=False, wait_user=True, error=question, output={"router": route_meta})
        return WorkerResult(ok=False, error=f"unsupported_task_kind:{kind or 'unknown'}")

    def has_tool(self, tool_name: str) -> bool:
        return str(tool_name or "").strip().lower() in {
            TASK_KIND_PLAN_GOAL,
            TASK_KIND_CODE_TASK,
            TASK_KIND_ASK_USER,
            "bootstrap",
        }

    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        t = str(tool_name or "").strip().lower()
        if t == TASK_KIND_PLAN_GOAL:
            return dict(self.planner_adapter.input_schema())
        if t == TASK_KIND_CODE_TASK:
            return dict(self.code_adapter.input_schema())
        if t == TASK_KIND_ASK_USER:
            return {"required": []}
        if t == "bootstrap":
            return {"required": []}
        return {"required": []}

    def list_tools(self) -> list[str]:
        return [TASK_KIND_PLAN_GOAL, TASK_KIND_CODE_TASK, TASK_KIND_ASK_USER, "bootstrap"]
