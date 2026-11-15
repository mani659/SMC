param(
    [string]$RepoRoot = "D:\Gold Scripts\MQL5\SMC"
)
$ErrorActionPreference = "Stop"

# INSTRUMENTED FILL-LEG CAPTURE - single-pass detached launcher.
# DIAGNOSTIC ONLY - NOT PERFORMANCE / NOT EDGE.
# Clone of the proven launch_detached.ps1 WMI detach pattern (survives
# terminal/IDE closure), targeting the capture script and its OWN out dir.
# The prior coupled_mtf_full_menu_diag/** DONE trees are never touched.

$scriptPath = Join-Path $RepoRoot "06_RESEARCH\scripts\coupled_mtf_fill_leg_capture.py"
$outDir = Join-Path $RepoRoot "06_RESEARCH\results\coupled_mtf_fill_leg_capture"
$stdoutLog = Join-Path $outDir "capture_stdout.log"
$stderrLog = Join-Path $outDir "capture_stderr.log"
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

Log-Sup "=== FILL-LEG CAPTURE LAUNCHER INITIALIZED ==="
Log-Sup "Script: $scriptPath"

# Refuse to double-launch: a live heartbeat within the last 120s means a
# capture process is already running.
$hb = Join-Path $outDir "runner_heartbeat.json"
if (Test-Path $hb) {
    try {
        $hbObj = Get-Content $hb -Raw | ConvertFrom-Json
        $hbAge = [DateTime]::UtcNow - [DateTime]::Parse($hbObj.timestamp_utc)
        if ($hbAge.TotalSeconds -lt 120) {
            Log-Sup "Active heartbeat ($($hbAge.TotalSeconds.ToString('0'))s old, pid=$($hbObj.pid)); NOT launching a second capture."
            exit 0
        }
    } catch {
        Log-Sup "Heartbeat unreadable; proceeding with launch."
    }
}

if (Test-Path (Join-Path $outDir "run1\DONE")) {
    Log-Sup "run1 DONE already present in capture tree. Nothing to launch."
    exit 0
}

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) {
    $pyExe = "python"
}

Log-Sup "Using Python: $pyExe"

# Launch fully detached via WMI Win32_Process.Create
# Breaks out of any caller Job Object and terminal/IDE session tree,
# parenting under WmiPrvSE so it survives terminal closure, IDE reloads, and tool exits.
$cmdLine = "cmd.exe /c `"`"$pyExe`" `"$scriptPath`" >> `"$stdoutLog`" 2>> `"$stderrLog`"`""
Log-Sup "Launching detached single-pass capture via WMI (~6h expected)..."

$wmiRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine
    CurrentDirectory = $RepoRoot
}

if ($wmiRes.ReturnValue -ne 0) {
    Log-Sup "ERROR: Failed to launch process via WMI, ReturnValue=$($wmiRes.ReturnValue)"
    exit 1
}

$cmdPid = $wmiRes.ProcessId
Log-Sup "Background capture cmd.exe launcher PID: $cmdPid"

$pyPidStr = "pending"
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 1
    $pyProc = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $cmdPid -and $_.Name -like "python*" }
    if ($pyProc) {
        $pyPidStr = "$($pyProc.ProcessId)"
        Log-Sup "Active capture Python PID: $pyPidStr"
        break
    }
}

$ts = [DateTime]::UtcNow.ToString("o")
Add-Content -Path (Join-Path $outDir "capture_progress.log") -Value "$ts  LAUNCHED pid=$cmdPid (python_pid=$pyPidStr)"

Log-Sup "Stdout: $stdoutLog"
Log-Sup "Stderr: $stderrLog"
Log-Sup "Heartbeat: $hb"
Log-Sup "Legs: $outDir\run1\fill_legs.jsonl"
