# Cloudflare IP 优选工具

[![GitHub stars](https://img.shields.io/github/stars/xinyitang3/cfnb?style=social)](https://github.com/xinyitang3/cfnb/stargazers)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()
[![Last Commit](https://img.shields.io/github/last-commit/xinyitang3/cfnb?label=Last%20Commit)](https://github.com/xinyitang3/cfnb/commits)
[![Repo Size](https://img.shields.io/github/repo-size/xinyitang3/cfnb?label=Repo%20Size)](https://github.com/xinyitang3/cfnb)
[![Telegram](https://img.shields.io/badge/Telegram-@MiaChatChannel-26A5E4?logo=telegram)](https://t.me/MiaChatChannel)

> ⭐ **如果觉得好用，点个 Star 支持一下～**

这是一个全自动的 **Cloudflare CDN 节点优选工具**。它通过 **TCP 延迟筛选** + **IP 可用性二次检测** + **HTTP 延迟及抖动检测** + **真实带宽测速** 多重机制，从多个公开数据源中聚合节点，自动识别并解析任意格式（标准代码、中文名、emoji国旗、JSON等），筛选出当前网络环境下速度最快、延迟最低、抖动最小的 Cloudflare IP，并支持**自动更新至 Cloudflare DNS** 以及**同步至 GitHub 仓库**，同时支持微信实时通知。

> [!IMPORTANT]
> **跨平台支持**：本工具同时兼容 **Windows** 和 **Linux** 操作系统。
> - `github_sync.py` 通过 GitHub Contents API 并发安全地合并多终端结果
> - `git_sync.ps1` / `git_sync.sh` 保留为手动同步入口

---

### 📍 快速导航
- 🚀 [我要部署](#-部署步骤)（Windows / Linux 命令对照）
- 🔐 [我要获取 Token](#-获取必要令牌重要)（GitHub / Cloudflare / WxPusher 三合一教程）
- ⚙️ [我要调整参数](#%EF%B8%8F-配置说明完整参数详解)
- ☁️ [我要配置 Cloudflare DNS](#%EF%B8%8F-配置-cloudflare-dns-自动更新)
- 📤 [我要配置 GitHub 同步](#-配置-github-自动同步)
- 🔧 [Fork 后无法推送？一键修复](#-fork-后无法推送一键修复)
- 🔗 [对接 EdgeTunnel 指南](#-%E5%AF%B9%E6%8E%A5-edgetunnel-20-%E6%8C%87%E5%8D%97)
- ❓ [常见问题](#-常见问题)

---

## ✨ 功能特性

| 模块 | 说明 |
| :--- | :--- |
| 🌐 **多模式筛选** | 全局最优 TopN / 分国家最优 TopN |
| ⚡ **TCP 连接测试** | 并发测延迟，可设成功率阈值 |
| 🔍 **可用性二次检测** | API 验证代理能力 |
| 🔍 **HTTP 延迟与抖动检测** | 多次探测 HTTP 响应，计算平均延迟与抖动（标准差），过滤非 Cloudflare 节点，提升代理兼容性 |
| 📶 **真实带宽测速** | curl 下载测速，实测吞吐量 |
| ⚖️ **综合加权排序** | 同时考虑带宽、TCP 延迟、HTTP 延迟与抖动，四个权重可自由调整，选出综合体验最优的节点 |
| 🧩 **多源自适应聚合** | 支持多个数据源，自动识别并解析任意格式（标准代码、中文名、emoji国旗、JSON等），统一转换为标准格式 |
| ⚙️ **前置过滤（按序执行）** | TCP 测试前按序：端口过滤 → 黑名单过滤 → 白名单过滤（均可开关） |
| 🚫 **DNS 黑名单** | DNS 更新时剔除指定国家节点（**仅作用于 DNS 更新环节**） |
| 🛡️ **IPv6 落地过滤** | 过滤落地仅 IPv6 的节点，保留 IPv4/双栈节点（**仅作用于 DNS 更新环节**） |
| 🔍 **IP 风险等级过滤** | 仅允许低风险节点，高危自动回退（**仅作用于 DNS 更新环节**） |
| 🗺️ **IP 地区校准** | 基于 ipinfo.io 异步并发查询，自动校正节点国家代码，结果缓存复用 |
| 🔒 **强制直连模式** | 可配置开关，一键清除系统代理，确保所有测试流量走直连 |
| ☁️ **Cloudflare DNS 更新** | 原子批量替换同名 A/TXT 记录 |
| 📬 **微信实时通知** | 集成 WxPusher，异常/结果推送 |
| 🔄 **峰谷定时运行** | 中国 CF CDN 忙时每 15 分钟，非忙时每 30 分钟 |
| 🚀 **一键部署** | `setup.ps1` / `setup.sh` 自动安装依赖并配置 |
| 📤 **多终端安全同步** | 每台终端只替换自己的 5 行，冲突时自动拉取并重新合并 |
| 🔒 **隐私保护** | GitHub Token 不进入远程 URL；文档明确禁止提交真实密钥 |
| 🖥️ **跨平台兼容** | 同时支持 Windows 和 Linux |
| 🔄 **安全更新** | 内置 `update_fork.ps1` / `update_fork.sh`，快进更新并保留本机配置 |

---

## 📦 文件清单

| 文件 | 说明 |
| :--- | :--- |
| `main.py` | 核心优选程序（抓取、测试、筛选、更新、推送） |
| `config.json` | 所有运行参数的配置文件（含详细注释） |
| `github_sync.py` | GitHub 多终端并发安全合并程序 |
| `scheduled_run.py` | 按中国 CF CDN 峰谷时段运行并防止任务重叠 |
| `git_sync.ps1` | Windows 手动同步入口 |
| `git_sync.sh` | Linux 手动同步入口 |
| `setup.ps1` | Windows 一键部署脚本（安装依赖并配置计划任务） |
| `setup.sh` | Linux 一键部署脚本（安装依赖并配置 cron） |
| `requirements.txt` | Windows/Linux 共用的核心 Python 依赖清单 |
| `ip.txt` | 最终优选节点列表（每次运行覆盖） |
| `update_fork.ps1` | Windows 安全更新脚本（备份并保留本机配置） |
| `update_fork.sh` | Linux 安全更新脚本（备份并保留本机配置） |
| `valid_tokens.txt` | ipinfo.io API Token 列表（每行一个，用于 IP 地区校准） |

---

## 🖥️ 系统要求

- **操作系统**：Windows 10+ / Windows Server 2016+ 或 Linux（Ubuntu/Debian/CentOS 等）
- **必备软件**：
  - **Python 3.9+**
  - **Git**
  - **curl**（需在系统 PATH 中可用）
- **Python 依赖**：`requests`, `aiohttp`, `brotlicffi`

---

## 🚀 部署步骤

### 通用前置步骤

1. **获取项目文件**  
   - **方式一（推荐）**：点击本仓库页面的绿色 `Code` 按钮 → `Download ZIP`，下载压缩包后解压到本地。  
   - **方式二（熟悉 Git 的用户）**：使用命令行克隆仓库：
     ```bash
     git clone https://github.com/你的用户名/仓库名.git
     cd 仓库名
     ```

2. **配置各项令牌（见下一节）**  
   根据需求获取并填写 GitHub Token、Cloudflare API Token 和 WxPusher 凭证。

> 💡 部署脚本会创建项目专用 `.venv`，优先使用清华 PyPI 镜像并在失败时回退官方源；安装后会实际导入验证依赖。脚本只补充 `.gitignore`，不会覆盖已有内容，并配置中国 CF CDN 忙时 15 分钟、非忙时 30 分钟的定时任务。

---

### 🔐 获取必要令牌（重要）

若你希望启用 GitHub 自动推送、Cloudflare DNS 更新或微信通知，请参考下表获取对应令牌。

| GitHub Personal Access Token | Cloudflare API Token | WxPusher 微信通知 |
| :---: | :---: | :---: |
| **1.** 登录 GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) | **1.** 进入域名概览页，点击右侧API栏的获取您的 API 令牌 | **1.** 访问 [WxPusher 后台](https://wxpusher.zjiecode.com/admin/)，微信扫码登录 |
| **2.** Generate new token (classic)，Note 任意填 | **2.** 点击 创建令牌 → 选择 **编辑区域 DNS** 模板 | **2.** 左侧菜单“应用管理”→“应用信息”→“新增应用”，填写名称后创建 |
| **3.** **Expiration 必须选 `No expiration`** | **3.** 权限已自动填好（区域 - DNS - 编辑），区域资源选择你的域名 | **3.** 复制保存 AppToken（仅显示一次） |
| **4.** Select scopes: 仅勾选 **repo**（自动勾全） | **4.** 点击 继续以显示摘要 → 创建令牌 | **4.** 左侧“关注应用”→微信扫码关注公众号 |
| **5.** Generate token，保存 | **5.** 立即复制并保存令牌（仅显示一次） | **5.** 公众号菜单“我的”→“我的UID”获取 UID |
| 填入 `config.json` 的 `GITHUB_SYNC_TOKEN` | 填入 `config.json` 的 `CF_API_TOKEN` 和 `CF_ZONE_ID` | 填入 `config.json` 的 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UIDS` |

> 💡 若不需要某项功能，可跳过对应步骤或在配置中关闭开关：  
> - 无需微信通知：`config.json` 中设 `ENABLE_WXPUSHER: false`  
> - 无需 GitHub 推送：`config.json` 中设 `GITHUB_SYNC_MAX_RETRIES: 0`  
> - 无需 Cloudflare DNS 更新：`config.json` 中设 `CF_ENABLED: false`

---

### Windows 部署

以管理员身份打开 **PowerShell**，逐行执行以下命令：

```powershell
# 1. 进入项目目录
cd "C:\你的项目路径\cfnb"

# 2. 若提示脚本禁用，临时绕过（可选）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. 运行部署脚本
.\setup.ps1

# 4. 编辑配置，填入 GitHub 令牌、仓库和终端名称
notepad config.json

# 5. 测试运行（使用部署脚本创建的项目虚拟环境）
.\.venv\Scripts\python.exe main.py
```

### Linux 部署

在终端中逐行执行以下命令：

```bash
# 1. 进入项目目录
cd /path/to/cfnb

# 2. 赋予执行权限
chmod +x setup.sh

# 3. 运行部署脚本（仅安装缺失系统软件时自动调用 sudo）
./setup.sh

# 4. 编辑配置，填入 GitHub 令牌、仓库和终端名称
nano config.json

# 5. 测试运行（使用项目虚拟环境）
./.venv/bin/python main.py
```

<details>
<summary>📝 手动部署详细步骤（点击展开）</summary>

#### Windows 手动部署

1. 安装 [Python 3](https://www.python.org/downloads/)（勾选 “Add Python to PATH”）。
2. 安装 [Git](https://git-scm.com/download/win) 和 [curl](https://curl.se/windows/)（curl 需加入 PATH）。
3. 在项目目录创建虚拟环境并安装依赖：
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
   .\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple brotlicffi
   ```
4. （可选）手动创建计划任务：
   - 按 `Win + R`，输入 `taskschd.msc` 打开任务计划程序。
   - 创建任务，名称 `Cloudflare IP 优选`，勾选“不管用户是否登录都要运行”和“使用最高权限运行”。
   - 触发器：新建 → 开始任务“按预定计划” → 设置“一次”，开始时间为下一个整15分钟时刻；高级设置中勾选“重复任务间隔”，选择“15分钟”，持续时间“无限期”。
   - 操作：新建 → 操作“启动程序”，程序填写 `python.exe` 路径，参数填写 `scheduled_run.py` 完整路径，起始于填写项目目录。
   - 在 **“设置”** 选项卡中，将 **“优先级”** 下拉框设为 **“高”**。
   - 点击确定，输入 Windows 登录密码保存。

#### Linux 手动部署

1. 安装系统依赖（以 Debian/Ubuntu 为例）：
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv git curl cron
   ```
2. 创建项目虚拟环境并安装 Python 依赖：
   ```bash
   python3 -m venv .venv
   ./.venv/bin/python -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
   ./.venv/bin/python -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple brotlicffi
   ```
3. 赋予推送脚本执行权限（如果需要）：
   ```bash
   chmod +x git_sync.sh
   ```
4. （可选）添加 cron 任务：
   ```bash
   (crontab -l 2>/dev/null; echo "*/15 * * * * cd $(pwd) && $(pwd)/.venv/bin/python $(pwd)/scheduled_run.py >> $(pwd)/cron.log 2>&1") | crontab -
   ```
5. 验证：`crontab -l`

</details>

---

## 🔄 安全更新本地项目

需要从 GitHub 拉取最新版，同时保留本机 `config.json` 和 `ip.txt` 时，可运行：

| 平台 | 命令 |
| :--- | :--- |
| Windows PowerShell | `.\update_fork.ps1` |
| Linux | `chmod +x update_fork.sh && ./update_fork.sh` |

脚本会备份本机配置，只允许 `origin/main` 快进更新，并把本机配置值合并到最新版。若存在其他未提交代码，或本地与远端已经分叉，脚本会停止并保留备份。

> [!IMPORTANT]
> 更新脚本不会执行 `git reset --hard`，不会把 GitHub Token 写入远程 URL，也不会处理无关历史。GitHub 节点上报始终通过 `github_sync.py` 和 Contents API 完成。

---

## 🕒 定时自动运行说明

| 平台 | 方式 | 行为 |
| :--- | :--- | :--- |
| Windows | 计划任务 `Cloudflare IP 优选` | 每 15 分钟调用调度入口 |
| Linux | cron 定时任务 | 分钟字段为 `*/15`，整点对齐 |

默认按北京时间划分：`18:00–24:00` 为 Cloudflare CDN 中国忙时，每 15 分钟筛选；其余时间每 30 分钟筛选。任务每 15 分钟唤醒一次，非忙时的 `:15` 和 `:45` 自动跳过。若上次筛选尚未结束，本轮也会自动跳过，避免重叠测速。

如只想手动运行，请在 `config.json` 中设置：

```json
"ENABLE_SCHEDULED_TASK": false
```

然后重新执行一次 `setup.ps1`（Windows）或 `setup.sh`（Linux）。部署脚本会删除本项目已有的计划任务或 cron 条目，并且不会创建新任务。需要优选时手动执行：

```powershell
# Windows
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
# Linux
./.venv/bin/python main.py
```

手动运行 `main.py` 不受峰谷时段限制。以后把开关改回 `true` 并重新运行部署脚本，即可恢复自动调度。

该默认窗口是工程化覆盖范围：[Cloudflare 官方说明](https://blog.cloudflare.com/http-requests-on-cloudflare-radar/)中，Radar 的 HTTP 字节指标对应 CDN 流量，且晚间内容流量会快速上升并在当地约 22 点达到峰值；中国区域可在 [Cloudflare Radar](https://radar.cloudflare.com/traffic/cn) 持续观察。实际网络不同，可通过 `SCHEDULE_CF_BUSY_START_HOUR` 和 `SCHEDULE_CF_BUSY_END_HOUR` 调整。

**日志查看**：
- Windows：任务计划程序中查看历史记录。
- Linux：`tail -f cron.log`

---

## ⚙️ 配置说明（完整参数详解）

> [!NOTE]
> 默认参数按 **中国大陆跨境链路 + 2核2G 云服务器** 调优：使用北京时间、较宽松的网络超时与重试，并降低并发以减少家庭宽带/运营商 NAT 连接耗尽。若在软路由、树莓派或低配 PC 上运行，可继续降低 `MAX_WORKERS`、`HTTP_TEST_WORKERS`、`BANDWIDTH_WORKERS`。

所有参数均位于 `config.json`，以下为逐项说明。

### 筛选模式与数量控制

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `USE_GLOBAL_MODE` | `boolean` | `true` | `true`=全局优选；`false`=分国家优选 |
| `GLOBAL_TOP_N` | `int` | `5` | 全局模式保留节点数 |
| `PER_COUNTRY_TOP_N` | `int` | `1` | 分国家模式每国保留节点数 |
| `BANDWIDTH_CANDIDATES` | `int` | `150` | 进入测速的候选节点数 |
| `DNS_UPDATE_TARGET_COUNT` | `int` | `5` | DNS 更新时最多写入5个最优 IP |

### TCP 连接测试参数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `TCP_PROBES` | `int` | `2` | 每个节点 TCP 测试次数，降低跨境链路偶发抖动造成的误判 |
| `MIN_SUCCESS_RATE` | `float` | `1.0` | 最低成功率阈值（0.0~1.0） |
| `TCP_LATENCY_WEIGHT` | `float` | `0.0` | TCP延迟在综合排序中的权重（越大越排斥高TCP延迟） |
| `TIMEOUT` | `float` | `3.0` | 单次 TCP 连接超时（秒） |
| `SOCKET_DEFAULT_TIMEOUT` | `int` | `5` | 全局 Socket 默认超时（秒），防止永久阻塞 |
| `PROGRESS_PRINT_INTERVAL` | `float` | `1` | 进度打印刷新间隔（秒），避免频繁 I/O |

### 综合排序权重

最终节点的排名由综合得分决定，公式为：  
**得分 = (SPEED_WEIGHT × 带宽) / (1 + TCP_LATENCY_WEIGHT × TCP延迟 + HTTP_LATENCY_WEIGHT × HTTP延迟 + JITTER_WEIGHT × HTTP抖动)**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `HTTP_LATENCY_WEIGHT` | `float` | `3.0` | HTTP延迟在综合排序中的权重（越大越排斥高HTTP延迟） |
| `JITTER_WEIGHT` | `float` | `3.0` | HTTP延迟抖动（标准差）在综合排序中的权重（越大越排斥延迟波动大的节点） |
| `HTTP_JITTER_SAMPLES` | `int` | `3` | HTTP延迟抖动测试次数（至少3次，建议3~5次，越大越准但越慢） |
| `SPEED_WEIGHT` | `float` | `3.0` | 带宽在综合排序中的权重（越大越看重带宽） |

### 前置过滤参数（TCP 测试前生效）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `PRE_FILTER_PORT_ENABLED` | `boolean` | `true` | 是否启用前置端口过滤 |
| `PRE_FILTER_PORTS` | `array` | `[443]` | TCP 测试前允许的端口列表（可多个） |
| `PRE_FILTER_BLOCKED_ENABLED` | `boolean` | `true` | 是否启用前置黑名单过滤 |
| `PRE_FILTER_BLOCKED_COUNTRIES` | `array` | `["CN"]` | 前置黑名单国家代码列表（TCP 测试前剔除） |
| `FILTER_COUNTRIES_ENABLED` | `boolean` | `false` | 是否启用前置白名单过滤 |
| `ALLOWED_COUNTRIES` | `array` | `["US"]` | 前置白名单国家代码列表（仅在开关开启时生效） |

> 💡 过滤执行顺序：**前置端口过滤 → 前置黑名单 → 前置白名单**。  
> 所有前置过滤均在 TCP 测试前完成，可大幅减少无效测试。

### 网络直连控制

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `FORCE_DIRECT` | `boolean` | `false` | 是否强制所有网络请求直连（`true`=清除系统代理，全部走直连） |

### DNS 黑名单参数（仅作用于 DNS 更新环节）

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `FILTER_IPV6_AVAILABILITY` | `boolean` | `true` | **仅作用于 DNS**：是否过滤落地仅 IPv6 的节点（`ipv6_only`） |
| `FILTER_BLOCKED_COUNTRIES_ENABLED` | `boolean` | `true` | DNS 更新时是否启用黑名单过滤 |
| `BLOCKED_COUNTRIES` | `array` | `BD, BI, BY, CD, CF, CN, CU, DE, ET, HK,`<br>`IR, KP, LY, MO, NG, NL, PK, RU, SD, SO,`<br>`SY, TH, TW, UA, VE, VN, YE, ZW` | DNS 更新时需要剔除的国家代码列表（共 28 个） |
| `DNS_IP_RISK_FILTER_ENABLED` | `boolean` | `false` | 是否启用 IP 风险等级过滤 |
| `DNS_IP_RISK_MAX_LEVEL` | `string` | `高风险` | 允许的最高风险等级（可选：极度纯净、纯净、轻微风险、高风险、极度危险） |

> **说明**：  
> - 该过滤**仅作用于 Cloudflare DNS 批量更新环节**，不会影响 `ip.txt` 的内容和 GitHub 推送。  
> - DNS 更新时会**同时应用以下条件**，只有全部满足的节点才会写入 DNS：  
>   - 端口必须为 `443`  
>   - 落地不能仅为 IPv6（即保留 IPv4 或双栈节点，需开启 `FILTER_IPV6_AVAILABILITY`）  
>   - 国家不在 `BLOCKED_COUNTRIES` 黑名单中（需开启 `FILTER_BLOCKED_COUNTRIES_ENABLED`）  
>   - IP 风险等级不高于设定阈值（需开启 `DNS_IP_RISK_FILTER_ENABLED`，若过滤后无节点则自动回退到未过滤列表）

### 微信通知（WxPusher）参数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `ENABLE_WXPUSHER` | `boolean` | `false` | 是否启用微信通知，默认关闭 |
| `WXPUSHER_APP_TOKEN` | `string` | `"your_app_token_here"` | **【必填】** WxPusher 的 APP_TOKEN |
| `WXPUSHER_UIDS` | `array` | `["your_uid_here"]` | **【必填】** 接收通知的用户 UID 列表 |
| `WXPUSHER_API_URL` | `string` | `"https://wxpusher.zjiecode.com/api/send/message"` | 消息发送 API 地址 |
| `NOTIFY_TIMEOUT` | `int` | `8` | 微信通知 API 读取超时（秒） |
| `NOTIFY_CONNECT_TIMEOUT` | `int` | `5` | 微信通知 API 连接超时（秒） |

> 💡 若不需要通知，将 `ENABLE_WXPUSHER` 设为 `false` 即可。

### Cloudflare DNS 批量更新参数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `CF_ENABLED` | `boolean` | `true` | 是否启用 DNS 自动更新 |
| `CF_API_TOKEN` | `string` | `"your_CF_API_TOKEN"` | Cloudflare API 令牌（Zone:DNS:Edit 权限） |
| `CF_ZONE_ID` | `string` | `"your_CF_ZONE_ID"` | 域名区域 ID |
| `CF_DNS_RECORD_NAME` | `string` | `"your_CF_DNS_RECORD_NAME"` | 完整子域名 |
| `CF_TTL` | `int` | `60` | DNS 记录 TTL（秒） |
| `CF_PROXIED` | `boolean` | `false` | 是否启用 Cloudflare CDN 代理 |
| `CF_DNS_CONNECT_TIMEOUT` | `int` | `5` | Cloudflare API 连接超时（秒） |
| `CF_DNS_READ_TIMEOUT` | `int` | `10` | Cloudflare API 读取超时（秒） |
| `DNS_RECORD_TYPE` | `string` | `"TXT"` | DNS 记录类型（A 或 TXT） |

> 💡 若不需要 DNS 更新，将 `CF_ENABLED` 设为 `false` 即可。

### 节点数据源与获取配置

> [!NOTE]
> 本工具支持**多个数据源同时使用**，并内置了**完全自适应的解析引擎**。无论数据源是标准 `IP:端口#代码` 格式，还是中文标签、emoji国旗、JSON数组/对象，甚至是混合无关文字的标签，程序都能自动识别并统一转换为标准格式。添加新数据源只需在 `ADDITIONAL_SOURCES` 数组中新增一个对象，无需任何代码修改。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `ADDITIONAL_SOURCES` | `array` | `[]` | 所有数据源列表，每个对象包含 `url`（必填）和 `enabled`（可选，默认true）。程序会自动识别并解析任何常见格式（标准代码/中文/emoji/JSON等） |
| `FETCH_MAX_RETRIES` | `int` | `5` | 获取节点列表失败时的最大重试次数 |
| `FETCH_RETRY_DELAY` | `int` | `5` | 获取节点列表重试间隔（秒） |
| `FETCH_TIMEOUT` | `int` | `10` | 获取节点列表读取超时（秒） |
| `FETCH_CONNECT_TIMEOUT` | `int` | `5` | 获取节点列表连接超时（秒） |
| `OUTPUT_FILE` | `string` | `"ip.txt"` | 最终结果保存文件名 |
| `ENABLE_LOGGING` | `boolean` | `false` | 是否启用运行日志（每次运行覆盖 LOG_FILE） |
| `LOG_FILE` | `string` | `"cfnb.log"` | 运行日志文件名（仅在启用日志时生效） |

### IP 地区校准参数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `IP_CALIBRATION_ENABLED` | `boolean` | `false` | 是否启用 IP 地区校准（基于 ipinfo.io） |
| `IP_CALIBRATION_MIN_INTERVAL` | `float` | `0.1` | 请求最小间隔（秒） |
| `IP_CALIBRATION_TOKEN_FILE` | `string` | `"valid_tokens.txt"` | ipinfo.io Token 文件名 |
| `IP_CALIBRATION_CACHE_FILE` | `string` | `"ipinfo_cache.txt"` | 校准结果缓存文件名 |

> 💡 校准结果会实时写入缓存文件，程序结束后自动按 IP 地址排序，下次运行可复用。  
> Token 文件每行一个 ipinfo.io 的 API Token，可在 [ipinfo.io](https://ipinfo.io/) 注册免费获取（每月 5 万次）。  
> 程序会自动校验 Token 有效性并显示进度，当所有 Token 均触发速率限制时，会通过微信通知。

<details>
<summary>🔧 高级参数（可用性 /HTTP / 带宽 / 并发 / 重试 / 广告/ 输出）</summary>

**可用性检测参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `TEST_AVAILABILITY` | `boolean` | `true` | 是否进行可用性二次筛选 |
| `AVAILABILITY_CHECK_API` | `string` | `"https://api.090227.xyz/check"` | 可用性检测 API 地址 |
| `AVAILABILITY_TIMEOUT` | `int` | `8` | 可用性 API 读取超时（秒） |
| `AVAILABILITY_CONNECT_TIMEOUT` | `int` | `5` | 可用性 API 连接超时（秒） |
| `AVAILABILITY_RETRY_MAX` | `int` | `3` | 可用性检测最大重试轮数 |
| `AVAILABILITY_RETRY_DELAY` | `int` | `3` | 可用性检测重试间隔（秒） |
| `AVAILABILITY_INNER_RETRY_ENABLED` | `boolean` | `true` | 可用性检测是否启用单节点内部重试 |
| `AVAILABILITY_INNER_RETRY_MAX` | `int` | `2` | 可用性检测单节点内部最大重试次数 |
| `AVAILABILITY_INNER_RETRY_DELAY` | `int` | `3` | 可用性检测单节点内部重试间隔（秒） |

> 💡 IPv6 过滤逻辑：通过 API 返回的 `inferred_stack` 判断，仅淘汰 `ipv6_only` 节点，保留 `ipv4_only` 和 `dual_stack` 节点。

**HTTP 检测参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `HTTP_TEST_ENABLED` | `boolean` | `true` | 是否启用 HTTP检测（过滤 HTTP 响应头非Cloudflare 的节点） |
| `HTTP_TEST_TIMEOUT` | `int` | `8` | 单次 HTTP 请求读取超时（秒） |
| `HTTP_TEST_CONNECT_TIMEOUT` | `int` | `5` | HTTP 检测的连接超时（秒），与读取超时分离 |
| `HTTP_TEST_INNER_RETRY_ENABLED` | `boolean` | `true` | HTTP 检测是否启用单节点内部重试 |
| `HTTP_TEST_MAX_RETRIES` | `int` | `2` | 单节点 HTTP 请求超时重试次数 |
| `HTTP_TEST_RETRY_DELAY` | `int` | `3` | HTTP 请求重试间隔（秒） |
| `HTTP_TEST_MAX_ROUNDS` | `int` | `3` | 整体失败（通过率为0）时的最大重试轮数 |
| `HTTP_TEST_ROUND_DELAY` | `int` | `3` | 整体重试间隔（秒） |
| `HTTP_TEST_METHOD` | `string` | `"HEAD"` | 请求方法（`GET` 或 `HEAD`） |

> 💡 HTTP 检测在可用性检测之后、带宽测速之前执行，仅淘汰非 `Code: 400` 和 `Server: cloudflare` 的节点，其余均视为可用。

**带宽测速参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `BANDWIDTH_SIZE_MB` | `float` | `2.0` | 测速下载文件大小（MB），降低短时突发对结果的影响 |
| `BANDWIDTH_TIMEOUT` | `int` | `8` | 单个节点带宽测速超时（秒） |
| `BANDWIDTH_RETRY_MAX` | `int` | `2` | 带宽测速整体重试轮数 |
| `BANDWIDTH_RETRY_DELAY` | `int` | `3` | 带宽测速重试间隔（秒） |
| `BANDWIDTH_URL_TEMPLATE` | `string` | `"https://speed.cloudflare.com/__down?bytes={bytes}"` | 测速 URL 模板 |
| `BANDWIDTH_PROCESS_BUFFER` | `int` | `2` | curl 进程额外缓冲时间（秒） |
| `BANDWIDTH_CONNECT_TIMEOUT` | `int` | `5` | curl 测速连接超时（秒） |

**并发控制参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `IP_CALIBRATION_CONCURRENCY` | `int` | `100` | 地区校准的异步并发数 |
| `MAX_WORKERS` | `int` | `150` | TCP 并发测试最大线程数 |
| `AVAILABILITY_WORKERS` | `int` | `16` | 可用性检测并发数 |
| `FALLBACK_WORKERS` | `int` | `16` | 备用国家查询的并发线程数（当标签无法识别时自动调用可用性API查询国家） |
| `HTTP_TEST_WORKERS` | `int` | `16` | HTTP 检测并发线程数 |
| `BANDWIDTH_WORKERS` | `int` | `2` | 带宽测速并发数 |

**重试策略配置**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `DNS_UPDATE_MAX_RETRIES` | `int` | `5` | DNS 更新最大重试次数 |
| `DNS_UPDATE_RETRY_DELAY` | `int` | `5` | DNS 更新重试间隔（秒） |
| `GITHUB_SYNC_MAX_RETRIES` | `int` | `5` | GitHub 推送最大重试次数 |
| `GITHUB_SYNC_RETRY_DELAY` | `int` | `5` | GitHub 推送重试间隔（秒） |
| `GIT_SYNC_PROCESS_TIMEOUT` | `int` | `300` | Git 同步子进程最大运行时间（秒） |

**多终端 GitHub 同步参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `GITHUB_SYNC_TOKEN` | `string` | 占位符 | GitHub Token，不要提交真实值 |
| `GITHUB_SYNC_REPOSITORY` | `string` | 占位符 | 目标仓库，格式 `owner/repo` |
| `GITHUB_SYNC_BRANCH` | `string` | `main` | 目标分支 |
| `GITHUB_SYNC_REMOTE_PATH` | `string` | `ip.txt` | 远端汇总文件路径 |
| `GITHUB_SYNC_FIELD_ID` | `string` | 占位符 | 每台终端唯一名称 |
| `GITHUB_SYNC_TOP_N` | `int` | `5` | 每台终端最多上报节点数 |
| `GITHUB_SYNC_CONFLICT_RETRIES` | `int` | `8` | SHA 冲突时重新拉取合并次数 |

**Cloudflare CDN 中国峰谷调度参数**

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `ENABLE_SCHEDULED_TASK` | `boolean` | `true` | 是否创建并执行自动定时任务；关闭后仍可手动运行 `main.py` |
| `SCHEDULE_TIMEZONE_OFFSET_HOURS` | `number` | `8` | 调度时区，默认北京时间 |
| `SCHEDULE_CF_BUSY_START_HOUR` | `int` | `18` | CF CDN 中国忙时开始（含） |
| `SCHEDULE_CF_BUSY_END_HOUR` | `int` | `24` | CF CDN 中国忙时结束（不含） |
| `SCHEDULE_BUSY_INTERVAL_MINUTES` | `int` | `15` | 忙时筛选间隔 |
| `SCHEDULE_OFFPEAK_INTERVAL_MINUTES` | `int` | `30` | 非忙时筛选间隔 |
| `SCHEDULE_LOCK_STALE_MINUTES` | `int` | `180` | 防重叠锁失效时间 |

#### 广告植入参数

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `AD_HEADER_ENABLED` | `boolean` | `false` | 是否在 `ip.txt` 头部插入自定义广告行 |
| `AD_HEADER_LINES` | `array` | `["0.0.0.0:443#格式 或纯文本1", "0.0.0.0:443#格式 或纯文本2"]` | 头部广告内容列表（可填任意格式） |
| `AD_FOOTER_ENABLED` | `boolean` | `false` | 是否在 `ip.txt` 尾部插入自定义广告行 |
| `AD_FOOTER_LINES` | `array` | `["0.0.0.0:443#格式 或纯文本3", "0.0.0.0:443#格式 或纯文本4"]` | 尾部广告内容列表（可填任意格式） |
| `AD_PERLINE_ENABLED` | `boolean` | `false` | 是否在每行节点末尾追加固定文本 |
| `AD_PERLINE_TEXT` | `string` | `" 纯文本"` | 追加到每行节点末尾的文本 |

> 💡 三个开关完全独立，头部/尾部可为多条，行尾为单条固定文本。  
> 开启后只会改变 `ip.txt` 内容，不影响 Cloudflare DNS 更新（DNS 仍使用纯净节点列表）。

#### ip.txt 输出内容控制

控制最终 `ip.txt` 文件中每行节点后是否附带带宽测速、HTTP 延迟、HTTP 抖动和 TCP 延迟信息，方便直接查看或用于其他工具解析。

| 参数 | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `IP_TXT_SHOW_BANDWIDTH` | `boolean` | `false` | 是否附带带宽测速结果（如 ` 5.20 Mbps`） |
| `IP_TXT_SHOW_HTTP_LATENCY` | `boolean` | `false` | 是否附带 HTTP 延迟信息（如 ` 30.00 ms`） |
| `IP_TXT_SHOW_HTTP_JITTER` | `boolean` | `false` | 是否附带 HTTP 抖动信息（如 ` 2.50 ms`） |
| `IP_TXT_SHOW_LATENCY` | `boolean` | `false` | 是否附带 TCP 延迟信息（如 ` 50.30 ms`） |

> 多个开关可以独立或同时开启，输出格式示例：  
> `104.16.0.1:443#US 5.20 Mbps 30.00 ms 2.50 ms 50.30 ms`  
> （对应：速度 HTTP延迟 HTTP抖动 TCP延迟）

</details>

> 💡 **快速配置建议**  
> - 通常只需修改 `ALLOWED_COUNTRIES`、`WXPUSHER_APP_TOKEN`、`WXPUSHER_UIDS`。  
> - 启用 DNS 更新需正确填写 `CF_API_TOKEN`、`CF_ZONE_ID`、`CF_DNS_RECORD_NAME`。  
> - 网络不稳定时可 ↑ `TCP_PROBES` / `TIMEOUT`，↓ `MIN_SUCCESS_RATE` / `MAX_WORKERS`。  
> - 希望更快出结果可 ↓ `BANDWIDTH_CANDIDATES` 或 `BANDWIDTH_SIZE_MB`。

---

## 📊 结果输出说明

程序运行完成后，会在本地生成 `ip.txt` 文件，每行格式为 `IP地址:端口#国家代码`，例如：

> `104.16.x.x:443#US`  
> `162.159.x.x:443#HK`

**重要说明**：  
- `ip.txt` 中保存的是**基于综合加权排序的结果**，综合考虑了带宽、TCP 延迟、HTTP 延迟和抖动，以确保 GitHub 推送的节点列表完整且不丢失任何高速低延迟的 IP。  
- Cloudflare DNS 批量更新环节会额外应用 `FILTER_IPV6_AVAILABILITY`（过滤落地 IPv6）、`BLOCKED_COUNTRIES`（屏蔽特定国家）、`DNS_IP_RISK_FILTER_ENABLED`（IP 风险等级过滤，可设定最高允许等级，过滤后无节点自动回退到无风险过滤列表）等过滤，仅将符合条件的 IP 写入 DNS 记录。

---

## ☁️ 配置 Cloudflare DNS 自动更新

本工具支持将优选出的 IP 地址列表自动更新到 Cloudflare DNS 的同名 A 记录，实现解析层面的多 IP 轮询负载均衡。

### 第一步：获取 Cloudflare API Token 与 Zone ID

1. 按照 [获取必要令牌](#-获取必要令牌重要) 中的步骤获取 **Cloudflare API Token**（需具有 Zone:DNS:Edit 权限）。
2. 在 Cloudflare 域名概览页面右侧复制你的 **Zone ID**。

### 第二步：填写配置文件

编辑 `config.json`，找到 Cloudflare DNS 配置部分，填入你的信息：

```json
"CF_ENABLED": true,
"CF_API_TOKEN": "your_CF_API_TOKEN",
"CF_ZONE_ID": "your_CF_ZONE_ID",
"CF_DNS_RECORD_NAME": "your_CF_DNS_RECORD_NAME",
"CF_TTL": 60,
"CF_PROXIED": false
```

| 参数 | 说明 |
|------|------|
| `CF_ENABLED` | 设为 `true` 启用 DNS 自动更新 |
| `CF_API_TOKEN` | 上一步获取的 API Token |
| `CF_ZONE_ID` | 上一步获取的 Zone ID |
| `CF_DNS_RECORD_NAME` | 要更新的完整子域名 |
| `CF_TTL` | DNS 记录 TTL（秒），免费套餐最低 120 |
| `CF_PROXIED` | 是否启用 Cloudflare CDN 代理（橙色云朵），通常设为 `false` |

> 💡 若不需要 DNS 更新功能，将 `CF_ENABLED` 设为 `false` 即可。

### 第三步：测试运行

1. 手动运行一次优选程序：`python main.py`（Windows）或 `python3 main.py`（Linux）。
2. 程序运行结束后，观察控制台输出。若看到 `✅ Cloudflare DNS 批量更新成功！`，则配置成功。

### 工作原理

每次运行时，脚本会：

1. 查询目标子域名下现有的所有 A 记录。
2. 从带宽测速结果中按速度顺序挑选落地 IPv4 的节点（若启用 `FILTER_IPV6_AVAILABILITY`）。
3. 组装一个原子批量请求：同时删除所有旧记录并创建全部新记录。

### 注意事项

- 免费套餐单次批量操作最多支持 200 条记录，足够使用。
- 若候选池中落地 IPv4 节点不足目标数量，则更新实际可用的数量，不会强制凑满。
- 使用原子批量 API，单次请求完成删除和创建，可能存在极短暂的解析真空期（通常 1~5 秒）。

---

## 📤 配置 GitHub 自动同步

同步不再执行 `git pull` 或 `git push --force`，而是通过 GitHub Contents API 读取远端文件当前版本、只替换本终端节点，再带文件 SHA 提交。若其他终端先一步更新导致 SHA 冲突，程序会重新拉取并再次合并。

### 第一步：配置每台终端

每台终端编辑自己的 `config.json`：

```json
"GITHUB_SYNC_TOKEN": "你的 GitHub Token",
"GITHUB_SYNC_REPOSITORY": "uxudjs/BestCfCdn",
"GITHUB_SYNC_BRANCH": "main",
"GITHUB_SYNC_REMOTE_PATH": "ip.txt",
"GITHUB_SYNC_FIELD_ID": "济南联通",
"GITHUB_SYNC_TOP_N": 5
```

`GITHUB_SYNC_FIELD_ID` 必须在所有终端中唯一，例如另一台填写 `郑州教育网`。Fine-grained PAT 仅需给目标仓库授予 **Contents: Read and write**；classic PAT 需要 `repo` 权限。

### 第二步：测试同步

1. 确保项目目录下已有 `ip.txt` 文件（可先手动运行一次 `python main.py` 生成）。
2. 手动执行推送脚本测试：
   - **Windows**：双击运行 `git_sync.ps1` 或在 PowerShell 中执行 `.\git_sync.ps1`
   - **Linux**：执行 `./git_sync.sh`
3. 若终端显示“已安全同步”，则配置成功。之后每次运行 `main.py` 都会自动调用并发安全同步。
4. 远端文件示例：

```text
104.16.0.1:443#US|济南联通
104.16.0.2:443#US|济南联通
162.159.1.1:443#US|郑州教育网
```

每行仍是合法的 `IP:端口#标签`。某终端再次同步时，只替换标签最后一个 `|` 后与自己 `GITHUB_SYNC_FIELD_ID` 完全一致的行，其他内容保持原样。

<details>
<summary>🚨 推送报错常见原因</summary>

| 报错信息 | 原因 | 解决方法 |
|----------|------|----------|
| `401` / `403` | Token 无效或 Contents 权限不足 | 检查 Token 与仓库授权 |
| `404` | 仓库、分支或路径配置错误 | 检查 `GITHUB_SYNC_REPOSITORY` 与 `GITHUB_SYNC_BRANCH` |
| `409` / `422` | 多终端并发更新 | 程序会自动重新拉取合并；持续出现时增加冲突重试次数 |
| 没有有效节点 | 本机 `ip.txt` 尚未生成 | 先运行 `main.py` |
</details>

---

> [!WARNING]
> **关于私有仓库的特别提醒**
> 
> 如果你将仓库设置为 **Private（私有）**，则通过 Raw 链接访问 `ip.txt` 时必须在 URL 后附加 `?token=xxxxxx` 参数才能获取内容，例如：
> ```text
> https://raw.githubusercontent.com/用户名/仓库名/refs/heads/分支名/ip.txt?token=xxxxxx
> ```
> 但请注意，**部分代理工具或订阅解析器可能无法正确处理带 Token 参数的 URL**，原因包括：
> - 不支持自定义请求头（GitHub 要求完整的 User-Agent 等头信息）
> - 无法解析带查询参数的链接
> - 防火墙或网络环境限制
> 
> **因此，如果你希望将 `ip.txt` 作为订阅链接供代理工具使用，强烈建议将仓库设为 Public（公开）。**
> 
> 公开仓库的 Raw 链接无需 Token 即可访问，兼容性最佳：
> ```text
> https://raw.githubusercontent.com/用户名/仓库名/refs/heads/分支名/ip.txt
> ```

### 验证与订阅

推送成功后，访问 `https://raw.githubusercontent.com/你的用户名/仓库名/refs/heads/分支名/ip.txt` 即可获取最新节点列表，供代理工具订阅使用。

> 💡 若不需要 GitHub 同步功能，可在 `config.json` 中设置 `GITHUB_SYNC_MAX_RETRIES: 0` 即可关闭。

---

## 🚀 对接 EdgeTunnel (2.0+) 指南

**EdgeTunnel** (EDTunnel) 是基于 Cloudflare Workers 的隧道工具。使用本项目筛选出的 `ip.txt` 可以显著提升连接速度和稳定性。

### 方法一：优选订阅模式（推荐）

1. 复制你的 GitHub Raw 链接：
   ```text
   https://raw.githubusercontent.com/你的用户名/仓库名/refs/heads/分支名/ip.txt
   ```
2. 打开 EdgeTunnel 控制面板，点击菜单栏的 **“优选订阅生成”**。
3. 在 **“优选订阅模式”** 区域，选择 **“自定义订阅（支持汇聚订阅）”**。
4. 点击 **“订阅接口”** 按钮，在 **API URL** 输入框中粘贴上一步获取的 GitHub Raw 链接。
   > 💡 如需指定端口，可在链接后添加 `?port=443`。
5. （可选）勾选 **“将优选作为 PROXYIP”**。
6. 点击 **“可用性验证”**，系统将验证 API 并拉取节点列表。
7. 检查无误后，点击 **“追加API”** 按钮将链接加入自定义订阅地址。
8. 点击 **“保存”** 按钮完成配置。

### 方法二：手动替换 EdgeTunnel 节点配置

1. 打开 EdgeTunnel 控制面板，点击菜单栏的 **“优选订阅生成”**。
2. 在 **“优选订阅模式”** 区域，选择 **“自定义订阅（支持汇聚订阅）”**。
3. 在 **“自定义订阅地址”** 输入框中直接粘贴节点地址，每行一个，例如：
   ```text
   104.16.x.x:443#US
   162.159.x.x:443#HK
   ```
4. 点击 **“保存”** 按钮，即可手动指定优选的节点列表。

### 方法三：使用 Cloudflare DNS 域名（推荐）

如果你已启用 Cloudflare DNS 批量更新，可以直接将你的子域名（如 `cf.yourdomain.com`）填入 EdgeTunnel：

**方式一：通过“优选订阅生成”**
1. 打开 **“优选订阅生成”** 页面，选择 **“自定义订阅（支持汇聚订阅）”**。
2. 在 **“自定义订阅地址”** 输入框中，填入你的子域名（例如 `cf.yourdomain.com`）。
3. 点击 **“保存”** 按钮。

**方式二：通过“Cloudflare CDN 访问设置”**
1. 进入 **“Cloudflare CDN 访问设置”** 页面。
2. 在 **“PROXYIP”** 输入框中，填入你的子域名（例如 `cf.yourdomain.com`）。
3. 点击 **“保存”** 按钮。

该域名会自动解析到当前最优的多个 IP 之一，实现零配置动态切换。

### 💡 为什么这样对接更有效？
- **低延迟**：`main.py` 已经通过 TCP 握手筛选出了延迟最低的节点。
- **高带宽**：结果经过真实 `curl` 下载测试，排在前面的节点具有更强的并发吞吐能力。
- **高可用**：通过 `AVAILABILITY_CHECK_API` 过滤了那些能 Ping 通但无法正常通过代理请求的无效 IP。
- **自动更新**：DNS 记录随优选结果自动刷新，无需手动修改配置。

### 注意事项
- **GitHub 缓存**：GitHub Raw 链接有一定的 CDN 缓存时间（通常为 5 分钟左右）。如果刚运行完脚本发现链接内容没变，请稍等片刻。
- **网络环境**：建议在你的主运行环境（如家庭软路由或主力 PC）运行此脚本，因为不同网络环境下筛选出的最优 IP 可能不同。
- **DNS 生效时间**：修改 DNS 记录后受 TTL 影响，全球生效可能需要几分钟，但通常 Cloudflare 更新是实时的。

---

## ❓ 常见问题

<details>
<summary>🌐 代理环境影响</summary>

**会影响，尤其全局/TUN 模式。**

| 测试阶段 | 是否走代理 | 说明 |
| :--- | :--- | :--- |
| TCP 延迟测试 (Socket) | ❌ 直连 | 反映本机到节点的 RTT |
| HTTP 检测 (requests) | ❌ 直连 | 过滤非Cloudflare节点 |
| 带宽测速 (curl) | ❌ 直连 | 反映本机到 CDN 的速度 |
| API 请求类 (requests) | ✅ 跟随系统代理 | 获取节点、可用性、微信通知等 |
| Git 推送 (git) | ✅ 跟随系统代理 | 涉及 `github.com` 等 |

> 各阶段对应域名见上方“涉及域名”列表。

**涉及域名：**  
`cm.edu.kg` · `ipinfo.io` · `090227.xyz` · `cloudflare.com` · `zjiecode.com` · `pages.dev` · `ipapi.is` · `github.com` · `githubusercontent.com`

**建议：**  
1. 检查本机能否直连上述域名 → 能通设 `DIRECT`，不通设 `PROXY`  
2. **运行程序时关闭全局模式 / TUN 模式**  
3. 不确定网络情况就直接**退出代理工具再运行**

</details>

<details>
<summary>🔌 依赖与安装</summary>

1. **提示 `ModuleNotFoundError: No module named 'requests'` 或访问 PyPI 超时**
   Windows：
   ```powershell
   .\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
   .\.venv\Scripts\python.exe -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple brotlicffi
   ```
   Linux：
   ```bash
   ./.venv/bin/python -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple -r requirements.txt
   ./.venv/bin/python -m pip install --timeout 120 --retries 10 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple brotlicffi
   ```

2. **带宽测速被跳过**  
   请确保系统已安装 `curl` 且位于 PATH 环境变量中。

3. **Linux 下 `git_sync.sh` 权限被拒绝**  
   执行 `chmod +x git_sync.sh` 赋予执行权限。

</details>

<details>
<summary>📤 GitHub 推送与同步</summary>

4. **GitHub 推送失败**  
   - 检查 `config.json` 中的 Token、仓库、分支和终端名称是否正确。
   - 确保 fine-grained Token 具备 Contents 读写权限，或 classic Token 具备 `repo` 权限。

5. **GitHub 推送时提示权限错误或 403**  
   - 请确认令牌具有 `repo` 权限，且未过期。创建令牌时务必勾选 **repo** 全部子项，并将过期时间设为 **No expiration**。

6. **多个终端会互相覆盖吗？**
   - 不会。程序按 `GITHUB_SYNC_FIELD_ID` 只替换本终端节点，并用文件 SHA 检测并发冲突后重新合并。

7. **为什么远端标签多了 `|济南联通`？**
   - 这是终端所有权标识，仍属于 `IP:端口#标签` 格式，用于下一次精准替换本终端字段。

</details>

<details>
<summary>☁️ Cloudflare DNS 更新</summary>

8. **Cloudflare DNS 更新失败**  
   - 检查 `CF_API_TOKEN` 权限、`CF_ZONE_ID`、`CF_DNS_RECORD_NAME` 是否正确。  
   - 程序内置重试机制，全部失败时会通过微信通知（如已启用）。

9. **为什么我的 DNS 记录数量少于 `DNS_UPDATE_TARGET_COUNT`？**  
   如果你启用了 `FILTER_IPV6_AVAILABILITY`，且候选池中符合端口、落地类型、国家过滤等条件的节点总数不足你设定的 DNS 更新目标数量，则 DNS 只会更新实际可用的节点数。这是正常现象，你可以通过增加 `BANDWIDTH_CANDIDATES` 来扩大候选池。

10. **开启了风险等级过滤，但 DNS 更新似乎没有按预期过滤？**  
    - 检查 `DNS_IP_RISK_FILTER_ENABLED` 是否为 `true`，以及 `DNS_IP_RISK_MAX_LEVEL` 是否设置正确。  
    - 若 API 请求失败或所有节点均被过滤，程序会**自动回退到无风险过滤的列表**，并发送微信通知。  
    - 可以查看运行日志中的过滤统计信息确认过滤数量。

</details>

<details>
<summary>🔍 检测与过滤</summary>

11. **TCP 测试无节点通过**  
若所有节点的 TCP 连接成功率均低于 `MIN_SUCCESS_RATE`，程序将直接退出并提示检查网络或降低成功率阈值。此为第一道硬性门槛，无回退机制。

12. **可用性检测全部失败**  
若 API 接口异常导致可用性检测通过率为 0%，程序会自动跳过此步骤并回退到 TCP 筛选结果，同时发送微信提醒（如已配置）。

13. **HTTP检测全部失败**  
若所有候选节点均返回非 `400` / `cloudflare` 或连接失败，程序将降级使用过滤前列表（即可用性检测通过的结果），并发送微信通知（如已启用）。

14. **带宽测速全部失败**  
若 curl 测速多次重试仍无有效带宽数据，程序将回退到 TCP 延迟排序结果作为最终优选节点，并发送微信通知。

</details>

<details>
<summary>🗺️ IP 地区校准</summary>

15. **IP 地区校准是做什么的？**  
    - 程序会通过 ipinfo.io 查询每个节点 IP 的真实国家代码、城市和 ISP，并缓存到 `ipinfo_cache.txt`。
    - 校准后节点标签只保留国家代码（如 `#HK`），不影响原有筛选逻辑。

16. **校准速度很慢怎么办？**  
    - 可适当降低 `IP_CALIBRATION_CONCURRENCY`（如 100），或增加 `IP_CALIBRATION_MIN_INTERVAL`（如 0.15）。
    - 若不需要校准，将 `IP_CALIBRATION_ENABLED` 设为 `false` 即可跳过。

17. **收到"token可能已耗尽"的微信通知？**  
    - 只有所有 Token 都触发 ipinfo.io 的速率限制（429）时才会发送此通知，单个 Token 被限速会自动切换，不影响查询。
    - 可在 [ipinfo.io](https://ipinfo.io/) 申请更多免费 Token 放入 `valid_tokens.txt`。

</details>

<details>
<summary>🔒 隐私与其他</summary>

18. **隐私保护**  
   自动生成的 `.gitignore` 文件会忽略 `config.json`、`git_sync.ps1` 和 `git_sync.sh`，防止敏感信息被提交到公开仓库。

</details>

---

## 🙏 致谢

- 节点数据源 & 检测 API：[cmliussss](https://github.com/cmliussss)
- IP 风险检测 API：[ipapi.is](https://ipapi.is/)
- IP 地区校准：[ipinfo.io](https://ipinfo.io/)
- 微信通知服务：[WxPusher](https://wxpusher.zjiecode.com/)

---

**许可证**：本项目采用 [MIT License](https://opensource.org/licenses/MIT) 开源。
