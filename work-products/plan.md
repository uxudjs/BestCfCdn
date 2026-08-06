# 实施计划：Xray 链式代理前置连通性与 setup 自修复

## 规划结论

按已批准的 `work-products/SPEC.md` 实施：链式代理的 WS、gRPC、XHTTP 全部迁移到单一 Xray 内核。实现必须先完成真实代理预检，再允许候选源请求、TCP 优选、结果写入、DNS/GitHub 副作用或调度注册。

本计划最初只定义任务；用户已于 2026-08-06 授权本次 `@debug` 修复与同步。commit、push、部署及真实调度修改仍未授权。

## 规划依据与当前证据

- `core/app.py:2225-2339`：当前先抓取候选、校准并做 TCP 探测，之后才获取订阅和启动链式核心，前置失败门位置错误。
- `setup.ps1:382-593`、`setup.sh:323-476`：当前先准备环境并注册调度，最后才可选运行完整 `main.py`，没有共享链式预检门。
- `core/chain_proxy.py`：当前只返回一个逻辑模板、不保留真实端点；XHTTP 被拒绝；`fragment` 被折叠成布尔值；核心仍绑定 sing-box 和动态 `releases/latest`。
- `work-products/tests/test_chain_proxy.py`：规格记录的变更前基线为 16/16，但只覆盖 sing-box/WS/gRPC 与 XHTTP 拒绝；本次规划未把它冒充为变更后证据。
- Xray 实施候选为官方当前稳定版 `v26.3.27`。官方发布页将其标为 Latest，并明确包含 XHTTP 与 TLS ECH；本次以 Task 2 的固定资产、三传输配置契约和当前真实订阅提供的 XHTTP 连接门作为固定版本证据。不得自动改用预发布版或运行时追随 `latest`。

官方依据：

- `https://github.com/XTLS/Xray-core/releases/tag/v26.3.27`
- `https://xtls.github.io/en/config/transports/`
- `https://xtls.github.io/en/config/transports/tls.html`
- `https://github.com/XTLS/Xray-core/discussions/4113`

## 实施架构

```text
setup.ps1 / setup.sh                    main.py -> core.app
          |                                      |
          +-------- project .venv Python --------+
                             |
                  core.chain_proxy 共享入口
                             |
        严格配置 -> 订阅解析 -> Xray 修复/验证 -> SOCKS HTTPS 预检
                             |
                   ChainPreflightResult
             (模板、最多三端点、已验证核心路径)
                             |
               后续候选 Xray 运行时复用结果
```

核心边界：

1. `core.chain_proxy` 负责订阅契约、固定 Xray 资产、配置生成、临时运行时、真实连接预检与内部 CLI；Windows/Linux setup 不复制这些判断。
2. `core.app` 只在正确阶段调用共享预检并复用结果；链式关闭时不触碰订阅或 Xray。
3. setup 只管理项目根目录内的 `.venv`、`.xray` 和本项目调度项；旧 `.sing-box` 与项目外核心只保留、不执行、不修改。
4. 所有正式测试位于 `work-products/tests/`，测试从最终位置按仓库相对关系定位文件。

## 依赖顺序

```text
Task 1 订阅模型与 XHTTP
  -> Task 2A 固定 Xray 资产与发现
      -> Task 2B Xray 配置与运行时
          -> Task 3 共享真实预检与迁移入口
          -> Task 4 main.py 前置门
          -> Task 5 Windows setup
          -> Task 6 Linux setup
              -> Task 7 三语文档与遗留收口
                  -> Task 8 完整与真实验收
```

Task 4、5、6 都依赖 Task 3；Task 5 与 Task 6 可在 Task 3 通过后分别实施，但必须在 Checkpoint B 一起验收。

## Task 1：建立无损 CfGfwAX 订阅结果与 XHTTP 契约

**状态**：已完成（聚焦 22/22；BestCfCdn 完整 116 项中 110 通过、6 项 POSIX 跳过；CfGfwAX 24/24）。

**范围**

