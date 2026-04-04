from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, Optional

from .state import (
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

    def register_object(self, obj: SceneObjectState, *, position: Optional[str] = None) -> None:
        self.state.objects[obj.object_id] = obj
        if position is not None:
            self.state.positions[obj.object_id] = str(position)

    def register_interactable(self, point: SceneInteractablePoint) -> None:
        self.state.interactable_points[point.point_id] = point

    def register_rule(self, rule: SceneInteractionRule) -> None:
        self.state.interaction_rules.append(rule)

    def update_environment(self, updates: Dict[str, Any]) -> SceneDelta:
        self.state.tick += 1
        self.state.environment.update(dict(updates or {}))
        return SceneDelta(
            tick=self.state.tick,
            actor="system",
            action="env_update",
            point_id=None,
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
    ) -> tuple[SceneInteractionOutcome, SceneDelta]:
        outcome = self.evaluate_interaction(actor=actor, action=action, point_id=point_id)
        self.state.tick += 1
        if not outcome.success:
            return outcome, SceneDelta(
                tick=self.state.tick,
                actor=actor,
                action=action,
                point_id=point_id,
                side_effects=["interaction_rejected", *outcome.blocked_by],
            )

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

        return outcome, SceneDelta(
            tick=self.state.tick,
            actor=actor,
            action=action,
            point_id=point_id,
            object_updates=applied_object_updates,
            position_updates=applied_positions,
            env_updates=applied_env,
            side_effects=["interaction_applied"],
        )
