#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Batch run q.json and output responses as:
[
  {"id":"Q01","variant":"base","response":"..."},
  ...
]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover
    print("openai import failed:", e)
    sys.exit(1)


DEFAULT_SYSTEM = (
    "你是评测助手。请直接给结论（有用/没用/取决于），"
    "并用不超过两句话给出原因。"
)


def _read_json(path: str) -> Any:
    # Try utf-8 first, then gbk for legacy files
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except Exception:
            continue
    raise RuntimeError(f"Failed to read JSON with utf-8/gbk: {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="q.json")
    ap.add_argument("--out", dest="out", default="q_out.json")
    ap.add_argument("--model", dest="model", default=os.getenv("TEST_MODEL") or os.getenv("QWEN_MODEL") or "qwen3-max")
    ap.add_argument("--system", dest="system", default=DEFAULT_SYSTEM)
    ap.add_argument("--max-tokens", dest="max_tokens", type=int, default=300)
    ap.add_argument("--temperature", dest="temperature", type=float, default=0.2)
    args = ap.parse_args()

    data = _read_json(args.inp)
    if not isinstance(data, list):
        raise RuntimeError("Input JSON must be a list of objects")

    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = (
        os.getenv("DASHSCOPE_BASE_URL")
        or os.getenv("QWEN_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    client = OpenAI(api_key=api_key, base_url=base_url)
    out: List[Dict[str, Any]] = []
    variants = ["base", "example", "counter_example"]

    for item in data:
        qid = str(item.get("id", "")).strip()
        if not qid:
            continue
        for v in variants:
            text = str(item.get(v, "")).strip()
            if not text:
                continue
            messages = [
                {"role": "system", "content": args.system},
                {"role": "user", "content": text},
            ]
            resp = client.chat.completions.create(
                model=args.model,
                messages=messages,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            out.append({"id": qid, "variant": v, "response": content})

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(out)} rows -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
