#!/usr/bin/env bash
# update_fork.sh - setup.sh 使用的安全更新助手；也兼容手动调用

set -Eeuo pipefail
umask 077

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BRANCH="main"
BRANCH_SET=false
NON_INTERACTIVE=false
PRESERVE_MISSING_CONFIG=false

usage() {
    cat <<'EOF'
用法：update_fork.sh [main] [--non-interactive] [--preserve-missing-config]

通常无需直接运行本脚本，请统一运行 setup.sh。
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --non-interactive)
            NON_INTERACTIVE=true
            ;;
        --preserve-missing-config)
            PRESERVE_MISSING_CONFIG=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo -e "${RED}❌ 未知参数：$1${NC}" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [[ $BRANCH_SET == true ]]; then
                echo -e "${RED}❌ 只能指定一个目标分支。${NC}" >&2
                exit 2
            fi
            BRANCH="$1"
            BRANCH_SET=true
            ;;
    esac
    shift
done

# 保留该变量以明确表示此模式绝不会等待用户输入。
readonly NON_INTERACTIVE

command -v git >/dev/null 2>&1 || {
    echo -e "${RED}❌ 未找到 git，请运行 setup.sh。${NC}" >&2
    exit 2
}
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo -e "${RED}❌ 当前目录不是 Git 仓库。${NC}" >&2
    exit 2
}
REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
if [[ $REPOSITORY_ROOT != "$SCRIPT_DIR" ]]; then
    echo -e "${RED}❌ setup.sh 不在当前 Git 仓库根目录，已拒绝更新。${NC}" >&2
    exit 2
fi

CONFIG_PATH="$SCRIPT_DIR/config.json"
HAD_CONFIG=false
[[ -f $CONFIG_PATH ]] && HAD_CONFIG=true
if [[ -e $CONFIG_PATH && $HAD_CONFIG != true ]]; then
    echo -e "${RED}❌ config.json 已存在但不是普通文件。${NC}" >&2
    exit 2
fi

PYTHON_PATH=""
if [[ -x $SCRIPT_DIR/.venv/bin/python ]]; then
    PYTHON_PATH="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_PATH="$(command -v python3)"
fi

# 有旧配置时必须先确认它可解析，避免 fetch 后才发现无法保留敏感字段。
if [[ $HAD_CONFIG == true ]]; then
    if [[ -z $PYTHON_PATH ]]; then
        echo -e "${YELLOW}⚠️ 已有 config.json，但尚无可用 Python；本次跳过自动更新。${NC}" >&2
        exit 12
    fi
    if ! "$PYTHON_PATH" - "$CONFIG_PATH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8-sig") as file:
    config = json.load(file)
if not isinstance(config, dict):
    raise ValueError("config.json 顶层必须是 JSON 对象")
PY
    then
        echo -e "${RED}❌ config.json 不是有效的 JSON，未执行更新。${NC}" >&2
        exit 2
    fi
fi

CURRENT_BRANCH="$(git branch --show-current)"
if [[ $CURRENT_BRANCH != "$BRANCH" ]]; then
    echo -e "${RED}❌ 当前分支是 '$CURRENT_BRANCH'，自动更新仅支持 '$BRANCH'。${NC}" >&2
    exit 2
fi

UNRELATED_CHANGES="$(git status --porcelain | grep -Ev '(^.. | -> )(config\.json|ip\.txt|ip\.local\.txt)$' || true)"
if [[ -n $UNRELATED_CHANGES ]]; then
    echo -e "${RED}❌ 检测到本机配置/结果之外的本地改动，已停止：${NC}" >&2
    printf '%s\n' "$UNRELATED_CHANGES" >&2
    echo "请先提交或暂存这些改动。" >&2
    exit 2
fi

START_HEAD="$(git rev-parse HEAD)"
echo -e "${YELLOW}检查 origin/$BRANCH 更新...${NC}"
if ! GIT_TERMINAL_PROMPT=0 git \
    -c http.lowSpeedLimit=1 -c http.lowSpeedTime=30 fetch origin "$BRANCH"; then
    echo -e "${YELLOW}⚠️ 无法连接 GitHub，尚未修改本机文件。${NC}" >&2
    exit 11
