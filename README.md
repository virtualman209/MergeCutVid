# MergeCutVid (VideoTool)

Ghép và cắt video nhanh ngay từ menu chuột phải của Windows Explorer (giống menu của WinRAR).

- **Ghép video**: chọn `video_part_1 … part_N` → chuột phải → *VideoTool ▸ Ghép các video đã chọn*.
  Tự sắp đúng thứ tự số. Nếu các file cùng định dạng thì ghép không encode lại (vài giây là xong, giữ nguyên chất lượng); khác định dạng thì tự encode lại.
- **Cắt / xoá đoạn**: xem trước từng frame, đánh dấu `I` / `O`, `Enter` để thêm đoạn, `Ctrl+S` để lưu. Có chế độ nhanh (không encode) và chế độ cắt chính xác từng frame.
- **Tự cập nhật**: mỗi lần mở, tool kiểm tra GitHub (tối đa 6 tiếng/lần) và hỏi trước khi cập nhật. Có thể kiểm tra thủ công ở *VideoTool ▸ Kiểm tra cập nhật*.

## Cài đặt

Mở **PowerShell** và chạy:

```powershell
irm https://raw.githubusercontent.com/virtualman209/MergeCutVid/main/setup.ps1 | iex
```

Tool được cài vào `%LOCALAPPDATA%\VideoTool`. Nếu máy chưa có Python 3 hoặc ffmpeg, script sẽ tự cài qua `winget`.

Cách khác: tải ZIP (*Code ▸ Download ZIP*), giải nén ra một thư mục cố định rồi chạy `install.bat`.

Gỡ cài đặt: chạy `uninstall.bat` trong thư mục cài đặt.

> Windows 11: chuột phải → *Show more options* (hoặc Shift + chuột phải) mới thấy menu VideoTool.

Xem hướng dẫn chi tiết và phím tắt trong [README.txt](README.txt).

## Phát hành bản mới

Sửa code → tăng số phiên bản ở dòng đầu `version.txt` (các dòng sau là ghi chú thay đổi) → push lên `main`.
Máy đã cài sẽ thấy thông báo cập nhật ở lần mở tool tiếp theo.
