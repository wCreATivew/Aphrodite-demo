# -*- coding: utf-8 -*-
"""
Offline trainer for the style policy.

- Samples chat logs from monitor/metrics.db (chat_inbox + chat_feedback).
- Distills from the current policy (style_policy.json).
- Adds supervised weighting from explicit +/- feedback.

Usage:
  py offline_train_style_policy.py --db monitor/metrics.db --policy style_policy.json --out style_policy_offline.json
"""
import argparse
import json
import math
import os
import random
import sqlite3
import time
import hashlib
from typing import Dict, List, Optional, Tuple

import numpy as np

ACTIONS = ["comfort", "joke", "calm", "ask", "suggest"]


def _hash_stable(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    ex = np.exp(x)
    return ex / (np.sum(ex) + 1e-12)


def featurize_for_style(user_text: str, state: Dict[str, float], dim: int = 2048) -> np.ndarray:
    """
    Matches the hashing trick features used online.
    """
    x = np.zeros(dim + 8, dtype=np.float32)
    t = (user_text or "").strip()[:500]

    for n in (2, 3, 4):
        for i in range(0, max(0, len(t) - n + 1)):
            g = t[i : i + n]
            idx = _hash_stable(f"{n}:{g}") % dim
            x[idx] += 1.0

    norm = np.linalg.norm(x[:dim]) + 1e-6
    x[:dim] /= norm

    energy = float(state.get("energy", 60.0)) / 100.0
    affinity = float(state.get("affinity", 20.0)) / 100.0
    idle_pressure = float(state.get("idle_pressure", 0.0)) / 100.0
    topic = str(state.get("topic", ""))

    x[dim + 0] = energy
    x[dim + 1] = affinity
    x[dim + 2] = idle_pressure
    x[dim + 3] = 1.0 if "tech" in topic else 0.0
    x[dim + 4] = 1.0 if "work" in topic else 0.0
    x[dim + 5] = 1.0 if "sad" in str(state.get("emotion", "")) else 0.0
    x[dim + 6] = 1.0 if "angry" in str(state.get("emotion", "")) else 0.0
    x[dim + 7] = 1.0

    return x


def _extract_text_from_payload(payload: str) -> str:
    if payload is None:
        return ""
    try:
        obj = json.loads(payload)
    except Exception:
        return str(payload)
    if isinstance(obj, dict):
        return str(obj.get("text") or obj.get("content") or obj.get("prompt") or "")
    return str(obj)


class StylePolicy:
    def __init__(self, dim: int = 2048, temperature: float = 0.9):
        self.dim = dim
        self.temperature = temperature
        self.num_actions = len(ACTIONS)
        self.D = dim + 8
        self.W = np.zeros((self.num_actions, self.D), dtype=np.float32)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        W = np.array(data.get("W", []), dtype=np.float32)
        if W.shape == (self.num_actions, self.D):
            self.W = W

    def save(self, path: str) -> None:
        data = {
            "W": self.W.tolist(),
            "dim": self.dim,
            "temperature": self.temperature,
            "timestamp": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def probs(self, x: np.ndarray) -> np.ndarray:
        logits = (self.W @ x) / max(1e-6, float(self.temperature))
        return _softmax(logits)


def _normalize(v: np.ndarray) -> np.ndarray:
    s = float(np.sum(v))
    if s <= 1e-12:
        return np.ones_like(v) / float(len(v))
    return v / s


def _load_feedback_map(conn: sqlite3.Connection) -> Dict[str, Tuple[int, str]]:
    try:
        rows = conn.execute(
            "SELECT msg_id, rating, comment FROM chat_feedback WHERE status='done'"
        ).fetchall()
    except Exception:
        return {}
    out: Dict[str, Tuple[int, str]] = {}
    for msg_id, rating, comment in rows:
        out[str(msg_id)] = (int(rating), str(comment or ""))
    return out


def _load_samples(conn: sqlite3.Connection, limit: Optional[int] = None) -> List[Tuple[str, float, str]]:
    sql = "SELECT id, ts_unix, payload FROM chat_inbox ORDER BY ts_unix ASC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    out: List[Tuple[str, float, str]] = []
    for msg_id, ts_unix, payload in rows:
        text = _extract_text_from_payload(payload)
        if not text or not str(text).strip():
            continue
        out.append((str(msg_id), float(ts_unix), text))
    return out


def _metrics_state_for_ts(conn: sqlite3.Connection, ts_unix: float) -> Dict[str, float]:
    out: Dict[str, float] = {}
    try:
        rows = conn.execute(
            "SELECT ts_unix, name, value, text FROM metrics WHERE ts_unix <= ? "
            "ORDER BY ts_unix DESC LIMIT 300",
            (float(ts_unix),),
        ).fetchall()
    except Exception:
        return out
    for _ts, name, value, text in rows:
        key = str(name)
        if key in out:
            continue
        if value is not None:
            out[key] = float(value)
        elif text is not None:
            out[key] = text  # type: ignore[assignment]
        if len(out) >= 8:
            break
    return out


def train_offline(
    db_path: str,
    policy_path: str,
    out_path: str,
    epochs: int = 3,
    lr: float = 0.04,
    temperature: float = 0.9,
    sample_limit: Optional[int] = None,
    seed: int = 7,
    use_metrics: bool = False,
    dump_jsonl: Optional[str] = None,
) -> None:
    rng = random.Random(seed)

    conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=30000;")

    feedback = _load_feedback_map(conn)
    samples = _load_samples(conn, limit=sample_limit)
    if not samples:
        print("No chat_inbox rows found.")
        return

    policy = StylePolicy(temperature=temperature)
    policy.load(policy_path)

    dataset = []
    for msg_id, ts_unix, text in samples:
        state = {
            "energy": 60.0,
            "affinity": 20.0,
            "idle_pressure": 0.0,
            "topic": "",
            "emotion": "",
        }
        if use_metrics:
            state.update(_metrics_state_for_ts(conn, ts_unix))
        x = featurize_for_style(text, state)

        teacher = policy.probs(x)
        rating, comment = feedback.get(msg_id, (0, ""))
        if rating > 0:
            target = teacher
            weight = 1.2
        elif rating < 0:
            target = _normalize(1.0 - teacher)
            weight = 1.1
        else:
            target = teacher
            weight = 1.0

        dataset.append((x, target.astype(np.float32), float(weight), msg_id, text, int(rating), comment))

    if dump_jsonl:
        with open(dump_jsonl, "w", encoding="utf-8") as f:
            for _x, target, weight, msg_id, text, rating, comment in dataset:
                rec = {
                    "id": msg_id,
                    "text": text,
                    "target": target.tolist(),
                    "weight": weight,
                    "rating": rating,
                    "comment": comment,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    for ep in range(int(epochs)):
        rng.shuffle(dataset)
        total_loss = 0.0
        for x, target, weight, *_rest in dataset:
            p = policy.probs(x)
            grad = (target - p).reshape(-1, 1) * x.reshape(1, -1)
            policy.W += float(lr) * float(weight) * grad
            loss = -float(np.sum(target * np.log(p + 1e-12)))
            total_loss += loss
        avg_loss = total_loss / max(1, len(dataset))
        print(f"epoch {ep+1}/{epochs} loss={avg_loss:.4f}")

    policy.save(out_path)
    conn.close()
    print(f"saved: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="monitor/metrics.db", help="SQLite db with chat logs")
    parser.add_argument("--policy", default="style_policy.json", help="input policy json")
    parser.add_argument("--out", default="style_policy_offline.json", help="output policy json")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=0.04)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--sample", type=int, default=0, help="limit samples")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--use-metrics", action="store_true")
    parser.add_argument("--dump-jsonl", default="")
    args = parser.parse_args()

    sample_limit = args.sample if args.sample and args.sample > 0 else None
    dump_jsonl = args.dump_jsonl.strip() or None

    train_offline(
        db_path=args.db,
        policy_path=args.policy,
        out_path=args.out,
        epochs=args.epochs,
        lr=args.lr,
        temperature=args.temperature,
        sample_limit=sample_limit,
        seed=args.seed,
        use_metrics=args.use_metrics,
        dump_jsonl=dump_jsonl,
    )


if __name__ == "__main__":
    main()
