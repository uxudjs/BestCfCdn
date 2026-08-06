# Spec：Xray 链式代理前置连通性与 setup 自修复

状态：已批准；用户已授权本次 `@debug` 修复与同步，未授权 commit、push 或部署。

日期：2026-08-06

## 1. 结论与问题证据

当前链式代理的解析、sing-box 配置生成和候选链路测速已有单元测试，但启动顺序存在确定缺陷，setup 的自修复边界也不完整；现有 sing-box 路径还无法承载用户要求的 XHTTP。

### 1.1 已确认缺陷：链式代理检查发生得太晚

当前 `core/app.py::_run()` 的顺序是：

1. 获取 `ADDITIONAL_SOURCES`；
2. 地区校准、前置过滤；
3. 对全部节点执行 TCP 探测；
4. 形成最多 `BANDWIDTH_CANDIDATES` 个候选；
5. 仅此时才获取 CfGfwAX 订阅、定位或下载 sing-box、执行 `sing-box check` 并测试真实链路。

证据：`core/app.py:2225-2339`。因此订阅无效、sing-box 不可用、SOCKS5 未开启全局模式或真实链路不通时，用户必须等待前面的大量工作完成后才收到错误。这与“`CHAIN_PROXY_TEST_ENABLED=true` 时必须先测试连接”的要求冲突。

### 1.2 已确认缺陷：setup 会先注册调度，再知道链式代理能否工作

- `setup.ps1` 会创建 `.venv`、安装依赖并注册计划任务，最后才可选运行一次完整 `main.py`；用户选择不运行时完全没有链式预检。
- `setup.sh` 同样先写入 cron，最后才可选运行完整 `main.py`。
- 两个平台都没有在调度副作用前调用共享的链式连接预检。

证据：`setup.ps1:382-593`、`setup.sh:323-476`。

### 1.3 已确认测试缺口

- `work-products/tests/test_chain_proxy.py` 当前覆盖 mixed/base64 VLESS、WS/gRPC、ECH、TLS 分片、指纹、XHTTP 拒绝和 sing-box 下载校验；缺少 Xray 配置、安装和 XHTTP 成功路径。
- `work-products/tests/test_measurement_flow.py` 覆盖单节点链式 HTTP 样本，但没有断言预检先于数据源获取和 TCP 优选。
- setup 测试没有断言 `CHAIN_PROXY_TEST_ENABLED=true` 时，真实连接预检必须先于计划任务或 cron 注册。

### 1.4 已确认内核能力边界

- 本机 sing-box 1.13.14 对最小 VLESS 配置执行检查时明确返回 `unknown transport type: xhttp`；继续沿用 sing-box 无法满足 XHTTP。
- Xray 官方传输契约包含 VLESS 的 WebSocket、gRPC 与 XHTTP，XHTTP 可与 TLS 组合；CfGfwAX 当前 mixed 输出为 `type=xhttp&mode=stream-one`。
- 用户已明确决定：链式代理全部改用 Xray，不保留 WS/gRPC 走 sing-box、XHTTP 走 Xray 的双内核分支。
- 参考：`https://xtls.github.io/en/config/transports/`、`https://github.com/XTLS/Xray-core/discussions/4113`。

### 1.5 当前本机证据边界

- 项目 `.venv` 和旧 `.sing-box/sing-box.exe` 当前存在；项目内 Xray 运行时尚不存在。
- 当前本机 `config.json` 的链式开关为 `false`，订阅 URL 已配置但未输出或记录。
- 现有链式单元测试 16/16 通过。这只证明变更前的静态/模拟契约，不证明 Xray、当前真实订阅、真实 SOCKS5 出口或 Windows/Linux 全新 setup。

## 2. 目标

面向只会运行 `setup.ps1` 或 `setup.sh` 的普通用户，提供以下保证：

1. setup 能在项目目录内创建或修复 Python 虚拟环境，并准备可用的项目内 Xray 运行时。
2. 当且仅当 `CHAIN_PROXY_TEST_ENABLED` 为 JSON 布尔值 `true` 时，setup 与 `main.py` 都必须先验证 CfGfwAX 订阅、Xray 配置和真实代理连接。
3. 前置连接测试通过后，才允许抓取候选 IP、执行 TCP/HTTP/带宽优选、写结果、更新 DNS、同步 GitHub或注册定时任务。
4. 失败必须明确归因到环境、订阅、核心配置或真实链路，不得在优选结束后用笼统的“测试工具有误”收尾。
5. 全程 fail closed，不因链式代理失败而降级成直连测速，也不覆盖已有输出或触发外部发布副作用。

