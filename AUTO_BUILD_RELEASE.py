import json, os, shutil, subprocess, zipfile, datetime
from pathlib import Path

ROOT = Path(r"D:/Gold Scripts/MQL5/SMC")
SRC = ROOT / "04_SRC"
DIST = ROOT / "dist"
REL = ROOT / "06_RESEARCH/releases"
DIST.mkdir(parents=True, exist_ok=True)
REL.mkdir(parents=True, exist_ok=True)

VERSION = "v1.1-test.7"
sha_short = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.strip()
sha_full = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()
pyver = subprocess.run(["python", "--version"], capture_output=True, text=True, check=True).stdout.strip()
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def w(path, text, enc="utf-8"):
    path.write_text(text, encoding=enc)
    return path

# VERSION.txt
w(DIST / "VERSION.txt",
  "SMC tester release package\n"
  f"Version: {VERSION}\n"
  f"Git SHA (short): {sha_short}\n"
  f"Git SHA (full): {sha_full}\n"
  f"Python runtime verified on this build machine: {pyver}\n"
  "Origin repo: https://github.com/mani659/SMC\n"
  "\n"
  "IMPORTANT - READ FIRST:\n"
  "This package is a TESTER RUN SURFACE ONLY. It is configuration + runtime + a\n"
  "safety watchdog, not a strategy tuning kit.\n"
  "\n"
  "One-line rule for testers:\n"
  "  Edit ONLY config/live_tester.json if you need to fix the terminal path or\n"
  "  symbol. Do NOT edit anything under 04_SRC/smc/. Do not ask AI to change\n"
  "  strategy or threshold code. If something goes wrong, send VERSION.txt and\n"
  "  the logs - do not patch files.\n"
  "\n"
  f"Built from branch: main\n"
  f"Built on: {now}\n")

# config/live_tester.json
(CONFIG := DIST / "config").mkdir(parents=True, exist_ok=True)
w(CONFIG / "live_tester.json",
  json.dumps({
      "terminal_path": r"C:\Program Files\MetaTrader 5\terminal64.exe",
      "symbol": "XAUUSDm",
      "magic": 20260919,
      "dry_run": False,
      "require_demo": True,
      "risk_fraction": 0.01,
      "timeframe": "M5",
      "detection_timeframes": ["H4", "H1"],
      "allow_single_tf_degraded": False,
      "heartbeat_path": r"logs/phase_d/heartbeat.txt",
      "heartbeat_interval_s": 1.0,
      "poll_interval_s": 0.5,
      "console_refresh_s": 5.0,
      "console_mode": "event",
      "alive_interval_s": 300.0,
      "log_dir": r"logs/phase_d",
  }, indent=2) + "\n")

# requirements.txt
w(DIST / "requirements.txt",
  "\n".join([
      "numpy>=1.24",
      "pandas>=1.5",
      "requests>=2.28",
      "# The MT5 Python API - REQUIRED by smc.data.mt5_connector / run_operator.",
      "MetaTrader5>=5.0.45",
      "# NOTE: the actual SMC runtime package is the 04_SRC/smc folder included in the zip.",
      "# This requirements list is the pinned external dependency set for that package.",
  ]) + "\n")

