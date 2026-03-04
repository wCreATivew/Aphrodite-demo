from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_run_trigger_demo_cli() -> None:
    root = Path(__file__).resolve().parents[2]
    cmd = [
        sys.executable,
        "cli/run_trigger_demo.py",
        "--query",
        "\u5f00\u59cbdebug",
    ]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True)
    assert "decision=trigger" in proc.stdout
    assert "selected=code_debug" in proc.stdout


def test_eval_trigger_engine_cli() -> None:
    root = Path(__file__).resolve().parents[2]
    report_path = root / "outputs" / "test_report.json"
    trace_path = root / "outputs" / "test_trace.jsonl"
    cmd = [
        sys.executable,
        "cli/eval_trigger_engine.py",
        "--dataset",
        "data/eval/eval_dataset.jsonl",
        "--save-report",
        str(report_path),
        "--save-trace",
        str(trace_path),
    ]
    subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True)
    assert report_path.exists()
    assert trace_path.exists()
