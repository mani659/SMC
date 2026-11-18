param(
    [string]$RepoRoot = "D:\Gold Scripts\MQL5\SMC",
    [string]$Books = "F,B,C,E,A",
    [int]$Days = 0,
    [string]$Segments = "nov24,dec24,jan25,feb25,mar25,apr25,may25,jun25,jul25,aug25,sep25,oct25"
)
$ErrorActionPreference = "Stop"

# FULL-YEAR PARALLEL-BOOKS RESEARCH BT — detached launcher.
# Launch via WMI Win32_Process.Create so the run is parented under WmiPrvSE and
# survives IDE reloads, terminal closure and agent tool cleanup. The agent
# session is NOT held open: the python process owns its own log/pid/heartbeat.

$scriptPath = Join-Path $RepoRoot "06_RESEARCH\scripts\parallel_books_full_bt.py"
if ($Days -gt 0) {
    $outDir = Join-Path $RepoRoot "06_RESEARCH\results\parallel_books_full_bt\_preflight"
} else {
    $outDir = Join-Path $RepoRoot "06_RESEARCH\results\parallel_books_full_bt"
}
$stdoutLog = Join-Path $outDir "stdout.log"
$stderrLog = Join-Path $outDir "stderr.log"
$launchLog = Join-Path $outDir "launcher.log"

if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

function Log-Launch {
    param([string]$Msg)
    $ts = [DateTime]::UtcNow.ToString("o")
    $line = "$ts  $Msg"
    Write-Host $line
    Add-Content -Path $launchLog -Value $line
}

Log-Launch "=== PARALLEL BOOKS FULL BT LAUNCH ==="
Log-Launch "Script: $scriptPath"
Log-Launch "Books: $Books  Days: $Days  Out: $outDir"

# Refuse a second concurrent run (the harness is resumable, not concurrent).
$pidFile = Join-Path $outDir "pid.txt"
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -Raw).Trim()
    if ($oldPid -match '^\d+$') {
        $existing = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($existing) {
            Log-Launch "ABORT: harness PID $oldPid is still alive (resume is a re-launch only after it exits)."
            exit 1
        }
    }
}

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"
$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) { $pyExe = "python" }
Log-Launch "Using Python: $pyExe"

$argLine = "`"$scriptPath`" --books $Books --segments $Segments"
if ($Days -gt 0) { $argLine = "$argLine --days $Days" }
$argLine = "$argLine --out `"$outDir`""

$cmdLine = "cmd.exe /c `"`"$pyExe`" $argLine >> `"$stdoutLog`" 2>> `"$stderrLog`"`""
Log-Launch "CommandLine: $cmdLine"

$wmiRes = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine
    CurrentDirectory = $RepoRoot
}
if ($wmiRes.ReturnValue -ne 0) {
    Log-Launch "ERROR: WMI launch failed, ReturnValue=$($wmiRes.ReturnValue)"
    exit 1
}
$cmdPid = $wmiRes.ProcessId
Log-Launch "Detached cmd.exe launcher PID: $cmdPid"

$pyPid = "pending"
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-CimInstance Win32_Process |
        Where-Object { $_.ParentProcessId -eq $cmdPid -and $_.Name -like "python*" }
    if ($proc) { $pyPid = "$($proc.ProcessId)"; break }
}
Log-Launch "Harness python PID: $pyPid"
Log-Launch "Stdout: $stdoutLog"
Log-Launch "Stderr: $stderrLog"
Log-Launch "Heartbeat: $outDir\heartbeat.json"
Log-Launch "Verdict: $outDir\verdict.json   Exit code: $outDir\EXIT_CODE.txt"
if ($pyPid -ne "pending") {
    "Resume later: read verdict.json / EXIT_CODE.txt / stdout.log tail; harness skips finished runs." |
        Add-Content -Path $launchLog
    exit 0
}
exit 1
