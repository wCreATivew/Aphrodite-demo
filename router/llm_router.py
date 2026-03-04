from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional



class RouterAction(str, Enum):
    CHAT = "CHAT"
    ASK_CLARIFY = "ASK_CLARIFY"
    TOOL_LIGHT = "TOOL_LIGHT"
    EXECUTE_LIGHT = "EXECUTE_LIGHT"
    EXECUTE_HEAVY = "EXECUTE_HEAVY"


class RouterScope(str, Enum):
    MAIN = "MAIN"
    PROJECT_ONLY = "PROJECT_ONLY"
    ISOLATED = "ISOLATED"
    VM = "VM"
    LOBSTER = "LOBSTER"


@dataclass(frozen=True)
class RouterOutput:
    action: str
    scope: str
    needs_confirm: bool
    reason: str
    confidence: float

    @staticmethod
    def fallback(reason: str = "fallback") -> "RouterOutput":
        return RouterOutput(
            action=RouterAction.CHAT.value,
            scope=RouterScope.MAIN.value,
            needs_confirm=False,
            reason=reason,
            confidence=0.35,
        )


_ROUTER_PROMPT = """
You are B+DLLM intent router for an autonomous coding assistant.
Input JSON has: user_message, user_profile, recent_context, persona_policy.

Output strictly one JSON object with fields:
- action: one of [CHAT, ASK_CLARIFY, TOOL_LIGHT, EXECUTE_LIGHT, EXECUTE_HEAVY]
- scope: one of [MAIN, PROJECT_ONLY, ISOLATED, VM, LOBSTER]
- needs_confirm: boolean
- reason: short reason in <= 30 words
- confidence: 0~1 float

Hard rules:
1) Any write/delete/external-send/login/permission/cost/privacy sensitive action must set needs_confirm=true.
2) If input lacks critical slots for requested execution, prefer ASK_CLARIFY.
3) This is intent-level routing only. Never choose concrete tool names.
4) If uncertain, prefer CHAT or ASK_CLARIFY with low confidence.
""".strip()


def route_intent(
    *,
    user_message: str,
    user_profile: Optional[Dict[str, Any]] = None,
    recent_context: Optional[Dict[str, Any]] = None,
    persona_policy: Optional[Dict[str, Any]] = None,
    llm_client: Optional[Any] = None,
) -> RouterOutput:
    msg = str(user_message or "").strip()
    if not msg:
        return RouterOutput.fallback("empty_message")

    payload = {
        "user_message": msg,
        "user_profile": dict(user_profile or {}),
        "recent_context": dict(recent_context or {}),
        "persona_policy": dict(persona_policy or {}),
    }

    client = llm_client
    if client is None:
        return _heuristic_fallback(msg, reason="router_no_client")
    try:
        raw = client.chat(
            messages=[
                {"role": "system", "content": _ROUTER_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.1,
            max_tokens=240,
        )
        obj = _extract_json(raw)
        if not isinstance(obj, dict):
            return _heuristic_fallback(msg, reason="invalid_json")
        return _normalize(obj)
    except Exception:
        return _heuristic_fallback(msg, reason="router_llm_unavailable")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass

    l = s.find("{")
    r = s.rfind("}")
    if l < 0 or r <= l:
        return None
    try:
        return json.loads(s[l : r + 1])
    except Exception:
        return None


def _normalize(obj: Dict[str, Any]) -> RouterOutput:
    action = str(obj.get("action") or "").strip().upper()
    scope = str(obj.get("scope") or "").strip().upper()
    if action not in {x.value for x in RouterAction}:
        action = RouterAction.ASK_CLARIFY.value
    if scope not in {x.value for x in RouterScope}:
        scope = RouterScope.MAIN.value
    try:
        confidence = float(obj.get("confidence") or 0.0)
    except Exception:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reason = str(obj.get("reason") or "")[:240]
    needs_confirm = bool(obj.get("needs_confirm") or False)
    if action in {RouterAction.EXECUTE_LIGHT.value, RouterAction.EXECUTE_HEAVY.value} and _is_sensitive_reason(reason):
        needs_confirm = True
    return RouterOutput(
        action=action,
        scope=scope,
        needs_confirm=needs_confirm,
        reason=reason or "normalized",
        confidence=confidence,
    )


def _is_sensitive_reason(text: str) -> bool:
    low = str(text or "").lower()
    keys = ["write", "delete", "send", "login", "permission", "cost", "privacy", "外发", "写入", "删除"]
    return any(k in low for k in keys)


def _heuristic_fallback(msg: str, reason: str) -> RouterOutput:
    low = msg.lower()
    needs_confirm = any(k in low for k in ["删除", "删掉", "drop", "rm ", "write", "覆盖", "发送", "login", "授权", "付费", "隐私"])
    if any(k in low for k in ["不确定", "啥", "怎么", "clarify", "请问", "哪个"]):
        action = RouterAction.ASK_CLARIFY.value
    elif any(k in low for k in ["执行", "run", "修复", "改", "生成补丁"]):
        action = RouterAction.EXECUTE_HEAVY.value if any(k in low for k in ["全量", "所有", "entire", "全仓", "系统级"]) else RouterAction.EXECUTE_LIGHT.value
    elif any(k in low for k in ["搜索", "查", "lookup", "find"]):
        action = RouterAction.TOOL_LIGHT.value
    else:
        action = RouterAction.CHAT.value

    scope = RouterScope.MAIN.value
    if any(k in low for k in ["项目", "repo", "workspace", "工程"]):
        scope = RouterScope.PROJECT_ONLY.value
    if any(k in low for k in ["隔离", "sandbox", "isolated"]):
        scope = RouterScope.ISOLATED.value
    if any(k in low for k in ["vm", "虚拟机"]):
        scope = RouterScope.VM.value
    return RouterOutput(action=action, scope=scope, needs_confirm=needs_confirm, reason=reason, confidence=0.42)


def as_router_dict(output: RouterOutput) -> Dict[str, Any]:
    return asdict(output)
