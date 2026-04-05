from __future__ import annotations

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "agentlib" / "autonomy" / "actuation" / "interaction_executor.py"
spec = importlib.util.spec_from_file_location("interaction_executor_test_module", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"failed to load module: {MODULE_PATH}")
mod = importlib.util.module_from_spec(spec)
sys.modules["interaction_executor_test_module"] = mod
spec.loader.exec_module(mod)

DecisionContext = mod.DecisionContext
DecisionThresholds = mod.DecisionThresholds
InteractionExecutor = mod.InteractionExecutor


def test_policy_priority_safety_first() -> None:
    ex = InteractionExecutor(
        decision_thresholds=DecisionThresholds(
            safety_risk_threshold=0.70,
            task_blocking_threshold=0.55,
            flow_pressure_threshold=0.50,
        )
    )
    summary = ex.decide_strategy(
        DecisionContext(
            safety_risk=0.92,
            task_blocking=0.90,
            flow_pressure=0.80,
            expressive_gain=0.95,
        )
    )
    assert summary.strategy == "safety"
    assert "安全风险较高" in summary.reason


def test_policy_priority_task_before_flow() -> None:
    ex = InteractionExecutor(
        decision_thresholds=DecisionThresholds(
            safety_risk_threshold=0.70,
            task_blocking_threshold=0.55,
            flow_pressure_threshold=0.50,
        )
    )
    summary = ex.decide_strategy(
        DecisionContext(
            safety_risk=0.20,
            task_blocking=0.72,
            flow_pressure=0.86,
            expressive_gain=0.10,
        )
    )
    assert summary.strategy == "task_completion"
    assert "任务阻塞度高" in summary.reason


def test_policy_priority_flow_before_expressive() -> None:
    ex = InteractionExecutor(
        decision_thresholds=DecisionThresholds(
            safety_risk_threshold=0.70,
            task_blocking_threshold=0.55,
            flow_pressure_threshold=0.50,
        )
    )
    summary = ex.decide_strategy(
        DecisionContext(
            safety_risk=0.10,
            task_blocking=0.20,
            flow_pressure=0.60,
            expressive_gain=0.90,
        )
    )
    assert summary.strategy == "interaction_smoothness"
    assert "交互压力较高" in summary.reason


def test_policy_regression_fixed_cases() -> None:
    ex = InteractionExecutor(
        decision_thresholds=DecisionThresholds(
            safety_risk_threshold=0.70,
            task_blocking_threshold=0.55,
            flow_pressure_threshold=0.50,
        )
    )
    cases = [
        (DecisionContext(safety_risk=0.71, task_blocking=0.10, flow_pressure=0.10), "safety"),
        (DecisionContext(safety_risk=0.30, task_blocking=0.56, flow_pressure=0.10), "task_completion"),
        (DecisionContext(safety_risk=0.30, task_blocking=0.30, flow_pressure=0.51), "interaction_smoothness"),
        (DecisionContext(safety_risk=0.30, task_blocking=0.30, flow_pressure=0.10, expressive_gain=0.2), "expressive_enrichment"),
    ]
    got = [ex.decide_strategy(ctx).strategy for ctx, _ in cases]
    expected = [want for _, want in cases]
    assert got == expected


def test_turn_has_full_perceive_decide_plan_execute_feedback() -> None:
    ex = InteractionExecutor()
    report = ex.run_turn(
        context=DecisionContext(
            safety_risk=0.2,
            task_blocking=0.6,
            flow_pressure=0.1,
            expressive_gain=0.2,
            user_intent="send reminder",
        ),
        target="regression-check",
    )
    assert report.phase_trace == ["perceive", "decision", "plan", "execute", "feedback"]
    assert isinstance(report.feedback.message, str)
    assert bool(report.feedback.message)


def test_decision_outputs_readable_reason() -> None:
    ex = InteractionExecutor()
    out = ex.decide_strategy(DecisionContext(safety_risk=0.85, task_blocking=0.9, flow_pressure=0.9))
    assert out.strategy == "safety"
    assert "优先" in out.reason


def test_safety_priority_higher_than_task_completion() -> None:
    ex = InteractionExecutor(
        decision_thresholds=DecisionThresholds(
            safety_risk_threshold=0.70,
            task_blocking_threshold=0.55,
            flow_pressure_threshold=0.50,
        )
    )
    out = ex.decide_strategy(
        DecisionContext(
            safety_risk=0.80,  # hit safety
            task_blocking=0.95,  # also hit task
            flow_pressure=0.90,
        )
    )
    assert out.strategy == "safety"


def test_same_input_repeat_5_times_strategy_is_stable() -> None:
    ex = InteractionExecutor()
    stability = ex.evaluate_strategy_stability(
        DecisionContext(
            safety_risk=0.1,
            task_blocking=0.62,
            flow_pressure=0.8,
            expressive_gain=0.9,
            user_intent="help me finish this",
        ),
        repeats=5,
    )
    assert stability["repeats"] == 5
    assert stability["drift_count"] == 0
    assert stability["drift_rate"] == 0.0
    assert stability["stable"] is True
