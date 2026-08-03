# 实施计划：BestCfCdn 根目录瘦身与模块分组

## 规划结论

按 `work-products/SPEC.md` 的推荐方向 A 分两期迁移：第一期建立 `core/`、`scripts/` 和 `config/`，保留仅含委托逻辑的旧 updater/定时任务兼容包装器；第二期必须在 Windows、Linux/CI 和“旧布局升级到新布局”验收完成后，另行删除这些包装器。任何门禁失败都停止，不先删旧路径、不清理缓存。

本计划只定义工作，不修改业务代码。实施时每一任务都必须保留当前未提交改动，并把测试文件放在 `work-products/tests/`；测试从最终位置通过 `Path(__file__).resolve().parents[2]` 等相对定位方式访问仓库文件，不写入机器专用绝对路径。

## 规划依据

- 已批准规格：`work-products/SPEC.md`（2026-08-02）。其目标、范围、路径契约、安全边界、回滚与可度量验收条件足够具体，因此不需要新增规格。
- 当前迁移证据：`work-products/clean-migration.json` 已把正式测试映射到 `work-products/tests/`；这些未提交改动属于既有工作，实施不得覆盖或重新搬回。
- 当前代码审计：`main.py`、`github_sync.py`、`scheduled_run.py` 和 `chain_proxy.py` 均含根目录路径假设；setup/updater 还把脚本目录当作仓库根。
- 当前基线：聚焦链式代理 15/15；完整 Windows 套件 79 项通过、6 项 POSIX 条件跳过。该基线只用于防回归，不是 Linux、真实 GitHub、真实 sing-box 或已安装计划任务证明。
- 跨仓审计发现：`../CfGfwAX/AGENTS.md` 与 `../CGAX-Pages/AGENTS.md` 仍使用旧的 `tests.test_chain_proxy` 命令；用户已于 2026-08-02 授权 Task 9 做最小跨仓规则修正。

规划依据与跨仓规则授权均已具备；授权仅覆盖两个 `AGENTS.md` 中 BestCfCdn 聚焦测试命令的最小修正，不扩大到兄弟仓库业务代码。

## 架构与迁移决策

1. `core/paths.py` 是唯一仓库根与运行时路径解析点；包内模块不得从自身 `__file__` 推断配置、输出、日志、锁或 `.sing-box/` 位于包目录。
2. 根 `main.py` 最终只委托 `core.app.main`；原实现整体迁入 `core/app.py`，不在本次拆分业务函数。
3. 包内统一绝对包导入，不增加 `sys.path`、打包工具、第三方依赖或构建步骤。
4. 内部命令使用 `python -m core.github_sync` 与 `python -m core.scheduled_run`；根 `main.py`、`setup.ps1`、`setup.sh` 仍是公开入口。
5. updater 必须从 `scripts/` 的自身位置解析父级仓库根，并在写操作前验证 `.git/`、`main.py`、`config/config.example.json`。
6. `config/config.example.json` 是新代码的规范模板；第一期保留内容相同的根模板，兼容旧 updater 在快进前读取，第二期再与根包装器一并删除。真实 `config.json` 始终留在根目录。
7. 第一期兼容包装器仅委托新实现，不复制业务逻辑。第二期删除是独立变更集，必须满足 Task 10 的移除条件。
8. 缓存清理只在所有测试后执行；候选仅限规格白名单，拒绝符号链接、Git 跟踪项、保护目录和用户文件。

## 依赖顺序

```text
Task 1 路径基座
  ├─> Task 2A 本地状态模块
  ├─> Task 2B 评分模块
  ├─> Task 3 链式代理模块
  ├─> Task 4 GitHub 同步模块与脚本
  └─> Task 5 调度模块与兼容入口
          └─> Task 6 主程序薄入口
                  └─> Checkpoint A：Python 行为
                          └─> Task 7 Windows setup/updater
                                  └─> Task 8 Linux setup/updater
                                          └─> Checkpoint B：跨平台布局
                                                  └─> Task 9 文档与跨仓引用
                                                          └─> 第一期发布/升级验收
                                                                  └─> Task 10 删除包装器
                                                                          └─> Task 11 最终验证与缓存清理
```

