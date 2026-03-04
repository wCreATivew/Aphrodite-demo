from __future__ import annotations

import os
from typing import Iterable

_ENV_LOADED = False


def _env_candidates() -> Iterable[str]:
    cwd = os.getcwd()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yield os.path.join(cwd, ".env")
    if repo_root != cwd:
        yield os.path.join(repo_root, ".env")


def load_local_env_once() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    seen = set()
    for path in _env_candidates():
        if path in seen:
            continue
        seen.add(path)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = str(raw or "").strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    if key and (os.getenv(key) is None):
                        os.environ[key] = value
        except Exception:
            continue
