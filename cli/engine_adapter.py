from __future__ import annotations

import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class EngineAdapter:
    def infer(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        raise NotImplementedError


class StubEngineAdapter(EngineAdapter):
    def __init__(self) -> None:
        self._defs: List[Dict[str, str]] = [
            {"trigger_id": "set_reminder", "name": "Set Reminder", "hint": "remind reminder later tomorrow alarm"},
            {"trigger_id": "send_message", "name": "Send Message", "hint": "send message text sms tell"},
            {"trigger_id": "weather_query", "name": "Weather Query", "hint": "weather forecast rain temperature"},
            {"trigger_id": "web_search", "name": "Web Search", "hint": "search lookup find web"},
            {"trigger_id": "smalltalk_chat", "name": "Smalltalk", "hint": "hello hi chat"},
        ]

    def infer(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        q = str(query or "").strip()
        q_low = q.lower()
        candidates: List[Dict[str, Any]] = []
        for item in self._defs:
            score = self._score(q_low, item["hint"])
            candidates.append(
                {
                    "trigger_id": item["trigger_id"],
                    "recall_score": round(score * 0.95, 4),
                    "rerank_score": round(score, 4),
                    "final_score": round(score, 4),
                    "notes": f"stub_score={score:.4f}",
                    "name": item["name"],
                }
            )
        candidates.sort(key=lambda x: float(x.get("final_score") or 0.0), reverse=True)
        top = candidates[: max(1, int(top_k))]
        top1 = float(top[0]["final_score"]) if top else 0.0
        top2 = float(top[1]["final_score"]) if len(top) > 1 else 0.0
        margin = top1 - top2

        selected = top[0]["trigger_id"] if top else None
        extracted, missing = self._extract_slots(q, selected)
        reasons = [f"stub:top1={top1:.4f}", f"stub:top2={top2:.4f}", f"stub:margin={margin:.4f}"]
        decision = "no_trigger"
        clarification_question: Optional[str] = None

        if not q:
            reasons.append("stub:empty_query")
        elif top1 < 0.34:
            reasons.append("stub:below_threshold")
        elif missing:
            decision = "ask_clarification"
            clarification_question = "Please provide: " + ", ".join(missing)
            reasons.append("stub:missing_slots")
        elif margin < 0.08:
            decision = "ask_clarification"
            clarification_question = "Please clarify your intent."
            reasons.append("stub:ambiguous_margin")
        else:
            decision = "trigger"
            reasons.append("stub:trigger")

        if decision == "no_trigger":
            selected = None
            extracted = {}
            missing = []

        return {
            "user_query": q,
            "decision": decision,
            "selected_trigger": selected,
            "confidence": round(max(0.0, min(1.0, top1)), 4),
            "candidates": top,
            "extracted_slots": extracted,
            "missing_slots": missing,
            "clarification_question": clarification_question,
            "reasons": reasons,
            "debug": {
                "engine_backend": "stub",
                "top_k": int(top_k),
                "top1": top1,
                "top2": top2,
                "margin": margin,
            },
        }

    @staticmethod
    def _score(query_lower: str, hint: str) -> float:
        tokens = [x for x in hint.lower().split() if x]
        if not tokens:
            return 0.0
        hits = sum(1 for t in tokens if t in query_lower)
        base = hits / len(tokens)
        return max(0.0, min(1.0, 0.20 + 0.80 * base))

    @staticmethod
    def _extract_slots(query: str, trigger_id: Optional[str]) -> Tuple[Dict[str, Any], List[str]]:
        if not trigger_id:
            return {}, []
        q = str(query or "")
        out: Dict[str, Any] = {}
        missing: List[str] = []

        if trigger_id == "set_reminder":
            time_match = re.search(r"(\\d{1,2}(:\\d{2})?)|tomorrow|tonight|next|later|morning|afternoon", q, re.IGNORECASE)
            if time_match:
                out["time"] = time_match.group(0)
            else:
                missing.append("time")

            if "remind" in q.lower():
                content = re.sub(r".*remind me\\s*", "", q, flags=re.IGNORECASE).strip()
                if content and content != q:
                    out["content"] = content
            if "content" not in out:
                missing.append("content")

        if trigger_id == "send_message":
            to_match = re.search(r"to\\s+([^\\s:;,]+)", q, re.IGNORECASE)
            if to_match:
                out["recipient"] = to_match.group(1)
            if ":" in q:
                out["content"] = q.split(":", 1)[-1].strip()
            if "recipient" not in out:
                missing.append("recipient")
            if "content" not in out:
                missing.append("content")
        return out, missing


class RealEngineAdapter(EngineAdapter):
    def __init__(self, real_engine: Any) -> None:
        self._engine = real_engine

    def infer(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        res = self._engine.infer(query, top_k=top_k)
        if is_dataclass(res):
            data = asdict(res)
        elif isinstance(res, dict):
            data = dict(res)
        elif hasattr(res, "model_dump"):
            data = dict(res.model_dump())
        else:
            data = {
                "user_query": str(query),
                "decision": str(getattr(res, "decision", "no_trigger")),
                "selected_trigger": getattr(res, "selected_trigger", None),
                "confidence": float(getattr(res, "confidence", 0.0)),
                "candidates": getattr(res, "candidates", []),
                "extracted_slots": getattr(res, "extracted_slots", {}) or {},
                "missing_slots": getattr(res, "missing_slots", []) or [],
                "clarification_question": getattr(res, "clarification_question", None),
                "reasons": getattr(res, "reasons", []) or [],
                "debug": getattr(res, "debug", {}) or {},
            }
        debug = dict(data.get("debug") or {})
        debug.setdefault("engine_backend", "real")
        data["debug"] = debug
        return data


def build_engine_adapter(
    *,
    triggers_path: str = "",
    prefer_real: bool = True,
) -> EngineAdapter:
    if prefer_real:
        try:
            from semantic_trigger.config import load_app_config
            from semantic_trigger.engine import SemanticTriggerEngine
            from semantic_trigger.registry import load_trigger_registry

            root = Path(__file__).resolve().parents[1]
            reg_path = Path(triggers_path) if triggers_path else (root / "data" / "triggers" / "default_triggers.yaml")
            cfg_path = root / "configs" / "app.example.yaml"
            reg = load_trigger_registry(str(reg_path))
            cfg = load_app_config(str(cfg_path) if cfg_path.exists() else "")
            eng = SemanticTriggerEngine.build_default(reg, cfg)
            return RealEngineAdapter(eng)
        except Exception:
            pass
    return StubEngineAdapter()