Task 2A、2B、3、4、5 在 Task 1 之后可由不同会话准备，但都修改共享导入或测试文件，合并与验证必须按编号串行进行。

## Task 1：建立路径基座与布局回归骨架

**范围：** 新建无副作用包标记、单一仓库根解析模块和布局回归文件。布局测试先覆盖路径、保护目录、缓存白名单和允许根级契约；后续任务逐步补齐最终路径断言。

**可能涉及：**

- `core/__init__.py`
- `core/paths.py`
- `work-products/tests/test_project_layout.py`

**验收条件：**

- [x] `import core` 不读取配置、联网或写文件。
- [x] `paths.py` 从包位置稳定解析仓库根，并暴露根级 `config.json`、`ip.txt`、`ip.local.txt`、日志、锁、`.sing-box/` 和模板路径。
- [x] 布局测试精确区分允许删除缓存与 `.venv/`、`.codegraph/`、`.sing-box/`、`.agents/`、配置及用户文件。

**验证：**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_project_layout.py -v
.\.venv\Scripts\python.exe -X utf8 -c "import core; import core.paths"
```

**依赖：** 无。

**回滚：** 删除三个新增文件即可；不得触碰任何运行时目录或用户文件。

## Task 2A：迁移本地状态模块

**范围：** 将 `local_state.py` 移入包，切换主程序、GitHub 同步和测试导入；不修改本地/远端输出分离与旧重叠路径兼容行为。

**可能涉及：**

- `core/local_state.py`
- `main.py`
- `github_sync.py`
- `work-products/tests/test_multi_terminal_sync.py`

**验收条件：**

- [x] 包导入替代根 `local_state` 导入，根级旧模块不存在且无复制实现。
- [x] 相对 `OUTPUT_FILE` 仍按根级 `config.json` 所在目录解析。
- [x] 旧的 `OUTPUT_FILE=ip.txt` 与远端路径重叠时仍迁移到 `ip.local.txt`。

**验证：**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_multi_terminal_sync.py -v
```

**依赖：** Task 1。

**回滚：** 恢复根模块及原导入；不改写结果文件。

## Task 2B：迁移评分模块

**范围：** 将 `proxy_scoring.py` 移入包，切换主程序和评分测试导入；不修改公式、排序、数据类型或候选选择语义。

**可能涉及：**

- `core/proxy_scoring.py`
- `main.py`
- `work-products/tests/test_proxy_scoring.py`
- `work-products/tests/test_project_layout.py`

**验收条件：**

- [x] 包导入替代根 `proxy_scoring` 导入，根级旧模块不存在且无复制实现。
- [x] 评分 API、排序和带宽饱和语义不变。
- [x] 带宽失败、部分结果和无可用带宽的回退次序保持当前行为。

**验证：**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_proxy_scoring.py -v
```

**依赖：** Task 1；合并时排在 Task 2A 之后以避免共享 `main.py` 冲突。

**回滚：** 恢复根评分模块及原导入；不改写任何测速结果。

## Task 3：迁移链式代理模块

**范围：** 将 `chain_proxy.py` 移入包，改用统一仓库根解析 `.sing-box/`，更新主程序和聚焦测试导入；保留所有 fail-closed 行为。

**可能涉及：**

- `core/chain_proxy.py`
- `main.py`
- `work-products/tests/test_chain_proxy.py`
- `work-products/tests/test_project_layout.py`

**验收条件：**

- [x] mixed/base64 VLESS、WS/gRPC、TLS、ECH、fragment、fingerprint 和 `/video/` 全局 SOCKS5 语义不变。
- [x] XHTTP、模糊模板、非全局 SOCKS5、无效资源及 SHA-256 不匹配继续拒绝。
- [x] 默认 sing-box 仍解析到根级 `.sing-box/`，不落到 `core/.sing-box/`。

**验证：**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
```

