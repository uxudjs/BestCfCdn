#!/usr/bin/env bash
# setup.sh - Cloudflare IP 优选工具 Linux 一键部署脚本
# 推荐用法：chmod +x setup.sh && ./setup.sh
# 脚本仅在安装系统软件包时调用 sudo，避免生成 root 所有的项目文件。

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

TASK_INTERVAL_MINUTES=15
PYTHON_SCRIPT="scheduled_run.py"
TUNA_PYPI="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
OFFICIAL_PYPI="https://pypi.org/simple"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ${EUID} -eq 0 && -n ${SUDO_USER:-} && ${SUDO_USER} != root ]]; then
    TARGET_USER="$SUDO_USER"
else
    TARGET_USER="$(id -un)"
fi

echo -e "${CYAN}========================================"
echo -e " Cloudflare IP 优选工具 - Linux 部署"
echo -e "========================================${NC}\n"
echo -e "工作目录: $SCRIPT_DIR"
echo -e "运行用户: $TARGET_USER\n"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

run_as_target() {
    if [[ ${EUID} -eq 0 && $TARGET_USER != root ]]; then
        sudo -u "$TARGET_USER" -- "$@"
    else
        "$@"
    fi
}

if command_exists apt-get; then
    PKG_MANAGER="apt"
elif command_exists dnf; then
    PKG_MANAGER="dnf"
elif command_exists yum; then
    PKG_MANAGER="yum"
elif command_exists pacman; then
    PKG_MANAGER="pacman"
else
    PKG_MANAGER=""
fi

if [[ ${EUID} -eq 0 ]]; then
    PRIVILEGE=()
elif command_exists sudo; then
    PRIVILEGE=(sudo)
else
    PRIVILEGE=()
fi

APT_UPDATED=false
install_packages() {
    if [[ -z $PKG_MANAGER ]]; then
        echo -e "${RED}❌ 未检测到支持的包管理器，请手动安装：$*${NC}" >&2
        return 1
    fi
    if [[ ${EUID} -ne 0 && ${#PRIVILEGE[@]} -eq 0 ]]; then
        echo -e "${RED}❌ 安装 $* 需要 root 权限，但系统没有 sudo。${NC}" >&2
        return 1
    fi
    case "$PKG_MANAGER" in
        apt)
            if [[ $APT_UPDATED == false ]]; then
                "${PRIVILEGE[@]}" apt-get update
                APT_UPDATED=true
            fi
            "${PRIVILEGE[@]}" apt-get install -y "$@"
            ;;
        dnf) "${PRIVILEGE[@]}" dnf install -y "$@" ;;
        yum) "${PRIVILEGE[@]}" yum install -y "$@" ;;
        pacman) "${PRIVILEGE[@]}" pacman -Sy --needed --noconfirm "$@" ;;
    esac
}

ensure_command() {
    local command_name=$1
    shift
    if command_exists "$command_name"; then
        echo -e "✅ $command_name: $(command -v "$command_name")"
        return 0
    fi
    echo -e "${YELLOW}正在安装 $command_name...${NC}"
    install_packages "$@"
    if ! command_exists "$command_name"; then
        echo -e "${RED}❌ $command_name 安装失败。${NC}" >&2
        return 1
    fi
}

pip_install() {
    local description=$1
    shift
    local indexes=()
    if [[ -n ${PIP_INDEX_URL:-} ]]; then
        indexes+=("$PIP_INDEX_URL")
    fi
    for candidate in "$TUNA_PYPI" "$OFFICIAL_PYPI"; do
        local exists=false
        for current in "${indexes[@]:-}"; do
            [[ $current == "$candidate" ]] && exists=true
        done
        [[ $exists == false ]] && indexes+=("$candidate")
    done

    for index_url in "${indexes[@]}"; do
        echo -e "${YELLOW}  $description（源：$index_url）...${NC}"
        if run_as_target "$PYTHON_PATH" -m pip install \
            --disable-pip-version-check --timeout 120 --retries 10 \
            --index-url "$index_url" "$@"; then
            return 0
        fi
        echo -e "${YELLOW}  ⚠️ 当前源失败，尝试下一个源。${NC}"
    done
    return 1
}

