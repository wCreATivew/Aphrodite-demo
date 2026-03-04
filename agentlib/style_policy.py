from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


ACTIONS = ["comfort", "joke", "calm", "ask", "suggest"]


def _sl_softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    ex = np.exp(x)
    s = np.sum(ex)
    if s <= 0:
        return np.ones_like(x, dtype=np.float32) / max(1, len(x))
    return (ex / s).astype(np.float32)


def _hash_stable(s: str) -> int:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return int(h)


def featurize_for_style(user_text: str, state: Dict[str, Any], dim: int = 2048) -> np.ndarray:
    """
    Hash-trick bag-of-ngrams + a few scalar state features.
    Returns a vector of shape (dim + 8,).
    """
    t = (user_text or "").strip().lower()
    x = np.zeros((dim + 8,), dtype=np.float32)

    # character n-grams
    for n in (1, 2, 3):
        for i in range(0, max(0, len(t) - n + 1)):
            g = t[i : i + n]
            idx = _hash_stable(f"{n}:{g}") % dim
            x[idx] += 1.0

    # normalize
    norm = np.linalg.norm(x[:dim]) + 1e-6
    x[:dim] /= norm

    energy = float(state.get("energy", 60) or 60) / 100.0
    affinity = float(state.get("affinity", 20) or 20) / 100.0
    idle_pressure = float(state.get("idle_pressure", 0) or 0) / 100.0
    topic = str(state.get("topic", ""))

    x[dim + 0] = energy
    x[dim + 1] = affinity
    x[dim + 2] = idle_pressure
    x[dim + 3] = 1.0 if "tech" in topic else 0.0
    x[dim + 4] = 1.0 if "work" in topic else 0.0
    x[dim + 5] = 1.0 if "sad" in str(state.get("emotion", "")) else 0.0
    x[dim + 6] = 1.0 if "angry" in str(state.get("emotion", "")) else 0.0
    x[dim + 7] = 1.0  # bias

    return x


def infer_reward_from_user_text(
    user_text: str,
    pos_words: Optional[set[str]] = None,
    neg_words: Optional[set[str]] = None,
) -> float:
    """
    Heuristic reward from user text: +1 / -1 / 0.
    """
    t = (user_text or "").lower()
    pos_words = pos_words or set()
    neg_words = neg_words or set()
    hit_pos = any(w in t for w in pos_words)
    hit_neg = any(w in t for w in neg_words)
    if hit_pos and not hit_neg:
        return 1.0
    if hit_neg and not hit_pos:
        return -1.0
    return 0.0


@dataclass
class StyleDecision:
    action: str
    probs: Dict[str, float]
    debug: str


# RL knobs
RL_ENABLE = True
RL_USE_BASELINE = True
RL_BASELINE_BETA = 0.05
RL_USE_BATCH = False
RL_BATCH_SIZE = 16
RL_MAX_BUFFER = 512
RL_ADV_CLIP = 2.0
RL_REWARD_SHAPING = False


