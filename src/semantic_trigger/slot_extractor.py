from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from .schemas import SlotSpec, TriggerDef

TriggerLike = Union[TriggerDef, Dict[str, Any], None]


@dataclass(frozen=True)
class SlotExtractionResult:
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]
    reasons: List[str]

    @property
    def extracted(self) -> Dict[str, Any]:
        # Backward-compatible alias.
        return self.extracted_slots

    @property
    def missing_required(self) -> List[str]:
        # Backward-compatible alias.
        return self.missing_slots


@dataclass(frozen=True)
class SlotPipelineResult:
    extracted_slots: Dict[str, Any]
    missing_slots: List[str]
    constraint_ok: bool
    constraint_passed: List[str]
    constraint_failed: List[str]
    reasons: List[str]
    clarification_question: Optional[str] = None


def extract_slots(query: str, trigger_def: TriggerLike = None) -> SlotExtractionResult:
    """
    Public interface.

    Args:
        query: user query text.
        trigger_def: TriggerDef or dict-shaped trigger definition.

    Returns:
        SlotExtractionResult with `extracted_slots`, `missing_slots`, `reasons`.
    """
    return RuleSlotExtractor().extract(query=query, trigger=trigger_def)


def run_slot_pipeline(query: str, trigger_def: TriggerLike = None) -> SlotPipelineResult:
    """
    One-shot helper for parallel integration.

    Returns protocol-friendly fields in one call:
    - extracted_slots
    - missing_slots
    - constraint_ok / constraint_passed / constraint_failed
    - clarification_question
    """
    from .clarify import build_clarification_question
    from .constraints import validate_required_slots, validate_simple_constraints

    slot_result = extract_slots(query=query, trigger_def=trigger_def)
    missing_slots, missing_reasons = validate_required_slots(trigger_def, slot_result.extracted_slots)
    simple_ok, simple_passed, simple_failed = validate_simple_constraints(trigger_def, slot_result.extracted_slots)
    constraint_ok = (len(missing_slots) == 0) and simple_ok
    constraint_failed = list(simple_failed) + list(missing_reasons)
    clarification = build_clarification_question(
        trigger_def,
        missing_slots,
        extracted_slots=slot_result.extracted_slots,
        query=query,
    )

    return SlotPipelineResult(
        extracted_slots=dict(slot_result.extracted_slots),
        missing_slots=list(missing_slots),
        constraint_ok=bool(constraint_ok),
        constraint_passed=list(simple_passed),
        constraint_failed=constraint_failed,
        reasons=list(slot_result.reasons),
        clarification_question=clarification,
    )


