from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TaskRunStep:
    step_id: str
    ts_start: float
    ts_end: float
    duration_ms: int
    input_payload: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    status: str = "ok"


@dataclass
class TaskRun:
    run_id: str
    goal: str
    plan: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[TaskRunStep] = field(default_factory=list)
    status: str = "running"
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

    def append_step(self, run: TaskRun, step: TaskRunStep) -> None:
        run.steps.append(step)
        run.updated_at = float(time.time())
        with open(self._steps_path(run.run_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(step), ensure_ascii=False) + "\n")
        self.save_run(run)

    def finalize(self, run: TaskRun, *, status: str) -> None:
        run.status = str(status or run.status or "done")
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
        steps = [TaskRunStep(**dict(x)) for x in steps_raw if isinstance(x, dict)]
        out.append(
            TaskRun(
                run_id=str(obj.get("run_id") or ""),
                goal=str(obj.get("goal") or ""),
                plan=list(obj.get("plan") or []),
                steps=steps,
                status=str(obj.get("status") or "unknown"),
                created_at=float(obj.get("created_at") or 0.0),
                updated_at=float(obj.get("updated_at") or 0.0),
            )
        )
    return out


def load_task_run_steps(run_id: str, base_dir: str = os.path.join("outputs", "task_runs")) -> List[TaskRunStep]:
    p = os.path.join(str(base_dir or os.path.join("outputs", "task_runs")), f"{run_id}.steps.jsonl")
    out: List[TaskRunStep] = []
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
                    out.append(TaskRunStep(**obj))
                except Exception:
                    pass
    return out
