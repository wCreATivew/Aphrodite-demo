from __future__ import annotations

from typing import Dict, Optional


def build_system_prompt_sections(
    *,
    persona: Optional[str] = None,
    style: Optional[str] = None,
    safety: Optional[str] = None,
    response_rules: Optional[str] = None,
) -> Dict[str, str]:
    return {
        "persona": (persona or "你是 Aphrodite，一个温柔、稳定、共情的陪伴型助手。").strip(),
        "style": (
            style
            or "使用简短、温暖、实用的中文表达。先共情，再给一个具体可执行的小步骤。"
        ).strip(),
        "safety": (
            safety
            or "避免有害建议。若用户出现高风险倾向，优先建议立即寻求人类或专业支持。"
        ).strip(),
        "response_rules": (
            response_rules
            or "保持自然纯文本，不使用 emoji 与花哨符号。必要时最多只问一个澄清问题，语气稳定尊重。"
        ).strip(),
    }


def render_system_prompt(sections: Dict[str, str]) -> str:
    ordered_keys = ["persona", "style", "safety", "response_rules"]
    lines = []
    for key in ordered_keys:
        value = str(sections.get(key, "")).strip()
        if not value:
            continue
        lines.append(f"[{key}]\n{value}")
    return "\n\n".join(lines).strip()
