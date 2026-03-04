from __future__ import annotations

from semantic_trigger.error_ledger import build_hard_negatives_from_ledger, build_ledger_entry, summarize_ledger


def test_build_ledger_entry_contains_required_fields() -> None:
    row = build_ledger_entry(
        query="message queue design",
        predicted_decision="trigger",
        predicted_trigger="send_message",
        expected_decision="no_trigger",
        expected_trigger="",
        top_k_candidates=["send_message", "web_search"],
        recall_scores={"send_message": 0.71},
        rerank_scores={"send_message": 0.69},
        margin=0.11,
        extracted_slots={},
        missing_slots=[],
        clarification_question=None,
        reasons=["decision=trigger"],
        config_version="cfg.v2",
        policy_version="policy.v7",
        dataset_version="eval.2026-02",
    )
    assert row["query"] == "message queue design"
    assert row["predicted_decision"] == "trigger"
    assert row["expected_decision"] == "no_trigger"
    assert row["error_type"] == "false_positive"
    assert "timestamp" in row


def test_hard_negative_mining_from_false_positive() -> None:
    rows = [
        build_ledger_entry(
            query="weather plugin development",
            predicted_decision="trigger",
            predicted_trigger="weather_query",
            expected_decision="no_trigger",
            expected_trigger="",
            margin=0.2,
        ),
        build_ledger_entry(
            query="set alarm for tomorrow",
            predicted_decision="trigger",
            predicted_trigger="set_alarm",
            expected_decision="trigger",
            expected_trigger="set_alarm",
            margin=0.3,
        ),
    ]
    mined = build_hard_negatives_from_ledger(rows, min_margin=0.05)
    assert len(mined) == 1
    assert mined[0]["query"] == "weather plugin development"
    assert mined[0]["confusable_with"] == "weather_query"
    summary = summarize_ledger(rows)
    assert summary["total"] == 2