## 3. 用户场景

### 3.1 已有配置的普通用户

用户在项目根目录运行 setup。setup 自动完成项目虚拟环境、依赖、Xray 和链式连接预检；全部通过后才配置调度，并可按现有交互选择是否立即执行完整优选。

### 3.2 首次运行且缺少 `config.json`

setup 从 `config/config.example.json` 创建根目录 `config.json`，停止并要求用户填写订阅 URL 等私密配置。用户保存后只需再次运行同一个 setup 入口。setup 不应猜测、生成、回显或另存订阅 Token。

这仍是必要的两阶段流程：setup 可以自修复运行环境，但不能凭空获得用户的私密订阅。

### 3.3 手动运行 `main.py`

若链式代理关闭，保持当前直连流程。若链式代理开启，`main.py` 在任何候选源请求或 TCP 探测前执行同一共享预检。Python 依赖缺失时给出“重新运行 setup”的可操作提示；`main.py` 不自行执行 pip 或安装系统 Python。

## 4. 已确定决策与待批准假设

1. **已确定：** 链式代理全部使用 Xray；WS、gRPC、XHTTP 不再分流到 sing-box。
2. “连接测试”定义为：使用 CfGfwAX mixed/base64 订阅中实际存在、且通过契约验证的 VLESS WS/gRPC/XHTTP + TLS 节点启动 Xray，并通过本地 SOCKS 入站对独立轻量 HTTPS 2xx 目标发起最小请求；不得复用 CfGfwAX 明确禁止的测速域名，仅执行 Xray 配置检查或监听端口探测不算通过。
3. XHTTP 首版只接受 CfGfwAX 当前发布的 `mode=stream-one`；缺失、冲突或其他 mode 均 fail closed。`/video/<密文>` 可兼容 Xray stream-one 自动补出的单个末尾 `/`，但不得宽松改写路径中其他字节。
4. 预检最多尝试订阅中前三个去重后的“传输模板 + 端点”探针对；CfGfwAX 为每个节点随机生成的 CDN `host`/`sni` 必须与该节点端点保持绑定。任一探针对获得 HTTP 2xx 即通过。每个探针对使用现有连接/HTTP 超时，避免预检无限拖延。
5. 用户订阅契约以当前项目文档规定的 CfGfwAX mixed/base64 VLESS 为准。不要求 subconverter 生成的核心专用 JSON，也不改写用户 URL。
6. Xray 必须使用项目审核并固定的版本、官方资产和项目内预期 SHA-256 清单；不得在每次 setup 时动态信任 `releases/latest`。具体版本只可选择同时通过 WS、gRPC、XHTTP 配置契约和真实连接验收的发布版。
7. 缺失或损坏的项目 `.venv` 属于 setup 可自动修复范围；显式配置或 PATH 指向的外部核心永不被删除或覆盖。

## 5. 范围

### 5.1 包含

- `core/chain_proxy.py`：CfGfwAX 订阅端点保留、Xray 配置生成、核心发现/验证/项目内安装、真实连接预检、脱敏错误；删除运行路径中的 sing-box 专用实现。
- `core/app.py`：严格配置校验、启动顺序、预检结果复用、失败副作用门。
- `setup.ps1` 与 `setup.sh`：项目 `.venv` 自修复、共享链式预检、调度注册门。
- `config/config.example.json`：链式模式和自修复说明。
- `README.md`：简体中文、繁体中文、英文同步说明。
- `work-products/tests/`：最小 RED/GREEN 回归、跨平台 setup 契约和 CfGfwAX 消费契约。
- 必要时同步 `scripts/update_fork.ps1` 与 `scripts/update_fork.sh` 中受 setup 行为影响的兼容契约，但不改变更新策略。

### 5.2 不包含