**依赖：** Task 1；合并时排在 Task 2B 之后以避免共享 `main.py` 冲突。

**回滚：** 恢复根模块与导入；保留 `.sing-box/` 及任何已下载且校验通过的运行时。

## Task 4：迁移 GitHub 同步模块与手工脚本

**范围：** 将 `github_sync.py` 变为可用 `-m` 执行的包模块，把 `git_sync.ps1/.sh` 移入 `scripts/`，并把主程序的子进程调用切换为模块入口。

**可能涉及：**

- `core/github_sync.py`
- `scripts/git_sync.ps1`
- `scripts/git_sync.sh`
- `main.py`
- `work-products/tests/test_multi_terminal_sync.py`

**验收条件：**

- [x] `python -m core.github_sync` 默认读取根 `config.json`，并继续按 `OUTPUT_FILE` 读取本地结果。
- [x] CLI 参数、退出码、冲突重试与按终端字段替换行为不变。
- [x] 主程序和脚本不再依赖根 `github_sync.py`；错误输出不得暴露 Token、完整订阅 URI 或凭据。

**验证：**

```powershell
.\.venv\Scripts\python.exe -X utf8 -m core.github_sync --help
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_multi_terminal_sync.py -v
```

**依赖：** Task 2A。

**回滚：** 恢复根同步模块和脚本调用；不得修改远端 `ip.txt`，验证使用 mock/临时数据。

## Task 5：迁移调度模块并建立一期兼容入口

**范围：** 将调度实现移入包；根 `scheduled_run.py` 暂时变为纯委托包装器，保证旧计划任务在 setup 重新注册前仍可运行。

**可能涉及：**

- `core/scheduled_run.py`
- `scheduled_run.py`（一期包装器）
- `work-products/tests/test_multi_terminal_sync.py`
- `work-products/tests/test_project_layout.py`

**验收条件：**

- [x] `python -m core.scheduled_run` 从根读取配置、锁文件并在根工作目录调用公开 `main.py`。
- [x] 忙时 90 分钟、非忙时 180 分钟、30 分钟唤醒、禁用开关和防重入语义不变。
- [x] 根包装器不包含调度业务逻辑，并记录 Task 10 的可验证移除条件。

**验证：**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_multi_terminal_sync.py -v
.\.venv\Scripts\python.exe -X utf8 -c "import core.scheduled_run"
```

**依赖：** Task 1。

**回滚：** 恢复根调度实现和原计划任务命令；不删除锁文件以外的任何运行时数据。

## Task 6：把主程序收敛为薄入口

**范围：** 将原 `main.py` 实现整体迁入 `core/app.py`，用 `paths.py` 替换包目录路径假设，根 `main.py` 仅导入并执行 `main()`；更新内部测试导入。

**可能涉及：**

- `core/app.py`
- `main.py`
- `work-products/tests/test_measurement_flow.py`
- `work-products/tests/test_multi_terminal_sync.py`
- `work-products/tests/test_project_layout.py`

**验收条件：**

- [x] 根入口符合规格中的最小委托形态，`python main.py` 调用方式和退出语义不变。
- [x] 配置、Token、IP 信息缓存、日志、本地/远端输出和 sing-box 路径全部仍指向仓库根。
- [x] 原业务函数只有一份，测速、筛选、评分、DNS、GitHub 同步和链式代理语义不变。

**验证：**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_measurement_flow.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_project_layout.py -v
.\.venv\Scripts\python.exe -X utf8 -c "import core.app, main; assert main.main is core.app.main"
```

**依赖：** Tasks 2A、2B、3–5。

**回滚：** 恢复原根实现与导入；不得回滚或覆盖根级 `config.json` 和输出。

## Checkpoint A：Python 行为门禁