# run_live.bat AT ZIP ROOT with config/live_tester.json
w(DIST / "run_live.bat",
  "@echo off\n"
  "rem ============================================================\n"
  "rem SMC tester package launcher (v1.1-test.7)\n"
  "rem Run this bat from the extracted SMC_v1.1-test.7 folder.\n"
  "rem Do NOT run from inside the zip - extract first.\n"
  "rem Ctrl+C stops the session cleanly (heartbeat shutdown marker).\n"
  "rem ============================================================\n"
  "setlocal\n"
  "cd /d \"%~dp0\"\n"
  "\n"
  "set CONFIG=config\\live_tester.json\n"
  "set ENTRYPOINT=04_SRC\\smc\\live\\run_operator.py\n"
  "\n"
  "if not exist \"%CONFIG%\" (\n"
  "    echo [launcher] ERROR: config not found: %CD%\\%CONFIG%\n"
  "    echo [launcher] Extract the whole zip first; do not run from inside it.\n"
  "    pause\n"
  "    exit /b 1\n"
  ")\n"
  "if not exist \"%ENTRYPOINT%\" (\n"
  "    echo [launcher] ERROR: entrypoint not found: %CD%\\%ENTRYPOINT%\n"
  "    pause\n"
  "    exit /b 1\n"
  ")\n"
  "\n"
  "rem --- Python setup (creates a local venv if missing) ---\n"
  "set PYTHON_EXE=python\n"
  "where %PYTHON_EXE% >nul 2>nul\n"
  "if errorlevel 1 (\n"
  "    echo [launcher] ERROR: python not found on PATH.\n"
  "    echo [launcher] Install Python 3.11.x Windows 64-bit from python.org\n"
  "    echo [launcher] and check \"Add python.exe to PATH\" during install.\n"
  "    echo.\n"
  "    echo [launcher] The session cannot start without python on PATH.\n"
  "    pause\n"
  "    exit /b 1\n"
  ")\n"
  "\n"
  "if not exist \".venv\" (\n"
  "    echo [launcher] Creating local python venv .venv ...\n"
  "    %PYTHON_EXE% -m venv .venv\n"
  "    if errorlevel 1 (\n"
  "        echo [launcher] ERROR: venv creation failed. Install python3-venv or\n"
  "        echo [launcher] use a python install that includes the venv module.\n"
  "        pause\n"
  "        exit /b 1\n"
  "    )\n"
  ")\n"
  "\n"
  "echo [launcher] Installing runtime requirements into .venv ...\n"
  ".venv\\Scripts\\python.exe -m pip install --quiet -r requirements.txt\n"
  "if errorlevel 1 (\n"
  "    echo [launcher] ERROR: pip install failed - see messages above.\n"
  "    echo [launcher] If this is a proxy/firewall issue, check your connection.\n"
  "    echo [launcher] If it persists, run again with these commands manually:\n"
  "    echo [launcher]   .venv\\Scripts\\python.exe -m pip install --upgrade pip\n"
  "    echo [launcher]   .venv\\Scripts\\python.exe -m pip install -r requirements.txt\n"
  "    pause\n"
  "    exit /b 1\n"
  ")\n"
  "\n"
  "echo [launcher] Starting SMC tester session (pip ok, python ok)...\n"
  "echo [launcher] Config: %CD%\\%CONFIG%\n"
  "echo [launcher] Press Ctrl+C to stop the session.\n"
  "echo.\n"
  "echo.\n"
  "\n"
  ".venv\\Scripts\\python.exe \"%ENTRYPOINT%\" --config \"%CONFIG%\"\n"
  "set RC=%errorlevel%\n"
  "echo.\n"
  "echo [launcher] session exited with code %RC%\n"
  "if not \"%RC%\"==\"0\" goto fail\n"
  "pause\n"
  "exit /b 0\n"
  "\n"
  ":fail\n"
  "echo.\n"
  "echo [launcher] startup problem - see messages above.\n"
  "pause\n"
  "exit /b 1\n")

