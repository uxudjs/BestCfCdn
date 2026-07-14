#!/usr/bin/env bash
# update_fork.sh - 安全更新当前仓库并保留本机配置

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
BRANCH="${1:-main}"

command -v git >/dev/null 2>&1 || { echo -e "${RED}❌ 未找到 git，请先运行 setup.sh。${NC}"; exit 1; }
if [[ -x $SCRIPT_DIR/.venv/bin/python ]]; then
    PYTHON_PATH="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON_PATH="$(command -v python3 || true)"
fi
[[ -n $PYTHON_PATH ]] || { echo -e "${RED}❌ 未找到 Python，请先运行 setup.sh。${NC}"; exit 1; }

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || { echo -e "${RED}❌ 当前目录不是 Git 仓库。${NC}"; exit 1; }
CURRENT_BRANCH="$(git branch --show-current)"
if [[ $CURRENT_BRANCH != "$BRANCH" ]]; then
    echo -e "${RED}❌ 当前分支是 '$CURRENT_BRANCH'，请先切换到 '$BRANCH'。${NC}"
    exit 1
fi

UNRELATED_CHANGES="$(git status --porcelain | grep -Ev '(^.. | -> )(config\.json|ip\.txt|ip\.local\.txt)$' || true)"
if [[ -n $UNRELATED_CHANGES ]]; then
    echo -e "${RED}❌ 检测到本机配置/结果之外的本地改动，已停止：${NC}"
    printf '%s\n' "$UNRELATED_CHANGES"
    echo "请先提交或暂存这些改动。"
    exit 1
fi

BACKUP_DIR="$HOME/bestcfcdn_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for name in config.json ip.local.txt; do
    [[ -f $name ]] && cp -f "$name" "$BACKUP_DIR/$name"
done
if [[ -f ip.txt ]]; then
    if ! git ls-files --error-unmatch ip.txt >/dev/null 2>&1 \
        || ! git diff --quiet -- ip.txt \
        || ! git diff --cached --quiet -- ip.txt; then
        cp -f ip.txt "$BACKUP_DIR/ip.legacy.txt"
    fi
fi
echo -e "${YELLOW}配置备份：$BACKUP_DIR${NC}"

restore_backup() {
    for name in config.json ip.local.txt; do
        [[ -f $BACKUP_DIR/$name ]] && cp -f "$BACKUP_DIR/$name" "$name"
    done
    [[ -f $BACKUP_DIR/ip.legacy.txt ]] && cp -f "$BACKUP_DIR/ip.legacy.txt" ip.txt
}
trap 'echo -e "${RED}更新失败，正在恢复配置备份。${NC}"; restore_backup' ERR

if git ls-files --error-unmatch config.json >/dev/null 2>&1; then
    git restore --staged --worktree -- config.json
fi
if git ls-files --error-unmatch ip.txt >/dev/null 2>&1; then
    git restore --staged --worktree -- ip.txt
else
    rm -f ip.txt
fi

echo -e "${YELLOW}拉取 origin/$BRANCH...${NC}"
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"

CONFIG_TEMPLATE="$SCRIPT_DIR/config.example.json"
[[ -f $CONFIG_TEMPLATE ]] || { echo -e "${RED}❌ 更新后缺少 config.example.json。${NC}"; exit 1; }

if [[ -f $BACKUP_DIR/config.json ]]; then
    "$PYTHON_PATH" - "$BACKUP_DIR/config.json" "$CONFIG_TEMPLATE" "$SCRIPT_DIR/config.json" <<'PY'
import json
import os
import sys

backup_path, template_path, output_path = sys.argv[1:]
with open(backup_path, encoding="utf-8-sig") as file:
    backup = json.load(file)
with open(template_path, encoding="utf-8-sig") as file:
    current = json.load(file)
legacy_remote = str(backup.get("GITHUB_SYNC_REMOTE_PATH", "ip.txt")).strip()
for key, value in backup.items():
    if key in current and not key.startswith("_comment"):
        if key == "OUTPUT_FILE" and os.path.normcase(os.path.normpath(str(value))) == \
                os.path.normcase(os.path.normpath(legacy_remote)):
            continue
        current[key] = value
with open(output_path, "w", encoding="utf-8") as file:
    json.dump(current, file, ensure_ascii=False, indent=4)
    file.write("\n")
PY
else
    cp -f "$CONFIG_TEMPLATE" "$SCRIPT_DIR/config.json"
fi
if [[ -f $BACKUP_DIR/ip.local.txt ]]; then
    cp -f "$BACKUP_DIR/ip.local.txt" ip.local.txt
elif [[ -f $BACKUP_DIR/ip.legacy.txt ]]; then
    cp -f "$BACKUP_DIR/ip.legacy.txt" ip.local.txt
fi
trap - ERR

echo -e "${GREEN}✅ 更新完成，已保留本机配置与本机优选结果。${NC}"
echo "未执行 reset --hard，也未将 Token 写入 Git URL。"
echo "备份目录：$BACKUP_DIR"
