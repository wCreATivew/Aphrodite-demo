from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    REFLECTING = "reflecting"
    REPLANNING = "replanning"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class SceneObjectState:
    """Discrete world object representation used for replay-friendly state updates."""

    object_id: str
    object_type: str
    status: str = "idle"
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneInteractablePoint:
    """Declarative interaction entry-point in scene."""

    point_id: str
    object_id: str
    action: str
    enabled: bool = True
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneInteractionRule:
    """Rule for deciding whether an actor can execute an action on an interaction point."""

    rule_id: str
    action: str
    point_id: Optional[str] = None
    actor_whitelist: List[str] = field(default_factory=list)
    required_env: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneState:
    """Minimal discrete scene model.

    Design goals:
    1) Keep it auditable (plain values + append-only deltas).
    2) Keep it replayable (deterministic tick, state map updates).
    """

    scene_id: str = "default"
    tick: int = 0
    objects: Dict[str, SceneObjectState] = field(default_factory=dict)
    positions: Dict[str, str] = field(default_factory=dict)
    interactable_points: Dict[str, SceneInteractablePoint] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    interaction_rules: List[SceneInteractionRule] = field(default_factory=list)


@dataclass
class SceneInteractionOutcome:
    success: bool
    reason: str = ""
    blocked_by: List[str] = field(default_factory=list)


@dataclass
class SceneDelta:
    """Atomic scene mutation for trace + persistence replay."""

    tick: int
    actor: str
    action: str
    point_id: Optional[str]
    object_updates: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    position_updates: Dict[str, str] = field(default_factory=dict)
    env_updates: Dict[str, Any] = field(default_factory=dict)
    side_effects: List[str] = field(default_factory=list)
