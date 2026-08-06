#!/usr/bin/env bash
# setup.sh - Cloudflare IP 优选工具 Linux 一键部署脚本
# 推荐用法：bash setup.sh（安装、更新、配置均使用此入口）
# 脚本仅在安装系统软件包时调用 sudo，避免生成 root 所有的项目文件。

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

TASK_INTERVAL_MINUTES=30
PYTHON_MODULE="core.scheduled_run"
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

find_bootstrap_python() {
    local candidate python_dir environment_root
    while IFS= read -r candidate; do
        [[ -n $candidate && -x $candidate ]] || continue
        python_dir=$(dirname "$candidate")
        environment_root=$(dirname "$python_dir")
        [[ -f $environment_root/pyvenv.cfg ]] && continue
        printf '%s\n' "$candidate"
        return 0
    done < <(type -aP python3 2>/dev/null | awk '!seen[$0]++')
    return 1
}

run_as_target() {
    if [[ ${EUID} -eq 0 && $TARGET_USER != root ]]; then
        sudo -H -u "$TARGET_USER" -- "$@"
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

validate_project_venv() {
    [[ -d $VENV_DIR && ! -L $VENV_DIR && -x $PYTHON_PATH ]] || return 1
    run_as_target "$PYTHON_PATH" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1 || return 1
    run_as_target "$PYTHON_PATH" -m pip --version >/dev/null 2>&1 || return 1
    run_as_target "$PYTHON_PATH" -c "import requests, aiohttp, importlib.util as u; assert u.find_spec('brotlicffi') or u.find_spec('brotli')" >/dev/null 2>&1
}

restore_project_venv() {
    if [[ -n ${VENV_BACKUP:-} ]] &&
        [[ ! -d $VENV_BACKUP || -L $VENV_BACKUP || $VENV_BACKUP != "$SCRIPT_DIR"/.venv.repair-* ]]; then
        echo -e "${RED}❌ .venv 修复备份路径不安全，拒绝恢复。${NC}" >&2
        return 1
    fi
    if [[ -e $VENV_DIR ]]; then
        if [[ ! -d $VENV_DIR || -L $VENV_DIR || $VENV_DIR != "$SCRIPT_DIR/.venv" ]]; then
            echo -e "${RED}❌ 新 .venv 不是可安全移除的项目内真实目录，拒绝自动恢复。${NC}" >&2
            return 1
        fi
        run_as_target rm -rf -- "$VENV_DIR"
    fi
    [[ -n ${VENV_BACKUP:-} ]] || return 0
    run_as_target mv "$VENV_BACKUP" "$VENV_DIR"
    VENV_BACKUP=""
}

discard_project_venv_backup() {
    [[ -n ${VENV_BACKUP:-} ]] || return 0
    if [[ ! -d $VENV_BACKUP || -L $VENV_BACKUP || $VENV_BACKUP != "$SCRIPT_DIR"/.venv.repair-* ]]; then
        echo -e "${RED}❌ .venv 修复备份路径不安全，拒绝删除。${NC}" >&2
        return 1
    fi
    run_as_target rm -rf -- "$VENV_BACKUP"
    VENV_BACKUP=""
}

fail_project_venv_repair() {
    local message=$1
    local had_backup=false
    [[ -n ${VENV_BACKUP:-} ]] && had_backup=true
    if ! restore_project_venv; then
        echo -e "${RED}❌ $message，且旧 .venv 自动恢复失败。${NC}" >&2
    elif [[ $had_backup == true ]]; then
        echo -e "${RED}❌ $message；旧 .venv 已恢复。${NC}" >&2
    else
        echo -e "${RED}❌ $message；失败的新 .venv 已移除。${NC}" >&2
    fi
    exit 1
}

append_gitignore_entry() {
    local entry=$1
    local path="$SCRIPT_DIR/.gitignore"
    local git_root="" git_exclude=""
    if command_exists git; then
        git_root=$(run_as_target git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)
        if [[ $git_root == "$SCRIPT_DIR" ]]; then
            git_exclude=$(run_as_target git -C "$SCRIPT_DIR" rev-parse --git-path info/exclude 2>/dev/null || true)
            if [[ -n $git_exclude ]]; then
                [[ $git_exclude == /* ]] || git_exclude="$SCRIPT_DIR/$git_exclude"
                path=$git_exclude
            fi
        fi
    fi
    run_as_target mkdir -p "$(dirname "$path")"
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
    awk -v dir="$SCRIPT_DIR" '
        function is_project_command(line) {
            return index(line, dir "/main.py") \
                || index(line, dir "/scheduled_run.py") \
                || (index(line, dir) && index(line, "-m core.scheduled_run"))
        }
        {
            if (pending_comment != "") {
                if (is_project_command($0)) {
                    pending_comment = ""
                    next
                }
                print pending_comment
                pending_comment = ""
            }
            if (index($0, "# Cloudflare IP 优选工具") == 1) {
                pending_comment = $0
                next
            }
            if (!is_project_command($0)) { print }
        }
        END { if (pending_comment != "") print pending_comment }
    ' || true
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
CONFIG_TEMPLATE_PATH="$SCRIPT_DIR/config/config.example.json"
CONFIG_EXISTED_AT_START=false
[[ -f $CONFIG_PATH ]] && CONFIG_EXISTED_AT_START=true

# setup.sh 是用户唯一入口：在读取/生成配置前先尝试安全快进更新。
# 更新若替换了 setup.sh 自身，则只重新加载一次新版脚本，避免新旧逻辑混用。
SETUP_REEXEC_DEPTH="${BESTCFCDN_SETUP_REEXEC_DEPTH:-0}"
SETUP_RETRY_AUTO_UPDATE="${BESTCFCDN_SETUP_RETRY_AUTO_UPDATE:-0}"
[[ $SETUP_REEXEC_DEPTH =~ ^[0-9]+$ ]] || SETUP_REEXEC_DEPTH=0
if [[ $SETUP_REEXEC_DEPTH == 0 || $SETUP_RETRY_AUTO_UPDATE == 1 ]]; then
    UPDATE_HELPER="$SCRIPT_DIR/scripts/update_fork.sh"
    PROJECT_GIT_PREFIX=""
    IS_PROJECT_GIT_ROOT=false
    if command_exists git && [[ -f $UPDATE_HELPER ]]; then
        if PROJECT_GIT_PREFIX="$(
            run_as_target git -C "$SCRIPT_DIR" rev-parse --show-prefix 2>/dev/null
        )"; then
            [[ -z $PROJECT_GIT_PREFIX ]] && IS_PROJECT_GIT_ROOT=true
        fi
    fi
    if [[ $IS_PROJECT_GIT_ROOT == true ]]; then
        CAN_AUTO_UPDATE=true
        if [[ $CONFIG_EXISTED_AT_START == true \
            && ! -x $SCRIPT_DIR/.venv/bin/python ]] \
            && ! command_exists python3; then
            CAN_AUTO_UPDATE=false
            echo -e "${YELLOW}⚠️ 已有 config.json，但尚无 Python；本次先使用当前版本完成部署，下次运行 setup.sh 时再自动更新。${NC}"
        fi

        if [[ $CAN_AUTO_UPDATE == true ]]; then
            BEFORE_UPDATE_HEAD="$(run_as_target git -C "$SCRIPT_DIR" rev-parse HEAD)"
            UPDATE_STATUS=0
            if run_as_target bash "$UPDATE_HELPER" \
                --non-interactive --preserve-missing-config; then
                UPDATE_STATUS=0
            else
                UPDATE_STATUS=$?
            fi
            AFTER_UPDATE_HEAD="$(run_as_target git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || true)"

            if [[ -n $AFTER_UPDATE_HEAD && $AFTER_UPDATE_HEAD != "$BEFORE_UPDATE_HEAD" ]]; then
                NEXT_REEXEC_DEPTH=$((SETUP_REEXEC_DEPTH + 1))
                if (( NEXT_REEXEC_DEPTH > 2 )); then
                    echo -e "${RED}❌ 自动更新连续改变代码但未能稳定完成，已停止；本机配置仍由备份保护。${NC}" >&2
                    exit 2
                fi
                if [[ $UPDATE_STATUS -ne 0 ]]; then
                    echo -e "${YELLOW}⚠️ 更新已推进到新版，但后续步骤未完整完成；将由新版 setup.sh 接管并复核。${NC}"
                    exec env BESTCFCDN_SETUP_REEXEC_DEPTH="$NEXT_REEXEC_DEPTH" \
                        BESTCFCDN_SETUP_RETRY_AUTO_UPDATE=1 bash "$SCRIPT_DIR/setup.sh" "$@"
                else
                    echo -e "${GREEN}✅ 已获取新版，正在重新加载最新 setup.sh...${NC}"
                    exec env BESTCFCDN_SETUP_REEXEC_DEPTH="$NEXT_REEXEC_DEPTH" \
                        BESTCFCDN_SETUP_RETRY_AUTO_UPDATE=0 bash "$SCRIPT_DIR/setup.sh" "$@"
                fi
            fi

            case "$UPDATE_STATUS" in
                0) ;;
                11)
                    echo -e "${YELLOW}⚠️ GitHub 暂时不可达，继续使用当前本地版本部署。${NC}"
                    ;;
                12)
                    echo -e "${YELLOW}⚠️ 当前缺少用于合并旧配置的 Python，继续使用当前本地版本部署。${NC}"
                    ;;
                *)
                    echo -e "${RED}❌ 自动更新未通过安全检查，setup 已停止，且没有覆盖本机配置。${NC}" >&2
                    exit "$UPDATE_STATUS"
                    ;;
            esac
        fi
    else
        echo -e "${YELLOW}ℹ️ 当前不是可更新的 Git 仓库（例如 ZIP 安装），跳过在线更新。${NC}"
    fi
else
    echo -e "${GREEN}✅ 已切换到本次获取的最新版 setup.sh${NC}"
fi

if [[ -e $CONFIG_PATH && ! -f $CONFIG_PATH ]]; then
    echo -e "${RED}❌ config.json 已存在但不是普通文件。${NC}" >&2
    exit 1
fi
if [[ -f $CONFIG_PATH ]]; then
    run_as_target chmod 600 "$CONFIG_PATH"
fi
if [[ $CONFIG_EXISTED_AT_START != true ]]; then
    if [[ ! -f $CONFIG_TEMPLATE_PATH ]]; then
        echo -e "${RED}❌ 未找到 config.example.json，无法创建本机配置。${NC}" >&2
        exit 1
    fi
    remove_project_cron_entries || exit 1
    append_gitignore_entry "config.json"
    if [[ ! -f $CONFIG_PATH ]]; then
        run_as_target cp "$CONFIG_TEMPLATE_PATH" "$CONFIG_PATH"
    fi
    run_as_target chmod 600 "$CONFIG_PATH"
    echo -e "${GREEN}✅ 已从 config.example.json 创建本机 config.json（Git 将忽略此文件）${NC}"
    echo -e "${YELLOW}首次部署到此暂停：请先编辑 config.json，再次运行 ./setup.sh 以安装依赖并应用定时设置。${NC}"
    echo -e "${YELLOW}本次不会安装依赖、注册定时任务或运行 main.py。${NC}"
    exit 0
fi
if [[ ! -f $CONFIG_PATH ]]; then
    echo -e "${RED}❌ 更新后未能恢复已有的 config.json，已停止部署。${NC}" >&2
    exit 1
fi
remove_project_cron_entries || exit 1

# ---------- 1. 系统依赖 ----------
echo -e "${GREEN}[1/5] 检查系统依赖...${NC}"
if ! BOOTSTRAP_PYTHON=$(find_bootstrap_python); then
    install_packages python3
    hash -r
    if ! BOOTSTRAP_PYTHON=$(find_bootstrap_python); then
        echo -e "${RED}❌ 安装后仍未找到虚拟环境之外的 Python 3。${NC}" >&2
        exit 1
    fi
fi
if ! "$BOOTSTRAP_PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo -e "${RED}❌ 需要 Python 3.9 或更高版本。${NC}" >&2
    exit 1
fi
if ! SCHEDULE_ENABLED=$("$BOOTSTRAP_PYTHON" -c '
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
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_PATH="$VENV_DIR/bin/python"
VENV_BACKUP=""
VENV_NEEDS_REPAIR=false
if [[ -L $VENV_DIR ]]; then
    echo -e "${RED}❌ .venv 是符号链接，拒绝修改。${NC}" >&2
    exit 1
fi
if [[ -e $VENV_DIR && ! -d $VENV_DIR ]]; then
    echo -e "${RED}❌ .venv 已存在但不是真实目录，拒绝修改。${NC}" >&2
    exit 1
fi
if ! validate_project_venv; then
    VENV_NEEDS_REPAIR=true
    if [[ -d $VENV_DIR ]]; then
        VENV_BACKUP="$SCRIPT_DIR/.venv.repair-$$"
        [[ ! -e $VENV_BACKUP ]] || {
            echo -e "${RED}❌ .venv 修复备份路径已存在，拒绝覆盖。${NC}" >&2
            exit 1
        }
        run_as_target mv "$VENV_DIR" "$VENV_BACKUP"
    fi
    echo -e "${YELLOW}创建或修复项目虚拟环境 .venv...${NC}"
    if ! run_as_target "$BOOTSTRAP_PYTHON" -m venv "$SCRIPT_DIR/.venv"; then
        echo -e "${YELLOW}首次创建失败，尝试安装 venv 支持...${NC}"
        case "$PKG_MANAGER" in
            apt) install_packages python3-venv ;;
            dnf|yum|pacman) install_packages python3 ;;
        esac
        run_as_target "$BOOTSTRAP_PYTHON" -m venv "$SCRIPT_DIR/.venv" || fail_project_venv_repair ".venv 创建失败"
    fi
fi
if [[ ! -x $PYTHON_PATH ]]; then
    fail_project_venv_repair ".venv 创建后缺少项目解释器"
fi
echo -e "✅ 项目 Python: $PYTHON_PATH"

# ---------- 3. Python 依赖 ----------
echo -e "${GREEN}[3/5] 安装并验证 Python 依赖...${NC}"
if [[ $VENV_NEEDS_REPAIR == true ]]; then
    if ! run_as_target "$PYTHON_PATH" -m pip --version >/dev/null 2>&1; then
        run_as_target "$PYTHON_PATH" -m ensurepip --upgrade || fail_project_venv_repair "pip 修复失败"
    fi
    if ! pip_install "安装核心依赖" -r "$SCRIPT_DIR/requirements.txt"; then
        fail_project_venv_repair "requests 与 aiohttp 安装失败，请检查网络或代理"
    fi

    if ! run_as_target "$PYTHON_PATH" -c "import importlib.util as u; raise SystemExit(0 if u.find_spec('brotlicffi') or u.find_spec('brotli') else 1)"; then
        if ! pip_install "安装 brotlicffi" brotlicffi; then
            pip_install "安装 brotli 备用实现" brotli || fail_project_venv_repair "Brotli 解压依赖安装失败"
        fi
    fi

    if ! validate_project_venv; then
        fail_project_venv_repair "Python 依赖已安装但无法导入"
    fi
    discard_project_venv_backup || exit 1
fi
echo -e "${GREEN}✅ Python 依赖安装并验证完成${NC}"
# ---------- 4. 文件检查与 .gitignore ----------
echo -e "${GREEN}[4/5] 检查运行文件与 .gitignore...${NC}"
if [[ ! -f core/scheduled_run.py || ! -f main.py || ! -f core/proxy_scoring.py || ! -f requirements.txt ]]; then
    echo -e "${RED}❌ 缺少调度模块、main.py、core/proxy_scoring.py 或 requirements.txt。${NC}" >&2
    exit 1
fi
for entry in ".venv/" "__pycache__/" "*.py[cod]" ".cfnb_schedule.lock" "cron.log" \
    "config.json" "ip.local.txt" "valid_tokens.txt" "ipinfo_cache.txt" "cfnb.log"; do
    append_gitignore_entry "$entry"
done
echo -e "✅ 已保留原有 .gitignore，并补齐运行时条目"

# ---------- 5. 链式预检与 cron 门 ----------
escaped_dir=${SCRIPT_DIR//\"/\\\"}
CRON_COMMENT="# Cloudflare IP 优选工具（中国CF CDN忙时90分钟/非忙时180分钟）"
CRON_CMD="*/30 * * * * cd \"$escaped_dir\" && \"$PYTHON_PATH\" -m $PYTHON_MODULE >> \"$escaped_dir/cron.log\" 2>&1"

EXISTING_CRONTAB=""
CLEANED_CRONTAB=""
if command_exists crontab; then
    EXISTING_CRONTAB=$(read_target_crontab) || exit 1
    CLEANED_CRONTAB=$(printf '%s\n' "$EXISTING_CRONTAB" | filter_project_crontab)
    if [[ $CLEANED_CRONTAB != "$EXISTING_CRONTAB" ]]; then
        printf '%s\n' "$CLEANED_CRONTAB" | write_target_crontab
    fi
fi

echo -e "${GREEN}[5/5] 运行共享链式预检...${NC}"
if ! run_as_target "$PYTHON_PATH" -m core.chain_proxy preflight --config "$CONFIG_PATH"; then
    echo -e "${RED}❌ 链式预检失败；本项目 cron 保持移除状态。${NC}" >&2
    exit 1
fi

if [[ $SCHEDULE_ENABLED == true ]]; then
    echo -e "${GREEN}[5/5] 配置定时任务（每30分钟检查峰谷策略）...${NC}"
    (printf '%s\n' "$CLEANED_CRONTAB"; echo "$CRON_COMMENT"; echo "$CRON_CMD") | write_target_crontab
    echo -e "${GREEN}✅ 已为 $TARGET_USER 更新 cron 任务${NC}"
    echo -e "   Python: $PYTHON_PATH"
    echo -e "   日志: $SCRIPT_DIR/cron.log"
else
    echo -e "${GREEN}[5/5] 自动定时优选已关闭。${NC}"
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

chmod +x setup.sh 2>/dev/null || true

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
