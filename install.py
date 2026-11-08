"""Tạo cấu hình + file .reg cho menu chuột phải VideoTool.

Python bản Microsoft Store bị Windows cách ly: ghi registry qua winreg sẽ vào
một bản sao riêng mà Explorer không thấy. Vì vậy script này chỉ IN nội dung
.reg ra stdout, còn register.bat dùng `reg import` (chạy ngoài Python) để ghi thật.

    python install.py --config   # lưu đường dẫn ffmpeg vào config.json, in thông tin
    python install.py --reg      # in file .reg (UTF-16) để cài menu
    python install.py --unreg    # in file .reg để gỡ menu
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

ROOT = r"HKEY_CURRENT_USER\Software\Classes"
KEY = "VideoTool"
APP = core.APP_DIR
SCRIPT = os.path.join(APP, "videotool.pyw")
ICON = os.path.join(APP, "videotool.ico")


def pythonw():
    p = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return p if os.path.isfile(p) else sys.executable


def esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def cmd(mode, arg="%1"):
    return f'"{pythonw()}" "{SCRIPT}" {mode}' + (f' "{arg}"' if arg else "")


def bases():
    return [f"{ROOT}\\SystemFileAssociations\\{ext}" for ext in core.VIDEO_EXT] + \
           [f"{ROOT}\\Directory", f"{ROOT}\\Directory\\Background"]


def menu_items(base):
    upd = ("update", "Kiểm tra cập nhật", cmd("update", None))
    if base.endswith("\\Background") or base.endswith("\\Directory"):
        arg = "%V" if base.endswith("\\Background") else "%1"
        return [("mergefolder", "Ghép tất cả video trong thư mục này", cmd("merge-folder", arg)),
                ("compressfolder", "Nén tất cả video trong thư mục này…", cmd("compress-folder", arg)), upd]
    return [("merge", "Ghép các video đã chọn thành 1 file", cmd("merge")),
            ("edit", "Cắt / xoá đoạn video…", cmd("edit")),
            ("compress", "Nén video (giảm dung lượng)…", cmd("compress")), upd]


def reg_text(install=True):
    out = ["Windows Registry Editor Version 5.00", ""]
    icon = f'"Icon"="{esc(ICON)}"' if os.path.isfile(ICON) else None
    for base in bases():
        root = f"{base}\\shell\\{KEY}"
        out += [f"[-{root}]", ""]                       # xoá menu cũ
        if not install:
            continue
        out += [f"[{root}]", '"MUIVerb"="VideoTool"', '"SubCommands"=""', '"MultiSelectModel"="Player"']
        out += [icon, ""] if icon else [""]
        for n, (verb, label, command) in enumerate(menu_items(base), 1):
            k = f"{root}\\shell\\{n:02d}{verb}"
            out += [f"[{k}]", f'"MUIVerb"="{esc(label)}"', '"MultiSelectModel"="Player"']
            out += [icon] if icon else []
            out += ["", f"[{k}\\command]", f'@="{esc(command)}"', ""]
    return "\r\n".join(out) + "\r\n"


def write_config():
    cfg = {}
    for b in ("ffmpeg", "ffprobe", "ffplay"):
        p = core.find_bin(b)
        if p:
            cfg[b] = os.path.abspath(p)
    with open(core.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("  Python : " + pythonw())
    for b in ("ffmpeg", "ffprobe", "ffplay"):
        print(f"  {b:7}: " + (cfg.get(b) or "KHÔNG TÌM THẤY"))
    if "ffmpeg" not in cfg or "ffprobe" not in cfg:
        print("\n!! Thiếu ffmpeg. Cài bằng:  winget install Gyan.FFmpeg   rồi chạy lại install.bat")
        print("   hoặc chép ffmpeg.exe, ffprobe.exe, ffplay.exe vào thư mục: " + os.path.join(APP, "bin"))


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--config"
    if arg == "--config":
        write_config()
    elif arg in ("--reg", "--unreg"):
        sys.stdout.buffer.write(reg_text(arg == "--reg").encode("utf-16"))   # có BOM
        sys.stdout.flush()
    else:
        sys.exit(__doc__)
