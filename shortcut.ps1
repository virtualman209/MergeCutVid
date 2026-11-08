# Tạo / xoá lối tắt MergenCut trên Start Menu và Desktop.
param([string]$PythonW, [string]$AppDir, [switch]$Remove)
$places = @([Environment]::GetFolderPath("Programs"), [Environment]::GetFolderPath("Desktop"))
foreach ($p in $places) {
    $lnk = Join-Path $p "MergenCut.lnk"
    if ($Remove) { Remove-Item $lnk -ErrorAction SilentlyContinue; continue }
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $s.TargetPath = $PythonW
    $s.Arguments = '"' + (Join-Path $AppDir "mergencut.pyw") + '"'
    $s.WorkingDirectory = $AppDir
    $s.IconLocation = (Join-Path $AppDir "mergencut.ico") + ",0"
    $s.Description = "MergenCut - ghép, cắt, nén video"
    $s.Save()
}
