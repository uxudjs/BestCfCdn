# setup.ps1 - Cloudflare IP 优选工具 Windows 一键部署脚本
# 用法：在项目目录执行 .\setup.ps1。脚本会按需请求管理员权限。

param(
    # 仅供脚本自更新和提权重启时使用，普通用户无需传入。
    [switch]$SkipAutoUpdate
)

$ErrorActionPreference = "Stop"
try { $Host.UI.RawUI.WindowTitle = "Cloudflare IP 优选部署" } catch { }

# Windows PowerShell 5.1 会按当前系统代码页处理原生命令管道。
# 强制 PowerShell 与所有 Python 子进程使用 UTF-8，避免 CP950/GBK 编码异常。
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $OutputEncoding = $utf8NoBom
} catch { }

$TaskName = "Cloudflare IP 优选"
$TaskIntervalMinutes = 15
$PythonExePath = $null
$ScriptDir = $PSScriptRoot
$PythonScriptPath = Join-Path $ScriptDir "scheduled_run.py"
$WorkingDirectory = $ScriptDir
$TunaPyPI = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
$OfficialPyPI = "https://pypi.org/simple"

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $identity
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Refresh-EnvPath {
    $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath"
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @(),
        [switch]$AllowFailure,
        [switch]$Quiet
    )

    # Windows PowerShell 会把原生命令的 stderr 包装为 NativeCommandError。
    # 暂时改为 Continue，并始终以真实退出码判断成功与否。
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @()
    $exitCode = -1
    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }

    if (-not $Quiet -or $exitCode -ne 0) {
        $output | ForEach-Object { Write-Host "  $_" }
    }
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "命令执行失败（退出码 $exitCode）：$FilePath $($Arguments -join ' ')"
    }
    return ($exitCode -eq 0)
}

function Get-BootstrapPython {
    $projectVenvPython = Join-Path $script:ScriptDir ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $projectVenvPython -PathType Leaf) {
        return @{ Path = $projectVenvPython; Prefix = @() }
    }

    $activeVenvPython = if ($env:VIRTUAL_ENV) {
        Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
    } else { $null }
    if ($activeVenvPython -and (Test-Path $activeVenvPython)) {
        return @{ Path = $activeVenvPython; Prefix = @() }
    }

    $python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($python) {
        return @{ Path = $python.Source; Prefix = @() }
    }
    $pyLauncher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($pyLauncher) {
        return @{ Path = $pyLauncher.Source; Prefix = @("-3") }
    }
    return $null
}

function Get-NextAlignedTime {
    param([int]$IntervalMinutes = 15)
    $now = Get-Date
    $currentTotalMinutes = $now.Hour * 60 + $now.Minute
    $nextTotalMinutes = ([math]::Floor($currentTotalMinutes / $IntervalMinutes) + 1) * $IntervalMinutes
    return $now.Date.AddMinutes($nextTotalMinutes)
}

function Install-PythonPackages {
    param(
        [Parameter(Mandatory = $true)][string[]]$InstallArguments,
        [Parameter(Mandatory = $true)][string]$Description
    )

    foreach ($indexUrl in $script:PipIndexUrls) {
        Write-Host "  $Description（源：$indexUrl）..." -ForegroundColor Yellow
        $pipArgs = @(
            "-m", "pip", "install",
            "--disable-pip-version-check",
            "--timeout", "120",
            "--retries", "10",
            "--index-url", $indexUrl
        ) + $InstallArguments
        if (Invoke-NativeCommand -FilePath $script:PythonExePath -Arguments $pipArgs -AllowFailure) {
            return $true
        }
        Write-Host "  ⚠️ 当前源安装失败，尝试下一个源。" -ForegroundColor Yellow
    }
    return $false
}

function Add-GitIgnoreEntries {
    param([string]$Path, [string[]]$Entries)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    if (-not (Test-Path $Path)) {
        New-Item -ItemType File -Path $Path -Force | Out-Null
    }
    $existing = @(Get-Content -Path $Path -ErrorAction SilentlyContinue)
    foreach ($entry in $Entries) {
        if ($existing -notcontains $entry) {
            Add-Content -Path $Path -Value $entry -Encoding UTF8
            $existing += $entry
        }
    }
}