- 将解析结果从单个 `ChainTemplate` 扩展为“最多三个去重且模板与端点绑定的探针对 + 脱敏来源标识”。
- 保留 WS 的 `host/path`、gRPC 的 `authority/serviceName`、XHTTP 的 `host/path/mode`，以及 `security`、`sni`、`flow`、`allowInsecure`、`ech`、`fragment`、`fp` 的有效原值。
- XHTTP 只接受显式 `mode=stream-one`。验证 `/video/` 时先尝试原始密文；仅原始失败且路径恰有一个兼容末尾 `/` 时，再去掉一个 `/` 重试。返回模板仍保留原始传输路径，不宽松改写中间字节。
- 完全相同的探针对去重；CfGfwAX 随机 CDN `host`/`sni` 与各自端点不得交叉组合。无探针、非全局 SOCKS5、非法端口和无法无损保留的字段 fail closed。

**验收标准**

- mixed 明文和整份 base64 内容都返回顺序稳定、去重且最多三个的模板/端点探针对。
- WS、gRPC、XHTTP `stream-one` 成功；XHTTP 缺失 mode、其他 mode、两个尾斜杠或损坏密文失败。
- `fragment` 不再是布尔值；测试逐字段证明 ECH、分片、指纹、路径与传输参数未丢失。
- 错误或快照不出现完整订阅 URL、UUID、VLESS URI、`/video/` 密文或 SOCKS5 凭据。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
node --test ..\CfGfwAX\work-products\tests\chain_proxy.test.mjs
```

**依赖**：已批准规格。
**预计文件**：`core/chain_proxy.py`、`work-products/tests/test_chain_proxy.py`。
**规模**：M。
**回滚**：整体回退解析模型与对应测试；不得保留只接受 XHTTP 却丢弃其字段的半迁移状态。

## Task 2A：固定 Xray 资产、发现与安全安装

**范围**

- 先新增资产选择、固定 URL、摘要、身份/版本、原子替换和外部文件零修改的 RED 回归，并记录它们在现有动态 sing-box 路径下按预期失败；之后才实施 GREEN。
- 用固定 Xray 资产清单和 `resolve_xray_path` 替换运行路径中的 sing-box 发现、下载与版本判断。
- 以 `v26.3.27` 为候选，先记录每个现有受支持 OS/架构的官方资产名、大小和 SHA-256，再允许下载。若官方资产不能覆盖当前支持矩阵，停止并请求批准，不静默缩减平台。
- 发现顺序固定为：有效配置路径 -> 项目 `.xray` -> PATH `xray` -> 安装项目 `.xray`。每个候选都验证 Xray 身份、固定版本和配置检查能力；外部无效核心不被修改。
- 仅从 `XTLS/Xray-core` 固定 HTTPS 发布 URL 下载；限制大小、只提取清单内的 Xray 可执行文件，以同目录临时文件校验后原子替换。
- `.xray/` 加入忽略与保护集合；`.sing-box/` 继续忽略和保护，但不再执行或自动删除。

**验收标准**

- 单元测试覆盖资产选择、固定 URL、大小/SHA 错误、压缩包穿越/重复可执行文件、原子替换、身份/版本错误及外部文件零修改。
- 实际候选二进制通过 Xray 身份与固定版本验证；仅 mock 成功不能完成本任务。
- 下载、校验、身份或版本失败时不替换既有项目 Xray，也不修改外部核心。
- `rg` 证明核心发现与下载路径不存在 sing-box 命令或动态 `releases/latest`。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
git diff --check
```

**依赖**：Task 1。
**预计文件**：`core/chain_proxy.py`、`core/paths.py`、`.gitignore`、`work-products/tests/test_chain_proxy.py`、`work-products/tests/test_project_layout.py`。
**规模**：M。
**回滚**：代码与测试整体回退；不删除旧 `.sing-box` 或项目外核心。被忽略的 `.xray` 可保留，除非用户另行授权清理。

## Task 2B：实现 Xray 三传输配置与临时运行时

**范围**

- 先新增 WS、gRPC、XHTTP、TLS/ECH/fragment/fp/flow/allowInsecure 映射、配置检查和运行时清理的 RED 回归，并记录现有 sing-box 生成器按预期失败；之后才实施 GREEN。
- 用 `build_xray_config` 和 `XrayRuntime` 替换 sing-box 配置与进程调用。
- 每个端点生成独立本地 SOCKS 入站、VLESS 出站与路由。WS、gRPC、XHTTP 使用固定版本 schema，XHTTP 显式 `stream-one` 且不启用冲突 mux。
- 按固定版本实际 schema 无损映射 SNI、Host/Authority、路径、证书校验、`fp`、ECH 查询值、完整 fragment 参数、`flow` 与 `allowInsecure`；任何已设置但不能无损映射的字段都在网络前 `CORE_ERROR`，不得静默忽略。

