@echo off
rem Cap nhat MergenCut. Chay qua explorer.exe de nam ngoai vung cach ly cua Python ban Store.
title Cap nhat MergenCut
cd /d "%~dp0"
del update_error.txt >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\update.ps1" -AppDir "%CD%"
if errorlevel 1 exit /b 1
call register.bat
