# TODO：Xray 链式代理前置连通性与 setup 自修复

## 当前状态

- [x] `work-products/SPEC.md` 已批准。
- [x] 已确认当前链式检查晚于候选抓取/TCP，setup 调度也早于真实链式预检。
- [x] 已确定 WS、gRPC、XHTTP 全部使用 Xray；XHTTP 首版仅 `stream-one`。
- [x] 用户已授权本次 `@debug` 修复与规格/计划/文档同步，并明确接受 Windows/Linux 理论跨平台证据。
- [x] commit、push、部署、真实调度和生产环境修改仍未授权。

## Task 1：CfGfwAX 订阅与 XHTTP

- [x] 先补 mixed/base64、真实端点保留和 XHTTP 成功/失败 RED 回归。
- [x] 返回最多三个去重、且随机 CDN 模板与实际端点绑定的探针对和脱敏来源。
- [x] 保留 WS/gRPC/XHTTP、TLS、ECH、fragment、fp、flow 等原始有效语义。
- [x] 仅允许 XHTTP `mode=stream-one`；单尾斜杠兼容且不改写其他路径字节。
- [x] 多模板按节点与端点保持绑定；无探针、非全局 SOCKS5、无法无损映射继续 fail closed。
- [x] 验证：聚焦 22/22；完整 116 项中 110 通过、6 项 POSIX 跳过；CfGfwAX 24/24。

## Task 2A：固定 Xray 资产与发现

- [x] 先写资产选择、固定 URL、SHA、身份/版本、原子替换和外部零修改 RED 回归，再实施 GREEN。
- [x] 固定官方稳定版 `v26.3.27`，记录 Windows/Linux 支持矩阵的资产名、大小和 SHA-256。
- [x] 用户已明确正式支持矩阵仅限 Windows/Linux；矩阵覆盖完整，未改用预发布版。
- [x] 用 Xray 发现、下载、身份/版本验证和安全安装替换 sing-box 核心路径。
- [x] 发现顺序为配置路径 -> `.xray` -> PATH -> 项目内安装。
- [x] `.xray/` 纳入忽略与保护；`.sing-box/` 保留但不执行、不删除。
- [x] 实际固定资产通过大小、SHA-256、`Xray 26.3.27` 身份和空配置检查。

## Task 2B：Xray 三传输配置与运行时

- [x] 先写 WS/gRPC/XHTTP 与 TLS/ECH/fragment/fp/flow/allowInsecure 映射、配置检查和运行时清理 RED 回归，再实施 GREEN。
- [x] 为 WS、gRPC、XHTTP 生成独立 SOCKS/VLESS/路由，XHTTP 仅 `stream-one`。
- [x] 无损映射 TLS/ECH/fragment/fp/flow；`allowInsecure=true` 在网络前 fail closed，不降级或静默忽略。
- [x] 实际固定二进制对三类代表配置执行只读检查，退出码均为 0。
- [x] RED/GREEN 修正 `streamSettings.method` 为 Xray 26.3.27 官方 `network` 字段，防止三类传输静默退化为裸 TCP+TLS。
- [x] 运行时失败脱敏，退出后不遗留进程、临时配置或秘密日志。
- [x] 聚焦 28/28；完整 123 项通过（含 6 项 POSIX 环境跳过）。
## Task 3：共享真实预检与配置迁移

- [x] 先写真实 SOCKS HTTPS 失败、三端点、单次订阅、严格布尔值、配置迁移和幂等 RED 回归，再实施 GREEN。
- [x] 提供 setup/main 共用的 Python API 与内部模块 CLI，只传 `config.json` 路径。
- [x] 严格拒绝字符串/数字形式的 `CHAIN_PROXY_TEST_ENABLED`；`false` 零 Xray/订阅开销。
- [x] 严格验证订阅 HTTPS、安全 URL、2 MiB 上限和请求错误。
- [x] 最多三个真实探针对经 SOCKS 请求独立轻量 HTTPS 目标，HTTP 2xx 才通过；不复用 CfGfwAX 禁止的测速域名。
- [x] 输出可复用的模板和核心路径；后续不得再次取订阅或选核心。
- [x] 实现四类错误与脱敏恢复建议。
- [x] 仅在新 Xray 完整验证后原子迁移非空旧 sing-box/无效核心字段；其他配置不变。
- [x] 覆盖失败不改配置、不碰旧核心和重复运行幂等。

## Task 4：main 前置失败门

- [x] 先写预检失败时候选/TCP/输出/DNS/GitHub 调用数均为 0 的 RED 测试。
- [x] 在第一个候选源请求之前调用共享预检。
- [x] 移除候选形成后的重复订阅/核心检查。
- [x] 候选链式运行时复用同一预检结果。
- [x] 链式关闭流程保持不变。
- [x] 通过 `test_measurement_flow.py` 和 `test_chain_proxy.py`。

## Checkpoint A：Python 行为

- [x] Task 1-4 聚焦测试全部通过。
- [x] 实际 Xray 的 WS/gRPC/XHTTP 配置检查通过。
- [x] 预检失败时候选请求/TCP 为 0；成功时订阅只取一次。
- [x] 本地完整回归 133 项通过（含 6 项 POSIX 环境跳过），可进入 setup 改造。
- [x] 本机链式关闭态 CLI 返回 `CHAIN_PREFLIGHT_DISABLED`，未请求订阅或 Xray。

## Task 5：Windows setup

