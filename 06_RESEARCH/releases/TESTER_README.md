SMC Tester Setup Guide - plain text version
Release: v1.1-test.8
Git SHA: 830a26d (830a26d486a6477800bdfd8268d15422707fe2f9)
Python verified on build machine: Python 3.11.9

This is the text twin of TESTER_SETUP_GUIDE.pdf. Use whichever is easier
to read on your device.

HARD RULE FIRST
- Edit ONLY config/live_tester.json if you need to fix the terminal path
  or symbol.
- Do NOT edit anything under 04_SRC/smc/.
- Do NOT ask AI to change strategy/threshold code.
- If something goes wrong, send VERSION.txt and the logs - do not patch.

STEP 1 - Unzip to a folder
- Download SMC_v1.1-test.8_tester.zip
- Extract it to a normal folder, for example Desktop\SMC_Bot
- IMPORTANT: do not run from inside the zip. Extract first.

STEP 2 - Install Python
- Install Python 3.11.x (Windows 64-bit) from python.org
- During install, check "Add python.exe to PATH"
- This package was built and verified on Python Python 3.11.9

STEP 3 - Start MetaTrader 5 (demo only)
- Open MetaTrader 5
- Use a DEMO account only for this test unless the Architect said otherwise
- Make sure the terminal is running before you start the bot

STEP 4 - Install the safety watchdog EA (.ex5)
- The watchdog file lives in mql5/ in the package
- Copy the .ex5 into your MetaTrader terminal's MQL5/Experts folder
- In MetaEditor/MT5, attach the EA to the XAU chart
- Compile it if you only have .mq5: open SMC_Safety_Watchdog.mq5 in
  MetaEditor (F4 in MetaTrader), press F7 (Compile), close MetaEditor,
  then right-click Navigator > Expert Advisors > Refresh.
- Leave the EA input InpHeartbeatFile at its DEFAULT (smc_heartbeat.txt).
- The bot writes the heartbeat into your terminal DATA folder:
  <data folder>\MQL5\Files\smc_heartbeat.txt
  (MetaTrader 5 > File > Open Data Folder). That is the EA sandbox; it
  is often NOT next to terminal64.exe. The bot derives it itself.
- Typical inputs: symbol filter, magic number
- If you only have .mq5, compile it to .ex5 in MetaEditor first

STEP 5 - Edit the config file
- Open config/live_tester.json in a text editor
- terminal_path: paste the FULL path to terminal64.exe on your PC
- symbol: usually XAUUSDm
- Leave heartbeat_path OUT of the config: the bot derives the
  EA-readable path from your terminal. Never point it at logs/.
- DEMO TRADING IS ON: dry_run=false means the bot CAN place real (demo)
  orders. Losses are possible on the demo account; no real money.
- require_demo stays true: real (live) accounts are still blocked.
- Still no AI code edits: edit ONLY this config file.
- Save the file

STEP 6 - Start the bot
- In the extracted folder, double-click run_live.bat
- The bat creates a local .venv if needed and installs requirements
- Then it starts the SMC operator session
- Console stays quiet; prints on bars, new POIs, orders, and errors

STEP 7 - What success looks like
- A console window opens
- You should see a STRUCTURE board
- You should see heartbeat activity: the file is
  <data folder>\MQL5\Files\smc_heartbeat.txt
  (MetaTrader 5 > File > Open Data Folder > MQL5 > Files). Its
  timestamp changes every second while the bot runs.
- You do NOT need to edit code to make this work

STEP 8 - How to stop
- Press Ctrl+C in the console window
- The bot writes a heartbeat shutdown marker before stopping

SUPPORT
- Include VERSION.txt with any problem report
- Include the logs (logs/phase_d/)
- Do not send edited source files - send the originals plus logs