class RuleSlotExtractor:
    def extract(self, query: str, trigger: TriggerLike = None) -> SlotExtractionResult:
        q = str(query or "").strip()
        extracted = self._extract_common_slots(q)
        reasons: List[str] = [f"slot:{k}=hit({v})" for k, v in extracted.items()]

        required_names, optional_names = _resolve_slot_names(trigger)
        for slot_name in required_names + optional_names:
            if slot_name in extracted:
                continue
            spec = SlotSpec(
                slot_name=slot_name,
                slot_type=_guess_slot_type(slot_name),
                required=(slot_name in required_names),
            )
            value = self._extract_one(q, spec)
            if value is None or value == "":
                reasons.append(f"slot:{slot_name}=miss")
                continue
            extracted[slot_name] = value
            reasons.append(f"slot:{slot_name}=hit({value})")

        missing = [name for name in required_names if name not in extracted]
        return SlotExtractionResult(
            extracted_slots=extracted,
            missing_slots=missing,
            reasons=reasons,
        )

    def _extract_common_slots(self, query: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        date_val = self._extract_one(query, SlotSpec(slot_name="date", slot_type="date", required=False))
        if date_val:
            out["date"] = date_val

        time_val = self._extract_one(query, SlotSpec(slot_name="time", slot_type="time", required=False))
        if time_val:
            out["time"] = time_val
            out["time_struct"] = _normalize_time_expression(str(time_val), query)

        contact_val = self._extract_one(query, SlotSpec(slot_name="contact", slot_type="string", required=False))
        if contact_val:
            out["contact"] = contact_val
            out.setdefault("recipient", contact_val)

        message_val = self._extract_one(query, SlotSpec(slot_name="message", slot_type="string", required=False))
        if message_val:
            out["message"] = message_val
            out.setdefault("content", message_val)

        location_val = self._extract_one(query, SlotSpec(slot_name="location", slot_type="location", required=False))
        if location_val:
            out["location"] = location_val
        return out

    def _extract_one(self, query: str, spec: SlotSpec) -> Any:
        q = str(query or "").strip()
        low = q.lower()
        st = spec.slot_type.lower().strip()
        name = spec.slot_name.lower().strip()

        if st == "time":
            m = re.search(
                r"((今天|明天|后天|今晚|明早|下午|上午|中午|傍晚|晚上)?\s*(\d{1,2}:\d{2}\s*(?:am|pm)?)|"
                r"(今天|明天|后天|今晚|明早|下午|上午|中午|傍晚|晚上)?\s*(\d{1,2}\s*(?:am|pm))|"
                r"(今天|明天|后天|今晚|明早|下午|上午|中午|傍晚|晚上)?\s*(\d{1,2}点半?)|"
                r"(今天|明天|后天|今晚|明早|下午|上午|中午|傍晚|晚上)?\s*([一二三四五六七八九十两]{1,3}点半?)|"
                r"(今天|明天|后天|今晚|明早|下午|上午|中午|傍晚|晚上)?\s*(\d{1,2}点\d{1,2}分?))",
                q,
                flags=re.I,
            )
            if m:
                return m.group(0).strip()
            if any(x in q for x in ["今天", "明天", "后天", "下午", "上午", "晚上", "今晚", "明早"]):
                return _extract_time_window(q)
            if any(x in low for x in ["today", "tomorrow", "tonight", "morning", "afternoon", "evening"]):
                return _extract_time_window(q)
            return None

        if st == "date":
            return _extract_date_token(q)

        if st == "location":
            m = re.search(r"(?:在|到|去)\s*([A-Za-z\u4e00-\u9fff]{2,30})", q)
            if m:
                return m.group(1).strip()
            m2 = re.search(r"\b(?:in|to)\s+([A-Za-z][A-Za-z\- ]{1,30})", low)
            return m2.group(1).strip() if m2 else None

        if st in {"string", "json"}:
            return self._extract_string_like(q, name)

        return None

    def _extract_string_like(self, query: str, slot_name: str) -> Any:
        q = str(query or "").strip()
        low = q.lower()

        if slot_name in {"recipient", "contact", "receiver"}:
            patterns = [
                r"给\s*([\u4e00-\u9fffA-Za-z0-9_]{1,20}?)(?=发消息|发个消息|发信息|写邮件|发邮件|打电话|留言|说)",
                r"(?:发消息给|发信息给|发邮件给|写邮件给|打电话给)\s*([\u4e00-\u9fffA-Za-z0-9_]{1,20})",
                r"(?:to|for)\s+([A-Za-z][A-Za-z0-9_\- ]{1,30})",
            ]
            for p in patterns:
                m = re.search(p, q, flags=re.I)
                if m:
                    return m.group(1).strip()
            return None

        if slot_name in {"content", "message", "text"}:
            # Prefer explicit speech/content marker tails.
            for marker in ["说", "内容是", "内容:", "内容：", "that "]:
                idx = low.find(marker.lower())
                if idx >= 0:
                    tail = q[idx + len(marker) :].strip(" ：:，,。.!？? ")
                    if tail:
                        return tail

            if "提醒我" in q:
                tail = q.split("提醒我", 1)[1].strip(" ：:，,。.!？? ")
                tail = _strip_time_tokens(tail)
                if tail:
                    return tail
            if "提醒" in q:
                tail = q.split("提醒", 1)[1]
                tail = re.sub(r"^(一下|下|我)?", "", tail).strip(" ：:，,。.!？? ")
                tail = _strip_time_tokens(tail)
                if tail:
                    return tail

            return None

        return None


def _resolve_slot_names(trigger: TriggerLike) -> Tuple[List[str], List[str]]:
    if trigger is None:
        return [], []
    if isinstance(trigger, TriggerDef):
        req: List[str] = []
        opt: List[str] = []
        for item in trigger.required_slots:
            if isinstance(item, dict):
                name = str(item.get("slot_name") or item.get("name") or "").strip()
            else:
                name = str(getattr(item, "slot_name", "") or "").strip()
            if name:
                req.append(name)
        for item in trigger.optional_slots:
            if isinstance(item, dict):
                name = str(item.get("slot_name") or item.get("name") or "").strip()
            else:
                name = str(getattr(item, "slot_name", "") or "").strip()
            if name:
                opt.append(name)
        return req, opt
    if isinstance(trigger, dict):
        req = _slot_names_from_dict_list(trigger.get("required_slots"))
        opt = _slot_names_from_dict_list(trigger.get("optional_slots"))
        return req, opt
    return [], []


def _slot_names_from_dict_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("slot_name") or item.get("name") or "").strip()
            if name:
                out.append(name)
        elif isinstance(item, str):
            s = str(item).strip()
            if s:
                out.append(s)
    return out


def _guess_slot_type(slot_name: str) -> str:
    s = str(slot_name or "").strip().lower()
    if s in {"time", "datetime"}:
        return "time"
    if s in {"date", "day", "due_date"}:
        return "date"
    if s in {"contact", "recipient", "receiver"}:
        return "string"
    if s in {"location", "place"}:
        return "location"
    if s in {"content", "message", "text"}:
        return "string"
    return "string"