- [x] 先写 `.venv` 缺失/损坏/有效、reparse point、依赖导入和预检顺序 RED 回归，再实施 GREEN。
- [x] `.venv` 缺失时由 bootstrap Python 在项目准确路径创建；不使用或修改项目外环境。
- [x] 验证 `.venv` 解释器、版本、pip 和依赖导入，而非只看文件存在。
- [x] 安全修复项目内非 reparse-point 损坏环境，失败恢复备份；项目外零修改。
- [x] 不激活环境；后续使用 `.venv` 绝对解释器，修复 pip、安装 requirements/Brotli 并实际导入。
- [x] 依赖就绪后先移除本项目旧任务，再调用共享预检，成功后才注册。
- [x] 预检失败非零退出且不留下可运行任务。
- [x] 保持首次配置两阶段、管理员、自更新和 SYSTEM 调度既有契约。
- [x] 通过平台测试与 PowerShell 5.1 解析。

## Task 6：Linux setup

- [x] 先写 `.venv` 缺失/损坏/有效、符号链接、目标用户所有权和预检顺序 RED 回归，再实施 GREEN。
- [x] `.venv` 缺失时由目标用户在项目准确路径创建；损坏时按备份/恢复契约修复。
- [x] 拒绝符号链接/项目外环境；以目标用户创建项目资产。
- [x] 不激活环境；后续使用 `.venv/bin/python` 绝对路径，修复 pip、安装 requirements/Brotli 并实际导入。
- [x] 精确移除本项目 cron、保留其他条目；共享预检成功后才注册。
- [x] 预检失败非零退出且本项目 cron 不存在。
- [x] 通过平台测试与 `bash -n`；POSIX 集成 6 项在 Windows 按设计跳过，未冒充真实 Linux。

## Checkpoint B：跨平台 setup

- [x] 两个平台调用同一个 Python 预检入口，无重复业务判断。
- [x] 两个平台均先移除旧调度、预检成功后才注册。
- [x] 缺失/损坏/有效 `.venv` 和链接拒绝均有静态合同证据。
- [x] static/模拟证据不冒充真实空环境安装。
- [x] 验证：23 项 setup/平台合同通过；PowerShell 语法解析通过；`bash -n` 通过；真实空环境仍属于另行授权的 Task 8B。

## Task 7：配置、三语文档与遗留收口

- [x] 更新 `config/config.example.json` 的 Xray、XHTTP、严格布尔值与自修复说明，并保持根目录旧更新器字节桥一致。
- [x] 同步 README 简中、繁中、英文：Xray、三传输、前置实连、项目内修复、失败关闭、首次私密配置。
- [x] 更新 `AGENTS.md` 过时的 sing-box/XHTTP 运行约束。
- [x] 扫描并清除业务运行路径中的 sing-box 与动态 `latest`；只保留回滚/禁止语境。
- [x] 不改评分、候选、调度频率、发布策略或更新策略。
- [x] 验证：Task 7 RED/GREEN 合同 2/2、平台合同 11/11 通过；遗留引用扫描符合回滚/禁止边界。

## Task 8A：本地完整门

- [x] `test_chain_proxy.py` 通过（41/41）。
- [x] `test_measurement_flow.py` 通过（25/25）。
- [x] `unittest discover -s work-products/tests -v` 通过（共执行 145 项：139 通过、6 项 POSIX 环境跳过）。
- [x] PowerShell 与 Bash 语法门通过。
- [x] CfGfwAX `chain_proxy.test.mjs` 消费者契约通过（24/24；受限沙箱 `spawn EPERM` 后按边界在受限外重跑）。
- [x] `git diff --check` 与秘密扫描通过。
- [x] 脱敏扫描：高置信凭据/私钥为 0；其余命中仅为动态 ipinfo Token 拼接与 `proxy.example.com`/VLESS 测试夹具；模板私密字段为空。
- [x] `aiohttp` 安全下限提升到 `3.14.3`；当前环境 `pip check` 通过，`requests`、`aiohttp`、Brotli 的精确版本 OSV 查询均为 0。

## Task 8B：理论跨平台门与可用真实链路

- [x] Windows/Linux 共享入口、平台矩阵、PowerShell/Bash 语法和 setup 契约作为本次理论跨平台门；未冒充真实 Linux 或空环境 setup。
- [ ] Windows 一次性空环境 setup：本次不要求，明确未执行。
- [ ] Linux/WSL/VM 一次性空环境 setup：本次不要求，明确未执行。
- [x] WS/gRPC/XHTTP `stream-one` 静态配置和消费者契约通过；真实 WS/gRPC 未执行。
- [x] 用户真实 CfGfwAX XHTTP `stream-one` 订阅与 SOCKS5 出口完成前置 HTTPS 2xx 测试（首端点通过）。
- [ ] 故意失败证明候选/TCP/输出/发布为零副作用且调度未启用。
- [ ] 成功完成一次真实链式优选，脱敏记录平台、Xray 版本、传输与结果。
- [ ] 独立将完整优选结果质量记录为通过/失败/未执行，不以进程成功代替质量证明。
- [x] Windows/Linux 理论、真实 XHTTP、仅理论 WS/gRPC、空环境和结果质量的证据层级分开陈述。

## 完成与授权

- [x] 本次批准放行边界内的全部可测量验收有证据；豁免项保持未执行。
- [x] WS/gRPC/XHTTP 只有 Xray 路径，XHTTP 仅 `stream-one`。
- [x] 链式失败始终在候选、TCP、写入、发布和调度前停止。
- [x] 用户已批准本次 `@debug` 修复与同步；未扩大到 commit、push 或部署。
- [x] 任何固定版本/字段映射/平台矩阵偏差先回到规格审批，不静默变更。
