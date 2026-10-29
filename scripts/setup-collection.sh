#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  [[ -x .venv-collect/bin/python ]] || uv venv --python 3.12 .venv-collect
  uv pip install --python .venv-collect/bin/python -r requirements-collection.txt
else
  "${SO101_PYTHON:-python3.12}" -m venv .venv-collect
  .venv-collect/bin/python -m pip install -r requirements-collection.txt
fi
.venv-collect/bin/python -c 'from lerobot.datasets.lerobot_dataset import LeRobotDataset; import mujoco, av; print("LeRobot collection runtime ready")'
