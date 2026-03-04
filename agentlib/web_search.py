from __future__ import annotations

import time
from typing import Dict, Tuple


_web_cache: Dict[str, Tuple[float, str]] = {}


def web_search(
    query: str,
    enabled: bool = False,
    max_results: int = 3,
    cache_ttl_sec: int = 3600,
) -> str:
    """
    Lightweight search via duckduckgo-search (optional).
    """
    if not enabled:
        return ""

    q = (query or "").strip()
    if not q:
        return ""

    now = time.time()
    cached = _web_cache.get(q)
    if cached and now - cached[0] < cache_ttl_sec:
        return cached[1]

    try:
        from duckduckgo_search import DDGS
    except Exception:
        return ""

    out_lines = []
    try:
        with DDGS() as ddgs:
            for i, r in enumerate(ddgs.text(q, max_results=max_results)):
                if i >= int(max_results):
                    break
                title = str(r.get("title") or "").strip()
                body = str(r.get("body") or "").strip()
                href = str(r.get("href") or "").strip()
                line = title
                if body:
                    line += f" - {body}"
                if href:
                    line += f" ({href})"
                if line:
                    out_lines.append(line)
    except Exception:
        return ""

    result = "\n".join(out_lines)
    _web_cache[q] = (now, result)
    return result
