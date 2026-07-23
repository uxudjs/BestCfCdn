# Implementation Plan: 链式代理自动适配 sing-box

## Overview

按已确认规格，将 sing-box 的安全安装与配置、CfGfwAX 原生 sing-box 订阅解析、主流程前置预检和跨平台 setup 接入拆成五个可独立验证的小任务。所有共享行为集中在现有 `chain_proxy.py`，不新增依赖或额外服务。

## Dependency Graph

```text
Task 1 安全发现、安装与配置写入
    └── Task 3 主流程前置预检
    └── Task 4 Windows/Linux setup 接入

Task 2 sing-box 订阅自动适配与解析
    └── Task 3 主流程前置预检

Task 3 + Task 4
    └── Task 5 配置示例与文档收口
```

Task 1 与 Task 2 逻辑上可独立，但都会修改 `chain_proxy.py` 和同一测试文件，因此顺序执行以避免冲突。其余任务依赖共享接口稳定后再开始。

## Architecture Decisions

- 复用 `chain_proxy.py`：路径发现、官方资产下载、摘要验证、原子写配置和运行前检查只实现一次；setup 脚本只调用它。
- 使用 Python 标准库处理 GitHub JSON、SHA-256、ZIP/TAR 和原子替换，不新增依赖。
- 项目本地核心固定在 `.runtime/sing-box/`，只安装缺失核心，不实现自动升级。
- 订阅请求副本强制 `target=singbox`，配置中的原 URL 不变；解析器继续接受旧 mixed/base64。
- `main.py` 在读取外部节点源前取得并验证模板与核心，后续测速直接复用结果。
- 下载和配置写入 fail closed：摘要、归档成员、版本检查或写入失败时不替换现有可用文件。

## Task List

### Phase 1: Shared foundations

- [x] Task 1: 安全发现、安装 sing-box 并原子写入配置
- [x] Task 2: 自动请求并解析 CfGfwAX sing-box 订阅

### Checkpoint: Shared foundations

- [x] `python -m unittest tests.test_chain_proxy -v` 通过
- [x] 无新第三方依赖，下载失败不会破坏核心或配置
- [x] 旧 mixed/base64 链式订阅行为保持通过

### Phase 2: Runtime integration

- [x] Task 3: 将 sing-box 与订阅预检移动到主流程最前
- [x] Task 4: 接入 Windows/Linux setup 自动准备核心

### Checkpoint: Runtime integration

- [x] `python -m unittest tests.test_chain_proxy tests.test_measurement_flow -v` 通过
- [x] `python -m unittest tests.test_setup_update_integration tests.test_windows_updater -v` 通过
- [x] 链式关闭时不查找、不下载、不改写核心路径
- [x] 链式开启且预检失败时没有启动节点抓取或测速

### Phase 3: Documentation and release check

- [x] Task 5: 同步配置示例、README 与忽略规则

### Checkpoint: Implementation complete

- [x] `python -m unittest discover -s tests -v` 全部通过
- [ ] PowerShell 与 Bash setup 语法/集成回归通过
- [ ] Windows 和 Linux 各完成一次真实 setup 手工检查
- [ ] 使用真实 CfGfwAX 订阅完成一次链式预检与测速
- [ ] 规格中的十项 Success Criteria 全部满足

### Phase 4: Real platform acceptance

- [ ] Task 6: 冻结可复现的验证候选提交
- [ ] Task 7: 在隔离 Windows 环境验收真实 setup
- [ ] Task 8: 在隔离 Linux 环境验收真实 setup

### Checkpoint: Platform acceptance

- [ ] 两个平台均验证首次安装、配置写入、版本检查和二次运行幂等
- [ ] 每个平台的完整测试均通过；所有 setup 集成测试至少在一个支持平台实际执行
- [ ] 验收记录不包含 Token、UUID、本机用户路径或完整订阅 URL

### Phase 5: Real chain and security evidence

- [ ] Task 9: 使用真实 CfGfwAX 订阅完成无副作用链式冒烟测试
- [ ] Task 10: 完成依赖漏洞、秘密与官方发布元数据审计

