#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  [[ -x .venv/bin/python ]] || uv venv --python 3.12 .venv
  uv pip install --python .venv/bin/python -r requirements.txt
else
  PYTHON_BIN="${SO101_PYTHON:-python3.12}"
  [[ -x .venv/bin/python ]] || "$PYTHON_BIN" -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi
(cd frontend && npm ci)
echo 'Setup complete. Run: bash scripts/start.sh'