fi
REMOTE_HEAD="$(git rev-parse "origin/$BRANCH")"
if ! git merge-base --is-ancestor "$START_HEAD" "$REMOTE_HEAD"; then
    echo -e "${RED}❌ 本地与 origin/$BRANCH 已分叉，不能安全快进更新。${NC}" >&2
    exit 2
fi

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bestcfcdn-update.XXXXXX")"
CONFIG_STAGE=""
BACKUP_DIR=""
MUTATION_STARTED=false
UPDATE_SUCCEEDED=false
HAD_LOCAL_IP=false
HAD_LEGACY_IP=false
[[ -f $SCRIPT_DIR/ip.local.txt ]] && HAD_LOCAL_IP=true

restore_local_files() {
    if [[ -n $BACKUP_DIR ]]; then
        if [[ $HAD_CONFIG == true && -f $BACKUP_DIR/config.json ]]; then
            local restore_stage
            restore_stage="$(mktemp "$SCRIPT_DIR/.config.json.restore.XXXXXX")"
            if install -m 600 "$BACKUP_DIR/config.json" "$restore_stage"; then
                mv -f "$restore_stage" "$CONFIG_PATH"
            else
                rm -f "$restore_stage"
                cp -f "$BACKUP_DIR/config.json" "$CONFIG_PATH"
                chmod 600 "$CONFIG_PATH" 2>/dev/null || true
            fi
        elif [[ $HAD_CONFIG != true ]]; then
            rm -f "$CONFIG_PATH"
        fi
        if [[ $HAD_LOCAL_IP == true && -f $BACKUP_DIR/ip.local.txt ]]; then
            cp -f "$BACKUP_DIR/ip.local.txt" "$SCRIPT_DIR/ip.local.txt"
        elif [[ $HAD_LOCAL_IP != true ]]; then
            rm -f "$SCRIPT_DIR/ip.local.txt"
        fi
        if [[ $HAD_LEGACY_IP == true && -f $BACKUP_DIR/ip.legacy.txt ]]; then
            cp -f "$BACKUP_DIR/ip.legacy.txt" "$SCRIPT_DIR/ip.txt"
        fi
    elif [[ $HAD_CONFIG != true ]]; then
        rm -f "$CONFIG_PATH"
    fi
}

finish_update() {
    local status=$?
    trap - EXIT INT TERM HUP
    if [[ $status -ne 0 && $MUTATION_STARTED == true && $UPDATE_SUCCEEDED != true ]]; then
        echo -e "${RED}更新未完整完成，正在恢复本机配置与结果文件。${NC}" >&2
        restore_local_files || true
    fi
    [[ -n $CONFIG_STAGE ]] && rm -f "$CONFIG_STAGE"
    rm -rf "$TEMP_DIR"
    exit "$status"
}
trap finish_update EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

REMOTE_TEMPLATE="$TEMP_DIR/config.example.json"
if ! git show "$REMOTE_HEAD:config.example.json" > "$REMOTE_TEMPLATE"; then
    echo -e "${RED}❌ origin/$BRANCH 缺少 config.example.json，未修改工作树。${NC}" >&2
    exit 2
fi

MERGED_CONFIG="$TEMP_DIR/config.json"
CONFIG_CHANGE=false
if [[ $HAD_CONFIG == true ]]; then
    if ! "$PYTHON_PATH" - "$CONFIG_PATH" "$REMOTE_TEMPLATE" "$MERGED_CONFIG" <<'PY'
import json
import os
import sys

backup_path, template_path, output_path = sys.argv[1:]
with open(backup_path, encoding="utf-8-sig") as file:
    backup = json.load(file)
with open(template_path, encoding="utf-8-sig") as file:
    current = json.load(file)
if not isinstance(backup, dict) or not isinstance(current, dict):
    raise ValueError("配置文件顶层必须是 JSON 对象")
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
    then
        echo -e "${RED}❌ 无法将旧配置合并到最新版模板，未修改工作树。${NC}" >&2
        exit 2
    fi
    cmp -s "$CONFIG_PATH" "$MERGED_CONFIG" || CONFIG_CHANGE=true
elif [[ $PRESERVE_MISSING_CONFIG != true ]]; then
    cp "$REMOTE_TEMPLATE" "$MERGED_CONFIG"
    CONFIG_CHANGE=true