# TESTER_README.md (plain text twin of the PDF) - at BOTH dist and releases
README = (
f"SMC Tester Setup Guide - plain text version\n"
f"Release: {VERSION}\n"
f"Git SHA: {sha_short} ({sha_full})\n"
f"Python verified on build machine: {pyver}\n"
"\n"
"This is the text twin of TESTER_SETUP_GUIDE.pdf. Use whichever is easier\n"
"to read on your device.\n"
"\n"
"HARD RULE FIRST\n"
"- Edit ONLY config/live_tester.json if you need to fix the terminal path\n"
"  or symbol.\n"
"- Do NOT edit anything under 04_SRC/smc/.\n"
"- Do NOT ask AI to change strategy/threshold code.\n"
"- If something goes wrong, send VERSION.txt and the logs - do not patch.\n"
"\n"
"STEP 1 - Unzip to a folder\n"
"- Download SMC_v1.1-test.7_tester.zip\n"
"- Extract it to a normal folder, for example Desktop\\SMC_Bot\n"
"- IMPORTANT: do not run from inside the zip. Extract first.\n"
"\n"
"STEP 2 - Install Python\n"
"- Install Python 3.11.x (Windows 64-bit) from python.org\n"
'- During install, check "Add python.exe to PATH"\n'
f"- This package was built and verified on Python {pyver}\n"
"\n"
"STEP 3 - Start MetaTrader 5 (demo only)\n"
"- Open MetaTrader 5\n"
"- Use a DEMO account only for this test unless the Architect said otherwise\n"
"- Make sure the terminal is running before you start the bot\n"
"\n"
"STEP 4 - Install the safety watchdog EA (.ex5)\n"
"- The watchdog file lives in mql5/ in the package\n"
"- Copy the .ex5 into your MetaTrader terminal's MQL5/Experts folder\n"
"- In MetaEditor/MT5, attach the EA to the XAU chart\n"
"- Leave the EA input 'heartbeat path' at its DEFAULT (smc_heartbeat.txt):\n"
"  the bot writes the heartbeat to <terminal>\\MQL5\\Files\\smc_heartbeat.txt\n"
"  automatically (derived from terminal_path in the config).\n"
"- Typical inputs: symbol filter, magic number\n"
"- If you only have .mq5, compile it to .ex5 in MetaEditor first\n"
"\n"
"STEP 5 - Edit the config file\n"
"- Open config/live_tester.json in a text editor\n"
"- terminal_path: paste the FULL path to terminal64.exe on your PC\n"
"- symbol: usually XAUUSDm\n"
"- DEMO TRADING IS ON: dry_run=false means the bot CAN place real (demo)\n"
"  orders. Losses are possible on the demo account; no real money.\n"
"- require_demo stays true: real (live) accounts are still blocked.\n"
"- Still no AI code edits: edit ONLY this config file.\n"
"- Save the file\n"
"\n"
"STEP 6 - Start the bot\n"  "- In the extracted folder, double-click run_live.bat\n"
  "- The bat creates a local .venv if needed and installs requirements\n"
  "- Then it starts the SMC operator session\n"
  "- Console stays quiet; prints on bars, new POIs, orders, and errors\n"
"\n"
"STEP 7 - What success looks like\n"
"- A console window opens\n"
"- You should see a STRUCTURE board\n"
"- You should see heartbeat activity: the file lives in your terminal's\n"
"  MQL5\\Files\\smc_heartbeat.txt (next to terminal64.exe)\n"
"- You do NOT need to edit code to make this work\n"
"\n"
"STEP 8 - How to stop\n"
"- Press Ctrl+C in the console window\n"
"- The bot writes a heartbeat shutdown marker before stopping\n"
"\n"
"SUPPORT\n"
"- Include VERSION.txt with any problem report\n"
"- Include the logs (logs/phase_d/)\n"
"- Do not send edited source files - send the originals plus logs\n"
)
w(REL / "TESTER_README.md", README)
w(DIST / "TESTER_README.md", README)

# SUPPORT.txt
w(DIST / "SUPPORT.txt",
  f"SMC tester package support note\n"
  f"Release: {VERSION}\n"
  f"Git SHA: {sha_full}\n"
  "\n"
  "If the bot will not start:\n"
  "1. Confirm Python 3.11.x is installed and on PATH\n"
  "2. Confirm terminal64.exe path in config/live_tester.json is correct\n"
  "3. Confirm MetaTrader 5 is open and the watchdog EA is attached\n"
  "4. Send VERSION.txt and everything under logs/phase_d/\n"
  "\n"
  "Do not edit 04_SRC/smc/.\n")

# watchdog inclusion (copy .ex5 if present, else .mq5)
mql5_src = ROOT / "05_MQL5_SAFETY"
mql5_dst = DIST / "mql5"
mql5_dst.mkdir(parents=True, exist_ok=True)
if mql5_src.exists():
    names = []
    for p in mql5_src.iterdir():
        if p.name.endswith(".ex5"):
            shutil.copy2(p, mql5_dst / p.name)
            names.append(p.name)
        elif p.name.endswith(".mq5"):
            shutil.copy2(p, mql5_dst / p.name)
            names.append(p.name)
    print("MQL5_FILES_COPIED:", names)
