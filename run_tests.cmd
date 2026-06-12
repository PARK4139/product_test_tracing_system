@echo off
cd /d "%~dp0"
set LOG=%~dp0run_tests.log

echo [START] Running regression tests... > "%LOG%"
echo [START] Running regression tests...

echo.
echo [1/2] API regression tests...
echo [1/2] API regression tests... >> "%LOG%"
powershell -Command "& { $ErrorActionPreference='SilentlyContinue'; & uv run pytest tests/e2e_api/test_bulk_field_update.py -v 2>&1 | Tee-Object -FilePath '%LOG%' -Append }; exit $LASTEXITCODE"

echo.
echo [2/2] Playwright E2E tests...
echo [2/2] Playwright E2E tests... >> "%LOG%"
powershell -Command "& { $ErrorActionPreference='SilentlyContinue'; & uv run pytest tests/playwright/ -v --browser chromium 2>&1 | Tee-Object -FilePath '%LOG%' -Append }; exit $LASTEXITCODE"

echo [DONE] All tests complete. >> "%LOG%"
echo [DONE] All tests complete.
echo See run_tests.log for full results.
pause
