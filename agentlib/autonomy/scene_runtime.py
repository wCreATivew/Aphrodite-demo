from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any, Dict, Optional

from .state import (
    SceneActionReceipt,
    SceneActionStatus,
    SceneDelta,
    SceneInteractionOutcome,
    SceneInteractablePoint,
    SceneInteractionRule,
    SceneObjectState,
    SceneState,
)


class SceneRuntime:
    """Discrete scene state machine.

    Keeps interactions deterministic and append-only through SceneDelta.
    """

    def __init__(self, initial_state: Optional[SceneState] = None):
        self.state = initial_state or SceneState()
        self._last_pre_delta: Optional[SceneDelta] = None
        self._last_receipt: Optional[SceneActionReceipt] = None

    def _next_seq(self) -> int:
        self.state.delta_seq += 1
        return self.state.delta_seq

    def _bump_state_version(self) -> int:
        self.state.state_version += 1
        return self.state.state_version

    def register_object(self, obj: SceneObjectState, *, position: Optional[str] = None) -> None:
        self.state.objects[obj.object_id] = obj
        if position is not None:
            self.state.positions[obj.object_id] = str(position)

    def register_interactable(self, point: SceneInteractablePoint) -> None:
        self.state.interactable_points[point.point_id] = point

    def register_rule(self, rule: SceneInteractionRule) -> None:
        self.state.interaction_rules.append(rule)

    def consume_last_pre_delta(self) -> Optional[SceneDelta]:
        pre = self._last_pre_delta
        self._last_pre_delta = None
        return pre

    def consume_last_receipt(self) -> Optional[SceneActionReceipt]:
        receipt = self._last_receipt
        self._last_receipt = None
        return receipt

    def update_environment(self, updates: Dict[str, Any]) -> SceneDelta:
        self.state.tick += 1
        self.state.environment.update(dict(updates or {}))
        return SceneDelta(
            seq=self._next_seq(),
            tick=self.state.tick,
            actor="system",
            action="env_update",
            point_id=None,
            phase="post",
            outcome="applied",
            state_version=self._bump_state_version(),
            env_updates=dict(updates or {}),
            side_effects=["environment_updated"],
        )

    def evaluate_interaction(self, *, actor: str, action: str, point_id: str) -> SceneInteractionOutcome:
        point = self.state.interactable_points.get(point_id)
        if point is None:
            return SceneInteractionOutcome(success=False, reason="point_not_found", blocked_by=["point_missing"])
        if not point.enabled:
            return SceneInteractionOutcome(success=False, reason="point_disabled", blocked_by=["point_disabled"])
        if point.action != action:
            return SceneInteractionOutcome(success=False, reason="action_mismatch", blocked_by=["action_mismatch"])

        blockers = []
        for rule in self.state.interaction_rules:
            if rule.action != action:
                continue
            if rule.point_id and rule.point_id != point_id:
                continue
            if rule.actor_whitelist and actor not in rule.actor_whitelist:
                blockers.append(f"rule:{rule.rule_id}:actor_not_allowed")
                continue
            for k, v in rule.required_env.items():
                if self.state.environment.get(k) != v:
                    blockers.append(f"rule:{rule.rule_id}:env:{k}")

        if blockers:
            return SceneInteractionOutcome(success=False, reason="rule_blocked", blocked_by=blockers)
        for key, expected in (point.constraints or {}).items():
            if not str(key).startswith("env."):
                continue
            env_key = str(key)[4:]
            if self.state.environment.get(env_key) != expected:
                return SceneInteractionOutcome(
                    success=False,
                    reason="precondition_failed",
                    blocked_by=[f"precondition_failed:env:{env_key}"],
                )
        return SceneInteractionOutcome(success=True, reason="ok")

    def apply_action(
        self,
        *,
        actor: str,
        action: str,
        point_id: str,
        object_updates: Optional[Dict[str, Dict[str, Any]]] = None,
        env_updates: Optional[Dict[str, Any]] = None,
        position_updates: Optional[Dict[str, str]] = None,
        control: Optional[Dict[str, Any]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        idempotent: bool = False,
    ) -> tuple[SceneInteractionOutcome, SceneDelta]:
        action_id = f"act_{uuid.uuid4().hex[:10]}"
        control_map = dict(control or {})
        retry_cfg = dict(retry_policy or {})
        max_attempts = max(1, int(retry_cfg.get("max_attempts", 1)))
        timeout_ms = int(control_map.get("timeout_ms", 0) or 0)
        simulated_latency_ms = int(control_map.get("simulated_latency_ms", 0) or 0)
        cancel_requested = bool(control_map.get("cancel_requested", False))

        pre_delta = SceneDelta(
            seq=self._next_seq(),
            tick=self.state.tick,
            actor=actor,
            action=action,
            point_id=point_id,
            phase="pre",
            outcome="pending",
            state_version=self.state.state_version,
            side_effects=["interaction_started"],
        )
        self._last_pre_delta = pre_delta
        post_outcome = "applied"
        post_side_effects = ["interaction_applied"]
        final_outcome = SceneInteractionOutcome(success=True, reason="ok")
        status = SceneActionStatus.SUCCESS

        if cancel_requested:
            final_outcome = SceneInteractionOutcome(success=False, reason="cancelled", blocked_by=["cancel_requested"])
            status = SceneActionStatus.CANCEL
            post_outcome = "cancelled"
            post_side_effects = ["interaction_cancelled", "cancel_requested"]
        elif timeout_ms > 0 and simulated_latency_ms > timeout_ms:
            final_outcome = SceneInteractionOutcome(
                success=False,
                reason="timeout",
                blocked_by=[f"timeout>{timeout_ms}ms"],
            )
            status = SceneActionStatus.TIMEOUT
            post_outcome = "timeout"
            post_side_effects = ["interaction_timeout", f"timeout>{timeout_ms}ms"]
        else:
            final_outcome = self.evaluate_interaction(actor=actor, action=action, point_id=point_id)
            if not final_outcome.success:
                status = SceneActionStatus.FAIL
                post_outcome = final_outcome.reason or "rejected"
                post_side_effects = ["interaction_rejected", *final_outcome.blocked_by]

        self.state.tick += 1
        if not final_outcome.success:
            post_delta = SceneDelta(
                seq=self._next_seq(),
                tick=self.state.tick,
                actor=actor,
                action=action,
                point_id=point_id,
                phase="post",
                outcome=post_outcome,
                state_version=self._bump_state_version(),
                side_effects=post_side_effects,
            )
            retryable = status == SceneActionStatus.TIMEOUT
            should_retry = (
                retryable
                and bool(idempotent)
                and max_attempts > 1
                and bool(retry_cfg.get("auto_retry_on_timeout", True))
            )
            retry_trigger = "timeout" if should_retry else ""
            self._last_receipt = SceneActionReceipt(
                action_id=action_id,
                actor=actor,
                action=action,
                point_id=point_id,
                status=status,
                outcome_reason=final_outcome.reason,
                pre_delta_seq=pre_delta.seq,
                post_delta_seq=post_delta.seq,
                attempts_used=1,
                max_attempts=max_attempts,
                retryable=retryable and bool(idempotent),
                should_retry=should_retry,
                retry_trigger=retry_trigger,
            )
            return final_outcome, post_delta

        applied_object_updates: Dict[str, Dict[str, Any]] = {}
        for obj_id, patch in (object_updates or {}).items():
            if obj_id not in self.state.objects:
                continue
            obj = self.state.objects[obj_id]
            new_attrs = dict(obj.attrs)
            new_attrs.update(dict(patch or {}))
            self.state.objects[obj_id] = replace(obj, attrs=new_attrs)
            applied_object_updates[obj_id] = dict(patch or {})

        applied_positions: Dict[str, str] = {}
        for obj_id, pos in (position_updates or {}).items():
            if obj_id in self.state.objects:
                self.state.positions[obj_id] = str(pos)
                applied_positions[obj_id] = str(pos)

        applied_env: Dict[str, Any] = {}
        if env_updates:
            self.state.environment.update(dict(env_updates))
            applied_env = dict(env_updates)

        post_delta = SceneDelta(
            seq=self._next_seq(),
            tick=self.state.tick,
            actor=actor,
            action=action,
            point_id=point_id,
            phase="post",
            outcome="applied",
            state_version=self._bump_state_version(),
            object_updates=applied_object_updates,
            position_updates=applied_positions,
            env_updates=applied_env,
            side_effects=["interaction_applied"],
        )
        self._last_receipt = SceneActionReceipt(
            action_id=action_id,
            actor=actor,
            action=action,
            point_id=point_id,
            status=status,
            outcome_reason=final_outcome.reason,
            pre_delta_seq=pre_delta.seq,
            post_delta_seq=post_delta.seq,
            attempts_used=1,
            max_attempts=max_attempts,
            retryable=False,
            should_retry=False,
            retry_trigger="",
        )
        return final_outcome, post_delta
