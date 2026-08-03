# 规格：BestCfCdn 根目录瘦身与模块分组

## 状态

已实施并纠正升级兼容性（2026-08-03）。目录迁移、根级脚本兼容层删除、内部包名 `core/` 收敛和白名单缓存清理已完成；线上旧版 Linux updater 证明根模板仍是快进前引导契约，因此恢复其逐字节相同副本。6 项 POSIX 集成仍明确标为未在本机证明。

## 目标

为仓库维护者建立一眼可懂、可持续扩展的目录结构：根目录突出公开入口，Python 实现集中到单一包，运维脚本集中到脚本目录，同时保持现有用户命令、配置、输出、更新和定时任务行为不变。

问题重述：如何让维护者只在根目录看到真正的入口和仓库契约，而不因“看起来整齐”破坏已经被脚本、用户或外部服务依赖的路径？

### 目标用户

- 日常运行 `main.py`、`setup.ps1` 或 `setup.sh` 的最终用户。
- 维护 Python、Windows/Linux 安装更新流程和跨仓库链式代理契约的开发者与 agent。

### 成功定义

- 根目录不再平铺内部 Python 模块和运维辅助脚本。
- `main.py`、`setup.ps1`、`setup.sh` 的用户调用方式保持不变。
- Windows、Linux、GitHub 同步、定时运行、更新备份和链式代理行为不变。
- 根目录例外项都有明确的外部契约理由，而不是继续无原则堆放文件。

## 当前基线

- `main.py` 同时承担公开入口和大部分业务实现。
- `chain_proxy.py`、`github_sync.py`、`local_state.py`、`proxy_scoring.py`、`scheduled_run.py` 平铺在根目录。
- `git_sync.ps1/.sh` 和 `update_fork.ps1/.sh` 平铺在根目录，并大量使用“脚本目录等于仓库根目录”的假设。
- `config.json`、`config.example.json`、`ip.txt`、`ip.local.txt`、`requirements.txt`、`_headers` 与安装/更新/托管流程存在路径契约；用户已批准只移动配置示例，真实 `config.json` 继续留在根目录。
- 正式测试已位于 `work-products/tests/`；迁移规格为 `work-products/clean-migration.json`。
- 当前 Windows 基线为聚焦链式代理测试 15/15，通过；完整测试 79 项通过、6 项 POSIX 条件跳过。

## 明示假设

1. “最好只保留 main 和 setup 文件”表达的是减少根目录实现噪声，不要求移走 Git/GitHub/托管工具必须发现的标准文件。
2. `python main.py`、`.\setup.ps1`、`./setup.sh` 是必须保留的公开入口。
3. 本次只做结构迁移，不改变测速、评分、DNS、GitHub 同步、链式代理或调度语义。
4. 不引入新的打包工具、第三方依赖、构建步骤或 `sys.path` 注入。
5. `config.json`、`ip.local.txt`、`ip.txt` 和 `.sing-box/` 的运行时位置保持不变；规范模板迁入 `config/`，setup 和 updater 必须同步新模板路径。根模板仅作为旧 updater 快进前读取的完全相同兼容副本；在明确淘汰受影响旧版本前不得删除。
6. `ip.txt` 和 `_headers` 保持根目录，因为它们构成静态托管输出及缓存头契约。
7. 本次清理仅删除精确列出的可再生缓存；`.venv/`、`.codegraph/`、`.sing-box/` 和 `.agents/` 不是本次缓存清理对象。

若以上任一假设不成立，应先修订本规格，不能在实现阶段静默改变。

## 方向比较

### A. 单包分组，保留根目录契约（推荐）

将内部 Python 实现移入 `core/`，将平台运维助手移入 `scripts/`；根目录只保留公开入口和有外部发现契约的文件。

- 用户价值：高，最明显的实现噪声被移除。
- 可行性：高，不需要引入 Python 打包或改变数据路径。
- 风险：中，主要是导入、脚本根路径和定时任务路径。

### B. 字面上只剩 main/setup

连 README、LICENSE、依赖、配置模板、`ip.txt`、`_headers`、`.gitignore` 和 `AGENTS.md` 也移入子目录。

- 用户价值：表面整齐，但仓库可发现性下降。
- 可行性：低，会破坏 GitHub、pip、静态托管和 agent 指令发现惯例。
- 结论：不推荐，也不纳入第一阶段。

### C. 只移动几个脚本