- 改变 CDN 候选来源、TCP 评分、链式评分权重、候选数量或最终选择配额。
- 支持 Trojan、任意第三方订阅格式、非全局 SOCKS5 或 XHTTP 的非 `stream-one` 模式。
- 自动部署 CfGfwAX、发布 CGAX-Pages 或修改 Cloudflare 生产环境。
- 管理 Xray 系统服务、TUN 模式或全局系统代理。
- 自动轮换订阅 Token、改变 Token 存储位置或把秘密移出 `config.json`。
- 自动升级一个已经通过兼容性和连接预检的 Xray。

## 6. 行为契约

### 6.1 配置边界

- `CHAIN_PROXY_TEST_ENABLED` 必须是 JSON 布尔值。字符串 `"true"`、数字 `1` 或其他真值均视为配置错误。
- 开关为 `false` 时，不请求链式订阅、不下载 Xray、不执行链式连接预检，现有直连行为保持不变。
- 开关为 `true` 时，空白订阅 URL、非 HTTPS URL、带 URL 用户名/密码、响应超过 2 MiB或请求失败都必须在优选前失败。
- `CHAIN_PROXY_PREFLIGHT_URL` 必须是无认证信息的 HTTPS URL，默认使用独立的 Cloudflare trace 2xx 目标，不得隐式复用带宽测速地址。
- 不在日志、异常、通知、测试夹具或命令行中输出完整订阅 URL、Token、完整 VLESS URI、UUID、`/video/` 密文或 SOCKS5 凭据。

### 6.2 CfGfwAX 订阅契约

解析器必须：

1. 接受明文 mixed VLESS 行或整份 base64 编码的 mixed 内容；
2. 保留每个节点自身的 `server_name`/`host` 和 `server:port`；节点 CDN 域名可以不同于订阅 URL 域名，但不得与其他节点的端点交叉组合；
3. 要求 VLESS + TLS，并只接受 WS、gRPC 或 XHTTP；
4. WS 要求 `host`、`path`；gRPC 要求 `authority`/兼容 `host`、`serviceName`；XHTTP 要求 `host`、`path` 和唯一的 `mode=stream-one`；
5. 三种传输都必须使用 CfGfwAX `/video/<密文>` 链式路径。XHTTP 解析时只允许移除一个兼容性末尾 `/` 后重试解码，不能修改中间路径、查询参数或密文字节；
6. 解码 `/video/` 后要求代理类型为 `socks5`、`global=true`，并验证主机与端口存在；
7. 保留 `security`、`sni`、`host`/`authority`、`path`/`serviceName`、`mode`、`ech`、`fragment`、`fp`、`allowInsecure` 和 `flow` 的有效语义；任何不能无损映射到固定 Xray 版本的已设置字段都必须在网络测试前拒绝，不能静默丢弃；
8. 保留最多三个去重后的“完整逻辑模板 + 实际 `server:port`”探针对；完全相同的探针对去重，不拆分或重组；
9. 无可用探针、非法参数或不支持传输必须 fail closed。

解析结果需要同时提供：

- 有界、去重且模板与端点保持绑定的预检探针对；
- 不含秘密的订阅来源标识，仅用于诊断。

### 6.3 Xray 发现、迁移与项目内修复

`CHAIN_PROXY_CORE_PATH` 保留为兼容配置键，但其值必须指向 Xray。共享解析顺序：

1. 有效、身份正确且版本兼容的 `CHAIN_PROXY_CORE_PATH`；
2. 项目 `.xray/xray.exe` 或 `.xray/xray`；
3. PATH 中有效且兼容的 `xray`；
4. 都不可用时，安装审核固定版本到项目 `.xray/`。

兼容性不能仅以“文件存在”判断。必须验证：

- 可执行文件确为 Xray，而非 sing-box 或同名伪装文件；
- `xray version` 与项目固定版本契约一致；
- 能对 WS、gRPC、XHTTP 生成配置执行固定版本支持的只读配置检查；
- 能启动本地 SOCKS 入站并完成真实 HTTPS 代理请求。

修复规则：

