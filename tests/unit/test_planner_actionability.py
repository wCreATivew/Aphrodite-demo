from __future__ import annotations

from agent_kernel.adapters import GLM5PlannerAdapter


def test_compile_rejects_non_actionable_intent() -> None:
    ad = GLM5PlannerAdapter(client=lambda **_: {
        "generated_subgoals": [
            {
                "subgoal_id": "sg1",
                "intent": "brainstorm ideas for implementation",
                "executor_type": "code_task",
                "tool_name": "code_task",
                "inputs": {"instruction": "do something"},
                "success_criteria": [{"op": "predicate_ref", "args": {"name": "worker_ok"}}],
            }
        ]
    })
    compiled = ad.plan(goal="x", context={})
    issues = list(compiled.get("plan_compile_issues") or [])
    assert any("non_actionable_intent" in str(x) for x in issues)


def test_compile_rejects_code_task_without_instruction() -> None:
    ad = GLM5PlannerAdapter(client=lambda **_: {
        "generated_subgoals": [
            {
                "subgoal_id": "sg2",
                "intent": "implement parser for trigger output",
                "executor_type": "code_task",
                "tool_name": "code_task",
                "inputs": {},
                "success_criteria": [{"op": "predicate_ref", "args": {"name": "worker_ok"}}],
            }
        ]
    })
    compiled = ad.plan(goal="x", context={})
    issues = list(compiled.get("plan_compile_issues") or [])
    assert any("missing_instruction" in str(x) for x in issues)
