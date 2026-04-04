from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


@dataclass
class Goal:
    objective: str
    id: str = field(default_factory=lambda: _new_id("goal"))
    constraints: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


@dataclass
class Task:
    goal_id: str
    title: str
    description: str
    tool_name: str
    acceptance_criteria: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: _new_id("task"))
    status: str = "pending"  # pending|running|done|failed|blocked
    attempt_count: int = 0
    max_attempts: int = 2
    input_payload: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    success_criteria: List[Dict[str, Any]] = field(default_factory=list)
    failure_modes: List[Dict[str, Any]] = field(default_factory=list)
    fallback: Dict[str, Any] = field(default_factory=dict)


class SubgoalState(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    BLOCKED = "BLOCKED"
    FAILED_FATAL = "FAILED_FATAL"
    SKIPPED = "SKIPPED"


@dataclass
class RetryPolicy:
    max_attempts: int = 2
    backoff: str = "exponential"
    base_delay_ms: int = 300


@dataclass
class ExecutableSubgoal:
    id: str
    intent: str
    executor_type: str
    tool_name: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    success_criteria: List[Dict[str, Any]] = field(default_factory=list)
    failure_modes: List[Dict[str, Any]] = field(default_factory=list)
    fallback: Dict[str, Any] = field(default_factory=dict)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    state: SubgoalState = SubgoalState.DRAFT
    attempt_count: int = 0
    last_error: str = ""


@dataclass
class ExecutionRecord:
    goal_id: str
    task_id: str
    tool_name: str
    input_payload: str
    success: bool
    output: str = ""
    error: str = ""
    latency_ms: int = 0
    id: str = field(default_factory=lambda: _new_id("exec"))
    ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionRecord:
    goal_id: str
    task_id: str
    action: str  # retry|replan|halt|none
    reason: str
    replan_required: bool
    id: str = field(default_factory=lambda: _new_id("refl"))
    next_task_hint: Optional[str] = None
    ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActuatorCapability:
    name: str
    description: str
    command: str
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)
    supports_rollback: bool = False


@dataclass
class MotorCommand:
    command: str
    params: Dict[str, Any] = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: _new_id("motor"))
    idempotency_key: str = ""
    rollback_on_failure: bool = True


@dataclass
class ShellState:
    shell_id: str
    status: str
    pose: Dict[str, Any] = field(default_factory=dict)
    held_object: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MotorCommandResult:
    code: int
    success: bool
    execution: Optional[ExecutionRecord] = None
    error: str = ""


MOTOR_CODE_OK = 0
MOTOR_CODE_FAILED = 1
MOTOR_CODE_ACTION_NOT_FOUND = 2
MOTOR_CODE_COMMAND_MISMATCH = 3
