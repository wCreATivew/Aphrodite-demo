#!/usr/bin/env python
# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path


def load_module(path: str):
    spec = importlib.util.spec_from_file_location("agent_mod", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


class DummyMemoryStore:
    def __init__(self, items):
        self._items = items

    def retrieve_with_meta(self, query, k=6):
        return self._items[:k]


def extract_system_text(messages):
    for m in messages:
        if m.get("role") == "system":
            return m.get("content", "")
    return ""


def count_memory_lines(system_text: str) -> int:
    # count "- " lines under memory block
    lines = system_text.splitlines()
    count = 0
    in_block = False
    for ln in lines:
        if "【相关记忆" in ln:
            in_block = True
            continue
        if in_block and ln.startswith("【"):
            break
        if in_block and ln.strip().startswith("- "):
            count += 1
    return count


def main():
    mod_path = str(Path(__file__).with_name("A0.32026205.01.py"))
    mod = load_module(mod_path)

    # 1) eval question
    mod.memory_store = DummyMemoryStore([])
    msgs, _ = mod.build_messages("这个方案有没有用？")
    sys_text = extract_system_text(msgs)
    assert "Verdict" in sys_text, "eval verdict rule missing"
    assert "失败条件" in sys_text, "failure condition rule missing"

    # 2) eval + example
    msgs, _ = mod.build_messages("这个方案有没有用？比如：我会把top-k揉成一句话。")
    sys_text = extract_system_text(msgs)
    assert "示例：" in sys_text, "example formatting rule missing"

    # 3) conflict memory + evidence budget
    mem_items = [
        {"id": 1, "text": "用户不吃牛肉", "tags": [("牛肉", 0.8)]},
        {"id": 2, "text": "用户喜欢牛肉汉堡", "tags": [("牛肉", 0.7)]},
        {"id": 3, "text": "用户最近在健身", "tags": [("健身", 0.6)]},
        {"id": 4, "text": "用户喜欢跑步", "tags": [("跑步", 0.6)]},
    ]
    mod.memory_store = DummyMemoryStore(mem_items)
    msgs, _ = mod.build_messages("我该给他推荐什么午餐？")
    sys_text = extract_system_text(msgs)
    assert "记忆冲突" in sys_text, "conflict rule missing"
    assert count_memory_lines(sys_text) <= mod.MEM_EVIDENCE_MAX, "evidence budget exceeded"

    print("ok")


if __name__ == "__main__":
    main()
