# Tasks: 链式代理自动适配 sing-box

## Task 1: 安全发现、安装 sing-box 并原子写入配置

**Description:** 在现有 `chain_proxy.py` 中扩展共享路径解析与 setup 准备入口。按配置路径、项目本地、PATH 查找；仅在启用且全部缺失时，从 SagerNet 官方最新稳定版选择匹配平台资产，校验 SHA-256、受限解压、版本检查后安装，并原子更新本机配置。

**Acceptance criteria:**

- [x] 路径优先级、Windows/Linux x64/arm64 资产映射与幂等行为符合规格。
- [x] 摘要不匹配、归档异常、版本失败或配置写入失败时，旧核心和配置保持不变。
- [x] 配置仅更新 `CHAIN_PROXY_CORE_PATH`，其他键保留；链式关闭时无操作。

**Verification:**

- [x] Tests pass: `python -m unittest tests.test_chain_proxy -v`
- [x] Tests cover: 发现顺序、平台映射、摘要失败、受限解压、原子写入、重复运行。

**Dependencies:** None

**Files likely touched:**

- `chain_proxy.py`
- `tests/test_chain_proxy.py`

**Estimated scope:** S (2 files)

## Task 2: 自动请求并解析 CfGfwAX sing-box 订阅

**Description:** 将订阅 URL 的请求副本规范化为 `target=singbox`，保留 Token 与其他查询参数；扩展现有提取函数，从 sing-box JSON `outbounds` 识别唯一的 CfGfwAX 链式模板，同时保留旧 mixed/base64 解析。

**Acceptance criteria:**

- [x] 无 target、mixed 或其他 target 都被替换为 singbox，其他 URL 部分不变。
- [x] 只提取匹配订阅域名的 VLESS + WS + TLS `/video/` outbound，忽略外部和控制型 outbound。
- [x] 同模板多地址折叠；多模板、非全局 SOCKS5、ECH/TLS 分片和畸形 JSON fail closed。

**Verification:**

- [x] Tests pass: `python -m unittest tests.test_chain_proxy -v`
- [x] Existing seven chain tests remain green.

**Dependencies:** None

**Files likely touched:**

- `chain_proxy.py`
- `tests/test_chain_proxy.py`

**Estimated scope:** S (2 files)

## Checkpoint: Shared foundations

- [x] `python -m unittest tests.test_chain_proxy -v`
- [x] Review download trust boundary and secret redaction.

## Task 3: 将 sing-box 与订阅预检移动到主流程最前

**Description:** 在 `main.py` 的耗时工作开始前完成订阅获取、核心解析和 `sing-box check`，打印脱敏状态；后续候选测速复用预检得到的模板与核心路径，不再晚发现同类配置错误。

**Acceptance criteria:**

- [x] 链式开启时预检发生在任何节点源请求或 TCP 测试前。
- [x] 配置、订阅或核心检查失败立即退出且不降级直连；输出不泄密。
- [x] 正常流程只获取一次订阅，并复用模板和核心路径启动运行时。

**Verification:**

- [x] Tests pass: `python -m unittest tests.test_chain_proxy tests.test_measurement_flow -v`
- [x] Ordering regression proves node fetching is not called after a failed preflight.

**Dependencies:** Task 1, Task 2

**Files likely touched:**

- `chain_proxy.py`
- `main.py`
- `tests/test_measurement_flow.py`

**Estimated scope:** M (3 files)

## Task 4: 接入 Windows/Linux setup 自动准备核心

**Description:** 在 Python 环境就绪后，让 `setup.ps1` 与 `setup.sh` 调用 Task 1 的共享入口。链式启用时展示发现/安装结果并写入配置；关闭时跳过。扩充现有 setup 回归，不在两个脚本中复制下载算法。

**Acceptance criteria:**

- [x] Windows 和 Linux setup 都调用同一 Python 共享逻辑。
- [x] 已有有效核心不下载，缺失核心安装到 `.runtime/sing-box/` 并写入相对路径。
- [x] 失败会停止 setup，并保留原配置、原核心和计划任务状态。

