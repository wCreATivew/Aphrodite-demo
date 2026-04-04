from __future__ import annotations

from typing import Callable, Dict, List

from .models import (
    ExecutionRecord,
    MOTOR_CODE_ACTION_NOT_FOUND,
    MOTOR_CODE_COMMAND_MISMATCH,
    MOTOR_CODE_FAILED,
    MOTOR_CODE_OK,
    MotorCommand,
    MotorCommandResult,
)


class InMemoryToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Callable[[str], str]] = {}
        self._schemas: Dict[str, Dict[str, object]] = {}
        self._shell_actions: Dict[str, Callable[[MotorCommand], ExecutionRecord]] = {}
        self._shell_schemas: Dict[str, Dict[str, object]] = {}

    def register(self, name: str, fn: Callable[[str], str], schema: Dict[str, object] | None = None) -> None:
        k = str(name)
        self._tools[k] = fn
        self._schemas[k] = dict(schema or {"required": []})

    def has(self, name: str) -> bool:
        return str(name) in self._tools

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())

    def run(self, name: str, payload: str) -> str:
        tool = self._tools.get(str(name))
        if tool is None:
            raise KeyError(f"tool_not_found: {name}")
        # TODO: enforce policy guards/sandbox contracts here for real tools.
        return str(tool(str(payload)))

    def get_tool_schema(self, name: str) -> Dict[str, object]:
        return dict(self._schemas.get(str(name), {"required": []}))

    def register_shell_action(
        self,
        name: str,
        fn: Callable[[MotorCommand], ExecutionRecord],
        schema: Dict[str, object] | None = None,
    ) -> None:
        k = str(name)
        self._shell_actions[k] = fn
        self._shell_schemas[k] = dict(schema or {"required": ["command", "command_id"]})

    def has_shell_action(self, name: str) -> bool:
        return str(name) in self._shell_actions

    def list_shell_actions(self) -> List[str]:
        return sorted(self._shell_actions.keys())

    def run_shell_action(self, name: str, command: MotorCommand) -> ExecutionRecord:
        action = self._shell_actions.get(str(name))
        if action is None:
            raise KeyError(f"shell_action_not_found: {name}")
        return action(command)

    def dispatch_motor_command(self, name: str, command: MotorCommand) -> MotorCommandResult:
        try:
            execution = self.run_shell_action(name, command)
        except KeyError as e:
            return MotorCommandResult(code=MOTOR_CODE_ACTION_NOT_FOUND, success=False, error=f"{type(e).__name__}: {e}")
        except ValueError as e:
            # e.g. command mismatch or schema-level validation from action wrapper
            return MotorCommandResult(code=MOTOR_CODE_COMMAND_MISMATCH, success=False, error=f"{type(e).__name__}: {e}")
        except Exception as e:
            return MotorCommandResult(code=MOTOR_CODE_FAILED, success=False, error=f"{type(e).__name__}: {e}")

        if execution.success:
            return MotorCommandResult(code=MOTOR_CODE_OK, success=True, execution=execution)
        return MotorCommandResult(code=MOTOR_CODE_FAILED, success=False, execution=execution, error=execution.error)

    def get_shell_action_schema(self, name: str) -> Dict[str, object]:
        return dict(self._shell_schemas.get(str(name), {"required": ["command", "command_id"]}))

    def register_shell_capabilities(self, adapter: object) -> None:
        getter = getattr(adapter, "get_actuator_capabilities", None)
        runner = getattr(adapter, "execute_motor_command", None)
        if not callable(getter) or not callable(runner):
            raise TypeError("adapter must expose get_actuator_capabilities() and execute_motor_command()")

        for capability in list(getter()):
            name = str(getattr(capability, "name", "")).strip()
            command_name = str(getattr(capability, "command", "")).strip()
            if not name or not command_name:
                continue

            def _run(command: MotorCommand, expected: str = command_name) -> ExecutionRecord:
                if command.command != expected:
                    raise ValueError(f"command_mismatch: expected={expected}, got={command.command}")
                return runner(command)

            schema = {
                "required": ["command", "command_id", *list(getattr(capability, "required_params", []) or [])],
                "optional": list(getattr(capability, "optional_params", []) or []),
                "supports_rollback": bool(getattr(capability, "supports_rollback", False)),
            }
            self.register_shell_action(name, _run, schema=schema)
