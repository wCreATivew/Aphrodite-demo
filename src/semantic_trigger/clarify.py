from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_SLOT_QUESTIONS = {
    "time": "你希望我什么时候提醒你？",
    "date": "你希望我哪天处理这件事？",
    "contact": "你想发给谁？",
    "recipient": "你想发给谁？",
    "receiver": "你想发给谁？",
    "content": "你希望我发送什么内容？",
    "message": "你希望我发送什么内容？",
    "location": "你要在哪个地点执行这件事？",
    "intent": "你希望邮件表达什么目的？",
    "target_lang": "你想翻译成哪种语言？",
    "text": "请提供需要处理的原文内容。",
    "query": "你希望我搜索什么关键词？",
    "repeat": "是否需要重复提醒？例如每天或工作日。",
}
_SLOT_LABELS = {
    "time": "时间",
    "date": "日期",
    "contact": "联系人",
    "recipient": "收件人",
    "receiver": "收件人",
    "content": "内容",
    "message": "内容",
    "location": "地点",
    "intent": "邮件目的",
    "target_lang": "目标语言",
    "text": "原文",
    "query": "关键词",
    "repeat": "重复规则",
}
_SLOT_EXAMPLES = {
    "time": "例如：明天上午9点、今晚8点",
    "date": "例如：明天、下周一",
    "recipient": "例如：张三、Alex",
    "contact": "例如：张三、Alex",
    "content": "例如：提醒我开会、我晚点到",
    "message": "例如：我晚点到、请明早确认",
    "intent": "例如：请假申请、项目延期说明",
    "target_lang": "例如：英文、日语",
    "text": "例如：把要处理的原文贴上来",
    "location": "例如：北京、San Francisco",
}


