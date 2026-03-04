from __future__ import annotations

import json

from agentlib.task_run import (
    TaskRunRecorder,
    TaskRunStep,
    export_task_run_report,
    load_task_run_steps,
    load_task_runs,
)


def test_task_run_recorder_writes_meta_and_steps(tmp_path) -> None:
    rec = TaskRunRecorder(str(tmp_path))
    run = rec.start_run(goal="repair planner", plan=[{"task_id": "t1", "kind": "plan_goal"}])
    rec.append_step(
        run,
        TaskRunStep(
            step_id="s0001",
            ts_start=1.0,
            ts_end=2.0,
            duration_ms=1000,
            input_payload={"goal": "repair planner"},
            tool_calls=[{"tool_name": "plan_goal", "duration_ms": 21}],
            output={"ok": 1},
            error="",
            status="ok",
        ),
    )
    rec.finalize(run, status="done")

    runs = load_task_runs(str(tmp_path))
    assert len(runs) == 1
    assert runs[0].run_id == run.run_id
    assert runs[0].status == "done"
    assert len(runs[0].steps) == 1

    steps = load_task_run_steps(run.run_id, str(tmp_path))
    assert len(steps) == 1
    assert steps[0].step_id == "s0001"
    assert steps[0].tool_calls[0]["tool_name"] == "plan_goal"


def test_export_task_run_report_writes_json_and_markdown(tmp_path) -> None:
    rec = TaskRunRecorder(str(tmp_path))
    run = rec.start_run(goal="repair planner")
    rec.append_step(
        run,
        TaskRunStep(
            step_id="s0001",
            ts_start=10.0,
            ts_end=10.5,
            duration_ms=500,
            output={"summary": "first"},
            status="ok",
        ),
    )
    rec.append_step(
        run,
        TaskRunStep(
            step_id="s0002",
            ts_start=11.0,
            ts_end=12.0,
            duration_ms=1000,
            output={"selected_expert": "planner"},
            error="boom",
            status="error",
        ),
    )
    rec.finalize(run, status="failed")

    paths = export_task_run_report(run.run_id, base_dir=str(tmp_path), out_dir=str(tmp_path / "reports"))
    json_path = tmp_path / "reports" / f"{run.run_id}.report.json"
    md_path = tmp_path / "reports" / f"{run.run_id}.report.md"
    assert paths["json_path"] == str(json_path)
    assert paths["markdown_path"] == str(md_path)
    assert json_path.exists()
    assert md_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["step_count"] == 2
    assert report["duration_ms"] == 2000
    assert len(report["failed_steps"]) == 1
    assert "failed" in report["status"]

    md = md_path.read_text(encoding="utf-8")
    assert "## Timeline" in md
    assert "## Errors" in md
    assert "s0002" in md
