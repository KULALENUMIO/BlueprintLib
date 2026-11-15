@echo off
rem Blueprint Lib - rebuild the blueprint index (read-only scan of your blueprint folders)
python -B "%~dp0sync_index.py" %*
pause
