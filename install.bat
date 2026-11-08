@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Cai dat MergenCut

python -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [!] Chua co Python. Dang cai Python 3 qua winget...
    winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements
    echo.
    echo Cai Python xong. Hay DONG cua so nay va chay lai install.bat.
    pause
    exit /b
)

if exist "bin\ffmpeg.exe" goto :install
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [!] Chua co ffmpeg. Dang cai ffmpeg qua winget...
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
)

:install
call register.bat
echo.
echo Xong! Mo MergenCut tu Start Menu / Desktop, hoac chuot phai vao file video ^> MergenCut.
echo Muon ghim len Taskbar: mo Start, tim "MergenCut", chuot phai ^> Pin to taskbar.
pause
