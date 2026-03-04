from __future__ import annotations

import hashlib

from .schemas import (
    TASK_KIND_CODE_TASK,
    TASK_KIND_PLAN_GOAL,
    AgentState,
    JudgeResult,
    StatePatch,
    Task,
    WorkerResult,
)


class SimpleJudge:
    def evaluate(self, state: AgentState, task: Task, result: WorkerResult) -> JudgeResult:
        patch = StatePatch(
            active_task_id=task.task_id,
            budget_steps_used_inc=1,
        )
        if result.wait_user:
            patch.state_status = "waiting_user"
            patch.waiting_question = result.error or "Need user input"
            patch.task_updates[task.task_id] = {"status": "waiting_user"}
            patch.last_error = result.error
            return JudgeResult(decision="waiting_user", reason="worker_requested_user", patch=patch)

        if result.ok:
            patch.task_updates[task.task_id] = {"status": "done"}
            patch.append_artifacts.extend(list(result.artifacts or []))
            all_done = True
            for t in state.tasks:
                if t.task_id == task.task_id:
                    continue
                if t.status != "done":
                    all_done = False
                    break
            if all_done:
                patch.state_status = "done"
                patch.goal_done = True
            else:
                patch.state_status = "running"
            return JudgeResult(decision="accepted", reason="worker_ok", patch=patch)

        next_retry = int(task.retries) + 1
        if next_retry <= 1:
            patch.state_status = "running"
            patch.task_updates[task.task_id] = {
                "status": "pending",
                "retries": next_retry,
            }
            patch.last_error = result.error
            return JudgeResult(decision="retry", reason="first_failure_retry", patch=patch)

        patch.state_status = "failed"
        patch.task_updates[task.task_id] = {
            "status": "failed",
            "retries": next_retry,
        }
        patch.last_error = result.error
        return JudgeResult(decision="failed", reason="retry_exhausted", patch=patch)


