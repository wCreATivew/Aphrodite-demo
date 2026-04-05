from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "_autonomy_scene_replaypkg"


def _load_scene_modules():
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT / "agentlib" / "autonomy")]
    sys.modules[PKG] = pkg

    state_spec = importlib.util.spec_from_file_location(f"{PKG}.state", ROOT / "agentlib" / "autonomy" / "state.py")
    state_mod = importlib.util.module_from_spec(state_spec)
    sys.modules[f"{PKG}.state"] = state_mod
    assert state_spec and state_spec.loader
    state_spec.loader.exec_module(state_mod)

    runtime_spec = importlib.util.spec_from_file_location(
        f"{PKG}.scene_runtime", ROOT / "agentlib" / "autonomy" / "scene_runtime.py"
    )
    runtime_mod = importlib.util.module_from_spec(runtime_spec)
    sys.modules[f"{PKG}.scene_runtime"] = runtime_mod
    assert runtime_spec and runtime_spec.loader
    runtime_spec.loader.exec_module(runtime_mod)
    return state_mod, runtime_mod


def run_scenario() -> list[dict]:
    state_mod, runtime_mod = _load_scene_modules()
    runtime = runtime_mod.SceneRuntime(state_mod.SceneState(scene_id="replay-check"))
    runtime.register_object(state_mod.SceneObjectState(object_id="hero", object_type="actor"), position="room_a")
    runtime.register_interactable(
        state_mod.SceneInteractablePoint(
            point_id="move_room_b",
            object_id="hero",
            action="move",
            constraints={"env.door_unlocked": True},
        )
    )
    deltas = []
    _, post1 = runtime.apply_action(actor="player", action="move", point_id="move_room_b", position_updates={"hero": "room_b"})
    deltas.extend([runtime.consume_last_pre_delta(), post1])
    deltas.append(runtime.update_environment({"door_unlocked": True}))
    _, post2 = runtime.apply_action(actor="player", action="move", point_id="move_room_b", position_updates={"hero": "room_b"})
    deltas.extend([runtime.consume_last_pre_delta(), post2])
    return [asdict(d) for d in deltas if d is not None]


def main() -> int:
    first = run_scenario()
    second = run_scenario()
    if first != second:
        print("SCENE_DELTA_REPLAY_MISMATCH")
        print(json.dumps({"first": first, "second": second}, ensure_ascii=False, indent=2))
        return 1
    print("SCENE_DELTA_REPLAY_OK")
    print(json.dumps(first, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
