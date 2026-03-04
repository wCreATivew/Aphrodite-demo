from __future__ import annotations

import argparse
import os

from agentlib.task_run import export_task_run_report, load_task_runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay/export TaskRun report")
    parser.add_argument("--run-id", default="", help="Task run ID to export")
    parser.add_argument("--base-dir", default=os.path.join("outputs", "task_runs"), help="Task run directory")
    parser.add_argument("--out-dir", default="", help="Directory for exported reports")
    parser.add_argument("--latest", action="store_true", help="Use latest run when --run-id is omitted")
    return parser.parse_args()


def _resolve_run_id(args: argparse.Namespace) -> str:
    rid = str(args.run_id or "").strip()
    if rid:
        return rid
    if not bool(args.latest):
        raise ValueError("--run-id is required unless --latest is provided")
    runs = load_task_runs(base_dir=str(args.base_dir or ""))
    if not runs:
        raise FileNotFoundError(f"no task runs found under: {args.base_dir}")
    return str(runs[0].run_id)


def main() -> int:
    args = parse_args()
    run_id = _resolve_run_id(args)
    paths = export_task_run_report(
        run_id,
        base_dir=str(args.base_dir or os.path.join("outputs", "task_runs")),
        out_dir=str(args.out_dir or ""),
    )
    print(f"run_id={run_id}")
    print(f"json_report={paths['json_path']}")
    print(f"markdown_report={paths['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