append_gitignore_entry() {
    local entry=$1
    local path="$SCRIPT_DIR/.gitignore"
    run_as_target touch "$path"
    if ! grep -Fxq "$entry" "$path"; then
        printf '%s\n' "$entry" | if [[ ${EUID} -eq 0 && $TARGET_USER != root ]]; then
            sudo -u "$TARGET_USER" tee -a "$path" >/dev/null
        else
            tee -a "$path" >/dev/null
        fi
    fi
}

read_target_crontab() {
    local output
    if [[ ${EUID} -eq 0 && $TARGET_USER != root ]]; then
        if output=$(crontab -u "$TARGET_USER" -l 2>&1); then
            printf '%s' "$output"
            return 0
        fi
    else
        if output=$(crontab -l 2>&1); then
            printf '%s' "$output"
            return 0
        fi
    fi
    if grep -qiE 'no[[:space:]]+crontab' <<<"$output"; then
        return 0
    fi
    echo -e "${RED}❌ 无法读取 $TARGET_USER 的 crontab，已停止以避免覆盖其他任务：$output${NC}" >&2
    return 1
}

filter_project_crontab() {
    grep -v -F "$SCRIPT_DIR/main.py" \
        | grep -v -F "$SCRIPT_DIR/$PYTHON_SCRIPT" \
        | grep -v -F "# Cloudflare IP 优选工具" || true
}

write_target_crontab() {
    if [[ ${EUID} -eq 0 && $TARGET_USER != root ]]; then
        crontab -u "$TARGET_USER" -
    else
        crontab -
    fi
}

remove_project_cron_entries() {
    command_exists crontab || return 0
    local existing cleaned
    existing=$(read_target_crontab) || return 1
    cleaned=$(printf '%s\n' "$existing" | filter_project_crontab)
    if [[ $cleaned != "$existing" ]]; then
        printf '%s\n' "$cleaned" | write_target_crontab
    fi
}

CONFIG_PATH="$SCRIPT_DIR/config.json"
CONFIG_TEMPLATE_PATH="$SCRIPT_DIR/config.example.json"
if [[ -e $CONFIG_PATH && ! -f $CONFIG_PATH ]]; then
    echo -e "${RED}❌ config.json 已存在但不是普通文件。${NC}" >&2
    exit 1
fi
if [[ ! -f $CONFIG_PATH ]]; then
    if [[ ! -f $CONFIG_TEMPLATE_PATH ]]; then
        echo -e "${RED}❌ 未找到 config.example.json，无法创建本机配置。${NC}" >&2
        exit 1
    fi
    remove_project_cron_entries || exit 1
    append_gitignore_entry "config.json"
    run_as_target cp "$CONFIG_TEMPLATE_PATH" "$CONFIG_PATH"
    echo -e "${GREEN}✅ 已从 config.example.json 创建本机 config.json（Git 将忽略此文件）${NC}"
    echo -e "${YELLOW}首次部署到此暂停：请先编辑 config.json，再次运行 ./setup.sh 以安装依赖并应用定时设置。${NC}"
    echo -e "${YELLOW}本次不会安装依赖、注册定时任务或运行 main.py。${NC}"
    exit 0
fi

# ---------- 1. 系统依赖 ----------
echo -e "${GREEN}[1/5] 检查系统依赖...${NC}"
if ! command_exists python3; then
    install_packages python3
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo -e "${RED}❌ 需要 Python 3.9 或更高版本。${NC}" >&2
    exit 1
