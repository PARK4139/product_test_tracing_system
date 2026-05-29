@echo off
set DATA_DIR=%~dp0data

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

echo Done.
pause
