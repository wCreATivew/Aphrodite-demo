from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class StepLog:
    step_id: str
    ts_start: float
    ts_end: float
    duration_ms: int
    component: str = ""
    action: str = ""
    input_preview: str = ""
    output_preview: str = ""
    success: bool = True
    input_payload: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    status: str = "ok"


# Backward-compatible alias.
TaskRunStep = StepLog


@dataclass
class TaskRun:
    run_id: str
    goal: str
    plan: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[StepLog] = field(default_factory=list)
    status: str = "running"
    summary: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class TaskRunRecorder:
    def __init__(self, base_dir: str = os.path.join("outputs", "task_runs")):
        self.base_dir = str(base_dir or os.path.join("outputs", "task_runs"))
        os.makedirs(self.base_dir, exist_ok=True)

    def _meta_path(self, run_id: str) -> str:
        return os.path.join(self.base_dir, f"{run_id}.json")

    def _steps_path(self, run_id: str) -> str:
        return os.path.join(self.base_dir, f"{run_id}.steps.jsonl")

    def start_run(self, *, goal: str, plan: Optional[List[Dict[str, Any]]] = None) -> TaskRun:
        rid = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        run = TaskRun(run_id=rid, goal=str(goal or "").strip(), plan=list(plan or []), status="running")
        self.save_run(run)
        return run

    def save_run(self, run: TaskRun) -> None:
        run.updated_at = float(time.time())
        payload = asdict(run)
        payload["steps"] = [asdict(x) for x in list(run.steps or [])]
        with open(self._meta_path(run.run_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def append_step(self, run: TaskRun, step: StepLog) -> None:
        run.steps.append(step)
        run.updated_at = float(time.time())
        with open(self._steps_path(run.run_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(step), ensure_ascii=False) + "\n")
        self.save_run(run)

    # Explicit StepLog API while keeping append_step for compatibility.
    def append_step_log(self, run: TaskRun, step: StepLog) -> None:
        self.append_step(run, step)

    def finalize(self, run: TaskRun, *, status: str, summary: str = "") -> None:
        run.status = str(status or run.status or "done")
        if str(summary or "").strip():
            run.summary = str(summary).strip()
        run.updated_at = float(time.time())
        self.save_run(run)


def load_task_runs(base_dir: str = os.path.join("outputs", "task_runs")) -> List[TaskRun]:
    out: List[TaskRun] = []
    root = str(base_dir or os.path.join("outputs", "task_runs"))
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root), reverse=True):
        if not name.endswith(".json") or name.endswith(".steps.json"):
            continue
        p = os.path.join(root, name)
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        steps_raw = list(obj.get("steps") or [])
        steps = [StepLog(**dict(x)) for x in steps_raw if isinstance(x, dict)]
        out.append(
            TaskRun(
                run_id=str(obj.get("run_id") or ""),
                goal=str(obj.get("goal") or ""),
                plan=list(obj.get("plan") or []),
                steps=steps,
                status=str(obj.get("status") or "unknown"),
                summary=str(obj.get("summary") or ""),
                created_at=float(obj.get("created_at") or 0.0),
                updated_at=float(obj.get("updated_at") or 0.0),
            )
        )
    return out


def load_task_run_steps(run_id: str, base_dir: str = os.path.join("outputs", "task_runs")) -> List[StepLog]:
    p = os.path.join(str(base_dir or os.path.join("outputs", "task_runs")), f"{run_id}.steps.jsonl")
    out: List[StepLog] = []
    if not os.path.isfile(p):
        return out
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            t = str(line or "").strip()
            if not t:
                continue
            try:
                obj = json.loads(t)
            except Exception:
                continue
            if isinstance(obj, dict):
                try:
                    out.append(StepLog(**obj))
                except Exception:
                    pass
    return out


