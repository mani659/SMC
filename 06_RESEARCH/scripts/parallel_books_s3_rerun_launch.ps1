param(
    [string]$RepoRoot = "D:\Gold Scripts\MQL5\SMC",
    [string]$OutDir = "06_RESEARCH\results\parallel_books_s3_rerun"
)
$ErrorActionPreference = "Stop"

# S3 POST-R1 RE-BASELINE — detached launcher (same product_1y window, resume-.done).
# Fresh out dir so the pre-R1 .done markers never mask a post-R1 run. The harness
# skips any run whose .done exists, so a relaunch resumes exactly where it stopped.

$outDir = Join-Path $RepoRoot $OutDir
$scriptPath = Join-Path $RepoRoot "06_RESEARCH\scripts\parallel_books_full_bt.py"
$stdoutLog = Join-Path $outDir "stdout.log"
$stderrLog = Join-Path $outDir "stderr.log"
$launchLog = Join-Path $outDir "launcher.log"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

function Log-Launch { param([string]$Msg)
    $line = "$([DateTime]::UtcNow.ToString('o'))  $Msg"
    Write-Host $line; Add-Content -Path $launchLog -Value $line
}

Log-Launch "=== S3 POST-R1 RE-BASELINE LAUNCH ==="
$pidFile = Join-Path $outDir "pid.txt"
if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile -Raw).Trim()
    if ($oldPid -match '^\d+$' -and (Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue)) {
        Log-Launch "ABORT: harness PID $oldPid still alive."; exit 1
    }
}

$env:PYTHONUNBUFFERED = "1"; $env:PYTHONIOENCODING = "utf-8"
$pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyExe) { $pyExe = "python" }

$argLine = "--books F,B,C,E,A --segments nov24,dec24,jan25,feb25,mar25,apr25,may25,jun25,jul25,aug25,sep25,oct25 --out `"$outDir`""
$cmdLine = "cmd.exe /c `"`"$pyExe`" `"$scriptPath`" $argLine >> `"$stdoutLog`" 2>> `"$stderrLog`"`""
Log-Launch "CommandLine: $cmdLine"

$wmi = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $cmdLine; CurrentDirectory = $RepoRoot
}
if ($wmi.ReturnValue -ne 0) { Log-Launch "ERROR WMI $($wmi.ReturnValue)"; exit 1 }
$cmdPid = $wmi.ProcessId
Log-Launch "Detached cmd.exe PID: $cmdPid"

$pyPid = "pending"
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-CimInstance Win32_Process |
        Where-Object { $_.ParentProcessId -eq $cmdPid -and $_.Name -like "python*" }
    if ($proc) { $pyPid = "$($proc.ProcessId)"; break }
}
Log-Launch "Harness python PID: $pyPid"
if ($pyPid -ne "pending") { $pyPid | Set-Content -Path $pidFile -NoNewline; exit 0 }
exit 1