def _extract_time_window(query: str) -> str:
    q = str(query or "")
    for marker in ["今天", "明天", "后天", "下午", "上午", "晚上", "今晚", "明早", "today", "tomorrow", "tonight", "morning", "afternoon"]:
        if marker in q.lower() or marker in q:
            return marker
    return q


def _extract_date_token(query: str) -> Optional[str]:
    q = str(query or "").strip()
    low = q.lower()

    m = re.search(r"(今天|明天|后天|大后天|本周[一二三四五六日天]|下周[一二三四五六日天])", q)
    if m:
        return m.group(1)

    # 2026-03-01 / 2026/03/01 / 03-01
    m2 = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2})\b", q)
    if m2:
        return m2.group(1)

    m3 = re.search(
        r"\b(today|tomorrow|day after tomorrow|next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday)\b",
        low,
        flags=re.I,
    )
    if m3:
        return m3.group(1)
    return None


def _strip_time_tokens(text: str) -> str:
    t = str(text or "")
    t = re.sub(r"(今天|明天|后天|上午|下午|晚上|今晚|明早|中午)", "", t)
    t = re.sub(r"\d{1,2}(:\d{2})?\s*(am|pm)?", "", t, flags=re.I)
    t = re.sub(r"\d{1,2}点(\d{1,2}分?)?", "", t)
    return t.strip(" ，,。.!？? ")


def _normalize_time_expression(raw_time: str, full_query: str = "") -> Dict[str, Any]:
    """
    Lightweight time normalization for downstream scheduling.
    """
    raw = str(raw_time or "").strip()
    lower = raw.lower()
    full = str(full_query or "")
    full_lower = full.lower()

    day_offset = None
    if "今天" in raw or "today" in lower or "今天" in full or "today" in full_lower:
        day_offset = 0
    elif "明天" in raw or "tomorrow" in lower or "明天" in full or "tomorrow" in full_lower:
        day_offset = 1
    elif "后天" in raw or "后天" in full:
        day_offset = 2

    period = None
    if "上午" in raw or "morning" in lower:
        period = "morning"
    elif "中午" in raw or "noon" in lower:
        period = "noon"
    elif "下午" in raw or "afternoon" in lower:
        period = "afternoon"
    elif "晚上" in raw or "今晚" in raw or "evening" in lower or "tonight" in lower:
        period = "evening"
    elif "明早" in raw:
        period = "morning"
        if day_offset is None:
            day_offset = 1

    hour = None
    minute = 0
    source = "implicit"

    m_hhmm = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", lower, flags=re.I)
    if m_hhmm:
        hour = int(m_hhmm.group(1))
        minute = int(m_hhmm.group(2))
        ampm = (m_hhmm.group(3) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        source = "hh:mm"
    else:
        m_cn = re.search(r"([一二三四五六七八九十两]{1,3}|\d{1,2})点(半|\d{1,2}分?)?", raw)
        if m_cn:
            hour = _cn_or_digit_to_int(m_cn.group(1))
            tail = m_cn.group(2) or ""
            if "半" in tail:
                minute = 30
            else:
                m_min = re.search(r"(\d{1,2})", tail)
                minute = int(m_min.group(1)) if m_min else 0
            source = "cn_clock"
        else:
            m_ampm = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lower)
            if m_ampm:
                hour = int(m_ampm.group(1))
                minute = 0
                if m_ampm.group(2) == "pm" and hour < 12:
                    hour += 12
                if m_ampm.group(2) == "am" and hour == 12:
                    hour = 0
                source = "ampm"

    if hour is not None:
        if period in {"afternoon", "evening"} and 1 <= hour <= 11:
            hour += 12
        if period == "noon" and hour == 12:
            hour = 12
        if period == "morning" and hour == 12:
            hour = 0

    iso_time = None
    if hour is not None:
        iso_time = f"{max(0, min(23, hour)):02d}:{max(0, min(59, minute)):02d}"

    return {
        "raw": raw,
        "day_offset": day_offset,
        "period": period,
        "hour": hour,
        "minute": minute if hour is not None else None,
        "iso_time": iso_time,
        "source": source,
    }


def _cn_or_digit_to_int(token: str) -> Optional[int]:
    t = str(token or "").strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    mapping = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    if t == "十":
        return 10
    if t.startswith("十") and len(t) == 2:
        return 10 + mapping.get(t[1], 0)
    if t.endswith("十") and len(t) == 2:
        return mapping.get(t[0], 0) * 10
    if "十" in t and len(t) == 3:
        left = mapping.get(t[0], 0)
        right = mapping.get(t[2], 0)
        return left * 10 + right
    return mapping.get(t)
