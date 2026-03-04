from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from .circuit_breaker import CircuitBreaker
from .compile_check import CompileIssue, plan_compile_check
from .failure_router import classify_failure
from .judge import SimpleJudge
from .local_replan import action_fingerprint, apply_local_replan, compute_descendants
from .persistence import save_state_json
from .planner import SimplePlanner
from .schemas import (
    TASK_KIND_CODE_TASK,
    TASK_KIND_PLAN_GOAL,
    AgentState,
    FailureCategory,
    ExecutableSubgoal,
    Predicate,
    RouteAction,
    RetryPolicy,
    SuccessCriterion,
    SubgoalState,
    Task,
)
from .trace import make_trace_event
from .worker import SimpleWorker


class AgentKernel:
    def __init__(
        self,
        planner: Optional[SimplePlanner] = None,
        worker: Optional[SimpleWorker] = None,
        judge: Optional[SimpleJudge] = None,
    ):
        self.planner = planner or SimplePlanner()
        self.worker = worker or SimpleWorker()
        # Kept for backward compatibility, but scheduling now uses FSM path directly.
        self.judge = judge or SimpleJudge()
        self.circuit_breaker = CircuitBreaker(
            same_error_limit=2,
            same_action_replan_limit=3,
            stagnation_cycle_limit=10,
            stagnation_seconds=120,
        )

    def _save(self, state: AgentState, checkpoint_path: Optional[str]) -> None:
        if checkpoint_path:
            save_state_json(state, checkpoint_path)

    @staticmethod
    def _task_to_subgoal(task: Task) -> ExecutableSubgoal:
        return ExecutableSubgoal.from_task(task)

    @staticmethod
    def _sync_task_from_subgoal(task: Task, subgoal: ExecutableSubgoal) -> None:
        task.status = subgoal.to_task(priority=task.priority).status
        task.retries = int(subgoal.attempt_count)
        payload = dict(task.input_payload or {})
        if subgoal.retry_policy is not None:
            payload["retry_policy"] = {
                "max_attempts": int(subgoal.retry_policy.max_attempts),
                "backoff": str(subgoal.retry_policy.backoff),
                "base_delay_ms": int(subgoal.retry_policy.base_delay_ms),
            }
        task.input_payload = payload

    def _compile_issues_for(self, state: AgentState) -> Dict[str, List[CompileIssue]]:
        subgoals = [self._task_to_subgoal(t) for t in state.tasks]
        issues = plan_compile_check(subgoals=subgoals, tools=self.worker)
        grouped: Dict[str, List[CompileIssue]] = {}
        for issue in issues:
            grouped.setdefault(str(issue.subgoal_id), []).append(issue)
        return grouped

    @staticmethod
    def _hash_payload(payload: Dict[str, Any]) -> str:
        try:
            txt = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        except Exception:
            txt = str(payload or "")
        return hashlib.sha1(txt.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _input_summary(payload: Dict[str, Any], max_len: int = 220) -> str:
        if not isinstance(payload, dict):
            return ""
        keys = sorted([str(k) for k in payload.keys()])[:12]
        summary = f"keys={keys}"
        if "instruction" in payload:
            summary += f"; instruction={str(payload.get('instruction') or '')[:80]}"
        if "goal" in payload:
            summary += f"; goal={str(payload.get('goal') or '')[:80]}"
        return summary[:max_len]

    @staticmethod
    def _error_signature(error: str) -> str:
        txt = str(error or "").strip().lower()
        if not txt:
            return ""
        if ":" in txt:
            return txt.split(":", 1)[0]
        return "execution_error"

    def _output_schema_valid(self, task: Task, result: Any) -> bool:
        if result is None:
            return False
        if not isinstance(getattr(result, "output", {}), dict):
            return False
        kind = str(task.kind or "").strip().lower()
        output = dict(getattr(result, "output", {}) or {})
        if kind == TASK_KIND_PLAN_GOAL and bool(getattr(result, "ok", False)):
            has_plan = bool(output.get("generated_subgoals") or output.get("generated_tasks"))
            return has_plan
        if kind == TASK_KIND_CODE_TASK:
            if not bool(getattr(result, "ok", False)):
                return True
            return isinstance(output.get("summary"), str)
        if kind == "ask_user":
            return True
        return True


    @staticmethod
    def _ask_user_message_for_failure(category: FailureCategory) -> str:
        if category == FailureCategory.PERMISSION_DENIED:
            return "Permission denied. Please grant required workspace/tool permissions and retry."
        if category == FailureCategory.ENVIRONMENT_MISSING:
            return "Environment incomplete. Please install missing dependencies/files or provide runtime context."
        if category == FailureCategory.GOAL_NOT_EXECUTABLE:
            return "Goal is not executable yet. Please provide concrete acceptance criteria and boundaries."
        return "Please provide missing input required by current subgoal."

    @staticmethod
    def _all_dependencies_done(task: Task, state: AgentState) -> bool:
        deps = list((task.input_payload or {}).get("dependencies") or [])
        dep_ids = [str(x) for x in deps if str(x).strip()]
        if not dep_ids:
            return True
        status_by_id = {str(t.task_id): str(t.status or "") for t in state.tasks}
        for dep in dep_ids:
            if status_by_id.get(dep) not in {"done", "skipped"}:
                return False
        return True

    def _pick_runnable_task(self, state: AgentState) -> Optional[Task]:
        candidates: List[Task] = []
        for t in state.tasks:
            s = str(t.status or "").lower()
            if s in {"done", "skipped", "failed", "blocked", "running"}:
                continue
            if not self._all_dependencies_done(t, state):
                continue
            candidates.append(t)
        if not candidates:
            return None
        candidates.sort(key=lambda x: (int(x.priority), str(x.task_id)))
        return candidates[0]

    @staticmethod
    def _evaluate_success(task: Task, output: Dict[str, object], artifacts: List[str]) -> bool:
        criteria = list((task.input_payload or {}).get("success_criteria") or [])
        if not criteria:
            return True
        for c in criteria:
            if not isinstance(c, dict):
                return False
            op = str(c.get("op") or "").strip()
            args = dict(c.get("args") or {})
            if op == "tool_output_contains":
                needle = str(args.get("text") or "").strip().lower()
                hay = str(output.get("summary") or output).lower()
                if needle and needle not in hay:
                    return False
                continue
            if op == "artifact_exists":
                needle = str(args.get("path") or "").strip()
                if needle and needle not in artifacts:
                    return False
                continue
            if op == "field_equals":
                key = str(args.get("field") or "").strip()
                expected = args.get("value")
                if key and output.get(key) != expected:
                    return False
                continue
            if op == "exit_code_is":
                expected = int(args.get("code") or 0)
                got = int(output.get("exit_code", 0) or 0)
                if got != expected:
                    return False
                continue
            if op == "predicate_ref":
                # Placeholder extensibility point.
                continue
            return False
        return True

    def _append_generated_tasks(self, state: AgentState, plan_task: Task, generated: List[Dict[str, object]]) -> int:
        seq = int(state.next_task_seq or 1)
        added = 0
        for spec in generated:
            if not isinstance(spec, dict):
                continue
            desc = str(spec.get("description") or "").strip()
            if not desc:
                continue
            state.tasks.append(
                Task(
                    task_id=f"t{seq:04d}",
                    kind=str(spec.get("kind") or TASK_KIND_CODE_TASK),
                    description=desc,
                    input_payload=dict(spec.get("input_payload") or {}),
                    priority=int(spec.get("priority") or (20 + added)),
                    status="draft",
                    retries=0,
                )
            )
            seq += 1
            added += 1
        if added > 0:
            state.next_task_seq = seq
        return added

    @staticmethod
    def _subgoal_from_compiled_dict(spec: Dict[str, Any], task_id: str) -> ExecutableSubgoal:
        preconditions = []
        for p in list(spec.get("preconditions") or []):
            if isinstance(p, dict) and str(p.get("op") or "").strip():
                preconditions.append(Predicate(op=str(p.get("op") or "").strip(), args=dict(p.get("args") or {})))
        success_criteria = []
        for c in list(spec.get("success_criteria") or []):
            if isinstance(c, dict) and str(c.get("op") or "").strip():
                success_criteria.append(SuccessCriterion(op=str(c.get("op") or "").strip(), args=dict(c.get("args") or {})))
        rp_raw = dict(spec.get("retry_policy") or {})
        retry_policy = RetryPolicy(
            max_attempts=max(1, int(rp_raw.get("max_attempts") or 2)),
            backoff=str(rp_raw.get("backoff") or "exponential"),
            base_delay_ms=max(1, int(rp_raw.get("base_delay_ms") or 300)),
        )
        return ExecutableSubgoal(
            id=str(task_id),
            intent=str(spec.get("intent") or "").strip(),
            executor_type=str(spec.get("executor_type") or spec.get("tool_name") or ""),
            tool_name=str(spec.get("tool_name") or spec.get("executor_type") or ""),
            inputs=dict(spec.get("inputs") or {}),
            dependencies=[str(x) for x in (spec.get("dependencies") or []) if str(x).strip()],
            preconditions=preconditions,
            success_criteria=success_criteria,
            fallback=dict(spec.get("fallback") or {}),
            retry_policy=retry_policy,
            state=SubgoalState.DRAFT,
        )

    def _append_generated_subgoals(self, state: AgentState, generated: List[Dict[str, Any]]) -> Tuple[int, List[CompileIssue]]:
        if not generated:
            return 0, []
        seq = int(state.next_task_seq or 1)
        used_ids = {str(t.task_id) for t in state.tasks}
        id_map: Dict[str, str] = {}
        compiled_subgoals: List[ExecutableSubgoal] = []
        for idx, spec in enumerate(generated):
            if not isinstance(spec, dict):
                continue
            raw_id = str(spec.get("subgoal_id") or spec.get("id") or "").strip() or f"sg_{idx + 1:02d}"
            mapped = raw_id
            if mapped in used_ids or mapped in id_map.values():
                mapped = f"t{seq:04d}"
                seq += 1
            id_map[raw_id] = mapped
            id_map[mapped] = mapped
            compiled_subgoals.append(self._subgoal_from_compiled_dict(spec, mapped))
            used_ids.add(mapped)
        for sg in compiled_subgoals:
            remapped = []
            for dep in list(sg.dependencies or []):
                remapped.append(id_map.get(dep, dep))
            sg.dependencies = [d for d in remapped if d in used_ids]

        compile_issues = plan_compile_check(subgoals=compiled_subgoals, tools=self.worker)
        hard = [x for x in compile_issues if str(x.severity or "error") == "error"]
        if hard:
            return 0, hard

        added = 0
        for sg in compiled_subgoals:
            task = sg.to_task(priority=(20 + added))
            state.tasks.append(task)
            added += 1
        if added > 0:
            state.next_task_seq = max(int(state.next_task_seq or 1), seq)
        return added, []

    def _handle_local_replan(self, state: AgentState, failed_task: Task, *, constrained: bool) -> bool:
        current = [ExecutableSubgoal.from_task(t) for t in state.tasks]
        seq = int(state.next_task_seq or 1)
        can_delegate_replan = bool(getattr(self.worker, "planner_adapter", None))
        repl_intent = f"Replan failed node {failed_task.task_id}"
        if constrained:
            repl_intent += " with stricter constraints"
        affected_ids = sorted(list(compute_descendants(current, failed_task.task_id)))
        template = "local_repair_replan" if constrained else "suffix_replan"
        if can_delegate_replan:
            replacement = ExecutableSubgoal(
                id=f"t{seq:04d}",
                intent=repl_intent,
                executor_type=TASK_KIND_PLAN_GOAL,
                tool_name=TASK_KIND_PLAN_GOAL,
                inputs={
                    "goal": state.goal,
                    "supervisor_context": {
                        "source_task_id": failed_task.task_id,
                        "source_kind": failed_task.kind,
                        "source_error": state.last_error,
                        "replan_template": template,
                        "affected_node_ids": affected_ids,
                        "constraints": ["use_minimal_change"] if constrained else [],
                    },
                },
                dependencies=[],
                retry_policy=ExecutableSubgoal.from_task(failed_task).retry_policy,
                state=SubgoalState.DRAFT,
            )
        else:
            fallback_inputs = dict(failed_task.input_payload or {})
            fallback_inputs.pop("force_fail", None)
            fallback_inputs.setdefault("instruction", "fallback_retry")
            replacement = ExecutableSubgoal(
                id=f"t{seq:04d}",
                intent=f"Fallback execution for {failed_task.task_id}",
                executor_type=str(failed_task.kind or TASK_KIND_CODE_TASK),
                tool_name=str(failed_task.kind or TASK_KIND_CODE_TASK),
                inputs=fallback_inputs,
                dependencies=[],
                retry_policy=ExecutableSubgoal.from_task(failed_task).retry_policy,
                state=SubgoalState.DRAFT,
            )
        merged = apply_local_replan(current=current, failed_id=failed_task.task_id, replacements=[replacement])
        fp = action_fingerprint(replacement)
        sup = dict((failed_task.input_payload or {}).get("supervisor_context") or {})
        path_key = str(sup.get("source_task_id") or failed_task.task_id)
        cb_evt = self.circuit_breaker.on_replan_action(path_key=path_key, action_fingerprint=fp)
        state.trace.append(
            make_trace_event(
                "local_replan",
                task_id=failed_task.task_id,
                replacement_id=replacement.id,
                constrained=int(constrained),
                replan_template=template,
                affected_node_ids=affected_ids,
                action_fingerprint=fp,
            )
        )
        if cb_evt.triggered:
            failed_task.status = "failed"
            state.status = "failed"
            state.last_error = cb_evt.reason
            state.trace.append(make_trace_event("circuit_break", reason=cb_evt.reason, details=cb_evt.details))
            return False

        # Materialize merged subgoals back to legacy task list.
        old_by_id = {str(t.task_id): t for t in state.tasks}
        new_tasks: List[Task] = []
        for sg in merged:
            if sg.id in old_by_id:
                t = old_by_id[sg.id]
                self._sync_task_from_subgoal(t, sg)
                new_tasks.append(t)
            else:
                new_tasks.append(sg.to_task(priority=30))
        state.tasks = new_tasks
        state.next_task_seq = max(int(state.next_task_seq or 1), seq + 1)
        return True

    def run_step(self, state: AgentState, checkpoint_path: Optional[str] = None) -> AgentState:
        state.trace.append(make_trace_event("planning_started", goal=str(state.goal or "")))
        self.planner.bootstrap(state)
        state.trace.append(make_trace_event("planning_completed", task_count=len(list(state.tasks or []))))
        self._save(state, checkpoint_path)

        if state.status in {"done", "failed", "waiting_user"}:
            return state
        if int(state.budget_steps_used) >= int(state.budget_steps_max):
            state.status = "failed"
            state.last_error = "budget_exhausted"
            state.trace.append(make_trace_event("budget_exhausted", used=state.budget_steps_used))
            self._save(state, checkpoint_path)
            return state

        compile_issues = self._compile_issues_for(state)
        for task in state.tasks:
            issues = compile_issues.get(str(task.task_id), [])
            if not issues:
                if str(task.status or "").lower() in {"draft", "pending"}:
                    task.status = "ready"
                continue
            hard_errors = [x for x in issues if str(x.severity) == "error"]
            if hard_errors and str(task.status or "").lower() not in {"done", "skipped", "failed"}:
                task.status = "blocked"
                state.trace.append(
                    make_trace_event(
                        "compile_blocked",
                        task_id=task.task_id,
                        codes=[x.code for x in hard_errors],
                    )
                )

        task = self._pick_runnable_task(state)
        if task is None:
            terminal = [str(t.status or "").lower() for t in state.tasks]
            if terminal and all(s in {"done", "skipped"} for s in terminal):
                state.status = "done"
                state.goal_done = True
                state.trace.append(make_trace_event("all_tasks_done"))
            elif any(s in {"failed", "failed_fatal"} for s in terminal):
                state.status = "failed"
            elif any(s == "blocked" for s in terminal):
                state.status = "waiting_user"
                state.waiting_question = state.waiting_question or "Need missing input to continue."
            else:
                state.status = "failed"
            self._save(state, checkpoint_path)
            return state

        state.active_task_id = task.task_id
        task.status = "running"
        task_payload = dict(task.input_payload or {})
        task_payload.setdefault("budget_steps_used", int(state.budget_steps_used or 0))
        task_payload.setdefault("budget_steps_max", int(state.budget_steps_max or 0))
        task.input_payload = task_payload
        state.trace.append(make_trace_event("task_selected", task_id=task.task_id, kind=task.kind))

        inv_start = time.time()
        state.trace.append(make_trace_event("worker_execution_started", task_id=task.task_id, kind=task.kind))
        result = self.worker.execute(task)
        inv_end = time.time()
        tool_name = str(task.kind or "").strip().lower()
        tool_schema = {}
        if callable(getattr(self.worker, "get_tool_schema", None)):
            try:
                tool_schema = dict(self.worker.get_tool_schema(tool_name) or {})
            except Exception:
                tool_schema = {}
        schema_version = str(tool_schema.get("schema_version") or "")
        if not schema_version:
            schema_version = hashlib.sha1(
                json.dumps(tool_schema or {}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8", errors="ignore")
            ).hexdigest()[:10]
        output_schema_valid = self._output_schema_valid(task, result)
        err_sig = self._error_signature(str(result.error or ""))
        record = {
            "tool_name": tool_name,
            "schema_version": schema_version,
            "input_hash": self._hash_payload(task_payload),
            "input_summary": self._input_summary(task_payload),
            "start_time": float(inv_start),
            "end_time": float(inv_end),
            "duration_ms": int(max(0.0, (inv_end - inv_start)) * 1000.0),
            "output_schema_valid": int(bool(output_schema_valid)),
            "error_signature": err_sig,
            "retry_count": int(task.retries or 0),
            "called_by_subgoal_id": str(task.task_id),
        }
        state.trace.append(make_trace_event("tool_invocation_record", **record))
        if callable(getattr(self.worker, "record_tool_invocation", None)):
            try:
                self.worker.record_tool_invocation(
                    tool_name=tool_name,
                    ok=bool(result.ok) and bool(output_schema_valid),
                    latency_ms=float(record.get("duration_ms") or 0),
                    error_signature=err_sig,
                )
            except Exception:
                pass

        state.budget_steps_used += 1
        router_meta = dict((result.output or {}).get("router") or {})
        state.trace.append(
            make_trace_event(
                "worker_result",
                task_id=task.task_id,
                ok=int(bool(result.ok)),
                wait_user=int(bool(result.wait_user)),
                error=str(result.error),
                selected_expert=str(router_meta.get("selected_expert") or ""),
                why_this_expert=str(router_meta.get("why_this_expert") or ""),
                candidate_experts=list(router_meta.get("candidate_experts") or []),
                routing_scores=list(router_meta.get("routing_scores") or []),
                rejected_reason=dict(router_meta.get("rejected_reason") or {}),
            )
        )

        if str(task.kind or "").strip().lower() == TASK_KIND_PLAN_GOAL and result.ok:
            planner_compile_issues = [str(x) for x in list((result.output or {}).get("plan_compile_issues") or []) if str(x).strip()]
            if planner_compile_issues:
                result.ok = False
                result.error = "planner_compile_failed"
                state.trace.append(
                    make_trace_event(
                        "planner_compile_failed",
                        task_id=task.task_id,
                        issues=planner_compile_issues[:20],
                    )
                )
            generated_subgoals = list((result.output or {}).get("generated_subgoals") or [])
            compile_issues: List[CompileIssue] = []
            added = 0
            if result.ok and generated_subgoals:
                added, compile_issues = self._append_generated_subgoals(state, generated_subgoals)
                if compile_issues:
                    result.ok = False
                    result.error = "planner_compile_failed"
                    state.trace.append(
                        make_trace_event(
                            "planner_compile_failed",
                            task_id=task.task_id,
                            issues=[f"{i.subgoal_id}:{i.code}" for i in compile_issues][:20],
                        )
                    )
            if result.ok and added <= 0:
                generated = list((result.output or {}).get("generated_tasks") or [])
                added = self._append_generated_tasks(state, task, generated)
            if result.ok and added <= 0:
                result.ok = False
                result.error = "planner_returned_no_tasks"
            if result.ok:
                task.status = "done"
                if result.artifacts:
                    state.artifacts.extend([str(x) for x in result.artifacts if str(x).strip()])
                self.circuit_breaker.mark_done_progress(cycle=state.budget_steps_used, ts=time.time())
                state.status = "running"
                self._save(state, checkpoint_path)
                return state

        passed = bool(result.ok) and self._evaluate_success(task, dict(result.output or {}), list(result.artifacts or []))
        if passed:
            task.status = "done"
            if result.artifacts:
                state.artifacts.extend([str(x) for x in result.artifacts if str(x).strip()])
            self.circuit_breaker.mark_done_progress(cycle=state.budget_steps_used, ts=time.time())
            if all(str(t.status or "").lower() in {"done", "skipped"} for t in state.tasks):
                state.status = "done"
                state.goal_done = True
            else:
                state.status = "running"
            state.last_error = ""
            self._save(state, checkpoint_path)
            return state

        if (
            str(task.kind or "").strip().lower() == TASK_KIND_PLAN_GOAL
            and str(result.error or "").strip().lower() == "planner_compile_failed"
        ):
            task.status = "failed_retryable"
            state.last_error = "planner_compile_failed"
            state.trace.append(make_trace_event("planner_compile_failed_route", task_id=task.task_id, action="local_replan"))
            ok = self._handle_local_replan(state, task, constrained=True)
            if ok and state.status != "failed":
                state.status = "running"
            self._save(state, checkpoint_path)
            return state

        prior_fingerprints = [
            str(x.get("fingerprint") or "")
            for x in state.trace
            if str((x or {}).get("event") or "") == "failure_routed"
        ]
        decision = classify_failure(
            subgoal_id=str(task.task_id),
            tool_name=str(task.kind),
            error_message=str(result.error or "evaluation_failed"),
            compile_issues=compile_issues.get(str(task.task_id), []),
            prior_fingerprints=prior_fingerprints,
        )
        state.last_error = str(result.error or "execution_failed")
        state.trace.append(
            make_trace_event(
                "failure_routed",
                task_id=task.task_id,
                category=decision.category.value,
                action=decision.action.value,
                reason=decision.reason,
                fingerprint=decision.fingerprint,
            )
        )
        cb_evt = self.circuit_breaker.on_error(subgoal_id=task.task_id, fingerprint=decision.fingerprint)
        if cb_evt.triggered:
            task.status = "failed"
            state.status = "failed"
            state.trace.append(make_trace_event("circuit_break", reason=cb_evt.reason, details=cb_evt.details))
            self._save(state, checkpoint_path)
            return state

        # Transition based on failure router action.
        if decision.action == RouteAction.RETRY:
            policy = ExecutableSubgoal.from_task(task).retry_policy
            next_attempt = int(task.retries) + 1
            if policy and next_attempt < int(policy.max_attempts):
                task.retries = next_attempt
                task.status = "failed_retryable"
                # Immediately make it runnable on next loop.
                task.status = "ready"
                state.status = "running"
            else:
                task.status = "failed"
                state.status = "failed"
        elif decision.action == RouteAction.ASK_USER:
            task.status = "blocked"
            state.status = "waiting_user"
            state.waiting_question = self._ask_user_message_for_failure(decision.category)
        elif decision.action == RouteAction.REPAIR_AUTH:
            task.status = "blocked"
            state.status = "waiting_user"
            state.waiting_question = "Authentication required. Please provide/repair credentials."
        elif decision.action in {RouteAction.LOCAL_REPLAN, RouteAction.LOCAL_REPLAN_WITH_CONSTRAINTS}:
            task.status = "failed_retryable"
            ok = self._handle_local_replan(
                state,
                task,
                constrained=(decision.action == RouteAction.LOCAL_REPLAN_WITH_CONSTRAINTS),
            )
            if ok and state.status != "failed":
                state.status = "running"
        else:
            task.status = "failed"
            state.status = "failed"

        stagnant = self.circuit_breaker.check_stagnation(cycle=state.budget_steps_used, now_ts=time.time())
        if stagnant.triggered and state.status not in {"done", "failed"}:
            task.status = "failed"
            state.status = "failed"
            state.trace.append(make_trace_event("circuit_break", reason=stagnant.reason, details=stagnant.details))

        self._save(state, checkpoint_path)
        return state

    def run(self, state: AgentState, checkpoint_path: str) -> AgentState:
        while True:
            prev_used = int(state.budget_steps_used or 0)
            self.run_step(state=state, checkpoint_path=checkpoint_path)
            if state.status in {"done", "failed", "waiting_user"}:
                break
            if int(state.budget_steps_used or 0) <= prev_used:
                break
        return state
