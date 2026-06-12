@echo off
set LOG=%~dp0fix_temp.log
echo [%date% %time%] START > "%LOG%"

echo [1/3] Removing git lock files...
echo [1/3] Removing git lock files... >> "%LOG%"
del /f /q "%~dp0.git\HEAD.lock" 2>nul && (echo   HEAD.lock deleted & echo   HEAD.lock deleted >> "%LOG%") || (echo   HEAD.lock not found & echo   HEAD.lock not found >> "%LOG%")
del /f /q "%~dp0.git\index.lock" 2>nul && (echo   index.lock deleted & echo   index.lock deleted >> "%LOG%") || (echo   index.lock not found & echo   index.lock not found >> "%LOG%")

echo [2/3] Staging changes...
echo [2/3] Staging changes... >> "%LOG%"
cd /d "%~dp0"
git add app/services/product_test_run_service/ >> "%LOG%" 2>&1

echo [3/3] Committing...
echo [3/3] Committing... >> "%LOG%"
git commit -m "fix: add missing _common imports to split submodules" >> "%LOG%" 2>&1

echo [%date% %time%] DONE >> "%LOG%"
echo Done. See fix_temp.log for details.