fi

if [[ -f $SCRIPT_DIR/ip.txt ]]; then
    if ! git ls-files --error-unmatch ip.txt >/dev/null 2>&1 \
        || ! git diff --quiet -- ip.txt \
        || ! git diff --cached --quiet -- ip.txt; then
        HAD_LEGACY_IP=true
    fi
fi

SOURCE_CHANGE=false
[[ $START_HEAD != "$REMOTE_HEAD" ]] && SOURCE_CHANGE=true
if [[ $SOURCE_CHANGE != true && $CONFIG_CHANGE != true && $HAD_LEGACY_IP != true ]]; then
    UPDATE_SUCCEEDED=true
    echo -e "${GREEN}✅ 已是最新版，config.json 字段也完整。${NC}"
    exit 0
fi

if [[ $HAD_CONFIG == true || $HAD_LOCAL_IP == true || $HAD_LEGACY_IP == true ]]; then
    BACKUP_DIR="$(mktemp -d "${HOME%/}/bestcfcdn_backup_$(date +%Y%m%d_%H%M%S).XXXXXX")"
    chmod 700 "$BACKUP_DIR"
    if [[ $HAD_CONFIG == true ]]; then
        cp -f "$CONFIG_PATH" "$BACKUP_DIR/config.json"
        chmod 600 "$BACKUP_DIR/config.json"
    fi
    if [[ $HAD_LOCAL_IP == true ]]; then
        cp -f "$SCRIPT_DIR/ip.local.txt" "$BACKUP_DIR/ip.local.txt"
        chmod 600 "$BACKUP_DIR/ip.local.txt" 2>/dev/null || true
    fi
    if [[ $HAD_LEGACY_IP == true ]]; then
        cp -f "$SCRIPT_DIR/ip.txt" "$BACKUP_DIR/ip.legacy.txt"
        chmod 600 "$BACKUP_DIR/ip.legacy.txt" 2>/dev/null || true
    fi
    echo -e "${YELLOW}配置备份：$BACKUP_DIR${NC}"
fi

MUTATION_STARTED=true

# 只有 fetch、配置解析和备份全部成功后，才清理会阻止快进合并的旧文件。
if [[ $SOURCE_CHANGE == true ]]; then
    if git ls-files --error-unmatch config.json >/dev/null 2>&1; then
        git restore --staged --worktree -- config.json
    fi
    if git ls-files --error-unmatch ip.txt >/dev/null 2>&1; then
        git restore --staged --worktree -- ip.txt
    elif [[ $HAD_LEGACY_IP == true ]]; then
        rm -f "$SCRIPT_DIR/ip.txt"
    fi
    git merge --ff-only "origin/$BRANCH"
elif [[ $HAD_LEGACY_IP == true ]]; then
    if git ls-files --error-unmatch ip.txt >/dev/null 2>&1; then
        git restore --staged --worktree -- ip.txt
    else
        rm -f "$SCRIPT_DIR/ip.txt"
    fi
fi

if [[ $CONFIG_CHANGE == true ]]; then
    CONFIG_STAGE="$(mktemp "$SCRIPT_DIR/.config.json.update.XXXXXX")"
    install -m 600 "$MERGED_CONFIG" "$CONFIG_STAGE"
    mv -f "$CONFIG_STAGE" "$CONFIG_PATH"
fi
if [[ $HAD_LOCAL_IP == true && -n $BACKUP_DIR ]]; then
    cp -f "$BACKUP_DIR/ip.local.txt" "$SCRIPT_DIR/ip.local.txt"
elif [[ $HAD_LEGACY_IP == true && -n $BACKUP_DIR ]]; then
    cp -f "$BACKUP_DIR/ip.legacy.txt" "$SCRIPT_DIR/ip.local.txt"
fi

UPDATE_SUCCEEDED=true
echo -e "${GREEN}✅ 更新完成，已保留本机配置与本机优选结果。${NC}"
echo "未执行 reset --hard，也未将 Token 写入 Git URL。"
if [[ -n $BACKUP_DIR ]]; then
    echo "备份目录：$BACKUP_DIR"
fi
exit 0
