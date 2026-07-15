# update_fork.ps1 - 安全更新当前仓库并保留本机配置
param(
    [string]$Branch = "main",
    [switch]$NonInteractive,
    [switch]$PreserveMissingConfig
)

$ErrorActionPreference = "Stop"
try { $Host.UI.RawUI.WindowTitle = "BestCfCdn 安全更新" } catch { }
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8NoBom
    $OutputEncoding = $utf8NoBom
} catch { }

function Invoke-Git {
    param([string[]]$Arguments, [switch]$AllowFailure, [switch]$Quiet)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @()
    $exitCode = -1
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

function Get-UpdatePython {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        return @{ Path = $venvPython; Prefix = @() }
    }

    $python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($python) { return @{ Path = $python.Source; Prefix = @() } }

    $pyLauncher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pyLauncher) { return @{ Path = $pyLauncher.Source; Prefix = @("-3") } }
    return $null
}

function Invoke-UpdatePython {
    param([Parameter(Mandatory = $true)][string[]]$Arguments, [switch]$AllowFailure)

    $allArguments = @($script:PythonCommand.Prefix) + $Arguments
    $pythonPath = $script:PythonCommand.Path
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @()
    $exitCode = -1
    try {
        $output = & $pythonPath @allArguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($exitCode -ne 0) {
        $output | ForEach-Object { Write-Host "  $_" }
        if (-not $AllowFailure) {
            throw "Python 命令执行失败（退出码 $exitCode）。"
        }
    }
    return ($exitCode -eq 0)
}

$git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $git) { throw "未找到 git.exe，请先运行 setup.ps1。" }
$GitPath = $git.Source

$insideRepo = Invoke-Git -Arguments @("rev-parse", "--is-inside-work-tree") -AllowFailure -Quiet
if (-not $insideRepo.Success) { throw "当前目录不是 Git 仓库。" }
$repositoryRootResult = Invoke-Git -Arguments @("rev-parse", "--show-toplevel") -Quiet
$repositoryRoot = ($repositoryRootResult.Output -join "").Trim()
if (-not $repositoryRoot -or
        ([IO.Path]::GetFullPath($repositoryRoot) -ne [IO.Path]::GetFullPath($PSScriptRoot))) {
    throw "update_fork.ps1 必须位于当前 Git 仓库根目录，已拒绝更新。"
}

$currentBranchResult = Invoke-Git -Arguments @("branch", "--show-current") -Quiet
$currentBranch = ($currentBranchResult.Output -join "").Trim()
if ($currentBranch -ne $Branch) {
    throw "当前分支是 '$currentBranch'，请先切换到 '$Branch' 后再更新。"
}

$statusResult = Invoke-Git -Arguments @("status", "--porcelain") -Quiet
$unrelatedChanges = @($statusResult.Output | Where-Object {
    $_ -and $_ -notmatch '(?:^.. | -> )(config\.json|ip\.txt|ip\.local\.txt)$'
})
if ($unrelatedChanges.Count -gt 0) {
    Write-Host "检测到本机配置/结果之外的本地改动，已停止以免覆盖：" -ForegroundColor Red
    $unrelatedChanges | ForEach-Object { Write-Host "  $_" }
    throw "请先提交或暂存上述改动。"
}

$configPath = Join-Path $PSScriptRoot "config.json"
if ((Test-Path -LiteralPath $configPath) -and -not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "config.json 已存在但不是普通文件。"
}
$configExistedBeforeUpdate = Test-Path -LiteralPath $configPath -PathType Leaf
$localIpExistedBeforeUpdate = Test-Path -LiteralPath (Join-Path $PSScriptRoot "ip.local.txt") -PathType Leaf

# 存在旧配置时，必须先确认能够完整解析；验证失败时不触碰 Git 工作树。
if ($configExistedBeforeUpdate) {
    $PythonCommand = Get-UpdatePython
    if (-not $PythonCommand) {
        throw "未找到 Python，无法在更新前安全校验并合并现有 config.json。"
    }
    $validateCode = "import json, sys; data=json.load(open(sys.argv[1], encoding='utf-8-sig')); assert isinstance(data, dict), 'config root must be an object'"
    $configValid = Invoke-UpdatePython -Arguments @("-X", "utf8", "-c", $validateCode, $configPath) -AllowFailure
    if (-not $configValid) {
        throw "config.json 不是有效的 JSON，已在更新前停止，请先修正配置。"
    }
}