### Checkpoint: Release evidence

- [ ] 真实订阅预检、sing-box 启动和至少一个候选节点的链式 HTTP 测试成功
- [ ] Cloudflare DNS、GitHub 同步、通知和定时任务均未被测试触发
- [ ] 没有未处置的可达高危/严重漏洞，发布资产仍满足官方 stable + SHA-256 合同

### Phase 6: Immutable release candidate

- [ ] Task 11: 汇总十项成功标准、创建最终证据提交并重新执行 ship gate

### Checkpoint: GO

- [ ] 十项 Success Criteria 均有命令或人工验收证据
- [ ] 预期变更已提交，工作区不含 `config.json`、`.runtime/`、`.codegraph/` 或秘密
- [ ] `@ship` 返回 GO

## Verification Checkpoints

1. Task 1 后先审计下载信任边界：仅官方 stable release、匹配平台资产、SHA-256、受限解压、原子替换。
2. Task 2 后运行当前七个链式回归，确认兼容路径未被删除。
3. Task 3 后用 mock 证明预检调用顺序，不依赖耗时真实网络测试。
4. Task 4 后分别验证链式开/关、已发现/需下载四条 setup 路径。
5. Task 5 后执行全量测试和两个真实平台的最小手工验收。
6. Task 6 先冻结唯一验证 commit；Task 7 与 Task 8 可并行，但必须检出该同一 commit 并在可丢弃环境中运行。
7. Task 9 不调用完整 `main()`；复用 `preflight_chain_proxy()`、`SingBoxRuntime` 和链式 HTTP 检测函数，隔离所有外部写操作。
8. Task 10 未通过时不创建最终证据提交；Task 11 只汇总已存在的证据，不用勾选代替验证。

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GitHub 发布资产命名或 API 字段变化 | 高 | 只接受精确平台资产和 `sha256:` digest；不匹配即明确失败，不猜测下载 |
| 恶意或损坏归档覆盖项目文件 | 高 | 只读取预期的单个成员到临时目录，校验后原子替换 |
| config 写入中断或格式异常 | 高 | 先完整解析、同目录临时写入、刷新后 `os.replace`；失败保留原文件 |
| sing-box JSON 含外部/选择器节点 | 中 | 仅接受匹配订阅域名、VLESS + WS + TLS + `/video/` 的唯一逻辑模板 |
| 前置检查和运行时再次解析导致漂移 | 中 | 前置阶段只取一次模板与核心路径，运行阶段复用同一对象 |
| setup 的 PowerShell/Bash 行为分叉 | 中 | 两个脚本调用同一个 Python 入口，只保留平台壳层 |
| 当前分支落后 `origin/main` 55 个提交 | 中 | 不在本任务自动同步；实现前后保持最小文件范围，合并上游时单独处理冲突 |
| 真实 setup 修改源码、依赖或定时任务 | 高 | 仅在一次性 Windows/Linux VM 或 CI runner 中执行，并预先关闭定时任务 |
| 真实订阅验收误写 DNS/GitHub 或泄露 Token | 高 | 不调用完整 `main()`；关闭通知与同步，仅调用现有只读预检和链式测量边界，保存脱敏摘要 |
| 未固定依赖导致审计结果不可复现 | 中 | 对两个验收环境先记录精确安装版本，再用隔离审计工具检查该版本集合；发现可达高危项即保持 NO-GO |
| 未跟踪 `.codegraph/` 或本机运行文件被误提交 | 中 | 发布前显式按文件清单暂存，并用 `git diff --cached --name-only` 复核 |

## Open Questions

- Task 9 需要用户把真实 CfGfwAX 订阅 URL/Token 写入被忽略的本地 `config.json`；秘密不得粘贴到计划、日志或提交中。
- Task 6 的验证候选提交需要用户显式调用 `@commit`；规划阶段不会自动提交。
- 发布版本号与 tag 在 Task 11 的 GO 证据齐全后决定，不影响前置验收任务。
