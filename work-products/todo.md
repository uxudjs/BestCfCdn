# TODO：BestCfCdn 根目录瘦身与模块分组

## 当前状态

- [x] `work-products/SPEC.md` 已批准。
- [x] 正式测试已迁移到 `work-products/tests/`，迁移记录位于 `work-products/clean-migration.json`。
- [x] 已完成只读依赖、路径和跨仓引用审计。
- [x] 用户已授权修改 `../CfGfwAX/AGENTS.md` 与 `../CGAX-Pages/AGENTS.md` 的旧 BestCfCdn 测试命令（仅限最小规则修正）。
- [x] 用户已通过 `@uxu-code:build auto` 批准按计划连续实施；验证失败时停止。

## 第一期：建立新结构并保留兼容包装器

### Task 1：路径基座与布局测试

- [x] 新建无副作用 `core/__init__.py`。
- [x] 新建唯一根路径解析 `core/paths.py`。
- [x] 新建 `work-products/tests/test_project_layout.py`，从最终位置相对定位仓库。
- [x] 验证路径、保护目录和缓存白名单。

### Task 2A：本地状态

- [x] 移动 `local_state.py` 到 `core/local_state.py`。
- [x] 更新主程序、GitHub 同步及相关测试为绝对包导入。
- [x] 验证本地/远端输出分离与旧重叠路径兼容。

### Task 2B：评分模块

- [x] 移动 `proxy_scoring.py` 到 `core/proxy_scoring.py`。
- [x] 更新主程序及评分测试为绝对包导入。
- [x] 验证评分、排序、部分带宽和失败回退行为不变。

### Task 3：链式代理

- [x] 移动 `chain_proxy.py` 到 `core/chain_proxy.py`。
- [x] 让默认 `.sing-box/` 始终位于仓库根。
- [x] 更新主程序和 `work-products/tests/test_chain_proxy.py` 导入。
- [x] 聚焦链式代理保持 15/15 或更高且零失败。

### Task 4：GitHub 同步

- [x] 移动 `github_sync.py` 到 `core/github_sync.py`。
- [x] 移动 `git_sync.ps1/.sh` 到 `scripts/`。
- [x] 主程序和手工脚本改用 `python -m core.github_sync`。
- [x] 验证配置、输入、退出码、冲突合并与密钥脱敏。

### Task 5：调度与一期包装器

- [x] 移动调度实现到 `core/scheduled_run.py`。
- [x] 根 `scheduled_run.py` 仅保留一期委托包装器。
- [x] 验证 90/180 分钟网格、30 分钟唤醒、禁用和锁行为。

### Task 6：主程序薄入口

- [x] 将原实现整体迁入 `core/app.py`。
- [x] 根 `main.py` 只委托 `core.app.main`。
- [x] 所有运行时路径仍落在仓库根。
- [x] 更新 `test_measurement_flow.py` 等内部测试导入。

### Checkpoint A：Python 行为

- [x] 聚焦链式代理通过。
- [x] Windows 完整套件不低于 79 通过、6 POSIX skip，新增测试全通过。
- [x] 所有包模块可导入，无 `sys.path` 注入。
- [x] 失败即停止，不进入平台脚本迁移。

### Task 7：Windows setup/updater

- [x] updater 实现迁入 `scripts/update_fork.ps1`，显式解析父级仓库根。
- [x] 根 `update_fork.ps1` 仅保留一期委托包装器。
- [x] `setup.ps1` 使用新 updater、模块化调度和新模板路径。
- [x] 暂存 `config/config.example.json`，根模板仅为 Linux 切换期副本。
- [x] 验证 PowerShell BOM/解析、配置合并、备份 0/1、失败回滚和自更新。

### Task 8：Linux setup/updater

