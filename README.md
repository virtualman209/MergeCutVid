# MergenCut

Ghép, cắt và nén video nhanh trên Windows: mở từ Start Menu / Taskbar, hoặc chuột phải ngay trong Explorer (giống WinRAR).

- **Ghép video**: chọn `video_part_1 … part_N` → chuột phải → *MergenCut ▸ Ghép các video đã chọn*. Tự sắp đúng thứ tự số. Nếu các file cùng định dạng thì ghép không encode lại (vài giây là xong, giữ nguyên chất lượng).
- **Cắt / xoá đoạn**: xem trước từng frame, `I` / `O` đánh dấu, `Enter` thêm đoạn, `Ctrl+S` lưu. Có chế độ nhanh (không encode) và cắt chính xác từng frame.
- **Nén video**: H.265 / AV1 / H.264, có thể dùng GPU NVIDIA / Intel / AMD, ước tính dung lượng trước khi nén, nén nhiều file một lúc.
- **Kéo thả** file hoặc thư mục vào bất kỳ cửa sổ nào.
- **Tự cập nhật** từ GitHub (hỏi trước khi cập nhật).

## Cài đặt

Mở **PowerShell** và chạy:

```powershell
irm https://raw.githubusercontent.com/virtualman209/MergeCutVid/main/setup.ps1 | iex
```

Tool được cài vào `%LOCALAPPDATA%\MergenCut`, tạo lối tắt trên Start Menu và Desktop. Nếu máy chưa có Python 3 hoặc ffmpeg, script sẽ tự cài qua `winget`.

**Ghim lên Taskbar:** mở Start → tìm *MergenCut* → chuột phải → *Pin to taskbar*.

> Windows 11: chuột phải file → *Show more options* (hoặc Shift + chuột phải) mới thấy menu MergenCut.

Gỡ cài đặt: chạy `uninstall.bat` trong thư mục cài đặt.

## Phát hành bản mới

Sửa code → tăng số phiên bản ở dòng đầu `version.txt` (các dòng sau là ghi chú thay đổi) → push lên `main`.
