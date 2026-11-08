@echo off
rem Ghi menu chuot phai vao registry + tao loi tat Start Menu / Desktop.
rem Dung reg.exe (khong dung Python) vi Python ban Microsoft Store ghi registry vao ban sao rieng.
cd /d "%~dp0"
python install.py --config
python install.py --reg > "%TEMP%\mergencut_menu.reg"
reg import "%TEMP%\mergencut_menu.reg"
if errorlevel 1 (
    echo [!] Ghi registry that bai.
    exit /b 1
)
del "%TEMP%\mergencut_menu.reg" >nul 2>nul
for /f "usebackq delims=" %%P in (`python install.py --pythonw`) do set "MC_PYW=%%P"
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\shortcut.ps1" -PythonW "%MC_PYW%" -AppDir "%CD%"
echo Da cai menu chuot phai + loi tat MergenCut (Start Menu, Desktop).
