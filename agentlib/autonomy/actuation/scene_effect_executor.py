from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from .interaction_executor import ActionEnvelope, ActionReceipt, FailureClass, InteractionExecutor


class SceneEffectExecutor(InteractionExecutor):
    """Executor for non-dialogue expressive channels (animation, VFX, avatar cues)."""

    def __init__(self, effect_sink: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> None:
        super().__init__(action_sink=None)
        self._effect_sink = effect_sink

    def _execute_once(self, envelope: ActionEnvelope, started: float) -> ActionReceipt:
        if self._effect_sink is None:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="fail",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason="dependency_missing:scene_effect_sink",
                failure_class=FailureClass.DEPENDENCY_MISSING.value,
                details={"reason": "no_scene_effect_sink"},
            )

        try:
            out = self._effect_sink(dict(envelope.payload or {}))
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="success",
                success=True,
                started_at=started,
                ended_at=time.time(),
                failure_class="",
                details=dict(out or {}),
            )
        except Exception as e:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="fail",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason=f"scene_effect_error:{type(e).__name__}",
                failure_class=FailureClass.RETRYABLE.value,
            )
