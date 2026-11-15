@echo off
rem Blueprint Lib Manager - opens the blueprint manager in your browser (needs Python 3.10+).
rem The server stops by itself shortly after the last browser tab is closed.
rem -B: don't write .pyc caches into the mod folder
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw -B "%~dp0Manager\tools\manager_server.py" --open
) else (
  start "Blueprint Lib Manager" python -B "%~dp0Manager\tools\manager_server.py" --open
)