- [x] 聚焦链式代理保持 15/15 或更高且零失败。
- [x] Windows 完整套件至少保持既有 79 项通过、6 项 POSIX skip，新增测试全部通过。
- [x] 所有 `core` 模块从仓库根导入，无 `sys.path` 注入。
- [x] 根路径、输出、链式代理与 GitHub 同步的 mock 行为一致。
- [x] 任一失败即停止，不进入 setup/updater 迁移。

## Task 7：迁移 Windows setup/updater 与配置模板第一阶段

**范围：** 把 PowerShell updater 实现移入 `scripts/`，根 updater 暂时保留纯委托包装器；`setup.ps1` 改用新 updater 和模块化调度入口；先新增 `config/config.example.json`，在 Linux 切换完成前暂时保留内容相同的根模板。

**可能涉及：**

- `setup.ps1`
- `scripts/update_fork.ps1`
- `update_fork.ps1`（一期包装器）
- `config/config.example.json`
- `work-products/tests/test_windows_updater.py`
- `work-products/tests/test_multi_terminal_sync.py`

**验收条件：**

- [x] `scripts/update_fork.ps1` 从父目录解析并验证仓库根，在任何写操作前验证必要文件。
- [x] setup 从新模板生成根 `config.json`，新旧配置合并、备份保留 0/1、失败回滚和自更新重启语义不变。
- [x] 计划任务注册使用 `-m core.scheduled_run`，同时能识别并移除旧根调度命令；PowerShell 文件保持 UTF-8 BOM。

**验证：**

```powershell
$files = @('setup.ps1', 'scripts/update_fork.ps1', 'update_fork.ps1')
foreach ($file in $files) {
    [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8))
}
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_windows_updater.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_multi_terminal_sync.py -v
```

**依赖：** Checkpoint A。

**回滚：** 恢复根 updater 实现、旧调度命令和根模板；不得回滚用户配置或删除备份。

## Task 8：迁移 Linux setup/updater 并完成模板切换

**范围：** 把 Bash updater 实现移入 `scripts/`，根 updater 暂时保留纯委托包装器；`setup.sh` 使用新 updater、模块化调度和 `config/config.example.json`；根模板作为旧 updater 的一期兼容副本保留到第二期。

**可能涉及：**

- `setup.sh`
- `scripts/update_fork.sh`
- `update_fork.sh`（一期包装器）
- `config.example.json`（一期兼容副本，内容必须与规范模板相同）
- `work-products/tests/test_setup_update_integration.py`
- `work-products/tests/test_multi_terminal_sync.py`

**验收条件：**

- [x] `scripts/update_fork.sh` 显式解析父级仓库根，并保留快进、配置合并、备份、失败回滚与自更新接管行为。
- [x] cron 注册使用 `python -m core.scheduled_run`，清理逻辑同时识别旧命令，不覆盖其他用户 cron。
- [x] 新 setup/updater 仅消费 `config/config.example.json`；根模板仅为相同内容的一期兼容副本，根真实 `config.json`、远端 `ip.txt` 和 `_headers` 位置不变。

**验证：**

```bash
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh update_fork.sh
PYTHONUTF8=1 ./.venv/bin/python -m unittest discover \
  -s work-products/tests -p test_setup_update_integration.py -v
```

按用户 2026-08-03 的明确授权，本任务以理论多平台门禁代替真实 Linux/CI：Git Bash `bash -n`、跨平台源契约、嵌入 Python 代码编译及 Windows 完整回归必须通过；6 项 POSIX skip 必须单独披露，不得表述为真实 Linux 证明。

**依赖：** Task 7。

**回滚：** 恢复根 Bash updater、旧 cron 命令和根模板；保护 `config.json`、crontab 非项目项与备份。

## Checkpoint B：跨平台布局门禁

