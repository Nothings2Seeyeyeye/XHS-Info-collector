#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
if [ ! -f frontend/dist/index.html ]; then
  echo '首次使用请先执行：uv sync --group dev，然后 cd frontend && npm install && npm run build'
  exit 1
fi
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python -m spider_xhs.web.serve "$@"
else
  exec uv run python -m spider_xhs.web.serve "$@"
fi
