# Spec: 链式代理自动适配 sing-box

## Assumptions

1. 只有 `CHAIN_PROXY_TEST_ENABLED=true` 时，setup 才查找或下载 sing-box；关闭链式测速时不增加下载和启动开销。
2. 项目内安装位置固定为 `.runtime/sing-box/sing-box.exe`（Windows）或 `.runtime/sing-box/sing-box`（Linux），并加入 `.gitignore`。
3. 自动下载支持 Windows 与 Linux 的 x86_64/amd64、arm64/aarch64；其他系统或架构给出明确错误，不猜测资产。
4. `CHAIN_PROXY_SUBSCRIPTION_URL` 仍由用户提供且保留 Token；运行时仅在请求副本中自动设置 `target=singbox`，不改写该订阅 URL。
5. 继续兼容旧 mixed/base64 VLESS 订阅，但 CfGfwAX 的首选输入改为其原生 sing-box JSON 订阅。
6. 自动下载仅使用 SagerNet 官方 GitHub 最新稳定版发布资产，并在落盘前验证发布资产提供的 SHA-256；无法验证时停止安装。

## Objective

修复现有链式测速对 CfGfwAX 新订阅能力适配不足、sing-box 校验过晚的问题，并让 setup 完成核心发现、安装和配置写入。

用户运行 setup 或 `main.py` 时应获得以下行为：

- setup 在链式测速启用时按“有效配置路径 → 项目内核心 → PATH”查找 sing-box。
- 找到核心后，将可执行文件路径写入本机 `config.json` 的 `CHAIN_PROXY_CORE_PATH`。
- 找不到核心时，从官方最新稳定版下载匹配当前系统/架构的资产到项目 `.runtime/sing-box/`，验证 SHA-256 和可执行性后再写配置。
- `main.py` 在获取节点、TCP 测试等耗时工作之前完成订阅获取、sing-box 路径解析和生成配置检查；失败立即停止。
- CfGfwAX 订阅请求自动使用 `target=singbox`，从 JSON `outbounds` 提取唯一的 VLESS + WebSocket + TLS `/video/` 链式模板。
- 不静默降级为直连，不在输出中泄露订阅 Token、UUID、链式路径或 SOCKS5 凭据。

## Tech Stack

- Python 3.9+
- Python 标准库：`json`、`urllib.parse`、`urllib.request`、`hashlib`、`zipfile`、`tarfile`、`platform`、`tempfile`、`shutil`、`subprocess`
- 现有依赖：`requests`、`aiohttp`
- Windows PowerShell 5.1+：`setup.ps1`
- Bash：`setup.sh`
- sing-box 官方稳定版发布资产

不新增第三方依赖。

## Commands

```powershell
# Windows setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1

# 链式代理单元测试
python -m unittest tests.test_chain_proxy -v

# setup 回归测试
python -m unittest tests.test_setup_update_integration tests.test_windows_updater -v

# 全量测试
python -m unittest discover -s tests -v

# 手工运行
.\.venv\Scripts\python.exe -X utf8 .\main.py
```

```bash
# Linux setup
bash ./setup.sh

# 全量测试
python3 -m unittest discover -s tests -v

# 手工运行
./.venv/bin/python main.py
```

本项目没有独立 build 或 lint 命令。

## Project Structure

```text
chain_proxy.py                  链式订阅解析、sing-box 路径解析、预检与安装共享逻辑
main.py                         主流程；在耗时节点处理前执行链式预检
setup.ps1                      Windows 部署入口，调用共享 sing-box setup 逻辑
setup.sh                       Linux 部署入口，调用共享 sing-box setup 逻辑
config.example.json            链式配置说明与默认值
tests/test_chain_proxy.py      sing-box JSON、旧订阅、路径发现、下载选择和预检回归
tests/test_setup_update_integration.py
                                Linux setup 配置写入集成回归
tests/test_windows_updater.py  Windows setup 静态/行为回归
docs/spec-sing-box-chain-adaptation.md
                                本规格
.runtime/sing-box/             setup 生成的本机核心目录，不纳入版本控制
```

## Code Style

沿用现有 Python 风格：snake_case、四空格、无新增框架；共享行为只在 `chain_proxy.py` 实现一次，两个 setup 脚本只负责调用。

```text
python chain_proxy.py --prepare-sing-box config.json
```

setup 通过上述共享入口准备核心；`main.py` 再调用 `preflight_chain_proxy()`，一次性取得并验证订阅模板与核心路径。

- 路径返回绝对路径，写入 JSON 时使用相对项目路径，保证项目可移动。
- 配置写入使用同目录临时文件和 `os.replace`，避免中断造成 `config.json` 损坏。
- 下载解压只读取预期的单个可执行文件成员，不进行整包无约束解压。
- 错误消息可定位系统、架构、订阅格式或核心检查问题，但必须脱敏。

