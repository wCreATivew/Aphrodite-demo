from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .router.llm_router import LLMRouter, RouterStateMachine


SEMANTIC_INTENT_MODULES: List[Dict[str, str]] = [
    {"name": "agentlib.router.llm_router", "path": "agentlib/router/llm_router.py", "role": "LLM 意图路由(仅意图级)"},
    {"name": "agentlib.semantic_intent_lane", "path": "agentlib/semantic_intent_lane.py", "role": "语义状态机 gate 与主链路适配"},
    {"name": "agentlib.persona_router", "path": "agentlib/persona_router.py", "role": "persona 侧路由"},
]


def list_semantic_intent_modules() -> List[Dict[str, str]]:
    return list(SEMANTIC_INTENT_MODULES)


class SemanticIntentLane:
    def __init__(
        self,
        *,
        semantic_trigger_enabled: bool,
        semantic_trigger_top_k: int,
        semantic_guard_conf_threshold: float,
        semantic_debug_autofix_enabled: bool,
        required_runtime_triggers: Sequence[str],
    ) -> None:
        self.semantic_trigger_enabled = bool(semantic_trigger_enabled)
        self.semantic_guard_conf_threshold = float(semantic_guard_conf_threshold)
        self.semantic_trigger_engine: Any = None
        self.semantic_trigger_last: Dict[str, Any] = {}
        self.router = LLMRouter()
        self.state_machine = RouterStateMachine()

    def init_engine(self, mon: Dict[str, Any]) -> None:
        mon.setdefault("semantic_trigger_enabled", int(bool(self.semantic_trigger_enabled)))
        mon.setdefault("semantic_trigger_ready", int(bool(self.semantic_trigger_enabled)))
        mon.setdefault("semantic_trigger_last_error", "")
        mon.setdefault("semantic_trigger_required_missing", "")
        mon.setdefault("semantic_trigger_calls", 0)
        mon.setdefault("semantic_trigger_hits", 0)
        mon.setdefault("semantic_trigger_last_trigger", "")
        mon.setdefault("semantic_trigger_last_decision", "")
        mon.setdefault("semantic_trigger_last_confidence", 0.0)
        mon.setdefault("semantic_trigger_last_margin", 0.0)

    def infer(self, text: str, mon: Dict[str, Any], *, confirmed: bool = False) -> Optional[Dict[str, Any]]:
        if not self.semantic_trigger_enabled:
            return None
        q = str(text or "").strip()
        if not q:
            return None
        mon["semantic_trigger_calls"] = int(mon.get("semantic_trigger_calls", 0) or 0) + 1
        routed = self.router.route(user_message=q, user_profile={}, recent_context=[], persona_policy="")
        gated = self.state_machine.apply(routed, confirmed=confirmed)

        suggested_mode = self._map_mode(gated.action)
        decision = "trigger"
        if gated.action == "ASK_CLARIFY":
            decision = "ask_clarification"
        elif gated.action == "CHAT":
            decision = "no_trigger"

        payload = {
            "intent": gated.action.lower(),
            "decision": decision,
            "selected_trigger": gated.action.lower(),
            "confidence": float(gated.confidence),
            "required_slots": [],
            "missing_slots": [],
            "risk_level": "high" if gated.action == "EXECUTE_HEAVY" else "low",
            "suggested_mode": suggested_mode,
            "suuggested_mode": suggested_mode,
            "execution_allowed": bool(gated.action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"} and not gated.needs_confirm),
            "needs_confirm": bool(gated.needs_confirm),
            "router_scope": gated.scope,
            "router_action": gated.action,
            "guard_reason": gated.reason,
            "reasons": [gated.reason],
            "margin": 0.0,
            "top_trigger": gated.action.lower(),
            "top_score": float(gated.confidence),
            "extracted_slots": {},
        }
        self.semantic_trigger_last = dict(payload)
        mon["semantic_trigger_last_trigger"] = str(payload.get("selected_trigger") or "")
        mon["semantic_trigger_last_decision"] = str(payload.get("decision") or "")
        mon["semantic_trigger_last_confidence"] = float(payload.get("confidence") or 0.0)
        mon["semantic_trigger_last_margin"] = 0.0
        if decision in {"trigger", "ask_clarification"}:
            mon["semantic_trigger_hits"] = int(mon.get("semantic_trigger_hits", 0) or 0) + 1
        return payload

    @staticmethod
    def _map_mode(action: str) -> str:
        a = str(action or "").upper()
        if a == "ASK_CLARIFY":
            return "ask_clarify"
        if a in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}:
            return "selfdrive"
        if a == "TOOL_LIGHT":
            return "tool"
        return "chat"

    def semantic_required_slots_for_trigger(self, trigger_id: str) -> List[str]:
        return []

    @staticmethod
    def semantic_suggested_mode(decision: str, intent: str, missing_slots: List[str]) -> str:
        return SemanticIntentLane._map_mode(intent)

    @staticmethod
    def semantic_risk_level(suggested_mode: str, confidence: float, missing_slots: List[str]) -> str:
        if str(suggested_mode or "") in {"selfdrive", "debug"}:
            return "high"
        return "low"

    def semantic_guard_decision(
        self,
        *,
        text: str,
        intent: str,
        suggested_mode: str,
        confidence: float,
    ) -> Dict[str, Any]:
        # compatibility API retained for existing tests/callers
        needs_confirm = bool(str(intent or "").upper() in {"EXECUTE_HEAVY", "CODE_DEBUG"})
        conf = float(confidence or 0.0)
        threshold = float(self.semantic_guard_conf_threshold)
        if conf < threshold:
            if needs_confirm:
                return {
                    "suggested_mode": "ask_user_confirm",
                    "execution_allowed": False,
                    "reason": f"low_confidence<{threshold:.2f}",
                }
            return {
                "suggested_mode": str(suggested_mode or "chat"),
                "execution_allowed": False,
                "reason": f"low_confidence_non_control<{threshold:.2f}",
            }
        if needs_confirm:
            return {
                "suggested_mode": "shadow_plan_only",
                "execution_allowed": False,
                "reason": "high_risk_control_intent",
            }
        return {
            "suggested_mode": str(suggested_mode or "chat"),
            "execution_allowed": False,
            "reason": "",
        }