function Get-RuntimeIgnorePath {
    $fallback = Join-Path $script:ScriptDir ".gitignore"
    $git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $git) { return $fallback }

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $rootOutput = @()
    $excludeOutput = @()
    $gitExitCode = -1
    try {
        $rootOutput = & $git.Source "-C" $script:ScriptDir "rev-parse" "--show-toplevel" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $excludeOutput = & $git.Source "-C" $script:ScriptDir "rev-parse" "--git-path" "info/exclude" 2>$null
            $gitExitCode = $LASTEXITCODE
        } else {
            $gitExitCode = $LASTEXITCODE
        }
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($gitExitCode -ne 0) { return $fallback }

    $root = (($rootOutput | ForEach-Object { $_.ToString() }) -join "").Trim()
    $exclude = (($excludeOutput | ForEach-Object { $_.ToString() }) -join "").Trim()
    if (-not $root -or -not $exclude -or
            ([IO.Path]::GetFullPath($root) -ne [IO.Path]::GetFullPath($script:ScriptDir))) {
        return $fallback
    }
    if (-not [IO.Path]::IsPathRooted($exclude)) {
        $exclude = Join-Path $script:ScriptDir $exclude
    }
    return [IO.Path]::GetFullPath($exclude)
}

function Test-TaskNotFoundException {
    param([System.Exception]$Exception)
    # PowerShell 会用 MethodInvocationException 包装 COMException，逐层查找
    # HRESULT_FROM_WIN32(ERROR_FILE_NOT_FOUND) (0x80070002)。
    $current = $Exception
    while ($null -ne $current) {
        if ($current.HResult -eq -2147024894) { return $true }
        $current = $current.InnerException
    }
    return $false
}