## Testing Strategy

使用现有 `unittest`，不引入测试框架。

- 单元测试：
  - URL 已有、缺少或包含其他 `target` 时，实际请求 URL 都正确变为 `target=singbox`，其余查询参数不变。
  - sing-box JSON 中只提取匹配订阅域名的 VLESS + WS + TLS `/video/` outbound，并忽略 selector、direct、block 和外部节点。
  - 多地址同模板折叠；多个不同模板、非全局 SOCKS5、ECH/TLS 分片、畸形 JSON 均 fail closed。
  - 路径优先级为有效配置路径、项目本地、PATH；无效显式路径不会阻止后续自动发现。
  - 平台/架构到官方资产名映射正确；摘要不匹配、归档缺少核心、非预期归档成员均不落盘。
  - 配置写入保留其他键，失败时原文件不变。
  - 前置检查调用 `sing-box check`，失败信息脱敏。
- 集成回归：
  - Windows/Linux setup 在链式关闭时不安装。
  - 已安装时不下载并写入路径；缺失时模拟官方发布响应、安装到 `.runtime/sing-box/` 并写入路径。
  - `main.py` 的链式预检发生在节点源抓取和 TCP 测试之前，并复用预检得到的模板与核心路径。
- 手工检查：在 Windows 和 Linux 各运行一次 setup，再以真实 CfGfwAX 订阅执行一次链式测速。

## Boundaries

- Always:
  - 先解析并验证 JSON，再原子写回 `config.json`。
  - 下载官方稳定版资产并校验 SHA-256 后才安装。
  - 使用项目本地临时文件，失败时清理临时内容并保留原核心与配置。
  - 前置验证失败立即停止，不降级直连。
  - 日志和异常对 Token、UUID、`/video/` 参数及 SOCKS5 凭据脱敏。
  - 保留旧 mixed/base64 订阅回归测试。
- Ask first:
  - 增加 macOS、32 位或其他架构支持。
  - 改为自动升级已经可用的 sing-box。
  - 改变 `config.json` 字段名或删除旧订阅兼容。
  - 增加第三方依赖或更改计划任务/cron 策略。
- Never:
  - 提交本机 `config.json`、下载的核心、订阅 Token 或运行日志。
  - 从非 SagerNet 官方源下载核心。
  - 未校验摘要就替换现有核心。
  - 对归档执行不受约束的全量解压。
  - 因 sing-box 或订阅失败而继续直连测速。

## Success Criteria

1. 当链式测速开启且 `CHAIN_PROXY_SUBSCRIPTION_URL` 是 mixed、无 target 或其他 target 时，请求实际使用同一 URL 的 `target=singbox`，Token 和其他参数原样保留。
2. CfGfwAX sing-box JSON 订阅能生成与当前 `ChainTemplate` 等价的模板；当前旧 mixed/base64 测试继续通过。
3. `main.py` 在任何节点源获取、TCP/HTTP/带宽测试前打印链式测速状态与预检结果；订阅、核心或生成配置无效时退出，且没有产生测速工作。
4. setup 在链式开启时自动发现有效核心并写入 `CHAIN_PROXY_CORE_PATH`；配置值优先，其次 `.runtime/sing-box/`，最后 PATH。
5. 三处都未找到时，setup 将官方最新稳定版的正确平台资产安装到 `.runtime/sing-box/`，校验 SHA-256、运行版本检查，并写入相对项目路径。
6. 链式关闭时 setup 不查找、不下载、不修改 `CHAIN_PROXY_CORE_PATH`。
7. 重复运行 setup 幂等：已有有效核心不会重复下载，已正确配置不会产生无意义改写。
8. 下载、解压、验证或写配置任一步失败时，旧核心和 `config.json` 保持可用；错误明确且不包含敏感值。
9. `python -m unittest discover -s tests -v` 全部通过；Windows 与 Linux 的真实 setup 手工检查通过。
10. README 的简体中文、繁体中文和英文说明同步描述自动适配、前置检查与项目内安装行为。

## Out of Scope

- 管理 sing-box 系统服务或 TUN 模式。
- 自动升级一个已经可用的 sing-box。
- 支持 CfGfwAX 之外任意 sing-box 配置结构。
- 改变现有链式评分算法、候选数量或并发策略。
- 改变订阅 Token 的存储方式。

## Open Questions

已按实现确认：项目内目录使用 `.runtime/sing-box/`；首版自动安装支持 Windows/Linux x64 与 arm64；仅在链式测速启用且没有可用核心时安装，不自动升级已有可用核心。
