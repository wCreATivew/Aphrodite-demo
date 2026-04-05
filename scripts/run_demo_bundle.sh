#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/outputs/demo"
REPORT_PATH="${REPORT_DIR}/demo_report.json"

mkdir -p "${REPORT_DIR}"

python "${ROOT_DIR}/cli/run_demo_pack.py" \
  --scenario all \
  --save-report "${REPORT_PATH}"

echo "report_path=${REPORT_PATH}"
