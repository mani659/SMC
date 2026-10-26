import zipfile, tempfile, sys, shutil, os, subprocess, json
from pathlib import Path

ZIP = Path(r"D:\Gold Scripts\MQL5\SMC\dist\SMC_v1.1-test.1_tester.zip")
ROOT = Path(r"D:\Gold Scripts\MQL5\SMC")


def check(label, condition, fail_note=None):
    status = "OK" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition and fail_note:
        print("    note:", fail_note)


print("=" * 70)
print("TESTER RELEASE VERIFICATION")
print("=" * 70)

# ---- artifact presence (on disk) ----
for k, p in {
    "pdf": ROOT / "dist" / "TESTER_SETUP_GUIDE.pdf",
    "readme_dist": ROOT / "dist" / "TESTER_README.md",
    "readme_rel": ROOT / "06_RESEARCH" / "releases" / "TESTER_README.md",
    "zip": ROOT / "dist" / "SMC_v1.1-test.1_tester.zip",
    "version": ROOT / "dist" / "VERSION.txt",
}.items():
    check(f"artifact exists: {k}", p.exists(), f"missing: {p}")

# ---- pdf validity ----
try:
    import PyPDF2
    r = PyPDF2.PdfReader(str(ROOT / "dist" / "TESTER_SETUP_GUIDE.pdf"))
    check("PDF opens and parses", len(r.pages) >= 1)
    check("PDF has >= 4 pages", len(r.pages) >= 4)
    txt = "\n".join((p.extract_text() or "") for p in r.pages)
    for needle in ["Step 1", "Step 8", "Hard rule", "Ctrl+C", "dry_run"]:
        check(f"PDF mentions '{needle}'", needle.lower() in txt.lower())
except Exception as e:
    check("PDF opens and parses", False, str(e))

# ---- zip contents by path suffix ----
def in_zip(name_set, suffix):
    return any(n.endswith(suffix) for n in name_set)


with zipfile.ZipFile(ZIP) as z:
    names = set(z.namelist())

    # Bat and config at zip root
    check("zip contains top-level run_live.bat", in_zip(names, "/run_live.bat"))
    check("zip contains top-level VERSION.txt", in_zip(names, "/VERSION.txt"))
    check("zip contains top-level SUPPORT.txt", in_zip(names, "/SUPPORT.txt"))
    check("zip contains top-level TESTER_README.md", in_zip(names, "/TESTER_README.md"))
    check("zip contains top-level TESTER_SETUP_GUIDE.pdf", in_zip(names, "/TESTER_SETUP_GUIDE.pdf"))

    # Config tree
    check("zip contains config/live_tester.json",
          in_zip(names, "/config/live_tester.json"))
    check("zip contains config/live_demo.json",
          in_zip(names, "/config/live_demo.json"))

    # Runtime package
    check("zip contains 04_SRC/smc/__init__.py",
          in_zip(names, "/04_SRC/smc/__init__.py"))
    check("zip contains 04_SRC/smc/live/run_operator.py",
          in_zip(names, "/04_SRC/smc/live/run_operator.py"))
    check("zip contains 04_SRC/smc/config/locked_constants.py",
          in_zip(names, "/04_SRC/smc/config/locked_constants.py"))

    # Watchdog
    check("zip contains mql5/SMC_Safety_Watchdog.mq5",
          in_zip(names, "/mql5/SMC_Safety_Watchdog.mq5"))

    # ---- no forbidden inclusions in zip ----
    forbidden = [".git", "__pycache__", "results/", ".venv", ".env", "credentials", ".exe"]
    bad = [n for n in names if any(b.lower() in n.lower() for b in forbidden)]
    check("zip has no forbidden artifacts (.git, pycache, results, venv, secrets, .exe)",
          not bad, f"found: {bad[:8]}")

# ---- unzip + bat-model smoke ----
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(td)
    root = td / "SMC_v1.1-test.1"

    for pc in root.rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)

    check("unzips to single top-level folder", (root / "run_live.bat").exists())

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(
        [sys.executable, "04_SRC/smc/live/run_operator.py", "--help"],
        cwd=str(root),
        capture_output=True,
        text=True,
        env=env,
        timeout=90,
    )
    help_ok = r.returncode == 0 and "SMC Phase D operator session" in r.stdout
    check("bat-model: run_operator --help succeeds from extracted folder", help_ok,
          r.stderr[:300] if not help_ok else None)

    cfg_path = root / "config" / "live_tester.json"
    cfg = json.loads(cfg_path.read_text("utf-8"))
    check("live_tester.json is valid JSON", True)
    check("live_tester.json dry_run=true", cfg.get("dry_run") is True)
    check("live_tester.json require_demo=true", cfg.get("require_demo") is True)
    check("live_tester.json detection_timeframes == [H4,H1]",
          cfg.get("detection_timeframes") == ["H4", "H1"])
    check("live_tester.json placeholder terminal_path",
          cfg.get("terminal_path", "").endswith("terminal64.exe"))

    ver_txt = (root / "VERSION.txt").read_text("utf-8")
    check("VERSION.txt contains v1.1-test.1", "v1.1-test.1" in ver_txt)
    check("VERSION.txt contains git SHA", "Git SHA" in ver_txt)
    check("VERSION.txt mentions python version", "Python" in ver_txt)

    readme_txt = (root / "TESTER_README.md").read_text("utf-8")
    check("TESTER_README contains v1.1-test.1", "v1.1-test.1" in readme_txt)

# ---- banned-content checks (release package) ----
print("\n--- banned-content checks (release package) ---")
with zipfile.ZipFile(ZIP) as z:
    names = z.namelist()
    test_shims = [n for n in names if "tests" in n.split("/") and n.endswith(".py")]
    check("zip does not bundle the repo test suite as runnable tests",
          not test_shims, f"found: {test_shims[:6]}")
    has_locked = any(n.endswith("locked_constants.py") for n in names)
    check("zip includes locked_constants.py (expected; it is part of smc package)",
          has_locked)

print("\nDone.")