**Verification:**

- [x] Tests pass: `python -m unittest tests.test_setup_update_integration tests.test_windows_updater -v`
- [x] Static assertions confirm neither setup script contains a second download/extract implementation.

**Dependencies:** Task 1

**Files likely touched:**

- `setup.ps1`
- `setup.sh`
- `tests/test_setup_update_integration.py`
- `tests/test_windows_updater.py`

**Estimated scope:** M (4 files)

## Checkpoint: Runtime integration

- [x] `python -m unittest tests.test_chain_proxy tests.test_measurement_flow tests.test_setup_update_integration tests.test_windows_updater -v`
- [x] Confirm enabled/disabled and found/download setup paths.

## Task 5: 同步配置示例、README 与忽略规则

**Description:** 更新三语 README、配置注释和忽略规则，准确说明自动 sing-box 订阅适配、前置预检、项目内安装位置与不自动升级边界；同步规格中的最终事实。

**Acceptance criteria:**

- [x] 简体中文、繁体中文和英文说明一致。
- [x] `.runtime/` 与本机核心不会被 Git 跟踪，示例配置不含真实路径或秘密。
- [x] 文档命令和实际 setup/main 行为一致。

**Verification:**

- [x] Tests pass: `python -m unittest discover -s tests -v`
- [x] Manual review: README and `config.example.json` contain no Token, UUID or local absolute path.

**Dependencies:** Task 3, Task 4

**Files likely touched:**

- `.gitignore`
- `config.example.json`
- `README.md`
- `docs/spec-sing-box-chain-adaptation.md`

**Estimated scope:** M (4 files)

## Checkpoint: Implementation complete

- [x] `python -m unittest discover -s tests -v`
- [ ] Windows setup manual check.
- [ ] Linux setup manual check.
- [ ] Real CfGfwAX subscription preflight and chain test.
- [ ] All spec success criteria reviewed.

## Task 6: 冻结可复现的验证候选提交

**Description:** 在不包含任何本机运行文件或秘密的前提下审查当前功能 diff，通过显式 `@commit` 将实现、测试、文档和计划冻结到短期验证分支。Windows、Linux 和真实链测必须检出这个相同 commit。

**Acceptance criteria:**

- [x] 暂存清单只包含预期功能文件与 `docs/`、`tasks/` 文档，不含 `config.json`、`.runtime/`、`.codegraph/` 或秘密。
- [ ] 创建单一可识别的验证 commit，并记录 commit SHA；当前实现完整测试仍为绿色。
- [ ] Windows/Linux 验收环境都能从该 SHA 创建干净检出，不依赖当前工作区的未提交文件。

**Verification:**

- [x] Review: `git diff --cached --name-only` 与 `git diff --cached`。
- [x] Run: `python -m unittest discover -s tests -v`、`git diff --check` 和秘密扫描。
- [ ] User action: 显式调用 `@commit`；记录生成的 commit SHA。

**Dependencies:** Task 1–5

**Files likely touched:**

- 当前功能实现、测试与文档的预期提交文件

**Estimated scope:** S (发布工作流，不改业务逻辑)

**Rollback:** 提交前取消暂存；提交后如清单错误，在尚未共享时追加修正提交，已共享时使用 `git revert <validation-commit>`，不改写共享历史。

## Task 7: 在隔离 Windows 环境验收真实 setup

**Description:** 在一次性 Windows VM 或 CI runner 的干净检出中启用链式测速、清空核心路径并关闭定时任务，执行真实 `setup.ps1`；验证官方核心首次安装、相对路径写入和第二次运行幂等。不得在当前主工作区执行。

**Acceptance criteria:**

- [ ] 首次 setup 退出码为 0，`.runtime/sing-box/sing-box.exe` 可执行，`CHAIN_PROXY_CORE_PATH` 写为项目相对路径且其他配置保留。
- [ ] `sing-box version` 成功；再次运行 setup 时核心 SHA-256 与修改时间不变，没有重复下载或无意义配置改写。
- [ ] `ENABLE_SCHEDULED_TASK=false` 生效，验收环境未创建或修改计划任务；记录已脱敏。

