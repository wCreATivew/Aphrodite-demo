from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ActionReceipt:
    action_id: str
    channel: str
    target: str
    status: str
    success: bool
    started_at: float
    ended_at: float
    retry_reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionEnvelope:
    """Unified action contract for all actuation channels.

    Priorities (high -> low): safety > interaction_smoothness > expressive_enrichment.
    """

    action_id: str
    channel: str
    target: str
    payload: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    timeout_s: float = 3.0
    interruptible: bool = True
    receipt_required: bool = True
    priority: str = "interaction_smoothness"
    rollback_payload: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        *,
        channel: str,
        target: str,
        payload: Optional[Dict[str, Any]] = None,
        preconditions: Optional[List[Dict[str, Any]]] = None,
        timeout_s: float = 3.0,
        interruptible: bool = True,
        receipt_required: bool = True,
        priority: str = "interaction_smoothness",
        rollback_payload: Optional[Dict[str, Any]] = None,
    ) -> "ActionEnvelope":
        return cls(
            action_id=f"act_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}",
            channel=str(channel or "generic").strip().lower(),
            target=str(target or "").strip(),
            payload=dict(payload or {}),
            preconditions=[dict(p) for p in list(preconditions or []) if isinstance(p, dict)],
            timeout_s=max(0.1, float(timeout_s or 0.1)),
            interruptible=bool(interruptible),
            receipt_required=bool(receipt_required),
            priority=str(priority or "interaction_smoothness").strip().lower(),
            rollback_payload=dict(rollback_payload or {}),
        )


class InteractionExecutor:
    """Base interaction executor that validates envelope preconditions."""

    PRIORITY_ORDER = {
        "safety": 0,
        "interaction_smoothness": 1,
        "expressive_enrichment": 2,
    }

    def __init__(self, action_sink: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> None:
        self._action_sink = action_sink

    def can_execute(self, envelope: ActionEnvelope) -> bool:
        for cond in list(envelope.preconditions or []):
            if not bool(cond.get("ok", True)):
                return False
        return True

    def execute(self, envelope: ActionEnvelope) -> ActionReceipt:
        started = time.time()
        if not self.can_execute(envelope):
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="blocked",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason="precondition_failed",
                details={"preconditions": list(envelope.preconditions or [])},
            )
        if self._action_sink is None:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="ok",
                success=True,
                started_at=started,
                ended_at=time.time(),
                details={"envelope": asdict(envelope), "sink": "noop"},
            )
        try:
            sink_out = self._action_sink(
                {
                    "action_id": envelope.action_id,
                    "channel": envelope.channel,
                    "target": envelope.target,
                    "payload": dict(envelope.payload or {}),
                }
            )
        except Exception as e:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="failed",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason=f"interaction_error:{type(e).__name__}",
            )
        return ActionReceipt(
            action_id=envelope.action_id,
            channel=envelope.channel,
            target=envelope.target,
            status="ok",
            success=True,
            started_at=started,
            ended_at=time.time(),
            details={"envelope": asdict(envelope), "sink_output": dict(sink_out or {})},
        )