def _iso_utc(ts: float) -> str:
    if float(ts or 0.0) <= 0.0:
        return ""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_step_rows(steps: List[TaskRunStep]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, step in enumerate(sorted(list(steps or []), key=lambda x: float(getattr(x, "ts_start", 0.0)))):
        tool_names: List[str] = []
        for tc in list(step.tool_calls or []):
            name = str((tc or {}).get("tool_name") or "").strip()
            if name:
                tool_names.append(name)
        rows.append(
            {
                "index": idx + 1,
                "step_id": str(step.step_id or f"s{idx+1:04d}"),
                "status": str(step.status or "unknown"),
                "start_time": _iso_utc(float(step.ts_start or 0.0)),
                "end_time": _iso_utc(float(step.ts_end or 0.0)),
                "duration_ms": int(step.duration_ms or 0),
                "error": str(step.error or ""),
                "tool_calls": tool_names,
                "output": dict(step.output or {}),
            }
        )
    return rows


def build_task_run_report(run: TaskRun, steps: Optional[List[TaskRunStep]] = None) -> Dict[str, Any]:
    ordered_steps = list(steps if steps is not None else run.steps or [])
    ordered_steps = sorted(ordered_steps, key=lambda x: float(getattr(x, "ts_start", 0.0)))
    step_rows = _normalize_step_rows(ordered_steps)
    start_ts, end_ts = _infer_run_bounds(run, ordered_steps)
    failed = [x for x in step_rows if str(x.get("status") or "").lower() in {"error", "failed"}]
    final_summary = _final_summary(run, step_rows)
    return {
        "run_id": str(run.run_id or ""),
        "goal": str(run.goal or ""),
        "status": str(run.status or "unknown"),
        "start_time": _iso_utc(start_ts),
        "end_time": _iso_utc(end_ts),
        "duration_ms": int(max(0.0, end_ts - start_ts) * 1000.0) if start_ts and end_ts and end_ts >= start_ts else 0,
        "step_count": len(step_rows),
        "failed_steps": [
            {
                "step_id": str(x.get("step_id") or ""),
                "error": str(x.get("error") or ""),
                "status": str(x.get("status") or ""),
            }
            for x in failed
        ],
        "final_summary": final_summary,
        "steps": step_rows,
    }


def _infer_run_bounds(run: TaskRun, steps: List[TaskRunStep]) -> Tuple[float, float]:
    if steps:
        starts = [float(s.ts_start or 0.0) for s in steps if float(s.ts_start or 0.0) > 0.0]
        ends = [float(s.ts_end or 0.0) for s in steps if float(s.ts_end or 0.0) > 0.0]
        if starts and ends:
            return min(starts), max(ends)
    created = float(run.created_at or 0.0)
    updated = float(run.updated_at or 0.0)
    if created > 0.0 and updated > 0.0 and updated >= created:
        return created, updated
    return created, updated


def _final_summary(run: TaskRun, step_rows: List[Dict[str, Any]]) -> str:
    if not step_rows:
        return f"Run ended with status={str(run.status or 'unknown')} and no recorded steps."
    last = step_rows[-1]
    if str(last.get("error") or ""):
        return f"Last step {last.get('step_id')} failed: {str(last.get('error') or '').strip()}"
    output = dict(last.get("output") or {})
    for key in ("summary", "message", "result", "selected_expert"):
        val = str(output.get(key) or "").strip()
        if val:
            return val
    return f"Run finished with status={str(run.status or 'unknown')} after {len(step_rows)} steps."


def render_task_run_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# Task Run Report: `{str(report.get('run_id') or '')}`",
        "",
        f"- Goal: {str(report.get('goal') or '-')}",
        f"- Status: {str(report.get('status') or 'unknown')}",
        f"- Start: {str(report.get('start_time') or '-')}",
        f"- End: {str(report.get('end_time') or '-')}",
        f"- Duration: {int(report.get('duration_ms') or 0)} ms",
        f"- Steps: {int(report.get('step_count') or 0)}",
        "",
        "## Final Summary",
        str(report.get("final_summary") or "-"),
        "",
        "## Timeline",
    ]
    steps = list(report.get("steps") or [])
    if not steps:
        lines.append("- No steps recorded.")
    for row in steps:
        tools = ", ".join([str(x) for x in list(row.get("tool_calls") or []) if str(x).strip()])
        duration = int(row.get("duration_ms") or 0)
        suffix = f" | tools: {tools}" if tools else ""
        lines.append(
            f"- {row.get('step_id')} | {row.get('status')} | {row.get('start_time')} -> {row.get('end_time')} "
            f"({duration} ms){suffix}"
        )
    lines.extend(["", "## Errors"])
    failed = list(report.get("failed_steps") or [])
    if not failed:
        lines.append("- None")
    else:
        for item in failed:
            lines.append(f"- {item.get('step_id')}: {item.get('error') or item.get('status')}")
    lines.extend(["", "## Key Outputs"])
    if not steps:
        lines.append("- None")
    else:
        for row in steps:
            output = dict(row.get("output") or {})
            if output:
                lines.append(f"- {row.get('step_id')}: `{json.dumps(output, ensure_ascii=False, sort_keys=True)}`")
    return "\n".join(lines).strip() + "\n"


def export_task_run_report(run_id: str, *, base_dir: str = os.path.join("outputs", "task_runs"), out_dir: Optional[str] = None) -> Dict[str, str]:
    runs = [x for x in load_task_runs(base_dir) if str(x.run_id) == str(run_id)]
    if not runs:
        raise FileNotFoundError(f"task run not found: {run_id}")
    run = runs[0]
    steps = load_task_run_steps(run_id, base_dir=base_dir)
    report = build_task_run_report(run, steps=steps)

    target_dir = str(out_dir or os.path.join(base_dir, "reports"))
    os.makedirs(target_dir, exist_ok=True)
    json_path = os.path.join(target_dir, f"{run_id}.report.json")
    md_path = os.path.join(target_dir, f"{run_id}.report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_task_run_markdown(report))
    return {"json_path": json_path, "markdown_path": md_path}
