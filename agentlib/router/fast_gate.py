from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FastGateOutput:
    route: str  # CHAT | EXECUTE
    request: bool
    request_type: str  # task | emotional_support | unknown


class FastGate:
    """Ultra-fast gate: only decide whether user is requesting action."""

    def infer(self, user_message: str) -> FastGateOutput:
        text = str(user_message or "").strip()
        low = text.lower()
        if not text:
            return FastGateOutput(route="CHAT", request=False, request_type="unknown")

        emotional_support = bool(
            re.search(r"(安慰我|陪我聊聊|陪我说说话|鼓励我|我好难过|我很烦|情绪支持)", low, re.IGNORECASE)
        )
        if emotional_support:
            return FastGateOutput(route="CHAT", request=True, request_type="emotional_support")

        task_request = bool(
            re.search(
                r"(帮我|请你|请帮|生成|总结|排查|修复|配置|安装|执行|运行|写代码|写脚本|改|优化|做个|给我一个)",
                low,
                re.IGNORECASE,
            )
        )
        if task_request:
            return FastGateOutput(route="EXECUTE", request=True, request_type="task")

        emotion_only = bool(
            re.search(r"(好累|很烦|不想写代码|焦虑|崩溃|难受|没状态|压力大)", low, re.IGNORECASE)
        )
        if emotion_only:
            return FastGateOutput(route="CHAT", request=False, request_type="unknown")

        return FastGateOutput(route="CHAT", request=False, request_type="unknown")
