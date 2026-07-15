# BestCfCdn

### 🌐 选择语言 | 選擇語言 | Choose Language

- [🇨🇳 简体中文](#-简体中文)
- [🇹🇼 繁體中文](#-繁體中文)
- [🇺🇸 English](#-english)

---

## 🇨🇳 简体中文

面向 Cloudflare CDN 与 EdgeTunnel 代理场景的跨平台 IP 自动优选工具。

### 主要功能

- ✅ **多源聚合** - 自动解析文本、JSON、中文地区名和 emoji 国旗等节点格式
- ⚡ **分层检测** - 依次检查 TCP 成功率、代理可用性、HTTP 延迟、抖动和真实带宽
- ⚖️ **体验评分** - 综合响应速度、稳定性和带宽，避免只追求单项最高值
- 🏆 **最优输出** - 全局模式默认保留综合体验最好的 5 个节点
- 📤 **多终端同步** - 每台终端只替换远端 `ip.txt` 中属于自己的记录
- ⏱️ **峰谷调度** - 北京时间 18:00–24:00 每 15 分钟运行，其余时段每 30 分钟运行
- 🖥️ **一键部署** - setup 自动更新代码、创建 `.venv`、安装依赖并管理定时任务
- ☁️ **可选发布** - 支持 GitHub、Cloudflare DNS 和 WxPusher 异常通知

### 安装使用

#### 1. 获取项目

需要 GitHub 汇总结果时，先 Fork 本仓库作为结果仓库。推荐克隆上游项目，让 setup 可以直接获取更新。

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

如果克隆自己的 Fork，请先在 GitHub 使用 `Sync fork` 同步上游。ZIP 版本可以运行，但不支持 setup 自动更新。

#### 2. 首次运行 setup

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

Linux：

```bash
bash setup.sh
```

首次运行只会生成 `config.json` 并退出，请先修改配置。

#### 3. 修改 config.json

- `GITHUB_SYNC_FIELD_ID` - 使用不含个人信息的别名，例如 `device-a`；该值会出现在公开的 `ip.txt` 中
- `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` - 启用 GitHub 同步时填写
- `GITHUB_SYNC_MAX_RETRIES` - 不使用 GitHub 同步时设为 `0`
- `ENABLE_SCHEDULED_TASK` - `true` 自动运行；`false` 仅手动运行
- `CF_ENABLED` - 启用 DNS 更新时填写 Cloudflare Token、Zone ID 和记录名称
- `ENABLE_WXPUSHER` - 启用异常通知时填写 App Token 和 UID

`GITHUB_SYNC_FIELD_ID` 不能包含任何空白字符、`|` 或 `#`。不要把真实 Token 提交到 GitHub。

#### 4. 完成部署

保存配置后再次运行 setup。脚本会创建项目虚拟环境、安装依赖、应用定时设置，并询问是否立即测试。

### 运行说明

手动运行：

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- 🔄 **自动模式** - `ENABLE_SCHEDULED_TASK=true`；无需手动激活 `.venv`
- ⏸️ **手动模式** - 改为 `false` 后重新运行 setup，已有定时任务会被清除
- 📄 **本地结果** - 当前终端结果保存在 `ip.local.txt`
- 🌐 **远端结果** - 多终端汇总保存在 GitHub `ip.txt`，每个终端默认最多上传 5 行
- 🔐 **配置安全** - `config.json` 会被 Git 忽略，但仍是明文文件，请使用最小权限 Token
- 🧩 **DNS 模式** - `TXT` 保存 `IP:端口`；`A` 保存纯 IPv4，作为入口域名时保持 `CF_PROXIED=false`

### 适用范围

- ✅ Windows 10 / 11
- ✅ 常见 Linux 发行版
- ✅ Python 3.9 或更高版本、Git 与 curl
- ✅ Cloudflare CDN、EdgeTunnel 等入口节点优选场景
- ✅ [MIT License](./LICENSE)

---

## 🇹🇼 繁體中文

面向 Cloudflare CDN 與 EdgeTunnel 代理情境的跨平台 IP 自動優選工具。

### 主要功能

- ✅ **多來源彙整** - 自動解析文字、JSON、中文地區名稱和 emoji 國旗等節點格式
- ⚡ **分層檢測** - 依序檢查 TCP 成功率、代理可用性、HTTP 延遲、抖動和真實頻寬
- ⚖️ **體驗評分** - 綜合回應速度、穩定性和頻寬，避免只追求單項最高值
- 🏆 **最佳輸出** - 全域模式預設保留綜合體驗最好的 5 個節點
- 📤 **多終端同步** - 每台終端只替換遠端 `ip.txt` 中屬於自己的記錄
- ⏱️ **峰谷排程** - 北京時間 18:00–24:00 每 15 分鐘執行，其餘時段每 30 分鐘執行
- 🖥️ **一鍵部署** - setup 自動更新程式碼、建立 `.venv`、安裝依賴並管理排程任務
- ☁️ **可選發佈** - 支援 GitHub、Cloudflare DNS 和 WxPusher 異常通知

### 安裝使用

#### 1. 取得專案

需要 GitHub 彙總結果時，先 Fork 本倉庫作為結果倉庫。建議複製上游專案，讓 setup 可以直接取得更新。

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

如果複製自己的 Fork，請先在 GitHub 使用 `Sync fork` 同步上游。ZIP 版本可以執行，但不支援 setup 自動更新。

#### 2. 首次執行 setup

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

Linux：

```bash
bash setup.sh
```

首次執行只會產生 `config.json` 並退出，請先修改設定。

#### 3. 修改 config.json

- `GITHUB_SYNC_FIELD_ID` - 使用不含個人資訊的別名，例如 `device-a`；該值會出現在公開的 `ip.txt` 中
- `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` - 啟用 GitHub 同步時填寫
- `GITHUB_SYNC_MAX_RETRIES` - 不使用 GitHub 同步時設為 `0`
- `ENABLE_SCHEDULED_TASK` - `true` 自動執行；`false` 僅手動執行
- `CF_ENABLED` - 啟用 DNS 更新時填寫 Cloudflare Token、Zone ID 和記錄名稱
- `ENABLE_WXPUSHER` - 啟用異常通知時填寫 App Token 和 UID

`GITHUB_SYNC_FIELD_ID` 不能包含任何空白字元、`|` 或 `#`。不要把真實 Token 提交到 GitHub。

#### 4. 完成部署

儲存設定後再次執行 setup。腳本會建立專案虛擬環境、安裝依賴、套用排程設定，並詢問是否立即測試。

### 執行說明

手動執行：

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- 🔄 **自動模式** - `ENABLE_SCHEDULED_TASK=true`；不需要手動啟用 `.venv`
- ⏸️ **手動模式** - 改為 `false` 後重新執行 setup，已有排程任務會被清除
- 📄 **本機結果** - 目前終端結果儲存在 `ip.local.txt`
- 🌐 **遠端結果** - 多終端彙總儲存在 GitHub `ip.txt`，每個終端預設最多上傳 5 行
- 🔐 **設定安全** - `config.json` 會被 Git 忽略，但仍是明文檔案，請使用最小權限 Token
- 🧩 **DNS 模式** - `TXT` 儲存 `IP:連接埠`；`A` 儲存純 IPv4，作為入口網域時保持 `CF_PROXIED=false`

### 適用範圍

- ✅ Windows 10 / 11
- ✅ 常見 Linux 發行版
- ✅ Python 3.9 或更高版本、Git 與 curl
- ✅ Cloudflare CDN、EdgeTunnel 等入口節點優選情境
- ✅ [MIT License](./LICENSE)

---

## 🇺🇸 English

A cross-platform IP selection tool for Cloudflare CDN and EdgeTunnel proxy scenarios.

### Features

- ✅ **Multi-source aggregation** - Parses node lists in text, JSON, Chinese region names, emoji flags, and other common formats
- ⚡ **Layered checks** - Tests TCP success rate, proxy availability, HTTP latency, jitter, and real bandwidth
- ⚖️ **Experience scoring** - Balances responsiveness, stability, and bandwidth instead of maximizing one metric
- 🏆 **Best endpoint output** - Keeps the five best overall endpoints by default
- 📤 **Multi-device sync** - Each device replaces only its own lines in the remote `ip.txt`
- ⏱️ **Peak/off-peak schedule** - Runs every 15 minutes from 18:00 to 24:00 Beijing time and every 30 minutes otherwise
- 🖥️ **One-command setup** - Setup updates code, creates `.venv`, installs dependencies, and manages scheduled tasks
- ☁️ **Optional publishing** - Supports GitHub, Cloudflare DNS, and WxPusher error notifications

### Installation

#### 1. Get the project

To aggregate results on GitHub, fork this repository as the result repository. Clone the upstream project so setup can retrieve updates directly.

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

If you clone your own fork, use GitHub's `Sync fork` first. ZIP copies can run but do not support automatic updates through setup.

#### 2. Run setup for the first time

Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

Linux:

```bash
bash setup.sh
```

The first run only creates `config.json` and exits. Edit the configuration before continuing.

#### 3. Edit config.json

- `GITHUB_SYNC_FIELD_ID` - Use a non-identifying alias such as `device-a`; this value appears in public `ip.txt`
- `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` - Fill these in when GitHub sync is enabled
- `GITHUB_SYNC_MAX_RETRIES` - Set to `0` when GitHub sync is not needed
- `ENABLE_SCHEDULED_TASK` - `true` for automatic runs or `false` for manual-only mode
- `CF_ENABLED` - When enabling DNS updates, fill in the Cloudflare token, Zone ID, and record name
- `ENABLE_WXPUSHER` - When enabling error notifications, fill in the App Token and UID

`GITHUB_SYNC_FIELD_ID` cannot contain whitespace, `|`, or `#`. Never commit a real token to GitHub.

#### 4. Complete setup

Save the configuration and run setup again. It creates the project virtual environment, installs dependencies, applies scheduling, and asks whether to run a test.

### Usage

Run manually:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- 🔄 **Automatic mode** - Set `ENABLE_SCHEDULED_TASK=true`; `.venv` activation is not required
- ⏸️ **Manual mode** - Set it to `false` and rerun setup to remove existing scheduled tasks
- 📄 **Local results** - Results for the current device are stored in `ip.local.txt`
- 🌐 **Remote results** - Aggregated results are stored in GitHub `ip.txt`, with five lines per device by default
- 🔐 **Configuration safety** - Git ignores `config.json`, but it remains plaintext; use least-privilege tokens
- 🧩 **DNS modes** - `TXT` stores `IP:port`; `A` stores plain IPv4 and should keep `CF_PROXIED=false` for an entry hostname

### Compatibility

- ✅ Windows 10 / 11
- ✅ Common Linux distributions
- ✅ Python 3.9 or newer, Git, and curl
- ✅ Cloudflare CDN, EdgeTunnel, and similar entry-endpoint selection scenarios
- ✅ [MIT License](./LICENSE)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=uxudjs/BestCfCdn&type=Date)](https://star-history.com/#uxudjs/BestCfCdn&Date)