else:
    print("MQL5_DIR_MISSING")
print("OPERATOR NOTE: the tester needs SMC_Safety_Watchdog.ex5 in mql5/ - "
      "compile the .mq5 locally and replace/add the .ex5 before shipping the zip.")

# 04_SRC/smc package copy
smc_dst = DIST / "04_SRC" / "smc"
if smc_dst.exists():
    shutil.rmtree(smc_dst)
shutil.copytree(SRC / "smc", smc_dst)
for p in smc_dst.rglob("__pycache__"):
    shutil.rmtree(p, ignore_errors=True)
print("SMC_PACKAGE_COPIED")

# config directory copy (keep live_demo for reference)
cfg_dst = DIST / "config"
cfg_dst.mkdir(parents=True, exist_ok=True)
for name in ["live_demo.json"]:
    src = ROOT / "config" / name
    if src.exists():
        shutil.copy2(src, cfg_dst / name)
print("CONFIG_COPIED")

# top-level file at zip root (run_live.bat is written above; nothing to copy from root here)

# ---- PDF: TESTER_SETUP_GUIDE.pdf ----
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

PDF = DIST / "TESTER_SETUP_GUIDE.pdf"
doc = SimpleDocTemplate(
    str(PDF),
    pagesize=A4,
    leftMargin=18*mm, rightMargin=18*mm,
    topMargin=16*mm, bottomMargin=16*mm,
    title=f"SMC Tester Setup Guide - {VERSION}",
    author="SMC build process",
)
styles = getSampleStyleSheet()
TITLE = ParagraphStyle("Title2", parent=styles["Title"], fontSize=22, leading=26,
                       textColor=HexColor("#1a1a1a"), spaceAfter=6*mm)
SUBTITLE = ParagraphStyle("Sub2", parent=styles["Normal"], fontSize=12, leading=15,
                          textColor=HexColor("#555555"), spaceAfter=8*mm)
STEP_HEAD = ParagraphStyle("StepHead", parent=styles["Heading2"], fontSize=13, leading=16,
                           textColor=HexColor("#0b3d91"), spaceBefore=3*mm, spaceAfter=2*mm)
BODY = ParagraphStyle("Body2", parent=styles["Normal"], fontSize=10.5, leading=14,
                      spaceAfter=2.5*mm)
HARD_RULE = ParagraphStyle("HardRule", parent=BODY, fontSize=10.5, leading=14,
                           textColor=HexColor("#8a1c1c"), backColor=HexColor("#fbeaea"),
                           borderPadding=(6, 8, 6, 8), spaceBefore=2*mm, spaceAfter=3*mm)
CAP = ParagraphStyle("Caption", parent=styles["Normal"], fontSize=9, leading=12,
                     textColor=HexColor("#666666"), alignment=TA_CENTER,
                     spaceBefore=1*mm, spaceAfter=3*mm)
NOTE = ParagraphStyle("Note", parent=BODY, fontSize=9.5, leading=12.5,
                      textColor=HexColor("#444444"))

def placeholder_image(width_px, height_px, caption):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path
    tmp = Path.cwd() / "AUTO_PDF_PLACEHOLDER.png"
    fig, ax = plt.subplots(figsize=(width_px/100, height_px/100), dpi=100)
    ax.text(0.5, 0.5, caption, ha="center", va="center",
            fontsize=10, wrap=True, color="#555555")
    ax.axis("off")
    fig.savefig(tmp, dpi=100, bbox_inches="tight", facecolor="#f7f8fa")
    plt.close(fig)
    return Image(str(tmp), width=width_px, height=height_px)

story = []
story.append(Paragraph("SMC Tester Setup Guide", TITLE))
story.append(Paragraph(
    f"Release {VERSION} - non-coder run surface\n"
    f"Git SHA: {sha_short} ({sha_full})\n"
    f"Python verified on build machine: {pyver}",
    SUBTITLE))
