from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import logging
from typing import Any, Dict, List


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str, level: str = "INFO", json_log: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonLogFormatter() if json_log else logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_with_fields(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


def result_to_dict(result: Any) -> Dict[str, Any]:
    def _convert(obj: Any) -> Any:
        if obj is None:
            return None
        if is_dataclass(obj):
            return _convert(asdict(obj))
        if hasattr(obj, "model_dump"):
            try:
                return _convert(obj.model_dump())
            except Exception:
                pass
        if isinstance(obj, dict):
            return {str(k): _convert(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_convert(x) for x in obj]
        if hasattr(obj, "__dict__"):
            return _convert(vars(obj))
        return obj

    data = _convert(result)
    if not isinstance(data, dict):
        data = {"raw_result": data}

    debug_payload = data.get("debug")
    if (not isinstance(debug_payload, dict)) and isinstance(data.get("debug_trace"), dict):
        debug_payload = dict(data.get("debug_trace") or {})
    if not isinstance(debug_payload, dict):
        debug_payload = {}

    return {
        "user_query": str(data.get("user_query") or data.get("query") or ""),
        "decision": str(data.get("decision") or "no_trigger"),
        "selected_trigger": data.get("selected_trigger"),
        "confidence": float(data.get("confidence") or 0.0),
        "candidates": list(data.get("candidates") or []),
        "extracted_slots": dict(data.get("extracted_slots") or {}),
        "missing_slots": list(data.get("missing_slots") or []),
        "clarification_question": data.get("clarification_question"),
        "reasons": list(data.get("reasons") or []),
        "debug": debug_payload,
        "top_k_candidates": list(data.get("top_k_candidates") or debug_payload.get("top_k_candidates") or []),
        "recall_scores": dict(data.get("recall_scores") or debug_payload.get("recall_scores") or {}),
        "rerank_scores": dict(data.get("rerank_scores") or debug_payload.get("rerank_scores") or {}),
        "margin": float(data.get("margin") or debug_payload.get("margin") or 0.0),
        "config_version": str(data.get("config_version") or debug_payload.get("config_version") or "v1"),
        "policy_version": str(data.get("policy_version") or debug_payload.get("policy_version") or "v1"),
        "dataset_version": str(data.get("dataset_version") or debug_payload.get("dataset_version") or ""),
    }


def format_engine_result(result: Any, *, debug: bool = False, max_candidates: int = 5) -> str:
    data = result_to_dict(result)
    lines: List[str] = [
        f"decision={data['decision']}",
        f"selected_trigger={data['selected_trigger']}",
        f"confidence={float(data['confidence']):.4f}",
    ]
    cands = list(data.get("candidates") or [])[: max(1, int(max_candidates))]
    lines.append("candidates:")
    for idx, c in enumerate(cands, start=1):
        cid = c.get("trigger_id")
        fs = c.get("final_score")
        if fs is None:
            fs = c.get("combined_score")
        rs = c.get("recall_score")
        rrs = c.get("rerank_score")
        lines.append(f"  {idx}. trigger_id={cid} final={_fmt_num(fs)} recall={_fmt_num(rs)} rerank={_fmt_num(rrs)}")

    lines.append("extracted_slots=" + json.dumps(data.get("extracted_slots") or {}, ensure_ascii=False))
    lines.append("missing_slots=" + json.dumps(data.get("missing_slots") or [], ensure_ascii=False))
    lines.append("clarification_question=" + str(data.get("clarification_question")))
    lines.append("reasons=" + json.dumps(data.get("reasons") or [], ensure_ascii=False))
    lines.append("debug_summary=" + _debug_summary(data.get("debug") or {}))
    if debug:
        lines.append("debug=" + json.dumps(data.get("debug") or {}, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def make_structured_prediction_log(
    result: Any,
    *,
    expected_decision: Any = None,
    expected_trigger: Any = None,
    run_id: Any = None,
    note: Any = None,
    source: str = "prediction",
) -> Dict[str, Any]:
    data = result_to_dict(result)
    from .error_ledger import make_ledger_record_from_prediction

    return make_ledger_record_from_prediction(
        data,
        query=data.get("user_query"),
        expected_decision=expected_decision,
        expected_trigger=expected_trigger,
        run_id=run_id,
        note=note,
        source=source,
    )


def append_prediction_log(
    path: str,
    result: Any,
    *,
    expected_decision: Any = None,
    expected_trigger: Any = None,
    run_id: Any = None,
    note: Any = None,
    source: str = "prediction",
) -> int:
    from .error_ledger import append_ledger_record

    rec = make_structured_prediction_log(
        result,
        expected_decision=expected_decision,
        expected_trigger=expected_trigger,
        run_id=run_id,
        note=note,
        source=source,
    )
    return append_ledger_record(path, rec)


def _fmt_num(val: Any) -> str:
    try:
        return f"{float(val):.4f}"
    except Exception:
        return "n/a"


def _debug_summary(debug_payload: Dict[str, Any]) -> str:
    if not debug_payload:
        return "{}"
    keys = ["engine_backend", "top_k", "top1", "top2", "margin", "top1_score", "top2_score"]
    compact = {k: debug_payload.get(k) for k in keys if k in debug_payload}
    return json.dumps(compact, ensure_ascii=False)
