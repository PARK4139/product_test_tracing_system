@echo off
set DATA_DIR=%~dp0data
set SRC=%~dp0..\ai_coworking\product_test_tracking_system_FIXED.db
set DST=%DATA_DIR%\product_test_tracking_system.db

echo [1/5] Cleaning WAL files in data/...
if exist "%DATA_DIR%\*.db-wal" (
    del /f /q "%DATA_DIR%\*.db-wal"
    echo [OK] .db-wal deleted
) else (
    echo [--] .db-wal not found
)
if exist "%DATA_DIR%\*.db-shm" (
    del /f /q "%DATA_DIR%\*.db-shm"
    echo [OK] .db-shm deleted
) else (
    echo [--] .db-shm not found
)

echo [2/5] Cleaning journal from source DB...
if exist "%SRC%-journal" (
    del /f /q "%SRC%-journal"
    echo [OK] source journal deleted
) else (
    echo [--] source journal not found
)
if exist "%SRC%-wal" (
    del /f /q "%SRC%-wal"
    echo [OK] source wal deleted
)
if exist "%SRC%-shm" (
    del /f /q "%SRC%-shm"
    echo [OK] source shm deleted
)

echo [3/5] Checking source DB...
if not exist "%SRC%" (
    echo [ERROR] Source not found: %SRC%
    pause
    exit /b 1
)

echo [4/5] Replacing DB...
copy /y "%SRC%" "%DST%"
if %errorlevel% neq 0 (
    echo [ERROR] Copy failed.
    pause
    exit /b 1
)
echo [OK] DB replaced.

echo [5/5] Starting server...
cd /d "%~dp0"
uv run python run.py