story.append(Spacer(1, 2*mm))
story.append(placeholder_image(380, 92,
    "SCREENSHOT TBD - example: a clean extracted folder ready to run.\n"
    "This is a placeholder, not a real screenshot."))
story.append(Spacer(1, 4*mm))
story.append(Paragraph(
    "<b>Who this is for:</b> testers who can follow numbered steps and install "
    "software, but do not edit Python strategy code.<br/>"
    "<b>What you will do:</b> unzip, install Python, start MetaTrader 5, attach "
    "the safety EA, edit one config line, and double-click one bat file.",
    BODY))
story.append(Paragraph(
    "<b>Hard rule before anything else:</b> edit <b>only</b> config/live_tester.json "
    "when you need to fix the terminal path or symbol. Do <b>not</b> edit anything "
    "under 04_SRC/smc/. Do <b>not</b> ask AI to change strategy or threshold code.",
    HARD_RULE))
story.append(PageBreak())

story.append(Paragraph("Step 1 - Unzip to a folder", STEP_HEAD))
story.append(Paragraph(
    "Download <b>SMC_v1.1-test.7_tester.zip</b> and extract it to a normal folder "
    "on your computer, for example <b>Desktop\\SMC_Bot</b>.", BODY))
story.append(Paragraph(
    "<b>Important:</b> do not run from inside the zip. Extract the whole zip first, "
    "then run the bat file from the extracted folder.", BODY))
story.append(placeholder_image(380, 120,
    "SCREENSHOT TBD - example: right-click the zip > Extract All.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 2 - Install Python", STEP_HEAD))
story.append(Paragraph(
    "Install <b>Python 3.11.x (Windows 64-bit)</b> from python.org. During the "
    f"install, check the box that says <b>Add python.exe to PATH</b>. This package "
    f"was built and verified on <b>{pyver}</b>.", BODY))
story.append(placeholder_image(380, 120,
    "SCREENSHOT TBD - example: Python installer with \"Add python.exe to PATH\"\n"
    "checked. This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 3 - Start MetaTrader 5 (demo only)", STEP_HEAD))
story.append(Paragraph(
    "Open <b>MetaTrader 5</b> and use a <b>DEMO account</b> for this test, unless "
    "the Architect said otherwise. Make sure the terminal is running before you "
    "start the bot.", BODY))
story.append(placeholder_image(380, 110,
    "SCREENSHOT TBD - example: MT5 terminal open on a chart.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 4 - Install the safety watchdog EA (.ex5)", STEP_HEAD))
story.append(Paragraph(
    "The watchdog file lives in the <b>mql5/</b> folder inside the package. "
    "Copy the <b>.ex5</b> into your MetaTrader terminal's "
    "<b>MQL5/Experts</b> folder.", BODY))
story.append(Paragraph(
    "In MetaEditor / MetaTrader 5, attach the EA to the <b>XAU chart</b>. Leave the "
    "EA input <b>heartbeat path</b> at its <b>default (smc_heartbeat.txt)</b>: the bot "
    "writes the heartbeat to <b>&lt;terminal&gt;\\MQL5\\Files\\smc_heartbeat.txt</b> "
    "automatically, derived from terminal_path in the config. Typical inputs are the "
    "symbol filter and magic number.", BODY))
story.append(Paragraph(
    "If you only have <b>.mq5</b>, compile it to <b>.ex5</b> in MetaEditor first.", BODY))
story.append(placeholder_image(380, 120,
    "SCREENSHOT TBD - example: EA attached to an XAU chart.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 5 - Edit the config file", STEP_HEAD))
story.append(Paragraph(
    "Open <b>config/live_tester.json</b> in a text editor.", BODY))
story.append(Paragraph(
    "<b>terminal_path:</b> paste the FULL path to <b>terminal64.exe</b> on your PC. "
    "This is the one value most testers need to change.", BODY))
