from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, Dict, Optional

from .interaction_executor import ActionEnvelope, ActionReceipt, FailureClass, InteractionExecutor


class DialogueExecutor(InteractionExecutor):
    """Dialogue actuation channel.

    Uses a tiny background pool so dialogue I/O does not block other executors.
    """

    def __init__(
        self,
        *,
        text_sink: Callable[[str, Dict[str, Any]], None],
        voice_sink: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(action_sink=None)
        self._text_sink = text_sink
        self._voice_sink = voice_sink
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="dialogue-actuation")

    def _execute_once(self, envelope: ActionEnvelope, started: float) -> ActionReceipt:
        text = str(envelope.payload.get("text") or "").strip()
        if not text:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="fail",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason="empty_text",
                failure_class=FailureClass.NON_RETRYABLE.value,
            )

        def _run_text() -> None:
            self._text_sink(text, dict(envelope.payload or {}))

        text_future = self._pool.submit(_run_text)
        try:
            text_future.result(timeout=float(envelope.timeout_s or 3.0))
        except TimeoutError:
            return ActionReceipt(
                action_id=envelope.action_id,
                channel=envelope.channel,
                target=envelope.target,
                status="timeout",
                success=False,
                started_at=started,
                ended_at=time.time(),
                retry_reason="dialogue_text_timeout",
                failure_class=FailureClass.RETRYABLE.value,
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
                retry_reason=f"dialogue_text_error:{type(e).__name__}",
                failure_class=FailureClass.RETRYABLE.value,
            )

        details: Dict[str, Any] = {"text_delivered": True}
        if bool(envelope.payload.get("voice_enabled")) and self._voice_sink is not None:
            voice_future = self._pool.submit(self._voice_sink, text, dict(envelope.payload or {}))
            try:
                voice_out = voice_future.result(timeout=float(envelope.timeout_s or 3.0))
                details["voice"] = dict(voice_out or {})
            except TimeoutError:
                details["voice"] = {"ok": False, "error": "timeout"}
            except Exception as e:
                details["voice"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

        return ActionReceipt(
            action_id=envelope.action_id,
            channel=envelope.channel,
            target=envelope.target,
            status="success",
            success=True,
            started_at=started,
            ended_at=time.time(),
            failure_class="",
            details=details,
        )
