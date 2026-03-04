from __future__ import annotations

import argparse
from typing import Any, Dict, List

from common import read_jsonl


def train_triplet_model(
    triplets: List[Dict[str, Any]],
    base_model: str,
    out_model: str,
    epochs: int,
    batch_size: int,
    lr: float,
) -> None:
    from sentence_transformers import InputExample, SentenceTransformer, losses
    from torch.utils.data import DataLoader

    examples = []
    for t in triplets:
        q = str(t.get("query", "")).strip()
        p = str(t.get("positive", "")).strip()
        n = str(t.get("negative", "")).strip()
        if not q or not p or not n:
            continue
        examples.append(InputExample(texts=[q, p, n]))

    if not examples:
        raise RuntimeError("No valid triplets found.")

    model = SentenceTransformer(base_model)
    loader = DataLoader(examples, batch_size=max(1, int(batch_size)), shuffle=True)
    train_loss = losses.TripletLoss(model=model)
    warmup_steps = max(1, int(len(loader) * int(epochs) * 0.1))
    model.fit(
        train_objectives=[(loader, train_loss)],
        epochs=max(1, int(epochs)),
        warmup_steps=warmup_steps,
        optimizer_params={"lr": float(lr)},
        show_progress_bar=True,
    )
    model.save(out_model)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--triplets", required=True, help="triplets jsonl from prepare_triplets.py")
    ap.add_argument("--base-model", default="BAAI/bge-small-zh-v1.5")
    ap.add_argument("--out-model", required=True, help="output model dir")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    args = ap.parse_args()

    triplets = read_jsonl(args.triplets)
    train_triplet_model(
        triplets=triplets,
        base_model=args.base_model,
        out_model=args.out_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
    )
    print(f"saved model -> {args.out_model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
