VIDEOTOOL — Ghép & cắt video nhanh từ menu chuột phải
=====================================================

CÀI ĐẶT (1 lần)
---------------
1. Giải nén thư mục VideoTool tới một chỗ cố định, ví dụ  C:\Tools\VideoTool
   (đừng để ở Downloads rồi xoá, vì menu chuột phải trỏ vào thư mục này).
2. Chạy  install.bat
   - Nếu máy chưa có Python 3 hoặc ffmpeg, script sẽ cài giúp qua winget.
     Sau khi cài Python, chạy lại install.bat lần nữa.
   - Không muốn dùng winget? Chép ffmpeg.exe, ffprobe.exe, ffplay.exe vào thư mục  bin\
     (tải từ https://www.gyan.dev/ffmpeg/builds/ , bản "essentials").
3. Xong. Chuột phải vào file video  →  VideoTool.
   Windows 11: chuột phải  →  "Show more options" (hoặc Shift + chuột phải).

Gỡ cài đặt: chạy  uninstall.bat  rồi xoá thư mục.


GHÉP VIDEO
----------
• Kéo chuột (hoặc Ctrl/Shift + click) chọn video_part_1, part_2, … → chuột phải
  → VideoTool → "Ghép các video đã chọn thành 1 file".
• Hoặc chuột phải vào THƯ MỤC (hay vùng trống trong thư mục) → "Ghép tất cả video trong thư mục này".
• Tool tự sắp đúng thứ tự số (part_2 đứng trước part_10). Đổi thứ tự bằng ▲▼ hoặc Alt+↑/↓.
• Các file cùng định dạng thì ghép kiểu "copy stream": vài giây là xong, không giảm chất lượng.
  Nếu khác độ phân giải hoặc codec, tool tự encode lại (chậm hơn), video lệch khung thì thêm viền đen.
• Tên file kết quả gợi ý tự động: video_part_1..5  →  video_merged.mp4


CẮT / XOÁ ĐOẠN
--------------
Chuột phải 1 video → VideoTool → "Cắt / xoá đoạn video…"

  Click / kéo trên thanh timeline   tua tới vị trí
  ← / →                             lùi / tới 1 giây   (Shift: 5 giây)
  ,  /  .                           lùi / tới 1 frame
  I                                 đánh dấu ĐẦU đoạn
  O                                 đánh dấu CUỐI đoạn
  Enter                             thêm đoạn vào danh sách
  Space                             phát video từ vị trí hiện tại (ffplay)
  Ctrl+Z                            hoàn tác
  Ctrl+S                            lưu

• "Xoá đoạn đã chọn": cắt bỏ các đoạn (màu đỏ), giữ phần còn lại.
• "Giữ đoạn đã chọn": chỉ giữ các đoạn đã chọn và nối lại với nhau.
• Lưu mặc định ở chế độ NHANH (không encode). Điểm cắt bám theo keyframe nên có thể lệch
  khoảng 1–3 giây. Muốn cắt chính xác từng frame thì tick "Cắt chính xác" (encode lại H.264).
• File gốc không bao giờ bị ghi đè. Kết quả mặc định là  ten_edit.mp4.


GẶP LỖI?
--------
• Menu không hiện: chạy lại install.bat. Nếu bạn đã chuyển thư mục tool đi chỗ khác thì cũng phải chạy lại.
• Lỗi được ghi vào  %TEMP%\videotool.log
