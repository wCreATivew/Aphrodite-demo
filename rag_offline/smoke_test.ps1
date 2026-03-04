$ErrorActionPreference = "Stop"

py rag_offline\prepare_triplets.py `
  --input rag_offline\evalset_template.jsonl `
  --output rag_offline\triplets.jsonl
if ($LASTEXITCODE -ne 0) { throw "prepare_triplets failed" }

py rag_offline\eval_retrieval.py `
  --dataset rag_offline\evalset_template.jsonl `
  --rag-mode keyword `
  --top-k 3 `
  --out rag_offline\eval_report.keyword.json
if ($LASTEXITCODE -ne 0) { throw "eval_retrieval failed" }

py rag_offline\tune_rag_params.py `
  --dataset rag_offline\evalset_template.jsonl `
  --rag-mode keyword `
  --top-k 3 `
  --out rag_offline\tune_report.keyword.json
if ($LASTEXITCODE -ne 0) { throw "tune_rag_params failed" }

py rag_offline\export_env.py `
  --tune-report rag_offline\tune_report.keyword.json `
  --output rag_offline\best_rag.keyword.env
if ($LASTEXITCODE -ne 0) { throw "export_env failed" }

Write-Host "RAG offline smoke test complete."
