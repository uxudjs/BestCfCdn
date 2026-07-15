# BestCfCdn

### 🌐 选择语言 | 選擇語言 | Choose Language

- [🇨🇳 简体中文](#-简体中文)
- [🇹🇼 繁體中文](#-繁體中文)
- [🇺🇸 English](#-english)

---

## 🇨🇳 简体中文

面向 Cloudflare CDN 与 EdgeTunnel 代理场景的跨平台 IP 自动优选工具。它负责筛选和发布节点，本身不提供代理服务。

### 主要功能

- ✅ **多源节点聚合** - 自动读取多个公开数据源，并适配普通文本、JSON、中文地区名和 emoji 国旗等格式
- ⚡ **分层质量检测** - 依次进行端口与地区预筛、TCP 成功率、代理可用性、HTTP 延迟、抖动和真实带宽测试
- ⚖️ **代理体验评分** - 以 HTTP 响应体验为主，综合带宽、抖动和 TCP 建连延迟，避免只追求单项最高速度
- 🇨🇳 **中国大陆默认配置** - 默认参数针对中国大陆跨境代理场景设置，并保留完整注释方便调整
- 🏆 **最优节点输出** - 全局模式默认只保留 5 个综合体验最好的节点，也支持按国家筛选
- 📤 **多终端安全同步** - 每台终端只替换远端 `ip.txt` 中属于自己的行，默认最多 5 行且不会覆盖其他终端结果
- ⏱️ **峰谷自动调度** - 默认按北京时间 18:00–24:00 每 15 分钟运行，其余时段每 30 分钟运行，并防止任务重叠
- 🖥️ **一键安装更新** - Windows 和 Linux 均以 setup 为日常唯一入口，自动创建 `.venv`、安装依赖、应用定时设置并安全更新
- ☁️ **可选结果发布** - 支持更新 Cloudflare DNS、同步 GitHub 和发送 WxPusher 异常通知，三项功能可分别配置
- 🔒 **本地配置保护** - 含 Token 的 `config.json` 和本机结果默认不会提交到 Git，更新时会合并并保留有效旧配置

### 安装使用

#### 1. 获取项目

需要把结果同步到 GitHub 时，请先 Fork 本仓库作为结果仓库。为了让 setup 直接获取本项目更新，推荐克隆上游仓库，并在配置中把同步目标指向你自己的 Fork。

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

如果选择克隆自己的 Fork，请先通过 GitHub 的 `Sync fork` 更新该 Fork；setup 只会拉取当前克隆仓库的 `origin/main`，不会代替 GitHub 同步上游。ZIP 版本可以运行，但无法由 setup 自动更新。

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

首次没有 `config.json` 时，setup 会先尝试安全更新，再根据当前版本模板创建配置并退出，不会安装依赖、注册定时任务或立即运行优选。

#### 3. 修改 config.json

打开 setup 生成的 `config.json`，至少检查以下设置：

- `GITHUB_SYNC_MAX_RETRIES` - 需要 GitHub 同步时保持大于 `0`；不需要时设为 `0`
- `GITHUB_SYNC_FIELD_ID` - 启用 GitHub 同步时填写本终端唯一名称，例如 `济南联通`；不能包含任何空白字符、`|` 或 `#`
- `GITHUB_SYNC_TOKEN` - 启用 GitHub 同步时填写仅授权目标仓库 Contents 读写权限的 Fine-grained Token
- `GITHUB_SYNC_REPOSITORY` - 启用 GitHub 同步时填写目标结果仓库，格式为 `用户名/仓库名`
- `ENABLE_SCHEDULED_TASK` - `true` 为自动运行，`false` 为仅手动运行
- `CF_ENABLED` - 默认关闭；启用时填写 `CF_API_TOKEN`、`CF_ZONE_ID` 和 `CF_DNS_RECORD_NAME`，Token 需有区域 DNS 编辑权限，并检查 `DNS_RECORD_TYPE`
- `ENABLE_WXPUSHER` - 默认关闭；启用异常通知时填写 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UIDS`

`DNS_RECORD_TYPE` 默认为 `TXT`，每条记录保存一个 `IP:端口`；只有 `A` 模式会发布纯 IPv4 地址。需要直接把域名作为 EdgeTunnel 入口时使用 `A`，并保持 `CF_PROXIED` 为 `false`。

其余筛选、评分、并发和超时参数都带有中文注释。请只编辑本机 `config.json`；Git 忽略不等于加密，不要把真实 Token 写入 `config.example.json`、提交到 GitHub 或公开在日志中。

#### 4. 再次运行 setup

保存配置后，再运行一次与上一步相同的 setup 命令。脚本会自动创建项目专用 `.venv`、安装依赖并根据配置创建或清理定时任务，最后询问是否立即测试。

以后更新代码、修改定时模式或修复依赖时，仍然只需运行 setup。

#### 5. 手动运行（可选）

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

Linux：

```bash
./.venv/bin/python main.py
```

无需手动激活 `.venv`。手动运行会立即开始优选，不受峰谷时间限制。

### 自动运行与手动模式

`ENABLE_SCHEDULED_TASK` 默认为 `true`。setup 会在 Windows 创建计划任务，在 Linux 创建 cron，并让 `scheduled_run.py` 每 15 分钟检查一次当前属于忙时还是闲时。定时任务只运行优选程序；只有用户运行 setup 时才会检查代码更新。

Windows 计划任务以 `SYSTEM` 身份运行，其代理和网络环境可能与当前用户手动运行 PowerShell 时不同。

将其改为 `false` 后必须重新运行 setup；setup 会清除本项目已经注册的计划任务，但仍可随时手动执行 `main.py`。重新改回 `true` 并运行 setup 即可恢复自动任务。

### 结果与多终端同步

- `ip.local.txt` - 当前终端的本地优选结果，每次运行覆盖
- `ip.txt` - GitHub 上的多终端汇总结果，不会作为本地输入覆盖
- `GITHUB_SYNC_TOP_N` - 单个终端最多上报的节点数，默认为 5
- `GITHUB_SYNC_MAX_RETRIES` - GitHub 自动同步失败时的外层重试次数；设为 `0` 可关闭 GitHub 同步

远端每行会附加终端标识，例如 `IP:端口#地区|济南联通`。同步程序只识别并替换相同 `GITHUB_SYNC_FIELD_ID` 的行；多个终端同时写入时会重新拉取、合并并重试。

公开结果仓库可通过 `https://raw.githubusercontent.com/<用户名>/BestCfCdn/refs/heads/main/ip.txt` 读取汇总文件。私有仓库不要把 Token 拼接到 URL 查询参数中，应使用支持 `Authorization` 请求头的客户端，或改用 Cloudflare DNS 发布结果。

### 常见问题

#### setup 会自动使用虚拟环境吗？

会。setup 会优先使用项目中的 `.venv`，不存在时自动创建；计划任务也会直接调用该环境中的 Python。

#### GitHub 暂时无法访问时还能部署吗？

可以。自动更新遇到单纯网络故障时会继续使用当前本地版本；如果检测到配置和结果文件之外的本地代码改动、分支分叉或配置损坏等风险，setup 会停止，避免覆盖本机文件。

#### 已有旧版 config.json 会被覆盖吗？

不会直接覆盖。安全更新成功后会把新版模板中的新增字段补入，同时保留仍受支持的本机值。非常旧的安装第一次升级时，可先运行一次 `update_fork.ps1` 或 `update_fork.sh`，之后只使用 setup。

#### 为什么改为手动模式后任务仍然存在？

修改 `ENABLE_SCHEDULED_TASK` 后还需要重新运行 setup，脚本才会应用设置并删除旧任务。

#### GitHub 同步失败应该检查什么？

确认 Token 具有 Contents 读写权限、仓库名和分支正确、`GITHUB_SYNC_FIELD_ID` 合法，并检查当前网络是否能够访问 GitHub。不要在 Issue 或日志中公开 Token。

#### 为什么不推荐 ZIP 安装？

ZIP 版本缺少 Git 历史，setup 会跳过自动更新。希望长期只操作 setup 时，请使用 Git 克隆版本。

### 适用范围

- ✅ Windows 10 / 11 与常见 Linux 发行版
- ✅ Python 3.9 或更高版本、Git 与 curl
- ✅ Cloudflare CDN、EdgeTunnel 等需要优选入口节点的代理场景
- ✅ 单终端本地筛选或多地区、多运营商终端联合维护
- ✅ 项目采用 [MIT License](./LICENSE)

---

## 🇹🇼 繁體中文

面向 Cloudflare CDN 與 EdgeTunnel 代理情境的跨平台 IP 自動優選工具。它負責篩選和發佈節點，本身不提供代理服務。

### 主要功能

- ✅ **多來源節點彙整** - 自動讀取多個公開資料來源，並適配一般文字、JSON、中文地區名稱和 emoji 國旗等格式
- ⚡ **分層品質檢測** - 依序進行連接埠與地區預篩、TCP 成功率、代理可用性、HTTP 延遲、抖動和真實頻寬測試
- ⚖️ **代理體驗評分** - 以 HTTP 回應體驗為主，綜合頻寬、抖動和 TCP 連線延遲，避免只追求單項最高速度
- 🇨🇳 **中國大陸預設設定** - 預設參數針對中國大陸跨境代理情境設定，並保留完整註解方便調整
- 🏆 **最佳節點輸出** - 全域模式預設只保留 5 個綜合體驗最好的節點，也支援按國家篩選
- 📤 **多終端安全同步** - 每台終端只替換遠端 `ip.txt` 中屬於自己的行，預設最多 5 行且不會覆蓋其他終端結果
- ⏱️ **峰谷自動排程** - 預設按北京時間 18:00–24:00 每 15 分鐘執行，其餘時段每 30 分鐘執行，並防止任務重疊
- 🖥️ **一鍵安裝更新** - Windows 和 Linux 均以 setup 為日常唯一入口，自動建立 `.venv`、安裝依賴、套用排程設定並安全更新
- ☁️ **可選結果發佈** - 支援更新 Cloudflare DNS、同步 GitHub 和傳送 WxPusher 異常通知，三項功能可分別設定
- 🔒 **本機設定保護** - 含 Token 的 `config.json` 和本機結果預設不會提交到 Git，更新時會合併並保留有效舊設定

### 安裝使用

#### 1. 取得專案

需要把結果同步到 GitHub 時，請先 Fork 本倉庫作為結果倉庫。為了讓 setup 直接取得本專案更新，建議複製上游倉庫，並在設定中把同步目標指向你自己的 Fork。

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

如果選擇複製自己的 Fork，請先透過 GitHub 的 `Sync fork` 更新該 Fork；setup 只會拉取目前複製倉庫的 `origin/main`，不會代替 GitHub 同步上游。ZIP 版本可以執行，但無法由 setup 自動更新。

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

首次沒有 `config.json` 時，setup 會先嘗試安全更新，再依照目前版本範本建立設定並退出，不會安裝依賴、註冊排程任務或立即執行優選。

#### 3. 修改 config.json

開啟 setup 產生的 `config.json`，至少檢查以下設定：

- `GITHUB_SYNC_MAX_RETRIES` - 需要 GitHub 同步時保持大於 `0`；不需要時設為 `0`
- `GITHUB_SYNC_FIELD_ID` - 啟用 GitHub 同步時填寫本終端唯一名稱，例如 `濟南聯通`；不能包含任何空白字元、`|` 或 `#`
- `GITHUB_SYNC_TOKEN` - 啟用 GitHub 同步時填寫僅授權目標倉庫 Contents 讀寫權限的 Fine-grained Token
- `GITHUB_SYNC_REPOSITORY` - 啟用 GitHub 同步時填寫目標結果倉庫，格式為 `使用者名稱/倉庫名稱`
- `ENABLE_SCHEDULED_TASK` - `true` 為自動執行，`false` 為僅手動執行
- `CF_ENABLED` - 預設關閉；啟用時填寫 `CF_API_TOKEN`、`CF_ZONE_ID` 和 `CF_DNS_RECORD_NAME`，Token 需有區域 DNS 編輯權限，並檢查 `DNS_RECORD_TYPE`
- `ENABLE_WXPUSHER` - 預設關閉；啟用異常通知時填寫 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UIDS`

`DNS_RECORD_TYPE` 預設為 `TXT`，每筆記錄儲存一個 `IP:連接埠`；只有 `A` 模式會發佈純 IPv4 位址。需要直接把網域作為 EdgeTunnel 入口時使用 `A`，並保持 `CF_PROXIED` 為 `false`。

其餘篩選、評分、並行和逾時參數都有中文註解。請只編輯本機 `config.json`；Git 忽略不等於加密，不要把真實 Token 寫入 `config.example.json`、提交到 GitHub 或公開在日誌中。

#### 4. 再次執行 setup

儲存設定後，再執行一次與上一步相同的 setup 指令。腳本會自動建立專案專用 `.venv`、安裝依賴並依照設定建立或清理排程任務，最後詢問是否立即測試。

以後更新程式碼、修改排程模式或修復依賴時，仍然只需執行 setup。

#### 5. 手動執行（可選）

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

Linux：

```bash
./.venv/bin/python main.py
```

不需要手動啟用 `.venv`。手動執行會立即開始優選，不受峰谷時間限制。

### 自動執行與手動模式

`ENABLE_SCHEDULED_TASK` 預設為 `true`。setup 會在 Windows 建立排程任務，在 Linux 建立 cron，並讓 `scheduled_run.py` 每 15 分鐘檢查一次目前屬於忙時還是閒時。排程任務只執行優選程式；只有使用者執行 setup 時才會檢查程式碼更新。

Windows 排程任務以 `SYSTEM` 身分執行，其代理和網路環境可能與目前使用者手動執行 PowerShell 時不同。

將其改為 `false` 後必須重新執行 setup；setup 會清除本專案已經註冊的排程任務，但仍可隨時手動執行 `main.py`。重新改回 `true` 並執行 setup 即可恢復自動任務。

### 結果與多終端同步

- `ip.local.txt` - 目前終端的本機優選結果，每次執行覆蓋
- `ip.txt` - GitHub 上的多終端彙總結果，不會作為本機輸入覆蓋
- `GITHUB_SYNC_TOP_N` - 單一終端最多上報的節點數，預設為 5
- `GITHUB_SYNC_MAX_RETRIES` - GitHub 自動同步失敗時的外層重試次數；設為 `0` 可關閉 GitHub 同步

遠端每行會附加終端標識，例如 `IP:連接埠#地區|濟南聯通`。同步程式只識別並替換相同 `GITHUB_SYNC_FIELD_ID` 的行；多個終端同時寫入時會重新拉取、合併並重試。

公開結果倉庫可透過 `https://raw.githubusercontent.com/<使用者名稱>/BestCfCdn/refs/heads/main/ip.txt` 讀取彙總檔案。私有倉庫不要把 Token 串接到 URL 查詢參數中，應使用支援 `Authorization` 請求標頭的用戶端，或改用 Cloudflare DNS 發佈結果。

### 常見問題

#### setup 會自動使用虛擬環境嗎？

會。setup 會優先使用專案中的 `.venv`，不存在時自動建立；排程任務也會直接呼叫該環境中的 Python。

#### GitHub 暫時無法存取時還能部署嗎？

可以。自動更新遇到單純網路故障時會繼續使用目前本機版本；如果偵測到設定和結果檔案之外的本機程式碼改動、分支分叉或設定損壞等風險，setup 會停止，避免覆蓋本機檔案。

#### 已有舊版 config.json 會被覆蓋嗎？

不會直接覆蓋。安全更新成功後會把新版範本中的新增欄位補入，同時保留仍受支援的本機值。非常舊的安裝第一次升級時，可先執行一次 `update_fork.ps1` 或 `update_fork.sh`，之後只使用 setup。

#### 為什麼改為手動模式後任務仍然存在？

修改 `ENABLE_SCHEDULED_TASK` 後還需要重新執行 setup，腳本才會套用設定並刪除舊任務。

#### GitHub 同步失敗應該檢查什麼？

確認 Token 具有 Contents 讀寫權限、倉庫名稱和分支正確、`GITHUB_SYNC_FIELD_ID` 合法，並檢查目前網路是否能夠存取 GitHub。不要在 Issue 或日誌中公開 Token。

#### 為什麼不建議 ZIP 安裝？

ZIP 版本缺少 Git 歷史，setup 會略過自動更新。希望長期只操作 setup 時，請使用 Git 複製版本。

### 適用範圍

- ✅ Windows 10 / 11 與常見 Linux 發行版
- ✅ Python 3.9 或更高版本、Git 與 curl
- ✅ Cloudflare CDN、EdgeTunnel 等需要優選入口節點的代理情境
- ✅ 單終端本機篩選或多地區、多營運商終端聯合維護
- ✅ 專案採用 [MIT License](./LICENSE)

---

## 🇺🇸 English

A cross-platform IP selection tool for Cloudflare CDN and EdgeTunnel proxy scenarios. It selects and publishes endpoints; it is not a proxy service itself.

### Features

- ✅ **Multi-source aggregation** - Reads multiple public sources and adapts to plain text, JSON, Chinese region names, emoji flags, and other common formats
- ⚡ **Layered quality checks** - Applies port and region prefilters, TCP success-rate checks, proxy availability tests, HTTP latency and jitter measurements, and real bandwidth tests
- ⚖️ **Proxy experience scoring** - Prioritizes HTTP responsiveness while balancing bandwidth, jitter, and TCP connection latency instead of maximizing one metric
- 🇨🇳 **Mainland China defaults** - Ships with defaults tuned for cross-border proxy use from mainland China, with inline comments for further adjustment
- 🏆 **Best endpoint output** - Keeps the five best overall endpoints by default and also supports per-country selection
- 📤 **Safe multi-device sync** - Each device replaces only its own lines in the remote `ip.txt`, with a default limit of five and no overwrites of other devices
- ⏱️ **Peak/off-peak scheduling** - Runs every 15 minutes from 18:00 to 24:00 Beijing time and every 30 minutes otherwise, with overlap protection
- 🖥️ **One-command setup and updates** - Uses setup as the only routine entrypoint on Windows and Linux to create `.venv`, install dependencies, apply scheduling, and update safely
- ☁️ **Optional result publishing** - Can update Cloudflare DNS, sync to GitHub, and send WxPusher error notifications, with each feature configured independently
- 🔒 **Local configuration protection** - Keeps token-bearing `config.json` and local results out of Git and merges supported local values during updates

### Installation

#### 1. Get the project

To sync results to GitHub, first fork this repository to create a result repository. To let setup retrieve project updates directly, clone the upstream repository and point the sync configuration to your own fork.

```bash
git clone https://github.com/uxudjs/BestCfCdn.git
cd BestCfCdn
```

If you clone your own fork instead, update it with GitHub's `Sync fork` first. Setup pulls only the cloned repository's `origin/main`; it does not synchronize the upstream repository on GitHub. A ZIP copy can run but cannot be updated automatically by setup.

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

When `config.json` is missing, setup first attempts a safe update, creates the file from the current version's template, and exits. It does not install dependencies, register a scheduled task, or start endpoint selection.

#### 3. Edit config.json

Open the generated `config.json` and review at least these settings:

- `GITHUB_SYNC_MAX_RETRIES` - Keep it above `0` when GitHub sync is needed; set it to `0` otherwise
- `GITHUB_SYNC_FIELD_ID` - When GitHub sync is enabled, set a unique device name such as `Jinan-Unicom`; it cannot contain whitespace, `|`, or `#`
- `GITHUB_SYNC_TOKEN` - When GitHub sync is enabled, use a fine-grained token limited to Contents read and write access on the target repository
- `GITHUB_SYNC_REPOSITORY` - When GitHub sync is enabled, set the target result repository in `owner/repository` format
- `ENABLE_SCHEDULED_TASK` - `true` for automatic runs or `false` for manual-only mode
- `CF_ENABLED` - Disabled by default; when enabled, fill in `CF_API_TOKEN`, `CF_ZONE_ID`, and `CF_DNS_RECORD_NAME`, grant the token Zone DNS edit access, and review `DNS_RECORD_TYPE`
- `ENABLE_WXPUSHER` - Disabled by default; when enabling error notifications, fill in `WXPUSHER_APP_TOKEN` and `WXPUSHER_UIDS`

`DNS_RECORD_TYPE` defaults to `TXT`, with one `IP:port` value in each record; only `A` mode publishes plain IPv4 addresses. To use the hostname directly as an EdgeTunnel entrypoint, select `A` and keep `CF_PROXIED` set to `false`.

All other filtering, scoring, concurrency, and timeout options include inline comments. Edit only your local `config.json`; Git exclusion is not encryption, so never put a real token in `config.example.json`, commit it to GitHub, or expose it in logs.

#### 4. Run setup again

Save the configuration and run the same setup command again. The script creates the project `.venv`, installs dependencies, creates or removes the scheduled task according to the configuration, and then asks whether to run a test.

For future code updates, schedule changes, or dependency repairs, keep using setup as the only routine command.

#### 5. Run manually (optional)

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

Linux:

```bash
./.venv/bin/python main.py
```

You do not need to activate `.venv`. A manual run starts immediately and is not restricted by the peak/off-peak schedule.

### Automatic and manual modes

`ENABLE_SCHEDULED_TASK` defaults to `true`. Setup creates a Windows Task Scheduler entry or a Linux cron entry, and `scheduled_run.py` checks every 15 minutes whether the current period is peak or off-peak. Scheduled tasks run only endpoint selection; code updates are checked only when the user runs setup.

The Windows scheduled task runs as `SYSTEM`, so its proxy and network environment may differ from an interactive PowerShell session.

After changing it to `false`, run setup again. Setup removes previously registered tasks for this project while keeping manual execution available. Change it back to `true` and rerun setup to restore automation.

### Results and multi-device sync

- `ip.local.txt` - Local results for the current device, overwritten on every run
- `ip.txt` - Aggregated multi-device results on GitHub; it is never used to overwrite local input
- `GITHUB_SYNC_TOP_N` - Maximum endpoints uploaded by one device; defaults to 5
- `GITHUB_SYNC_MAX_RETRIES` - Outer retry count for automatic GitHub sync failures; set it to `0` to disable GitHub sync

Each remote line includes a device identifier, for example `IP:port#region|Jinan-Unicom`. The sync process replaces only lines with the same `GITHUB_SYNC_FIELD_ID`; concurrent updates are fetched, merged, and retried.

For a public result repository, read the aggregate from `https://raw.githubusercontent.com/<username>/BestCfCdn/refs/heads/main/ip.txt`. For a private repository, never append a token to the URL query string; use a client that supports the `Authorization` header or publish through Cloudflare DNS instead.

### FAQ

#### Does setup use the virtual environment automatically?

Yes. Setup prefers the project `.venv` and creates it when missing. Scheduled tasks also call the Python executable inside that environment directly.

#### Can setup continue when GitHub is temporarily unreachable?

Yes. A network-only update failure falls back to the current local version. Setup stops on unsafe conditions such as local code changes outside configuration and result files, diverged branches, or invalid configuration to avoid overwriting local files.

#### Will an existing config.json be overwritten?

Not directly. After a safe update succeeds, new fields from the updated template are added while supported local values are preserved. For a very old installation, run `update_fork.ps1` or `update_fork.sh` once for the first upgrade, then use setup only.

#### Why does a scheduled task remain after switching to manual mode?

Run setup again after changing `ENABLE_SCHEDULED_TASK`; that is when the script applies the setting and removes the old task.

#### What should I check when GitHub sync fails?

Verify that the token has Contents read and write access, the repository and branch are correct, `GITHUB_SYNC_FIELD_ID` is valid, and the network can reach GitHub. Never expose a token in an Issue or log.

#### Why is a ZIP installation not recommended?

A ZIP copy has no Git history, so setup skips automatic updates. Use a Git clone if you want setup to remain the only routine command.

### Compatibility

- ✅ Windows 10 / 11 and common Linux distributions
- ✅ Python 3.9 or newer, Git, and curl
- ✅ Cloudflare CDN, EdgeTunnel, and similar proxy scenarios that need optimized entry endpoints
- ✅ Local selection on one device or shared maintenance across regions and network providers
- ✅ Released under the [MIT License](./LICENSE)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=uxudjs/BestCfCdn&type=Date)](https://star-history.com/#uxudjs/BestCfCdn&Date)
