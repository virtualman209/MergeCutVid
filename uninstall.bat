@echo off
cd /d "%~dp0"
python install.py --unreg > "%TEMP%\videotool_unmenu.reg"
reg import "%TEMP%\videotool_unmenu.reg"
del "%TEMP%\videotool_unmenu.reg" >nul 2>nul
echo Da go menu chuot phai VideoTool.
pause
