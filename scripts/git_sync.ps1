# git_sync.ps1
# 功能：调用并发安全同步模块，只更新 config.json 中本终端对应的节点。

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8NoBom
    $OutputEncoding = $utf8NoBom
} catch { }

$venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonPath = $venvPython
} else {
    $python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3.exe -CommandType Application -ErrorAction SilentlyContinue }
    $pythonPath = if ($python) { $python.Source } else { $null }
}
if (-not $pythonPath) {
    Write-Host "❌ 未找到 Python" -ForegroundColor Red
    exit 1
}

& $pythonPath -X utf8 -m core.github_sync
exit $LASTEXITCODE