function Remove-ProjectScheduledTask {
    param([Parameter(Mandatory = $true)][string]$Name)

    $taskService = New-Object -ComObject Schedule.Service
    $taskService.Connect()
    $rootFolder = $taskService.GetFolder("\")
    try {
        $existingTask = $rootFolder.GetTask("\$Name")
    } catch {
        if (Test-TaskNotFoundException -Exception $_.Exception) { return $false }
        throw
    }
    if ($null -eq $existingTask) { return $false }

    $rootFolder.DeleteTask($Name, 0)
    try {
        $null = $rootFolder.GetTask("\$Name")
    } catch {
        if (Test-TaskNotFoundException -Exception $_.Exception) { return $true }
        throw
    }
    throw "计划任务 '$Name' 删除后仍然存在。"
}

function Get-RepositoryHead {
    param([Parameter(Mandatory = $true)][string]$GitPath)

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @()
    $exitCode = -1
    try {
        $output = & $GitPath "rev-parse" "--verify" "HEAD" 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($exitCode -ne 0) { return $null }
    return (($output | ForEach-Object { $_.ToString() }) -join "").Trim()
}

function Get-RepositoryRoot {
    param([Parameter(Mandatory = $true)][string]$GitPath)

    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = @()
    $exitCode = -1
    try {
        $output = & $GitPath "rev-parse" "--show-toplevel" 2>$null
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    if ($exitCode -ne 0) { return $null }
    return (($output | ForEach-Object { $_.ToString() }) -join "").Trim()
}

function Get-PowerShellExecutable {
    $executableName = if ($PSVersionTable.PSEdition -eq "Core") { "pwsh.exe" } else { "powershell.exe" }
    $candidate = Join-Path $PSHOME $executableName
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    return (Get-Process -Id $PID).Path
}

function Restart-UpdatedSetup {
    param([switch]$RetryAutoUpdate)

    $powerShellPath = Get-PowerShellExecutable
    Write-Host "✅ 已获取新版代码，正在重新加载最新 setup.ps1..." -ForegroundColor Green
    $restartArguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath)
    if (-not $RetryAutoUpdate) { $restartArguments += "-SkipAutoUpdate" }
    & $powerShellPath @restartArguments
    $childExitCode = $LASTEXITCODE
    exit $childExitCode
}

Set-Location $ScriptDir

# ---------- 首先安全更新代码，普通用户始终只需运行 setup.ps1 ----------
if (-not $SkipAutoUpdate) {
    Write-Host "正在检查 GitHub 上的项目更新..." -ForegroundColor Cyan
    $updateScriptPath = Join-Path $ScriptDir "update_fork.ps1"
    $gitForUpdate = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $repositoryRoot = if ($gitForUpdate) { Get-RepositoryRoot -GitPath $gitForUpdate.Source } else { $null }
    $configExistsForUpdate = Test-Path -LiteralPath (Join-Path $ScriptDir "config.json") -PathType Leaf
    $bootstrapForUpdate = if ($configExistsForUpdate) { Get-BootstrapPython } else { $null }

    if (-not $gitForUpdate) {
        Write-Host "⚠️ 未检测到 Git，本次跳过自动更新；完成部署后下次运行会再次尝试。" -ForegroundColor Yellow
    } elseif (-not $repositoryRoot -or
            ([IO.Path]::GetFullPath($repositoryRoot) -ne [IO.Path]::GetFullPath($ScriptDir))) {
        Write-Host "⚠️ 当前目录不是独立 Git 仓库根目录（可能是 ZIP 解压版），已跳过自动更新。" -ForegroundColor Yellow
    } elseif (-not (Test-Path -LiteralPath $updateScriptPath -PathType Leaf)) {
        Write-Host "⚠️ 未找到 update_fork.ps1，已跳过自动更新并继续本地部署。" -ForegroundColor Yellow
    } elseif ($configExistsForUpdate -and -not $bootstrapForUpdate) {
        Write-Host "⚠️ 现有部署暂未检测到 Python，为了先安全校验旧配置，本次跳过更新。" -ForegroundColor Yellow
        Write-Host "   setup 安装 Python 后，下次运行会自动更新。" -ForegroundColor Yellow
    } else {
        $headBeforeUpdate = Get-RepositoryHead -GitPath $gitForUpdate.Source
        $updateFailure = $null
        try {
            & $updateScriptPath -Branch "main" -NonInteractive -PreserveMissingConfig
        } catch {
            $updateFailure = $_
        }
        $headAfterUpdate = Get-RepositoryHead -GitPath $gitForUpdate.Source

        if ($headBeforeUpdate -and $headAfterUpdate -and $headAfterUpdate -ne $headBeforeUpdate) {
            if ($updateFailure) {
                Restart-UpdatedSetup -RetryAutoUpdate
            } else {
                Restart-UpdatedSetup
            }
        }
        if ($updateFailure) {
            $failureKind = $updateFailure.Exception.Data["BestCfCdnFailureKind"]
            if ($failureKind -eq "Network") {
                Write-Host ""
                Write-Host "⚠️ GitHub 暂时不可达，仓库 HEAD 未改变。" -ForegroundColor Yellow
                Write-Host "   将继续使用当前本地版本完成部署。" -ForegroundColor Yellow
            } else {
                Write-Host "❌ 自动更新未通过安全检查，setup 已停止。" -ForegroundColor Red
                throw $updateFailure
            }
        }
    }
    Write-Host ""
}

if (-not (Test-Administrator)) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " Cloudflare IP 优选工具 - 智能部署" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "创建 SYSTEM 计划任务需要管理员权限。" -ForegroundColor Yellow
    $choice = Read-Host "是否以管理员身份重新启动脚本？(Y/N)"
    if ($choice -match '^[Yy]$') {
        $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SkipAutoUpdate"
        try {
            $powerShellPath = Get-PowerShellExecutable
            $elevated = Start-Process -FilePath $powerShellPath -Verb RunAs -ArgumentList $arguments -Wait -PassThru
            exit $elevated.ExitCode
        } catch {
            Write-Host "❌ 无法自动提权：$_" -ForegroundColor Red
        }
    }
    Write-Host "请在管理员 PowerShell 中进入以下目录后重新运行：" -ForegroundColor Yellow
    Write-Host "  cd '$PSScriptRoot'" -ForegroundColor Cyan
    Write-Host "  .\setup.ps1" -ForegroundColor Cyan
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Cloudflare IP 优选工具 - 智能部署" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $ScriptDir
Write-Host "工作目录: $ScriptDir`n" -ForegroundColor Gray

$configPath = Join-Path $ScriptDir "config.json"
$configTemplatePath = Join-Path $ScriptDir "config.example.json"
if ((Test-Path -LiteralPath $configPath) -and -not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "config.json 已存在但不是普通文件。"
}
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $configTemplatePath -PathType Leaf)) {
        throw "未找到 config.example.json，无法创建本机配置。"
    }
    try {
        $null = Remove-ProjectScheduledTask -Name $TaskName
    } catch {
        throw "无法确认旧计划任务已停止，尚未创建 config.json：$_"
    }
    Add-GitIgnoreEntries -Path (Get-RuntimeIgnorePath) -Entries @("config.json")
    Copy-Item -LiteralPath $configTemplatePath -Destination $configPath
    Write-Host "✅ 已从 config.example.json 创建本机 config.json（Git 将忽略此文件）" -ForegroundColor Green
    Write-Host "首次部署到此暂停：请先编辑 config.json，再次运行 .\setup.ps1 以安装依赖并应用定时设置。" -ForegroundColor Yellow
    Write-Host "本次不会安装依赖、注册计划任务或运行 main.py。" -ForegroundColor Yellow
    exit 0
}

