@echo off
set SRC=%~dp0..\ai_coworking\product_test_tracking_system_FIXED.db
set DST=%~dp0data\product_test_tracking_system.db

if not exist "%SRC%" (
    echo [ERROR] Source not found: %SRC%
    pause
    exit /b 1
)

copy /y "%SRC%" "%DST%"
if %errorlevel% == 0 (
    echo [OK] DB replaced successfully.
) else (
    echo [ERROR] Copy failed.
)

pause
