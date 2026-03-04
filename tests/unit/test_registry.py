from __future__ import annotations

from pathlib import Path

from semantic_trigger.registry import load_trigger_registry


def test_registry_loads_default_triggers() -> None:
    root = Path(__file__).resolve().parents[2]
    reg = load_trigger_registry(str(root / "data" / "triggers" / "default_triggers.yaml"))
    assert len(reg.triggers) >= 12
    assert len(reg.enabled_triggers()) >= 12
    assert reg.get("set_reminder") is not None
    assert reg.get("code_debug") is not None


def test_trigger_example_counts() -> None:
    root = Path(__file__).resolve().parents[2]
    reg = load_trigger_registry(str(root / "data" / "triggers" / "default_triggers.yaml"))
    for trig in reg.triggers:
        assert len(trig.positive_examples) >= 8
        assert len(trig.negative_examples) >= 8
