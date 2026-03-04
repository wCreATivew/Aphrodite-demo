from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ToolDecision:
    use_tool: bool
    tool_name: Optional[str] = None
    query: str = ""
    reason: str = ""


def simple_tool_router(user_text: str, allow_web: bool = False) -> ToolDecision:
    """
    Conservative router:
    - Only suggests web search when explicitly asked and allow_web=True.
    """
    t = (user_text or "").strip().lower()
    if not t:
        return ToolDecision(use_tool=False, reason="empty")

    web_triggers = ["搜索", "查一下", "查找", "资料", "最新", "新闻", "链接", "来源", "引用"]
    if allow_web and any(k in t for k in web_triggers):
        return ToolDecision(use_tool=True, tool_name="web_search", query=user_text, reason="explicit_web")

    return ToolDecision(use_tool=False, reason="no_tool")
