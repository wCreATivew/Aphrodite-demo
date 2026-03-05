from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence


VALID_ACTIONS = {"CHAT", "ASK_CLARIFY", "TOOL_LIGHT", "EXECUTE_LIGHT", "EXECUTE_HEAVY"}
VALID_SCOPES = {"MAIN", "PROJECT_ONLY", "ISOLATED", "VM", "LOBSTER"}


@dataclass
class RouterOutput:
    action: str
    scope: str
    needs_confirm: bool
    reason: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LLMRouter:
    """Intent-level router only. Tool-level decisions are left to planner/tool registry."""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self.llm_client = llm_client

    @staticmethod
    def build_prompt(
        *,
        user_message: str,
        user_profile: Optional[Dict[str, Any]] = None,
        recent_context: Optional[Sequence[str]] = None,
        persona_policy: str = "",
    ) -> str:
        profile = user_profile or {}
        context = list(recent_context or [])[-6:]
        return (
            "你是意图路由器。只做意图级路由，不做工具级选择。\\n"
            "输出严格JSON，字段: action, scope, needs_confirm, reason, confidence。\\n"
            "action 只能是: CHAT/ASK_CLARIFY/TOOL_LIGHT/EXECUTE_LIGHT/EXECUTE_HEAVY。\\n"
            "scope 只能是: MAIN/PROJECT_ONLY/ISOLATED/VM/LOBSTER。\\n"
            "当涉及写入/删除/外发/登录/权限/费用/隐私操作时，needs_confirm 必须为 true。\\n"
            f"persona_policy={persona_policy or ''}\\n"
            f"user_profile={json.dumps(profile, ensure_ascii=False)}\\n"
            f"recent_context={json.dumps(context, ensure_ascii=False)}\\n"
            f"user_message={user_message}"
        )

    def route(
        self,
        *,
        user_message: str,
        user_profile: Optional[Dict[str, Any]] = None,
        recent_context: Optional[Sequence[str]] = None,
        persona_policy: str = "",
    ) -> RouterOutput:
        prompt = self.build_prompt(
            user_message=user_message,
            user_profile=user_profile,
            recent_context=recent_context,
            persona_policy=persona_policy,
        )
        raw = None
        if self.llm_client is not None and hasattr(self.llm_client, "chat"):
            try:
                raw = self.llm_client.chat(prompt)
            except Exception:
                raw = None
        if isinstance(raw, str) and raw.strip():
            parsed = self._parse_json_output(raw)
            if parsed is not None:
                return parsed
        return self._heuristic_route(user_message)

    def _parse_json_output(self, raw: str) -> Optional[RouterOutput]:
        try:
            obj = json.loads(raw)
        except Exception:
            return None
        action = str(obj.get("action") or "").strip().upper()
        scope = str(obj.get("scope") or "").strip().upper()
        if action not in VALID_ACTIONS or scope not in VALID_SCOPES:
            return None
        needs_confirm = bool(obj.get("needs_confirm", False))
        reason = str(obj.get("reason") or "")
        try:
            confidence = float(obj.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        # hard safety correction
        if self._looks_sensitive_action(reason + " " + action + " " + scope):
            needs_confirm = True
        return RouterOutput(action=action, scope=scope, needs_confirm=needs_confirm, reason=reason, confidence=confidence)

    def _heuristic_route(self, user_message: str) -> RouterOutput:
        text = str(user_message or "").strip()
        low = text.lower()

        sensitive = self._looks_sensitive_action(text)
        project_like = bool(re.search(r"(项目|仓库|代码|bug|测试|py|git|repo|compile|build|修复|调试)", low, re.IGNORECASE))
        env_like = bool(re.search(r"(安装|配置环境|docker|vm|虚拟机|sandbox|isolated|隔离)", low, re.IGNORECASE))
        ask_plan = bool(re.search(r"(计划|总结|解释|建议|方案|写一个|生成)", low, re.IGNORECASE))
        execute = bool(re.search(r"(执行|运行|修改|修复|提交|push|安装|启动|自动|迭代|删除)", low, re.IGNORECASE))
        unclear = len(text) < 5 or bool(re.search(r"(随便|你看着办|不知道|不确定)", low, re.IGNORECASE))

        scope = "PROJECT_ONLY" if project_like else "MAIN"
        if env_like:
            scope = "ISOLATED"

        if unclear:
            action = "ASK_CLARIFY"
            conf = 0.62
        elif execute and sensitive:
            action = "EXECUTE_HEAVY"
            conf = 0.84
        elif execute:
            action = "EXECUTE_LIGHT"
            conf = 0.78
        elif ask_plan:
            action = "TOOL_LIGHT"
            conf = 0.74
        else:
            action = "CHAT"
            conf = 0.70

        return RouterOutput(
            action=action,
            scope=scope,
            needs_confirm=bool(sensitive),
            reason="heuristic_fallback",
            confidence=conf,
        )

    @staticmethod
    def _looks_sensitive_action(text: str) -> bool:
        low = str(text or "").lower()
        patterns = (
            r"写入|删除|外发|发给|登录|权限|付费|费用|隐私|token|apikey|账号|password",
            r"write|delete|remove|send out|publish|login|permission|billing|payment|privacy|secret|credential",
            r"push|commit|merge|deploy|install|sudo|rm\s+-rf",
        )
        return any(re.search(p, low, re.IGNORECASE) for p in patterns)


class RouterStateMachine:
    """Gate execution scopes that require explicit confirmation."""

    restricted_scopes = {"PROJECT_ONLY", "ISOLATED", "VM", "LOBSTER"}
    executable_actions = {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}

    def apply(self, route: RouterOutput, *, confirmed: bool = False) -> RouterOutput:
        if route.scope in self.restricted_scopes and route.action in self.executable_actions:
            if route.needs_confirm and not bool(confirmed):
                return RouterOutput(
                    action="ASK_CLARIFY",
                    scope="MAIN",
                    needs_confirm=True,
                    reason="confirm_required_gate",
                    confidence=max(0.0, min(1.0, route.confidence)),
                )
        return route
