from __future__ import annotations

from agentlib.task_run import TaskRunRecorder, TaskRunStep, load_task_run_steps, load_task_runs


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
