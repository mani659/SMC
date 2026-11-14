"""PFE-1.5 smoke — both named compositions run end-to-end without exception.

Runs the SHARED research composition (``phase3_structure_funnel``) twice on a
short window:

* ``--composition seek`` — the O1–O5 continuity path (PipelineAdapter only);
* ``--composition menu`` — the shipped live ``PRODUCT_V1`` law
  (``ProductMenuEngine`` sweep → one-shot LTF confirmation, winners queued into
  the same adapter/risk seam).

It is a smoke, not a measurement: it proves both modes execute, that the menu
mode actually drives ``ProductMenuEngine`` (episodes/winners counters), and that
the seek mode is untouched (``menu_episodes == 0``). Window and artifacts are
throwaway; the 6-month product run is PFE-2.

Usage::

    python 06_RESEARCH/scripts/pfe15_composition_smoke.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "06_RESEARCH" / "scripts" / "phase3_structure_funnel.py"
OUT_ROOT = REPO_ROOT / "06_RESEARCH" / "results" / "pfe15_smoke"
LOAD_FROM = "2025-09-15"
EXEC_FROM = "2025-10-01"
EXEC_TO = "2025-10-03"


def _run(composition: str) -> dict:
    out = OUT_ROOT / composition
    out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(SCRIPT),
        "--tag", f"pfe15_smoke_{composition}",
        "--out-root", str(out),
        "--load-from", LOAD_FROM,
        "--exec-from", EXEC_FROM,
        "--exec-to", EXEC_TO,
        "--composition", composition,
    ]
    print(f"[pfe15] {composition}: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=REPO_ROOT / "04_SRC",
                          capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-4000:], file=sys.stderr)
        print(proc.stderr[-4000:], file=sys.stderr)
        raise SystemExit(f"composition {composition} failed "
                         f"(exit {proc.returncode})")
    summary = json.loads((out / "funnel_summary.json").read_text(encoding="utf-8"))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args(argv)
    seek = _run("seek")
    menu = _run("menu")
    fields = ["composition", "bars_m5", "htf_batches", "batch_errors",
              "armed", "routes", "placed", "fills", "menu_episodes",
              "menu_winners", "menu_errors"]
    table = {name: {f: summary.get(f) for f in fields}
             for name, summary in (("seek", seek), ("menu", menu))}
    print(json.dumps(table, indent=2))
    problems = []
    if seek.get("composition") != "seek" or menu.get("composition") != "menu":
        problems.append("composition stamp missing or wrong")
    if seek.get("menu_episodes") != 0:
        problems.append("seek mode drove the menu engine")
    if menu.get("menu_errors"):
        problems.append(f"menu errors: {menu.get('menu_errors')}")
    if not menu.get("menu_episodes"):
        problems.append("menu mode opened no episodes (engine not exercised)")
    if menu.get("htf_batches", 0) == 0:
        problems.append("menu mode ran no HTF batches")
    if problems:
        print("SMOKE: FAIL — " + "; ".join(problems), file=sys.stderr)
        return 1
    print("SMOKE: PASS — both compositions ran; menu engine exercised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
