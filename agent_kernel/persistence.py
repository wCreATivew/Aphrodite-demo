from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from .schemas import (
    AgentState,
    RUN_STATUS_PENDING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SUCCESS,
    StepLog,
    TaskRun,
)

DEFAULT_RUNS_DIR = Path("monitor") / "runs"


# Run layout example:
# monitor/runs/<run_id>/
#   task_run.json      -> TaskRun metadata (goal/status/timestamps/summary/error/metadata)
#   steps.jsonl        -> one StepLog JSON object per line, append-only


def save_state_json(state: AgentState, path: str) -> None:
    """Persist AgentState snapshot to a JSON file."""
    p = Path(path)
    if p.parent and (not p.parent.exists()):
        p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_state_json(path: str) -> AgentState:
    """Load AgentState from JSON snapshot."""
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    return AgentState.from_dict(payload)


def create_run(
    goal: str,
    *,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> TaskRun:
    """Create a new TaskRun and persist initial metadata."""
    resolved_run_id = str(run_id or _new_run_id())
    now = float(time.time())
    run = TaskRun(
        run_id=resolved_run_id,
        goal=str(goal or "").strip(),
        status=RUN_STATUS_RUNNING,
        created_at=now,
        started_at=now,
        metadata=dict(metadata or {}),
    )
    _write_run_meta(run, runs_dir)
    return run


def append_step(
    run_id: str,
    step_index: int,
    component: str,
    action: str,
    *,
    step_id: Optional[str] = None,
    input_preview: str = "",
    output_preview: str = "",
    status: str = RUN_STATUS_SUCCESS,
    error: Optional[str] = None,
    started_at: Optional[float] = None,
    finished_at: Optional[float] = None,
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> StepLog:
    """Append one step event to monitor/runs/<run_id>/steps.jsonl."""
    ts_start = float(started_at if started_at is not None else time.time())
    ts_end = float(finished_at if finished_at is not None else ts_start)
    computed_duration_ms = duration_ms
    if computed_duration_ms is None:
        computed_duration_ms = max(0, int((ts_end - ts_start) * 1000))
    step = StepLog(
        step_id=str(step_id or f"{run_id}-s{int(step_index):04d}"),
        run_id=str(run_id),
        step_index=int(step_index),
        component=str(component or ""),
        action=str(action or ""),
        input_preview=str(input_preview or ""),
        output_preview=str(output_preview or ""),
        status=str(status or RUN_STATUS_PENDING),
        error=(None if error is None else str(error)),
        started_at=ts_start,
        finished_at=ts_end,
        duration_ms=int(computed_duration_ms),
        metadata=dict(metadata or {}),
    )
    _append_step_jsonl(step, runs_dir)
    return step


def finalize_run(
    run_id: str,
    *,
    status: str,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    finished_at: Optional[float] = None,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> TaskRun:
    """Finalize a TaskRun by updating status/result metadata in task_run.json."""
    run = _read_run_meta(run_id, runs_dir) or TaskRun(run_id=str(run_id), goal="", status=RUN_STATUS_PENDING)
    run.status = str(status or run.status or RUN_STATUS_SUCCESS)
    run.finished_at = float(finished_at if finished_at is not None else time.time())
    if run.started_at is None:
        run.started_at = run.created_at
    if summary is not None:
        run.summary = str(summary)
    if error is not None:
        run.error = str(error)
    if metadata:
        merged = dict(run.metadata or {})
        merged.update(dict(metadata))
        run.metadata = merged
    _write_run_meta(run, runs_dir)
    return run


def _new_run_id() -> str:
    return f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def _run_dir(run_id: str, runs_dir: Path | str) -> Path:
    root = Path(runs_dir)
    return root / str(run_id)


def _run_meta_path(run_id: str, runs_dir: Path | str) -> Path:
    return _run_dir(run_id, runs_dir) / "task_run.json"


def _steps_path(run_id: str, runs_dir: Path | str) -> Path:
    return _run_dir(run_id, runs_dir) / "steps.jsonl"


def _write_run_meta(run: TaskRun, runs_dir: Path | str) -> None:
    path = _run_meta_path(run.run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _append_step_jsonl(step: StepLog, runs_dir: Path | str) -> None:
    path = _steps_path(step.run_id, runs_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(step.to_dict(), ensure_ascii=False) + "\n")


def _read_run_meta(run_id: str, runs_dir: Path | str) -> Optional[TaskRun]:
    path = _run_meta_path(run_id, runs_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return TaskRun.from_dict(payload)
