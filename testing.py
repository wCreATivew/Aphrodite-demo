import json
import re
from collections import defaultdict

# ---------- Heuristics ----------
VERDICT_PATTERNS = [
    ("YES", re.compile(r"\b(yes|useful|recommended)\b", re.I)),
    ("NO", re.compile(r"\b(no|not\s+useful|not\s+recommended|useless)\b", re.I)),
    ("DEPENDS", re.compile(r"\b(depends|it\s+depends)\b", re.I)),
    # Chinese
    ("YES", re.compile(r"(有用|建议|可行|值得|推荐)")),
    ("NO", re.compile(r"(没用|不建议|不可行|不值得|不推荐|不太有用|风险很大|不合适)")),
    ("DEPENDS", re.compile(r"(取决于|看情况|视情况|需要看|要看你)")),
]

FAILURE_MARKERS = re.compile(
    r"(不建议|没用|不可行|风险|否则|前提|如果.*(不|没)|在.*情况下.*(不|没)|会导致|容易|失败|不稳定)",
    re.S
)

EXAMPLE_MARKERS = ["比如", "例如", "for example", "e.g."]
CONSTRAINT_MARKERS = ["必须", "只能", "仅限", "就按", "一定要", "硬性", "严格", "必须按照"]

def extract_verdict(text: str) -> str:
    # Use only first ~2 sentences to enforce "verdict first"
    head = text.strip().split("\n")[0]
    # also include second sentence if very short
    parts = re.split(r"[。！？\.\!\?]\s*", text.strip())
    head2 = " ".join(parts[:2])[:200]
    head_text = (head + " " + head2).strip()
    for label, pat in VERDICT_PATTERNS:
        if pat.search(head_text):
            return label
    return "UNKNOWN"

def has_failure_condition(text: str) -> bool:
    return bool(FAILURE_MARKERS.search(text))

def example_anchoring_rate(response: str, example_text: str) -> float:
    """
    crude: count overlap keywords from example_text that appear in response
    """
    # extract simple keywords: Chinese characters sequences / alnum tokens length>=2
    toks = re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", example_text)
    if not toks:
        return 0.0
    toks = list(dict.fromkeys(toks))  # unique preserve order
    hit = 0
    for t in toks:
        if t in response:
            hit += 1
    return hit / max(len(toks), 1)

def detects_example_as_constraint(response: str) -> bool:
    # if response uses strong constraint language frequently, might be treating example as binding
    return any(m in response for m in CONSTRAINT_MARKERS)

# ---------- Scoring ----------
def score_item(item, responses_by_id):
    qid = item["id"]
    expected = item["label"]
    variants = ["base", "example", "counter_example"]
    out = {}
    for v in variants:
        resp = responses_by_id.get((qid, v), "").strip()
        verdict = extract_verdict(resp)
        failure = has_failure_condition(resp)
        out[v] = {"response": resp, "verdict": verdict, "failure": failure}

    # 1) Verdict clarity: verdict not UNKNOWN
    verdict_clarity = sum(1 for v in variants if out[v]["verdict"] != "UNKNOWN") / 3.0

    # 2) Failure condition rate (for evaluation questions, always required here)
    failure_rate = sum(1 for v in variants if out[v]["failure"]) / 3.0

    # 3) Verdict consistency among variants
    verdicts = [out[v]["verdict"] for v in variants]
    consistency = 1.0 if (verdicts[0] == verdicts[1] == verdicts[2] and verdicts[0] != "UNKNOWN") else 0.0

    # 4) Anchoring (example vs response)
    anch_example = example_anchoring_rate(out["example"]["response"], item["example"])
    anch_counter = example_anchoring_rate(out["counter_example"]["response"], item["counter_example"])
    anch_score = 1.0 - (anch_example + anch_counter) / 2.0  # higher is better

    # 5) Expected verdict match (use base verdict only; allow DEPENDS to match if expected is DEPENDS)
    base_match = 1.0 if out["base"]["verdict"] == expected else 0.0

    # Penalty: treating examples as constraints (in example/counter_example)
    constraint_penalty = 0.0
    if detects_example_as_constraint(out["example"]["response"]):
        constraint_penalty += 0.25
    if detects_example_as_constraint(out["counter_example"]["response"]):
        constraint_penalty += 0.25

    # Total score (0..1)
    total = (
        0.30 * base_match +
        0.20 * verdict_clarity +
        0.20 * failure_rate +
        0.15 * consistency +
        0.15 * max(0.0, anch_score - constraint_penalty)
    )

    diagnostics = []
    if out["base"]["verdict"] == "UNKNOWN":
        diagnostics.append("Base未给出明确Verdict（前两句看不出来Yes/No/Depends）")
    if not out["base"]["failure"]:
        diagnostics.append("Base缺少失败条件/否定条件（容易迎合）")
    if consistency < 0.5:
        diagnostics.append("Base/Example/Counter-example结论不一致（疑似被例子绑架）")
    if anch_example > 0.55 or anch_counter > 0.55:
        diagnostics.append("例子关键词在回答中占比过高（疑似围绕例子展开过多）")
    if constraint_penalty > 0:
        diagnostics.append("回答中出现强约束语气，可能把示例当成硬约束")

    return total, out, diagnostics

def main(evalset_path="memory_retrieval_evalset.json", responses_path="responses.json"):
    with open(evalset_path, "r", encoding="utf-8") as f:
        evalset = json.load(f)
    with open(responses_path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    responses_by_id = {}
    for r in responses:
        responses_by_id[(r["id"], r["variant"])] = r["response"]

    scores = []
    per_q = []
    for item in evalset:
        s, detail, diag = score_item(item, responses_by_id)
        scores.append(s)
        per_q.append((item["id"], s, item["label"], detail["base"]["verdict"], diag))

    avg = sum(scores) / max(len(scores), 1)
    print(f"Total questions: {len(scores)}")
    print(f"Average score: {avg:.3f}")

    # Show worst 5
    per_q.sort(key=lambda x: x[1])
    print("\nWorst 5 cases:")
    for qid, s, exp, base_v, diag in per_q[:5]:
        print(f"- {qid}: score={s:.3f}, expected={exp}, base_verdict={base_v}")
        if diag:
            for d in diag[:3]:
                print(f"    * {d}")

    # Optional: dump full report
    report = []
    for qid, s, exp, base_v, diag in per_q:
        report.append({
            "id": qid,
            "score": round(s, 4),
            "expected": exp,
            "base_verdict": base_v,
            "diagnostics": diag
        })
    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nWrote report.json")

if __name__ == "__main__":
    main("q.json", "q_out.json")
