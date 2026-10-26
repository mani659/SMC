# POST-V1 PHASE C — spread-sensitivity ladder launcher (§5 requirement).
#
# Launches the frozen config once per constant spread on ONE representative
# window, each run detached (survives the launching shell), with its own
# out-root, log and stderr file.  The ladder is PAIRED: spread 0.00 is the
# window's own reference run, so every spread is compared against an identical
# cold-start execution of the same window (the full-period baseline used the
# same config but different segment boundaries).
#
# Window and spread rationale: see 06_RESEARCH/PHASE_C_BASELINE_REPORT.md
# (calibration evidence: 06_RESEARCH/results/phase_c_spread_calibration.json —
# the §28.5 gate threshold is 0.15 x ATR x grade multiplier, so the ladder is
# chosen to bracket the threshold range of the window, anchored on the
# plan-documented representative retail value 0.35).
#
# Re-running the SAME command resumes at segment granularity (manifest
# fingerprint checkpoint).  Artifacts are never deleted by this script.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File 06_RESEARCH/scripts/phase_c_spread_sens_launch.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # repo root
Set-Location $root

$windowFrom = '2023-02-01'
$windowTo   = '2023-04-30'

$ladder = @(
  @{ tag = 'sens0p00'; spread = '0.00' },
  @{ tag = 'sens0p05'; spread = '0.05' },
  @{ tag = 'sens0p15'; spread = '0.15' },
  @{ tag = 'sens0p35'; spread = '0.35' }
)

foreach ($run in $ladder) {
    $tag    = $run.tag
    $spread = $run.spread
    $outRoot = "06_RESEARCH/results/phase_c_spread_sens_$tag"
    $log     = "06_RESEARCH/results/phase_c_spread_sens_$tag.log"
    $err     = "06_RESEARCH/results/phase_c_spread_sens_$tag.err"

    $args = @(
        '06_RESEARCH/scripts/phase_c_baseline_backtest.py',
        '--tag', $tag,
        '--out-root', $outRoot,
        '--from', $windowFrom,
        '--to', $windowTo,
        '--spread', $spread
    )
    $proc = Start-Process -FilePath 'python' -ArgumentList $args `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    Write-Output "launched $tag (spread $spread) pid=$($proc.Id) -> $outRoot"
}

Write-Output "window $windowFrom -> $windowTo ; 4 runs detached"