**验收标准**

- 生成配置的逐字段测试覆盖 WS、gRPC、XHTTP 以及 TLS/ECH/fragment/fp/flow/allowInsecure；无法映射的已设置字段 fail closed。
- 下载并校验后的实际固定 Xray 分别对 WS、gRPC、XHTTP 配置通过只读配置检查，并记录命令、版本和退出码；不得提交二进制或临时配置。
- 运行时启动失败、监听失败和日志错误均脱敏；正常退出不遗留进程、临时配置或秘密日志。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
git diff --check
```

**依赖**：Task 1、Task 2A。
**预计文件**：`core/chain_proxy.py`、`work-products/tests/test_chain_proxy.py`。
**规模**：M。
**回滚**：与 Task 2A 一起回退 Xray 单内核运行路径；不得留下“已下载 Xray、候选测试仍执行 sing-box”的半迁移状态。
## Task 3：实现共享真实连接预检、错误分类与配置迁移

**范围**

- 先新增真实 SOCKS HTTPS 失败分类、最多三端点、单次订阅、严格布尔值、配置迁移和幂等性的 RED 回归，并记录现有晚检查路径按预期失败；之后才实施 GREEN。
- 在 `core.chain_proxy` 提供单一 Python API，并提供 setup 可调用的内部模块入口，例如 `python -m core.chain_proxy preflight --config config.json`；命令行只传配置文件路径，不传订阅或凭据。
- 严格验证 `CHAIN_PROXY_TEST_ENABLED` 为 JSON 布尔值。`false` 立即成功且不请求订阅、不解析或下载 Xray；`true` 才进入订阅、核心和连接状态机。
- 严格验证订阅 HTTPS URL、无 URL 用户名/密码、2 MiB 上限与请求超时，然后复用 Task 1 解析结果。
- 用最多三个真实订阅探针对启动 Xray，通过本地 SOCKS 对独立的轻量 HTTPS 2xx 目标发起最小请求；不得复用 CfGfwAX 明确禁止的测速域名。任一 HTTP 2xx 通过，全部失败为 `CONNECTIVITY_ERROR`。仅配置检查或端口就绪不算通过。
- 返回 `ChainPreflightResult`，至少包含模板、已验证核心路径和端点证据，供 `core.app` 后续复用；结果不得包含可打印秘密。
- 给 `ChainProxyError` 增加稳定分类：`ENVIRONMENT_ERROR`、`SUBSCRIPTION_ERROR`、`CORE_ERROR`、`CONNECTIVITY_ERROR`，并统一阶段、脱敏原因与恢复建议。
- 当非空 `CHAIN_PROXY_CORE_PATH` 指向 sing-box、无效或不兼容外部核心，而项目 Xray 已完整验证时，只原子更新该字段为可移动的项目相对路径；其他 JSON 字段语义、UTF-8 与文件权限保持。空值保持空值以继续使用共享发现顺序。

**验收标准**

- 配置检查成功但 SOCKS HTTPS 请求失败时返回 `CONNECTIVITY_ERROR` 和非零 CLI 退出码。
- 三端点中第二或第三个成功可通过；最多尝试三个，全部失败不降级直连。
- 同一预检只请求一次订阅；错误、stdout/stderr 和通知用固定脱敏夹具证明不泄密。
- 旧 sing-box 配置字段成功迁移且旧 `.sing-box`/外部文件未变；下载、校验或连接失败不改写配置。
- 第二次运行有效环境不下载、不改配置，具备幂等证据。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
```

**依赖**：Task 1、Task 2A、Task 2B。
**预计文件**：`core/chain_proxy.py`、`work-products/tests/test_chain_proxy.py`。
**规模**：M。
**回滚**：回退 API、CLI 和配置迁移为一个单元；若已迁移真实 `config.json`，回滚代码不自动改回 sing-box，避免重新启用旧核心。

## Task 4：把 main 链式门移动到第一个候选请求之前

**范围**

- 在 `core.app::_run()` 的第一个候选源请求之前调用共享预检；链式配置类型错误也在任何网络请求前失败。
- 删除当前候选形成后才获取订阅/解析核心的晚检查。
- 后续候选 Xray 运行时只使用同一 `ChainPreflightResult` 的模板和核心路径，不重新获取订阅或重新选核心。
- 预检失败保持候选源、校准、TCP、输出、DNS、GitHub 同步调用数为零；链式关闭流程保持原行为。

**验收标准**