- 缺失、零字节、不可执行、身份错误或版本不兼容的项目本地 Xray，可由 setup 使用 `.xray/` 内临时文件重新安装并原子替换。
- 外部显式路径或 PATH 核心无效时，不修改外部文件；转而安装和验证项目本地 Xray。
- 下载只允许 XTLS/Xray-core 官方 HTTPS 发布地址、固定版本、固定资产名和项目内预期 SHA-256；限制下载大小，只提取固定清单中的必要文件。
- 新 Xray 完全验证前保留旧 Xray；失败时清理临时文件并保持旧文件不变。
- 旧 `.sing-box/` 仅作为回滚遗留，不再执行也不由 setup 自动删除；若 `CHAIN_PROXY_CORE_PATH` 指向 sing-box，setup 必须安装项目内 Xray 并原子迁移该字段。
- `CHAIN_PROXY_CORE_PATH` 需要修正时，只能原子更新该字段，并保留 `config.json` 的其他字段和 UTF-8 内容；项目内路径写成可移动的相对路径。

### 6.4 Xray 配置映射

- 每个候选端点使用独立本地 SOCKS 入站、VLESS 出站和路由规则，避免候选之间串流。
- 候选替换只允许改变 VLESS 服务地址与端口；UUID、SNI、Host/Authority、路径、传输、安全参数和链式 SOCKS5 密文保持模板语义一致。
- WS、gRPC、XHTTP 分别映射到所固定 Xray 版本对应的 WebSocket、gRPC、XHTTP 出站结构；XHTTP 必须显式设置 `stream-one`，不得启用与 XHTTP 冲突的通用 mux。
- TLS 必须映射证书校验、SNI、`fp` 指纹与 `ech` 的完整查询值；不能把 ECH 降级成普通 DNS。
- `fragment` 必须保留 CfGfwAX 值的次数、长度、间隔与 TLS ClientHello 语义，并映射到 Xray 支持的分片出站链；不得像旧实现一样只折叠成布尔值。
- 生成器必须对 WS、gRPC、XHTTP 都通过固定 Xray 版本的配置检查；任何字段不兼容必须在启动前 fail closed。

### 6.5 Python 项目环境自修复

setup 必须只管理项目根目录 `.venv`：

- 不存在：使用受支持的 bootstrap Python 创建；
- 解释器无法启动、版本不足、pip 不可用或核心依赖无法导入：确认目标是项目内非链接目录后重建或修复；
- 安装 `requirements.txt` 和现有 Brotli 运行依赖后，实际执行导入验证；`aiohttp` 的安全下限为 `3.14.3`；
- 不激活虚拟环境，不依赖用户当前 shell 状态；所有后续命令使用项目 `.venv` 的绝对解释器路径；
- 不删除、覆盖或修改项目外虚拟环境。

若系统没有可用 Python，保留现有平台安装能力；系统安装失败时给出明确恢复命令。系统 Python、Git、curl 和包管理器不属于项目目录内可原子回滚的资产。

### 6.6 前置连接状态机

链式模式的唯一允许顺序：

```text
读取并严格验证配置
  -> 获取并解析 CfGfwAX 订阅
  -> 发现/迁移/修复并验证 Xray
  -> 用订阅实际端点启动临时运行时
  -> 通过 SOCKS 执行最小 HTTPS 连接测试
  -> 预检通过
  -> 获取候选源/校准/过滤
  -> TCP 候选优选
  -> 候选全链路 HTTP 与带宽测试
  -> 排名与选择
  -> 写本地输出
  -> DNS/GitHub 副作用
```

预检必须返回可复用的模板与核心路径，后续候选链路测试不得再次获取订阅或重新决定核心。

### 6.7 setup 调度门

- setup 在准备 `.venv` 和依赖后读取链式开关。
- 链式开启：共享真实连接预检必须先于 Windows 计划任务或 Linux cron 的创建、更新或启用。
- 预检失败：setup 返回非零，不注册新任务；属于本项目且会运行当前失败配置的已有任务必须保持禁用/移除状态，并打印修复后重新运行 setup 的方法。
- 预检成功：才继续配置调度。
- 链式关闭：按现有调度流程执行，不引入 Xray 开销。
- 重复运行必须幂等；有效 `.venv`、依赖和核心不得重复重建或下载。

### 6.8 错误分类与副作用

错误至少分为：

- `ENVIRONMENT_ERROR`：Python、依赖、curl 或安全文件操作失败；
- `SUBSCRIPTION_ERROR`：URL、请求、大小、格式、模板或 `/video/` 契约失败；
- `CORE_ERROR`：Xray 获取、摘要、身份、版本、配置检查或启动失败；
- `CONNECTIVITY_ERROR`：运行时已启动，但所有预检端点的真实 HTTPS 请求均失败。

