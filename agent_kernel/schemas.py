from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


TaskStatus = str
KernelStatus = str
TASK_KIND_PLAN_GOAL = "plan_goal"
TASK_KIND_CODE_TASK = "code_task"
TASK_KIND_ASK_USER = "ask_user"


class SubgoalState(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    BLOCKED = "BLOCKED"
    FAILED_FATAL = "FAILED_FATAL"
    SKIPPED = "SKIPPED"


class FailureCategory(str, Enum):
    MISSING_INPUT = "missing_input"
    TRANSIENT_TOOL_ERROR = "transient_tool_error"
    AUTH_ERROR = "auth_error"
    PERMISSION_DENIED = "permission_denied"
    ENVIRONMENT_MISSING = "environment_missing"
    GOAL_NOT_EXECUTABLE = "goal_not_executable"
    CAPABILITY_GAP = "capability_gap"
    LOGIC_CONFLICT = "logic_conflict"
    REPEATED_SAME_ERROR = "repeated_same_error"
    UNKNOWN = "unknown"


class RouteAction(str, Enum):
    ASK_USER = "ask_user"
    RETRY = "retry"
    REPAIR_AUTH = "repair_auth"
    LOCAL_REPLAN_WITH_CONSTRAINTS = "local_replan_with_constraints"
    LOCAL_REPLAN = "local_replan"
    CIRCUIT_BREAK = "circuit_break"


@dataclass
class RetryPolicy:
    max_attempts: int = 2
    backoff: str = "exponential"
    base_delay_ms: int = 300


@dataclass
class FailureMode:
    code: str
    description: str = ""


@dataclass
class Predicate:
    op: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SuccessCriterion:
    op: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutableSubgoal:
    id: str
    intent: str
    executor_type: str
    tool_name: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    preconditions: List[Predicate] = field(default_factory=list)
    success_criteria: List[SuccessCriterion] = field(default_factory=list)
    failure_modes: List[FailureMode] = field(default_factory=list)
    fallback: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Optional[RetryPolicy] = None
    state: SubgoalState = SubgoalState.DRAFT
    attempt_count: int = 0
    last_error: str = ""

    @staticmethod
    def from_task(task: "Task") -> "ExecutableSubgoal":
        payload = dict(task.input_payload or {})
        dep_raw = payload.get("dependencies")
        dependencies: List[str] = []
        if isinstance(dep_raw, list):
            dependencies = [str(x) for x in dep_raw if str(x).strip()]
        preconditions = _parse_predicates(payload.get("preconditions"))
        success = _parse_success_criteria(payload.get("success_criteria"))
        retry_policy = _parse_retry_policy(payload.get("retry_policy"), retries=int(task.retries or 0))
        state = _task_status_to_subgoal_state(str(task.status or ""))
        return ExecutableSubgoal(
            id=str(task.task_id),
            intent=str(task.description or "").strip(),
            executor_type=str(task.kind or ""),
            tool_name=str(task.kind or ""),
            inputs=payload,
            dependencies=dependencies,
            preconditions=preconditions,
            success_criteria=success,
            failure_modes=[],
            fallback=_parse_fallback(payload.get("fallback")),
            retry_policy=retry_policy,
            state=state,
            attempt_count=int(task.retries or 0),
            last_error="",
        )

    def to_task(self, *, priority: int = 100) -> "Task":
        payload = dict(self.inputs or {})
        if self.dependencies:
            payload["dependencies"] = list(self.dependencies)
        if self.preconditions:
            payload["preconditions"] = [{"op": p.op, "args": dict(p.args or {})} for p in self.preconditions]
        if self.success_criteria:
            payload["success_criteria"] = [{"op": c.op, "args": dict(c.args or {})} for c in self.success_criteria]
        if self.fallback:
            payload["fallback"] = dict(self.fallback)
        if self.retry_policy:
            payload["retry_policy"] = asdict(self.retry_policy)
        return Task(
            task_id=str(self.id),
            kind=str(self.executor_type or self.tool_name),
            description=str(self.intent or ""),
            input_payload=payload,
            priority=int(priority),
            status=_subgoal_state_to_task_status(self.state),
            retries=int(self.attempt_count),
        )


@dataclass
class Task:
    task_id: str
    kind: str
    description: str
    input_payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    status: TaskStatus = "pending"
    retries: int = 0


@dataclass
class WorkerResult:
    ok: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    wait_user: bool = False
    artifacts: List[str] = field(default_factory=list)


@dataclass
class JudgeResult:
    decision: str
    reason: str = ""
    patch: Optional["StatePatch"] = None


@dataclass
class StatePatch:
    state_status: Optional[KernelStatus] = None
    goal_done: Optional[bool] = None
    waiting_question: Optional[str] = None
    last_error: Optional[str] = None
    active_task_id: Optional[str] = None
    budget_steps_used_inc: int = 0
    task_updates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    task_additions: List["Task"] = field(default_factory=list)
    next_task_seq_inc: int = 0
    append_trace: List[Dict[str, Any]] = field(default_factory=list)
    append_artifacts: List[str] = field(default_factory=list)


@dataclass
class AgentState:
    goal: str
    tasks: List[Task] = field(default_factory=list)
    status: KernelStatus = "running"
    trace: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    budget_steps_used: int = 0
    budget_steps_max: int = 20
    active_task_id: str = ""
    goal_done: bool = False
    waiting_question: str = ""
    last_error: str = ""
    next_task_seq: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: Dict[str, Any]) -> "AgentState":
        tasks_raw = list(payload.get("tasks") or [])
        tasks = [Task(**dict(t)) for t in tasks_raw]
        return AgentState(
            goal=str(payload.get("goal") or ""),
            tasks=tasks,
            status=str(payload.get("status") or "running"),
            trace=list(payload.get("trace") or []),
            artifacts=list(payload.get("artifacts") or []),
            budget_steps_used=int(payload.get("budget_steps_used") or 0),
            budget_steps_max=int(payload.get("budget_steps_max") or 20),
            active_task_id=str(payload.get("active_task_id") or ""),
            goal_done=bool(payload.get("goal_done") or False),
            waiting_question=str(payload.get("waiting_question") or ""),
            last_error=str(payload.get("last_error") or ""),
            next_task_seq=int(payload.get("next_task_seq") or 1),
        )


