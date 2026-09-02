#!/usr/bin/env bash
# 统一入口脚本：始终在仓库根目录运行，确保 node_modules / assets / .env 可被正确解析。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if command -v uv >/dev/null 2>&1; then
  exec uv run main.py "$@"
else
  exec python main.py "$@"
fi