**Verification:**

- [ ] Run: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1`
- [ ] Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
- [ ] Manual evidence: 两次 setup 的退出码、核心版本/哈希、配置字段与计划任务状态。

**Dependencies:** Task 6

**Files likely touched:**

- 隔离环境中的 `config.json`
- 隔离环境中的 `.runtime/sing-box/`
- `tasks/go-evidence.md`（仅写脱敏结论）

**Estimated scope:** S (验收，不改业务代码)

**Rollback:** 丢弃一次性 VM/runner；若意外创建计划任务，先删除该验收环境的任务再销毁环境。不得从当前工作区删除文件。

## Task 8: 在隔离 Linux 环境验收真实 setup

**Description:** 在一次性 Linux VM 或 CI runner 的干净检出中启用链式测速、清空核心路径并关闭 cron，执行真实 `setup.sh`；验证 Linux 资产、执行权限、配置写入和幂等行为。

**Acceptance criteria:**

- [ ] 首次 setup 退出码为 0，`.runtime/sing-box/sing-box` 可执行，`CHAIN_PROXY_CORE_PATH` 写为项目相对路径且其他配置保留。
- [ ] `sing-box version` 成功；再次运行 setup 时核心 SHA-256 与修改时间不变，没有重复下载或无意义配置改写。
- [ ] `ENABLE_SCHEDULED_TASK=false` 生效，用户 crontab 未变化；记录已脱敏。

**Verification:**

- [ ] Run: `bash ./setup.sh`
- [ ] Run: `./.venv/bin/python -m unittest discover -s tests -v`
- [ ] Manual evidence: 两次 setup 的退出码、核心版本/哈希、配置字段、执行权限与 crontab 状态。

**Dependencies:** Task 6

**Files likely touched:**

- 隔离环境中的 `config.json`
- 隔离环境中的 `.runtime/sing-box/`
- `tasks/go-evidence.md`（仅写脱敏结论）

**Estimated scope:** S (验收，不改业务代码)

**Rollback:** 丢弃一次性 VM/runner；若意外写入 cron，先恢复验收用户原 crontab 再销毁环境。

## Checkpoint: Real platform acceptance

- [ ] Windows 与 Linux 首次安装和二次幂等均通过。
- [ ] 每项测试至少在一个支持平台实际执行，没有意外跳过或失败。
- [ ] 验收摘要不含订阅 URL、Token、UUID 或本机绝对路径。

## Task 9: 使用真实订阅完成无副作用链式冒烟测试

**Description:** 用户仅在被忽略的本地 `config.json` 中提供真实 CfGfwAX 订阅；在已通过 Task 7 或 Task 8 的隔离环境中，不调用完整 `main()`，而是复用 `preflight_chain_proxy()`、`SingBoxRuntime`、现有节点抓取/TCP 检测与链式 HTTP 检测边界完成一次真实端到端请求。

**Acceptance criteria:**

- [ ] 请求副本实际使用 `target=singbox`，预检成功且输出不包含 Token、UUID 或 `/video/` 完整参数。
- [ ] 从正常节点源动态选择一个 TCP 可用候选，sing-box 启动成功，至少一次链式 HTTP 检测通过。
- [ ] 不调用 `main()`；Cloudflare DNS、GitHub 同步、WxPusher、结果文件和定时任务均无写入。

**Verification:**

- [ ] Run: 临时只读 smoke 驱动调用现有函数；驱动文件放在系统临时目录且不提交。
- [ ] Compare: 测试前后 DNS/GitHub/计划任务配置与项目受跟踪文件无变化。
- [ ] Manual evidence: 脱敏记录预检结果、sing-box 版本、候选数量和链式 HTTP 成功数。

**Dependencies:** Task 6，以及 Task 7 或 Task 8

**Files likely touched:**

- 被忽略的本地 `config.json`
- 系统临时目录中的 smoke 驱动与运行日志
- `tasks/go-evidence.md`（仅写脱敏结论）

**Estimated scope:** S (验收，不改业务代码)

**Rollback:** 停止临时 sing-box 进程、删除临时驱动/日志并恢复本地 `config.json`；若发现任何外部写入立即保持 NO-GO 并单独调查。

## Task 10: 完成依赖、秘密与上游发布审计

**Description:** 对 Windows/Linux 验收环境的精确已安装版本执行漏洞审计，复核当前官方 stable release 的四个平台资产与 SHA-256 字段，并扫描预期提交内容中的秘密和本机运行文件。此任务只收集证据，不自动升级依赖。

**Acceptance criteria:**

- [ ] 两个平台记录精确依赖版本并完成漏洞审计；没有未处置的可达 high/critical 项。
- [ ] SagerNet latest stable 仍各有唯一 Windows/Linux amd64/arm64 资产，且每项包含合法 `sha256:` digest。
- [ ] 预期提交不含真实 Token、UUID、私钥、本机绝对路径、`config.json`、`.runtime/` 或 `.codegraph/`。

**Verification:**

- [ ] Run: `python -m pip check`，并用隔离安装的审计工具检查验收环境导出的精确版本集合。
- [ ] Run: 官方 GitHub Releases API 元数据只读检查。
- [ ] Run: `git diff --check`、敏感值扫描与显式文件清单复核。

**Dependencies:** Task 7, Task 8

**Files likely touched:**

- `tasks/go-evidence.md`

**Estimated scope:** XS (1 个证据文件)

**Rollback:** 审计工具只安装在临时工具环境；删除该环境即可。发现漏洞或元数据不兼容时保持 NO-GO，不做强制自动升级。

## Checkpoint: Real chain and security evidence

- [ ] 真实订阅预检与至少一个候选的链式 HTTP 请求成功。
- [ ] 外部系统和受跟踪工作区均未被冒烟测试修改。
- [ ] 依赖、秘密与官方资产审计通过。

## Task 11: 汇总成功标准并创建最终证据提交

**Description:** 将规格十项 Success Criteria 逐条映射到自动测试或 Task 7–10 的脱敏证据，更新计划状态，将证据与状态作为独立提交追加到验证候选，再重新运行 ship gate。此任务不得用勾选框代替缺失证据。

**Acceptance criteria:**

- [ ] `tasks/go-evidence.md` 对十项标准逐条记录平台、命令/人工步骤、结果和回滚状态，所有项通过。
- [ ] 完整测试、语法检查、秘密扫描和 staged diff 复核通过；提交不含 `.codegraph/` 或本机运行文件。
- [ ] 通过显式 `@commit` 创建发布提交，工作区达到预期清洁状态，随后 `@ship` 返回 GO。

**Verification:**

- [ ] Run on both platforms: `python -m unittest discover -s tests -v`
- [ ] Run: PowerShell parser、`bash -n setup.sh`、`python -m py_compile chain_proxy.py main.py`、`git diff --check`。
- [ ] Review: `git diff --cached --name-only` 与 `git diff --cached` 后再提交并执行 ship gate。

**Dependencies:** Task 6, Task 7, Task 8, Task 9, Task 10

**Files likely touched:**

- `tasks/plan.md`
- `tasks/todo.md`
- `tasks/go-evidence.md`
- 当前功能实现与文档的预期提交文件

**Estimated scope:** M (证据、状态与发布工作流)

**Rollback:** 提交前取消暂存即可；提交后若最终 gate 失败，保持提交不发布并修复证据缺口。已发布后使用 `CHAIN_PROXY_TEST_ENABLED=false` 快速关闭，再 `git revert <release-commit>`。

## Checkpoint: GO

- [ ] Windows setup manual check.
- [ ] Linux setup manual check.
- [ ] Real CfGfwAX subscription preflight and chain test.
- [ ] Dependency/security/upstream metadata audit.
- [ ] All ten spec success criteria reviewed with evidence.
- [ ] Immutable release commit created and `@ship` returns GO.