story.append(Paragraph(
    "<b>symbol:</b> usually <b>XAUUSDm</b>. "
    "<b>DEMO TRADING IS ON:</b> <b>dry_run=false</b> means the bot CAN place real "
    "(demo) orders - losses are possible on the demo account, never real money. "
    "<b>require_demo</b> stays <b>true</b>: live accounts are still blocked.", BODY))
story.append(Paragraph(
    "Still <b>no AI code edits</b>: edit ONLY this config file.", BODY))
story.append(Paragraph("Save the file after editing.", BODY))
story.append(placeholder_image(380, 130,
    "SCREENSHOT TBD - example: config/live_tester.json open in a text editor.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 6 - Start the bot", STEP_HEAD))
story.append(Paragraph(
    "In the extracted folder, <b>double-click run_live.bat</b>. The bat file will "
    "create a local <b>.venv</b> if needed and install the runtime requirements, then "
    "it starts the SMC operator session. The first run may take a little longer "
    "because of the venv and pip install.", BODY))
story.append(Paragraph(
    "<b>The console stays quiet:</b> it prints on bars, new POIs, orders, and "
    "errors — plus a short one-line alive ping every 5 minutes so you know it "
    "is still running.", BODY))
story.append(Paragraph(
    "If python is not found, the bat will stop and tell you to install Python 3.11.x "
    "with \"Add python.exe to PATH\".", BODY))
story.append(placeholder_image(380, 130,
    "SCREENSHOT TBD - example: a console window starting up.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 7 - What success looks like", STEP_HEAD))
story.append(Paragraph(
    "A <b>console window opens</b>. You should see a <b>STRUCTURE board</b>. You should "
    "also see <b>heartbeat activity</b>: the heartbeat file lives in your terminal's "
    "<b>MQL5\\Files\\smc_heartbeat.txt</b> (next to terminal64.exe). You do "
    "<b>not</b> need to edit code to make this work.", BODY))
story.append(placeholder_image(380, 150,
    "SCREENSHOT TBD - example: console window with a STRUCTURE board.\n"
    "This is a placeholder, not a real screenshot."))

story.append(Paragraph("Step 8 - How to stop", STEP_HEAD))
story.append(Paragraph(
    "Press <b>Ctrl+C</b> in the console window. The bot writes a heartbeat "
    "<b>shutdown marker</b> before stopping.", BODY))

story.append(PageBreak())
story.append(Paragraph("Hard rules for testers", STEP_HEAD))
for r in [
    "Do <b>not</b> edit any file under <b>04_SRC/smc/</b>.",
    "Do <b>not</b> ask AI to change strategy or threshold code.",
    "You are <b>allowed</b> to change config paths, symbol, and dry_run only.",
    "If something goes wrong, send <b>VERSION.txt</b> and the <b>logs</b>. Do not patch files.",
    "Use a <b>demo account</b> unless the Architect said otherwise.",
    "This package is for <b>running</b>, not for strategy tuning.",
]:
    story.append(Paragraph(r, HARD_RULE))
story.append(Spacer(1, 4*mm))
story.append(Paragraph(
    "Support: include VERSION.txt with any problem report, and include "
    "everything under logs/phase_d/. Do not send edited source files.",
    NOTE))
story.append(Spacer(1, 6*mm))
story.append(Paragraph(
    f"Release {VERSION} - built from branch main - Git SHA {sha_short}",
    CAP))
doc.build(story)
print("PDF_WRITTEN:", PDF, PDF.stat().st_size, "bytes")

# ---- re-zip including the new PDF ----
zip_path = DIST / "SMC_v1.1-test.7_tester.zip"
if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(DIST.rglob("*")):
        if not p.is_file():
            continue
        if p.name == zip_path.name:
            continue
        if p.suffix.lower() == ".zip":   # never ship a stale pack inside the pack
            continue
        z.write(p, arcname=f"SMC_v1.1-test.7/{p.relative_to(DIST).as_posix()}",
               compress_type=zipfile.ZIP_DEFLATED)
print("ZIP_REBUILT:", zip_path, zip_path.stat().st_size, "bytes")
print("DIST_TREE:")
for p in sorted(DIST.rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(DIST))
