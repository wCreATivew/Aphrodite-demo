from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Set

from .schemas import ExecutableSubgoal


class ToolCapabilityRegistry(Protocol):
    def has_tool(self, tool_name: str) -> bool: ...
    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]: ...


@dataclass
class CompileIssue:
    code: str
    subgoal_id: str
    message: str
    severity: str = "error"
    hint: str = ""


_SUPPORTED_PRECONDITION_OPS = {
    "input_present",
    "dependency_done",
    "tool_available",
    "env_flag",
}

_SUPPORTED_SUCCESS_OPS = {
    "tool_output_contains",
    "artifact_exists",
    "field_equals",
    "exit_code_is",
    "predicate_ref",
}


def plan_compile_check(
    *,
    subgoals: Iterable[ExecutableSubgoal],
    tools: ToolCapabilityRegistry,
) -> List[CompileIssue]:
    nodes = list(subgoals)
    issues: List[CompileIssue] = []
    id_map = {s.id: s for s in nodes}

    # Tool registration and schema/input checks.
    for s in nodes:
        if not tools.has_tool(s.tool_name):
            issues.append(
                CompileIssue(
                    code="tool_not_registered",
                    subgoal_id=s.id,
                    message=f"tool '{s.tool_name}' is not registered",
                    hint="register tool or fix tool_name",
                )
            )
            continue
        schema = dict(tools.get_tool_schema(s.tool_name) or {})
        required = [str(x) for x in list(schema.get("required") or []) if str(x).strip()]
        missing = [k for k in required if k not in dict(s.inputs or {})]
        if missing:
            issues.append(
                CompileIssue(
                    code="input_schema_incomplete",
                    subgoal_id=s.id,
                    message=f"missing required inputs: {missing}",
                    hint="fill required fields in subgoal.inputs",
                )
            )
        if s.retry_policy is None:
            issues.append(
                CompileIssue(
                    code="retry_policy_missing",
                    subgoal_id=s.id,
                    message="retry_policy is required",
                    hint="set retry_policy with max_attempts/backoff/base_delay_ms",
                )
            )

    # Dependency checks (unknown + cycle).
    for s in nodes:
        for dep in s.dependencies:
            if dep not in id_map:
                issues.append(
                    CompileIssue(
                        code="dependency_not_found",
                        subgoal_id=s.id,
                        message=f"dependency '{dep}' not found",
                        hint="fix dependencies or add missing node",
                    )
                )
    cycle_nodes = _find_cycle_nodes(nodes)
    for subgoal_id in cycle_nodes:
        issues.append(
            CompileIssue(
                code="dependency_cycle",
                subgoal_id=subgoal_id,
                message="dependencies must form a DAG",
                hint="remove cyclic dependencies",
            )
        )

    # Preconditions and success criteria executability.
    for s in nodes:
        for pred in list(s.preconditions or []):
            if pred.op not in _SUPPORTED_PRECONDITION_OPS:
                issues.append(
                    CompileIssue(
                        code="precondition_not_evaluable",
                        subgoal_id=s.id,
                        message=f"unsupported precondition op: {pred.op}",
                        hint=f"supported: {sorted(_SUPPORTED_PRECONDITION_OPS)}",
                    )
                )
        for crit in list(s.success_criteria or []):
            if crit.op not in _SUPPORTED_SUCCESS_OPS:
                issues.append(
                    CompileIssue(
                        code="success_criteria_not_executable",
                        subgoal_id=s.id,
                        message=f"unsupported success op: {crit.op}",
                        hint=f"supported: {sorted(_SUPPORTED_SUCCESS_OPS)}",
                    )
                )

    # Fallback loop.
    fallback_cycles = _find_fallback_cycles(nodes)
    for subgoal_id in fallback_cycles:
        issues.append(
            CompileIssue(
                code="fallback_self_loop",
                subgoal_id=subgoal_id,
                message="fallback graph contains self/indirect loop",
                hint="ensure fallback path cannot return to same node chain",
            )
        )

    return issues


def action_plan_gate_check(
    *,
    subgoal: ExecutableSubgoal,
    tools: ToolCapabilityRegistry,
    budget_used: Optional[int] = None,
    budget_max: Optional[int] = None,
    require_success_criteria: bool = True,
) -> List[CompileIssue]:
    issues = plan_compile_check(subgoals=[subgoal], tools=tools)
    if require_success_criteria and not list(subgoal.success_criteria or []):
        issues.append(
            CompileIssue(
                code="success_criteria_missing",
                subgoal_id=str(subgoal.id),
                message="success_criteria is required before execution",
                hint="set machine-checkable success_criteria",
            )
        )
    if budget_used is not None and budget_max is not None:
        used = int(budget_used or 0)
        maxv = int(budget_max or 0)
        if maxv > 0 and used >= maxv:
            issues.append(
                CompileIssue(
                    code="budget_exhausted",
                    subgoal_id=str(subgoal.id),
                    message=f"budget exhausted: used={used}, max={maxv}",
                    hint="increase budget or reduce action cost",
                )
            )
    return issues


def _find_cycle_nodes(nodes: List[ExecutableSubgoal]) -> Set[str]:
    graph = {n.id: list(n.dependencies or []) for n in nodes}
    visiting: Set[str] = set()
    visited: Set[str] = set()
    in_cycle: Set[str] = set()

    def dfs(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            in_cycle.add(node_id)
            return
        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep not in graph:
                continue
            if dep in visiting:
                in_cycle.add(node_id)
                in_cycle.add(dep)
                continue
            dfs(dep)
            if dep in in_cycle:
                in_cycle.add(node_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        if node_id not in visited:
            dfs(node_id)
    return in_cycle


def _find_fallback_cycles(nodes: List[ExecutableSubgoal]) -> Set[str]:
    edges: Dict[str, str] = {}
    for n in nodes:
        target = _fallback_target(n.fallback)
        if target:
            edges[n.id] = target
    cycle_nodes: Set[str] = set()
    for start in list(edges.keys()):
        seen: Set[str] = set()
        cur: Optional[str] = start
        while cur and cur in edges:
            if cur in seen:
                cycle_nodes.update(seen)
                break
            seen.add(cur)
            cur = edges.get(cur)
    return cycle_nodes


def _fallback_target(fallback: Dict[str, Any]) -> str:
    if not isinstance(fallback, dict):
        return ""
    for key in ("on_failure", "target", "fallback_to"):
        value = str(fallback.get(key) or "").strip()
        if value:
            return value
    return ""
