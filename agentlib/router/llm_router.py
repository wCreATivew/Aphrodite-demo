from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from agentlib.coach import Coach
from .fast_gate import FastGate


VALID_SCOPES = {"MAIN", "PROJECT_ONLY", "ISOLATED", "VM", "LOBSTER"}


ROUTER_PROMPT = """Hard Clarify Gate（最高优先级）
当用户在委托任务（request=true）且满足任一条件时，必须 action=ASK_CLARIFY：
- 目标不明确：看不出要交付什么结果（输出物/改变什么/解决什么）
- 对象不明确：看不出要针对哪个对象开始（哪段内容/哪个问题/哪个系统对象）
并且在该情况下，不允许选择 CHAT 或 TOOL_LIGHT 作为替代。
ASK_CLARIFY 时只问一个问题（目标优先，其次对象）。

Router 决策顺序（stateless）：
Step 1：判断是否为任务委托。
Step 2（MSI / Hard Clarify）：
仅当无法采取任何低风险第一步且无法提出1–2个可选方向时，才 action=ASK_CLARIFY；否则继续判断是否改变外部状态以区分 EXECUTE vs TOOL。
Step 3：判断是否会改变外部状态（EXECUTE vs TOOL）。
Step 4：scope 保守判定（信息不足默认 MAIN）。
Step 5：高影响操作 needs_confirm=true。
"""


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
    """Stateless router: delegate intent -> MSI -> execute/tool -> scope -> confirm.

    Prompt policy reference: see ROUTER_PROMPT.
    """

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

        gate = self.fast_gate.infer(text)
        if str(gate.request_type or "") == "emotional_support":
            return RouterOutput("CHAT", "MAIN", False, "fast_gate_emotional_support", 0.9)

        is_task = self._is_task_delegation(text)
        if not is_task:
            return RouterOutput("CHAT", "MAIN", False, "fast_gate_stay_chat", 0.86)

        # no-early-return path for task requests
        hard_reason = self._hard_clarify_reason(text)
        needs_clarify = (hard_reason is not None) or self._is_insufficient_info(text)
        can_low_risk_first_step = self._can_safe_start(text) or self._can_offer_options(text)
        world_change = self._is_execute_task(text)
        impact_high = self._is_high_impact_execute(text)

        scope = self._infer_scope(text)
        needs_confirm = self._needs_confirm(text=text, world_change=world_change, impact_high=impact_high)
        if needs_clarify and (not can_low_risk_first_step):
            out = self._clarify_output(reason="insufficient_info_hard_rule", confidence=0.78)
        elif impact_high and world_change:
            out = RouterOutput("EXECUTE_HEAVY", scope, needs_confirm, "need_act_execute_heavy", 0.88)
        elif world_change:
            out = RouterOutput("EXECUTE_LIGHT", scope, needs_confirm, "need_act_execute_light", 0.82)
        else:
            out = RouterOutput("TOOL_LIGHT", scope, False, "need_act_tool_light", 0.8)

        if out.action in {"EXECUTE_LIGHT", "EXECUTE_HEAVY", "TOOL_LIGHT"}:
            coach_decision = self.coach.decide(text, out.action, self._required_tools(text, out.action))
            out.reason = f"{out.reason};coach_mode={coach_decision.mode};gap={coach_decision.gap:.2f}"
        return out

    def _decide_chat_route(self, text: str) -> tuple[bool, str]:
        gate = self.fast_gate.infer(text)
        if str(gate.request_type or "") == "emotional_support":
            return True, "emotional_support"
        is_task = self._is_task_delegation(text)
        return (not is_task), ("task" if is_task else str(gate.request_type or "unknown"))

    def _decide_non_chat_reply(self, text: str) -> RouterOutput:
        # Step 2: task startability (missing goal/object -> clarify)
        if self._is_insufficient_info(text):
            return self._clarify_output(reason="insufficient_info_hard_rule", confidence=0.74)

        # Step 3: external state change => execute_light; content generation => tool_light
        scope = self._infer_scope(text)
        if self._is_execute_task(text):
            # Step 4: high impact escalation
            if self._is_high_impact_execute(text):
                return RouterOutput("EXECUTE_HEAVY", scope, True, "need_act_execute_heavy", 0.88)
            return RouterOutput("EXECUTE_LIGHT", scope, False, "need_act_execute_light", 0.82)

        return RouterOutput("TOOL_LIGHT", scope, False, "need_act_tool_light", 0.8)

    @staticmethod
    def _clarify_output(*, reason: str, confidence: float) -> RouterOutput:
        return RouterOutput(
            action="ASK_CLARIFY",
            scope="MAIN",
            needs_confirm=False,
            reason=reason,
            confidence=max(0.0, min(1.0, float(confidence))),
        )

    @staticmethod
    def _has_goal(text: str) -> bool:
        low = str(text or "").lower()
        return bool(
            re.search(
                r"(帮我|请你|请帮|想让你|想要你|我想让|希望你|需要你|能不能|可以不可以|帮忙|修|改|排查|分析|总结|整理|生成|写|制定|执行|运行|安装|配置|看看|想想办法|解决)",
                low,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _has_object(text: str) -> bool:
        low = str(text or "").lower()
        return bool(
            re.search(
                r"(项目|仓库|repo|代码|文件|目录|路径|系统|配置|脚本|环境|任务|bug|报错|程序|agent|模型|提示词|音轨|流程|文案|评测|分支|触发器|计划|方案|视频)",
                low,
                re.IGNORECASE,
            )
        )


    @staticmethod
    def _has_concrete_anchor(text: str) -> bool:
        low = str(text or "").lower()
        return bool(
            re.search(
                r"(文件|目录|路径|仓库|repo|项目|模块|接口|页面|报错|bug|配置|脚本|测试|日志|视频|分支|环境)",
                low,
                re.IGNORECASE,
            )
        )

    def _can_offer_options(self, text: str) -> bool:
        low = str(text or "").lower()
        # If user asks for ideas/plan/content, we can usually offer 1-2 directions safely.
        return bool(
            re.search(
                r"(给个思路|计划|总结|解释|文案|模板|标题|标签|以后|自己发现问题)",
                low,
                re.IGNORECASE,
            )
        )

    def _should_soft_clarify(self, text: str) -> bool:
        # Clarify only when neither safe first-step nor option-proposal is possible.
        return (not self._can_safe_start(text)) and (not self._can_offer_options(text))

    def _hard_clarify_reason(self, text: str) -> Optional[str]:
        low = str(text or "").lower()
        has_goal = self._has_goal(text)
        has_object = self._has_object(text)

        # Irreplaceable: execute-like intent without concrete object.
        execute_like = bool(
            re.search(r"(修复|修一下|修改|改动|弄|搞|处理|提交|推送|push|merge|部署|运行|执行|安装|配置|重启|应用|创建|删除|覆盖|写入|排查|调试)", low, re.IGNORECASE)
        )
        if execute_like and (not has_object):
            return "hard_clarify_missing_object"

        # Irreplaceable: pure deictic request, no concrete target.
        deictic_only = bool(re.search(r"^(这个|那个|它|这事|那事|你看看这个)[。？！!?. ]*$", low))
        if deictic_only and (not has_object):
            return "hard_clarify_missing_object"

        onboarding_or_capability_request = bool(
            re.search(r"(不太会|一步步带我做|睡觉的时候自己学习|学会.*运用工具|最轻松的解决办法)", low, re.IGNORECASE)
        )
        if onboarding_or_capability_request:
            return "hard_clarify_missing_object"

        # If both goal/object are missing and we also cannot safely start or offer options.
        if (not has_goal) and (not has_object) and self._should_soft_clarify(text):
            return "hard_clarify_missing_goal"

        # Goal exists but no concrete anchor, and not an immediately actionable execute flow.
        no_anchor = not self._has_concrete_anchor(text)
        if has_goal and no_anchor and self._should_soft_clarify(text):
            return "hard_clarify_missing_object"
        return None

    def _can_safe_start(self, text: str) -> bool:
        low = str(text or "").lower()
        return bool(
            re.search(r"(总结|解释|给出思路|列出|对比|建议|计划|模板|先给方案|先分析)", low, re.IGNORECASE)
        )

    def _is_task_delegation(self, text: str) -> bool:
        if not str(text or "").strip():
            return False
        low = str(text or "").lower()
        emotional = bool(re.search(r"(焦虑|难过|崩溃|不想做事|陪我|安慰)", low, re.IGNORECASE))
        if emotional and not self._has_goal(text):
            return False
        if re.search(r"^我刚刚说.*这次", low, re.IGNORECASE):
            return False
        if self._has_goal(text):
            return True
        vague_issue = bool(
            re.search(r"(这个有点不太对劲|这个是不是有问题|这个能不能做得更好一点|你觉得怎么样|有点怪|说不上来|一部分不是我想要的)", low, re.IGNORECASE)
        )
        if vague_issue:
            return True
        if re.search(r"(有一部分.*不是我想要的)", low, re.IGNORECASE):
            return True
        has_action_verb = bool(re.search(r"(修|改|排查|运行|安装|配置|总结|生成|写|制定|优化)", low, re.IGNORECASE))
        if bool(re.search(r"(系统.*慢|性能.*慢|太慢了)", low, re.IGNORECASE)):
            return True
        return has_action_verb and self._has_object(text)

    def _is_execute_task(self, text: str) -> bool:
        low = str(text or "").lower()
        state_change = bool(
            re.search(
                r"(修复|修一下|修改|改|改动|提交|推送|push|merge|部署|运行|执行|安装|配置|重启|应用|创建|删除|覆盖|写入|排查|调试|审计|检查|扫描|隐患|风险|自动化|迭代)",
                low,
                re.IGNORECASE,
            )
        )
        pure_generation = bool(
            re.search(r"(总结|写文案|文案|标题|标签|计划|解释|提纲|草稿|模板|复述|概念)", low, re.IGNORECASE)
        )
        if state_change and not pure_generation:
            return True
        diagnosis_workload = bool(
            re.search(r"(系统|项目|agent|仓库).*(慢|隐患|风险|问题|报错)", low, re.IGNORECASE)
        )
        return diagnosis_workload

    @staticmethod
    def _is_high_impact_execute(text: str) -> bool:
        low = str(text or "").lower()
        return bool(
            re.search(
                r"(删除|覆盖|发布|批量|自动化流程|自动迭代|跨系统|sudo|rm\s+-rf|deploy|merge.*main|合并分支|提交并推送|push.*main)",
                low,
                re.IGNORECASE,
            )
        )

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
        if re.search(r"(沙盒|隔离|isolated|vm|virtual machine)", low, re.IGNORECASE):
            return "ISOLATED"
        if re.search(r"(项目|仓库|repo|本地代码|代码库|文件|目录|路径|git)", low, re.IGNORECASE):
            return "PROJECT_ONLY"
        return "MAIN"

    @staticmethod
    def _scope_or_rollback_uncertain(text: str) -> bool:
        low = str(text or "").lower()
        explicitly_irreversible = bool(
            re.search(r"(不可逆|无法回滚|删除|覆盖|发布|批量|跨系统|push|merge|deploy)", low, re.IGNORECASE)
        )
        if explicitly_irreversible:
            return True

        read_only_intent = bool(
            re.search(r"(看一下|检查|扫描|审计|评估|总结|分析|查看|诊断)", low, re.IGNORECASE)
        )
        mutating_intent = bool(
            re.search(r"(修改|改动|写入|安装|配置|应用|提交|推送|merge|deploy|删除|覆盖)", low, re.IGNORECASE)
        )
        if read_only_intent and (not mutating_intent):
            return False

        explicitly_limited_and_rollbackable = bool(
            re.search(
                r"(仅|只|单个|一处|指定|这个文件|该文件|dry-run|演练|预览|不落盘|不提交|不推送|可回滚|可撤销|先模拟|更.*一点|调得)",
                low,
                re.IGNORECASE,
            )
        )
        if explicitly_limited_and_rollbackable:
            return False

        # Conservative default: if rollback/scope is unclear, treat as confirm-needed.
        return True

    @classmethod
    def _needs_confirm(cls, *, text: str, world_change: bool, impact_high: bool) -> bool:
        if impact_high:
            return True
        if world_change and cls._scope_or_rollback_uncertain(text):
            return True
        return False

    def _is_insufficient_info(self, user_message: str) -> bool:
        text = str(user_message or "").strip()
        if not text:
            return True
        if len(text) <= 4:
            return True

        low = text.lower()
        # Keep only strict non-actionable minimal utterances as insufficient.
        pronoun_only = bool(re.search(r"^(这个|那个|它|这事|那事|有点怪|不太对劲|你看看这个)[。？！!?. ]*$", low))
        if pronoun_only:
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
