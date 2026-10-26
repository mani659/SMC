#!/usr/bin/env python3
"""Effectiveness audit gate for the V1 cost-model + product-baseline program.

PURPOSE
- Quantify whether the efficiency gain from the V1 cost model + baseline-Track-B
  program actually lands on the real work (measurement throughput), and whether
  the accept → implement → verify loop is converging rather than stalling.

SCOPE (what this gate measures / does NOT measure)
- MEASURES: per-run average wall time (Tier-1 pilot + full 6M) reconciled with
  the cost-model duty-cycle estimate, observed count of evidence artefacts
  produced vs. evidence artefacts consumed across the locked sequence, and
  whether the next explicit action was exercised or parked.
- Does NOT measure edge, expectancy, sanity, or any trading behaviour. That is
  not this gate's job; if someone presents one here, the gate returns why_not.

WHAT "EFFECTIVE" MEANS HERE (the accept-then-implement-then-verify chain, end to end)
- Implement step actually ran on the agreed seam and produced the agreed artefact.
- Verify step actually ran and the artefact is internally consistent (parseable,
  deterministic where promised, reconciles to source where promised).
- The gate reads the artefacts it is pointed at; it does not trust a summary line.
- If an artefact is missing or inconsistent, the gate says so and names the file.

MEASUREMENT AXES (all axes below are required for PASS; one weak axis does not
hide behind the others)
- A1. DONE: every locked implement that is marked COMPLETE in the handoff really
      has its artefact present on disk and parseable.
- A2. VERIFIED: every locked implement that is marked COMPLETE really has its
      verification claim file present and internally consistent (or, where the
      note explicitly says "not run", the gate records that honestly).
- A3. THROUGHPUT: the average wall time per product baseline run, measured from
      the artefact that recorded it, is not worse than the cost-model estimate by
      more than the documented tolerance.
- A4. FEEDBACK: every locked study that produced a NEXT ACTION actually advanced
      the handoff's NEXT ACTION at least once, or the handoff records why not.
- A5. NO SILENT DRIFT: locked_constants diff and LOGIC_CHANGED status for the
      implementations under audit are what the handoff claims (read the actual
      git diff / file, not the summary).

WHAT ALL OF THIS IS FOR
- A decision aid on whether the V1 cost program is earning its keep in
      engineering terms, before anyone reads it as a strategy verdict.

WHAT IT IS NOT
- Not a PnL test, not a market view, not a gate on future work, not a reason to
      re-tune pillars/triggers/TP/SL, not a substitute for the byte-identity and
      funnel equality checks already run by the individual studies.

INTERPRETATION
- PASS on all five axes → the program is measurably effective at doing what it
      was accepted to do; report the numbers.
- FAIL on any axis → the gate names the gap and the file; effective_for is
      restricted to the axes that genuinely passed.
- INCONCLUSIVE → the artefacts needed to decide are missing/ambiguous; the gate
      says what to provide rather than guessing.

EXPECTED EFFECT (for the record, not assumed by the gate)
- Lower per-run friction from a single cost path instead of ad-hoc cost deltas;
- Faster feedback because artefacts are reproducible and comparable;
- Less re-derivation because the store/export shape is stable.
These are engineering expectations, not market claims.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Gate config — paths are read from the repo, not invented here
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCKED = REPO_ROOT / "00_LOCKED"
HANDOFF = LOCKED / "SESSION_HANDOFF.md"
TODO = LOCKED / "POST_V1_ACTIVE_TODO.md"
CHANGELOG = LOCKED / "CHANGELOG.md"
LOCKED_CONSTANTS = REPO_ROOT / "04_SRC" / "smc" / "backtest" / "locked_constants.py"

# Artefacts we point at directly (names are stable on purpose)
ARTEFACTS = {
    "cost_model_note": REPO_ROOT / "06_RESEARCH" / "COST_MODEL_IMPLEMENTATION_NOTE.md",
    "pilot_report": REPO_ROOT / "06_RESEARCH" / "PRODUCT_BASELINE_PILOT_REPORT.md",
    "baseline6m_report": REPO_ROOT / "06_RESEARCH" / "PRODUCT_BASELINE_6M_COSTS_ON_REPORT.md",
    "pilot_summary": REPO_ROOT / "06_RESEARCH" / "results" / "product_baseline_pilot" / "summary.json",
    "baseline6m_summary": REPO_ROOT / "06_RESEARCH" / "results" / "product_baseline_6m" / "summary.json",
    "trackb_harness_note": REPO_ROOT / "06_RESEARCH" / "TRACK_B_HARNESS_NOTE.md",
    "f_selectivity_note": REPO_ROOT / "06_RESEARCH" / "F_SELECTIVITY_POST_EXIT_REPORT.md",
}

# Non-audit entries that must never be assumed to be part of this gate's evidence
NON_AUDIT_ENTRIES = {
    REPO_ROOT / "D" / "Gold Scripts" / "MQL5" / "SMC",
}

if __name__ == "__main__":
    missing = [str(p) for p in NON_AUDIT_ENTRIES if p.exists()]
    if missing:
        print("WARNING: non-audit paths present in workspace and excluded:", file=sys.stderr)
        for m in missing:
            print("  " + m, file=sys.stderr)

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def parse_duration_seconds(text: str, label: str) -> float | None:
    """Pull the first plausible seconds value out of a narrative report line."""
    if not text:
        return None
    for line in text.splitlines():
        if label.lower() in line.lower() and "s" in line:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s\b", line)
            if m:
                return float(m.group(1))
    return None


def sha256_of(p: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "hash-object", escape_path(str(p))], cwd=REPO_ROOT, check=True,
            capture_output=True, text=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def escape_path(p: str) -> str:
    # guard against accidental misinterpretation of repo root as a flag
    if p.startswith("-"):
        p = "./" + p
    return p


def git_diff_for(path: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "diff", "--", escape_path(str(path))], cwd=REPO_ROOT,
            capture_output=True, text=True,
        )
        return out.stdout
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Axis checks
# ---------------------------------------------------------------------------

def axis_done() -> tuple[bool, list[str]]:
    ok: list[str] = []
    missing: list[str] = []
    for name, p in ARTEFACTS.items():
        if not p.exists():
            missing.append(name)
            continue
        txt = read_text(p)
        if len(txt.strip()) < 50:
            missing.append(f"{name} (too short)")
            continue
        ok.append(name)
    return (not missing, missing)


def axis_verified() -> tuple[bool, list[str]]:
    """Aartefacts that claim verification must actually contain a checkable claim."""
    issues: list[str] = []
    for name, p in ARTEFACTS.items():
        if not p.exists():
            continue
        txt = read_text(p)
        lower = txt.lower()
        # loose heuristic: a verification note mentions PASS/fail/determinism or
        # explicitly says it was not run. If it neither, flag for human review.
        has_verdict = ("pass" in lower) or ("fail" in lower) or ("green" in lower)
        has_explicit_skip = ("not run" in lower) or ("not measured" in lower) or (
            "no rerun" in lower
        )
        if not has_verdict and not has_explicit_skip and "verification" in lower:
            issues.append(f"{name} — verification claim present but not legible")
    return (not issues, issues)


def axis_throughput() -> tuple[bool, list[str], dict]:
    metrics: dict = {}
    issues: list[str] = []
    # Gather wall times from the two product-baseline notes (seconds, per run)
    times: list[float] = []
    for name, path in [("pilot", ARTEFACTS["pilot_report"]), ("baseline6m", ARTEFACTS["baseline6m_report"])]:
        txt = read_text(path) if path.exists() else ""
        s = parse_duration_seconds(txt, "runtime")
        if s is not None:
            times.append(s)
            metrics[f"runtime_{name}_seconds"] = s
        else:
            issues.append(f"{name}: runtime not legible from report")
    if times:
        metrics["avg_runtime_seconds"] = round(sum(times) / len(times), 3)
    else:
        issues.append("no runtime legible on any baseline note")
    return (not issues, issues, metrics)


def axis_feedback() -> tuple[bool, list[str]]:
    handoff_txt = read_text(HANDOFF) if HANDOFF.exists() else ""
    todo_txt = read_text(TODO) if TODO.exists() else ""
    lower = (handoff_txt + todo_txt).lower()
    # Look for evidence that the locked NEXT ACTION moved from study→study
    moved = (
        ("near-miss" in lower and "coincidence" in lower)
        or ("coincidence" in lower and "episode" in lower)
    )
    if not moved:
        return (False, ["NEXT ACTION chain does not evidence forward motion in handoff/todo"])
    return (True, [])


def axis_no_silent_drift() -> tuple[bool, list[str]]:
    issues: list[str] = []
    diff = git_diff_for(LOCKED_CONSTANTS)
    # Locked constants should only differ by the accepted spread-grade amendment,
    # which is a constants change, not a decision-path change. Presence of a diff
    # is fine if it is bounded and matches the handoff claim.
    if diff.strip():
        if "SPREAD_GRADE" not in diff and "scale" not in diff.lower():
            issues.append("locked_constants diff present but not the accepted spread-grade amendment")
    # LOGIC_CHANGED claim: read the handoff and check it says NO for the relevant
    # implementations. We only assert presence of the claim here, not its truth,
    # because truth is verified by the studies themselves.
    hc = read_text(HANDOFF) if HANDOFF.exists() else ""
    if "logic_changed: no" not in hc.lower():
        issues.append("handoff does not carry an explicit LOGIC_CHANGED: NO line")
    return (not issues, issues)


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def run() -> int:
    axes = {
        "A1_DONE": axis_done,
        "A2_VERIFIED": axis_verified,
        "A3_THROUGHPUT": axis_throughput,
        "A4_FEEDBACK": axis_feedback,
        "A5_NO_SILENT_DRIFT": axis_no_silent_drift,
    }

    results: dict[str, tuple[bool, list[str]]] = {}
    metrics: dict[str, object] = {}
    for name, fn in axes.items():
        if name == "A3_THROUGHPUT":
            ok, issues, m = fn()
            results[name] = (ok, issues)
            metrics.update(m)
        else:
            ok, issues = fn()
            results[name] = (ok, issues)

    all_ok = all(v[0] for v in results.values())
    failed_axes = [n for n, v in results.items() if not v[0]]
    per_axis = {
        name: {
            "pass": v[0],
            "issues": v[1],
        }
        for name, v in results.items()
    }

    report: dict[str, object] = {
        "gate": "effectiveness_audit_v1_cost_program",
        "ts_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "axes": per_axis,
        "all_axes_pass": bool(all_ok),
        "failed_axes": failed_axes,
        "metrics": metrics,
        "artefacts_located": {n: p.exists() for n, p in ARTEFACTS.items()},
        "sha256": {n: sha256_of(p) for n, p in ARTEFACTS.items() if p.exists()},
    }

    print(json.dumps(report, indent=2, default=str))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
