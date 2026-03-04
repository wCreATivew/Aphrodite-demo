from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def u(text: str) -> str:
    """Decode unicode escapes from ASCII source."""
    return text.encode("utf-8").decode("unicode_escape")


def _slot(name: str, slot_type: str, required: bool, hints: List[str], rules: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "slot_name": name,
        "slot_type": slot_type,
        "required": required,
        "extraction_hints": hints,
        "validation_rules": dict(rules or {}),
    }


def build_triggers() -> List[Dict[str, Any]]:
    return [
        {
            "trigger_id": "set_reminder",
            "name": "Set Reminder",
            "description": "Create reminder tasks with date/time and reminder content.",
            "aliases": [u(r"\u63d0\u9192"), u(r"\u63d0\u9192\u6211"), "remind", "set reminder"],
            "positive_examples": [
                u(r"\u660e\u5929\u4e0b\u53483\u70b9\u63d0\u9192\u6211\u5f00\u4f1a"),
                u(r"\u665a\u4e0a8\u70b9\u63d0\u9192\u6211\u5403\u836f"),
                u(r"\u540e\u59299:30\u63d0\u9192\u6211\u56de\u7535\u8bdd"),
                u(r"\u4e0b\u5468\u4e007\u70b9\u63d0\u9192\u6211\u8dd1\u6b65"),
                "remind me at 6pm to call mom",
                "set a reminder for tomorrow 10am dentist",
                "in 30 minutes remind me to stand up",
                "please remind me next Tuesday to pay rent",
            ],
            "negative_examples": [
                u(r"\u63d0\u9192\u529f\u80fd\u662f\u600e\u4e48\u505a\u7684"),
                u(r"\u4f60\u4f1a\u63d0\u9192\u6211\u5417"),
                u(r"\u6211\u5728\u770b\u63d0\u9192\u7cfb\u7edf\u8bbe\u8ba1"),
                u(r"\u63a8\u8350\u4e00\u4e0b\u63d0\u9192App"),
                "what is a reminder app",
                "event-driven reminder architecture",
                "how to design reminder queue",
                "explain reminder feature",
            ],
            "required_slots": [
                _slot("time", "time", True, ["when", "at 6pm"]),
                _slot("content", "string", True, ["what to remind"]),
            ],
            "optional_slots": [_slot("date", "date", False, ["tomorrow", "next week"])],
            "hard_constraints": [],
            "priority": 9,
            "enabled": True,
            "tags": ["task", "time"],
            "metadata": {},
        },
        {
            "trigger_id": "send_message",
            "name": "Send Message",
            "description": "Send a message to a person or channel with content.",
            "aliases": [u(r"\u53d1\u6d88\u606f"), u(r"\u53d1\u4fe1\u606f"), "send message", "text"],
            "positive_examples": [
                u(r"\u7ed9\u5f20\u4e09\u53d1\u6d88\u606f\u8bf4\u6211\u665a\u70b9\u5230"),
                u(r"\u5e2e\u6211\u53d1\u4fe1\u606f\u7ed9\u9879\u76ee\u7ec4\uff1a\u7248\u672c\u5df2\u4e0a\u7ebf"),
                u(r"\u7ed9\u8001\u677f\u53d1\u4e2a\u6d88\u606f\uff0c\u8bf4\u6211\u5728\u8def\u4e0a"),
                u(r"\u53d1\u6761\u6d88\u606f\u7ed9\u5bb6\u4eba\u62a5\u5e73\u5b89"),
                "send a message to John: running late",
                "text Alex that I will call tonight",
                "message team channel with deployment done",
                "send a quick note to Mia about schedule",
            ],
            "negative_examples": [
                u(r"\u6d88\u606f\u63a8\u9001\u7cfb\u7edf\u600e\u4e48\u8bbe\u8ba1"),
                u(r"\u6211\u6536\u4e0d\u5230\u6d88\u606f\u4e86"),
                u(r"\u89e3\u91ca\u4e00\u4e0bKafka\u6d88\u606f\u961f\u5217"),
                u(r"\u4eca\u5929\u6709\u4ec0\u4e48\u65b0\u95fb\u6d88\u606f"),
                "message queue tutorial",
                "how to improve message delivery",
                "notification center architecture",
                "send protocol explanation",
            ],
            "required_slots": [
                _slot("recipient", "string", True, ["who to send to"]),
                _slot("content", "string", True, ["message body"]),
            ],
            "optional_slots": [],
            "hard_constraints": [],
            "priority": 8,
            "enabled": True,
            "tags": ["communication"],
            "metadata": {},
        },
        {
            "trigger_id": "weather_query",
            "name": "Query Weather",
            "description": "Fetch weather forecast for a location and optional date.",
            "aliases": [u(r"\u5929\u6c14"), "weather", "forecast", u(r"\u67e5\u5929\u6c14")],
            "positive_examples": [
                u(r"\u5317\u4eac\u660e\u5929\u5929\u6c14\u600e\u4e48\u6837"),
                u(r"\u4e0a\u6d77\u540e\u5929\u4f1a\u4e0b\u96e8\u5417"),
                u(r"\u67e5\u4e00\u4e0b\u6df1\u5733\u4eca\u665a\u6c14\u6e29"),
                u(r"\u676d\u5dde\u5468\u672b\u5929\u6c14\u9884\u62a5"),
                "weather in San Francisco tomorrow",
                "will it rain in Seattle tonight",
                "show forecast for Tokyo this weekend",
                "temperature in London today",
            ],
            "negative_examples": [
                u(r"\u5929\u6c14API\u600e\u4e48\u63a5"),
                u(r"\u8bb2\u8bb2\u6c14\u5019\u53d8\u5316"),
                u(r"\u6211\u4eca\u5929\u5fc3\u60c5\u50cf\u5929\u6c14\u4e00\u6837"),
                u(r"\u5929\u6c14\u63d2\u4ef6\u5f00\u53d1\u6587\u6863"),
                "what is climate change",
                "forecasting model tutorial",
                "weather API pricing",
                "climate research papers",
            ],
            "required_slots": [_slot("location", "location", True, ["city", "in <city>"])],
            "optional_slots": [_slot("date", "date", False, ["tomorrow", "weekend"])],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["information"],
            "metadata": {},
        },
        {
            "trigger_id": "open_file",
            "name": "Open File",
            "description": "Open a local file by path or filename.",
            "aliases": [u(r"\u6253\u5f00\u6587\u4ef6"), "open file", u(r"\u6253\u5f00")],
            "positive_examples": [
                u(r"\u6253\u5f00\u6587\u4ef6 report.pdf"),
                u(r"\u5e2e\u6211\u6253\u5f00 README.md"),
                u(r"\u6253\u5f00 C:/tmp/a.txt"),
                u(r"\u6253\u5f00\u6700\u65b0\u65e5\u5fd7\u6587\u4ef6"),
                "open file notes.txt",
                "open C:/work/todo.md",
                "please open the latest log file",
                "open config.yaml",
            ],
            "negative_examples": [
                u(r"\u4e3a\u4ec0\u4e48\u6587\u4ef6\u6253\u4e0d\u5f00"),
                u(r"\u6253\u5f00\u65b9\u5f0f\u600e\u4e48\u8bbe\u7f6e"),
                "I cannot open my heart",
                "open source file format info",
                "filesystem architecture",
                "how to recover corrupted file",
                "what is open file descriptor",
                "file extension explanation",
            ],
            "required_slots": [_slot("file_path", "string", True, ["path or filename"])],
            "optional_slots": [],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["filesystem"],
            "metadata": {},
        },
        {
            "trigger_id": "web_search",
            "name": "Web Search",
            "description": "Search web information from public sources.",
            "aliases": [u(r"\u641c\u7d22"), "web search", u(r"\u641c\u4e00\u4e0b"), u(r"\u67e5\u4e00\u4e0b")],
            "positive_examples": [
                u(r"\u641c\u7d22\u4e00\u4e0b Python 3.13 \u65b0\u7279\u6027"),
                u(r"\u5e2e\u6211\u67e5 OpenAI Responses API \u6587\u6863"),
                u(r"\u7f51\u4e0a\u641c\u4e00\u4e0b\u4eca\u5e74AI\u65b0\u95fb"),
                u(r"\u67e5\u4e00\u67e5 RAG \u6700\u4f73\u5b9e\u8df5"),
                "search web for best laptop 2026",
                "find official docs for fastapi",
                "look up bitcoin latest news",
                "search for tokyo travel guide",
            ],
            "negative_examples": [
                u(r"\u641c\u7d22\u7b97\u6cd5\u539f\u7406\u662f\u4ec0\u4e48"),
                u(r"\u6211\u5728\u5b66\u4fe1\u606f\u68c0\u7d22"),
                u(r"\u641c\u7d22\u5f15\u64ce\u67b6\u6784\u8bba\u6587"),
                u(r"\u6570\u636e\u5e93\u7d22\u5f15\u600e\u4e48\u5efa"),
                "web search engine architecture tutorial",
                "inverted index internals",
                "search ranking model paper",
                "how BM25 works",
            ],
            "required_slots": [_slot("query", "string", True, ["search query"], {"min_len": 2})],
            "optional_slots": [],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["information", "web"],
            "metadata": {},
        },
        {
            "trigger_id": "play_music",
            "name": "Play Music",
            "description": "Play song, artist, or playlist.",
            "aliases": [u(r"\u64ad\u653e\u97f3\u4e50"), "play music", u(r"\u6765\u9996\u6b4c"), u(r"\u64ad\u653e")],
            "positive_examples": [
                u(r"\u64ad\u653e\u5468\u6770\u4f26\u7684\u6b4c"),
                u(r"\u6765\u70b9\u8f7b\u97f3\u4e50"),
                u(r"\u5e2e\u6211\u653e\u4e00\u9996\u591c\u66f2"),
                u(r"\u64ad\u653e\u6211\u7684\u5b66\u4e60\u6b4c\u5355"),
                "play music by Adele",
                "play my focus playlist",
                "put on some lo-fi beats",
                "play rock music",
            ],
            "negative_examples": [
                u(r"\u97f3\u4e50\u63a8\u8350\u7b97\u6cd5\u600e\u4e48\u505a"),
                u(r"\u64ad\u653e\u5668\u95ea\u9000\u4e86"),
                u(r"\u6211\u5728\u5b66\u97f3\u4e50\u7406\u8bba"),
                u(r"\u6b4c\u66f2\u7248\u6743\u600e\u4e48\u7533\u8bf7"),
                "music recommendation algorithm",
                "audio codec explanation",
                "music player crash analysis",
                "what is lossless audio",
            ],
            "required_slots": [_slot("target", "string", True, ["song, artist, or playlist"])],
            "optional_slots": [],
            "hard_constraints": [],
            "priority": 6,
            "enabled": True,
            "tags": ["media"],
            "metadata": {},
        },
        {
            "trigger_id": "set_alarm",
            "name": "Set Alarm",
            "description": "Set an alarm clock at specific time.",
            "aliases": [u(r"\u95f9\u949f"), "alarm", "set alarm"],
            "positive_examples": [
                u(r"\u8bbe\u7f6e7\u70b9\u95f9\u949f"),
                u(r"\u660e\u65e98:30\u53eb\u6211\u8d77\u5e8a"),
                u(r"\u8bbe\u4e00\u4e2a11\u70b9\u534a\u7684\u95f9\u949f"),
                u(r"5\u5206\u949f\u540e\u53eb\u9192\u6211"),
                "set an alarm for 6am",
                "wake me up at 7 tomorrow",
                "alarm at 14:00",
                "set recurring alarm every weekday 8",
            ],
            "negative_examples": [
                u(r"\u95f9\u949f\u4e3a\u4ec0\u4e48\u4e0d\u54cd"),
                u(r"\u63a8\u8350\u95f9\u949fapp"),
                u(r"\u600e\u4e48\u6539\u5584\u7761\u7720"),
                u(r"\u8d77\u5e8a\u56f0\u96be\u600e\u4e48\u529e"),
                "alarm clock circuit design",
                "wake up routine tips",
                "sleep quality tracking",
                "alarm app comparison",
            ],
            "required_slots": [_slot("time", "time", True, ["time expression"])],
            "optional_slots": [_slot("repeat", "string", False, ["daily", "weekday"])],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["time", "task"],
            "metadata": {},
        },
        {
            "trigger_id": "translate_text",
            "name": "Translate Text",
            "description": "Translate text between languages.",
            "aliases": [u(r"\u7ffb\u8bd1"), "translate", u(r"\u8bd1\u6210")],
            "positive_examples": [
                u(r"\u628a\u8fd9\u53e5\u8bdd\u7ffb\u8bd1\u6210\u82f1\u6587"),
                u(r"\u5e2e\u6211\u7ffb\u8bd1\u6210\u65e5\u8bed\uff1a\u4eca\u5929\u5f88\u9ad8\u5174\u89c1\u5230\u4f60"),
                u(r"\u628a\u4e0b\u9762\u5185\u5bb9\u8bd1\u6210\u6cd5\u8bed"),
                u(r"\u8bf7\u7ffb\u8bd1\u8fd9\u6bb5\u8bdd\u5230\u97e9\u8bed"),
                "translate this to Chinese: good luck",
                "translate to French: how are you",
                "translate this paragraph into English",
                "translate this Spanish sentence",
            ],
            "negative_examples": [
                u(r"\u7ffb\u8bd1\u6a21\u578b\u600e\u4e48\u8bad\u7ec3"),
                u(r"\u8bed\u8a00\u5b66\u548c\u7ffb\u8bd1\u5b66\u533a\u522b"),
                u(r"\u673a\u5668\u7ffb\u8bd1\u8bba\u6587\u63a8\u8350"),
                u(r"\u7ffb\u8bd1API\u4ef7\u683c"),
                "what is machine translation",
                "NMT architecture tutorial",
                "translation benchmark datasets",
                "translator app ranking",
            ],
            "required_slots": [
                _slot("text", "string", True, ["source text"]),
                _slot("target_lang", "string", True, ["target language"]),
            ],
            "optional_slots": [_slot("source_lang", "string", False, ["source language"])],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["nlp"],
            "metadata": {},
        },
        {
            "trigger_id": "summarize_text",
            "name": "Summarize Text",
            "description": "Summarize long text, article, or notes.",
            "aliases": [u(r"\u603b\u7ed3"), u(r"\u6458\u8981"), "summarize"],
            "positive_examples": [
                u(r"\u5e2e\u6211\u603b\u7ed3\u8fd9\u7bc7\u6587\u7ae0"),
                u(r"\u628a\u4e0b\u9762\u5185\u5bb9\u505a\u4e2a\u6458\u8981"),
                u(r"\u603b\u7ed3\u4e00\u4e0b\u8fd9\u6bb5\u4f1a\u8bae\u7eaa\u8981"),
                u(r"\u7ed9\u6211\u4e00\u4e2a\u4e09\u53e5\u8bdd\u603b\u7ed3"),
                "summarize this paragraph",
                "give me a short summary of the email",
                "summarize this report into bullet points",
                "make a brief summary of this text",
            ],
            "negative_examples": [
                u(r"\u603b\u7ed3\u80fd\u529b\u600e\u4e48\u8bad\u7ec3"),
                u(r"\u603b\u7ed3\u6a21\u677f\u6709\u54ea\u4e9b"),
                u(r"\u8bf7\u95ee\u6458\u8981\u957f\u5ea6\u89c4\u8303"),
                u(r"\u6211\u5728\u5199\u5468\u62a5"),
                "summary writing techniques",
                "how to write executive summary",
                "summarization model benchmark",
                "text summarization datasets",
            ],
            "required_slots": [_slot("text", "string", True, ["text to summarize"], {"min_len": 20})],
            "optional_slots": [_slot("length", "string", False, ["short", "brief"])],
            "hard_constraints": [],
            "priority": 6,
            "enabled": True,
            "tags": ["nlp"],
            "metadata": {},
        },
        {
            "trigger_id": "write_email",
            "name": "Write Email",
            "description": "Draft an email for a given recipient and intent.",
            "aliases": [u(r"\u5199\u90ae\u4ef6"), "email draft", "compose email"],
            "positive_examples": [
                u(r"\u5e2e\u6211\u5199\u4e00\u5c01\u90ae\u4ef6\u7ed9HR\u8bf7\u5047"),
                u(r"\u5199\u4e00\u5c01\u90ae\u4ef6\u7ed9\u5ba2\u6237\u8bf4\u660e\u5ef6\u671f"),
                u(r"\u8d77\u8349\u90ae\u4ef6\u7ed9\u8001\u677f\u6c47\u62a5\u8fdb\u5ea6"),
                u(r"\u7ed9\u4f9b\u5e94\u5546\u5199\u4e00\u5c01\u8be2\u4ef7\u90ae\u4ef6"),
                "draft an email to HR about leave",
                "compose a polite apology email",
                "write an email requesting budget approval",
                "draft a follow-up email to the client",
            ],
            "negative_examples": [
                u(r"\u90ae\u4ef6\u7cfb\u7edf\u600e\u4e48\u914d\u7f6e"),
                u(r"\u90ae\u7bb1\u6536\u4e0d\u5230\u90ae\u4ef6"),
                u(r"SMTP \u534f\u8bae\u662f\u4ec0\u4e48"),
                u(r"\u90ae\u4ef6\u6a21\u677f\u63a8\u8350"),
                "email security best practices",
                "mail server setup guide",
                "how to avoid spam filters",
                "email tracking implementation",
            ],
            "required_slots": [
                _slot("intent", "string", True, ["email intent"]),
                _slot("recipient", "string", True, ["recipient"]),
            ],
            "optional_slots": [_slot("tone", "enum", False, ["formal"], {"allowed": ["formal", "neutral", "friendly"]})],
            "hard_constraints": [],
            "priority": 7,
            "enabled": True,
            "tags": ["writing", "communication"],
            "metadata": {},
        },
        {
            "trigger_id": "schedule_query",
            "name": "Schedule Query",
            "description": "Query calendar events or schedule availability.",
            "aliases": [u(r"\u65e5\u7a0b"), "calendar", "schedule", u(r"\u884c\u7a0b")],
            "positive_examples": [
                u(r"\u660e\u5929\u6211\u6709\u4ec0\u4e48\u65e5\u7a0b"),
                u(r"\u67e5\u4e00\u4e0b\u4eca\u5929\u4e0b\u5348\u7684\u5b89\u6392"),
                u(r"\u8fd9\u5468\u4e94\u6709\u4f1a\u8bae\u5417"),
                u(r"\u770b\u770b\u4e0b\u5468\u4e00\u7684\u884c\u7a0b"),
                "what is on my calendar tomorrow",
                "show my schedule for Friday",
                "any meetings this afternoon",
                "do I have free time at 2pm",
            ],
            "negative_examples": [
                u(r"\u65e5\u7a0b\u7ba1\u7406\u8f6f\u4ef6\u63a8\u8350"),
                u(r"calendar app \u54ea\u4e2a\u597d"),
                u(r"\u65f6\u95f4\u7ba1\u7406\u65b9\u6cd5"),
                u(r"\u6211\u60f3\u5b89\u6392\u4e00\u4e0b\u4eba\u751f"),
                "schedule algorithm tutorial",
                "calendar sync issue troubleshooting",
                "meeting overload tips",
                "project scheduling framework",
            ],
            "required_slots": [],
            "optional_slots": [_slot("date", "date", False, ["tomorrow", "friday"])],
            "hard_constraints": [],
            "priority": 6,
            "enabled": True,
            "tags": ["calendar"],
            "metadata": {},
        },
        {
            "trigger_id": "smalltalk_chat",
            "name": "Smalltalk",
            "description": "General social chat without concrete executable intent.",
            "aliases": [u(r"\u95f2\u804a"), "chat", "smalltalk"],
            "positive_examples": [
                u(r"\u4f60\u597d\u5440"),
                u(r"\u6700\u8fd1\u600e\u4e48\u6837"),
                u(r"\u966a\u6211\u804a\u804a\u5929"),
                u(r"\u8bb2\u4e2a\u7b11\u8bdd"),
                "how are you doing",
                "let's just chat",
                "tell me a joke",
                "I feel bored, chat with me",
            ],
            "negative_examples": [
                u(r"\u660e\u5929\u4e0b\u5348\u63d0\u9192\u6211\u5f00\u4f1a"),
                u(r"\u5e2e\u6211\u53d1\u6d88\u606f\u7ed9\u8001\u677f"),
                u(r"\u6253\u5f00README\u6587\u4ef6"),
                u(r"\u67e5\u4e00\u4e0b\u5317\u4eac\u5929\u6c14"),
                "search RAG tutorial",
                "write an email to HR",
                "set alarm at 7am",
                "translate this sentence",
            ],
            "required_slots": [],
            "optional_slots": [],
            "hard_constraints": [
                {
                    "constraint_type": "requires_any_keyword",
                    "params": {"keywords": [u(r"\u4f60\u597d"), u(r"\u5728\u5417"), u(r"\u804a"), u(r"\u7b11\u8bdd"), "hello", "hi", "how are you", "chat"]},
                    "description": "smalltalk needs social keywords",
                }
            ],
            "priority": 1,
            "enabled": True,
            "tags": ["fallback"],
            "metadata": {},
        },
        {
            "trigger_id": "code_debug",
            "name": "Code Debug",
            "description": "Analyze bug reports, stack traces, and propose debug actions.",
            "aliases": ["debug", u(r"\u8c03\u8bd5"), u(r"\u5f00\u59cbdebug"), u(r"\u67e5\u9519")],
            "positive_examples": [
                u(r"\u5f00\u59cbdebug"),
                u(r"\u5e2e\u6211\u8c03\u8bd5\u8fd9\u4e2a\u62a5\u9519"),
                u(r"\u8fd9\u4e2a\u5806\u6808\u600e\u4e48\u4fee"),
                u(r"\u5b9a\u4f4d\u4e00\u4e0b\u8fd9\u4e2a\u5f02\u5e38\u539f\u56e0"),
                "debug this traceback",
                "help me fix this crash",
                "why this function throws AttributeError",
                "analyze this runtime error and suggest a fix",
            ],
            "negative_examples": [
                "what does debug mean",
                "debugger principles",
                "how to learn debugging",
                "debug tools comparison",
                "code style guide",
                "refactoring checklist",
                "unit testing tutorial",
                "architecture review tips",
            ],
            "required_slots": [_slot("content", "string", True, ["error message", "traceback"])],
            "optional_slots": [],
            "hard_constraints": [],
            "priority": 9,
            "enabled": True,
            "tags": ["engineering"],
            "metadata": {},
        },
    ]


