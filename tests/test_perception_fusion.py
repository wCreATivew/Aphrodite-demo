import json
from pathlib import Path

from agentlib.autonomy import Goal, InMemoryStateStore, InMemoryToolRegistry, Orchestrator
from agentlib.autonomy.mock_components import MockEvaluator, MockExecutor, MockPlanner, MockReflector
from agentlib.autonomy.perception import PerceptionFusionEngine


def test_fusion_handles_missing_modalities_as_degraded_mode():
    engine = PerceptionFusionEngine()
    snapshot = engine.run_cycle([])

    assert snapshot["degraded"] is True
    assert snapshot["aligned_events"] == []
    assert snapshot["conflicts"] == []


def test_fusion_detects_conflicts_and_penalizes_confidence():
    engine = PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 100.0,
                "source": "mock_camera",
                "modality": "vision",
                "payload": {"state_key": "door", "state_label": "open"},
                "confidence": 0.9,
                "noise_level": 0.1,
            },
            {
                "timestamp": 100.2,
                "source": "mock_touch",
                "modality": "tactile",
                "payload": {"state_key": "door", "state_label": "blocked"},
                "confidence": 0.8,
                "noise_level": 0.15,
            },
        ]
    )

    assert snapshot["conflicts"]
    labels = snapshot["conflicts"][0]["labels"]
    assert "open" in labels and "blocked" in labels
    assert snapshot["conflicts"][0]["winner_modality"] == "vision"
    assert snapshot["summary"]["door"]["best_modality"] == "vision"
    assert snapshot["aligned_events"][1]["confidence"] < 0.8
    assert snapshot["arbitration_log"]


def test_orchestrator_runs_perception_before_brain_execution_cycle():
    store = InMemoryStateStore()
    tools = InMemoryToolRegistry()
    tools.register("mock.fail", lambda payload: "fail")
    tools.register("mock.success", lambda payload: "ok")

    orchestrator = Orchestrator(
        planner=MockPlanner(),
        executor=MockExecutor(),
        evaluator=MockEvaluator(),
        reflector=MockReflector(),
        tools=tools,
        store=store,
    )

    result = orchestrator.run_goal(Goal(objective="test perception-first"), max_cycles=3)

    assert result["cycles"] >= 1
    assert store.latest_perception
    stages = [trace.stage for trace in store.traces]
    assert "perception" in stages
    assert stages.index("perception") < stages.index("executing")


def test_fusion_partial_modalities_runs_without_error():
    engine = PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 200.0,
                "source": "mock_camera",
                "modality": "vision",
                "payload": {"state_key": "door", "state_label": "open"},
                "confidence": 0.92,
                "noise_level": 0.08,
            }
        ]
    )

    assert snapshot["degraded"] is True
    assert snapshot["degradation_mode"] == "double_or_more_missing"
    assert len(snapshot["aligned_events"]) == 1
    assert snapshot["modality_status"]["vision"]["present"] is True
    assert snapshot["conflicts"] == []
    assert snapshot["brain_signal"]["confidence"] > 0.9


def test_fusion_outputs_unified_confidence_and_uncertainty_for_brain():
    engine = PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 300.0,
                "source": "mock_camera",
                "modality": "vision",
                "payload": {"state_key": "npc_mood", "state_label": "neutral"},
                "confidence": 0.75,
                "noise_level": 0.12,
            },
            {
                "timestamp": 300.1,
                "source": "mock_audio",
                "modality": "audio",
                "payload": {"state_key": "npc_mood", "state_label": "neutral"},
                "confidence": 0.7,
                "noise_level": 0.1,
            },
        ]
    )

    assert snapshot["summary"]["npc_mood"]["uncertainty"] >= 0.0
    assert snapshot["summary"]["npc_mood"]["uncertainty_label"] in {"low", "medium", "high", "critical"}
    assert snapshot["brain_signal"]["confidence"] > 0.0
    assert snapshot["brain_signal"]["uncertainty_label"] in {"low", "medium", "high", "critical"}


def test_fusion_conflict_replay_dataset_has_three_groups():
    fixture_path = Path(__file__).parent / "fixtures" / "perception_conflict_replays.json"
    replay_groups = json.loads(fixture_path.read_text(encoding="utf-8"))
    engine = PerceptionFusionEngine()

    assert len(replay_groups) == 3
    for replay in replay_groups:
        snapshot = engine.run_cycle(replay["frames"])
        assert snapshot["conflicts"], f"expected conflict in replay group: {replay['name']}"
        assert snapshot["arbitration_log"], f"missing arbitration log in replay group: {replay['name']}"
        assert snapshot["brain_signal"]["confidence"] > 0.0


class _BrokenAdapter:
    modality = "audio"

    def read(self):
        raise RuntimeError("simulated audio offline")


def test_orchestrator_tolerates_missing_or_failed_modalities():
    store = InMemoryStateStore()
    tools = InMemoryToolRegistry()
    tools.register("mock.fail", lambda payload: "fail")
    tools.register("mock.success", lambda payload: "ok")

    orchestrator = Orchestrator(
        planner=MockPlanner(),
        executor=MockExecutor(),
        evaluator=MockEvaluator(),
        reflector=MockReflector(),
        tools=tools,
        store=store,
    )
    orchestrator._adapters = [_BrokenAdapter()]

    result = orchestrator.run_goal(Goal(objective="degraded modalities"), max_cycles=1)

    assert result["cycles"] == 1
    assert store.latest_perception["degraded"] is True
    assert any(t.stage == "perception" for t in store.traces)