class V15Judge(SimpleJudge):
    def __init__(self, autonomous_mode: bool = True):
        self.autonomous_mode = bool(autonomous_mode)

    def _all_tasks_done(self, state: AgentState, current_task_id: str) -> bool:
        for t in state.tasks:
            if t.task_id == current_task_id:
                continue
            if str(t.status or "") != "done":
                return False
        return True

    def _same_error_repeat_count(self, state: AgentState, task_id: str, err: str) -> int:
        key = str(err or "").strip()
        if not key:
            return 0
        count = 0
        for evt in state.trace:
            if str((evt or {}).get("event") or "") != "worker_result":
                continue
            if str((evt or {}).get("task_id") or "") != str(task_id):
                continue
            if str((evt or {}).get("error") or "") == key:
                count += 1
        return count

    def _build_tasks_from_plan(self, state: AgentState, specs: list[dict]) -> list[Task]:
        out: list[Task] = []
        seq = int(state.next_task_seq or 1)
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            desc = str(spec.get("description") or "").strip()
            if not desc:
                continue
            t = Task(
                task_id=f"t{seq:04d}",
                kind=str(spec.get("kind") or TASK_KIND_CODE_TASK),
                description=desc,
                input_payload=dict(spec.get("input_payload") or {}),
                priority=int(spec.get("priority") or (20 + len(out))),
                status="pending",
                retries=0,
            )
            out.append(t)
            seq += 1
        return out

    def _build_replan_task(self, state: AgentState, reason: str, context_payload: dict) -> Task:
        seq = int(state.next_task_seq or 1)
        return Task(
            task_id=f"t{seq:04d}",
            kind=TASK_KIND_PLAN_GOAL,
            description=f"Replan based on codex feedback: {reason}",
            input_payload={
                "goal": state.goal,
                "supervisor_context": dict(context_payload or {}),
                "autonomous": True,
            },
            priority=12,
            status="pending",
            retries=0,
        )

    @staticmethod
    def _replan_signature(context_payload: dict) -> str:
        text = str(context_payload or "")
        return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

    def _replan_signature_seen_count(self, state: AgentState, sig: str) -> int:
        count = 0
        for evt in state.trace:
            if str((evt or {}).get("event") or "") != "replan_signature":
                continue
            if str((evt or {}).get("replan_signature") or "") == sig:
                count += 1
        return count

    def evaluate(self, state: AgentState, task: Task, result: WorkerResult) -> JudgeResult:
        patch = StatePatch(
            active_task_id=task.task_id,
            budget_steps_used_inc=1,
        )
        if result.wait_user:
            if self.autonomous_mode:
                context_payload = {
                    "source_task_id": task.task_id,
                    "source_kind": task.kind,
                    "worker_blocker": str(result.error or ""),
                }
                replan_task = self._build_replan_task(state, "worker_requested_user", context_payload)
                patch.task_updates[task.task_id] = {"status": "done"}
                patch.task_additions.append(replan_task)
                patch.next_task_seq_inc = 1
                patch.state_status = "running"
                patch.last_error = str(result.error or "")
                return JudgeResult(decision="replan", reason="autonomous_blocker_replan", patch=patch)
            patch.state_status = "waiting_user"
            patch.waiting_question = result.error or "Need user input"
            patch.task_updates[task.task_id] = {"status": "waiting_user"}
            patch.last_error = result.error
            return JudgeResult(decision="waiting_user", reason="worker_requested_user", patch=patch)

        kind = str(task.kind or "").strip().lower()
        if result.ok:
            if kind == TASK_KIND_PLAN_GOAL:
                generated = list(result.output.get("generated_tasks") or [])
                new_tasks = self._build_tasks_from_plan(state, generated)
                if not new_tasks:
                    result = WorkerResult(ok=False, error="planner_returned_no_tasks")
                else:
                    patch.task_updates[task.task_id] = {"status": "done"}
                    patch.task_additions.extend(new_tasks)
                    patch.next_task_seq_inc = len(new_tasks)
                    patch.state_status = "running"
                    patch.last_error = ""
                    return JudgeResult(decision="accepted_plan", reason="plan_generated_tasks", patch=patch)
            elif kind == TASK_KIND_CODE_TASK:
                has_effective = bool(result.artifacts) or bool((result.output or {}).get("changed_files"))
                if not has_effective:
                    result = WorkerResult(ok=False, error="code_task_no_effective_output")
                else:
                    output = dict(result.output or {})
                    improvements = list(output.get("improvement_items") or [])
                    questions = list(output.get("open_questions") or [])
                    needs_followup = bool(improvements or questions)
                    if needs_followup and self.autonomous_mode:
                        context_payload = {
                            "source_task_id": task.task_id,
                            "source_kind": kind,
                            "source_summary": str(output.get("summary") or ""),
                            "improvement_items": [str(x) for x in improvements if str(x).strip()],
                            "open_questions": [str(x) for x in questions if str(x).strip()],
                        }
                        sig = self._replan_signature(context_payload)
                        seen = self._replan_signature_seen_count(state, sig)
                        if seen >= 2:
                            patch.state_status = "failed"
                            patch.task_updates[task.task_id] = {"status": "failed"}
                            patch.last_error = "repeated_replan_signature"
                            return JudgeResult(
                                decision="failed",
                                reason="replan_signature_loop_guard",
                                patch=patch,
                            )
                        replan_task = self._build_replan_task(state, "codex_feedback", context_payload)
                        patch.task_updates[task.task_id] = {"status": "done"}
                        patch.append_artifacts.extend(list(result.artifacts or []))
                        patch.task_additions.append(replan_task)
                        patch.next_task_seq_inc = 1
                        patch.state_status = "running"
                        patch.last_error = ""
                        patch.append_trace.append({"event": "replan_signature", "replan_signature": sig})
                        return JudgeResult(decision="replan", reason="codex_feedback_to_glm", patch=patch)
                    patch.task_updates[task.task_id] = {"status": "done"}
                    patch.append_artifacts.extend(list(result.artifacts or []))
                    if self._all_tasks_done(state, task.task_id):
                        patch.state_status = "done"
                        patch.goal_done = True
                    else:
                        patch.state_status = "running"
                    patch.last_error = ""
                    return JudgeResult(decision="accepted", reason="code_task_effective", patch=patch)
            else:
                patch.task_updates[task.task_id] = {"status": "done"}
                if self._all_tasks_done(state, task.task_id):
                    patch.state_status = "done"
                    patch.goal_done = True
                else:
                    patch.state_status = "running"
                patch.last_error = ""
                return JudgeResult(decision="accepted", reason="worker_ok", patch=patch)

        next_retry = int(task.retries) + 1
        max_retries = int((task.input_payload or {}).get("max_retries", 1) or 1)
        same_err_count = self._same_error_repeat_count(state, task.task_id, result.error)
        should_retry = (next_retry <= max_retries) and (same_err_count < 2)
        if should_retry:
            patch.state_status = "running"
            patch.task_updates[task.task_id] = {"status": "pending", "retries": next_retry}
            patch.last_error = result.error
            return JudgeResult(decision="retry", reason="retry_with_guard", patch=patch)

        patch.state_status = "failed"
        patch.task_updates[task.task_id] = {"status": "failed", "retries": next_retry}
        patch.last_error = result.error
        return JudgeResult(decision="failed", reason="retry_exhausted_or_repeated_error", patch=patch)
