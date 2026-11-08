# Tải bản mới nhất từ GitHub và chép đè vào thư mục cài đặt (giữ cấu hình và bin\).
param([string]$AppDir = $PSScriptRoot)
$ErrorActionPreference = "Stop"
$repo = "virtualman209/MergeCutVid"
$keep = @("config.json", "update_state.json", "compress_prefs.json", "settings.json", "bin", ".git")
$zip = Join-Path $env:TEMP "MergenCut_update.zip"
$tmp = Join-Path $env:TEMP "MergenCut_update"
try {
    Write-Host "Đang tải bản mới MergenCut..." -ForegroundColor Cyan
    Invoke-WebRequest "https://codeload.github.com/$repo/zip/refs/heads/main" -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp -Force
    $src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    if (-not (Test-Path (Join-Path $src "mergencut.pyw"))) { throw "Gói cập nhật không hợp lệ." }
    Get-ChildItem $src -Force | Where-Object { $keep -notcontains $_.Name } | ForEach-Object {
        Copy-Item $_.FullName $AppDir -Recurse -Force
    }
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Đã cập nhật." -ForegroundColor Green
    exit 0
} catch {
    Write-Host "Cập nhật thất bại: $_" -ForegroundColor Red
    Set-Content (Join-Path $AppDir "update_error.txt") "$_" -Encoding UTF8
    Start-Sleep 5
    exit 1
}
