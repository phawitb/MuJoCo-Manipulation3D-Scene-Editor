#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest backend/tests -q
(cd frontend && npm test && npm run build)
echo 'For browser tests, start the app and run: cd frontend && npm run test:e2e'