# ---------- 1. 检测 Python 并固定使用项目虚拟环境 ----------
Write-Host "[1/5] 检查 Python 与项目虚拟环境..." -ForegroundColor Green
$bootstrap = Get-BootstrapPython
if (-not $bootstrap) {
    Write-Host "未检测到 Python，正在通过 winget 安装 Python 3..." -ForegroundColor Yellow
    $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $winget) {
        throw "未找到 winget，请先从 https://www.python.org/downloads/ 安装 Python 3。"
    }
    $null = Invoke-NativeCommand -FilePath $winget.Source -Arguments @(
        "install", "Python.Python.3", "--accept-package-agreements", "--accept-source-agreements"
    )
    Refresh-EnvPath
    $bootstrap = Get-BootstrapPython
    if (-not $bootstrap) { throw "Python 安装后仍无法检测，请重新打开 PowerShell 再运行。" }
}

$projectVenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $projectVenvPython)) {
    Write-Host "  创建项目虚拟环境 .venv..." -ForegroundColor Yellow
    $venvArgs = @($bootstrap.Prefix) + @("-m", "venv", (Join-Path $ScriptDir ".venv"))
    $null = Invoke-NativeCommand -FilePath $bootstrap.Path -Arguments $venvArgs
}
if (-not (Test-Path $projectVenvPython)) { throw "项目虚拟环境创建失败。" }
$PythonExePath = $projectVenvPython
$versionOk = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @(
    "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"
) -AllowFailure -Quiet
if (-not $versionOk) { throw "需要 Python 3.9 或更高版本。" }
Write-Host "✅ 项目 Python: $PythonExePath" -ForegroundColor Gray

# ---------- 2. 检测 Git ----------
Write-Host "[2/5] 检查 Git..." -ForegroundColor Green
$git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $git) {
    Write-Host "未检测到 Git，正在通过 winget 安装..." -ForegroundColor Yellow
    $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $winget) { throw "未找到 winget，请手动安装 Git。" }
    $null = Invoke-NativeCommand -FilePath $winget.Source -Arguments @(
        "install", "Git.Git", "--accept-package-agreements", "--accept-source-agreements"
    )
    Refresh-EnvPath
    $git = Get-Command git.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
}
if (-not $git) { throw "Git 安装失败或尚未加入 PATH。" }
Write-Host "✅ Git: $($git.Source)" -ForegroundColor Gray

# ---------- 3. 检测真正的 curl.exe，避免误识别 PowerShell 别名 ----------
Write-Host "[3/5] 检查 curl..." -ForegroundColor Green
$curl = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $curl) {
    Write-Host "未检测到 curl.exe，正在通过 winget 安装..." -ForegroundColor Yellow
    $winget = Get-Command winget.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $winget) { throw "未找到 winget，请手动安装 curl。" }
    $null = Invoke-NativeCommand -FilePath $winget.Source -Arguments @(
        "install", "cURL.cURL", "--accept-package-agreements", "--accept-source-agreements"
    )
    Refresh-EnvPath
    $curl = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
}
if (-not $curl) { throw "curl.exe 安装失败或尚未加入 PATH。" }
Write-Host "✅ curl: $($curl.Source)" -ForegroundColor Gray