- RED/GREEN 调用记录证明预检严格早于 `fetch_additional_source`、`calibrate_regions` 和 `test_node`。
- 任一预检错误使进程非零退出，且 `write_ip_txt`、Cloudflare DNS、GitHub 同步与通知内容不泄密。
- 预检成功的完整链式流程仅获取一次订阅；候选运行时复用同一模板和核心路径。
- `CHAIN_PROXY_TEST_ENABLED=false` 时预检 no-op 且现有直连测量回归通过。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_measurement_flow.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
```

**依赖**：Task 3。
**预计文件**：`core/app.py`、`work-products/tests/test_measurement_flow.py`、必要时 `work-products/tests/test_chain_proxy.py`。
**规模**：M。
**回滚**：Task 3 可保留为独立内部能力，但不得发布会恢复“最后才检查”的 `core.app`；发布回滚必须同时恢复规格前整个链式单元。

## Checkpoint A：Python 行为门

- Task 1 至 Task 4 的聚焦测试全部通过。
- 实际固定 Xray 已对 WS、gRPC、XHTTP 配置检查成功。
- 预检失败时，候选源请求和 TCP 探测均为 0；预检成功时只取一次订阅。
- 链式关闭回归保持通过。
- 任一项失败即停止，不进入 setup 调度改造。

## Task 5：Windows setup 项目环境自修复与调度门

**范围**

- 先新增 `.venv` 缺失/损坏/有效、reparse point 拒绝、依赖导入及预检先于调度的 Windows RED 回归，并记录现有 setup 按预期失败；之后才实施 GREEN。
- `.venv` 不存在时，使用受支持的 bootstrap Python 在项目根准确路径创建；不使用或修改当前激活的项目外环境。
- 将 `.venv` 判定从“解释器文件存在”提升为：解释器可启动、Python >= 3.9、pip 可用、核心依赖可导入。有效环境幂等复用。
- 损坏环境只在确认目标是项目根下真实目录且不是 reparse point 后修复：先把旧 `.venv` 改名为同目录备份，再在准确的 `.venv` 路径重建；失败时恢复旧目录，成功后才移除备份。项目外环境永不修改。
- 对新建或修复的环境不执行激活；后续全部命令使用项目 `.venv` 的绝对解释器路径，依次修复 pip、安装 `requirements.txt` 与现有 Brotli 依赖，并实际导入 `requests`、`aiohttp` 和 Brotli 实现。
- 依赖成功后、任何 COM/schtasks 注册前，先移除/禁用本项目旧任务，再调用 Task 3 的共享模块入口；失败非零并保持本项目任务不存在。
- 共享入口在链式关闭时 no-op；开启时负责准备/验证 `.xray` 与真实连接。成功后才按 `ENABLE_SCHEDULED_TASK` 注册或保持关闭。
- 首次缺少 `config.json` 的两阶段流程不变：只生成模板、移除本项目旧任务并停止，不安装环境或猜测秘密。

**验收标准**

- 已配置项目在 `.venv` 完全缺失时可创建环境、安装 requirements/Brotli 并通过实际导入；后续命令记录为项目绝对解释器路径。
- 调用顺序测试证明：依赖导入 -> 移除本项目任务 -> 共享预检 -> 注册任务。
- 预检失败、损坏 `.venv` 修复失败或配置类型错误时，没有可运行的新任务，且退出码非零。
- 有效 `.venv`/`.xray` 第二次 setup 不重建、不下载、不无意义改写配置。
- reparse point、项目外路径和旧 `.sing-box` 不被删除或覆盖。
- PowerShell 5.1 解析通过，现有管理员、自更新和 SYSTEM 调度语义不被无关改写。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_platform_contract.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_multi_terminal_sync.py -v
$files = @('setup.ps1', 'scripts/git_sync.ps1', 'scripts/update_fork.ps1')
foreach ($file in $files) { [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8)) }
```

**依赖**：Task 3、Checkpoint A。
**预计文件**：`setup.ps1`、`work-products/tests/test_platform_contract.py`、`work-products/tests/test_multi_terminal_sync.py`，必要时新增 `work-products/tests/test_setup_chain_preflight.py`。
**规模**：M。
**回滚**：回退 setup 代码前先确认本项目任务状态；不得把失败配置重新注册。环境备份仅由本次受控修复创建和清理。

## Task 6：Linux setup 项目环境自修复与 cron 门

**范围**

