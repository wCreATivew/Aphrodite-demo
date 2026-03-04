from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.llm_router import route_intent


DEFAULT_INPUT_CANDIDATES = (
    "evals/*.jsonl",
    "router_regression_set_v1.jsonl",
)


def _load_jsonl(paths: Iterable[Path]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except Exception as exc:
                    raise ValueError(f"invalid jsonl: {path}:{idx}: {exc}") from exc
                obj["__source__"] = str(path)
                obj["__line__"] = idx
                rows.append(obj)
    return rows


def _acc(rows: List[Dict[str, Any]], key_gold: str, key_pred: str) -> float:
    if not rows:
        return 0.0
    ok = 0
    for r in rows:
        if str(r.get(key_gold) or "").upper() == str(r.get(key_pred) or "").upper():
            ok += 1
    return ok / len(rows)


def _matrix(rows: List[Dict[str, Any]], gold_key: str, pred_key: str) -> Dict[str, Dict[str, int]]:
    m: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        g = str(r.get(gold_key) or "").upper() or "UNKNOWN"
        p = str(r.get(pred_key) or "").upper() or "UNKNOWN"
        m[g][p] += 1
    return {g: dict(cols) for g, cols in m.items()}


def _resolve_input_paths(input_globs: Sequence[str], input_files: Sequence[str]) -> List[Path]:
    out: List[Path] = []
    seen = set()

    for path_text in input_files:
        p = Path(path_text)
        if p.is_file():
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                out.append(p)

    for pat in input_globs:
        for p in sorted(Path(".").glob(pat)):
            if not p.is_file():
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out




def _find_fallback_dataset_candidates() -> List[Path]:
    roots = [Path('.'), ROOT, Path('/workspace')]
    patterns = [
        '**/router_regression_set_v1.jsonl',
        '**/*router*regression*.jsonl',
    ]
    out: List[Path] = []
    seen = set()
    for r in roots:
        if not r.exists():
            continue
        for pat in patterns:
            try:
                for hit in sorted(r.glob(pat)):
                    if not hit.is_file():
                        continue
                    key = str(hit.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(hit)
            except Exception:
                continue
    return out

def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate B+DLLM router on jsonl regression sets.")
    ap.add_argument(
        "--input-glob",
        action="append",
        default=[],
        help="Glob pattern(s) for datasets. Can be repeated. Default: evals/*.jsonl + router_regression_set_v1.jsonl",
    )
    ap.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Explicit dataset file path(s). Can be repeated.",
    )
    ap.add_argument("--report-path", default="report.json")
    ap.add_argument("--matrix-path", default="confusion_matrix.json")
    args = ap.parse_args()

    globs = list(args.input_glob or [])
    if not globs:
        globs = list(DEFAULT_INPUT_CANDIDATES)

    paths = _resolve_input_paths(globs, list(args.input_file or []))
    if not paths:
        fallback_hits = _find_fallback_dataset_candidates()
        if fallback_hits:
            paths = fallback_hits
        else:
            searched = {"input_files": list(args.input_file or []), "input_globs": globs, "cwd": str(Path('.').resolve())}
            raise SystemExit(
                f"No eval files found. searched={json.dumps(searched, ensure_ascii=False)}; "
                "tip=put router_regression_set_v1.jsonl under repo root or pass --input-file /abs/path"
            )

    rows = _load_jsonl(paths)
    outputs: List[Dict[str, Any]] = []
    for row in rows:
        pred = route_intent(
            user_message=str(row.get("user_message") or row.get("query") or ""),
            user_profile=dict(row.get("user_profile") or {}),
            recent_context=dict(row.get("recent_context") or {}),
            persona_policy=dict(row.get("persona_policy") or {}),
        )
        enriched = dict(row)
        enriched["pred_action"] = pred.action
        enriched["pred_scope"] = pred.scope
        enriched["pred_needs_confirm"] = bool(pred.needs_confirm)
        outputs.append(enriched)

    action_accuracy = _acc(outputs, "expected_action", "pred_action")
    scope_accuracy = _acc(outputs, "expected_scope", "pred_scope")

    confirm_hits = 0
    confirm_total = 0
    for r in outputs:
        if "expected_needs_confirm" in r:
            confirm_total += 1
            if bool(r.get("expected_needs_confirm")) == bool(r.get("pred_needs_confirm")):
                confirm_hits += 1
    confirm_compliance = (confirm_hits / confirm_total) if confirm_total else 0.0

    failures = []
    for r in outputs:
        bad = []
        if str(r.get("expected_action") or "").upper() != str(r.get("pred_action") or "").upper():
            bad.append("action")
        if str(r.get("expected_scope") or "").upper() != str(r.get("pred_scope") or "").upper():
            bad.append("scope")
        if "expected_needs_confirm" in r and bool(r.get("expected_needs_confirm")) != bool(r.get("pred_needs_confirm")):
            bad.append("confirm")
        if bad:
            failures.append(
                {
                    "source": r.get("__source__"),
                    "line": r.get("__line__"),
                    "user_message": r.get("user_message") or r.get("query"),
                    "failed_dims": bad,
                    "expected_action": r.get("expected_action"),
                    "pred_action": r.get("pred_action"),
                    "expected_scope": r.get("expected_scope"),
                    "pred_scope": r.get("pred_scope"),
                    "expected_needs_confirm": r.get("expected_needs_confirm"),
                    "pred_needs_confirm": r.get("pred_needs_confirm"),
                }
            )

    report = {
        "samples": len(outputs),
        "files": [str(p) for p in paths],
        "action_accuracy": action_accuracy,
        "scope_accuracy": scope_accuracy,
        "confirm_compliance": confirm_compliance,
        "failure_count": len(failures),
        "failure_samples": failures,
    }

    action_matrix = _matrix(outputs, "expected_action", "pred_action")
    scope_matrix = _matrix(outputs, "expected_scope", "pred_scope")

    Path(args.report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.matrix_path).write_text(
        json.dumps({"action": action_matrix, "scope": scope_matrix}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "action_accuracy": action_accuracy,
                "scope_accuracy": scope_accuracy,
                "confirm_compliance": confirm_compliance,
                "samples": len(outputs),
                "files": [str(p) for p in paths],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
