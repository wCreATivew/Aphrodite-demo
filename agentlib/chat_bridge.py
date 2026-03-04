from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, Optional


EventHandler = Callable[[Dict[str, Any]], None]
FeedbackHandler = Callable[[str, float, str, str], None]


def ensure_chat_tables_backend(db_path: str) -> None:
    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=30000;")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_inbox(
            id TEXT PRIMARY KEY,
            ts_unix REAL NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new'
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_inbox_ts ON chat_inbox(ts_unix);")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_outbox(
            id TEXT PRIMARY KEY,
            ts_unix REAL NOT NULL,
            reply TEXT NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_outbox_ts ON chat_outbox(ts_unix);")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_feedback(
            id TEXT PRIMARY KEY,
            ts_unix REAL NOT NULL,
            msg_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            status TEXT NOT NULL DEFAULT 'new'
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_feedback_ts ON chat_feedback(ts_unix);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_feedback_msg ON chat_feedback(msg_id);")
    conn.commit()
    conn.close()


def db_set_inbox_status(db_path: str, msg_id: str, status: str) -> None:
    try:
        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("UPDATE chat_inbox SET status=? WHERE id=?", (status, msg_id))
        conn.commit()
        conn.close()
    except Exception:
        pass


def db_write_outbox(db_path: str, msg_id: str, reply_text: str) -> None:
    try:
        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute(
            "INSERT OR REPLACE INTO chat_outbox(id, ts_unix, reply) VALUES (?,?,?)",
            (msg_id, time.time(), str(reply_text)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def db_write_system_pair(db_path: str, reply_text: str, tag: str = "idle") -> Optional[str]:
    try:
        msg_id = f"system_{int(time.time() * 1000)}"
        payload = {"type": "SYSTEM", "text": "", "tag": str(tag)}
        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute(
            "INSERT INTO chat_inbox(id, ts_unix, payload, status) VALUES (?,?,?,?)",
            (msg_id, time.time(), json.dumps(payload, ensure_ascii=False), "done"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO chat_outbox(id, ts_unix, reply) VALUES (?,?,?)",
            (msg_id, time.time(), str(reply_text)),
        )
        conn.commit()
        conn.close()
        return msg_id
    except Exception:
        return None


def extract_text_from_payload(payload: str) -> str:
    if payload is None:
        return ""
    try:
        obj = json.loads(payload)
    except Exception:
        return str(payload)
    if isinstance(obj, dict):
        return str(obj.get("text") or obj.get("content") or obj.get("prompt") or "")
    return str(obj)


class ChatBridge:
    def __init__(
        self,
        db_path: str,
        stop_event: threading.Event,
        on_event: EventHandler,
        on_feedback: FeedbackHandler,
    ):
        self.db_path = db_path
        self.stop_event = stop_event
        self.on_event = on_event
        self.on_feedback = on_feedback
        self._threads: list[threading.Thread] = []

    def start(self) -> list[threading.Thread]:
        ensure_chat_tables_backend(self.db_path)
        self._threads = [
            threading.Thread(target=self._pull_inbox_loop, daemon=True, name="db-chat-pull"),
            threading.Thread(target=self._pull_feedback_loop, daemon=True, name="db-chat-feedback"),
        ]
        for th in self._threads:
            th.start()
        return list(self._threads)

    def _pull_inbox_loop(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=30000;")
        while not self.stop_event.is_set():
            try:
                rows = conn.execute(
                    "SELECT id, payload FROM chat_inbox WHERE status='new' ORDER BY ts_unix ASC LIMIT 5"
                ).fetchall()
                if not rows:
                    time.sleep(0.2)
                    continue
                for msg_id, payload in rows:
                    cur = conn.execute("UPDATE chat_inbox SET status='processing' WHERE id=? AND status='new'", (msg_id,))
                    if cur.rowcount == 0:
                        continue
                    conn.commit()
                    evt = json.loads(payload)
                    evt["msg_id"] = msg_id
                    self.on_event(evt)
            except Exception:
                time.sleep(0.5)
        conn.close()

    def _pull_feedback_loop(self) -> None:
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=30000;")
        while not self.stop_event.is_set():
            try:
                rows = conn.execute(
                    "SELECT id, msg_id, rating, comment FROM chat_feedback WHERE status='new' ORDER BY ts_unix ASC LIMIT 10"
                ).fetchall()
                if not rows:
                    time.sleep(0.3)
                    continue
                for fb_id, msg_id, rating, comment in rows:
                    conn.execute("UPDATE chat_feedback SET status='processing' WHERE id=?", (fb_id,))
                    conn.commit()
                    try:
                        rv = float(rating)
                        if rv > 0:
                            r = 1.0
                        elif rv < 0:
                            r = -1.0
                        else:
                            r = 0.0
                    except Exception:
                        r = 0.0
                    try:
                        payload_row = conn.execute("SELECT payload FROM chat_inbox WHERE id=?", (msg_id,)).fetchone()
                        payload_text = extract_text_from_payload(payload_row[0]) if payload_row else ""
                    except Exception:
                        payload_text = ""
                    self.on_feedback(str(msg_id), float(r), str(comment or ""), payload_text)
                    conn.execute("UPDATE chat_feedback SET status='done' WHERE id=?", (fb_id,))
                    conn.commit()
            except Exception:
                time.sleep(0.5)
        conn.close()
