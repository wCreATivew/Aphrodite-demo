from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Protocol

try:
    from .schemas import CandidateScore
    from .scoring_utils import (
        candidates_to_dicts,
        clamp01,
        coerce_trigger,
        compute_idf,
        max_text_similarity,
        normalize_text,
        token_counts,
        trigger_searchable_text,
    )
except ImportError:
    from schemas import CandidateScore  # type: ignore
    from scoring_utils import (  # type: ignore
        candidates_to_dicts,
        clamp01,
        coerce_trigger,
        compute_idf,
        max_text_similarity,
        normalize_text,
        token_counts,
        trigger_searchable_text,
    )


class Reranker(Protocol):
    def rerank(self, query: str, candidates: List[CandidateScore], by_id: Dict[str, Any]) -> List[CandidateScore]: ...


_ACTION_HINTS = {
    "set_reminder": ["提醒", "remind", "reminder", "闹钟", "alarm", "会议"],
    "send_message": ["发", "消息", "message", "text", "通知", "email"],
    "weather_query": ["天气", "weather", "forecast", "下雨", "温度"],
    "translate_text": ["翻译", "translate", "译成", "中文", "英文"],
    "summarize_text": ["总结", "摘要", "summarize", "summary", "概括"],
    "open_file": ["打开", "open", "文件", "file", "路径"],
    "code_debug": ["debug", "调试", "报错", "异常", "traceback", "bug", "crash", "修复", "修bug"],
}

_SLOT_CUES = {
    "time": ["明天", "后天", "下午", "上午", "今晚", "点", "am", "pm", "tomorrow", "today"],
    "recipient": ["给", "发给", "to", "recipient", "联系人"],
    "location": ["在", "天气", "where", "city", "城市", "地点"],
    "target_lang": ["翻译", "成", "to", "中文", "英文", "日文", "french", "chinese", "english"],
    "text": ["这段", "这句", "paragraph", "text", "内容"],
}


def rerank_candidates(query: str, candidates: Iterable[CandidateScore], trigger_map: Mapping[str, Any]) -> List[CandidateScore]:
    """Baseline rerank over recalled candidates.

    Args:
        query: user query.
        candidates: recall candidates.
        trigger_map: trigger_id -> TriggerDef-like or dict-like.

    Returns:
        Candidates sorted by final_score desc.
    """
    q = str(query or "").strip()
    if not q:
        return []

    q_norm = normalize_text(q)
    q_tf = token_counts(q)

    normalized_map: Dict[str, Dict[str, Any]] = {}
    for tid, trig in dict(trigger_map).items():
        coerced = coerce_trigger(trig)
        trigger_id = str(coerced.get("trigger_id") or tid or "").strip()
        if trigger_id:
            normalized_map[trigger_id] = coerced

    doc_tfs = [token_counts(trigger_searchable_text(t)) for t in normalized_map.values()]
    idf = compute_idf(doc_tfs + [q_tf])

    out: List[CandidateScore] = []
    for c in candidates:
        trig = normalized_map.get(str(c.trigger_id or ""))
        if trig is None:
            continue

        trigger_id = str(trig.get("trigger_id") or c.trigger_id)
        trigger_name = str(trig.get("name") or c.name or trigger_id)

        alias_exact = 1.0 if _alias_exact_hit(q_norm, trig.get("aliases", [])) else 0.0
        action_score = _action_hint_score(q_norm, trig)
        positive_score = max_text_similarity(q_tf, trig.get("positive_examples", [])[:20], idf)
        negative_score = max_text_similarity(q_tf, trig.get("negative_examples", [])[:20], idf)
        name_desc_score = max_text_similarity(
            q_tf,
            [f"{trig.get('name', '')} {trig.get('description', '')}"],
            idf,
        )
        slot_cue_score = _slot_cue_score(q_norm, trig)

        rerank_score = (
            0.30 * alias_exact
            + 0.24 * action_score
            + 0.18 * positive_score
            + 0.16 * slot_cue_score
            + 0.12 * name_desc_score
            - 0.25 * negative_score
        )
        rerank_score = clamp01(rerank_score)

        recall_score = float(c.recall_score or 0.0)
        final_score = clamp01(0.45 * recall_score + 0.55 * rerank_score)

        reasons = list(c.reasons) + [
            f"rerank_alias_exact={alias_exact:.4f}",
            f"rerank_action={action_score:.4f}",
            f"rerank_positive={positive_score:.4f}",
            f"rerank_negative={negative_score:.4f}",
            f"rerank_slot_cue={slot_cue_score:.4f}",
            f"rerank_name_desc={name_desc_score:.4f}",
        ]
        notes = (
            f"stage=rerank; recall={recall_score:.3f}; rerank={rerank_score:.3f}; "
            f"alias={alias_exact:.3f}; action={action_score:.3f}; slot={slot_cue_score:.3f}; "
            f"neg={negative_score:.3f}"
        )

        out.append(
            CandidateScore(
                trigger_id=trigger_id,
                name=trigger_name,
                recall_score=recall_score,
                rerank_score=rerank_score,
                final_score=final_score,
                notes=notes,
                reasons=reasons,
            )
        )

    out.sort(key=lambda x: float(x.final_score or 0.0), reverse=True)
    return out


