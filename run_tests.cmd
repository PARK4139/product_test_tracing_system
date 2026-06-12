@echo off
cd /d "%~dp0"
set LOG=%~dp0run_tests.log
echo [%date% %time%] Running regression tests... > "%LOG%"
echo [%date% %time%] Running regression tests...
uv run pytest tests/e2e_api/test_bulk_field_update.py -v >> "%LOG%" 2>&1
echo [%date% %time%] Done. >> "%LOG%"
echo [%date% %time%] Done.
echo See run_tests.log for full results.
pause
