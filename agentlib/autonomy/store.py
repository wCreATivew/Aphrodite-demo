from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import ExecutionRecord, Goal, ReflectionRecord, Task
from .scene_runtime import SceneRuntime
from .state import AgentState, SceneActionReceipt, SceneDelta, SceneInteractionOutcome, SceneState
from .tracing import TraceEvent


@dataclass
class SceneSnapshot:
    """Minimal replayable scene persistence payload."""

    version: str
    scene_id: str
    state_version: int
    delta_seq: int
    tick: int
    objects: Dict[str, Dict[str, Any]]
    positions: Dict[str, str]
    interactable_points: Dict[str, Dict[str, Any]]
    environment: Dict[str, Any]
    interaction_rules: List[Dict[str, Any]]
    last_delta: Optional[Dict[str, Any]] = None




@dataclass
class ScenePerception:
    """Actor-facing scene view used as next-step perception input."""

    actor: str
    state_version: int
    delta_seq: int
    tick: int
    objects: Dict[str, Dict[str, Any]]
    positions: Dict[str, str]
    interactable_points: Dict[str, Dict[str, Any]]
    environment: Dict[str, Any]
    recent_deltas: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class InMemoryStateStore:
    state: AgentState = AgentState.IDLE
    goals: Dict[str, Goal] = field(default_factory=dict)
    tasks_by_goal: Dict[str, List[Task]] = field(default_factory=dict)
    executions: List[ExecutionRecord] = field(default_factory=list)
    reflections: List[ReflectionRecord] = field(default_factory=list)
    traces: List[TraceEvent] = field(default_factory=list)
    failure_fingerprints: List[str] = field(default_factory=list)
    replan_actions: List[str] = field(default_factory=list)
    scene: SceneState = field(default_factory=SceneState)
    scene_deltas: List[SceneDelta] = field(default_factory=list)
    scene_action_receipts: List[SceneActionReceipt] = field(default_factory=list)
    last_done_ts: float = 0.0
    last_done_cycle: int = 0
    pause_requested: bool = False
    stop_requested: bool = False
    latest_perception: Dict[str, object] = field(default_factory=dict)

    def add_goal(self, goal: Goal) -> None:
        self.goals[goal.id] = goal
        self.tasks_by_goal.setdefault(goal.id, [])

    def add_tasks(self, goal_id: str, tasks: List[Task]) -> None:
        self.tasks_by_goal.setdefault(goal_id, []).extend(tasks)

    def list_tasks(self, goal_id: str) -> List[Task]:
        return list(self.tasks_by_goal.get(goal_id, []))

    def next_pending_task(self, goal_id: str) -> Optional[Task]:
        for task in self.tasks_by_goal.get(goal_id, []):
            if str(task.status or "").lower() in {"pending", "draft", "ready", "failed_retryable"}:
                return task
        return None

    def add_execution(self, rec: ExecutionRecord) -> None:
        self.executions.append(rec)

    def add_reflection(self, rec: ReflectionRecord) -> None:
        self.reflections.append(rec)

    def add_trace(self, evt: TraceEvent) -> None:
        self.traces.append(evt)

    def add_scene_delta(self, delta: SceneDelta) -> None:
        self.scene_deltas.append(delta)

    def add_scene_action_receipt(self, receipt: SceneActionReceipt) -> None:
        self.scene_action_receipts.append(receipt)

    def apply_scene_action(
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
    ) -> Tuple[SceneInteractionOutcome, SceneDelta]:
        runtime = SceneRuntime(self.scene)
        outcome, delta = runtime.apply_action(
            actor=actor,
            action=action,
            point_id=point_id,
            object_updates=object_updates,
            env_updates=env_updates,
            position_updates=position_updates,
            control=control,
            retry_policy=retry_policy,
            idempotent=idempotent,
        )
        pre_delta = runtime.consume_last_pre_delta()
        receipt = runtime.consume_last_receipt()
        self.scene = runtime.state
        if pre_delta is not None:
            self.add_scene_delta(pre_delta)
        self.add_scene_delta(delta)
        if receipt is not None:
            self.add_scene_action_receipt(receipt)
        return outcome, delta

    def update_scene_environment(self, updates: Dict[str, Any]) -> SceneDelta:
        runtime = SceneRuntime(self.scene)
        delta = runtime.update_environment(updates)
        self.scene = runtime.state
        self.add_scene_delta(delta)
        return delta

    def get_scene_perception(self, *, actor: str, recent_delta_limit: int = 5) -> ScenePerception:
        recent = self.scene_deltas[-max(0, int(recent_delta_limit)) :] if recent_delta_limit else []
        return ScenePerception(
            actor=str(actor or "agent"),
            state_version=int(self.scene.state_version),
            delta_seq=int(self.scene.delta_seq),
            tick=int(self.scene.tick),
            objects={
                obj_id: {
                    "object_type": obj.object_type,
                    "status": obj.status,
                    "attrs": dict(obj.attrs),
                }
                for obj_id, obj in self.scene.objects.items()
            },
            positions={k: str(v) for k, v in self.scene.positions.items()},
            interactable_points={
                point_id: {
                    "object_id": point.object_id,
                    "action": point.action,
                    "enabled": bool(point.enabled),
                    "constraints": dict(point.constraints),
                }
                for point_id, point in self.scene.interactable_points.items()
            },
            environment=dict(self.scene.environment),
            recent_deltas=[
                {
                    "seq": d.seq,
                    "tick": d.tick,
                    "actor": d.actor,
                    "action": d.action,
                    "point_id": d.point_id,
                    "phase": d.phase,
                    "outcome": d.outcome,
                    "state_version": d.state_version,
                    "object_updates": dict(d.object_updates),
                    "position_updates": dict(d.position_updates),
                    "env_updates": dict(d.env_updates),
                    "side_effects": list(d.side_effects),
                }
                for d in recent
            ],
        )

    def set_state(self, state: AgentState) -> None:
        self.state = state

    def set_latest_perception(self, snapshot: Dict[str, object]) -> None:
        self.latest_perception = dict(snapshot or {})

    def mark_done_progress(self, cycle: int, ts: float) -> None:
        self.last_done_cycle = max(int(self.last_done_cycle), int(cycle))
        self.last_done_ts = max(float(self.last_done_ts), float(ts))

    def build_scene_snapshot(self) -> SceneSnapshot:
        last_delta = None
        if self.scene_deltas:
            d = self.scene_deltas[-1]
            last_delta = {
                "seq": d.seq,
                "tick": d.tick,
                "actor": d.actor,
                "action": d.action,
                "point_id": d.point_id,
                "phase": d.phase,
                "outcome": d.outcome,
                "state_version": d.state_version,
                "object_updates": dict(d.object_updates),
                "position_updates": dict(d.position_updates),
                "env_updates": dict(d.env_updates),
                "side_effects": list(d.side_effects),
            }

        return SceneSnapshot(
            version="scene_snapshot.v1",
            scene_id=str(self.scene.scene_id),
            state_version=int(self.scene.state_version),
            delta_seq=int(self.scene.delta_seq),
            tick=int(self.scene.tick),
            objects={
                obj_id: {
                    "object_id": obj.object_id,
                    "object_type": obj.object_type,
                    "status": obj.status,
                    "attrs": dict(obj.attrs),
                }
                for obj_id, obj in self.scene.objects.items()
            },
            positions={k: str(v) for k, v in self.scene.positions.items()},
            interactable_points={
                point_id: {
                    "point_id": point.point_id,
                    "object_id": point.object_id,
                    "action": point.action,
                    "enabled": bool(point.enabled),
                    "constraints": dict(point.constraints),
                }
                for point_id, point in self.scene.interactable_points.items()
            },
            environment=dict(self.scene.environment),
            interaction_rules=[
                {
                    "rule_id": r.rule_id,
                    "action": r.action,
                    "point_id": r.point_id,
                    "actor_whitelist": list(r.actor_whitelist),
                    "required_env": dict(r.required_env),
                }
                for r in self.scene.interaction_rules
            ],
            last_delta=last_delta,
        )
