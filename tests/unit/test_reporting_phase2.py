from __future__ import annotations

from semantic_trigger.reporting import build_eval_report, mine_hard_negatives


def test_build_eval_report_contains_error_ledger_fields() -> None:
    rows = [
        {
            "query": "set reminder architecture",
            "expected_decision": "no_trigger",
            "expected_trigger": "",
            "predicted_decision": "trigger",
            "predicted_trigger": "set_reminder",
            "top_k_candidates": ["set_reminder", "web_search"],
            "recall_scores": {"set_reminder": 0.62},
            "rerank_scores": {"set_reminder": 0.60},
            "margin": 0.41,
            "extracted_slots": {},
            "missing_slots": [],
            "clarification_question": None,
            "reasons": ["decision=trigger"],
            "difficulty": "hard",
        }
    ]
    report = build_eval_report(
        rows,
        config_version="cfg_v2",
        policy_version="policy_v2",
        dataset_version="eval_v2",
    )
    assert report["total"] == 1
    assert isinstance(report["error_ledger"], list)
    assert len(report["error_ledger"]) == 1
    row0 = report["error_ledger"][0]
    assert row0["query"] == "set reminder architecture"
    assert row0["predicted_decision"] == "trigger"
    assert row0["predicted_trigger"] == "set_reminder"
    assert isinstance(row0["top_k_candidates"], list)
    assert isinstance(row0["recall_scores"], dict)
    assert isinstance(row0["rerank_scores"], dict)
    assert row0["config_version"] == "cfg_v2"
    assert row0["policy_version"] == "policy_v2"
    assert row0["dataset_version"] == "eval_v2"
    assert "timestamp" in row0


def test_mine_hard_negatives_from_false_positives() -> None:
    rows = [
        {
            "query": "alarm app ranking",
            "expected_decision": "no_trigger",
            "predicted_decision": "trigger",
            "predicted_trigger": "set_alarm",
            "timestamp": "2026-02-27T00:00:00+00:00",
        },
        {
            "query": "normal trigger",
            "expected_decision": "trigger",
            "predicted_decision": "trigger",
            "predicted_trigger": "set_reminder",
        },
    ]
    hard = mine_hard_negatives(rows)
    assert len(hard) == 1
    assert hard[0]["query"] == "alarm app ranking"
    assert hard[0]["confusable_with"] == "set_alarm"