- [x] updater 实现迁入 `scripts/update_fork.sh`，显式解析父级仓库根。
- [x] 根 `update_fork.sh` 仅保留一期委托包装器。
- [x] `setup.sh` 使用新 updater、模块化调度和新模板路径。
- [x] 验证新代码只消费规范模板，根 `config.example.json` 作为一期兼容副本保持相同内容。
- [x] 完成理论多平台门禁：Bash/PowerShell 静态解析、跨平台源契约、嵌入 Python 编译和 Windows 完整回归。

验收覆盖（2026-08-03）：用户明确授权理论多平台检测代替真实 Linux/CI；6 项 POSIX skip 必须保留并单独披露。根模板兼容旧 updater 的快进前读取，第二期才删除。

### Checkpoint B：跨平台布局

- [x] 新鲜配置、既有配置、无更新、快进、失败回滚、备份 0/1 有理论源契约证据。
- [x] 根兼容入口、旧模板副本和 setup 重载逻辑提供旧布局升级的理论证据。
- [x] Windows 与 Linux 命令、模板和更新语义同步。
- [x] 理论门禁通过；真实 Linux/安装状态继续明确标记为未证明。

### Task 9：文档与规则

- [x] 同步 README 简体中文、繁体中文、英文三部分。
- [x] 更新本仓 `AGENTS.md` 的结构、命令和验证门禁。
- [x] 修正 `../CfGfwAX/AGENTS.md` 的旧聚焦命令（已授权；该文件在其仓库被忽略）。
- [x] 修正 `../CGAX-Pages/AGENTS.md` 的旧聚焦命令（已授权；该文件被跟踪）。
- [x] 扫描并解释所有旧路径命中：仅一期包装器、根模板兼容副本、迁移记录和明确的新路径说明保留。

### 第一期发布与升级验收

- [x] Windows 旧布局升级、setup 重载和模块化任务命令的理论契约通过。
- [x] Linux 旧布局升级、setup 重载和模块化 cron 命令的理论契约通过。
- [x] 新鲜安装与既有配置升级的理论源契约通过。
- [x] 除一期包装器、根模板兼容副本和迁移记录外，旧路径消费者为零。
- [x] 第一期理论验收完成；真实 Linux/安装未证明，第二期未授权，继续保留兼容层。

## 第二期：删除兼容包装器并最终收口

### Task 10：删除旧入口

- [x] 以独立变更集删除根 `scheduled_run.py` 包装器。
- [x] 删除根 `update_fork.ps1`、`update_fork.sh` 包装器及根模板兼容副本。
- [x] 收紧布局允许列表和陈旧路径测试。
- [x] 验证根级 Python 业务入口仅 `main.py`，平台入口仅两个 setup。

### Task 11：最终验证与缓存清理

- [x] Windows 聚焦/完整测试、模块导入、PowerShell 解析通过。
- [x] 理论多平台源契约、Bash 解析和 Windows 完整测试通过；6 项 POSIX skip 已披露。
- [x] `git diff --check` 通过，无敏感信息或非目标改动。
- [x] 记录缓存候选的相对路径、Git 跟踪和链接状态。
- [x] 仅删除规格白名单缓存；保护目录和用户文件零删除。
- [x] 删除后只读复核，不重跑会重新生成缓存的测试。

### Task 12：内部包改名

- [x] 将内部包目录统一改为 `core/`，不保留旧包或中间包别名。
- [x] 同步 Python 导入、模块命令、setup、同步脚本和测试 mock 路径。
- [x] 同步三语 README、`AGENTS.md`、规格、计划与清单引用。
- [x] 增加唯一包名和入口引用回归。

## 完成定义

- [x] `work-products/SPEC.md` 的全部可度量验收条件已满足。
- [x] 本地/static、理论多平台、安装升级、兄弟仓规则与真实外部运行证据分开陈述。
- [x] 任一未验证平台或外部状态明确标为未证明，不以本地通过替代。
- [x] 计划获批后才使用 `@uxu-code:build auto`；验证失败时按门禁停止并修正。
