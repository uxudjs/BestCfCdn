# BestCfCdn

跨平台 Cloudflare CDN / EdgeTunnel IP 自动优选：分层检测、体验评分、多终端同步，并可选发布到 GitHub 与 Cloudflare DNS。

### 🌐 选择语言 | 選擇語言 | Choose Language

- [🇨🇳 简体中文](#-简体中文)
- [🇹🇼 繁體中文](#-繁體中文)
- [🇺🇸 English](#-english)

---

## 🇨🇳 简体中文

> **最快上手：运行 setup 生成 `config.json` → 修改配置 → 再次运行 setup。**

### 3 步开始

1. 克隆项目。需要汇总结果到 GitHub 时，先 Fork 本仓库作为结果仓库；推荐克隆上游，以便 setup 自动获取更新。

   ```bash
   git clone https://github.com/uxudjs/BestCfCdn.git
   cd BestCfCdn
   ```

   克隆自己的 Fork 前，请先在 GitHub 使用 `Sync fork`。ZIP 可以运行，但不支持 setup 自动更新。

2. 首次运行 setup。

   **Windows PowerShell**

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\setup.ps1
   ```

   **Linux**

   ```bash
   bash setup.sh
   ```

   首次运行只生成 `config.json` 并退出。**首次运行不会生成私密订阅地址，也不会安装环境或注册调度。**

3. 修改 `config.json`，保存后再次运行 setup。脚本会验证环境、安装依赖、配置调度，并询问是否立即测试。

### 核心能力

- **自动优选**：聚合文本、JSON、地区名与 emoji 国旗等来源，依次检测 TCP、可用性、HTTP 延迟、抖动和真实带宽。
- **体验优先**：综合响应速度、稳定性与带宽；全局模式默认输出最优 3 个节点。
- **多终端同步**：每台终端只替换 GitHub `ip.txt` 中属于自己的记录。
- **峰谷调度**：北京时间 00:00–18:00 每 3 小时，18:00–24:00 每 1.5 小时。
- **可选发布**：支持 GitHub、Cloudflare DNS 与 WxPusher 异常通知。
- **可选链式测速**：验证“客户端 → CF 节点 → CfGfwAX → SOCKS5 → 目标服务器”的真实链路。

### 常用配置

完整配置及注释见 [`config/config.example.json`](./config/config.example.json)。优先确认：

| 配置 | 用途 |
| --- | --- |
| `GITHUB_SYNC_FIELD_ID` | 公开显示的终端别名，例如 `device-a`；不能含空白、`\|` 或 `#` |
| `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` | GitHub 同步凭据与结果仓库；不用同步时将 `GITHUB_SYNC_MAX_RETRIES` 设为 `0` |
| `ENABLE_SCHEDULED_TASK` | `true` 自动运行；`false` 仅手动运行并清除已有任务 |
| `CF_ENABLED` | 启用 Cloudflare DNS 更新 |
| `ENABLE_WXPUSHER` | 启用异常通知 |
| `UPDATE_BACKUP_RETENTION` | `1` 保留最新备份；`0` 在更新成功后删除，失败时仍保留救援备份 |

不要提交真实 Token。`config.json` 已被 Git 忽略，但仍是本地明文文件，请使用最小权限凭据。

<details>
<summary><strong>可选：链式测速</strong></summary>

在 `config.json` 中设置：

- `CHAIN_PROXY_TEST_ENABLED=true`
- `CHAIN_PROXY_SUBSCRIPTION_URL`：CfGfwAX mixed 订阅地址，例如 `https://代理域名/sub?token=***&target=mixed`
- `CHAIN_PROXY_CORE_PATH`：Xray 26.3.27 路径；留空时按项目内 `.xray/`、`PATH`、固定官方资产的顺序发现或安装
- `CHAIN_PROXY_PREFLIGHT_URL`：独立的轻量 HTTPS 2xx 预检目标，默认使用 Cloudflare trace
- `CHAIN_PROXY_TEST_SAMPLES` / `CHAIN_PROXY_MIN_SUCCESS_RATE`：默认测试 3 次，至少成功 2 次
- `CHAIN_PROXY_WORKERS`：默认低并发 4，减少共享 SOCKS5 拥塞对排名的干扰

支持 CfGfwAX VLESS + WebSocket、gRPC 与 XHTTP `stream-one` + TLS，以及 ECH、TLS 分片、浏览器指纹和 flow。启用后，setup 与 `main.py` 会在候选抓取、TCP 测试或调度注册前执行前置真实 SOCKS HTTPS 连接，最多尝试三个订阅端点，并验证 `/video/` 为全局 SOCKS5。无效字段、不可用核心或无法无损映射的配置都会停止，**不降级为直连**。

setup 只修复项目内 `.venv`/`.xray`；旧 `.sing-box/` 仅供人工回滚，不执行、不修改。链式排名为：HTTP 延迟 40%、带宽 30%、抖动 20%、成功率 10%。订阅 URL 含 Token，只能保存在本地 `config.json`，不要写入配置模板、日志或公开仓库。

</details>

### 手动运行与结果

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- 本地结果：`ip.local.txt`
- GitHub 汇总：`ip.txt`，每个终端默认最多 3 行
- DNS：`TXT` 保存 `IP:端口`；`A` 保存纯 IPv4，作为入口域名时保持 `CF_PROXIED=false`
- 失败保护：可用性或 HTTP 检测全部失败时，不覆盖现有本地、GitHub 与 DNS 结果；DNS 发布过滤无结果时，仅保留现有 DNS 记录

<details>
<summary><strong>维护与兼容性</strong></summary>

- 支持 Windows 10 / 11、常见 Linux、Python 3.9+、Git 与 curl。
- 公开入口为根目录 `main.py`、`setup.ps1`、`setup.sh`；内部实现位于 `core/`。
- 上述规范模板是唯一应编辑的示例；根目录同名 JSON 仅供旧版更新器在快进前读取，请勿单独编辑。
- 维护者内部命令：`python -m core.github_sync`、`python -m core.scheduled_run`、`scripts/update_fork.*`。
- 旧安装请重新运行 setup，以迁移调度与更新器。
- [MIT License](./LICENSE)

</details>

---

## 🇹🇼 繁體中文

> **最快上手：執行 setup 產生 `config.json` → 修改設定 → 再次執行 setup。**

### 3 步開始

1. 複製專案。需要彙總結果到 GitHub 時，先 Fork 本倉庫作為結果倉庫；建議複製上游，以便 setup 自動取得更新。

   ```bash
   git clone https://github.com/uxudjs/BestCfCdn.git
   cd BestCfCdn
   ```

   複製自己的 Fork 前，請先在 GitHub 使用 `Sync fork`。ZIP 可以執行，但不支援 setup 自動更新。

2. 首次執行 setup。

   **Windows PowerShell**

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\setup.ps1
   ```

   **Linux**

   ```bash
   bash setup.sh
   ```

   首次執行只產生 `config.json` 並退出。**首次執行不會產生私密訂閱網址，也不會安裝環境或註冊排程。**

3. 修改 `config.json`，儲存後再次執行 setup。腳本會驗證環境、安裝依賴、設定排程，並詢問是否立即測試。

### 核心能力

- **自動優選**：彙整文字、JSON、地區名稱與 emoji 國旗等來源，依序檢測 TCP、可用性、HTTP 延遲、抖動和真實頻寬。
- **體驗優先**：綜合回應速度、穩定性與頻寬；全域模式預設輸出最佳 3 個節點。
- **多終端同步**：每台終端只替換 GitHub `ip.txt` 中屬於自己的記錄。
- **峰谷排程**：北京時間 00:00–18:00 每 3 小時，18:00–24:00 每 1.5 小時。
- **可選發佈**：支援 GitHub、Cloudflare DNS 與 WxPusher 異常通知。
- **可選鏈式測速**：驗證「客戶端 → CF 節點 → CfGfwAX → SOCKS5 → 目標伺服器」的真實鏈路。

### 常用設定

完整設定與註解請見 [`config/config.example.json`](./config/config.example.json)。優先確認：

| 設定 | 用途 |
| --- | --- |
| `GITHUB_SYNC_FIELD_ID` | 公開顯示的終端別名，例如 `device-a`；不能含空白、`\|` 或 `#` |
| `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` | GitHub 同步憑據與結果倉庫；不使用同步時將 `GITHUB_SYNC_MAX_RETRIES` 設為 `0` |
| `ENABLE_SCHEDULED_TASK` | `true` 自動執行；`false` 僅手動執行並清除已有任務 |
| `CF_ENABLED` | 啟用 Cloudflare DNS 更新 |
| `ENABLE_WXPUSHER` | 啟用異常通知 |
| `UPDATE_BACKUP_RETENTION` | `1` 保留最新備份；`0` 在更新成功後刪除，失敗時仍保留救援備份 |

不要提交真實 Token。`config.json` 已被 Git 忽略，但仍是本機明文檔案，請使用最小權限憑據。

<details>
<summary><strong>可選：鏈式測速</strong></summary>

在 `config.json` 中設定：

- `CHAIN_PROXY_TEST_ENABLED=true`
- `CHAIN_PROXY_SUBSCRIPTION_URL`：CfGfwAX mixed 訂閱網址，例如 `https://代理網域/sub?token=***&target=mixed`
- `CHAIN_PROXY_CORE_PATH`：Xray 26.3.27 路徑；留空時依專案內 `.xray/`、`PATH`、固定官方資產的順序尋找或安裝
- `CHAIN_PROXY_PREFLIGHT_URL`：獨立的輕量 HTTPS 2xx 預檢目標，預設使用 Cloudflare trace
- `CHAIN_PROXY_TEST_SAMPLES` / `CHAIN_PROXY_MIN_SUCCESS_RATE`：預設測試 3 次，至少成功 2 次
- `CHAIN_PROXY_WORKERS`：預設低併發 4，減少共用 SOCKS5 壅塞對排名的干擾

支援 CfGfwAX VLESS + WebSocket、gRPC 與 XHTTP `stream-one` + TLS，以及 ECH、TLS 分片、瀏覽器指紋和 flow。啟用後，setup 與 `main.py` 會在候選抓取、TCP 測試或排程註冊前執行前置真實 SOCKS HTTPS 連線，最多嘗試三個訂閱端點，並驗證 `/video/` 為全域 SOCKS5。無效欄位、不可用核心或無法無損映射的設定都會停止，**不降級為直連**。

setup 只修復專案內 `.venv`/`.xray`；舊 `.sing-box/` 僅供人工回滾，不執行、不修改。鏈式排名為：HTTP 延遲 40%、頻寬 30%、抖動 20%、成功率 10%。訂閱網址含 Token，只能儲存在本機 `config.json`，不要寫入設定範本、日誌或公開倉庫。

</details>

### 手動執行與結果

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- 本機結果：`ip.local.txt`
- GitHub 彙總：`ip.txt`，每個終端預設最多 3 行
- DNS：`TXT` 儲存 `IP:連接埠`；`A` 儲存純 IPv4，作為入口網域時保持 `CF_PROXIED=false`
- 失敗保護：可用性或 HTTP 檢測全部失敗時，不覆蓋現有本機、GitHub 與 DNS 結果；DNS 發佈過濾無結果時，僅保留現有 DNS 記錄

<details>
<summary><strong>維護與相容性</strong></summary>

- 支援 Windows 10 / 11、常見 Linux、Python 3.9+、Git 與 curl。
- 公開入口為根目錄 `main.py`、`setup.ps1`、`setup.sh`；內部實作位於 `core/`。
- 上述規範範本是唯一應編輯的範例；根目錄同名 JSON 僅供舊版更新器在快進前讀取，請勿單獨編輯。
- 維護者內部命令：`python -m core.github_sync`、`python -m core.scheduled_run`、`scripts/update_fork.*`。
- 舊安裝請重新執行 setup，以遷移排程與更新器。
- [MIT License](./LICENSE)

</details>

---

## 🇺🇸 English

> **Fastest path: run setup to create `config.json` → edit it → run setup again.**

### Start in 3 steps

1. Clone the project. If you need GitHub aggregation, fork this repository as the result repository first. Clone upstream so setup can retrieve updates automatically.

   ```bash
   git clone https://github.com/uxudjs/BestCfCdn.git
   cd BestCfCdn
   ```

   Before cloning your own fork, use GitHub's `Sync fork`. ZIP copies can run but do not support setup updates.

2. Run setup for the first time.

   **Windows PowerShell**

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\setup.ps1
   ```

   **Linux**

   ```bash
   bash setup.sh
   ```

   The first run only creates `config.json` and exits. **The first run does not generate a private subscription URL, install an environment, or register scheduling.**

3. Edit `config.json`, save it, and run setup again. The script validates the environment, installs dependencies, configures scheduling, and offers a test run.

### Core capabilities

- **Automatic selection**: Aggregates text, JSON, region names, emoji flags, and other sources; then tests TCP, availability, HTTP latency, jitter, and real bandwidth.
- **Experience-first ranking**: Balances responsiveness, stability, and bandwidth; global mode keeps the best three endpoints by default.
- **Multi-device sync**: Each device replaces only its own lines in GitHub `ip.txt`.
- **Peak/off-peak schedule**: Beijing time, every three hours from 00:00 to 18:00 and every 90 minutes from 18:00 to 24:00.
- **Optional publishing**: Supports GitHub, Cloudflare DNS, and WxPusher error notifications.
- **Optional chain testing**: Verifies the real client → CF endpoint → CfGfwAX → SOCKS5 → target path.

### Common configuration

See [`config/config.example.json`](./config/config.example.json) for every option and its comments. Check these first:

| Setting | Purpose |
| --- | --- |
| `GITHUB_SYNC_FIELD_ID` | Public device alias such as `device-a`; cannot contain whitespace, `\|`, or `#` |
| `GITHUB_SYNC_TOKEN` / `GITHUB_SYNC_REPOSITORY` | GitHub credentials and result repository; set `GITHUB_SYNC_MAX_RETRIES=0` when sync is unused |
| `ENABLE_SCHEDULED_TASK` | `true` runs automatically; `false` is manual-only and removes existing tasks |
| `CF_ENABLED` | Enables Cloudflare DNS updates |
| `ENABLE_WXPUSHER` | Enables error notifications |
| `UPDATE_BACKUP_RETENTION` | `1` keeps the latest backup; `0` removes it after success while preserving rescue backups after failure |

Never commit real tokens. Git ignores `config.json`, but it is still a plaintext local file; use least-privilege credentials.

<details>
<summary><strong>Optional: chain testing</strong></summary>

Set these in `config.json`:

- `CHAIN_PROXY_TEST_ENABLED=true`
- `CHAIN_PROXY_SUBSCRIPTION_URL`: CfGfwAX mixed subscription URL, for example `https://proxy.example/sub?token=***&target=mixed`
- `CHAIN_PROXY_CORE_PATH`: Path to Xray 26.3.27; when empty, discovery or installation checks project-local `.xray/`, `PATH`, then the pinned official asset
- `CHAIN_PROXY_PREFLIGHT_URL`: Dedicated lightweight HTTPS 2xx target; defaults to Cloudflare trace
- `CHAIN_PROXY_TEST_SAMPLES` / `CHAIN_PROXY_MIN_SUCCESS_RATE`: Three samples by default, with at least two successes required
- `CHAIN_PROXY_WORKERS`: Low concurrency of four by default to reduce ranking bias from shared SOCKS5 saturation

Supports CfGfwAX VLESS + WebSocket, gRPC, and XHTTP `stream-one` + TLS, including ECH, TLS fragmentation, browser fingerprints, and flow. When enabled, setup and `main.py` preflight real SOCKS HTTPS before candidate fetching, TCP tests, or scheduler registration, try at most three subscription endpoints, and verify global SOCKS5 semantics in `/video/`. Invalid fields, an unavailable core, or settings that cannot be mapped losslessly stop the run; it **never falls back to direct testing**.

Setup repairs only project-local `.venv`/`.xray`; legacy `.sing-box/` is retained for manual rollback and is never executed or modified. Chain ranking is HTTP latency 40%, bandwidth 30%, jitter 20%, and success rate 10%. The subscription URL contains a token: keep it only in local `config.json`, never in the configuration template, logs, or public repositories.

</details>

### Manual runs and results

```powershell
.\.venv\Scripts\python.exe -X utf8 main.py
```

```bash
./.venv/bin/python main.py
```

- Local results: `ip.local.txt`
- GitHub aggregation: `ip.txt`, with up to three lines per device by default
- DNS: `TXT` stores `IP:port`; `A` stores plain IPv4 and should keep `CF_PROXIED=false` for an entry hostname
- Failure protection: if availability or HTTP checks reject every candidate, existing local, GitHub, and DNS results remain unchanged; empty DNS publishing filters preserve existing DNS records

<details>
<summary><strong>Maintenance and compatibility</strong></summary>

- Supports Windows 10 / 11, common Linux distributions, Python 3.9+, Git, and curl.
- Public entry points are root-level `main.py`, `setup.ps1`, and `setup.sh`; implementation lives under `core/`.
- The canonical template linked above is the only example to edit; the same-named root JSON exists only for legacy updaters to read before fast-forwarding. Do not edit it independently.
- Maintainer commands: `python -m core.github_sync`, `python -m core.scheduled_run`, and `scripts/update_fork.*`.
- Existing installations should rerun setup to migrate scheduling and updater behavior.
- [MIT License](./LICENSE)

</details>

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=uxudjs/BestCfCdn&type=Date)](https://star-history.com/#uxudjs/BestCfCdn&Date)
