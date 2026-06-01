@echo off
set ROOT=%~dp0
set DATA_DIR=%ROOT%data
set RECOVERED=C:\Users\USER\AppData\Roaming\Claude\local-agent-mode-sessions\30d84356-7c5b-461d-a7ac-d35cab6415a4\db8ae934-8942-4876-a40f-c0ab06a3aeeb\local_3b7a0fc4-4092-4196-b4ff-91587726519e\outputs\product_test_tracking_system_RECOVERED.db
set DST_DATA=%DATA_DIR%\product_test_tracking_system.db
set DST_FIXED=%ROOT%..\ai_coworking\product_test_tracking_system_FIXED.db

echo ============================================
echo  DB Recovery Script
echo ============================================

echo [1/5] Check recovery file...
if not exist "%RECOVERED%" (
    echo [ERROR] File not found: %RECOVERED%
    pause
    exit /b 1
)
echo [OK] Recovery file found.

echo [2/5] Remove stale WAL/journal files...
if exist "%DATA_DIR%\*.db-wal"  del /f /q "%DATA_DIR%\*.db-wal"
if exist "%DATA_DIR%\*.db-shm"  del /f /q "%DATA_DIR%\*.db-shm"
if exist "%DST_FIXED%-journal"  del /f /q "%DST_FIXED%-journal"
if exist "%DST_FIXED%-wal"      del /f /q "%DST_FIXED%-wal"
if exist "%DST_FIXED%-shm"      del /f /q "%DST_FIXED%-shm"
if exist "%DST_DATA%-journal"   del /f /q "%DST_DATA%-journal"
echo [OK] Cleanup done.

echo [3/5] Replace data DB...
copy /y "%RECOVERED%" "%DST_DATA%"
if %errorlevel% neq 0 (
    echo [ERROR] Copy to data failed.
    pause
    exit /b 1
)
echo [OK] data DB replaced.

echo [4/5] Replace FIXED.db...
copy /y "%RECOVERED%" "%DST_FIXED%"
if %errorlevel% neq 0 (
    echo [ERROR] Copy to FIXED.db failed.
    pause
    exit /b 1
)
echo [OK] FIXED.db replaced.

echo [5/5] Starting server...
cd /d "%ROOT%"
uv run python run.py
