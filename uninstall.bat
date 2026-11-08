@echo off
cd /d "%~dp0"
python install.py --unreg > "%TEMP%\mergencut_unmenu.reg"
reg import "%TEMP%\mergencut_unmenu.reg"
del "%TEMP%\mergencut_unmenu.reg" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\shortcut.ps1" -Remove
echo Da go MergenCut khoi menu chuot phai, Start Menu va Desktop.
pause