def _parse_predicates(value: Any) -> List[Predicate]:
    out: List[Predicate] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict):
            op = str(item.get("op") or "").strip()
            if not op:
                continue
            out.append(Predicate(op=op, args=dict(item.get("args") or {})))
    return out


def _parse_success_criteria(value: Any) -> List[SuccessCriterion]:
    out: List[SuccessCriterion] = []
    if not isinstance(value, list):
        return out
    for item in value:
        if isinstance(item, dict):
            op = str(item.get("op") or "").strip()
            if not op:
                continue
            out.append(SuccessCriterion(op=op, args=dict(item.get("args") or {})))
    return out


def _parse_fallback(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        return {"on_failure": value.strip()}
    return {}


def _parse_retry_policy(value: Any, *, retries: int) -> RetryPolicy:
    if isinstance(value, dict):
        return RetryPolicy(
            max_attempts=max(1, int(value.get("max_attempts") or 2)),
            backoff=str(value.get("backoff") or "exponential"),
            base_delay_ms=max(1, int(value.get("base_delay_ms") or 300)),
        )
    # Backward compatible default policy.
    return RetryPolicy(max_attempts=max(2, retries + 1), backoff="exponential", base_delay_ms=300)


def _task_status_to_subgoal_state(status: str) -> SubgoalState:
    s = str(status or "").strip().lower()
    if s in {"ready"}:
        return SubgoalState.READY
    if s in {"running"}:
        return SubgoalState.RUNNING
    if s in {"done"}:
        return SubgoalState.DONE
    if s in {"failed_retryable"}:
        return SubgoalState.FAILED_RETRYABLE
    if s in {"blocked", "waiting_user"}:
        return SubgoalState.BLOCKED
    if s in {"failed", "failed_fatal"}:
        return SubgoalState.FAILED_FATAL
    if s in {"skipped"}:
        return SubgoalState.SKIPPED
    if s in {"pending", "draft", ""}:
        return SubgoalState.DRAFT
    return SubgoalState.DRAFT


def _subgoal_state_to_task_status(state: SubgoalState) -> str:
    if state == SubgoalState.DRAFT:
        return "draft"
    if state == SubgoalState.READY:
        return "ready"
    if state == SubgoalState.RUNNING:
        return "running"
    if state == SubgoalState.DONE:
        return "done"
    if state == SubgoalState.FAILED_RETRYABLE:
        return "failed_retryable"
    if state == SubgoalState.BLOCKED:
        return "blocked"
    if state == SubgoalState.FAILED_FATAL:
        return "failed"
    if state == SubgoalState.SKIPPED:
        return "skipped"
    return "draft"
