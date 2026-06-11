@echo off
REM ============================================================
REM  fix_git_push_as_temp_file.cmd  (ASCII only - no Korean)
REM  remove stale locks, checkpoint DB (integrity gate),
REM  stage everything, single commit, then push.
REM  run from repo root.
REM ============================================================
setlocal
cd /d "%~dp0"

echo [0/5] removing stale locks...
if exist ".git\index.lock" del /f /q ".git\index.lock"
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\config.lock" del /f /q ".git\config.lock"
if exist ".git\packed-refs.lock" del /f /q ".git\packed-refs.lock"
for /r ".git" %%f in (*.lock) do del /f /q "%%f"

echo.
echo [1/5] checkpoint DB (merge WAL into .db, verify integrity)...
set DB_OK=1
uv run python -c "import sqlite3; c=sqlite3.connect(r'data\product_test_tracking_system.db'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); ic=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close(); print('integrity_check:', ic); exit(0 if ic=='ok' else 1)"
if errorlevel 1 (
  echo [WARN] checkpoint/integrity failed - DB will NOT be committed ^(other changes still commit^).
  set DB_OK=0
)

echo.
echo [2/5] stage all changes...
git add -A

echo.
echo [3/5] integrity gate: unstage DB if check failed...
if "%DB_OK%"=="0" (
  echo [SKIP] unstaging data\product_test_tracking_system.db
  git restore --staged data/product_test_tracking_system.db
)

echo.
echo [4/5] commit...
git commit -m "TASK 15-6 finish release->round code/test sync (73 tests green); update handover docs"
if errorlevel 1 echo [INFO] nothing to commit ^(or commit skipped^).

echo.
echo [5/5] push origin main
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] push failed. check messages above.
  goto :end
)

echo.
echo === done. current state ===
git log --oneline -6
git status -sb

:end
endlocal
pause
