# Cài VideoTool chỉ bằng 1 lệnh (PowerShell):
#   irm https://raw.githubusercontent.com/virtualman209/MergeCutVid/main/setup.ps1 | iex
$ErrorActionPreference = "Stop"
$repo = "virtualman209/MergeCutVid"
$dest = Join-Path $env:LOCALAPPDATA "VideoTool"
$zip  = Join-Path $env:TEMP "VideoTool.zip"
$tmp  = Join-Path $env:TEMP "VideoTool_setup"

Write-Host "Đang tải VideoTool từ GitHub..." -ForegroundColor Cyan
Invoke-WebRequest "https://codeload.github.com/$repo/zip/refs/heads/main" -OutFile $zip -UseBasicParsing
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip $tmp -Force
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item (Join-Path $src.FullName "*") $dest -Recurse -Force
Remove-Item $zip, $tmp -Recurse -Force

Write-Host "Đã chép vào $dest" -ForegroundColor Green
Start-Process -FilePath (Join-Path $dest "install.bat") -WorkingDirectory $dest -Wait
