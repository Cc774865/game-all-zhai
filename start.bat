@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   十域九王 · 回合制 RPG
echo ============================================
where python >nul 2>nul
if %errorlevel%==0 (
    python run.py
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 run.py
    ) else (
        echo 未找到 Python，请先安装 Python 3.10 或更高版本。
        pause
        exit /b 1
    )
)
pause
