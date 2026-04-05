import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FUSION_PATH = ROOT / "agentlib" / "autonomy" / "perception" / "fusion.py"


def _load_fusion_module():
    spec = importlib.util.spec_from_file_location("perception_fusion_test_module", FUSION_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_all_four_modalities_can_be_normalized_to_unified_structure():
    module = _load_fusion_module()
    engine = module.PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 1.0,
                "source": "cam",
                "modality": "visual",
                "payload": {"state_key": "path", "state_label": "clear"},
                "confidence": 0.93,
                "noise_level": 0.07,
            },
            {
                "timestamp": 1.1,
                "source": "mic",
                "modality": "audio",
                "payload": {"state_key": "path", "state_label": "clear"},
                "confidence": 0.81,
                "noise_level": 0.1,
            },
            {
                "timestamp": 1.2,
                "source": "touch",
                "modality": "touch",
                "payload": {"state_key": "obstacle", "state_label": "none"},
                "confidence": 0.79,
                "noise_level": 0.16,
            },
            {
                "timestamp": 1.3,
                "source": "gas",
                "modality": "smell",
                "payload": {"state_key": "air", "state_label": "normal"},
                "confidence": 0.72,
                "noise_level": 0.21,
            },
        ]
    )

    modalities = {item["modality"] for item in snapshot["aligned_events"]}
    assert modalities == {"vision", "audio", "tactile", "olfactory"}
    assert snapshot["degraded"] is False
    assert snapshot["degradation_mode"] == "full"


def test_conflict_has_explicit_adjudication_result():
    module = _load_fusion_module()
    engine = module.PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 2.0,
                "source": "cam",
                "modality": "vision",
                "payload": {"state_key": "road", "state_label": "passable"},
                "confidence": 0.88,
                "noise_level": 0.09,
            },
            {
                "timestamp": 2.1,
                "source": "touch",
                "modality": "tactile",
                "payload": {"state_key": "road", "state_label": "blocked"},
                "confidence": 0.9,
                "noise_level": 0.14,
            },
        ]
    )

    assert snapshot["conflicts"][0]["state_key"] == "road"
    assert snapshot["conflicts"][0]["winner_modality"] == "vision"
    assert snapshot["summary"]["road"]["state_label"] == "passable"
    assert snapshot["arbitration_log"][0]["reason"] == "priority_rule"


def test_missing_modalities_degrade_without_crash():
    module = _load_fusion_module()
    engine = module.PerceptionFusionEngine()
    snapshot = engine.run_cycle(
        [
            {
                "timestamp": 3.0,
                "source": "cam",
                "modality": "vision",
                "payload": {"state_key": "npc", "state_label": "idle"},
                "confidence": 0.77,
                "noise_level": 0.11,
            }
        ]
    )

    assert snapshot["degraded"] is True
    assert snapshot["degradation_mode"] == "double_or_more_missing"
    assert snapshot["summary"]["npc"]["state_label"] == "idle"
    assert snapshot["brain_signal"]["confidence"] == 0.77


def test_three_replay_examples_emit_confidence_outputs():
    module = _load_fusion_module()
    engine = module.PerceptionFusionEngine()
    replay = [
        {
            "name": "sample_a",
            "frames": [
                {
                    "timestamp": 10.0,
                    "source": "cam",
                    "modality": "vision",
                    "payload": {"state_key": "door", "state_label": "open"},
                    "confidence": 0.92,
                    "noise_level": 0.05,
                },
                {
                    "timestamp": 10.1,
                    "source": "touch",
                    "modality": "tactile",
                    "payload": {"state_key": "door", "state_label": "blocked"},
                    "confidence": 0.84,
                    "noise_level": 0.1,
                },
            ],
        },
        {
            "name": "sample_b",
            "frames": [
                {
                    "timestamp": 11.0,
                    "source": "cam",
                    "modality": "vision",
                    "payload": {"state_key": "npc_mood", "state_label": "calm"},
                    "confidence": 0.73,
                    "noise_level": 0.13,
                },
                {
                    "timestamp": 11.1,
                    "source": "mic",
                    "modality": "audio",
                    "payload": {"state_key": "npc_mood", "state_label": "angry"},
                    "confidence": 0.79,
                    "noise_level": 0.16,
                },
            ],
        },
        {
            "name": "sample_c",
            "frames": [
                {
                    "timestamp": 12.0,
                    "source": "gas",
                    "modality": "olfactory",
                    "payload": {"state_key": "air", "state_label": "smoke"},
                    "confidence": 0.66,
                    "noise_level": 0.25,
                }
            ],
        },
    ]
    outputs = []
    for item in replay:
        snapshot = engine.run_cycle(item["frames"])
        outputs.append(
            {
                "name": item["name"],
                "brain_confidence": snapshot["brain_signal"]["confidence"],
                "degradation_mode": snapshot["degradation_mode"],
            }
        )

    assert len(outputs) == 3
    assert all(entry["brain_confidence"] >= 0.0 for entry in outputs)
    # easy-to-read assertion message if changed unexpectedly
    assert json.loads(json.dumps(outputs)) == outputs
