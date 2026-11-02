@echo off
cd /d "%~dp0.."
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe Web\run.py
) else (
    python Web\run.py
)
pause