用户消息应包含分类、当前阶段、脱敏原因和下一步操作。任何失败都不得：

- 继续候选抓取或 TCP 优选；
- 覆盖 `OUTPUT_FILE`；
- 更新 Cloudflare DNS；
- 同步 GitHub；
- 静默降级直连；
- 发送包含秘密的通知。

## 7. 技术与代码约束

- Python 3.9+，沿用 `unittest`、四空格和 `snake_case`。
- 不新增第三方 Python 依赖；优先复用 `requests`、标准库和现有 curl 测量逻辑。
- Windows 与 Linux setup 必须调用同一个 Python 预检入口，不复制订阅解析、下载或连接判断逻辑。
- 预检入口属于内部模块接口；根 `main.py`、`setup.ps1`、`setup.sh` 仍是公开用户入口。
- 所有新增正式测试位于 `work-products/tests/test_*.py`。
- 测试从其最终位置使用仓库相对关系定位源码，例如 `Path(__file__).resolve().parents[2]`；不得写入机器专属绝对路径。
- setup、配置模板和 README 的三种语言是同一验收边界。

## 8. 测试策略

### 8.1 必须先出现的 RED 回归

1. `CHAIN_PROXY_TEST_ENABLED=true` 时，若预检失败，`fetch_additional_source`、`calibrate_regions`、`test_node`、结果写入、DNS 和 GitHub 同步均未调用。
2. 调用记录证明预检成功发生在第一个候选源请求之前；后续候选运行时复用同一模板和核心路径。
3. Xray 配置检查成功但 SOCKS 真实 HTTPS 请求失败时，分类为 `CONNECTIVITY_ERROR`，而不是预检成功。
4. mixed 明文与 base64 订阅都保留实际端点；每个逻辑模板只与原节点端点组成探针对，完全相同的探针对可去重，不跨节点归并或拒绝合法多模板。
5. XHTTP `stream-one` 与带单个末尾 `/` 的 `/video/` 路径成功解析；缺失/其他 mode、破坏密文的路径和多个尾斜杠被拒绝。
6. WS、gRPC、XHTTP 分别生成可通过固定 Xray 配置检查的出站；ECH、分片、指纹和传输路径未被丢弃。
7. `CHAIN_PROXY_TEST_ENABLED` 的字符串或数字值在任何网络请求前被拒绝。
8. Windows/Linux setup 的契约测试证明链式预检先于调度注册；预检失败不留下可运行的新任务。
9. 缺失或损坏的项目 `.venv`、项目 `.xray` 能在安全边界内修复；配置指向旧 sing-box 时自动迁移，外部核心和旧 `.sing-box` 不会被修改。

### 8.2 成功、失败与安全覆盖

- 成功：WS、gRPC、XHTTP `stream-one`、ECH、TLS 分片、指纹、前三个端点中后续端点成功。
- 失败：订阅超限、非 HTTPS、非全局 SOCKS5、不支持的 XHTTP mode、字段无法无损映射、无探针、摘要错误、核心身份/版本错误、配置检查失败、监听失败、全部端点连接失败。
- 安全：异常、stdout/stderr、通知和测试快照不包含 Token、UUID、完整 URI、`/video/` 或代理凭据。
- 幂等：第二次 setup 不重建有效 `.venv`、不重新下载有效 Xray、不产生无意义配置改写。
- 兼容：链式关闭的既有测量流程与全部正式测试保持通过；运行路径中不存在 sing-box 调用。