def build_clarification_payload(
    trigger_def: Any,
    missing_slots: Iterable[str],
    *,
    extracted_slots: Optional[Dict[str, Any]] = None,
    query: str = "",
    candidate_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    trigger_id, trigger_name = _trigger_identity(trigger_def)
    slots = _normalize_slots(missing_slots)
    return {
        "trigger_id": trigger_id,
        "trigger_name": trigger_name,
        "missing_slots": slots,
        "missing_slot_labels": [_SLOT_LABELS.get(s, s) for s in slots],
        "slot_examples": {s: _SLOT_EXAMPLES.get(s, "") for s in slots},
        "clarification_question": build_clarification_question(
            trigger_def,
            slots,
            extracted_slots=extracted_slots,
            query=query,
            candidate_names=candidate_names,
        ),
    }


def build_clarification_question(
    trigger_def_or_missing_slots: Any,
    missing_slots: Optional[Iterable[str]] = None,
    *,
    extracted_slots: Optional[Dict[str, Any]] = None,
    query: str = "",
    selected_trigger: str = "",
    candidate_names: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """
    Compatibility:
    - New API: build_clarification_question(trigger_def, missing_slots, ...)
    - Old API: build_clarification_question(missing_slots, selected_trigger=..., candidate_names=...)
    """
    trigger_def, slots = _resolve_call_shape(trigger_def_or_missing_slots, missing_slots)
    trigger_id, _ = _trigger_identity(trigger_def)
    if not trigger_id:
        trigger_id = str(selected_trigger or "").strip()

    names = [str(x).strip() for x in (candidate_names or []) if str(x).strip()]
    extracted = dict(extracted_slots or {})
    _ = str(query or "").strip()

    if not slots:
        if len(names) >= 2:
            return f"我理解成两个方向：{names[0]} 或 {names[1]}。你更想要哪一个？"
        if len(names) == 1:
            return f"我需要再确认一下，你是要执行「{names[0]}」吗？"
        return None

    templated = _template_question(trigger_id=trigger_id, slots=slots, extracted_slots=extracted)
    if templated:
        return templated

    if len(slots) > 1:
        details: List[str] = []
        for slot in slots[:3]:
            label = _SLOT_LABELS.get(slot, slot)
            ex = _SLOT_EXAMPLES.get(slot, "")
            details.append(f"{label}{('（' + ex + '）') if ex else ''}")
        return "为了减少来回确认，我一次问全：请补充" + "、".join(details) + "。"

    for slot in slots:
        if slot in _SLOT_QUESTIONS:
            ex = _SLOT_EXAMPLES.get(slot, "")
            return f"{_SLOT_QUESTIONS[slot]} {ex}".strip()
    return f"我还缺少一些必要信息：{', '.join(slots)}。"


def build_clarification_question_v2(
    *,
    missing_slots: Iterable[str],
    candidate_names: Optional[Sequence[str]] = None,
    missing_slot_reasons: Optional[dict[str, str]] = None,
) -> Optional[str]:
    slots = _normalize_slots(missing_slots)
    if slots:
        if len(slots) == 1:
            slot = slots[0]
            if slot in _SLOT_QUESTIONS:
                return f"{_SLOT_QUESTIONS[slot]} {_SLOT_EXAMPLES.get(slot, '')}".strip()
            label = _SLOT_LABELS.get(slot, slot)
            hint = ""
            if missing_slot_reasons and slot in missing_slot_reasons:
                reason = str(missing_slot_reasons.get(slot) or "").strip()
                if reason:
                    hint = f"（{reason}）"
            return f"请补充必要信息：{label}{hint}。"
        if len(slots) == 2:
            left = _SLOT_LABELS.get(slots[0], slots[0])
            right = _SLOT_LABELS.get(slots[1], slots[1])
            return f"我还需要两个信息：{left} 和 {right}，请补充后我再执行。"
        return "我还缺少多个必要信息，请再具体一点（例如时间、对象、内容）。"

    names = [str(x).strip() for x in (candidate_names or []) if str(x).strip()]
    if len(names) >= 2:
        return f"你是想要“{names[0]}”还是“{names[1]}”？"
    if len(names) == 1:
        return f"我理解可能是“{names[0]}”，但还需要你补充一点细节。"
    return "我还缺少一些必要信息，你可以再具体一点吗？"


def _normalize_slots(missing_slots: Iterable[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for raw in missing_slots or []:
        slot = str(raw).strip().lower()
        if not slot or slot in seen:
            continue
        seen.add(slot)
        out.append(slot)
    return out


def _resolve_call_shape(trigger_def_or_missing_slots: Any, missing_slots: Optional[Iterable[str]]) -> Tuple[Any, List[str]]:
    if missing_slots is not None:
        return trigger_def_or_missing_slots, _normalize_slots(missing_slots)
    if isinstance(trigger_def_or_missing_slots, (list, tuple, set)):
        return None, _normalize_slots(trigger_def_or_missing_slots)
    return trigger_def_or_missing_slots, []


def _trigger_identity(trigger_def: Any) -> Tuple[str, str]:
    if trigger_def is None:
        return "", ""
    if isinstance(trigger_def, dict):
        return str(trigger_def.get("trigger_id") or "").strip(), str(trigger_def.get("name") or "").strip()
    return str(getattr(trigger_def, "trigger_id", "") or "").strip(), str(getattr(trigger_def, "name", "") or "").strip()


def _template_question(*, trigger_id: str, slots: List[str], extracted_slots: Dict[str, Any]) -> Optional[str]:
    sid = str(trigger_id or "").strip().lower()
    slot_set = set(slots)

    if sid in {"set_reminder", "set_alarm"}:
        if {"time", "content"}.issubset(slot_set):
            return "我可以马上帮你设提醒，还差两个信息：时间和提醒内容。时间可选明天上午/下午/晚上。"
        if "time" in slot_set:
            content = str(extracted_slots.get("content") or "").strip()
            if content:
                return f"我已记下提醒内容“{content}”，还需要提醒时间（例如明天上午9点）。"
            return "还需要提醒时间（例如明天上午9点、今晚8点）。"
        if "content" in slot_set:
            time_val = str(extracted_slots.get("time") or "").strip()
            if time_val:
                return f"时间我记为“{time_val}”，还要补充提醒内容（例如：提醒我交周报）。"
            return "还需要提醒内容（例如：提醒我交周报）。"

    if sid == "send_message":
        if {"recipient", "content"}.issubset(slot_set):
            return "我可以帮你发消息，请一次补充：发给谁 + 发送内容（例如：发给张三：我晚点到）。"
        if "recipient" in slot_set:
            return "你想把消息发给谁？（例如：张三、Alex）"
        if "content" in slot_set or "message" in slot_set:
            target = str(extracted_slots.get("recipient") or extracted_slots.get("contact") or "").strip()
            if target:
                return f"收件人我记为“{target}”，请补充消息内容。"
            return "请补充你要发送的具体内容。"

    if sid == "email_draft":
        if {"recipient", "intent"}.issubset(slot_set):
            return "我可以起草邮件，请补充：收件人和邮件目的（如请假申请/延期说明）。"
        if "recipient" in slot_set:
            return "这封邮件要发给谁？（例如：HR、经理）"
        if "intent" in slot_set:
            return "这封邮件想表达什么目的？（例如：请假申请、项目延期说明）"

    if sid == "calendar_query":
        if "date" in slot_set:
            return "你想查哪天的日程？（例如：今天、明天、下周一）"
        return "你要查日程还是空闲时间？可以直接说“查明天下午日程”。"

    return None
