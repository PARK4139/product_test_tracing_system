@echo off
cd /d "%~dp0"
set LOG=%~dp0temp.log

echo [START] Playwright setup > "%LOG%"
echo [START] Playwright setup

echo.
echo [1/2] uv sync --dev ...
echo [1/2] uv sync --dev ... >> "%LOG%"
powershell -Command "& { $ErrorActionPreference='SilentlyContinue'; & uv sync --dev 2>&1 | Tee-Object -FilePath '%LOG%' -Append }; exit $LASTEXITCODE"
if %errorlevel% neq 0 (
    echo [ERROR] uv sync failed >> "%LOG%"
    echo [ERROR] uv sync failed
    pause & exit /b 1
)

echo.
echo [2/2] playwright install chromium ...
echo [2/2] playwright install chromium ... >> "%LOG%"
powershell -Command "& { $ErrorActionPreference='SilentlyContinue'; & uv run playwright install chromium --with-deps 2>&1 | Tee-Object -FilePath '%LOG%' -Append }; exit $LASTEXITCODE"
if %errorlevel% neq 0 (
    echo [ERROR] playwright install failed >> "%LOG%"
    echo [ERROR] playwright install failed
    pause & exit /b 1
)

echo [DONE] Setup complete. Run run_tests.cmd next. >> "%LOG%"
echo [DONE] Setup complete. Run run_tests.cmd next.
echo See temp.log for full results.
pause
