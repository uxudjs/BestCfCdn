# Repository Guidelines

## Project Structure & Related Repositories

`main.py` is the stable public entry point and delegates to `core/app.py`. Internal Python modules live under `core/`; `core/chain_proxy.py` parses CfGfwAX subscriptions and manages the temporary Xray runtime. Focused regressions live under `work-products/tests/`. Root `setup.ps1`/`setup.sh` are the only platform entry points, while updater and manual-sync implementations live under `scripts/`. The only configuration template is `config/config.example.json`. `README.md` contains Simplified Chinese, Traditional Chinese, and English user documentation.

The sibling `../CfGfwAX` repository is the source of mixed/base64 VLESS subscriptions used by optional chain testing. Treat `/video/` global SOCKS5 semantics and the WS/gRPC/XHTTP + TLS fields `type`, `host`/`authority`, `path`/`serviceName`, `mode`, `security`, `ech`, `fragment`, `fp`, and `flow` as an upstream contract. The sibling `../CGAX-Pages` repository owns the management controls that enable SOCKS5 global mode and select WS, gRPC, or XHTTP. XHTTP `stream-one` is the only supported XHTTP mode; any other explicit mode must fail closed.

## Build, Test, and Development Commands

There is no build step. In Windows PowerShell, use process-local UTF-8 for Python output:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s work-products/tests -p test_chain_proxy.py -v
$files = @('setup.ps1', 'scripts/git_sync.ps1', 'scripts/update_fork.ps1')
foreach ($file in $files) { [void][scriptblock]::Create((Get-Content -LiteralPath $file -Raw -Encoding utf8)) }
bash -n setup.sh scripts/git_sync.sh scripts/update_fork.sh
git diff --check
```

The setup scripts install `requirements.txt`; when working directly from a checkout, create `.venv` and install those requirements before testing. Run the focused chain-proxy test after changes to `core/chain_proxy.py` or the CfGfwAX/CGAX-Pages contract. Run the full suite before opening a pull request. Internal commands use `python -m core.github_sync` and `python -m core.scheduled_run`; users continue to invoke root `main.py` and setup files. Windows/static or theoretical platform checks, including skipped POSIX tests, do not prove a live Linux install, CfGfwAX deployment, published CGAX-Pages UI, real scheduled task, or real Xray traffic.

## Coding Style & Naming Conventions

Match the existing Python style: four-space indentation, `snake_case` functions and variables, `PascalCase` classes, standard-library modules before third-party imports, and explicit fail-closed validation. Keep comments concise and in Simplified Chinese. Preserve established configuration keys and output formats unless compatibility changes are explicitly requested.

Keep Windows and Linux setup/update behavior synchronized. When changing a setup default or user-facing workflow, update both platform scripts and all three README language sections in the same task. Do not refactor adjacent measurement or updater code as part of a narrow chain-proxy change.

## Testing Guidelines

Use `unittest` and add the smallest regression under `work-products/tests/test_*.py`. Cover malformed input and failure paths as well as the successful path. Chain-proxy changes must preserve rejection of ambiguous templates, invalid `/video/` data, non-global SOCKS5 configuration, unavailable or checksum-mismatched Xray assets, unsupported transports, and unsupported XHTTP modes.

For cross-repository changes, update the producer before the consumer: CfGfwAX must emit the new contract before this parser depends on it, and CGAX-Pages must publish controls before workflows require them. Link the related pull requests and state the rollout order.

## Commit & Pull Request Guidelines

Keep commits single-purpose and follow the repository's existing concise commit style. Pull requests should describe behavior, affected platforms, validation commands, and any linked CfGfwAX or CGAX-Pages change. Separate updater/setup changes from scoring or chain-proxy changes when they can be reviewed independently.

## Security & Runtime Assets

Never commit or print a populated `CHAIN_PROXY_SUBSCRIPTION_URL`, subscription token, complete node URI, UUID, proxy credential, cookie, or downloaded runtime configuration containing real endpoints. Redact diagnostic samples. Keep Xray downloads version-pinned and SHA-256 verified, store runtime files only under the project-local `.xray` directory, and fail closed on unavailable, malformed, or mismatched assets. Legacy `.sing-box` is retained only for manual rollback and must never be executed, deleted, or modified automatically.
