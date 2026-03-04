# status_writer.py
from __future__ import annotations
import json
import os
import tempfile
import time
from typing import Any, Dict

def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    """
    稳定写 JSON：先写到临时文件，再原子替换，避免前端读到半截内容。
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".status_", suffix=".json", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())  # 强制落盘，更稳
        os.replace(tmp_path, path)  # 原子替换
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass

def build_status(metrics: Dict[str, Any], extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {
        "ts_unix": time.time(),
        "ts_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": metrics,
    }
    if extra:
        payload.update(extra)
    return payload
