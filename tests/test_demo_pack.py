from __future__ import annotations

from pathlib import Path

from cli.run_demo_pack import DemoRunner


def test_all_scenarios_have_expected_panel_metrics() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = DemoRunner(scenario_dir=root / "demos" / "scenarios", mock_injection=True)

    for scenario in ("security_scene", "social_scene", "task_scene"):
        result = runner.run(scenario)
        panel = dict(result.get("panel") or {})
        assert panel["action_success_rate"] == 1.0
        assert panel["degradation_count"] == 1
        assert float(panel["event_throughput_eps"]) > 0.0


def test_no_mock_mode_can_fail_degraded_step() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = DemoRunner(scenario_dir=root / "demos" / "scenarios", mock_injection=False)

    result = runner.run("security_scene")
    steps = list(result.get("steps") or [])
    failed = [s for s in steps if not bool(s.get("success"))]
    assert failed, "without mock injection at least one degraded step should fail"
