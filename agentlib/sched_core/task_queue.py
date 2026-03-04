from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Task:
    id: int
    text: str
    status: str
    priority: int
    created_at: float
    updated_at: float


class TaskQueue:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=30000;")
        self._lock = threading.Lock()
        self._init_table()

    def _init_table(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);")
            self._conn.commit()

    def add(self, text: str, priority: int = 0) -> int:
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tasks(text, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (str(text), "pending", int(priority), now, now),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def list(self, status: Optional[str] = None, limit: int = 50) -> List[Task]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT id, text, status, priority, created_at, updated_at FROM tasks WHERE status=? "
                    "ORDER BY priority DESC, id ASC LIMIT ?",
                    (str(status), int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, text, status, priority, created_at, updated_at FROM tasks "
                    "ORDER BY priority DESC, id ASC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [Task(*row) for row in rows]

    def next(self) -> Optional[Task]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, text, status, priority, created_at, updated_at FROM tasks WHERE status='pending' "
                "ORDER BY priority DESC, id ASC LIMIT 1"
            ).fetchone()
        return Task(*row) if row else None

    def set_status(self, task_id: int, status: str) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
                (str(status), now, int(task_id)),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