# ---------- 4. 安装并实际导入验证 Python 依赖 ----------
Write-Host "[4/5] 检查并安装 Python 依赖..." -ForegroundColor Green
$PipIndexUrls = @()
if ($env:PIP_INDEX_URL) { $PipIndexUrls += $env:PIP_INDEX_URL }
foreach ($candidate in @($TunaPyPI, $OfficialPyPI)) {
    if ($PipIndexUrls -notcontains $candidate) { $PipIndexUrls += $candidate }
}

$pipOk = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @("-m", "pip", "--version") -AllowFailure -Quiet
if (-not $pipOk) {
    $null = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @("-m", "ensurepip", "--upgrade")
}

if (-not (Install-PythonPackages -InstallArguments @("-r", (Join-Path $ScriptDir "requirements.txt")) -Description "安装核心依赖")) {
    throw "requests 与 aiohttp 安装失败，请检查网络或代理设置。"
}

$brotliPresent = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @(
    "-c", "import importlib.util as u; raise SystemExit(0 if u.find_spec('brotlicffi') or u.find_spec('brotli') else 1)"
) -AllowFailure -Quiet
if (-not $brotliPresent) {
    $brotliPresent = Install-PythonPackages -InstallArguments @("brotlicffi") -Description "安装 brotlicffi"
    if (-not $brotliPresent) {
        $brotliPresent = Install-PythonPackages -InstallArguments @("brotli") -Description "安装 brotli 备用实现"
    }
}
if (-not $brotliPresent) { throw "Brotli 解压依赖安装失败。" }

$importsOk = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @(
    "-c", "import requests, aiohttp, importlib.util as u; assert u.find_spec('brotlicffi') or u.find_spec('brotli'); print('dependency import check passed')"
) -AllowFailure
if (-not $importsOk) { throw "Python 依赖已安装但无法导入。" }
Write-Host "✅ Python 依赖安装并验证完成" -ForegroundColor Green

# ---------- 5. 保留已有 .gitignore，只补充运行时条目 ----------
Write-Host "[5/5] 检查运行文件与 .gitignore..." -ForegroundColor Green
$requiredFilesMissing = (-not (Test-Path $PythonScriptPath)) -or (-not (Test-Path (Join-Path $ScriptDir "main.py"))) -or (-not (Test-Path (Join-Path $ScriptDir "proxy_scoring.py")))
if ($requiredFilesMissing) {
    throw "未找到 scheduled_run.py、main.py 或 proxy_scoring.py。"
}
Add-GitIgnoreEntries -Path (Get-RuntimeIgnorePath) -Entries @(
    ".venv/", "__pycache__/", "*.py[cod]", ".cfnb_schedule.lock", "cron.log",
    "config.json", "ip.local.txt", "valid_tokens.txt", "ipinfo_cache.txt", "cfnb.log"
)
Write-Host "✅ 文件检查完成（未覆盖已有 .gitignore）" -ForegroundColor Gray

# ---------- 按配置创建或清理计划任务 ----------
$scheduleEnabled = $true
try {
    $config = Get-Content -Path $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($null -ne $config.ENABLE_SCHEDULED_TASK) {
        $scheduleEnabled = [System.Convert]::ToBoolean($config.ENABLE_SCHEDULED_TASK)
    }
} catch {
    throw "无法读取 config.json 中的 ENABLE_SCHEDULED_TASK：$_"
}

