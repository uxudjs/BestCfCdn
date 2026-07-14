# update_fork.ps1 - 安全更新当前仓库并保留本机配置
param([string]$Branch = "main")

$ErrorActionPreference = "Stop"
try { $Host.UI.RawUI.WindowTitle = "BestCfCdn 安全更新" } catch { }
Set-Location $PSScriptRoot

function Invoke-Git {
    param([string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $script:GitPath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if (-not $Quiet -or $exitCode -ne 0) {
        $output | ForEach-Object { Write-Host "  $_" }
    }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "git $($Arguments -join ' ') 执行失败（退出码 $exitCode）"
    }
    return [PSCustomObject]@{
        Success = ($exitCode -eq 0)
        Output = @($output | ForEach-Object { $_.ToString() })
        ExitCode = $exitCode
    }
}

$git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue
if (-not $git) { throw "未找到 git.exe，请先运行 setup.ps1。" }
$GitPath = $git.Source

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $PythonPath = $venvPython
} else {
    $python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue
    if (-not $python) { throw "未找到 Python，请先运行 setup.ps1。" }
    $PythonPath = $python.Source
}

$insideRepo = Invoke-Git -Arguments @("rev-parse", "--is-inside-work-tree") -AllowFailure -Quiet
if (-not $insideRepo.Success) { throw "当前目录不是 Git 仓库。" }

$currentBranchResult = Invoke-Git -Arguments @("branch", "--show-current") -Quiet
$currentBranch = ($currentBranchResult.Output -join "").Trim()
if ($currentBranch -ne $Branch) {
    throw "当前分支是 '$currentBranch'，请先切换到 '$Branch' 后再更新。"
}

$statusResult = Invoke-Git -Arguments @("status", "--porcelain") -Quiet
$unrelatedChanges = @($statusResult.Output | Where-Object {
    $_ -and $_ -notmatch '(?:^.. | -> )(config\.json|ip\.txt)$'
})
if ($unrelatedChanges.Count -gt 0) {
    Write-Host "检测到 config.json/ip.txt 之外的本地改动，已停止以免覆盖：" -ForegroundColor Red
    $unrelatedChanges | ForEach-Object { Write-Host "  $_" }
    throw "请先提交或暂存上述改动。"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $HOME "bestcfcdn_backup_$timestamp"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
foreach ($name in @("config.json", "ip.txt")) {
    if (Test-Path $name) { Copy-Item $name (Join-Path $BackupDir $name) -Force }
}
Write-Host "配置备份：$BackupDir" -ForegroundColor Yellow

try {
    $configTracked = Invoke-Git -Arguments @("ls-files", "--error-unmatch", "config.json") -AllowFailure -Quiet
    if ($configTracked.Success) {
        $null = Invoke-Git -Arguments @("restore", "--staged", "--worktree", "--", "config.json") -Quiet
    }
    $ipTracked = Invoke-Git -Arguments @("ls-files", "--error-unmatch", "ip.txt") -AllowFailure -Quiet
    if ($ipTracked.Success) {
        $null = Invoke-Git -Arguments @("restore", "--staged", "--worktree", "--", "ip.txt") -Quiet
    } elseif (Test-Path "ip.txt") {
        Remove-Item "ip.txt" -Force
    }

    Write-Host "拉取 origin/$Branch..." -ForegroundColor Yellow
    $null = Invoke-Git -Arguments @("fetch", "origin", $Branch)
    $null = Invoke-Git -Arguments @("merge", "--ff-only", "origin/$Branch")

    $configBackup = Join-Path $BackupDir "config.json"
    if (Test-Path $configBackup) {
        $mergeCode = @'
import json, sys
backup_path, current_path = sys.argv[1:]
with open(backup_path, encoding="utf-8-sig") as f:
    backup = json.load(f)
with open(current_path, encoding="utf-8-sig") as f:
    current = json.load(f)
for key, value in backup.items():
    if key in current and not key.startswith("_comment"):
        current[key] = value
with open(current_path, "w", encoding="utf-8") as f:
    json.dump(current, f, ensure_ascii=False, indent=4)
    f.write("\n")
'@
        & $PythonPath -c $mergeCode $configBackup (Join-Path $PSScriptRoot "config.json")
        if ($LASTEXITCODE -ne 0) { throw "config.json 合并失败。" }
    }
    $ipBackup = Join-Path $BackupDir "ip.txt"
    if (Test-Path $ipBackup) { Copy-Item $ipBackup "ip.txt" -Force }
} catch {
    foreach ($name in @("config.json", "ip.txt")) {
        $backupPath = Join-Path $BackupDir $name
        if (Test-Path $backupPath) { Copy-Item $backupPath $name -Force }
    }
    throw
}

Write-Host ""
Write-Host "✅ 更新完成，已保留本机配置。" -ForegroundColor Green
Write-Host "未执行 reset --hard，也未将 Token 写入 Git URL。" -ForegroundColor Gray
Write-Host "备份目录：$BackupDir" -ForegroundColor Gray
Read-Host "按 Enter 键退出"