- 先新增 `.venv` 缺失/损坏/有效、符号链接拒绝、目标用户所有权及预检先于 cron 的 Linux RED 回归，并记录现有 setup 按预期失败；之后才实施 GREEN。
- `.venv` 不存在时，以目标用户和受支持的 bootstrap Python 在项目根准确路径创建；损坏时按 Task 5 的备份/恢复契约修复，并拒绝符号链接、项目外目标和无法安全恢复的目录。
- 不激活环境；所有后续命令使用项目 `.venv/bin/python` 的绝对路径，修复 pip、安装 `requirements.txt` 与现有 Brotli 依赖，并实际导入 `requests`、`aiohttp` 和 Brotli 实现。
- 依赖成功后先从目标用户 crontab 精确移除本项目条目，保留其他 cron；之后调用同一 Python 预检入口，成功后才按开关写回本项目条目。
- 确保以目标用户而非 root 创建 `.venv`、`.xray` 和配置临时文件；现有包管理器与 sudo 边界保持不变。
- 共享入口在链式关闭时 no-op，不引入 Xray 下载或订阅请求。

**验收标准**

- Bash 集成/源契约测试证明预检严格早于 `write_target_crontab` 注册动作；失败时本项目 cron 不存在、其他条目字节语义保持。
- 已配置项目在 `.venv` 完全缺失时可由目标用户创建并通过 requirements/Brotli 实际导入；损坏环境失败时恢复旧目录，外部或链接目录零修改。
- 有效环境重复 setup 幂等，文件所有者保持目标用户。
- `bash -n` 与现有更新、配置合并、非交互执行回归通过。

**验证**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_setup_update_integration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_platform_contract.py -v
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh
```

**依赖**：Task 3、Checkpoint A。
**预计文件**：`setup.sh`、`work-products/tests/test_setup_update_integration.py`、`work-products/tests/test_platform_contract.py`，必要时 `work-products/tests/test_setup_chain_preflight.py`。
**规模**：M。
**回滚**：只回退本项目 setup/测试；不得覆盖目标用户其他 cron，也不得自动恢复会运行失败链式配置的旧条目。

## Checkpoint B：跨平台 setup 门

- Windows 与 Linux 都调用同一个 Python 预检入口，没有复制订阅解析、Xray 下载或连接判断。
- 两个平台均先移除本项目旧调度，预检成功后才注册；失败时不留下可运行调度。
- 缺失、损坏和有效 `.venv` 三类路径都有测试；链接与项目外环境 fail closed。
- 静态/模拟测试只称为跨平台契约证据，不称为真实 Windows/Linux 空环境安装证明。

## Task 7：同步配置、三语文档与遗留运行引用

**范围**

- 更新 `config/config.example.json`：Xray 单内核、XHTTP `stream-one`、项目 `.xray`、前置真实连接、严格布尔值、首次配置边界与失败不降级。
- 同步 README 简体中文、繁体中文、英文三个区段，明确 setup 可修复项目 `.venv`/`.xray`，但不能生成私密订阅。
- 更新项目规则中已过时的 “XHTTP 不支持/sing-box 运行路径” 描述，同时保留 `.sing-box` 仅为人工回滚遗留的安全边界。
- 扫描 sing-box/XHTTP/链式核心引用；运行时代码不得执行 sing-box，测试与文档只允许保留迁移、回滚或“不得执行”的明确语境。
- 仅当聚焦测试证明 setup 兼容契约受影响时，才最小修改 `scripts/update_fork.ps1`/`.sh`；不得顺手改变更新策略。

**验收标准**

- 三语内容覆盖同一 6 项：Xray、WS/gRPC/XHTTP、前置实连、项目内自修复、失败关闭、首次私密配置。
- 模板不含真实 URL/Token/UUID；README 示例继续使用 `***`。
- `.xray/` 被 Git 忽略并受清理保护，`.sing-box/` 仍保留但无执行路径。
- 文档、模板和项目规则不再引导用户配置 sing-box。

**验证**

```powershell
rg -n "sing-box|XHTTP|CHAIN_PROXY_CORE_PATH|\.xray" README.md AGENTS.md config core setup.ps1 setup.sh work-products/tests
git diff --check
```

**依赖**：Task 4、Task 5、Task 6、Checkpoint B。
**预计文件**：`README.md`、`config/config.example.json`、`AGENTS.md`；更新脚本仅在测试证明必要时加入。
**规模**：M。
**回滚**：文档、模板与实现必须一起回滚；不得留下声称支持 XHTTP、实际却执行旧核心的文档。

## Task 8：完整回归、消费者契约与真实验收

**范围**

- 执行本地完整回归、跨仓消费者契约、秘密扫描，以及用户本次接受的 Windows/Linux 理论跨平台门；可用的真实订阅类型另行验证，不在本任务新增功能。

**验证**

### 8A 本地可重复门

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_measurement_flow.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -v
$files = @('setup.ps1', 'scripts/git_sync.ps1', 'scripts/update_fork.ps1')
foreach ($file in $files) { [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8)) }
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh
node --test ..\CfGfwAX\work-products\tests\chain_proxy.test.mjs
git diff --check
```

