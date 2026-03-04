from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from replay_data import enrich_sessions, filter_sessions, read_jsonl, summarize_sessions


def _cli_mode(rows: List[Dict[str, Any]], limit: int = 20) -> int:
    print("Conversation Replay (CLI)")
    print(f"Loaded sessions: {len(rows)}")
    summary = summarize_sessions(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("")
    for row in rows[: max(1, int(limit))]:
        print(f"[{row.get('_idx')}] query: {row.get('query', '')}")
        print(f"  feedback: {row.get('feedback', '')} (signal={row.get('feedback_signal', 0)})")
        print(f"  retrieval_used: {row.get('retrieval_used', False)}")
        print(f"  mode: {row.get('mode_used', '')}")
        ret = row.get("retrieved", []) or []
        for i, t in enumerate(ret[:3], start=1):
            print(f"    {i}. {str(t)[:120]}")
        if row.get("_triplet"):
            print(f"  triplet: {json.dumps(row['_triplet'], ensure_ascii=False)}")
        print("")
    return 0


def _streamlit_mode(rows: List[Dict[str, Any]]) -> int:
    try:
        import streamlit as st
    except Exception as e:  # pragma: no cover
        print("streamlit is not installed. Use --cli or install streamlit.")
        print(f"import error: {e}")
        return 1

    st.set_page_config(page_title="RAG Conversation Replay", layout="wide")
    st.title("RAG Conversation Replay")

    with st.sidebar:
        st.header("Filters")
        keyword = st.text_input("Keyword", value="")
        signal_label = st.selectbox("Feedback Signal", ["all", "positive", "neutral", "negative"], index=0)
        retrieval_label = st.selectbox("Retrieval Used", ["all", "true", "false"], index=0)

    signal = None
    if signal_label == "positive":
        signal = 1
    elif signal_label == "neutral":
        signal = 0
    elif signal_label == "negative":
        signal = -1

    retrieval_used = None
    if retrieval_label == "true":
        retrieval_used = True
    elif retrieval_label == "false":
        retrieval_used = False

    filtered = filter_sessions(rows, keyword=keyword, signal=signal, retrieval_used=retrieval_used)
    summary = summarize_sessions(filtered)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", summary["total"])
    c2.metric("Feedback +", summary["feedback_pos"])
    c3.metric("Feedback -", summary["feedback_neg"])
    c4.metric("Retrieval Used", summary["retrieval_used"])
    c5.metric("Triplets", summary["triplet_generated"])

    if not filtered:
        st.warning("No sessions matched current filters.")
        return 0

    labels = [
        f"#{r.get('_idx')} | sig={r.get('feedback_signal', 0)} | mode={r.get('mode_used', '-')}"
        for r in filtered
    ]
    selected_label = st.selectbox("Session", labels, index=len(labels) - 1)
    row = filtered[labels.index(selected_label)]

    st.subheader("Query")
    st.code(str(row.get("query", "")))

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Retrieved")
        for i, t in enumerate(row.get("retrieved", []) or [], start=1):
            st.markdown(f"{i}. {str(t)}")
    with col_b:
        st.subheader("Feedback")
        st.write(str(row.get("feedback", "")))
        st.write(f"Signal: {row.get('feedback_signal', 0)}")
        st.write(f"Retrieval used: {row.get('retrieval_used', False)}")
        st.write(f"Skip reason: {row.get('skip_reason', '') or '-'}")

    st.subheader("RAG Debug")
    st.json(
        {
            "mode_used": row.get("mode_used"),
            "queries": row.get("queries", []),
            "trace": row.get("trace", []),
        }
    )

    st.subheader("Pseudo Triplet")
    if row.get("_triplet"):
        st.json(row.get("_triplet"))
    else:
        st.info("No triplet generated for this session.")

    st.subheader("Export Selected Session")
    st.download_button(
        label="Download JSON",
        data=json.dumps(row, ensure_ascii=False, indent=2),
        file_name=f"session_{row.get('_idx')}.json",
        mime="application/json",
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", default="rag_offline/conversation_sessions.jsonl")
    ap.add_argument("--triplets", default="rag_offline/conversation_triplets.jsonl")
    ap.add_argument("--cli", action="store_true", help="run in CLI mode")
    ap.add_argument("--limit", type=int, default=20, help="CLI preview size")
    args = ap.parse_args()

    sessions = read_jsonl(args.sessions)
    triplets = read_jsonl(args.triplets)
    rows = enrich_sessions(sessions, triplets)

    if args.cli:
        return _cli_mode(rows, limit=args.limit)
    return _streamlit_mode(rows)


if __name__ == "__main__":
    raise SystemExit(main())
