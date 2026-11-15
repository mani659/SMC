param(
    [string]$RepoRoot = "D:\Gold Scripts\MQL5\SMC",
    [int]$MaxRestarts = 3
)
$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $RepoRoot "06_RESEARCH\scripts\run_full_menu_background.py"
$outDir = Join-Path $RepoRoot "06_RESEARCH\results\coupled_mtf_full_menu_diag"
$stdoutLog = Join-Path $outDir "chain_stdout.log"
$stderrLog = Join-Path $outDir "chain_stderr.log"
$supervisorLog = Join-Path $outDir "supervisor.log"

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

function Log-Sup {
    param([string]$Msg)
    $ts = [DateTime]::UtcNow.ToString("o")
    $line = "$ts  $Msg"
    Write-Host $line
    Add-Content -Path $supervisorLog -Value $line
}

Log-Sup "=== SUPERVISOR LAUNCHER INITIALIZED ==="
Log-Sup "Script: $scriptPath"

# Ensure environment variables for clean unbuffered logging
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

# Check if DONE is already achieved
$done1 = Test-Path (Join-Path $outDir "run1\DONE")
$done2 = Test-Path (Join-Path $outDir "run2\DONE")
if ($done1 -and $done2) {
    Log-Sup "Both run1 and run2 have DONE markers. Nothing to launch."
    exit 0
}

# Resolve python executable path
$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) {
    $pyExe = "python"
}

Log-Sup "Using Python: $pyExe"

# Launch fully detached via WMI Win32_Process.Create
# This breaks out of any caller Job Object and terminal/IDE session tree,
# parenting under WmiPrvSE so it survives terminal closure, IDE reloads, and tool exits.
$cmdLine = "cmd.exe /c `"`"$pyExe`" `"$scriptPath`" >> `"$stdoutLog`" 2>> `"$stderrLog`"`""
Log-Sup "Launching detached background runner via WMI (immune to IDE/terminal lifecycle)..."

$wmiRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine
    CurrentDirectory = $RepoRoot
}

if ($wmiRes.ReturnValue -ne 0) {
    Log-Sup "ERROR: Failed to launch process via WMI, ReturnValue=$($wmiRes.ReturnValue)"
    exit 1
}

$cmdPid = $wmiRes.ProcessId
Log-Sup "Background runner cmd.exe launcher PID: $cmdPid"

# Wait a few seconds to discover child Python process
$pyPidStr = "pending"
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $pyProc = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $cmdPid -and $_.Name -like "python*" }
    if ($pyProc) {
        $pyPidStr = "$($pyProc.ProcessId)"
        Log-Sup "Active background Python PID: $pyPidStr"
        break
    }
}

# Append RESUMED line to chain_progress.log
$chainLog = Join-Path $outDir "chain_progress.log"
$ts = [DateTime]::UtcNow.ToString("o")
Add-Content -Path $chainLog -Value "$ts  RESUMED pid=$cmdPid (python_pid=$pyPidStr)"

Log-Sup "Stdout: $stdoutLog"
Log-Sup "Stderr: $stderrLog"
Log-Sup "Progress: $chainLog"
Log-Sup "Heartbeat: $outDir\runner_heartbeat.json"

