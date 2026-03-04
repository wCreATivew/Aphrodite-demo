from __future__ import annotations

import os
import sqlite3
import threading
import time
from typing import Any, Dict, Callable


class MetricsDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=30000;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                ts_unix   REAL NOT NULL,
                run_id    TEXT NOT NULL,
                pid       INTEGER,
                name      TEXT NOT NULL,
                value     REAL,
                text      TEXT,
                PRIMARY KEY (ts_unix, run_id, pid, name)
            );
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(ts_unix);")
        self._conn.commit()
        self._lock = threading.Lock()

    def write(self, ts_unix: float, run_id: str, pid: int, metrics: Dict[str, Any]) -> None:
        rows = []
        for k, v in (metrics or {}).items():
            if v is None:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                rows.append((ts_unix, run_id, pid, str(k), float(v), None))
            else:
                rows.append((ts_unix, run_id, pid, str(k), None, str(v)))

        if not rows:
            return

        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO metrics(ts_unix, run_id, pid, name, value, text) VALUES (?,?,?,?,?,?)",
                rows,
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass


def start_metrics_thread(
    stop_event: threading.Event,
    get_metrics_fn: Callable[[], Dict[str, Any]],
    db_path: str,
    run_id: str,
    interval_sec: float = 10.0,
) -> threading.Thread:
    """Start a daemon thread that samples metrics and writes to SQLite."""
    db = MetricsDB(db_path)
    pid = os.getpid()

    def _loop() -> None:
        next_t = time.time()
        while not stop_event.is_set():
            now = time.time()
            if now >= next_t:
                try:
                    db.write(ts_unix=now, run_id=run_id, pid=pid, metrics=get_metrics_fn() or {})
                except Exception:
                    pass
                next_t = now + interval_sec
            time.sleep(0.2)
        db.close()

    th = threading.Thread(target=_loop, daemon=True, name="metrics-writer")
    th.start()
    return th
