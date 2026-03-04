from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List

from common import load_companion_rag_module, read_jsonl, write_jsonl
from conversation_utils import infer_feedback_signal, pick_pseudo_triplet
from unlabeled_ingest import DocChunk, ingest_paths


def _load_triplets(path: str) -> List[Dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    rows = read_jsonl(str(p))
    out: List[Dict[str, str]] = []
    for r in rows:
        q = str(r.get("query", "")).strip()
        pos = str(r.get("positive", "")).strip()
        neg = str(r.get("negative", "")).strip()
        if q and pos and neg:
            out.append({"query": q, "positive": pos, "negative": neg})
    return out


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _train_embedding_if_requested(
    *,
    triplets_path: str,
    base_model: str,
    out_model: str,
    epochs: int,
    batch_size: int,
    lr: float,
) -> None:
    from train_embedding import train_triplet_model

    rows = _load_triplets(triplets_path)
    if not rows:
        print("[train] no triplets available")
        return
    train_triplet_model(
        triplets=rows,
        base_model=base_model,
        out_model=out_model,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
    )
    print(f"[train] saved model -> {out_model}")


def _print_help() -> None:
    print("Commands:")
    print("  /help                         show help")
    print("  /add <path>                   ingest more files/dirs")
    print("  /stats                        show corpus/triplet stats")
    print("  /save                         save current corpus snapshot")
    print("  /train                        run embedding training now")
    print("  /exit                         quit")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", required=True, help="unlabeled text/video paths")
    ap.add_argument("--rag-mode", default=os.getenv("RAG_MODE") or "hybrid")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--triplets-out", default="rag_offline/conversation_triplets.jsonl")
    ap.add_argument("--sessions-out", default="rag_offline/conversation_sessions.jsonl")
    ap.add_argument("--corpus-out", default="rag_offline/conversation_corpus.json")
    ap.add_argument("--auto-train-every", type=int, default=0, help="train every N new triplets; 0 to disable")
    ap.add_argument("--base-model", default="BAAI/bge-small-zh-v1.5")
    ap.add_argument("--out-model", default="monitor/rag_embed_model_conversation")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--video-transcribe", action="store_true", help="enable local whisper transcription for videos")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    rag_mod = load_companion_rag_module(repo_root)
    cfg = rag_mod.load_rag_config()
    cfg.mode = str(args.rag_mode).strip().lower()

    chunks = ingest_paths(
        args.inputs,
        chunk_size=420,
        chunk_overlap=80,
        enable_video_transcribe=bool(args.video_transcribe),
    )
    if not chunks:
        print("No usable text/video content found.")
        return 1

    corpus_docs = [c.text for c in chunks]
    corpus_meta = [{"chunk_id": c.chunk_id, "source": c.source, "text": c.text} for c in chunks]
    Path(args.corpus_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.corpus_out, "w", encoding="utf-8") as f:
        json.dump(corpus_meta, f, ensure_ascii=False, indent=2)

    print(f"Loaded corpus chunks: {len(corpus_docs)}")
    print(f"RAG mode: {cfg.mode}; top_k={args.top_k}")
    _print_help()

    rng = random.Random(7)
    triplets = _load_triplets(args.triplets_out)
    new_triplet_count = 0

    while True:
        user_text = input("\nYou> ").strip()
        if not user_text:
            continue
        if user_text.startswith("/"):
            cmd = user_text.split(" ", 1)[0].strip().lower()
            if cmd == "/exit":
                print("Bye.")
                break
            if cmd == "/help":
                _print_help()
                continue
            if cmd == "/stats":
                print(f"Corpus chunks: {len(corpus_docs)}")
                print(f"Triplets: {len(triplets)}")
                continue
            if cmd == "/save":
                with open(args.corpus_out, "w", encoding="utf-8") as f:
                    json.dump(corpus_meta, f, ensure_ascii=False, indent=2)
                write_jsonl(args.triplets_out, triplets)
                print(f"Saved corpus -> {args.corpus_out}")
                print(f"Saved triplets -> {args.triplets_out}")
                continue
            if cmd == "/train":
                write_jsonl(args.triplets_out, triplets)
                _train_embedding_if_requested(
                    triplets_path=args.triplets_out,
                    base_model=args.base_model,
                    out_model=args.out_model,
                    epochs=args.epochs,
                    batch_size=args.batch_size,
                    lr=args.lr,
                )
                continue
            if cmd == "/add":
                extra = user_text.split(" ", 1)[1].strip() if " " in user_text else ""
                if not extra:
                    print("Usage: /add <path>")
                    continue
                new_chunks = ingest_paths(
                    [extra],
                    chunk_size=420,
                    chunk_overlap=80,
                    enable_video_transcribe=bool(args.video_transcribe),
                )
                if not new_chunks:
                    print("No usable content found in path.")
                    continue
                corpus_docs.extend([x.text for x in new_chunks])
                corpus_meta.extend(
                    [{"chunk_id": c.chunk_id, "source": c.source, "text": c.text} for c in new_chunks]
                )
                print(f"Added chunks: {len(new_chunks)}; total: {len(corpus_docs)}")
                continue
            print("Unknown command. Type /help")
            continue

        result = rag_mod.build_rag_package(
            user_text=user_text,
            knowledge_base=corpus_docs,
            top_k=max(1, int(args.top_k)),
            rag_mode=cfg.mode,
            config=cfg,
        )
        retrieved = list(result.items)
        print("\nRetrieved context:")
        if not retrieved:
            print("- (none)")
        else:
            for i, t in enumerate(retrieved, start=1):
                print(f"{i}. {t[:180]}")

        feedback_text = input("Feedback (natural language, optional)> ").strip()
        signal = infer_feedback_signal(feedback_text)
        triplet = pick_pseudo_triplet(
            query=user_text,
            retrieved_docs=retrieved,
            corpus_docs=corpus_docs,
            feedback_signal=signal,
            rng=rng,
        )
        session_row = {
            "query": user_text,
            "retrieved": retrieved,
            "feedback": feedback_text,
            "feedback_signal": signal,
            "triplet_generated": bool(triplet),
            "trace": result.trace,
            "queries": result.queries,
            "mode_used": result.mode_used,
            "retrieval_used": result.retrieval_used,
            "skip_reason": result.skip_reason,
        }
        _append_jsonl(args.sessions_out, session_row)

        if triplet:
            triplets.append(triplet)
            _append_jsonl(args.triplets_out, triplet)
            new_triplet_count += 1
            print("Triplet added.")
        else:
            print("No triplet generated this turn.")

        if int(args.auto_train_every) > 0 and new_triplet_count >= int(args.auto_train_every):
            print(f"[auto-train] triggering after {new_triplet_count} new triplets...")
            write_jsonl(args.triplets_out, triplets)
            _train_embedding_if_requested(
                triplets_path=args.triplets_out,
                base_model=args.base_model,
                out_model=args.out_model,
                epochs=args.epochs,
                batch_size=args.batch_size,
                lr=args.lr,
            )
            new_triplet_count = 0

    write_jsonl(args.triplets_out, triplets)
    with open(args.corpus_out, "w", encoding="utf-8") as f:
        json.dump(corpus_meta, f, ensure_ascii=False, indent=2)
    print(f"Saved triplets -> {args.triplets_out}")
    print(f"Saved sessions -> {args.sessions_out}")
    print(f"Saved corpus -> {args.corpus_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
