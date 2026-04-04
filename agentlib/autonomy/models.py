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


class EmbodiedLifecycle(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DROPPED = "dropped"


class EmbodiedEventType(str, Enum):
    INPUT_VISUAL_PSEUDO = "input.visual.pseudo"
    INPUT_AUDIO_PSEUDO = "input.audio.pseudo"
    INPUT_TOUCH_PSEUDO = "input.touch.pseudo"
    INPUT_OLFACTORY_PSEUDO = "input.olfactory.pseudo"
    OUTPUT_SCENE_ACTION = "output.scene.action"
    OUTPUT_DIALOG_UTTERANCE = "output.dialog.utterance"
    OUTPUT_INTERACTION_FEEDBACK = "output.interaction.feedback"
    INTERNAL_BRAIN_DECISION = "internal.brain.decision"
    INTERNAL_STATE_UPDATED = "internal.state.updated"
    INTERNAL_MEMORY_WRITE = "internal.memory.write"


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
class EmbodiedEvent:
    """Protocol draft: unified event model for autonomy runtime."""

    event_id: str = field(default_factory=lambda: _new_id("evt"))
    event_type: str = EmbodiedEventType.INTERNAL_BRAIN_DECISION.value
    lifecycle: EmbodiedLifecycle = EmbodiedLifecycle.QUEUED
    ts: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: _new_id("trace"))
    source: str = ""
    target: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    # Extension zone: keep optional, avoid algorithm lock-in in v0.
    emotion: Optional[str] = None
    uncertainty: Optional[float] = None
    source_latency_ms: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_input_modality(
        cls,
        *,
        modality: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "",
        target: str = "brain",
        trace_id: Optional[str] = None,
    ) -> "EmbodiedEvent":
        mapping = {
            "visual": EmbodiedEventType.INPUT_VISUAL_PSEUDO.value,
            "audio": EmbodiedEventType.INPUT_AUDIO_PSEUDO.value,
            "touch": EmbodiedEventType.INPUT_TOUCH_PSEUDO.value,
            "olfactory": EmbodiedEventType.INPUT_OLFACTORY_PSEUDO.value,
        }
        normalized = str(modality or "").strip().lower()
        if normalized not in mapping:
            raise ValueError(f"unsupported input modality: {modality}")
        return cls(
            event_type=mapping[normalized],
            trace_id=str(trace_id or _new_id("trace")),
            source=source,
            target=target,
            payload=dict(payload or {}),
        )

    @classmethod
    def from_output_channel(
        cls,
        *,
        channel: str,
        payload: Optional[Dict[str, Any]] = None,
        source: str = "brain",
        target: str = "",
        trace_id: Optional[str] = None,
    ) -> "EmbodiedEvent":
        mapping = {
            "scene_action": EmbodiedEventType.OUTPUT_SCENE_ACTION.value,
            "dialog_utterance": EmbodiedEventType.OUTPUT_DIALOG_UTTERANCE.value,
            "interaction_feedback": EmbodiedEventType.OUTPUT_INTERACTION_FEEDBACK.value,
        }
        normalized = str(channel or "").strip().lower()
        if normalized not in mapping:
            raise ValueError(f"unsupported output channel: {channel}")
        return cls(
            event_type=mapping[normalized],
            trace_id=str(trace_id or _new_id("trace")),
            source=source,
            target=target,
            payload=dict(payload or {}),
        )