fi
if ! SCHEDULE_ENABLED=$(python3 -c '
import json, os, sys
path = sys.argv[1]
config = json.load(open(path, encoding="utf-8-sig")) if os.path.exists(path) else {}
value = config.get("ENABLE_SCHEDULED_TASK", True)
if not isinstance(value, bool):
    raise ValueError("ENABLE_SCHEDULED_TASK must be true or false")
print("true" if value else "false")
' "$CONFIG_PATH"); then
    echo -e "${RED}❌ 无法读取 config.json 中的 ENABLE_SCHEDULED_TASK。${NC}" >&2
    exit 1
fi
ensure_command git git
ensure_command curl curl

if [[ $SCHEDULE_ENABLED == true ]]; then
    if ! command_exists crontab; then
        case "$PKG_MANAGER" in
            apt) install_packages cron ;;
            dnf|yum|pacman) install_packages cronie ;;
            *) echo -e "${RED}❌ 请手动安装 cron/cronie。${NC}"; exit 1 ;;
        esac
    fi
    if ! command_exists crontab; then
        echo -e "${RED}❌ crontab 安装失败。${NC}" >&2
        exit 1
    fi
fi

# ---------- 2. 项目虚拟环境 ----------
echo -e "${GREEN}[2/5] 检查项目虚拟环境...${NC}"
PYTHON_PATH="$SCRIPT_DIR/.venv/bin/python"
if [[ ! -x $PYTHON_PATH ]]; then
    echo -e "${YELLOW}创建项目虚拟环境 .venv...${NC}"
    if ! run_as_target python3 -m venv "$SCRIPT_DIR/.venv"; then
        echo -e "${YELLOW}首次创建失败，尝试安装 venv 支持...${NC}"
        case "$PKG_MANAGER" in
            apt) install_packages python3-venv ;;
            dnf|yum|pacman) install_packages python3 ;;
        esac
        run_as_target python3 -m venv "$SCRIPT_DIR/.venv"
    fi
fi
if [[ ! -x $PYTHON_PATH ]]; then
    echo -e "${RED}❌ .venv 创建失败。${NC}" >&2
    exit 1
fi
echo -e "✅ 项目 Python: $PYTHON_PATH"

# ---------- 3. Python 依赖 ----------
echo -e "${GREEN}[3/5] 安装并验证 Python 依赖...${NC}"
if ! run_as_target "$PYTHON_PATH" -m pip --version >/dev/null 2>&1; then
    run_as_target "$PYTHON_PATH" -m ensurepip --upgrade
fi
if ! pip_install "安装核心依赖" -r "$SCRIPT_DIR/requirements.txt"; then
    echo -e "${RED}❌ requests 与 aiohttp 安装失败，请检查网络或代理。${NC}" >&2
    exit 1
fi

if ! run_as_target "$PYTHON_PATH" -c \
    "import importlib.util as u; raise SystemExit(0 if u.find_spec('brotlicffi') or u.find_spec('brotli') else 1)"; then
    if ! pip_install "安装 brotlicffi" brotlicffi; then
        pip_install "安装 brotli 备用实现" brotli || {
            echo -e "${RED}❌ Brotli 解压依赖安装失败。${NC}" >&2
            exit 1
        }
    fi
fi

run_as_target "$PYTHON_PATH" -c \
    "import requests, aiohttp, importlib.util as u; assert u.find_spec('brotlicffi') or u.find_spec('brotli'); print('依赖导入验证通过')"
echo -e "${GREEN}✅ Python 依赖安装并验证完成${NC}"

# ---------- 4. 文件检查与 .gitignore ----------
echo -e "${GREEN}[4/5] 检查运行文件与 .gitignore...${NC}"
if [[ ! -f $PYTHON_SCRIPT || ! -f main.py || ! -f proxy_scoring.py || ! -f requirements.txt ]]; then
    echo -e "${RED}❌ 缺少 scheduled_run.py、main.py、proxy_scoring.py 或 requirements.txt。${NC}" >&2
    exit 1
fi
for entry in ".venv/" "__pycache__/" "*.py[cod]" ".cfnb_schedule.lock" "cron.log" \
    "config.json" "ip.local.txt" "valid_tokens.txt" "ipinfo_cache.txt" "cfnb.log"; do
    append_gitignore_entry "$entry"
