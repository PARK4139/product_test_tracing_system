@echo off
cd /d "%~dp0"
uv run python run_tests.py %*
echo "%*" | findstr /C:"--auto" >nul 2>&1 || pause