- [x] Windows 与 Linux setup/update 使用同一模板和模块命令。
- [x] Windows PowerShell 静态解析、BOM、更新器回归通过。
- [x] Git Bash `bash -n`、跨平台源契约和嵌入 Python 代码编译通过；6 项 POSIX skip 单独披露。
- [x] 新鲜配置、既有配置、无更新、正常快进、失败回滚、备份保留 0/1 均有理论源契约证据。
- [x] 根兼容入口、旧模板副本和 setup 自更新重载路径构成旧布局升级的理论证据；未声明真实安装证明。

## Task 9：同步三语文档、项目规则与跨仓命令

**范围：** 同步 README 简体中文、繁体中文、英文三部分和本仓 `AGENTS.md`；按 2026-08-02 已取得的授权，修正兄弟仓库指向 BestCfCdn 的旧测试命令。

**可能涉及：**

- `README.md`
- `AGENTS.md`
- `../CfGfwAX/AGENTS.md`（已授权最小规则修正）
- `../CGAX-Pages/AGENTS.md`（已授权最小规则修正）

**验收条件：**

- [x] 三语文档统一说明公开入口、新内部命令、模板位置和一期兼容/移除条件。
- [x] 本仓规则使用 `work-products/tests/`、`core/`、`scripts/` 和新的平台验证命令。
- [x] 两兄弟仓库改用从 BestCfCdn 根执行的 `work-products/tests/test_chain_proxy.py` 聚焦命令；不复制无关规则。

**验证：**

```powershell
rg -n "tests\.test_chain_proxy|tests[/\\]|scheduled_run\.py|github_sync\.py|update_fork\.(ps1|sh)|config\.example\.json" README.md AGENTS.md ..\CfGfwAX\AGENTS.md ..\CGAX-Pages\AGENTS.md
git diff --check
```

允许迁移规格、迁移清单和一期包装器保留历史路径；其余命中必须逐项解释或修正。

**依赖：** Checkpoint B；跨仓规则修改已获用户授权。

**回滚：** 各仓规则独立回滚；不把一个仓库的规则整段复制到另一个仓库。

## 第一期发布与升级验收门禁

第一期变更集保留 `scheduled_run.py`、`update_fork.ps1`、`update_fork.sh` 三个纯委托包装器。用户于 2026-08-03 再次明确继续 `@uxu-code:build auto`，授权进入独立第二期并删除兼容包装器与根模板副本。

- [x] Windows 理论升级契约：根 `setup.ps1`、兼容 updater、HEAD 变化检测、重载和模块化任务命令完整。
- [x] Linux 理论升级契约：根 `setup.sh`、兼容 updater、HEAD 变化检测、重载和模块化 cron 命令完整。
- [x] 新鲜配置、既有配置合并、无更新、快进、失败回滚及备份 0/1 的源契约完整。
- [x] 仓库、三语文档和已授权兄弟仓库除包装器、根模板兼容副本和迁移记录外不存在旧路径消费者。
- [x] 第一期理论验收完成；6 项 POSIX skip 和真实安装未验证单独披露，包装器因第二期未授权继续保留。

## Task 10：第二期删除兼容包装器并锁定根目录允许列表

**范围：** 在第一期门禁全部通过后的独立变更集中，删除三个根兼容包装器及根模板副本，收紧布局测试和陈旧引用扫描。

**可能涉及：**

- `scheduled_run.py`（删除）
- `update_fork.ps1`（删除）
- `update_fork.sh`（删除）
- `config.example.json`（删除一期兼容副本）
- `work-products/tests/test_project_layout.py`
- `work-products/tests/test_multi_terminal_sync.py`

**验收条件：**

- [x] 根级 Python 业务入口仅 `main.py`，根级平台入口仅 `setup.ps1`、`setup.sh`。
- [x] updater、调度、setup、README 和规则中没有旧物理路径消费者。
- [x] 根级允许列表没有意外增长，且 `config.json`、`ip.txt`、`_headers` 等保留项仍在原位。

