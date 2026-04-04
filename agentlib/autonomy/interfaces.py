from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Protocol, Tuple

from .models import (
    ActuatorCapability,
    ExecutionRecord,
    Goal,
    MotorCommand,
    MotorCommandResult,
    ReflectionRecord,
    ShellState,
    Task,
)

if TYPE_CHECKING:
    from .store import InMemoryStateStore


class ToolRegistry(Protocol):
    def register(self, name: str, fn: Callable[[str], str], schema: Dict[str, object] | None = None) -> None: ...
    def run(self, name: str, payload: str) -> str: ...
    def has(self, name: str) -> bool: ...
    def list_tools(self) -> List[str]: ...
    def get_tool_schema(self, name: str) -> Dict[str, object]: ...


class ShellAdapter(Protocol):
    def observe_shell_state(self) -> ShellState: ...
    def execute_motor_command(self, command: MotorCommand) -> ExecutionRecord: ...
    def get_actuator_capabilities(self) -> List[ActuatorCapability]: ...


class ShellActionRegistry(Protocol):
    def register_shell_action(
        self,
        name: str,
        fn: Callable[[MotorCommand], ExecutionRecord],
        schema: Dict[str, object] | None = None,
    ) -> None: ...

    def run_shell_action(self, name: str, command: MotorCommand) -> ExecutionRecord: ...
    def dispatch_motor_command(self, name: str, command: MotorCommand) -> MotorCommandResult: ...
    def has_shell_action(self, name: str) -> bool: ...
    def list_shell_actions(self) -> List[str]: ...
    def get_shell_action_schema(self, name: str) -> Dict[str, object]: ...


class Planner(Protocol):
    def plan(self, goal: Goal, store: "InMemoryStateStore") -> List[Task]: ...

    def replan(
        self, goal: Goal, store: "InMemoryStateStore", reflection: ReflectionRecord
    ) -> List[Task]: ...


class Executor(Protocol):
    def execute(
        self, goal: Goal, task: Task, tools: ToolRegistry, store: "InMemoryStateStore"
    ) -> ExecutionRecord: ...


class Evaluator(Protocol):
    def evaluate(
        self,
        goal: Goal,
        task: Task,
        execution: ExecutionRecord,
        store: "InMemoryStateStore",
    ) -> Tuple[bool, str]: ...


class Reflector(Protocol):
    def reflect(
        self,
        goal: Goal,
        task: Task,
        execution: ExecutionRecord,
        passed: bool,
        evaluation_note: str,
        store: "InMemoryStateStore",
    ) -> ReflectionRecord: ...