仅移动 `git_sync` 和 `update_fork`，保留所有 Python 模块在根目录。

- 用户价值：低，无法解决主要杂乱来源。
- 结论：不足以达到目标。

## 范围

### 纳入

- 将 `main.py` 收敛为薄入口，把现有实现移入 `core/app.py`。
- 将内部 Python 模块移入直接可导入的 `core/` 包。
- 将 Windows/Linux 运维辅助脚本移入 `scripts/`。
- 将规范模板移入 `config/config.example.json`，但继续在根目录生成和读取真实 `config.json`；第一期保留根模板兼容副本。
- 更新所有 Python 导入、子进程调用、脚本根路径、定时任务命令和测试引用。
- 同步更新 README 的简体中文、繁体中文和英文路径说明，以及 `AGENTS.md`。
- 增加目录布局与陈旧路径回归测试。
- 在最终验证后按缓存白名单清理可再生缓存。
- 保留迁移前后的行为验证和可逆路径。

### 不纳入

- 不拆分或重写 `main.py` 内部业务函数；只做整体搬移和入口委托。
- 不改变配置键、默认值、输出格式、远端 `ip.txt` 路径或 Cloudflare/CfGfwAX/CGAX-Pages 契约。
- 不移动 `config.json`、`ip.local.txt`、`ip.txt`、`.sing-box/` 等运行时数据；仅移动配置示例。
- 不引入 `pyproject.toml`、安装型 Python 包、CLI 框架或新依赖。
- 不重构相邻算法、清理死代码或更改日志文案。
- 不修改兄弟仓库，除非实施审计发现其引用了被移动的物理路径；届时必须先请求授权并协调变更。

## 目标目录结构

```text
BestCfCdn/
├── main.py                         # 稳定公开入口，薄启动器
├── setup.ps1                       # 稳定 Windows 安装入口
├── setup.sh                        # 稳定 Linux 安装入口
├── README.md                       # GitHub 入口文档
├── LICENSE                         # GitHub/许可证发现契约
├── AGENTS.md                       # agent 规则发现契约
├── .gitignore                      # Git 根级配置
├── requirements.txt                # 保持现有安装命令
├── config.json                     # 本机真实配置，Git 忽略，路径保持不变
├── ip.txt                          # 保持现有远端/静态输出路径
├── _headers                        # 保持根级静态托管缓存规则
├── config/
│   └── config.example.json         # 无敏感信息的配置模板
├── core/
│   ├── __init__.py                 # 无副作用的包标记
│   ├── app.py                      # 原 main.py 业务实现
│   ├── chain_proxy.py
│   ├── github_sync.py              # 支持 python -m core.github_sync
│   ├── local_state.py
│   ├── paths.py                    # 唯一仓库根/运行时路径解析点
│   ├── proxy_scoring.py
│   └── scheduled_run.py            # 支持 python -m core.scheduled_run
├── scripts/
│   ├── git_sync.ps1
│   ├── git_sync.sh
│   ├── update_fork.ps1
│   └── update_fork.sh
└── work-products/
    ├── SPEC.md
    ├── clean-migration.json
    └── tests/
```

本地生成且已忽略的 `.git/`、`.venv/`、`.codegraph/`、`.agents/`、`.sing-box/`、`__pycache__/` 和运行时文件不计入“已跟踪根目录瘦身”指标。

### 根目录保留项及理由

| 文件 | 类型 | 必须留在根目录的理由 |
|---|---|---|
| `main.py` | CLI | 用户稳定运行入口，继续支持 `python main.py` |
| `setup.ps1`、`setup.sh` | CLI | Windows/Linux 稳定安装和更新入口 |
| `README.md` | GitHub | 仓库首页和三语快速开始由 GitHub 自动发现 |
| `LICENSE` | GitHub | GitHub 许可证识别和分发合规入口 |
| `AGENTS.md` | 工程规则 | Codex/agent 从仓库根发现项目约束 |
| `.gitignore` | Git | Git 根级忽略规则，不能迁入普通子目录 |
| `requirements.txt` | CLI | 保持 `pip install -r requirements.txt` 及 setup 依赖安装契约 |
| `config.json` | CLI/运行时 | 用户已批准继续使用根级真实配置；该文件被 Git 忽略且可能含敏感信息 |
| `ip.txt` | GitHub/托管 | 默认远端聚合路径及静态输出契约，外部消费者可能依赖原 URL |
| `_headers` | 托管 | 无构建步骤时必须在发布根目录为 `/*.txt` 提供禁缓存响应头 |