### 8.3 验证命令

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_measurement_flow.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -v
$files = @('setup.ps1', 'scripts/git_sync.ps1', 'scripts/update_fork.ps1')
foreach ($file in $files) { [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8)) }
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh
git diff --check
```

跨仓库消费者契约：

```powershell
node --test ..\CfGfwAX\work-products\tests\chain_proxy.test.mjs
```

本次用户明确接受 Windows/Linux 理论跨平台证据，因此空环境 setup、真实 Linux 与完整优选结果质量不作为本次修复放行前提，仍必须标为未执行。用户真实 CfGfwAX XHTTP `stream-one` 订阅与 SOCKS5 出口应在可用时单独验证；静态/模拟证据不得冒充真实环境证明。

## 9. 可测量验收标准

1. 链式开启且订阅、核心或真实连接预检失败时，候选源请求数和 TCP 探测数均为 0。
2. Xray 配置检查成功但真实 HTTPS 代理请求失败时，进程非零退出并报告 `CONNECTIVITY_ERROR`。
3. 预检最多尝试三个去重的 CfGfwAX 实际端点，任一端点返回 HTTP 2xx 即通过；全部失败则停止。
4. 预检成功后完整链式优选只获取一次订阅，并复用已验证模板和核心路径。
5. 链式关闭时不获取订阅、不解析或下载 Xray，既有输出行为不变。
6. setup 可从缺失 `.venv` 的已配置项目恢复到依赖可导入状态；损坏项目环境可安全重建，且不触碰项目外环境。
7. 无可用 Xray 时，setup 将固定且摘要匹配的官方资产安装到 `.xray/`；摘要、身份、版本或配置验证失败时不替换旧 Xray。
8. 配置仍指向 sing-box 时，setup 自动迁移到项目内 Xray，且旧 `.sing-box/` 与任何外部核心保持不变。
9. Windows/Linux setup 只在链式真实连接预检成功后注册调度；失败退出码非零且没有新调度副作用。
10. 所有失败路径均保持既有输出文件、DNS 与 GitHub 远端不变。
11. CfGfwAX mixed/base64 的 WS、gRPC、XHTTP `stream-one` 消费契约和 BestCfCdn 正式测试全部通过；本次真实订阅提供的 XHTTP 类型另有真实 SOCKS HTTPS 证据，WS/gRPC 保持理论契约证据。
12. README 简中、繁中、英文同时说明 Xray 单内核、XHTTP、前置真实连接测试、setup 项目内自修复、失败不降级和首次配置边界。
13. 秘密扫描证明代码、测试、规格和日志夹具不含真实订阅、Token、UUID、完整节点 URI 或代理凭据。

## 10. 风险与回滚

- 前置真实连接增加一次小请求和最多三个端点的有限重试；收益是避免在基础链路已坏时浪费完整优选时间。
- 订阅本身所有端点短时不可用可能造成 fail closed；通过最多三个端点和现有超时控制误判，不允许绕过为直连。
- Xray 版本选择会影响 XHTTP 与配置 schema；必须固定经过三传输配置检查和真实 XHTTP 验收的版本，不能直接追随 latest。
- `.venv` 和 `.xray` 修复涉及本地运行资产；实现必须先验证目标位于项目内且不是链接，再使用临时路径和原子替换。
- sing-box 到 Xray 是本地运行时迁移；旧 `.sing-box/` 保留供人工回滚，但运行路径和配置不得继续引用它。
- 若新行为需要回滚，应整体回滚“Xray 单内核 + 共享预检 + setup 调度门 + 文档/测试”这一单元；不得只移除测试或保留会在预检失败后继续运行的分支。

## 11. 边界

### Always

- 先验证环境和真实链路，再进行昂贵优选或外部副作用。
- 使用项目内 `.venv` 和可验证的 `.xray` 资产；WS、gRPC、XHTTP 全部走 Xray。
- 失败关闭、错误脱敏、Windows/Linux 同步、三语文档同步。
- 生产者 CfGfwAX 契约先验证，消费者 BestCfCdn 才依赖。

### Ask first

- 改变 CfGfwAX mixed/base64 订阅格式或加入核心专用 JSON。
- 支持 XHTTP 的新 mode、新操作系统/架构或新的链式代理协议。
- 改变评分、候选数量、调度频率、DNS/GitHub 发布策略。
- 新增依赖或自动升级已验证可用的 Xray。

### Never

- 提交或打印秘密和真实节点 URI。
- 使用未固定版本、未验证 SHA-256 或非 XTLS/Xray-core 官方来源的核心。
- 执行、下载或自动删除旧 sing-box，或修改项目外环境/核心文件。
- 丢弃 CfGfwAX 已设置的 ECH、分片、指纹、传输 mode 或路径语义后继续测试。
- 预检失败后继续直连、写结果、更新 DNS、同步 GitHub或启用调度。

## 12. 审批门

本规格已于 2026-08-06 获用户批准；同日用户授权本次 `@debug` 修复与同步，并明确接受 Windows/Linux 理论跨平台证据。commit、push、部署及生产环境修改仍不在授权范围。
