"""Tự cập nhật VideoTool từ GitHub.

So sánh version.txt trên GitHub với bản trên máy. Nếu có bản mới thì tải zip
của nhánh main về và chép đè vào thư mục tool (giữ nguyên config.json và bin/).
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

REPO = "virtualman209/MergeCutVid"
BRANCH = "main"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(APP_DIR, "update_state.json")
KEEP = {"config.json", "update_state.json", "bin", ".git"}
CHECK_EVERY = 6 * 3600          # tự kiểm tra tối đa 6 tiếng / lần
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.txt"
ZIP = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"


def _vtuple(v):
    return tuple(int(x) if x.isdigit() else 0 for x in v.strip().lstrip("v").split("."))


def _read_version_file(text):
    lines = text.strip().splitlines() or ["0"]
    return lines[0].strip(), "\n".join(lines[1:]).strip()


def local_version():
    try:
        with open(os.path.join(APP_DIR, "version.txt"), encoding="utf-8") as f:
            return _read_version_file(f.read())[0]
    except OSError:
        return "0"


def _get(url, timeout=6):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + f"t={int(time.time())}",
                                 headers={"User-Agent": "VideoTool-updater", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(**kw):
    s = _state()
    s.update(kw)
    try:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except OSError:
        pass


def check(force=False):
    """Trả về (version_mới, ghi_chú) nếu có bản mới hơn, ngược lại None."""
    if os.path.isdir(os.path.join(APP_DIR, ".git")):
        return None                       # đang là thư mục dev, không tự cập nhật
    st = _state()
    if not force and time.time() - st.get("last_check", 0) < CHECK_EVERY:
        return None
    remote, notes = _read_version_file(_get(RAW).decode("utf-8", "replace"))
    _save_state(last_check=time.time())
    if _vtuple(remote) > _vtuple(local_version()):
        if not force and st.get("skip") == remote:
            return None
        return remote, notes
    return None


def skip(version):
    _save_state(skip=version)


def apply_update():
    """Tải và chép đè bản mới. Trả về version mới."""
    data = _get(ZIP, timeout=60)
    tmp = tempfile.mkdtemp(prefix="videotool_upd_")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(tmp)
        roots = [os.path.join(tmp, d) for d in os.listdir(tmp)]
        src = roots[0] if len(roots) == 1 and os.path.isdir(roots[0]) else tmp
        if not os.path.isfile(os.path.join(src, "videotool.pyw")):
            raise RuntimeError("Gói cập nhật không hợp lệ.")
        for name in os.listdir(src):
            if name in KEEP:
                continue
            s, d = os.path.join(src, name), os.path.join(APP_DIR, name)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # Cài lại menu chuột phải (phòng khi bản mới thêm/đổi menu)
    if os.name == "nt":
        py = os.path.join(os.path.dirname(sys.executable), "python.exe")
        subprocess.run([py if os.path.isfile(py) else sys.executable,
                        os.path.join(APP_DIR, "install.py"), "--quiet"],
                       creationflags=0x08000000, capture_output=True)
    _save_state(skip=None)
    return local_version()


def restart():
    """Mở lại tool với đúng tham số cũ."""
    subprocess.Popen([sys.executable] + sys.argv, creationflags=0x08000000 if os.name == "nt" else 0)


if __name__ == "__main__":      # python updater.py  -> cập nhật từ dòng lệnh
    r = check(force=True)
    if r:
        print(f"Có bản mới {r[0]} (đang dùng {local_version()}). Đang cập nhật…")
        print("Đã cập nhật lên", apply_update())
    else:
        print("Đang dùng bản mới nhất:", local_version())
