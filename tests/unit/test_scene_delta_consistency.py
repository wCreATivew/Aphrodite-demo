from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = "_autonomy_scene_testpkg"


def _load_scene_modules():
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT / "agentlib" / "autonomy")]
    sys.modules[PKG] = pkg

    state_spec = importlib.util.spec_from_file_location(f"{PKG}.state", ROOT / "agentlib" / "autonomy" / "state.py")
    assert state_spec and state_spec.loader
    state_mod = importlib.util.module_from_spec(state_spec)
    sys.modules[f"{PKG}.state"] = state_mod
    state_spec.loader.exec_module(state_mod)

    runtime_spec = importlib.util.spec_from_file_location(
        f"{PKG}.scene_runtime", ROOT / "agentlib" / "autonomy" / "scene_runtime.py"
    )
    assert runtime_spec and runtime_spec.loader
    runtime_mod = importlib.util.module_from_spec(runtime_spec)
    sys.modules[f"{PKG}.scene_runtime"] = runtime_mod
    runtime_spec.loader.exec_module(runtime_mod)
    return state_mod, runtime_mod


state_mod, runtime_mod = _load_scene_modules()


SceneRuntime = runtime_mod.SceneRuntime
SceneActionStatus = state_mod.SceneActionStatus
SceneInteractablePoint = state_mod.SceneInteractablePoint
SceneObjectState = state_mod.SceneObjectState
SceneState = state_mod.SceneState


def _build_runtime() -> object:
    runtime = SceneRuntime(SceneState(scene_id="demo"))
    runtime.register_object(SceneObjectState(object_id="hero", object_type="actor"), position="room_a")
    runtime.register_interactable(
        SceneInteractablePoint(
            point_id="move_to_room_b",
            object_id="hero",
            action="move",
            constraints={"env.door_unlocked": True},
        )
    )
    return runtime


def test_apply_action_emits_pre_and_post_deltas() -> None:
    runtime = _build_runtime()
    outcome, post = runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        position_updates={"hero": "room_b"},
    )

    pre = runtime.consume_last_pre_delta()
    assert pre is not None
    assert outcome.success is False
    assert outcome.reason == "precondition_failed"
    assert pre.phase == "pre"
    assert pre.outcome == "pending"
    assert post.phase == "post"
    assert post.outcome == "precondition_failed"
    receipt = runtime.consume_last_receipt()
    assert receipt is not None
    assert receipt.status == SceneActionStatus.FAIL
    assert receipt.should_retry is False


def test_version_and_seq_progression() -> None:
    runtime = _build_runtime()
    deltas = []

    _, post1 = runtime.apply_action(actor="player", action="move", point_id="move_to_room_b")
    deltas.append(runtime.consume_last_pre_delta())
    deltas.append(post1)

    deltas.append(runtime.update_environment({"door_unlocked": True}))

    ok, post2 = runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        position_updates={"hero": "room_b"},
    )
    deltas.append(runtime.consume_last_pre_delta())
    deltas.append(post2)

    assert ok.success is True
    seqs = [d.seq for d in deltas if d is not None]
    assert seqs == list(range(1, len(seqs) + 1))
    assert runtime.state.delta_seq == len(seqs)
    assert runtime.state.state_version >= 4


def test_same_input_replays_same_deltas() -> None:
    def run_once() -> list[tuple]:
        runtime = _build_runtime()
        out = []

        _, p1 = runtime.apply_action(actor="player", action="move", point_id="move_to_room_b")
        out.extend([runtime.consume_last_pre_delta(), p1])
        out.append(runtime.update_environment({"door_unlocked": True}))
        _, p2 = runtime.apply_action(
            actor="player",
            action="move",
            point_id="move_to_room_b",
            position_updates={"hero": "room_b"},
        )
        out.extend([runtime.consume_last_pre_delta(), p2])
        return [
            (
                d.seq,
                d.phase,
                d.actor,
                d.action,
                d.outcome,
                dict(d.position_updates),
                dict(d.env_updates),
            )
            for d in out
            if d is not None
        ]

    assert run_once() == run_once()


def test_unified_receipt_success_failure_timeout_cancel() -> None:
    runtime = _build_runtime()
    runtime.update_environment({"door_unlocked": True})

    _, post_success = runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        position_updates={"hero": "room_b"},
    )
    runtime.consume_last_pre_delta()
    success_receipt = runtime.consume_last_receipt()
    assert success_receipt is not None
    assert success_receipt.status == SceneActionStatus.SUCCESS
    assert post_success.outcome == "applied"

    _, post_fail = runtime.apply_action(actor="player", action="invalid", point_id="move_to_room_b")
    runtime.consume_last_pre_delta()
    fail_receipt = runtime.consume_last_receipt()
    assert fail_receipt is not None
    assert fail_receipt.status == SceneActionStatus.FAIL
    assert post_fail.outcome == "action_mismatch"

    _, post_timeout = runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        control={"timeout_ms": 100, "simulated_latency_ms": 120},
        retry_policy={"max_attempts": 2},
        idempotent=True,
    )
    runtime.consume_last_pre_delta()
    timeout_receipt = runtime.consume_last_receipt()
    assert timeout_receipt is not None
    assert timeout_receipt.status == SceneActionStatus.TIMEOUT
    assert timeout_receipt.should_retry is True
    assert post_timeout.outcome == "timeout"

    _, post_cancel = runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        control={"cancel_requested": True},
    )
    runtime.consume_last_pre_delta()
    cancel_receipt = runtime.consume_last_receipt()
    assert cancel_receipt is not None
    assert cancel_receipt.status == SceneActionStatus.CANCEL
    assert cancel_receipt.should_retry is False
    assert post_cancel.outcome == "cancelled"


def test_non_idempotent_action_does_not_auto_retry_by_default() -> None:
    runtime = _build_runtime()
    runtime.update_environment({"door_unlocked": True})

    runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_to_room_b",
        control={"timeout_ms": 100, "simulated_latency_ms": 200},
        retry_policy={"max_attempts": 3, "auto_retry_on_timeout": True},
        idempotent=False,
    )
    runtime.consume_last_pre_delta()
    receipt = runtime.consume_last_receipt()
    assert receipt is not None
    assert receipt.status == SceneActionStatus.TIMEOUT
    assert receipt.retryable is False
    assert receipt.should_retry is False