if (-not $scheduleEnabled) {
    Write-Host "[5/5] 自动定时优选已关闭，正在清理本项目旧计划任务..." -ForegroundColor Yellow
    try {
        $null = Remove-ProjectScheduledTask -Name $TaskName
    } catch {
        throw "无法关闭本项目计划任务：$_"
    }
    Write-Host "✅ 已确认本项目计划任务不存在；需要时请手动运行 main.py" -ForegroundColor Green
} else {
    $firstRunTime = Get-NextAlignedTime -IntervalMinutes $TaskIntervalMinutes
    $startBoundaryStr = $firstRunTime.ToString("yyyy-MM-ddTHH:mm:ss")
    $startTimeDisplay = $firstRunTime.ToString("HH:mm")
    Write-Host "[5/5] 正在配置 Windows 计划任务 '$TaskName'..." -ForegroundColor Yellow

    $taskCreated = $false
    try {
        $null = Remove-ProjectScheduledTask -Name $TaskName
        $taskService = New-Object -ComObject Schedule.Service
        $taskService.Connect()
        $rootFolder = $taskService.GetFolder("\")

        $taskDefinition = $taskService.NewTask(0)
        $taskDefinition.RegistrationInfo.Description = "Cloudflare CDN 中国忙时每15分钟、非忙时每30分钟优选"
        $taskDefinition.Principal.LogonType = 5
        $taskDefinition.Principal.RunLevel = 1
        $taskDefinition.Settings.Enabled = $true
        $taskDefinition.Settings.StartWhenAvailable = $true
        $taskDefinition.Settings.AllowHardTerminate = $true
        $taskDefinition.Settings.ExecutionTimeLimit = "PT3H"
        $taskDefinition.Settings.MultipleInstances = 2
        $taskDefinition.Settings.Priority = 4
        $taskDefinition.Settings.DisallowStartIfOnBatteries = $false
        $taskDefinition.Settings.StopIfGoingOnBatteries = $false

        $trigger = $taskDefinition.Triggers.Create(1)
        $trigger.StartBoundary = $startBoundaryStr
        $trigger.Repetition.Interval = "PT${TaskIntervalMinutes}M"
        $trigger.Repetition.StopAtDurationEnd = $false
        $trigger.Enabled = $true

        $action = $taskDefinition.Actions.Create(0)
        $action.Path = $PythonExePath
        $action.Arguments = "-X utf8 `"$PythonScriptPath`""
        $action.WorkingDirectory = $WorkingDirectory

        $rootFolder.RegisterTaskDefinition($TaskName, $taskDefinition, 6, "SYSTEM", $null, 5) | Out-Null
        $taskCreated = $true
        Write-Host "✅ 计划任务创建成功（COM，SYSTEM，每15分钟检查）" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ COM 创建失败：$_" -ForegroundColor Yellow
        Write-Host "  尝试 schtasks 备用方式..." -ForegroundColor Yellow
        $taskCommand = "`"$PythonExePath`" -X utf8 `"$PythonScriptPath`""
        $schtasksOk = Invoke-NativeCommand -FilePath "schtasks.exe" -Arguments @(
            "/Create", "/TN", $TaskName,
            "/TR", $taskCommand,
            "/SC", "MINUTE", "/MO", "$TaskIntervalMinutes",
            "/ST", $startTimeDisplay,
            "/RU", "SYSTEM", "/RL", "HIGHEST", "/F"
        ) -AllowFailure
        if ($schtasksOk) {
            $taskCreated = $true
            Write-Host "✅ 计划任务创建成功（schtasks）" -ForegroundColor Green
        }
    }
    if (-not $taskCreated) { throw "Windows 计划任务创建失败。" }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 🎉 部署完成！" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. 在 config.json 填写 GITHUB_SYNC_TOKEN、GITHUB_SYNC_REPOSITORY 和 GITHUB_SYNC_FIELD_ID" -ForegroundColor White
Write-Host "2. 微信推送默认关闭；需要时再填写 WxPusher 信息并启用" -ForegroundColor White
if ($scheduleEnabled) {
    Write-Host "3. 计划任务使用固定解释器：$PythonExePath" -ForegroundColor Gray
} else {
    Write-Host "3. 手动运行：& `"$PythonExePath`" -X utf8 `"$(Join-Path $ScriptDir 'main.py')`"" -ForegroundColor Gray
}

$response = Read-Host "是否立即运行一次 main.py 进行测试？(Y/N)"
if ($response -match '^[Yy]$') {
    $runOk = Invoke-NativeCommand -FilePath $PythonExePath -Arguments @(
        "-X", "utf8", (Join-Path $ScriptDir "main.py")
    ) -AllowFailure
    if (-not $runOk) { Write-Host "⚠️ main.py 测试运行失败，请根据上方日志检查配置。" -ForegroundColor Yellow }
}

Read-Host "`n部署完成，按 Enter 键退出"
