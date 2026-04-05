from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "_autonomy_scene_receiptpkg"


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


def build_runtime():
    state_mod, runtime_mod = _load_scene_modules()
    runtime = runtime_mod.SceneRuntime(state_mod.SceneState(scene_id="receipt-demo"))
    runtime.register_object(state_mod.SceneObjectState(object_id="hero", object_type="actor"), position="room_a")
    runtime.register_interactable(
        state_mod.SceneInteractablePoint(
            point_id="move_room_b",
            object_id="hero",
            action="move",
            constraints={"env.door_unlocked": True},
        )
    )
    return runtime


def run() -> list[dict]:
    runtime = build_runtime()
    runtime.update_environment({"door_unlocked": True})
    rows = []

    runtime.apply_action(actor="player", action="move", point_id="move_room_b", position_updates={"hero": "room_b"})
    runtime.consume_last_pre_delta()
    rows.append(asdict(runtime.consume_last_receipt()))

    runtime.apply_action(actor="player", action="move", point_id="missing_point")
    runtime.consume_last_pre_delta()
    rows.append(asdict(runtime.consume_last_receipt()))

    runtime.apply_action(
        actor="player",
        action="move",
        point_id="move_room_b",
        control={"timeout_ms": 100, "simulated_latency_ms": 180},
        retry_policy={"max_attempts": 2},
        idempotent=True,
    )
    runtime.consume_last_pre_delta()
    rows.append(asdict(runtime.consume_last_receipt()))

    return rows


def main() -> int:
    records = run()
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
