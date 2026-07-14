#!/bin/bash
# git_sync.sh
# 功能：调用并发安全同步程序，只更新 config.json 中本终端对应的节点。

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ 未找到 Python"
    exit 1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/github_sync.py"
