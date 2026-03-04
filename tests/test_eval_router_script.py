from __future__ import annotations

from pathlib import Path

from scripts.eval_router import _find_fallback_dataset_candidates, _resolve_input_paths
import scripts.eval_router as eval_router


def test_resolve_input_paths_supports_explicit_file(tmp_path: Path) -> None:
    p = tmp_path / "router_regression_set_v1.jsonl"
    p.write_text('{"user_message":"hi"}\n', encoding='utf-8')

    out = _resolve_input_paths([], [str(p)])
    assert len(out) == 1
    assert out[0] == p


def test_resolve_input_paths_deduplicates_files(tmp_path: Path, monkeypatch) -> None:
    p = tmp_path / "evals"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "a.jsonl"
    f.write_text('{"user_message":"hi"}\n', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    out = _resolve_input_paths(["evals/*.jsonl"], [str(f)])
    assert len(out) == 1
    assert out[0].name == "a.jsonl"


def test_find_fallback_dataset_candidates_scans_repo_like_paths(tmp_path: Path, monkeypatch) -> None:
    ds = tmp_path / "nested" / "router_regression_set_v1.jsonl"
    ds.parent.mkdir(parents=True, exist_ok=True)
    ds.write_text('{"user_message":"hi"}\n', encoding='utf-8')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(eval_router, "ROOT", tmp_path)
    hits = _find_fallback_dataset_candidates()
    assert any(h.name == "router_regression_set_v1.jsonl" for h in hits)
