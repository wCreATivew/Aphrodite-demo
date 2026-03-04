from __future__ import annotations

from semantic_trigger.metrics import EvalRow, compute_overall_metrics, confusion_pairs


def test_metrics_compute() -> None:
    rows = [
        EvalRow("q1", "trigger", "set_reminder", "trigger", "set_reminder"),
        EvalRow("q2", "trigger", "send_message", "trigger", "set_alarm"),
        EvalRow("q3", "no_trigger", "", "trigger", "web_search"),
        EvalRow("q4", "trigger", "set_alarm", "no_trigger", ""),
    ]
    m = compute_overall_metrics(rows)
    assert m["tp"] == 1.0
    assert m["fp"] == 2.0
    assert m["fn"] == 1.0
    pairs = confusion_pairs(rows, top_n=5)
    assert pairs[0][0] == "send_message->set_alarm"
