from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_kernel.kernel import AgentKernel
from agent_kernel.schemas import AgentState, Task, WorkerResult
from agentlib.runtime_engine import RuntimeEngine
from agentlib.task_run import TaskRunRecorder, TaskRunStep


class _SequenceWorker:
    def __init__(self, results: list[WorkerResult]):
        self._results = list(results)
        self.calls = 0

    def execute(self, task: Task) -> WorkerResult:
        idx = min(self.calls, len(self._results) - 1)
        self.calls += 1
        return self._results[idx]

    @staticmethod
    def has_tool(tool_name: str) -> bool:
        return True

    @staticmethod
    def get_tool_schema(tool_name: str) -> dict:
        return {"required": []}


def test_task_run_lifecycle_writes_expected_files_and_fields(tmp_path) -> None:
    rec = TaskRunRecorder(str(tmp_path))
    run = rec.start_run(goal="ship MVP", plan=[{"task_id": "t1", "kind": "code_task"}])
    rec.append_step(
        run,
        TaskRunStep(
            step_id="s0001",
            ts_start=1.0,
            ts_end=1.2,
            duration_ms=200,
            input_payload={"goal": "ship MVP"},
            tool_calls=[{"tool_name": "code_task", "duration_ms": 5}],
            output={"ok": 1},
            status="ok",
        ),
    )
    rec.finalize(run, status="done")

    meta_path = tmp_path / f"{run.run_id}.json"
    steps_path = tmp_path / f"{run.run_id}.steps.jsonl"
    assert meta_path.exists()
    assert steps_path.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["goal"] == "ship MVP"
    assert meta["status"] == "done"
    assert isinstance(meta["steps"], list) and len(meta["steps"]) == 1


def test_tracing_write_failure_is_swallowed_in_runtime_step_recording(monkeypatch) -> None:
    e = RuntimeEngine()
    e._task_run_start("test goal")

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(e._task_run_recorder, "append_step", _boom)

    # Should not raise even if append_step persistence fails.
    e._task_run_record_step(ts_start=1.0, ts_end=1.1, trace_events=[])


def test_emit_reply_executes_three_actuation_channels_and_records_receipts(tmp_path, monkeypatch) -> None:
    receipt_log = tmp_path / "actuation_receipts.jsonl"
    monkeypatch.setenv("ACTUATION_RECEIPT_LOG_PATH", str(receipt_log))
    e = RuntimeEngine()
    e.speech_cfg.enabled_tts = False

    e._emit_reply(msg_id=None, reply_text="hello world", idle_tag=False, structured=False)

    assert receipt_log.exists()
    rows = [json.loads(x) for x in receipt_log.read_text(encoding="utf-8").splitlines() if x.strip()]
    channels = [str(r.get("channel") or "") for r in rows]
    assert "dialogue" in channels
    assert "interaction" in channels
    assert "scene_effect" in channels
    for row in rows:
        assert "action_id" in row
        assert "status" in row
        assert "success" in row



def test_retryable_error_retries_until_success() -> None:
    worker = _SequenceWorker(
        [
            WorkerResult(ok=False, error="timeout while invoking tool"),
            WorkerResult(ok=True, output={"summary": "ok"}),
        ]
    )
    kernel = AgentKernel(worker=worker)
    state = AgentState(
        goal="do work",
        tasks=[
            Task(
                task_id="t1",
                kind="code_task",
                description="run once",
                status="ready",
                input_payload={"retry_policy": {"max_attempts": 3}},
            )
        ],
        budget_steps_max=5,
    )

    kernel.run_step(state=state, checkpoint_path="")
    assert state.tasks[0].status == "ready"
    assert state.tasks[0].retries == 1

    kernel.run_step(state=state, checkpoint_path="")
    assert state.tasks[0].status == "done"
    assert worker.calls == 2


def test_non_retryable_error_does_not_retry() -> None:
    worker = _SequenceWorker([WorkerResult(ok=False, error="permission denied writing file")])
    kernel = AgentKernel(worker=worker)
    state = AgentState(
        goal="do work",
        tasks=[Task(task_id="t1", kind="code_task", description="run once", status="ready")],
        budget_steps_max=3,
    )

    kernel.run_step(state=state, checkpoint_path="")

    assert state.tasks[0].status == "blocked"
    assert state.status == "waiting_user"
    assert state.tasks[0].retries == 0
    assert worker.calls == 1