done
echo -e "✅ 已保留原有 .gitignore，并补齐运行时条目"

# ---------- 5. 按配置创建或清理 cron 计划任务 ----------
escaped_dir=${SCRIPT_DIR//\"/\\\"}
CRON_COMMENT="# Cloudflare IP 优选工具（中国CF CDN忙时15分钟/非忙时30分钟）"
CRON_CMD="*/15 * * * * cd \"$escaped_dir\" && \"$PYTHON_PATH\" \"$escaped_dir/$PYTHON_SCRIPT\" >> \"$escaped_dir/cron.log\" 2>&1"

EXISTING_CRONTAB=""
CLEANED_CRONTAB=""
if command_exists crontab; then
    EXISTING_CRONTAB=$(read_target_crontab) || exit 1
    CLEANED_CRONTAB=$(printf '%s\n' "$EXISTING_CRONTAB" | filter_project_crontab)
fi

if [[ $SCHEDULE_ENABLED == true ]]; then
    echo -e "${GREEN}[5/5] 配置定时任务（每15分钟检查峰谷策略）...${NC}"
    (printf '%s\n' "$CLEANED_CRONTAB"; echo "$CRON_COMMENT"; echo "$CRON_CMD") \
        | write_target_crontab
    echo -e "${GREEN}✅ 已为 $TARGET_USER 更新 cron 任务${NC}"
    echo -e "   Python: $PYTHON_PATH"
    echo -e "   日志: $SCRIPT_DIR/cron.log"
else
    echo -e "${GREEN}[5/5] 自动定时优选已关闭，正在清理本项目旧 cron 任务...${NC}"
    if command_exists crontab && [[ $CLEANED_CRONTAB != "$EXISTING_CRONTAB" ]]; then
        printf '%s\n' "$CLEANED_CRONTAB" | write_target_crontab
    fi
    echo -e "${GREEN}✅ 已确认本项目 cron 任务不存在；需要时请手动运行 main.py${NC}"
fi

# 尝试启动 cron 服务；WSL、容器或非 systemd 环境失败时只提示。
if [[ $SCHEDULE_ENABLED == true ]] && command_exists systemctl \
    && [[ ${EUID} -eq 0 || ${#PRIVILEGE[@]} -gt 0 ]]; then
    cron_service=""
    systemctl list-unit-files cron.service >/dev/null 2>&1 && cron_service="cron"
    [[ -z $cron_service ]] && systemctl list-unit-files crond.service >/dev/null 2>&1 && cron_service="crond"
    if [[ -n $cron_service ]]; then
        "${PRIVILEGE[@]}" systemctl enable --now "$cron_service" >/dev/null 2>&1 \
            || echo -e "${YELLOW}⚠️ 无法自动启动 $cron_service，请确认 cron 服务正在运行。${NC}"
    fi
fi

chmod +x setup.sh git_sync.sh 2>/dev/null || true

echo -e "\n${CYAN}========================================"
echo -e " 🎉 部署完成！"
echo -e "========================================${NC}"
echo -e "1. 在 config.json 填写 GitHub 同步信息和本终端唯一名称"
echo -e "2. 微信推送默认关闭，需要时再启用"
echo -e "3. 手动测试: ${CYAN}$PYTHON_PATH main.py${NC}"
if [[ $SCHEDULE_ENABLED == true ]]; then
    echo -e "4. 查看日志: ${CYAN}tail -f cron.log${NC}\n"
else
    echo -e "4. 当前为手动模式，不会自动执行。${NC}\n"
fi

reply=""
if [[ -t 0 ]]; then
    read -r -p "是否立即运行一次 main.py 进行测试？(y/N) " reply || true
fi
if [[ $reply =~ ^[Yy]$ ]]; then
    run_as_target "$PYTHON_PATH" "$SCRIPT_DIR/main.py" \
        || echo -e "${YELLOW}⚠️ main.py 测试失败，请根据日志检查配置。${NC}"
fi
