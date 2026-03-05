from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from agentlib.coach import Coach
from .fast_gate import FastGate


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
    """FastGate first; Coach only for execute flow. Keep routing minimal and deterministic."""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self.llm_client = llm_client  # retained for API compatibility
        self.fast_gate = FastGate()
        self.coach = Coach()

    def route(
        self,
        *,
        user_message: str,
        user_profile: Optional[Dict[str, Any]] = None,
        recent_context: Optional[List[str]] = None,
        persona_policy: str = "",
    ) -> RouterOutput:
        _ = user_profile, recent_context, persona_policy
        text = str(user_message or "").strip()
        stay_chat, request_type = self._decide_chat_route(text)
        if stay_chat:
            if request_type == "emotional_support":
                return RouterOutput("CHAT", "MAIN", False, "fast_gate_emotional_support", 0.9)
            return RouterOutput("CHAT", "MAIN", False, "fast_gate_stay_chat", 0.85)

        # Non-chat branch: decide which kind of reply/action is needed.
        out = self._decide_non_chat_reply(text)
        if out.action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY", "TOOL_LIGHT"}:
            coach_decision = self.coach.decide(text, out.action, self._required_tools(text, out.action))
            out.reason = f"{out.reason};coach_mode={coach_decision.mode};gap={coach_decision.gap:.2f}"
        return out

    def _decide_chat_route(self, text: str) -> tuple[bool, str]:
        gate = self.fast_gate.infer(text)
        if str(gate.route or "").upper() == "CHAT":
            return True, str(gate.request_type or "unknown")
        return False, str(gate.request_type or "unknown")

    def _decide_non_chat_reply(self, text: str) -> RouterOutput:
        
        if self._is_insufficient_info(text):
            return self._clarify_output(reason="insufficient_info_hard_rule", confidence=0.72)

        out = self._classify_need_act(text)
        if out is None:
            out = RouterOutput(
                action="TOOL_LIGHT",
                scope=self._infer_scope(text),
                needs_confirm=False,
                reason="need_act_fallback_tool_light",
                confidence=0.6,
            )
        return out

    @staticmethod
    def _clarify_output(*, reason: str, confidence: float) -> RouterOutput:
        return RouterOutput(
            action="ASK_CLARIFY",
            scope="MAIN",
            needs_confirm=False,
            reason=reason,
            confidence=max(0.0, min(1.0, float(confidence))),
        )

    def _classify_need_act(self, user_message: str) -> Optional[RouterOutput]:
        text = str(user_message or "").strip()
        low = text.lower()
        scope = self._infer_scope(text)

        if re.search(r"(repo\s*修改|仓库.*修改|自动迭代|批量执行|运行评测|跑评测|合并分支|merge|提交并推送|push)", low, re.IGNORECASE):
            return RouterOutput("EXECUTE_HEAVY", scope, True, "need_act_execute_heavy", 0.86)

        if re.search(r"(改单个配置|单个配置|写一段脚本|一步命令|给个命令|只改|小改|改配置|排查|修一下|修复一下|配置这个环境)", low, re.IGNORECASE):
            return RouterOutput("EXECUTE_LIGHT", scope, self._looks_sensitive_action(text), "need_act_execute_light", 0.8)

        if re.search(r"(生成|整理|总结|写文案|润色|改写|提纲|草稿|计划|清单|标题|标签)", low, re.IGNORECASE):
            return RouterOutput("TOOL_LIGHT", "MAIN", False, "need_act_tool_light", 0.78)
        return None

    @staticmethod
    def _required_tools(text: str, action: str) -> List[str]:
        low = str(text or "").lower()
        tools: List[str] = ["planner"]
        if action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}:
            tools.append("filesystem")
        if re.search(r"(代码|仓库|bug|测试|脚本|py|git)", low, re.IGNORECASE):
            tools.append("code_expert")
        if re.search(r"(环境|安装|docker|vm|虚拟机)", low, re.IGNORECASE):
            tools.append("env_manager")
        if re.search(r"(页面|点击|界面|gui)", low, re.IGNORECASE):
            tools.append("gui_operator")
        return sorted(set(tools))

    @staticmethod
    def _infer_scope(text: str) -> str:
        low = str(text or "").lower()
        project_like = bool(re.search(r"(项目|仓库|代码|bug|测试|py|git|repo|compile|build|修复|调试)", low, re.IGNORECASE))
        env_like = bool(re.search(r"(安装|配置环境|docker|vm|虚拟机|sandbox|isolated|隔离)", low, re.IGNORECASE))
        scope = "PROJECT_ONLY" if project_like else "MAIN"
        if env_like:
            scope = "ISOLATED"
        if scope not in VALID_SCOPES:
            return "MAIN"
        return scope

    @staticmethod
    def _looks_sensitive_action(text: str) -> bool:
        low = str(text or "").lower()
        patterns = (
            r"写入|删除|外发|发给|登录|权限|付费|费用|隐私|token|apikey|账号|password",
            r"write|delete|remove|send out|publish|login|permission|billing|payment|privacy|secret|credential",
            r"push|commit|merge|deploy|install|sudo|rm\s+-rf",
        )
        return any(re.search(p, low, re.IGNORECASE) for p in patterns)

    @staticmethod
    def _is_insufficient_info(user_message: str) -> bool:
        text = str(user_message or "").strip()
        if not text:
            return True
        low = text.lower()
        if len(text) <= 6:
            return True
        if re.search(r"(不知道|不确定|说不上来|拿不准)", low, re.IGNORECASE):
            return True
        pronoun_hits = re.findall(r"(这个|那个|它|这|那|这样|那样|这边|那边|这事|那事)", text)
        has_object = bool(re.search(r"(代码|项目|文档|接口|页面|测试|任务|仓库|流程|配置|脚本|模型|数据)", low, re.IGNORECASE))
        has_goal = bool(re.search(r"(请|帮我|需要|想要|怎么|如何|能否|希望|解决|修复|实现|生成|总结|解释|分析)", low, re.IGNORECASE))
        if len(text) <= 14 and len(pronoun_hits) >= 1 and not has_object:
            return True
        if len(pronoun_hits) >= 2 and not has_object and not has_goal:
            return True
        return False


class RouterStateMachine:
    """Gate execution scopes that require explicit confirmation."""

    restricted_scopes = {"PROJECT_ONLY", "ISOLATED", "VM", "LOBSTER"}
    executable_actions = {"EXECUTE_LIGHT", "EXECUTE_HEAVY"}

    def __init__(self) -> None:
        self.state = "IDLE"

    def apply(self, route: RouterOutput, *, confirmed: bool = False) -> RouterOutput:
        self.state = "CLARIFYING" if route.action == "ASK_CLARIFY" else "READY"

        if route.scope in self.restricted_scopes and route.action in self.executable_actions:
            if route.needs_confirm and not bool(confirmed):
                self.state = "CLARIFYING"
                return RouterOutput(
                    action="ASK_CLARIFY",
                    scope="MAIN",
                    needs_confirm=True,
                    reason="confirm_required_gate",
                    confidence=max(0.0, min(1.0, route.confidence)),
                )
        return route
