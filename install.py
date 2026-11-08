"""Cài / gỡ menu chuột phải VideoTool (chỉ cho user hiện tại, không cần quyền Admin).

    python install.py            # cài
    python install.py uninstall  # gỡ
"""
import json
import os
import sys
import winreg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

HKCU = winreg.HKEY_CURRENT_USER
CLASSES = r"Software\Classes"
KEY = "VideoTool"
APP = core.APP_DIR
SCRIPT = os.path.join(APP, "videotool.pyw")
ICON = os.path.join(APP, "videotool.ico")


def pythonw():
    p = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return p if os.path.isfile(p) else sys.executable


def setval(path, name, value):
    with winreg.CreateKeyEx(HKCU, path, 0, winreg.KEY_WRITE) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def delete_tree(path):
    try:
        with winreg.OpenKey(HKCU, path, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                except OSError:
                    break
                delete_tree(path + "\\" + sub)
        winreg.DeleteKey(HKCU, path)
    except FileNotFoundError:
        pass


def cmd(mode, arg="%1"):
    return f'"{pythonw()}" "{SCRIPT}" {mode} "{arg}"'


def add_cascade(base, items):
    """Menu con kiểu WinRAR: VideoTool ▸ ..."""
    root = f"{base}\\shell\\{KEY}"
    setval(root, "MUIVerb", "VideoTool")
    setval(root, "SubCommands", "")
    setval(root, "MultiSelectModel", "Player")   # vẫn hiện khi chọn >15 file
    if os.path.isfile(ICON):
        setval(root, "Icon", ICON)
    for order, (verb, label, command) in enumerate(items, 1):
        k = f"{root}\\shell\\{order:02d}{verb}"
        setval(k, "MUIVerb", label)
        setval(k, "MultiSelectModel", "Player")
        if os.path.isfile(ICON):
            setval(k, "Icon", ICON)
        setval(k + "\\command", "", command)


def install():
    # Lưu đường dẫn ffmpeg tuyệt đối (Explorer có thể chưa nhận PATH mới sau khi cài ffmpeg)
    cfg = {}
    for b in ("ffmpeg", "ffprobe", "ffplay"):
        p = core.find_bin(b)
        if p:
            cfg[b] = os.path.abspath(p)
    with open(core.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    uninstall(quiet=True)  # xoá menu cũ trước (phòng khi bản mới đổi menu)
    upd = ("update", "Kiểm tra cập nhật", f'"{pythonw()}" "{SCRIPT}" update')
    for ext in core.VIDEO_EXT:
        add_cascade(f"{CLASSES}\\SystemFileAssociations\\{ext}", [
            ("merge", "Ghép các video đã chọn thành 1 file", cmd("merge")),
            ("edit", "Cắt / xoá đoạn video…", cmd("edit")),
            upd,
        ])
    add_cascade(f"{CLASSES}\\Directory", [
        ("mergefolder", "Ghép tất cả video trong thư mục này", cmd("merge-folder")),
        upd,
    ])
    add_cascade(f"{CLASSES}\\Directory\\Background", [
        ("mergefolder", "Ghép tất cả video trong thư mục này", cmd("merge-folder", "%V")),
        upd,
    ])
    if QUIET:
        return

    print("Đã cài menu chuột phải VideoTool.")
    print("  Python : " + pythonw())
    for b in ("ffmpeg", "ffprobe", "ffplay"):
        print(f"  {b:7}: " + (cfg.get(b) or "KHÔNG TÌM THẤY"))
    if "ffmpeg" not in cfg or "ffprobe" not in cfg:
        print("\n!! Thiếu ffmpeg. Cài bằng:  winget install Gyan.FFmpeg   rồi chạy lại install.bat")
        print("   hoặc chép ffmpeg.exe, ffprobe.exe, ffplay.exe vào thư mục: " + os.path.join(APP, "bin"))


def uninstall(quiet=False):
    for ext in core.VIDEO_EXT:
        delete_tree(f"{CLASSES}\\SystemFileAssociations\\{ext}\\shell\\{KEY}")
    delete_tree(f"{CLASSES}\\Directory\\shell\\{KEY}")
    delete_tree(f"{CLASSES}\\Directory\\Background\\shell\\{KEY}")
    if not quiet:
        print("Đã gỡ menu chuột phải VideoTool.")


QUIET = "--quiet" in sys.argv


if __name__ == "__main__":
    if os.name != "nt":
        sys.exit("Chỉ chạy trên Windows.")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    uninstall() if len(sys.argv) > 1 and sys.argv[1] == "uninstall" else install()
