@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERROR] Failed to move to script directory.
    pause
    exit /b 1
)

set "SCRIPT_PATH=%~dp0ensure_repo_pushed_by_ai_agent_commit_message.py"

if not exist "%SCRIPT_PATH%" (
    echo [ERROR] Python script not found:
    echo %SCRIPT_PATH%
    pause
    exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
    py "%SCRIPT_PATH%"
    set "EXIT_CODE=%ERRORLEVEL%"
    if not "!EXIT_CODE!"=="0" (
        echo.
        echo [ERROR] Python script failed with exit code !EXIT_CODE!.
        pause
    )
    exit /b !EXIT_CODE!
)

where python >nul 2>nul
if not errorlevel 1 (
    python "%SCRIPT_PATH%"
    set "EXIT_CODE=%ERRORLEVEL%"
    if not "!EXIT_CODE!"=="0" (
        echo.
        echo [ERROR] Python script failed with exit code !EXIT_CODE!.
        pause
    )
    exit /b !EXIT_CODE!
)

echo [ERROR] Neither "py" nor "python" was found in PATH.
pause
exit /b 1
