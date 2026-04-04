from __future__ import annotations

from agentlib.autonomy.models import (
    MOTOR_CODE_FAILED,
    MOTOR_CODE_OK,
    MotorCommand,
)
from agentlib.autonomy.shell_adapters import MockShellAdapter
from agentlib.autonomy.tool_registry import InMemoryToolRegistry


def test_shell_capability_discovery_and_registry_split() -> None:
    adapter = MockShellAdapter()
    tools = InMemoryToolRegistry()

    tools.register("classic.echo", lambda payload: payload)
    tools.register_shell_capabilities(adapter)

    shell_actions = tools.list_shell_actions()
    assert "move" in shell_actions
    assert "interact" in shell_actions
    assert tools.has("classic.echo")
    assert not tools.has("move")


def test_motor_command_idempotency_and_rollback() -> None:
    adapter = MockShellAdapter()

    move_cmd = MotorCommand(
        command="move",
        params={"dx": 2, "dy": -1},
        command_id="cmd-1",
        idempotency_key="move-1",
    )
    first = adapter.execute_motor_command(move_cmd)
    second = adapter.execute_motor_command(move_cmd)

    assert first.success is True
    assert second.success is True
    assert second.metadata.get("idempotent_replay") is True

    state_after_move = adapter.observe_shell_state()
    assert state_after_move.pose["x"] == 2
    assert state_after_move.pose["y"] == -1

    failing = MotorCommand(
        command="interact",
        params={"target": "forbidden_zone"},
        command_id="cmd-2",
    )
    failed = adapter.execute_motor_command(failing)
    assert failed.success is False
    assert failed.metadata.get("rolled_back") is True

    state_after_fail = adapter.observe_shell_state()
    assert state_after_fail.pose == state_after_move.pose
    assert state_after_fail.status == state_after_move.status


def test_can_dispatch_two_shell_actions_and_return_codes() -> None:
    adapter = MockShellAdapter()
    tools = InMemoryToolRegistry()
    tools.register_shell_capabilities(adapter)

    move_result = tools.dispatch_motor_command(
        "move",
        MotorCommand(command="move", params={"dx": 1, "dy": 1}, command_id="move-2"),
    )
    assert move_result.code == MOTOR_CODE_OK
    assert move_result.success is True

    grasp_result = tools.dispatch_motor_command(
        "grasp",
        MotorCommand(command="grasp", params={"object_id": "cube-1"}, command_id="grasp-1"),
    )
    assert grasp_result.code == MOTOR_CODE_OK
    assert grasp_result.success is True

    fail_result = tools.dispatch_motor_command(
        "interact",
        MotorCommand(command="interact", params={"target": "forbidden_zone"}, command_id="int-1"),
    )
    assert fail_result.code == MOTOR_CODE_FAILED
    assert fail_result.success is False