def build_config() -> Dict[str, Any]:
    return {
        "top_k": 20,
        "rerank_top_k": 20,
        "low_confidence_threshold": 0.42,
        "no_trigger_threshold": 0.28,
        "margin_threshold": 0.06,
        "ask_clarification_margin": 0.03,
        "min_consistency_score": 0.20,
        "default_trigger_threshold": 0.55,
        "per_trigger_threshold": {
            "set_reminder": 0.48,
            "send_message": 0.46,
            "weather_query": 0.50,
            "open_file": 0.48,
            "web_search": 0.48,
            "play_music": 0.50,
            "set_alarm": 0.50,
            "translate_text": 0.52,
            "summarize_text": 0.52,
            "write_email": 0.53,
            "schedule_query": 0.50,
            "smalltalk_chat": 0.58,
            "code_debug": 0.50,
        },
        "enable_adjudicator": False,
        "log_level": "INFO",
        "json_log": False,
    }


def build_eval_dataset(triggers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for trig in triggers:
        tid = trig["trigger_id"]
        for q in trig["positive_examples"]:
            rows.append({"query": q, "expected_decision": "trigger", "expected_trigger": tid})
        for q in trig["negative_examples"]:
            rows.append({"query": q, "expected_decision": "no_trigger", "expected_trigger": ""})

    ask_rows = [
        {"query": u(r"\u63d0\u9192\u6211"), "expected_decision": "ask_clarification", "expected_trigger": "set_reminder"},
        {"query": u(r"\u7ed9\u4ed6\u53d1\u6d88\u606f"), "expected_decision": "ask_clarification", "expected_trigger": "send_message"},
        {"query": u(r"\u67e5\u4e00\u4e0b\u5929\u6c14"), "expected_decision": "ask_clarification", "expected_trigger": "weather_query"},
        {"query": "open file", "expected_decision": "ask_clarification", "expected_trigger": "open_file"},
        {"query": u(r"\u5e2e\u6211\u641c\u4e00\u4e0b"), "expected_decision": "ask_clarification", "expected_trigger": "web_search"},
        {"query": u(r"\u653e\u9996\u6b4c"), "expected_decision": "ask_clarification", "expected_trigger": "play_music"},
        {"query": u(r"\u8bbe\u4e2a\u95f9\u949f"), "expected_decision": "ask_clarification", "expected_trigger": "set_alarm"},
        {"query": u(r"\u5e2e\u6211\u7ffb\u8bd1"), "expected_decision": "ask_clarification", "expected_trigger": "translate_text"},
        {"query": u(r"\u5e2e\u6211\u603b\u7ed3"), "expected_decision": "ask_clarification", "expected_trigger": "summarize_text"},
        {"query": u(r"\u5e2e\u6211\u5199\u90ae\u4ef6"), "expected_decision": "ask_clarification", "expected_trigger": "write_email"},
        {"query": u(r"\u6211\u4eca\u5929\u6709\u4ec0\u4e48\u65e5\u7a0b"), "expected_decision": "trigger", "expected_trigger": "schedule_query"},
        {"query": u(r"\u966a\u6211\u804a\u5929"), "expected_decision": "trigger", "expected_trigger": "smalltalk_chat"},
        {"query": u(r"\u8c03\u8bd5\u8fd9\u6bb5\u62a5\u9519"), "expected_decision": "trigger", "expected_trigger": "code_debug"},
    ]
    rows.extend(ask_rows)

    # Hard negatives and mixed-language paraphrases.
    rows.extend(
        [
            {"query": "reminder architecture design", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "message queue latency optimization", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "weather API integration guide", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "open source file parser", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "translate model benchmark", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "summarization papers 2025", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "schedule algorithm with constraints", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": "debugging mindset tutorial", "expected_decision": "no_trigger", "expected_trigger": ""},
            {"query": u(r"\u660e\u5929 remind me"), "expected_decision": "ask_clarification", "expected_trigger": "set_reminder"},
            {"query": u(r"\u7ed9Alice text"), "expected_decision": "ask_clarification", "expected_trigger": "send_message"},
            {"query": u(r"\u67e5\u4e00\u4e0b weather in Tokyo"), "expected_decision": "trigger", "expected_trigger": "weather_query"},
            {"query": u(r"\u7ffb\u8bd1 to English"), "expected_decision": "ask_clarification", "expected_trigger": "translate_text"},
            {"query": u(r"\u5f00\u59cb debug this crash"), "expected_decision": "trigger", "expected_trigger": "code_debug"},
        ]
    )
    return rows


def build_hard_negatives() -> List[Dict[str, Any]]:
    return [
        {"query": "set reminder architecture", "confusable_with": "set_reminder"},
        {"query": "alarm app ranking", "confusable_with": "set_alarm"},
        {"query": "message queue design", "confusable_with": "send_message"},
        {"query": "weather plugin development", "confusable_with": "weather_query"},
        {"query": "translate model training", "confusable_with": "translate_text"},
        {"query": "chatbot smalltalk dataset", "confusable_with": "smalltalk_chat"},
        {"query": "debugging tutorial basics", "confusable_with": "code_debug"},
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    triggers = build_triggers()
    cfg = build_config()
    eval_rows = build_eval_dataset(triggers)
    hard_neg = build_hard_negatives()

    (root / "data" / "triggers").mkdir(parents=True, exist_ok=True)
    (root / "data" / "eval").mkdir(parents=True, exist_ok=True)
    (root / "configs").mkdir(parents=True, exist_ok=True)

    (root / "data" / "triggers" / "default_triggers.yaml").write_text(
        json.dumps({"triggers": triggers}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / "configs" / "triggers.example.yaml").write_text(
        json.dumps({"triggers": [triggers[0]]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / "configs" / "app.example.yaml").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (root / "data" / "eval" / "eval_dataset.jsonl").open("w", encoding="utf-8") as f:
        for row in eval_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (root / "data" / "eval" / "hard_negatives.jsonl").open("w", encoding="utf-8") as f:
        for row in hard_neg:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "triggers": len(triggers),
                "eval_rows": len(eval_rows),
                "hard_negatives": len(hard_neg),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
