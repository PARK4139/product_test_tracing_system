@REM chcp 65001 >nul
@REM setlocal enabledelayedexpansion
@REM set "SCRIPT_NAME=%~nx0"
@REM git add .
@REM git commit -m "make save point by !SCRIPT_NAME!"
@REM git push


call "%USERPROFILE%\Downloads\pk_system\.venv\Scripts\activate.bat"
set BASENAME=%~n0
python %BASENAME%.py