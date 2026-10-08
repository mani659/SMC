' PHASE C GUARD - hidden launcher
' Runs phase_c_guard.bat with a fully hidden window (style 0) and does not
' wait for it. Invoked by scheduled task SMC_phase_c_guard (every 5 min) and
' by the Startup folder entry, so the auto-restart guard never shows a
' console window. The bat itself starts the windowless pythonw daemon and
' exits immediately.
CreateObject("WScript.Shell").Run _
    """D:\Gold Scripts\MQL5\SMC\06_RESEARCH\scripts\phase_c_guard.bat""", 0, False