`config/config.example.json` 是可版本控制的无敏感信息模板，不属于根级运行时契约；setup 仍从它生成根级 `config.json`。

## 文件映射

| 当前路径 | 目标路径 | 要求 |
|---|---|---|
| `main.py` 的实现 | `core/app.py` | 根 `main.py` 仅委托，不复制两份实现 |
| `chain_proxy.py` | `core/chain_proxy.py` | 保持 fail-closed 和 sing-box 契约 |
| `github_sync.py` | `core/github_sync.py` | 保持命令行参数和退出码 |
| `local_state.py` | `core/local_state.py` | 保持输出路径兼容逻辑 |
| `proxy_scoring.py` | `core/proxy_scoring.py` | 保持评分 API 和结果顺序 |
| `scheduled_run.py` | `core/scheduled_run.py` | 更新 Windows 任务和 Linux cron 命令 |
| `git_sync.ps1/.sh` | `scripts/git_sync.ps1/.sh` | 改为 `python -m core.github_sync` |
| `update_fork.ps1/.sh` | `scripts/update_fork.ps1/.sh` | 显式计算仓库根，不再把脚本目录当根目录 |
| `config.example.json` | `config/config.example.json` | 新 setup/updater 读取规范模板；第一期根模板仅兼容旧 updater，真实 `config.json` 仍生成在根目录 |
| `work-products/tests/*` | 原位 | 只更新包导入和路径断言 |

## 接口与兼容性契约

