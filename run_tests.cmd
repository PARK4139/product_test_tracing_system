@echo off
cd /d "%~dp0"
set LOG=%~dp0run_tests.log
echo [%date% %time%] Running regression tests... > "%LOG%"
echo [%date% %time%] Running regression tests...
powershell -Command "& uv run pytest tests/e2e_api/test_bulk_field_update.py -v 2>&1 | Tee-Object -FilePath '%LOG%' -Append"
echo [%date% %time%] Done. >> "%LOG%"
echo [%date% %time%] Done.
echo See run_tests.log for full results.
pause
