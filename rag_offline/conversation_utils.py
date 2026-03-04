from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence


POS_MARKERS = {
    "good",
    "great",
    "helpful",
    "useful",
    "yes",
    "对",
    "是",
    "可以",
    "有用",
    "满意",
    "不错",
}
NEG_MARKERS = {
    "bad",
    "wrong",
    "useless",
    "no",
    "not",
    "不对",
    "不是",
    "没用",
    "不行",
    "不满意",
}


def infer_feedback_signal(text: str) -> int:
    t = str(text or "").strip().lower()
    if not t:
        return 0
    if any(x in t for x in NEG_MARKERS):
        return -1
    if any(x in t for x in POS_MARKERS):
        return 1
    return 0


def pick_pseudo_triplet(
    *,
    query: str,
    retrieved_docs: Sequence[str],
    corpus_docs: Sequence[str],
    feedback_signal: int,
    rng: Optional[random.Random] = None,
) -> Optional[Dict[str, str]]:
    q = str(query or "").strip()
    if not q:
        return None

    retrieved = [str(x).strip() for x in retrieved_docs if str(x).strip()]
    corpus = [str(x).strip() for x in corpus_docs if str(x).strip()]
    if not retrieved or len(corpus) < 2:
        return None

    r = rng or random.Random(7)
    pool_neg = [x for x in corpus if x not in set(retrieved)]
    if not pool_neg:
        return None

    if feedback_signal < 0 and len(retrieved) >= 2:
        positive = retrieved[1]
        negative = retrieved[0]
    elif feedback_signal < 0 and len(pool_neg) >= 1:
        # when user says this answer is wrong, treat top retrieved as hard negative
        negative = retrieved[0]
        positive = r.choice(pool_neg)
    else:
        positive = retrieved[0]
        negative = r.choice(pool_neg)

    if positive == negative:
        return None
    return {"query": q, "positive": positive, "negative": negative}
