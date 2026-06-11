@echo off
REM ============================================================
REM  fix_git_push_as_temp_file.cmd  (ASCII only - no Korean)
REM  remove stale .git\index.lock, make 3 commits, then push
REM  run from repo root
REM ============================================================
setlocal
cd /d "%~dp0"

echo [0/4] removing stale locks...
if exist ".git\index.lock" del /f /q ".git\index.lock"
if exist ".git\HEAD.lock" del /f /q ".git\HEAD.lock"
if exist ".git\config.lock" del /f /q ".git\config.lock"
if exist ".git\packed-refs.lock" del /f /q ".git\packed-refs.lock"
for /r ".git" %%f in (*.lock) do del /f /q "%%f"

echo.
echo [1/4] commit: reorganize handover docs
git add -A -- ai_handover/ HANDOVER.md HANDOVER_20260604_archived.md docs/codex_prompt*.md docs/cursor_prompt*.md handover_2026_*.md
git commit -m "Reorganize handover docs into ai_handover/ (archive done prompts)"

echo.
echo [2/4] commit: gitignore agent temp dirs
git add .gitignore
git commit -m "Ignore permission-locked agent temp dirs (stepc_*, task12b/13)"

echo.
echo [3/4] commit: task15 dry-run output
git add docs/task15_3_dryrun.json docs/task15_4_dryrun.json
git commit -m "Update task15-3/15-4 dry-run output (15-4 READY)"

echo.
echo [4/4] push origin main
git push origin main
if errorlevel 1 (
  echo.
  echo [ERROR] push failed. check messages above.
  goto :end
)

echo.
echo === done. current state ===
git log --oneline -4
git status -sb

:end
endlocal
pause
