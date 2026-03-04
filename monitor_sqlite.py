# monitor_sqlite.py
from __future__ import annotations
import os
import sqlite3
import time
import threading
from typing import Any, Dict, Optional

class MetricsDB:
    def __init__(self, db_path: str = "monitor/metrics.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,  # 允许后台线程写
            timeout=30.0,
        )
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=30000;")
        self._conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            ts_unix   REAL NOT NULL,
            run_id    TEXT NOT NULL,
            pid       INTEGER,
            name      TEXT NOT NULL,
            value     REAL,
            text      TEXT,
            PRIMARY KEY (ts_unix, run_id, pid, name)
        );
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(ts_unix);")
        self._conn.commit()
        self._lock = threading.Lock()

    def write(self, ts_unix: float, run_id: str, pid: int, metrics: Dict[str, Any]) -> None:
        """
        把一批 metrics 以 (name,value/text) 形式写入。
        - 数值 -> value
        - 非数值 -> text（也会存）
        """
        rows = []
        for k, v in metrics.items():
            if v is None:
                continue
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                rows.append((ts_unix, run_id, pid, str(k), float(v), None))
            else:
                # 非数值进 text（比如 emotion/topic）
                rows.append((ts_unix, run_id, pid, str(k), None, str(v)))

        if not rows:
            return

        # 稳定写：加锁 + 事务
        with self._lock:
            # 如果未来多进程同时写，WAL + timeout/busy_timeout 会让冲突更少
            self._conn.executemany(
                "INSERT OR REPLACE INTO metrics(ts_unix, run_id, pid, name, value, text) VALUES (?,?,?,?,?,?)",
                rows
            )
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()


def start_metrics_thread(
    stop_event,
    get_metrics_fn,
    db_path: str = "monitor/metrics.db",
    run_id: str = "default",
    interval_sec: float = 10.0,
):
    """
    启动后台线程：每 interval_sec 采样一次 get_metrics_fn() 并写 DB
    get_metrics_fn: () -> Dict[str, Any]
    """
    import os

    db = MetricsDB(db_path=db_path)
    pid = os.getpid()

    def loop():
        # 让采样更“准”：用下一次目标时间推进，而不是 sleep(interval) 累积漂移
        next_t = time.time()
        while not stop_event.is_set():
            now = time.time()
            if now >= next_t:
                try:
                    metrics = get_metrics_fn() or {}
                    db.write(ts_unix=now, run_id=run_id, pid=pid, metrics=metrics)
                except Exception:
                    # 监控线程绝不应该把主程序搞崩；必要时你可以在这里加日志
                    pass
                next_t = now + interval_sec
            time.sleep(0.2)

        db.close()

    th = threading.Thread(target=loop, daemon=True, name="metrics-writer")
    th.start()
    return th
