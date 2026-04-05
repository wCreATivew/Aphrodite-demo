from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIO_DIR = ROOT / "demos" / "scenarios"


@dataclass
class StepResult:
    scenario_id: str
    index: int
    event: str
    action: str
    success: bool
    degraded: bool


@dataclass
class PanelMetrics:
    event_throughput_eps: float
    action_success_rate: float
    degradation_count: int


class DemoRunner:
    def __init__(self, *, scenario_dir: Path, mock_injection: bool = True) -> None:
        self.scenario_dir = Path(scenario_dir)
        self.mock_injection = bool(mock_injection)

    def load_scenario(self, scenario_name: str) -> Dict[str, Any]:
        path = self.scenario_dir / f"{scenario_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"scenario not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def run(self, scenario_name: str) -> Dict[str, Any]:
        scenario = self.load_scenario(scenario_name)
        degrade_steps = {int(x) for x in list(scenario.get("degrade_steps") or [])}
        steps = list(scenario.get("steps") or [])
        if not steps:
            raise ValueError(f"scenario {scenario_name} has no steps")

        started = time.time()
        results: List[StepResult] = []
        for i, step in enumerate(steps, start=1):
            event = str(step.get("event") or "")
            action = str(step.get("action") or "")
            degraded = i in degrade_steps
            injected = dict(step.get("mock_perception") or {}) if self.mock_injection else {}
            success = self._execute_action(action=action, event=event, injected=injected, degraded=degraded)
            results.append(
                StepResult(
                    scenario_id=str(scenario.get("id") or scenario_name),
                    index=i,
                    event=event,
                    action=action,
                    success=success,
                    degraded=degraded,
                )
            )

        duration = max(time.time() - started, 0.001)
        panel = self._build_panel(results, duration)
        return {
            "scenario_id": str(scenario.get("id") or scenario_name),
            "scenario_name": str(scenario.get("name") or scenario_name),
            "goal": str(scenario.get("goal") or ""),
            "mock_injection": self.mock_injection,
            "duration_sec": round(duration, 3),
            "panel": {
                "event_throughput_eps": panel.event_throughput_eps,
                "action_success_rate": panel.action_success_rate,
                "degradation_count": panel.degradation_count,
            },
            "steps": [
                {
                    "index": r.index,
                    "event": r.event,
                    "action": r.action,
                    "success": r.success,
                    "degraded": r.degraded,
                }
                for r in results
            ],
        }

    @staticmethod
    def _execute_action(*, action: str, event: str, injected: Dict[str, Any], degraded: bool) -> bool:
        if not action or not event:
            return False
        if degraded and not injected:
            return False
        return True

    @staticmethod
    def _build_panel(results: List[StepResult], duration_sec: float) -> PanelMetrics:
        total = len(results)
        successes = len([r for r in results if r.success])
        degradations = len([r for r in results if r.degraded])
        throughput = float(total) / float(max(duration_sec, 0.001))
        success_rate = (float(successes) / float(total)) if total else 0.0
        return PanelMetrics(
            event_throughput_eps=round(throughput, 2),
            action_success_rate=round(success_rate, 4),
            degradation_count=degradations,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run polished demo scenarios with mock perception injection")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["all", "security_scene", "social_scene", "task_scene"],
        help="Scenario to run",
    )
    parser.add_argument(
        "--scenario-dir",
        default=str(DEFAULT_SCENARIO_DIR),
        help="Scenario directory",
    )
    parser.add_argument("--no-mock", action="store_true", help="Disable mock perception input injection")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument(
        "--save-report",
        default="",
        help="Optional output JSON path",
    )
    return parser.parse_args()


def _render_panel(name: str, run: Dict[str, Any]) -> str:
    panel = dict(run.get("panel") or {})
    return (
        f"[{name}] throughput={panel.get('event_throughput_eps')} eps | "
        f"success_rate={panel.get('action_success_rate'):.2%} | "
        f"degradations={panel.get('degradation_count')}"
    )


def main() -> int:
    args = parse_args()
    runner = DemoRunner(scenario_dir=Path(args.scenario_dir), mock_injection=not bool(args.no_mock))
    selected = [args.scenario] if args.scenario != "all" else ["security_scene", "social_scene", "task_scene"]

    runs = [runner.run(item) for item in selected]
    aggregate = {
        "total_scenarios": len(runs),
        "total_steps": sum(len(list(x.get("steps") or [])) for x in runs),
        "avg_success_rate": round(
            sum(float((x.get("panel") or {}).get("action_success_rate") or 0.0) for x in runs) / max(len(runs), 1),
            4,
        ),
        "degradation_count": sum(int((x.get("panel") or {}).get("degradation_count") or 0) for x in runs),
    }
    payload = {"runs": runs, "aggregate": aggregate}

    if args.save_report:
        out = Path(args.save_report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("=== Demo Metrics Panel (Minimal) ===")
        for run in runs:
            print(_render_panel(run.get("scenario_id", "unknown"), run))
        print(
            "aggregate:",
            f"scenarios={aggregate['total_scenarios']} steps={aggregate['total_steps']} "
            f"avg_success_rate={aggregate['avg_success_rate']:.2%} degradation_count={aggregate['degradation_count']}",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