def _clip_value(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def _shape_reward(raw_reward: float, state_snapshot: Optional[Dict[str, Any]]) -> float:
    r = float(raw_reward)
    if not state_snapshot:
        return r

    idle_p = int(state_snapshot.get("idle_pressure", 0) or 0)
    if idle_p >= 85:
        r -= 0.15
    elif idle_p >= 60:
        r -= 0.08
    elif idle_p >= 40:
        r -= 0.04

    now = time.time()
    last_user_ts = state_snapshot.get("last_user_ts")
    dwell_sec = None
    if isinstance(last_user_ts, (int, float)):
        dwell_sec = max(0.0, now - float(last_user_ts))

    if dwell_sec is not None:
        if dwell_sec >= 600:
            r -= 0.05
        elif dwell_sec >= 180:
            r += 0.05
        elif dwell_sec >= 60:
            r += 0.02

    topic = str(state_snapshot.get("topic") or "").strip()
    prev_topic = str(state_snapshot.get("topic_prev") or "").strip()
    gap_sec = state_snapshot.get("gap_seconds")
    if isinstance(gap_sec, str):
        try:
            gap_sec = float(gap_sec)
        except Exception:
            gap_sec = None

    if topic and prev_topic:
        if topic == prev_topic:
            r += 0.03
        else:
            if isinstance(gap_sec, (int, float)) and gap_sec < 120:
                r -= 0.05

    return r


class SelfLearningStylePolicy:
    """
    Softmax policy + REINFORCE.
    - act(): sample an action
    - update(): update policy with reward
    """

    def __init__(
        self,
        dim: int = 2048,
        lr: float = 0.06,
        entropy_bonus: float = 0.01,
        temperature: float = 0.9,
        model_path: str = "style_policy.json",
    ):
        self.dim = dim
        self.lr = lr
        self.entropy_bonus = entropy_bonus
        self.temperature = temperature
        self.model_path = model_path

        self.num_actions = len(ACTIONS)
        self.D = dim + 8
        self.W = np.zeros((self.num_actions, self.D), dtype=np.float32)
        self._pending: Dict[str, Tuple[np.ndarray, int, np.ndarray, Optional[Dict[str, Any]]]] = {}
        self._last_msg_id: Optional[str] = None
        self._baseline = 0.0
        self._exp_buffer: List[Tuple[np.ndarray, int, np.ndarray, float]] = []

        self.load()

    def load(self) -> None:
        if not os.path.exists(self.model_path):
            return
        try:
            with open(self.model_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            W = np.array(data.get("W", []), dtype=np.float32)
            if W.shape == (self.num_actions, self.D):
                self.W = W
        except Exception:
            pass

    def save(self) -> None:
        try:
            data = {
                "W": self.W.tolist(),
                "dim": self.dim,
                "lr": self.lr,
                "entropy_bonus": self.entropy_bonus,
                "temperature": self.temperature,
                "timestamp": time.time(),
            }
            with open(self.model_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def act(self, user_text: str, state: Dict[str, Any], msg_id: Optional[str] = None) -> StyleDecision:
        x = featurize_for_style(user_text, state, dim=self.dim)
        logits = (self.W @ x) / max(1e-6, float(self.temperature))
        p = _sl_softmax(logits)

        a = int(np.random.choice(self.num_actions, p=p))

        if msg_id is None:
            msg_id = f"__local_{time.time():.6f}"
        state_snapshot = {
            "idle_pressure": state.get("idle_pressure"),
            "energy": state.get("energy"),
            "affinity": state.get("affinity"),
            "topic": state.get("topic"),
            "topic_prev": state.get("topic_prev"),
            "gap_seconds": state.get("gap_seconds"),
            "last_user_ts": state.get("last_user_ts"),
            "last_turn_ts": state.get("last_turn_ts"),
            "session_start_ts": state.get("session_start_ts"),
        }
        self._pending[str(msg_id)] = (x, a, p, state_snapshot)
        self._last_msg_id = str(msg_id)

        if len(self._pending) > 300:
            for k in list(self._pending.keys())[:100]:
                self._pending.pop(k, None)

        probs = {ACTIONS[i]: float(p[i]) for i in range(self.num_actions)}
        debug = f"logits={np.round(logits,3).tolist()} p={np.round(p,3).tolist()} chosen={ACTIONS[a]}"
        return StyleDecision(action=ACTIONS[a], probs=probs, debug=debug)

    def update_for_msg(self, msg_id: str, reward: float) -> None:
        key = str(msg_id)
        if key not in self._pending:
            return

        item = self._pending.get(key)
        if not item:
            return
        if len(item) == 3:
            x, a, p = item  # type: ignore
            state_snapshot = None
        else:
            x, a, p, state_snapshot = item  # type: ignore
        if x is None or p is None:
            return

        r = _clip_value(float(reward), -1.0, 1.0)
        if RL_ENABLE and RL_REWARD_SHAPING:
            r = _clip_value(_shape_reward(r, state_snapshot), -1.0, 1.0)

        adv = r
        if RL_ENABLE and RL_USE_BASELINE:
            self._baseline = (1.0 - float(RL_BASELINE_BETA)) * self._baseline + float(RL_BASELINE_BETA) * r
            adv = r - self._baseline
        if RL_ENABLE:
            adv = _clip_value(adv, -float(RL_ADV_CLIP), float(RL_ADV_CLIP))

        if RL_ENABLE and RL_USE_BATCH:
            self._exp_buffer.append((x, int(a), p, float(adv)))
            if len(self._exp_buffer) < int(RL_BATCH_SIZE):
                self._pending.pop(key, None)
                return
            batch = self._exp_buffer[-int(RL_BATCH_SIZE):]
            self._exp_buffer = self._exp_buffer[-int(RL_MAX_BUFFER):]
            grad = np.zeros_like(self.W)
            for bx, ba, bp, badv in batch:
                y = np.zeros(self.num_actions, dtype=np.float32)
                y[int(ba)] = 1.0
                g = (y - bp).reshape(-1, 1) * bx.reshape(1, -1) * float(badv)
                ent_grad = (-bp * (np.log(bp + 1e-12) + 1.0)).reshape(-1, 1) * bx.reshape(1, -1)
                g += float(self.entropy_bonus) * ent_grad
                grad += g
            grad /= float(len(batch))
            self.W += float(self.lr) * grad
        else:
            y = np.zeros(self.num_actions, dtype=np.float32)
            y[int(a)] = 1.0
            grad = (y - p).reshape(-1, 1) * x.reshape(1, -1) * float(adv)

            ent_grad = (-p * (np.log(p + 1e-12) + 1.0)).reshape(-1, 1) * x.reshape(1, -1)
            grad += float(self.entropy_bonus) * ent_grad

            self.W += float(self.lr) * grad
        self.save()

        self._pending.pop(key, None)

    def update_last(self, reward: float) -> None:
        if not self._last_msg_id:
            return
        self.update_for_msg(self._last_msg_id, reward)

    def update(self, reward: float) -> None:
        self.update_last(reward)


def style_guidance_from_action(action: str) -> str:
    if action == "comfort":
        return "This turn should be comforting: acknowledge feelings, then a light suggestion."
    if action == "joke":
        return "This turn can be light and humorous, but still helpful."
    if action == "calm":
        return "This turn should be calm, structured, and direct."
    if action == "ask":
        return "This turn should ask one clarifying question."
    return "This turn should provide 2-4 actionable suggestions."
