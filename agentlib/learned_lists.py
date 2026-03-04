from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern, Set


DEFAULT_FILLERS = [
    "嗯", "呃", "嗯嗯", "那个", "这个", "唔", "呀", "哎", "哎呀",
    "哈哈", "嘿", "嗯哼", "啊", "em", "emm",
]
DEFAULT_POS_WORDS = ["好", "赞", "喜欢", "棒", "满意", "谢谢", "nice", "thx", "thanks", "good"]
DEFAULT_NEG_WORDS = ["不", "差", "讨厌", "生气", "烦", "停", "stop"]
DEFAULT_STOP_CHARS = list("的了在就和呀啊哦嗯呃这那")
DEFAULT_ALLOW_SINGLE = list("爱美酷甜暖暖萌")
DEFAULT_STOP_PHRASES = {
    "你好", "谢谢", "哈哈", "我不理解", "我在听", "抱抱", "呜呜", "好的",
}


@dataclass
class ListState:
    fillers: List[str]
    filler_prefix_re: Pattern[str]
    pos_words: Set[str]
    neg_words: Set[str]
    stop_chars: Set[str]
    allow_single: Set[str]
    stop_phrases: Set[str]


class LearnedLists:
    def __init__(self, path: str, defaults: Optional[Dict[str, List[str]]] = None):
        self.path = path
        self._lock = threading.Lock()
        self._last_save_ts = 0.0
        self.data: Dict[str, List[str]] = {}
        if defaults:
            for k, v in defaults.items():
                self.data[str(k)] = [str(x) for x in (v or []) if str(x).strip()]
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                with self._lock:
                    for k, v in obj.items():
                        if isinstance(v, list):
                            items = [str(x) for x in v if str(x).strip()]
                            if k in self.data:
                                self.data[k] = self._merge_unique(self.data[k], items)
                            else:
                                self.data[k] = items
        except Exception:
            pass

    def save(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_save_ts < 1.5:
            return
        try:
            with self._lock:
                payload = {k: list(v) for k, v in self.data.items()}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self._last_save_ts = now
        except Exception:
            pass

    def ensure_list(self, name: str, defaults: List[str]) -> None:
        key = str(name)
        with self._lock:
            if key not in self.data:
                self.data[key] = [str(x) for x in defaults if str(x).strip()]
            else:
                self.data[key] = self._merge_unique(self.data[key], defaults)
        self.save()

    def get_list(self, name: str, defaults: Optional[List[str]] = None) -> List[str]:
        key = str(name)
        with self._lock:
            items = list(self.data.get(key, []))
        if not items and defaults:
            items = [str(x) for x in defaults if str(x).strip()]
        return self._merge_unique([], items)

    def add_items(
        self,
        name: str,
        items: List[str],
        min_len: int = 1,
        max_len: int = 32,
        max_add: int = 50,
    ) -> None:
        if not items:
            return
        key = str(name)
        cleaned: List[str] = []
        for raw in items:
            s = str(raw).strip()
            if not s:
                continue
            if len(s) < int(min_len) or len(s) > int(max_len):
                continue
            cleaned.append(s)
        if not cleaned:
            return
        cleaned = self._merge_unique([], cleaned)[:int(max_add)]
        with self._lock:
            cur = self.data.get(key, [])
            self.data[key] = self._merge_unique(cur, cleaned)
        self.save()

    @staticmethod
    def _merge_unique(existing: List[str], new_items: List[str]) -> List[str]:
        seen = set(existing)
        out = list(existing)
        for item in new_items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out


def init_learned_lists(path: str) -> LearnedLists:
    ll = LearnedLists(
        path,
        defaults={
            "fillers": DEFAULT_FILLERS,
            "pos_words": DEFAULT_POS_WORDS,
            "neg_words": DEFAULT_NEG_WORDS,
            "stop_chars": DEFAULT_STOP_CHARS,
            "allow_single": DEFAULT_ALLOW_SINGLE,
        },
    )
    ll.ensure_list("stop_phrases", list(DEFAULT_STOP_PHRASES))
    return ll


def refresh_state(learned_lists: LearnedLists) -> ListState:
    fillers = learned_lists.get_list("fillers", DEFAULT_FILLERS)
    filler_prefix_re = re.compile(
        r"^\s*(?:"
        + "|".join(map(re.escape, sorted(fillers, key=len, reverse=True)))
        + r")([，,。.\s…~！!？?]*)"
    )
    pos_words = {str(x).lower() for x in learned_lists.get_list("pos_words", DEFAULT_POS_WORDS)}
    neg_words = {str(x).lower() for x in learned_lists.get_list("neg_words", DEFAULT_NEG_WORDS)}
    stop_chars = set(learned_lists.get_list("stop_chars", DEFAULT_STOP_CHARS))
    allow_single = set(learned_lists.get_list("allow_single", DEFAULT_ALLOW_SINGLE))
    stop_phrases = set(learned_lists.get_list("stop_phrases", list(DEFAULT_STOP_PHRASES)))
    return ListState(
        fillers=fillers,
        filler_prefix_re=filler_prefix_re,
        pos_words=pos_words,
        neg_words=neg_words,
        stop_chars=stop_chars,
        allow_single=allow_single,
        stop_phrases=stop_phrases,
    )