def rerank_candidates_dict(
    query: str,
    candidates: Iterable[CandidateScore | Mapping[str, Any]],
    trigger_map: Mapping[str, Any],
) -> List[dict[str, Any]]:
    """Dict-output adapter for strict protocol consumers."""
    normalized_candidates: List[CandidateScore] = []
    for item in candidates:
        if isinstance(item, Mapping):
            normalized_candidates.append(
                CandidateScore(
                    trigger_id=str(item.get("trigger_id") or "").strip(),
                    recall_score=item.get("recall_score"),
                    rerank_score=item.get("rerank_score"),
                    final_score=item.get("final_score"),
                    notes=item.get("notes"),
                )
            )
        else:
            normalized_candidates.append(item)
    ranked = rerank_candidates(query=query, candidates=normalized_candidates, trigger_map=trigger_map)
    return candidates_to_dicts(ranked)


@dataclass
class BaselineReranker:
    def rerank(self, query: str, candidates: List[CandidateScore], by_id: Dict[str, Any]) -> List[CandidateScore]:
        return rerank_candidates(query=query, candidates=candidates, trigger_map=by_id)



def _alias_exact_hit(query_norm: str, aliases: Iterable[str]) -> bool:
    if not query_norm:
        return False
    for alias in aliases:
        marker = normalize_text(alias)
        if marker and marker in query_norm:
            return True
    return False



def _action_hint_score(query_norm: str, trigger: Mapping[str, Any]) -> float:
    trigger_id = str(trigger.get("trigger_id") or "").strip().lower()
    trigger_text = normalize_text(
        " ".join(
            [
                str(trigger.get("name") or ""),
                str(trigger.get("description") or ""),
                " ".join(trigger.get("aliases") or []),
            ]
        )
    )

    hints = list(_ACTION_HINTS.get(trigger_id, []))
    if not hints:
        hints = [x for x in ["提醒", "消息", "翻译", "总结", "天气", "文件", "remind", "message", "translate", "summary", "weather", "open"] if x in trigger_text]
    if not hints:
        return 0.0

    hit = 0
    for hint in hints:
        marker = normalize_text(hint)
        if marker and marker in query_norm:
            hit += 1
    return clamp01(hit / max(1, min(4, len(hints))))



def _slot_cue_score(query_norm: str, trigger: Mapping[str, Any]) -> float:
    slot_names: List[str] = []

    for raw in list(trigger.get("required_slots") or []) + list(trigger.get("optional_slots") or []):
        if isinstance(raw, Mapping):
            slot_name = str(raw.get("slot_name") or "").strip().lower()
        else:
            slot_name = str(getattr(raw, "slot_name", "") or "").strip().lower()
        if slot_name:
            slot_names.append(slot_name)

    if not slot_names:
        return 0.0

    matched = 0
    for slot_name in slot_names:
        cues = _SLOT_CUES.get(slot_name, [])
        if not cues:
            continue
        if any(normalize_text(cue) in query_norm for cue in cues if normalize_text(cue)):
            matched += 1

    return clamp01(matched / max(1, len(slot_names)))