# fetch 只更新远程引用。网络失败时，config/ip 和工作树都不会被修改。
Write-Host "拉取 origin/$Branch..." -ForegroundColor Yellow
$previousGitTerminalPrompt = $env:GIT_TERMINAL_PROMPT
try {
    $env:GIT_TERMINAL_PROMPT = "0"
    $null = Invoke-Git -Arguments @(
        "-c", "http.lowSpeedLimit=1",
        "-c", "http.lowSpeedTime=30",
        "fetch", "origin", $Branch
    )
} catch {
    $networkError = [System.InvalidOperationException]::new(
        "无法连接 origin/$Branch，尚未修改本机文件。",
        $_.Exception
    )
    $networkError.Data["BestCfCdnFailureKind"] = "Network"
    throw $networkError
} finally {
    if ($null -eq $previousGitTerminalPrompt) {
        Remove-Item Env:GIT_TERMINAL_PROMPT -ErrorAction SilentlyContinue
    } else {
        $env:GIT_TERMINAL_PROMPT = $previousGitTerminalPrompt
    }
}
$fastForwardCheck = Invoke-Git -Arguments @(
    "merge-base", "--is-ancestor", "HEAD", "origin/$Branch"
) -AllowFailure -Quiet
if (-not $fastForwardCheck.Success) {
    throw "本地 '$Branch' 与 origin/$Branch 已分叉，无法安全快进更新。"
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$BackupDir = Join-Path $HOME "bestcfcdn_backup_$timestamp"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
foreach ($name in @("config.json", "ip.local.txt")) {
    if (Test-Path -LiteralPath $name -PathType Leaf) {
        Copy-Item -LiteralPath $name -Destination (Join-Path $BackupDir $name) -Force
    }
}
$legacyIpBackup = Join-Path $BackupDir "ip.legacy.txt"
if (Test-Path -LiteralPath "ip.txt" -PathType Leaf) {
    $ipTrackedBeforeUpdate = Invoke-Git -Arguments @("ls-files", "--error-unmatch", "ip.txt") -AllowFailure -Quiet
    $ipWorktreeClean = Invoke-Git -Arguments @("diff", "--quiet", "--", "ip.txt") -AllowFailure -Quiet
    $ipIndexClean = Invoke-Git -Arguments @("diff", "--cached", "--quiet", "--", "ip.txt") -AllowFailure -Quiet
    if (-not $ipTrackedBeforeUpdate.Success -or -not $ipWorktreeClean.Success -or -not $ipIndexClean.Success) {
        Copy-Item -LiteralPath "ip.txt" -Destination $legacyIpBackup -Force
    }
}
Write-Host "配置备份：$BackupDir" -ForegroundColor Yellow

$configTempPath = Join-Path $PSScriptRoot (".config.json.update.{0}.{1}.tmp" -f $PID, ([guid]::NewGuid()).ToString("N"))
$mutationStarted = $false
$updateCompleted = $false
$updateError = $null
try {
    # 只有 fetch 和快进检查都成功后，才临时还原旧版本中可能被跟踪的本机文件。
    $mutationStarted = $true
    $configTracked = Invoke-Git -Arguments @("ls-files", "--error-unmatch", "config.json") -AllowFailure -Quiet
    if ($configTracked.Success) {
        $null = Invoke-Git -Arguments @("restore", "--staged", "--worktree", "--", "config.json") -Quiet
    }
    $ipTracked = Invoke-Git -Arguments @("ls-files", "--error-unmatch", "ip.txt") -AllowFailure -Quiet
    if ($ipTracked.Success) {
        $null = Invoke-Git -Arguments @("restore", "--staged", "--worktree", "--", "ip.txt") -Quiet
    } elseif (Test-Path -LiteralPath "ip.txt") {
        Remove-Item -LiteralPath "ip.txt" -Force
    }

    $null = Invoke-Git -Arguments @("merge", "--ff-only", "origin/$Branch")

    $configBackup = Join-Path $BackupDir "config.json"
    $configTemplate = Join-Path $PSScriptRoot "config.example.json"
    if (-not (Test-Path -LiteralPath $configTemplate -PathType Leaf)) {
        throw "更新后缺少 config.example.json。"
    }
    if (Test-Path -LiteralPath $configBackup -PathType Leaf) {
        $mergeCode = @'
import json, os, sys
backup_path, template_path, temp_path, output_path = sys.argv[1:]
with open(backup_path, encoding="utf-8-sig") as f:
    backup = json.load(f)
with open(template_path, encoding="utf-8-sig") as f:
    current = json.load(f)
if not isinstance(backup, dict) or not isinstance(current, dict):
    raise ValueError("config root must be an object")
legacy_remote = str(backup.get("GITHUB_SYNC_REMOTE_PATH", "ip.txt")).strip()
for key, value in backup.items():
    if key in current and not key.startswith("_comment"):
        if key == "OUTPUT_FILE" and os.path.normcase(os.path.normpath(str(value))) == os.path.normcase(os.path.normpath(legacy_remote)):
            continue
        current[key] = value
with open(temp_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(current, f, ensure_ascii=False, indent=4)
    f.write("\n")
    f.flush()
    os.fsync(f.fileno())
os.replace(temp_path, output_path)
'@
        $mergeOk = Invoke-UpdatePython -Arguments @(
            "-X", "utf8", "-c", $mergeCode,
            $configBackup, $configTemplate, $configTempPath, $configPath
        ) -AllowFailure
        if (-not $mergeOk) { throw "config.json 合并失败。" }
    } elseif (-not $PreserveMissingConfig) {
        Copy-Item -LiteralPath $configTemplate -Destination $configTempPath -Force
        Move-Item -LiteralPath $configTempPath -Destination $configPath -Force
    }
    $localIpBackup = Join-Path $BackupDir "ip.local.txt"
    if (Test-Path -LiteralPath $localIpBackup -PathType Leaf) {
        Copy-Item -LiteralPath $localIpBackup -Destination "ip.local.txt" -Force
    } elseif (Test-Path -LiteralPath $legacyIpBackup -PathType Leaf) {
        Copy-Item -LiteralPath $legacyIpBackup -Destination "ip.local.txt" -Force
    }
    $updateCompleted = $true
} catch {
    $updateError = $_
} finally {
    if ($mutationStarted -and -not $updateCompleted) {
        Write-Host "更新未完整完成，正在恢复本机配置与结果文件。" -ForegroundColor Red
        foreach ($name in @("config.json", "ip.local.txt")) {
            try {
                $backupPath = Join-Path $BackupDir $name
                if (Test-Path -LiteralPath $backupPath -PathType Leaf) {
                    Copy-Item -LiteralPath $backupPath -Destination $name -Force
                }
            } catch {
                Write-Host "⚠️ 恢复 $name 失败：$($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
        try {
            if (-not $configExistedBeforeUpdate -and (Test-Path -LiteralPath $configPath)) {
                Remove-Item -LiteralPath $configPath -Force
            }
        } catch {
            Write-Host "⚠️ 清理临时 config.json 失败：$($_.Exception.Message)" -ForegroundColor Yellow
        }
        try {
            if (-not $localIpExistedBeforeUpdate -and (Test-Path -LiteralPath "ip.local.txt") -and
                    -not (Test-Path -LiteralPath (Join-Path $BackupDir "ip.local.txt"))) {
                Remove-Item -LiteralPath "ip.local.txt" -Force
            }
        } catch {
            Write-Host "⚠️ 清理临时 ip.local.txt 失败：$($_.Exception.Message)" -ForegroundColor Yellow
        }
        try {
            if (Test-Path -LiteralPath $legacyIpBackup -PathType Leaf) {
                Copy-Item -LiteralPath $legacyIpBackup -Destination "ip.txt" -Force
            }
        } catch {
            Write-Host "⚠️ 恢复旧 ip.txt 失败：$($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    if (Test-Path -LiteralPath $configTempPath) {
        Remove-Item -LiteralPath $configTempPath -Force -ErrorAction SilentlyContinue
    }
}
if ($updateError) { throw $updateError }

Write-Host ""
Write-Host "✅ 更新完成，已保留本机配置与本机优选结果。" -ForegroundColor Green
Write-Host "未执行 reset --hard，也未将 Token 写入 Git URL。" -ForegroundColor Gray
Write-Host "备份目录：$BackupDir" -ForegroundColor Gray
if (-not $NonInteractive) {
    $null = Read-Host "按 Enter 键退出"
}