**验证：**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_project_layout.py -v
rg -n --hidden -g '!.git/**' -g '!.venv/**' -g '!.codegraph/**' \
  -e 'scheduled_run\.py' -e 'update_fork\.(ps1|sh)' -e 'github_sync\.py' .
```

**依赖：** 第一期发布与升级验收门禁。

**回滚：** 恢复纯委托包装器；不恢复业务实现副本，不改用户任务状态。

## Task 11：完整验证后清理白名单缓存

**范围：** 运行所有本地、静态、跨平台和升级验证；通过后记录并删除规格白名单缓存，最后只做非写入复核。

**验收条件：**

- [x] Windows 完整测试、聚焦测试、模块导入、PowerShell 解析和 `git diff --check` 全通过。
- [x] 理论多平台源契约、Bash 解析和升级场景通过；6 项 POSIX 集成按用户授权继续跳过，未表述为真实 Linux 证明。
- [x] 仅删除仓库内 `.venv/` 之外的两个 `__pycache__/`；未发现其他白名单候选，保护项零删除。

**验证顺序：**

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -v
.\.venv\Scripts\python.exe -X utf8 -c "import core; import core.app"
git diff --check
```

1. 记录缓存候选的仓库相对路径、Git 跟踪状态、链接状态和白名单分类。
2. 有任何不明项即停止，不删除。
3. 删除白名单缓存；不得在删除后重跑会重新生成缓存的 Python 测试。
4. 仅复核缓存候选为空、保护目录/用户文件存在、Git 状态只含预期变更。

**依赖：** Task 10；若第二期尚未获准，则只完成第一期验证，不执行最终布局结论或缓存清理。

**回滚：** 代码和路径变更整体回滚；缓存不可恢复但均可再生。任何配置、输出、备份、`.sing-box/` 或用户文件都不属于回滚删除范围。

## Task 12：将内部包名收敛为 core

**范围：** 按用户 2026-08-03 的明确要求，将容易与仓库名混淆的内部包目录改为 `core/`，同步所有导入、模块命令、平台脚本、测试、三语文档与规则；不保留旧包别名。

**验收条件：**

- [x] `core/` 是唯一内部 Python 包目录，旧名和中间名目录均不存在。
- [x] 根入口、setup、同步脚本和包内绝对导入全部使用 `core`。
- [x] 代码、测试、三语 README、规则和当前工作流文档不存在旧包路径消费者。
- [x] 聚焦布局、完整回归、模块导入及平台静态门禁通过。

**回滚：** 将 `core/` 及全部引用整体改回原包名；不得增加双包兼容层。

## 风险与停止条件

| 风险 | 门禁与缓解 |
|---|---|
| 包迁移把运行时文件写进 `core/` | Task 1 统一路径；每个纵向切片检查根路径断言 |
| updater 自身在快进时被移动 | 第一期根包装器 + 旧布局升级夹具；新版 setup 必须重新加载 |
| 旧计划任务/cron 中断 | 第一期保留调度包装器；setup 同时清理旧命令并注册模块命令 |
| 配置模板切换丢失敏感配置 | Windows/Linux 分阶段但不分阶段发布；配置合并和失败回滚测试 |
| 跨仓测试命令继续陈旧 | Task 9 先取授权，再做最小规则更新 |
| 缓存清理误删用户数据 | 最终测试后、白名单、仓库边界、Git/链接检查；不明即停 |
| 理论结果被误当作真实 Linux 证明 | Checkpoint B 明确记录用户授权、静态/模拟证据和 6 项 POSIX skip |

## 授权状态

1. 已授权：Task 9 可同时修改 `../CfGfwAX/AGENTS.md` 与 `../CGAX-Pages/AGENTS.md`，仅把 `tests.test_chain_proxy` 修正为迁移后的聚焦命令。
2. 已授权：用户于 2026-08-03 再次明确继续 `@uxu-code:build auto`，授权独立执行第二期兼容包装器和根模板副本删除。