def _mock_triggers() -> List[Dict[str, Any]]:
    return [
        {
            "trigger_id": "set_reminder",
            "name": "Set Reminder",
            "description": "Create reminder with time and content.",
            "aliases": ["提醒", "remind", "set reminder"],
            "positive_examples": [
                "明天下午三点提醒我开会",
                "今晚8点提醒我吃药",
                "remind me at 6pm to call mom",
            ],
            "negative_examples": ["提醒系统怎么实现", "reminder architecture tutorial"],
            "required_slots": [{"slot_name": "time"}, {"slot_name": "content"}],
            "optional_slots": [{"slot_name": "date"}],
            "enabled": True,
            "tags": ["task", "time"],
        },
        {
            "trigger_id": "translate_text",
            "name": "Translate Text",
            "description": "Translate text between languages.",
            "aliases": ["翻译", "translate", "译成"],
            "positive_examples": [
                "把这句英文翻译成中文",
                "translate this sentence into Chinese",
                "把这段日文翻译成英文",
            ],
            "negative_examples": ["机器翻译模型原理", "translation benchmark tutorial"],
            "required_slots": [{"slot_name": "text"}, {"slot_name": "target_lang"}],
            "optional_slots": [{"slot_name": "source_lang"}],
            "enabled": True,
            "tags": ["nlp"],
        },
        {
            "trigger_id": "weather_query",
            "name": "Query Weather",
            "description": "Get weather forecast for location/date.",
            "aliases": ["天气", "weather", "forecast"],
            "positive_examples": ["今天天气怎么样", "明天北京会下雨吗", "weather in Shanghai"],
            "negative_examples": ["weather api pricing", "climate model paper"],
            "required_slots": [{"slot_name": "location"}],
            "optional_slots": [{"slot_name": "date"}],
            "enabled": True,
            "tags": ["information"],
        },
        {
            "trigger_id": "send_message",
            "name": "Send Message",
            "description": "Send message to someone with content.",
            "aliases": ["发消息", "message", "text"],
            "positive_examples": ["帮我发消息给张三说我晚点到", "text Alex I am late"],
            "negative_examples": ["message queue tutorial", "kafka design"],
            "required_slots": [{"slot_name": "recipient"}, {"slot_name": "content"}],
            "optional_slots": [],
            "enabled": True,
            "tags": ["communication"],
        },
        {
            "trigger_id": "summarize_text",
            "name": "Summarize Text",
            "description": "Summarize long text into concise points.",
            "aliases": ["总结", "摘要", "summarize"],
            "positive_examples": ["帮我总结这篇文章", "summarize this email"],
            "negative_examples": ["summarization model benchmark", "summary writing tips"],
            "required_slots": [{"slot_name": "text"}],
            "optional_slots": [],
            "enabled": True,
            "tags": ["nlp"],
        },
        {
            "trigger_id": "open_file",
            "name": "Open File",
            "description": "Open local file path or filename.",
            "aliases": ["打开文件", "open file", "打开"],
            "positive_examples": ["打开README.md", "open config.yaml"],
            "negative_examples": ["文件系统设计", "open file descriptor concept"],
            "required_slots": [{"slot_name": "file_path"}],
            "optional_slots": [],
            "enabled": True,
            "tags": ["filesystem"],
        },
    ]


if __name__ == "__main__":
    try:
        from .retriever import retrieve_candidates
    except ImportError:
        from retriever import retrieve_candidates  # type: ignore

    demo_triggers = _mock_triggers()
    trigger_map = {t["trigger_id"]: t for t in demo_triggers}
    demo_queries = [
        "帮我明天下午提醒我开会",
        "把这段英文翻译成中文",
        "今天天气怎么样",
    ]

    for q in demo_queries:
        recall = retrieve_candidates(q, demo_triggers, top_k=5)
        ranked = rerank_candidates(q, recall, trigger_map)
        print(f"\nQuery: {q}")
        for i, item in enumerate(ranked[:3], start=1):
            print(
                f"  {i}. {item.trigger_id:16s} "
                f"recall={float(item.recall_score or 0.0):.3f} "
                f"rerank={float(item.rerank_score or 0.0):.3f} "
                f"final={float(item.final_score or 0.0):.3f}"
            )