还须执行脱敏扫描，确认 diff、测试夹具和捕获日志不含真实订阅、Token、UUID、完整 VLESS URI、`/video/` 密文或 SOCKS5 凭据。

### 8B 理论跨平台门与可用真实链路

- Windows/Linux：本次按用户授权，以共享 Python 入口、PowerShell/Bash 语法、平台矩阵、setup 契约和 Xray 配置检查作为理论跨平台证据；不冒充真实 Linux 或空环境 setup。
- 固定版本的 WS、gRPC、XHTTP `stream-one` 均须通过配置与消费者契约。用户当前真实订阅实际提供的类型执行 SOCKS HTTPS；未提供的类型标为仅理论证明，不因此单独判定 NO-GO。
- 真实链式开关为 `true` 时，记录预检先于候选抓取；故意制造订阅/连接失败时，确认候选请求/TCP 为 0、输出和外部发布不变、调度未启用。
- 成功路径完成一次真实链式优选，确认订阅只获取一次，并单独报告 Xray 版本、传输类型、setup 平台与结果；证据必须脱敏。
- 独立评估完整优选后的结果质量：最终节点数量/配额、链式成功率与延迟/带宽资格、排序及输出一致性分别记录为通过、失败或未执行；进程成功退出不能自动推断结果质量通过。

**验收标准**

- 8A 全绿且无敏感信息。
- 8B 的 Windows/Linux 理论证据、真实订阅/出口、WS、gRPC、XHTTP `stream-one` 与完整优选结果质量分别陈述为理论通过、真实通过、失败或未执行；不得混写。
- `v26.3.27` 必须通过三类传输的静态配置/消费者契约，且当前订阅的实际 XHTTP 类型须真实通过；真实 WS/gRPC 和空环境 setup 在本次用户授权下不是放行前提。

**依赖**：Task 1 至 Task 7。
**预计文件**：无；仅当回归定位出本范围缺陷时回到对应任务做最小修正。
**规模**：M（外部环境时间另计）。
**回滚**：任一安全、顺序、当前真实 XHTTP 或理论跨平台门失败即 NO-GO；整体回滚 Xray 单内核、共享预检、setup 调度门和配套文档，不保留半迁移发布候选。

## 完成定义与停止条件

只有以下条件全部成立，实施才可标记完成：

1. 本次用户批准的 Windows/Linux 理论门、真实 XHTTP 预检及本地可重复验收全部有证据；明确豁免的空环境、真实 Linux、真实 WS/gRPC 和完整优选质量继续标为未执行。
2. 链式 `true` 的所有失败路径在候选请求、TCP、写文件、DNS/GitHub 和调度之前停止。
3. WS、gRPC、XHTTP 全部只有 Xray 运行路径，XHTTP 仅 `stream-one`。
4. Windows/Linux setup 共享预检且项目 `.venv`/`.xray` 修复幂等、安全。
5. 本地/static、实际 Xray 配置检查、Windows/Linux 理论证据、真实订阅/出口分别报告，不混为一谈。

遇到以下任一情况立即停止并请求用户决策：

- 固定 Xray 无法无损映射订阅中已设置的 ECH、fragment、fp、flow 或传输字段；
- 官方固定资产不能覆盖现有支持矩阵；
- CfGfwAX 生产者契约与 approved spec 不一致；
- 需要新增第三方依赖、支持其他 XHTTP mode、改评分/调度/发布策略；
- 真实验收需要修改当前用户调度、系统包或外部环境而尚未获得授权。

## 授权状态

- `work-products/SPEC.md`：已批准。
- 本实施计划及本次 `@debug` 修复/同步：已批准。
- commit、push、部署、真实调度与外部环境操作：尚未授权。
