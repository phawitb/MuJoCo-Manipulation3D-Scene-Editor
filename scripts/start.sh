#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d frontend/node_modules ]]; then
  echo 'Installing the project dependencies…'
  bash scripts/setup.sh
fi
# Do not stop other applications that happen to use these ports.
for port in 8765 5173; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Close the existing Scene Studio instance or free this port."
    exit 1
  fi
done
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 &
backend_pid=$!
frontend_pid=''
cleanup() {
  [[ -z "$frontend_pid" ]] || kill "$frontend_pid" 2>/dev/null || true
  kill "$backend_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM
for i in {1..50}; do
  if curl -fsS http://127.0.0.1:8765/api/health >/dev/null 2>&1; then break; fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then echo 'Simulation server failed to start.'; exit 1; fi
  sleep .1
done
(cd frontend && exec node node_modules/vite/bin/vite.js --host 127.0.0.1) &
frontend_pid=$!
echo 'Scene Studio is starting at http://127.0.0.1:5173 — press Ctrl+C to stop.'
wait "$frontend_pid"
