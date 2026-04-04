from __future__ import annotations

import copy
import time
from typing import Dict, List

from ..models import ActuatorCapability, ExecutionRecord, MotorCommand, ShellState


class MockShellAdapter:
    """Mock shell adapter with capability discovery and idempotent command execution."""

    def __init__(self) -> None:
        self._state = ShellState(
            shell_id="mock-shell",
            status="idle",
            pose={"x": 0, "y": 0, "z": 0},
            held_object="",
        )
        self._capabilities: Dict[str, ActuatorCapability] = {
            "move": ActuatorCapability(
                name="move",
                description="Move shell to a relative delta.",
                command="move",
                required_params=["dx", "dy"],
                optional_params=["dz"],
                supports_rollback=True,
            ),
            "interact": ActuatorCapability(
                name="interact",
                description="Interact with a target object in scene.",
                command="interact",
                required_params=["target"],
                optional_params=["mode"],
                supports_rollback=False,
            ),
            "grasp": ActuatorCapability(
                name="grasp",
                description="Pick up a scene object.",
                command="grasp",
                required_params=["object_id"],
                optional_params=[],
                supports_rollback=True,
            ),
        }
        self._executed_by_key: Dict[str, ExecutionRecord] = {}

    def observe_shell_state(self) -> ShellState:
        return copy.deepcopy(self._state)

    def get_actuator_capabilities(self) -> List[ActuatorCapability]:
        return [copy.deepcopy(self._capabilities[key]) for key in sorted(self._capabilities)]

    def execute_motor_command(self, command: MotorCommand) -> ExecutionRecord:
        t0 = time.time()
        key = str(command.idempotency_key or command.command_id)
        cached = self._executed_by_key.get(key)
        if cached is not None:
            out = copy.deepcopy(cached)
            out.metadata = dict(out.metadata)
            out.metadata["idempotent_replay"] = True
            return out

        snapshot = copy.deepcopy(self._state)
        try:
            cap = self._capabilities.get(command.command)
            if cap is None:
                raise ValueError(f"unsupported_command: {command.command}")

            missing = [p for p in cap.required_params if p not in command.params]
            if missing:
                raise ValueError(f"missing_required_params: {','.join(missing)}")

            self._apply(command)
            rec = ExecutionRecord(
                goal_id="shell",
                task_id=command.command_id,
                tool_name=f"shell.{command.command}",
                input_payload=str(command.params),
                success=True,
                output="ok",
                latency_ms=int((time.time() - t0) * 1000),
                metadata={"idempotent_replay": False},
            )
            self._executed_by_key[key] = copy.deepcopy(rec)
            return rec
        except Exception as e:
            if command.rollback_on_failure:
                self._state = snapshot
            return ExecutionRecord(
                goal_id="shell",
                task_id=command.command_id,
                tool_name=f"shell.{command.command}",
                input_payload=str(command.params),
                success=False,
                error=f"{type(e).__name__}: {e}",
                latency_ms=int((time.time() - t0) * 1000),
                metadata={"rolled_back": bool(command.rollback_on_failure)},
            )

    def _apply(self, command: MotorCommand) -> None:
        params = dict(command.params)
        if command.command == "move":
            self._state.pose["x"] = int(self._state.pose.get("x", 0)) + int(params.get("dx", 0))
            self._state.pose["y"] = int(self._state.pose.get("y", 0)) + int(params.get("dy", 0))
            self._state.pose["z"] = int(self._state.pose.get("z", 0)) + int(params.get("dz", 0))
            self._state.status = "moving"
            return

        if command.command == "interact":
            target = str(params.get("target") or "")
            if target == "forbidden_zone":
                raise RuntimeError("interaction_blocked")
            self._state.status = f"interacting:{target}"
            return

        if command.command == "grasp":
            obj = str(params.get("object_id") or "")
            if obj == "":
                raise ValueError("object_id_empty")
            self._state.held_object = obj
            self._state.status = f"holding:{obj}"
            return

        raise ValueError(f"unsupported_command: {command.command}")
