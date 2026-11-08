@echo off
rem Ghi menu chuot phai vao registry. Dung reg.exe (khong dung Python) de
rem tranh viec Python ban Microsoft Store ghi registry vao ban sao rieng.
cd /d "%~dp0"
python install.py --config
python install.py --reg > "%TEMP%\videotool_menu.reg"
reg import "%TEMP%\videotool_menu.reg"
if errorlevel 1 (
    echo [!] Ghi registry that bai.
    exit /b 1
)
del "%TEMP%\videotool_menu.reg" >nul 2>nul
echo Da cai menu chuot phai VideoTool.
