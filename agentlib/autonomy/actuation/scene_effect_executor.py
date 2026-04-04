from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from .interaction_executor import ActionEnvelope, ActionReceipt, InteractionExecutor


class SceneEffectExecutor(InteractionExecutor):
    """Executor for non-dialogue expressive channels (animation, VFX, avatar cues)."""

    def __init__(self, effect_sink: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> None:
        super().__init__(action_sink=None)
        self._effect_sink = effect_sink

    def execute(self, envelope: ActionEnvelope) -> ActionReceipt:
        started = time.time()
        base = super().execute(envelope)
        if not base.success:
            return base

        if self._effect_sink is None:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="skipped",
                success=True,
                started_at=started,
                ended_at=time.time(),
                details={"reason": "no_scene_effect_sink"},
            )

        try:
            out = self._effect_sink(dict(envelope.payload or {}))
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="ok",
                success=True,
                started_at=started,
                ended_at=time.time(),
                details=dict(out or {}),
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
                retry_reason=f"scene_effect_error:{type(e).__name__}",
            )