### 保持不变的公开命令

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -X utf8 main.py
.\setup.ps1
```

```bash
./.venv/bin/python main.py
./setup.sh
```

### 新的内部命令

```powershell
.\.venv\Scripts\python.exe -X utf8 -m core.github_sync
.\.venv\Scripts\python.exe -X utf8 -m core.scheduled_run
```

直接执行根目录 `github_sync.py`、`scheduled_run.py`、`git_sync.*` 或 `update_fork.*` 不属于最终根目录契约。若需要兼容旧手工调用，只允许提供有明确移除条件的一期委托包装器；不得无限期保留双实现。

### Python 模块边界

- 根 `main.py` 只从 `core.app` 导入公开 `main`。
- 包内使用绝对包导入，例如 `from core.local_state import resolve_local_output`。
- `core/__init__.py` 不执行配置加载、网络请求或文件写入。
- `core/paths.py` 统一解析仓库根；模块不得再用自己的 `__file__` 猜测根目录。
- 配置、输出和运行时路径仍解析到现有仓库根位置。

### 脚本边界

- `setup.ps1` 和 `setup.sh` 是唯一稳定根级平台入口。
- `scripts/update_fork.*` 必须从自身位置显式解析父级仓库根，并在任何写操作前验证 `.git/`、`main.py` 与 `config/config.example.json`。
- setup 和 updater 必须从 `config/config.example.json` 生成或合并根级 `config.json`；不得把真实配置移入 `config/`。
- Windows 与 Linux 的脚本位置、配置保留、备份保留和调度行为必须同步。
- PowerShell 文件继续保留 UTF-8 BOM，兼容 Windows PowerShell 5.1。

### 外部契约

- `ip.txt` 的 Git 路径和默认 `GITHUB_SYNC_REMOTE_PATH` 不变。
- `_headers` 继续对根级 `/*.txt` 生效。
- CfGfwAX mixed/base64 VLESS、`/video/` 全局 SOCKS5、WS/gRPC、ECH、fragment 和 fingerprint 行为不变。
- XHTTP 仍明确拒绝，不因目录迁移改变。

## 代码风格

根入口应保持最小：

```python
from core.app import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- Python 保持四空格、`snake_case`、标准库优先和显式 fail-closed 校验。
- 不为此次迁移引入抽象层级；只建立一个包目录和一个脚本目录。
- 所有新增注释使用简体中文，只解释路径兼容原因，不复述代码。

## 实施迁移约束

1. 先建立新包和路径解析，保持旧入口可运行。
2. 逐个迁移模块并更新直接消费者，每一步运行相关测试。
3. 更新 setup、同步包装器、更新器和定时任务命令。
4. 移动配置模板，并验证新鲜安装与既有根级配置合并。
5. 更新三语 README、`AGENTS.md` 和测试路径。
6. 确认旧路径零引用后，才移除根级旧文件。
7. 完成所有测试后，按精确白名单删除可再生缓存。
8. 最后验证根目录允许列表和新鲜安装/既有配置更新流程。

不得在“新路径尚未通过完整验证”时先删除旧路径。迁移完成后不得保留两份业务实现。

## 缓存清理契约

### 允许删除

- 仓库内、`.venv/` 之外的 `__pycache__/` 和 `*.pyc`。
- 存在时的 `.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`。
- 已被 Git 忽略的根级 `ipinfo_cache.txt`；应用会在需要时重新生成。

### 必须保留

- `.codegraph/`：代码索引，不按普通 Python 缓存处理。
- `.venv/`：项目依赖环境。
- `.sing-box/`：校验过的运行时资产，不是缓存。
- `.agents/`：本地 agent/技能资产。
- `config.json`、`ip.txt`、`ip.local.txt`、`valid_tokens.txt`、`cfnb.log`、更新备份和任何用户文件。

### 删除前置条件

- 逐项解析绝对路径并确认仍位于仓库内。
- 拒绝符号链接、Git 跟踪文件、外部 excludes 命中的不明文件和非白名单内容。
- 先记录候选清单，再删除；缓存删除不可恢复，但所有允许项均须可由应用或测试重新生成。
- 测试会重新生成 Python 缓存，因此缓存清理必须放在最终测试之后。

## 测试策略

### 自动化测试位置

所有新增测试必须位于 `work-products/tests/`，并从其最终位置使用仓库相对路径。

新增 `work-products/tests/test_project_layout.py`，至少覆盖：

- 根级内部模块和辅助脚本已经消失。
- 允许的根级文件集合没有意外增长。
- `main.py` 是薄入口且可导入。
- 所有 `core` 模块可从仓库根导入，无 `sys.path` 修改。
- setup、同步、更新和调度脚本不含旧物理路径。
- PowerShell BOM 保持不变。
- `config/config.example.json` 可读取，setup 仍在根目录生成 `config.json`。
- `config.json`、`ip.local.txt`、`ip.txt` 与 `_headers` 运行时契约保持不变。
- 缓存清理候选仅来自本规格白名单，受保护目录和用户文件不进入候选。

### Windows 本地验证

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -v
.\.venv\Scripts\python.exe -X utf8 -c "import core; import core.app"
git diff --check
```

### 脚本静态验证

```powershell
$files = @('setup.ps1', 'scripts/git_sync.ps1', 'scripts/update_fork.ps1')
foreach ($file in $files) {
    [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8))
}
```

```bash
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh
```

### 平台验收

- Windows：新鲜配置生成、既有 `config.json` 更新、任务计划注册/禁用、手工 `main.py`。
- Linux 理论门禁：按用户 2026-08-03 的明确授权，以 Bash 静态解析、跨平台源契约、嵌入配置合并代码编译及 Windows 可运行回归代替真实 Linux/CI；结论必须标明未做真实 Linux 运行。
- 更新器：分别验证无更新、正常快进、失败回滚、备份保留数 0/1 和自迁移后的脚本位置。
- Git 同步：保持默认读取 `config.json` 和 `OUTPUT_FILE`，不得输出 Token 或完整订阅 URL。

本地测试不证明真实 Cloudflare、GitHub、sing-box 流量或已安装计划任务；这些仍需相应平台验收。

## 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `__file__` 改变导致读取包目录下的配置 | 启动失败或读取错误配置 | 使用单一 `core/paths.py`，增加路径断言 |
| Python 导入名改变 | 单测或运行时 `ModuleNotFoundError` | 先建立包，再逐个切换绝对导入 |
| updater 移入 `scripts/` 后仍把脚本目录当仓库根 | 配置或备份写错位置 | 每个平台显式计算并验证仓库根 |
| 旧计划任务仍指向根 `scheduled_run.py` | 自动运行中断 | setup 重注册任务；删除旧路径前验证迁移流程 |
| 正在执行的 updater 同时被移动 | Windows/Linux 更新中断 | 分阶段切换，先让根入口委托新实现，再移除旧入口 |
| 配置模板移动后 setup/updater 仍查找根路径 | 新鲜安装或配置合并失败 | Windows/Linux 同步改用 `config/config.example.json` 并覆盖新鲜/升级场景 |
| 缓存清理范围过宽 | 删除运行时、索引或用户数据 | 白名单、Git/链接检查、最终测试后执行 |
| PowerShell BOM/换行变化 | Windows PowerShell 5.1 解析异常 | 保留现有 BOM 回归并检查对象差异 |
| 文档只更新一种语言 | 用户命令漂移 | 三语 README 作为同一验收边界 |
| `ip.txt` 或 `_headers` 被误移 | 下游或静态托管断链 | 根目录允许列表固定保留两者 |

## 回滚

- 结构迁移必须保持为可整体回滚的单一变更集，不夹带业务行为修改。
- 回滚恢复旧物理路径、旧导入、旧脚本命令及根级配置模板；不得删除或重写用户的 `config.json`、`ip.local.txt`、备份目录或 `.sing-box/`。
- 已清理缓存不可从回滚恢复，但只允许删除可再生白名单项；回滚后应用可重新生成这些缓存。
- 在移除兼容包装器前，必须验证回滚后的 setup、调度和更新器仍能使用现有配置。
- 若任一平台完整测试失败，结论为 NO-GO，保留旧结构。

## 边界

### 始终执行

- 保持 `main.py` 与 setup 用户命令不变。
- 同步 Windows/Linux 和三语 README。
- 在删除旧路径前搜索所有消费者并通过完整测试。
- 保留未提交工作和用户本地配置。

### 必须先询问

- 移动 `config.json`、`requirements.txt`、`ip.txt` 或 `_headers`。
- 添加 Python 打包/安装机制或第三方依赖。
- 修改兄弟仓库、CI、托管路径或公开命令。
- 扩大缓存删除白名单或删除任何受保护目录/用户文件。

### 禁止

- 使用 `git reset --hard`、强制覆盖配置或删除备份。
- 用复制形成新旧两份长期业务实现。
- 通过 `sys.path` 修改掩盖包结构错误。
- 在日志、测试夹具、规格或迁移证据中保存 Token、UUID、完整订阅 URI 或代理凭据。

## 可度量验收条件

- [x] 根级 Python 业务入口只有 `main.py`；其余 Python 实现位于 `core/`。
- [x] 根级平台入口只有 `setup.ps1` 和 `setup.sh`；辅助脚本位于 `scripts/`。
- [x] 根级例外文件仅为本规格列出的仓库、配置、依赖和托管契约文件。
- [x] 规范模板已迁入 `config/config.example.json`；根兼容副本与其逐字节相同，供旧 updater 快进前读取；根级真实 `config.json` 的生成、读取和升级行为不变。
- [x] `python main.py`、`.\setup.ps1`、`./setup.sh` 的调用方式与退出语义不变。
- [x] 所有 Python 模块从仓库根正常导入，且仓库中不存在 `sys.path` 注入。
- [x] 旧的根级模块/辅助脚本消费者为零；迁移记录和回归夹具只保留历史 source。
- [x] 聚焦链式代理测试全部通过。
- [x] Windows 完整测试超过原 79 项通过、6 项 POSIX 条件跳过的基线。
- [x] 理论多平台门禁通过：Bash 静态解析、Windows 完整回归及跨平台源契约均通过；6 项 POSIX skip 单独披露。
- [x] Windows PowerShell BOM、setup/update、定时任务和 Git 同步回归全部通过。
- [x] 三语 README、`AGENTS.md` 和命令示例全部指向新结构。
- [x] 旧布局升级契约覆盖旧 updater 的根模板读取，setup 保留旧 cron 清理能力。
- [x] 最终测试后仅删除白名单缓存；`.venv/`、`.codegraph/`、`.sing-box/`、`.agents/` 和用户文件均保持不变。
- [x] `git diff --check` 通过，且没有业务行为差异或敏感信息。

## 已批准决策

1. 根目录保留公开 main/setup 入口、必要 GitHub/CLI/工程文件、根级真实 `config.json`、`ip.txt` 和 `_headers`；每项理由见“根目录保留项及理由”。
2. 规范模板迁入 `config/`；真实 `config.json` 继续留在根目录。根模板继续作为旧 updater 的引导副本，并由测试锁定与规范模板逐字节相同。最终测试后按精确白名单清理缓存，不迁移或删除受保护运行环境与用户文件。
3. 根脚本兼容包装器已在第二期移除；根模板删除因线上旧版 Linux updater 的实际失败证据而回滚，不能再以理论门禁替代该升级路径。

本规格已批准，可以进入 `@uxu-code:plan`；在计划批准前不得实施目录重组或缓存删除。
