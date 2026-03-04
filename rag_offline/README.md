# RAG Offline Pipeline

This folder provides an end-to-end offline workflow for your companion RAG:

1. Prepare labeled retrieval data
2. Train/fine-tune embedding model
3. Evaluate retrieval quality
4. Tune RAG runtime parameters
5. Export best params to `.env` snippet
6. Conversational weak-supervision training from unlabeled text/video files
7. Visual replay UI for conversation training logs

## Data Format

Use JSONL where each line is:

```json
{
  "query": "user question",
  "knowledge_base": ["doc a", "doc b", "doc c"],
  "relevant": ["doc b"],
  "meta": {"split": "train"}
}
```

Fields:
- `query` (required): retrieval query
- `knowledge_base` (required): candidate docs for this sample
- `relevant` (required): one or more relevant docs that must be in `knowledge_base`
- `meta` (optional): any additional metadata

## Commands

### 0) Conversational weak training (no labels needed)

```powershell
py rag_offline\conversation_train.py `
  --inputs .\your_texts .\your_videos `
  --rag-mode hybrid `
  --top-k 3 `
  --triplets-out rag_offline\conversation_triplets.jsonl `
  --sessions-out rag_offline\conversation_sessions.jsonl `
  --auto-train-every 20
```

Inside CLI:
- ask questions as normal dialogue turns
- optional natural-language feedback each turn
- script auto-generates pseudo triplets (`query/positive/negative`)
- can run `/train` anytime to fine-tune embedding

Commands:
- `/help`, `/add <path>`, `/stats`, `/save`, `/train`, `/exit`

For videos:
- preferred: provide sidecar transcript (`.srt/.vtt/.txt`)
- optional: `--video-transcribe` to try local `whisper` transcription

### 0.1) Replay UI for conversation logs

Streamlit mode:
```powershell
streamlit run rag_offline\replay_viewer.py -- `
  --sessions rag_offline\conversation_sessions.jsonl `
  --triplets rag_offline\conversation_triplets.jsonl
```

CLI mode:
```powershell
py rag_offline\replay_viewer.py `
  --sessions rag_offline\conversation_sessions.jsonl `
  --triplets rag_offline\conversation_triplets.jsonl `
  --cli `
  --limit 30
```

### 1) Create triplets for embedding training

```powershell
py rag_offline\prepare_triplets.py `
  --input rag_offline\evalset_template.jsonl `
  --output rag_offline\triplets.jsonl
```

### 2) Train embedding model (sentence-transformers)

```powershell
py rag_offline\train_embedding.py `
  --triplets rag_offline\triplets.jsonl `
  --base-model BAAI/bge-small-zh-v1.5 `
  --out-model monitor\rag_embed_model `
  --epochs 1 `
  --batch-size 16
```

### 3) Evaluate retrieval quality

```powershell
py rag_offline\eval_retrieval.py `
  --dataset rag_offline\evalset_template.jsonl `
  --rag-mode hybrid `
  --top-k 3 `
  --embed-model monitor\rag_embed_model
```

### 4) Tune runtime params

```powershell
py rag_offline\tune_rag_params.py `
  --dataset rag_offline\evalset_template.jsonl `
  --top-k 3 `
  --out rag_offline\tune_report.json
```

### 5) Export best params to env snippet

```powershell
py rag_offline\export_env.py `
  --tune-report rag_offline\tune_report.json `
  --output rag_offline\best_rag.env
```

Then merge `best_rag.env` into your project `.env`.

## Notes

- These scripts do not require changes to online runtime code.
- Evaluation metrics: `Recall@k`, `MRR@k`, `nDCG@k`.
- If embedding dependencies are missing, evaluate/tune with `--rag-mode keyword`.
