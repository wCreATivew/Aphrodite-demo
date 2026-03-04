from __future__ import annotations

import os

from agentlib.runtime_engine import RuntimeEngine


def test_selfdrive_start_creates_task_run_meta(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    e = RuntimeEngine()
    out = e._execute_selfdrive_control_dsl(
        {"command": "START_SELFDRIVE", "args": {"goal": "实现最小可运行代理链路"}},
        source_text="实现最小可运行代理链路",
    )
    assert isinstance(out, str)
    assert "[selfdrive] started" in out

    task_run_dir = tmp_path / "outputs" / "task_runs"
    assert task_run_dir.exists()
    meta_files = [x for x in os.listdir(task_run_dir) if x.endswith('.json') and not x.endswith('.steps.json')]
    assert meta_files
