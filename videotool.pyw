"""VideoTool — Ghép & cắt video nhanh từ menu chuột phải Windows Explorer.

Cách gọi:
    pythonw videotool.pyw merge <file1> [file2 ...]   # ghép (gom nhiều lần gọi từ Explorer)
    pythonw videotool.pyw merge-folder <thư mục>      # ghép tất cả video trong thư mục
    pythonw videotool.pyw edit <file>                 # cắt / xoá đoạn
"""
import base64
import json
import os
import socket
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

import tkinter as tk  # noqa: E402
from tkinter import ttk, filedialog, messagebox  # noqa: E402

PORT = 47863
LOG = os.path.join(os.environ.get("TEMP", "/tmp"), "videotool.log")


# ============================================================ gom file từ nhiều lần gọi
def gather_paths(mode, paths):
    """Explorer gọi tool 1 lần cho MỖI file được chọn. Tiến trình đầu tiên mở cổng
    localhost, gom đường dẫn từ các tiến trình sau rồi mở 1 cửa sổ duy nhất."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        srv.bind(("127.0.0.1", PORT))
    except OSError:
        srv.close()
        for _ in range(40):  # gửi cho tiến trình chính rồi thoát
            try:
                with socket.create_connection(("127.0.0.1", PORT), timeout=1) as c:
                    c.sendall(json.dumps(paths).encode("utf-8"))
                return None
            except OSError:
                time.sleep(0.05)
        return paths
    srv.listen(64)
    srv.settimeout(0.1)
    got = list(paths)
    deadline = time.time() + 0.9
    while time.time() < deadline:
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            continue
        with conn:
            buf = b""
            conn.settimeout(1)
            try:
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                got += json.loads(buf.decode("utf-8"))
            except Exception:
                pass
        deadline = time.time() + 0.5
    srv.close()
    seen, out = set(), []
    for p in got:
        k = os.path.normcase(os.path.abspath(p))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


# ============================================================ tiện ích UI
def setup_style(root):
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    style.configure("Big.TButton", padding=(14, 6))
    style.configure("Hint.TLabel", foreground="#666")
    root.option_add("*Font", ("Segoe UI", 10))


def center(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth() - w) // 2
    y = (win.winfo_screenheight() - h) // 3
    win.geometry(f"{w}x{h}+{x}+{y}")


def check_ffmpeg():
    if core.find_bin("ffmpeg") and core.find_bin("ffprobe"):
        return True
    messagebox.showerror("VideoTool", "Không tìm thấy ffmpeg/ffprobe.\n\n"
                         "Chạy lại install.bat, hoặc chép ffmpeg.exe + ffprobe.exe (+ ffplay.exe) "
                         "vào thư mục 'bin' cạnh videotool.pyw.")
    return False


def ask_output(parent, initial, title="Lưu video"):
    ext = os.path.splitext(initial)[1] or ".mp4"
    return filedialog.asksaveasfilename(
        parent=parent, title=title, initialdir=os.path.dirname(initial),
        initialfile=os.path.basename(initial), defaultextension=ext,
        filetypes=[("Video", "*" + ext), ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("Tất cả", "*.*")])


def reveal(path):
    if os.name == "nt":
        import subprocess
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])


class ProgressMixin:
    """Thanh tiến trình + chạy job ở thread nền."""

    def build_progress(self, parent):
        bar = ttk.Frame(parent)
        self.pvar = tk.DoubleVar()
        self.pbar = ttk.Progressbar(bar, variable=self.pvar, maximum=100)
        self.pbar.pack(side="left", fill="x", expand=True)
        self.plabel = ttk.Label(bar, text="", width=26, anchor="e")
        self.plabel.pack(side="left", padx=(8, 0))
        self._cancel = False
        self._busy = False
        return bar

    def run_job(self, label, fn, out):
        self._busy, self._cancel, self._label = True, False, None
        self.set_busy(True)
        t0 = time.time()

        def prog(p):
            el = time.time() - t0
            eta = f" · còn ~{int(el / p - el)}s" if p > 0.02 else ""
            self.root.after(0, lambda: (self.pvar.set(p * 100),
                                        self.plabel.config(text=f"{getattr(self, '_label', None) or label} {p * 100:4.0f}%{eta}")))

        def work():
            err, res = None, None
            try:
                res = fn(prog, lambda: self._cancel)
            except core.Cancelled:
                err = "cancel"
            except Exception as e:  # noqa: BLE001
                err = str(e)
            self.root.after(0, lambda: self.job_done(err, out, time.time() - t0, res))
        threading.Thread(target=work, daemon=True).start()

    def job_done(self, err, out, secs, res=None):
        self._busy = False
        self.set_busy(False)
        if err == "cancel":
            self.plabel.config(text="Đã huỷ")
            self.pvar.set(0)
            if os.path.exists(out):
                try:
                    os.remove(out)
                except OSError:
                    pass
            return
        if err:
            self.plabel.config(text="Lỗi!")
            messagebox.showerror("VideoTool", err, parent=self.root)
            return
        self.plabel.config(text=f"Xong trong {secs:.1f}s")
        msg = res if isinstance(res, str) else f"Đã lưu:\n{out}"
        target = out or getattr(self, "on_job_reveal", lambda: None)()
        if not target:
            messagebox.showinfo("VideoTool", msg, parent=self.root)
        elif messagebox.askyesno("VideoTool", msg + "\n\nMở thư mục chứa file?", parent=self.root):
            reveal(target)

    def on_close(self):
        if self._busy and not messagebox.askyesno("VideoTool", "Đang xử lý. Huỷ và thoát?", parent=self.root):
            return
        self._cancel = True
        self.root.destroy()


# ============================================================ cửa sổ GHÉP
class MergeWindow(ProgressMixin):
    def __init__(self, root, paths):
        self.root = root
        root.title("VideoTool — Ghép video")
        center(root, 760, 520)
        self.files = sorted([p for p in paths if os.path.isfile(p)], key=core.natural_key)
        self.infos = {}

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="Thứ tự ghép (đã tự sắp theo tên: part_1, part_2, … part_10):",
                  ).pack(anchor="w")

        mid = ttk.Frame(main)
        mid.pack(fill="both", expand=True, pady=6)
        cols = ("name", "dur", "info")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t, w in (("name", "Tên file", 330), ("dur", "Thời lượng", 90), ("info", "Định dạng", 230)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        side = ttk.Frame(mid, padding=(8, 0, 0, 0))
        side.pack(side="left", fill="y")
        for txt, cmd in (("▲ Lên", lambda: self.move(-1)), ("▼ Xuống", lambda: self.move(1)),
                         ("+ Thêm…", self.add), ("✕ Bỏ", self.remove),
                         ("A→Z Sắp lại", self.resort), ("▶ Xem", self.preview)):
            ttk.Button(side, text=txt, command=cmd, width=13).pack(pady=2)

        self.status = ttk.Label(main, text="", style="Hint.TLabel", wraplength=720)
        self.status.pack(anchor="w", pady=(2, 6))

        opt = ttk.Frame(main)
        opt.pack(fill="x")
        self.mode = tk.StringVar(value="auto")
        ttk.Radiobutton(opt, text="Tự động", variable=self.mode, value="auto").pack(side="left")
        ttk.Radiobutton(opt, text="Nhanh (không encode, giữ nguyên chất lượng)",
                        variable=self.mode, value="fast").pack(side="left", padx=10)
        ttk.Radiobutton(opt, text="Encode lại (video khác định dạng/độ phân giải)",
                        variable=self.mode, value="re").pack(side="left")

        outf = ttk.Frame(main)
        outf.pack(fill="x", pady=8)
        ttk.Label(outf, text="Lưu thành:").pack(side="left")
        self.out = tk.StringVar(value=core.suggest_merged_name(self.files) if self.files else "")
        ttk.Entry(outf, textvariable=self.out).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(outf, text="…", width=3, command=self.browse).pack(side="left")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x")
        self.build_progress(bottom).pack(side="left", fill="x", expand=True)
        self.btn_cancel = ttk.Button(bottom, text="Huỷ", command=lambda: setattr(self, "_cancel", True),
                                     state="disabled")
        self.btn_cancel.pack(side="right", padx=(8, 0))
        self.btn_go = ttk.Button(bottom, text="Ghép ngay", style="Big.TButton", command=self.go)
        self.btn_go.pack(side="right", padx=(8, 0))

        root.bind("<Return>", lambda e: self.go())
        root.bind("<Delete>", lambda e: self.remove())
        root.bind("<Alt-Up>", lambda e: self.move(-1))
        root.bind("<Alt-Down>", lambda e: self.move(1))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        threading.Thread(target=self.probe_all, daemon=True).start()

    # ---- list
    def refresh(self):
        sel = [self.files[int(i)] for i in self.tree.selection() if int(i) < len(self.files)]
        self.tree.delete(*self.tree.get_children())
        for n, f in enumerate(self.files):
            info = self.infos.get(f)
            if info:
                v, a = info["video"], info["audio"]
                desc = (f"{v['codec']} {v['w']}x{v['h']} {v['fps']:g}fps" if v else "không hình") + \
                       (f" · {a['codec']}" if a else " · không tiếng")
                dur = core.fmt_time(info["duration"], ms=False)
            else:
                desc, dur = "đang đọc…", ""
            self.tree.insert("", "end", iid=str(n), values=(os.path.basename(f), dur, desc))
        for n, f in enumerate(self.files):
            if f in sel:
                self.tree.selection_add(str(n))
        self.update_status()

    def update_status(self):
        if len(self.files) < 2:
            self.status.config(text="Cần ít nhất 2 video để ghép.", foreground="#b00")
            return
        infos = [self.infos.get(f) for f in self.files]
        if None in infos:
            self.status.config(text=f"{len(self.files)} file · đang kiểm tra định dạng…", foreground="#666")
            return
        ok, why = core.compatible(infos)
        total = core.fmt_time(sum(i["duration"] for i in infos), ms=False)
        self.compat = ok
        self.status.config(text=f"{len(self.files)} file · tổng {total} · " +
                           (why if ok else "⚠ " + why + " → sẽ encode lại."),
                           foreground="#070" if ok else "#a60")

    def probe_all(self):
        for f in list(self.files):
            if f not in self.infos:
                try:
                    self.infos[f] = core.probe(f)
                except Exception:
                    self.infos[f] = {"path": f, "duration": 0, "video": None, "audio": None}
        self.root.after(0, self.refresh)

    def selected(self):
        return sorted(int(i) for i in self.tree.selection())

    def move(self, d):
        idx = self.selected()
        if not idx:
            return
        if (d < 0 and idx[0] == 0) or (d > 0 and idx[-1] == len(self.files) - 1):
            return
        for i in (idx if d < 0 else reversed(idx)):
            self.files[i], self.files[i + d] = self.files[i + d], self.files[i]
        self.refresh()
        self.tree.selection_set([str(i + d) for i in idx])

    def add(self):
        fs = filedialog.askopenfilenames(parent=self.root, title="Thêm video",
                                         filetypes=[("Video", " ".join("*" + e for e in core.VIDEO_EXT)),
                                                    ("Tất cả", "*.*")])
        for f in fs:
            if f not in self.files:
                self.files.append(f)
        if fs and not self.out.get():
            self.out.set(core.suggest_merged_name(self.files))
        self.refresh()
        threading.Thread(target=self.probe_all, daemon=True).start()

    def remove(self):
        for i in reversed(self.selected()):
            del self.files[i]
        self.refresh()

    def resort(self):
        self.files.sort(key=core.natural_key)
        self.refresh()

    def preview(self):
        idx = self.selected()
        if idx:
            core.play(self.files[idx[0]])

    def browse(self):
        p = ask_output(self.root, self.out.get() or core.suggest_merged_name(self.files))
        if p:
            self.out.set(p)

    def set_busy(self, busy):
        self.btn_go.config(state="disabled" if busy else "normal")
        self.btn_cancel.config(state="normal" if busy else "disabled")

    # ---- go
    def go(self):
        if self._busy or len(self.files) < 2:
            return
        infos = [self.infos.get(f) for f in self.files]
        if None in infos:
            messagebox.showinfo("VideoTool", "Đang đọc thông tin video, thử lại sau giây lát.", parent=self.root)
            return
        out = self.out.get().strip()
        if not out:
            return self.browse()
        if os.path.normcase(os.path.abspath(out)) in {os.path.normcase(os.path.abspath(f)) for f in self.files}:
            messagebox.showerror("VideoTool", "File đầu ra trùng với file nguồn.", parent=self.root)
            return
        if os.path.exists(out) and not messagebox.askyesno("VideoTool", "File đã tồn tại. Ghi đè?", parent=self.root):
            return
        mode = self.mode.get()
        fast = core.compatible(infos)[0] if mode == "auto" else mode == "fast"
        total = sum(i["duration"] for i in infos)
        files = list(self.files)
        if fast:
            self.run_job("Đang ghép", lambda p, c: core.merge_fast(files, out, total, p, c), out)
        else:
            self.run_job("Đang encode", lambda p, c: core.merge_reencode(infos, out, p, c), out)


# ============================================================ cửa sổ CẮT / SỬA
class EditWindow(ProgressMixin):
    PREVIEW_W = 720

    def __init__(self, root, path):
        self.root, self.path = root, path
        root.title(f"VideoTool — Cắt video — {os.path.basename(path)}")
        center(root, 900, 760)
        self.info = core.probe(path)
        self.dur = self.info["duration"] or 0.0
        fps = (self.info["video"] or {}).get("fps") or 30
        self.frame_step = 1.0 / fps
        self.pos = 0.0
        self.mark_in = None
        self.mark_out = None
        self.ranges = []           # [(a, b)]
        self.undo = []
        self._img = None
        self._req = 0
        self._loading = False
        self._pending = None

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(main, bg="#111", height=405, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.show_frame())

        # timeline
        self.tl = tk.Canvas(main, height=46, bg="#f3f3f3", highlightthickness=1, highlightbackground="#ccc",
                            cursor="hand2")
        self.tl.pack(fill="x", pady=(8, 2))
        self.tl.bind("<Button-1>", self.tl_click)
        self.tl.bind("<B1-Motion>", self.tl_click)
        self.tl.bind("<Configure>", lambda e: self.draw_tl())

        row = ttk.Frame(main)
        row.pack(fill="x", pady=4)
        self.tlabel = ttk.Label(row, text="", font=("Consolas", 12, "bold"))
        self.tlabel.pack(side="left")
        ttk.Label(row, text="  Đến:").pack(side="left")
        self.goto = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.goto, width=11)
        e.pack(side="left")
        e.bind("<Return>", lambda ev: (self.seek(core.parse_time(self.goto.get() or "0")), self.root.focus()))
        for txt, d in (("−5s", -5), ("−1s", -1), ("−1f", -self.frame_step),
                       ("+1f", self.frame_step), ("+1s", 1), ("+5s", 5)):
            ttk.Button(row, text=txt, width=5, command=lambda d=d: self.seek(self.pos + d)).pack(side="left", padx=1)
        ttk.Button(row, text="▶ Phát từ đây (Space)", command=lambda: core.play(self.path, self.pos)
                   ).pack(side="right")

        row2 = ttk.Frame(main)
        row2.pack(fill="x", pady=4)
        ttk.Button(row2, text="[ Đầu đoạn (I)", command=self.set_in).pack(side="left")
        ttk.Button(row2, text="Cuối đoạn (O) ]", command=self.set_out).pack(side="left", padx=4)
        ttk.Button(row2, text="✂ Thêm đoạn (Enter)", command=self.add_range).pack(side="left", padx=4)
        ttk.Button(row2, text="Hoàn tác (Ctrl+Z)", command=self.do_undo).pack(side="left", padx=4)
        self.mode = tk.StringVar(value="remove")
        ttk.Radiobutton(row2, text="Giữ đoạn đã chọn", variable=self.mode, value="keep",
                        command=self.mode_changed).pack(side="right")
        ttk.Radiobutton(row2, text="Xoá đoạn đã chọn", variable=self.mode, value="remove",
                        command=self.mode_changed).pack(side="right", padx=8)

        lst = ttk.Frame(main)
        lst.pack(fill="x", pady=4)
        self.lb = tk.Listbox(lst, height=4, activestyle="none", font=("Consolas", 10))
        self.lb.pack(side="left", fill="x", expand=True)
        self.lb.bind("<Double-Button-1>", self.lb_jump)
        self.lb.bind("<Delete>", lambda e: self.del_range())
        bl = ttk.Frame(lst, padding=(6, 0, 0, 0))
        bl.pack(side="left", fill="y")
        ttk.Button(bl, text="✕ Bỏ đoạn", command=self.del_range).pack(fill="x")
        ttk.Button(bl, text="Xoá hết", command=self.clear_ranges).pack(fill="x", pady=2)
        self.summary = ttk.Label(main, text="", style="Hint.TLabel")
        self.summary.pack(anchor="w")

        exp = ttk.Frame(main)
        exp.pack(fill="x", pady=(6, 0))
        self.accurate = tk.BooleanVar(value=False)
        ttk.Checkbutton(exp, text="Cắt chính xác từng frame (encode lại, chậm hơn)",
                        variable=self.accurate).pack(side="left")
        ttk.Label(exp, text="  Chế độ nhanh: cắt bám theo keyframe (lệch ≤ vài giây), không giảm chất lượng.",
                  style="Hint.TLabel").pack(side="left")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(8, 0))
        self.build_progress(bottom).pack(side="left", fill="x", expand=True)
        self.btn_cancel = ttk.Button(bottom, text="Huỷ", state="disabled",
                                     command=lambda: setattr(self, "_cancel", True))
        self.btn_cancel.pack(side="right", padx=(8, 0))
        self.btn_go = ttk.Button(bottom, text="💾 Lưu (Ctrl+S)", style="Big.TButton", command=self.save)
        self.btn_go.pack(side="right", padx=(8, 0))

        kb = root.bind
        kb("<Left>", lambda e: self.seek(self.pos - 1))
        kb("<Right>", lambda e: self.seek(self.pos + 1))
        kb("<Shift-Left>", lambda e: self.seek(self.pos - 5))
        kb("<Shift-Right>", lambda e: self.seek(self.pos + 5))
        kb("<comma>", lambda e: self.seek(self.pos - self.frame_step))
        kb("<period>", lambda e: self.seek(self.pos + self.frame_step))
        kb("<Home>", lambda e: self.seek(0))
        kb("<End>", lambda e: self.seek(self.dur))
        for k in ("i", "I"):
            kb(f"<KeyPress-{k}>", lambda e: self.set_in() if not self._in_entry(e) else None)
        for k in ("o", "O"):
            kb(f"<KeyPress-{k}>", lambda e: self.set_out() if not self._in_entry(e) else None)
        kb("<Return>", lambda e: self.add_range() if not self._in_entry(e) else None)
        kb("<space>", lambda e: core.play(self.path, self.pos) if not self._in_entry(e) else None)
        kb("<Control-z>", lambda e: self.do_undo())
        kb("<Control-s>", lambda e: self.save())
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(50, self.update_all)

    @staticmethod
    def _in_entry(e):
        return isinstance(e.widget, (tk.Entry, ttk.Entry))

    # ---- preview
    def seek(self, t):
        self.pos = min(max(0.0, t), max(0.0, self.dur - 0.001))
        self.update_all()

    def update_all(self):
        self.tlabel.config(text=f"{core.fmt_time(self.pos)} / {core.fmt_time(self.dur)}")
        self.draw_tl()
        self.show_frame()

    def show_frame(self):
        if self.info["video"] is None:
            self.canvas.delete("all")
            self.canvas.create_text(self.canvas.winfo_width() // 2, 200, text="(file không có hình)", fill="#aaa")
            return
        if self._loading:          # gộp yêu cầu khi kéo nhanh
            self._pending = self.pos
            return
        self._loading = True
        t = self.pos
        w = max(320, min(self.canvas.winfo_width(), 1280))

        def work():
            data = None
            try:
                data = core.grab_frame_png(self.path, t, w)
            except Exception:
                pass
            self.root.after(0, lambda: self._frame_ready(data))
        threading.Thread(target=work, daemon=True).start()

    def _frame_ready(self, data):
        self._loading = False
        if data:
            try:
                img = tk.PhotoImage(data=base64.b64encode(data).decode("ascii"))
                cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
                f = max(1, -(-img.height() // max(1, ch)))
                if f > 1:
                    img = img.subsample(f)
                self._img = img
                self.canvas.delete("all")
                self.canvas.create_image(cw // 2, ch // 2, image=img)
            except tk.TclError:
                pass
        if self._pending is not None:
            self._pending = None
            self.show_frame()

    # ---- timeline
    def x_of(self, t):
        w = self.tl.winfo_width()
        return 4 + (w - 8) * (t / self.dur if self.dur else 0)

    def tl_click(self, e):
        w = self.tl.winfo_width()
        self.seek((e.x - 4) / max(1, w - 8) * self.dur)

    def draw_tl(self):
        c = self.tl
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        c.create_rectangle(4, 12, w - 4, h - 10, fill="#cfe8cf" if self.mode.get() == "remove" else "#e6c6c6",
                           outline="")
        for a, b in core.normalize(self.ranges, self.dur):
            col = "#e57373" if self.mode.get() == "remove" else "#81c784"
            c.create_rectangle(self.x_of(a), 12, self.x_of(b), h - 10, fill=col, outline="")
        if self.mark_in is not None:
            x = self.x_of(self.mark_in)
            end = self.mark_out if self.mark_out is not None else self.pos
            if end > self.mark_in:
                c.create_rectangle(x, 12, self.x_of(end), h - 10, fill="#ffd54f", outline="", stipple="gray50")
            c.create_line(x, 4, x, h - 2, fill="#1565c0", width=2)
            c.create_text(x + 2, 6, text="[", anchor="w", fill="#1565c0")
        if self.mark_out is not None:
            x = self.x_of(self.mark_out)
            c.create_line(x, 4, x, h - 2, fill="#1565c0", width=2)
        x = self.x_of(self.pos)
        c.create_line(x, 0, x, h, fill="#000", width=2)
        c.create_polygon(x - 5, 0, x + 5, 0, x, 7, fill="#000")
        # vạch chia
        if self.dur:
            step = next(s for s in (1, 5, 10, 30, 60, 300, 600, 1800, 3600, 1e9) if self.dur / s <= 12)
            t = 0.0
            while t <= self.dur:
                xx = self.x_of(t)
                c.create_line(xx, h - 10, xx, h - 6, fill="#888")
                c.create_text(xx + 2, h - 1, text=core.fmt_time(t, ms=False).lstrip("0:") or "0",
                              anchor="sw", fill="#777", font=("Segoe UI", 7))
                t += step

    # ---- ranges
    def set_in(self):
        self.mark_in = self.pos
        if self.mark_out is not None and self.mark_out <= self.mark_in:
            self.mark_out = None
        self.draw_tl()

    def set_out(self):
        self.mark_out = self.pos
        if self.mark_in is None or self.mark_in >= self.mark_out:
            self.mark_in = 0.0 if self.mark_in is None else self.mark_in
            if self.mark_in >= self.mark_out:
                self.mark_in = 0.0
        self.draw_tl()

    def add_range(self):
        a = self.mark_in
        b = self.mark_out if self.mark_out is not None else self.pos
        if a is None or b - a < 0.01:
            messagebox.showinfo("VideoTool", "Đặt Đầu đoạn (I) và Cuối đoạn (O) trước.", parent=self.root)
            return
        self.undo.append(list(self.ranges))
        self.ranges.append((a, b))
        self.ranges = core.normalize(self.ranges, self.dur)
        self.mark_in = self.mark_out = None
        self.refresh_list()

    def del_range(self):
        sel = self.lb.curselection()
        if not sel:
            return
        self.undo.append(list(self.ranges))
        del self.ranges[sel[0]]
        self.refresh_list()

    def clear_ranges(self):
        if self.ranges:
            self.undo.append(list(self.ranges))
            self.ranges = []
            self.refresh_list()

    def do_undo(self):
        if self.undo:
            self.ranges = self.undo.pop()
            self.refresh_list()

    def lb_jump(self, e):
        sel = self.lb.curselection()
        if sel:
            self.seek(self.ranges[sel[0]][0])

    def mode_changed(self):
        self.refresh_list()

    def refresh_list(self):
        self.lb.delete(0, "end")
        verb = "XOÁ" if self.mode.get() == "remove" else "GIỮ"
        for n, (a, b) in enumerate(self.ranges, 1):
            self.lb.insert("end", f" {n:2d}. {verb}  {core.fmt_time(a)} → {core.fmt_time(b)}   ({b - a:.2f}s)")
        keep = core.keep_ranges(self.ranges, self.dur, self.mode.get())
        new_len = sum(b - a for a, b in keep)
        self.summary.config(text=f"Thời lượng sau khi cắt: {core.fmt_time(new_len)}  "
                                 f"(gốc {core.fmt_time(self.dur)}) · {len(keep)} đoạn được giữ")
        self.draw_tl()

    # ---- save
    def set_busy(self, busy):
        self.btn_go.config(state="disabled" if busy else "normal")
        self.btn_cancel.config(state="normal" if busy else "disabled")

    def save(self):
        if self._busy:
            return
        if not self.ranges:
            messagebox.showinfo("VideoTool", "Chưa chọn đoạn nào.\nDùng I / O để đánh dấu, Enter để thêm đoạn.",
                                parent=self.root)
            return
        keep = core.keep_ranges(self.ranges, self.dur, self.mode.get())
        if not keep:
            messagebox.showerror("VideoTool", "Không còn gì để lưu (đã xoá toàn bộ video).", parent=self.root)
            return
        base, ext = os.path.splitext(self.path)
        out = ask_output(self.root, core.unique_path(base + "_edit" + ext))
        if not out:
            return
        if os.path.normcase(os.path.abspath(out)) == os.path.normcase(os.path.abspath(self.path)):
            messagebox.showerror("VideoTool", "Không thể ghi đè lên file gốc. Chọn tên khác.", parent=self.root)
            return
        if self.accurate.get():
            self.run_job("Đang encode", lambda p, c: core.export_accurate(self.path, self.info, keep, out, p, c), out)
        else:
            self.run_job("Đang cắt", lambda p, c: core.export_fast(self.path, keep, out, p, c), out)


# ============================================================ cửa sổ NÉN
class CompressWindow(ProgressMixin):
    def __init__(self, root, paths):
        self.root = root
        root.title("VideoTool — Nén video")
        center(root, 820, 620)
        self.files = sorted([p for p in paths if os.path.isfile(p) and core.is_video(p)], key=core.natural_key)
        self.infos = {}
        self.encoders = None
        cfg = self.load_prefs()

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        mid = ttk.Frame(main)
        mid.pack(fill="both", expand=True)
        cols = ("name", "dur", "size", "info", "est")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=7)
        for c, t, w in (("name", "Tên file", 250), ("dur", "Thời lượng", 75), ("size", "Dung lượng", 80),
                        ("info", "Định dạng", 190), ("est", "Sau khi nén", 150)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        side = ttk.Frame(mid, padding=(8, 0, 0, 0))
        side.pack(side="left", fill="y")
        ttk.Button(side, text="+ Thêm…", width=11, command=self.add).pack(pady=2)
        ttk.Button(side, text="✕ Bỏ", width=11, command=self.remove).pack(pady=2)
        ttk.Button(side, text="▶ Xem", width=11, command=self.preview).pack(pady=2)

        opt = ttk.LabelFrame(main, text="Tuỳ chọn nén", padding=10)
        opt.pack(fill="x", pady=10)
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Codec:").grid(row=0, column=0, sticky="nw", pady=2)
        self.codec = tk.StringVar(value=cfg.get("codec", "hevc"))
        cf = ttk.Frame(opt)
        cf.grid(row=0, column=1, sticky="w")
        for k, (label, _, _) in core.CODECS.items():
            ttk.Radiobutton(cf, text=label, variable=self.codec, value=k, command=self.opts_changed).pack(anchor="w")

        ttk.Label(opt, text="Chất lượng:").grid(row=1, column=0, sticky="w", pady=(8, 2))
        self.quality = tk.StringVar(value=cfg.get("quality", "balanced"))
        qf = ttk.Frame(opt)
        qf.grid(row=1, column=1, sticky="w", pady=(8, 2))
        for k in core.QUALITY_LEVELS:
            ttk.Radiobutton(qf, text=core.QUALITY_LABELS[k], variable=self.quality, value=k,
                            command=self.opts_changed).pack(side="left", padx=(0, 12))

        ttk.Label(opt, text="Tốc độ:").grid(row=2, column=0, sticky="w", pady=2)
        self.speed = tk.StringVar(value=cfg.get("speed", "medium"))
        sf = ttk.Frame(opt)
        sf.grid(row=2, column=1, sticky="w")
        for k in core.SPEED_LEVELS:
            ttk.Radiobutton(sf, text=core.SPEED_LABELS[k], variable=self.speed, value=k,
                            command=self.opts_changed).pack(side="left", padx=(0, 12))

        ttk.Label(opt, text="Phần cứng:").grid(row=3, column=0, sticky="w", pady=2)
        self.gpu = tk.StringVar(value="cpu")
        gf = ttk.Frame(opt)
        gf.grid(row=3, column=1, sticky="w")
        self.gpu_box = ttk.Combobox(gf, textvariable=self.gpu, state="readonly", width=46)
        self.gpu_box.pack(side="left")
        self.gpu_box.bind("<<ComboboxSelected>>", lambda e: self.opts_changed())
        self.gpu_hint = ttk.Label(gf, text="  đang dò GPU…", style="Hint.TLabel")
        self.gpu_hint.pack(side="left")

        ttk.Label(opt, text="Độ phân giải:").grid(row=4, column=0, sticky="w", pady=2)
        self.maxh = tk.StringVar(value=cfg.get("maxh", "Giữ nguyên"))
        rf = ttk.Frame(opt)
        rf.grid(row=4, column=1, sticky="w")
        ttk.Combobox(rf, textvariable=self.maxh, state="readonly", width=14,
                     values=("Giữ nguyên", "Tối đa 1440p", "Tối đa 1080p", "Tối đa 720p", "Tối đa 480p")
                     ).pack(side="left")
        ttk.Label(rf, text="   Âm thanh:").pack(side="left")
        self.audio = tk.StringVar(value=cfg.get("audio", "AAC 128 kbps"))
        ttk.Combobox(rf, textvariable=self.audio, state="readonly", width=16,
                     values=("AAC 96 kbps", "AAC 128 kbps", "AAC 192 kbps", "Giữ nguyên")).pack(side="left")
        for w in rf.winfo_children():
            if isinstance(w, ttk.Combobox):
                w.bind("<<ComboboxSelected>>", lambda e: self.opts_changed())

        self.skip_bigger = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt, text="Nếu file nén ra không nhỏ hơn bản gốc thì bỏ, không lưu",
                        variable=self.skip_bigger).grid(row=5, column=1, sticky="w", pady=(6, 0))

        self.status = ttk.Label(main, text="", style="Hint.TLabel", wraplength=780)
        self.status.pack(anchor="w")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", pady=(8, 0))
        self.build_progress(bottom).pack(side="left", fill="x", expand=True)
        self.btn_cancel = ttk.Button(bottom, text="Huỷ", state="disabled",
                                     command=lambda: setattr(self, "_cancel", True))
        self.btn_cancel.pack(side="right", padx=(8, 0))
        self.btn_go = ttk.Button(bottom, text="Nén ngay", style="Big.TButton", command=self.go)
        self.btn_go.pack(side="right", padx=(8, 0))
        self.btn_est = ttk.Button(bottom, text="Ước tính dung lượng", command=self.estimate)
        self.btn_est.pack(side="right", padx=(8, 0))

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.estimates = {}
        self.refresh()
        threading.Thread(target=self.probe_all, daemon=True).start()
        threading.Thread(target=self.detect_gpu, args=(cfg.get("gpu", "cpu"),), daemon=True).start()

    # ---- prefs
    PREFS = os.path.join(core.APP_DIR, "compress_prefs.json")

    def load_prefs(self):
        try:
            with open(self.PREFS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_prefs(self):
        try:
            with open(self.PREFS, "w", encoding="utf-8") as f:
                json.dump({"codec": self.codec.get(), "quality": self.quality.get(), "speed": self.speed.get(),
                           "gpu": self.gpu_key(), "maxh": self.maxh.get(), "audio": self.audio.get()}, f)
        except OSError:
            pass

    # ---- options
    def detect_gpu(self, want):
        try:
            encs = core.available_encoders()
        except Exception:
            encs = set()
        self.root.after(0, lambda: self._gpu_ready(encs, want))

    def _gpu_ready(self, encs, want):
        self.encoders = encs
        self._want_gpu = want
        self.gpu_hint.config(text="")
        self.opts_changed()

    def gpu_choices(self):
        codec = self.codec.get()
        _, sw, hw = core.CODECS[codec]
        ch = [("cpu", "CPU — nén tốt nhất, file nhỏ nhất (khuyên dùng)")]
        for g, enc in hw.items():
            if self.encoders and enc in self.encoders:
                ch.append((g, f"GPU {core.GPU_LABELS[g]} — nhanh gấp nhiều lần, file lớn hơn ~15-30%"))
        return ch

    def gpu_key(self):
        for k, label in self.gpu_choices():
            if label == self.gpu.get():
                return k
        return "cpu"

    def opts_changed(self):
        if self.encoders is not None:
            ch = self.gpu_choices()
            cur = getattr(self, "_want_gpu", None) or self.gpu_key()
            self._want_gpu = None
            self.gpu_box.config(values=[l for _, l in ch])
            self.gpu.set(dict(ch).get(cur, ch[0][1]))
            if len(ch) == 1:
                self.gpu_hint.config(text="  (không có GPU hỗ trợ codec này)")
            else:
                self.gpu_hint.config(text="")
            sw = core.CODECS[self.codec.get()][1]
            if sw not in self.encoders and self.gpu_key() == "cpu":
                self.gpu_hint.config(text=f"  ⚠ ffmpeg thiếu {sw}")
        self.estimates = {}
        self.refresh()

    def opts(self):
        maxh = {"Tối đa 1440p": 1440, "Tối đa 1080p": 1080, "Tối đa 720p": 720, "Tối đa 480p": 480}.get(self.maxh.get(), 0)
        audio = {"AAC 96 kbps": "aac96", "AAC 192 kbps": "aac192", "Giữ nguyên": "copy"}.get(self.audio.get(), "aac128")
        g = self.gpu_key()
        return dict(codec=self.codec.get(), quality=self.quality.get(), speed=self.speed.get(),
                    gpu=None if g == "cpu" else g, max_h=maxh, audio=audio)

    # ---- list
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        tot_src = tot_est = 0
        for n, f in enumerate(self.files):
            info = self.infos.get(f)
            size = os.path.getsize(f) if os.path.exists(f) else 0
            tot_src += size
            if info:
                v = info["video"]
                bitrate = size * 8 / info["duration"] / 1e6 if info["duration"] else 0
                desc = (f"{v['codec']} {v['w']}x{v['h']} · {bitrate:.1f} Mbps" if v else "không có hình")
                dur = core.fmt_time(info["duration"], ms=False)
            else:
                desc, dur = "đang đọc…", ""
            est = self.estimates.get(f)
            if est:
                tot_est += est[0]
                pct = (1 - est[0] / size) * 100 if size else 0
                es = f"~{core.fmt_size(est[0])} ({-pct:+.0f}%)" if pct < 0 else f"~{core.fmt_size(est[0])} (−{pct:.0f}%)"
            else:
                es = ""
            self.tree.insert("", "end", iid=str(n), values=(os.path.basename(f), dur, core.fmt_size(size), desc, es))
        txt = f"{len(self.files)} file · tổng {core.fmt_size(tot_src)}"
        if self.estimates and len(self.estimates) == len(self.files):
            tt = sum(e[1] for e in self.estimates.values())
            txt += (f"  →  ước tính ~{core.fmt_size(tot_est)} (giảm {(1 - tot_est / tot_src) * 100:.0f}%), "
                    f"mất khoảng {self._fmt_dur(tt)}")
        else:
            txt += "  ·  Bấm “Ước tính dung lượng” để nén thử vài đoạn ngắn và xem trước kết quả."
        self.status.config(text=txt)

    @staticmethod
    def _fmt_dur(s):
        s = int(s)
        return f"{s // 3600} giờ {s % 3600 // 60} phút" if s >= 3600 else (f"{s // 60} phút {s % 60}s" if s >= 60 else f"{s}s")

    def probe_all(self):
        for f in list(self.files):
            if f not in self.infos:
                try:
                    self.infos[f] = core.probe(f)
                except Exception:
                    self.infos[f] = {"path": f, "duration": 0, "video": None, "audio": None}
        self.root.after(0, self.refresh)

    def add(self):
        fs = filedialog.askopenfilenames(parent=self.root, title="Thêm video",
                                         filetypes=[("Video", " ".join("*" + e for e in core.VIDEO_EXT))])
        for f in fs:
            if f not in self.files:
                self.files.append(f)
        self.refresh()
        threading.Thread(target=self.probe_all, daemon=True).start()

    def remove(self):
        for i in sorted((int(x) for x in self.tree.selection()), reverse=True):
            self.estimates.pop(self.files[i], None)
            del self.files[i]
        self.refresh()

    def preview(self):
        sel = self.tree.selection()
        if sel:
            core.play(self.files[int(sel[0])])

    def set_busy(self, busy):
        for b in (self.btn_go, self.btn_est):
            b.config(state="disabled" if busy else "normal")
        self.btn_cancel.config(state="normal" if busy else "disabled")

    def ready(self):
        if self._busy or not self.files:
            return False
        if any(f not in self.infos for f in self.files) or self.encoders is None:
            messagebox.showinfo("VideoTool", "Đang đọc thông tin video / dò GPU, thử lại sau giây lát.",
                                parent=self.root)
            return False
        return True

    # ---- estimate
    def estimate(self):
        if not self.ready():
            return
        opts, files = self.opts(), list(self.files)

        def job(prog, cancel):
            for n, f in enumerate(files):
                if cancel():
                    raise core.Cancelled()
                prog(n / len(files))
                self.estimates[f] = core.estimate(self.infos[f], opts, cancel=cancel)
                self.root.after(0, self.refresh)
            prog(1.0)
            return "est"
        self.run_job("Đang nén thử", job, "")

    def job_done(self, err, out, secs, res=None):
        if res == "est":
            self._busy = False
            self.set_busy(False)
            self.plabel.config(text="Ước tính xong")
            self.refresh()
            return
        super().job_done(err, out, secs, res)

    # ---- go
    def go(self):
        if not self.ready():
            return
        self.save_prefs()
        opts = self.opts()
        files = list(self.files)
        infos = [self.infos[f] for f in files]
        total = sum(i["duration"] for i in infos) or 1
        skip = self.skip_bigger.get()

        def job(prog, cancel):
            done, lines, saved = 0.0, [], 0
            for n, info in enumerate(infos):
                src = info["path"]
                out = core.compress_out_name(src)
                self._label = f"Đang nén {n + 1}/{len(infos)}" if len(infos) > 1 else None
                try:
                    core.compress(info, out, opts,
                                  lambda p, d=done, i=info: prog((d + p * i["duration"]) / total), cancel)
                except core.Cancelled:
                    if os.path.exists(out):
                        os.remove(out)
                    raise
                except Exception as e:  # noqa: BLE001
                    if os.path.exists(out):
                        os.remove(out)
                    lines.append(f"✗ {os.path.basename(src)}: lỗi — {str(e).splitlines()[-1][:120]}")
                    done += info["duration"]
                    continue
                done += info["duration"]
                a, b = os.path.getsize(src), os.path.getsize(out)
                if skip and b >= a:
                    os.remove(out)
                    lines.append(f"• {os.path.basename(src)}: bản nén không nhỏ hơn ({core.fmt_size(b)}) → bỏ qua")
                    continue
                saved += a - b
                self._last_out = out
                lines.append(f"✓ {os.path.basename(out)}: {core.fmt_size(a)} → {core.fmt_size(b)} "
                             f"(−{(1 - b / a) * 100:.0f}%)")
            head = f"Đã nén {len(infos)} file, tiết kiệm {core.fmt_size(saved)}.\n\n" if len(infos) > 1 else ""
            return head + "\n".join(lines[:25])
        self._last_out = None
        self.run_job("Đang nén", job, "")

    def on_job_reveal(self):
        return getattr(self, "_last_out", None)


# ============================================================ cập nhật
def auto_update_check(root, get_busy=lambda: False):
    """Kiểm tra GitHub ở nền; có bản mới thì hỏi người dùng."""
    import updater

    def work():
        try:
            r = updater.check()
        except Exception:
            return
        if r:
            root.after(1500, lambda: prompt(r))

    def prompt(r):
        if get_busy():
            root.after(5000, lambda: prompt(r))
            return
        ver, notes = r
        ans = messagebox.askyesnocancel(
            "VideoTool — Có bản mới",
            f"Có phiên bản mới {ver} (đang dùng {updater.local_version()}).\n\n{notes}\n\n"
            "Cập nhật ngay?\n(Có = cập nhật · Không = nhắc lần sau · Huỷ = bỏ qua bản này)",
            parent=root)
        if ans is None:
            updater.skip(ver)
        elif ans:
            threading.Thread(target=lambda: do_update(root), daemon=True).start()
    threading.Thread(target=work, daemon=True).start()


def do_update(root, then_quit=False):
    import updater
    try:
        v = updater.apply_update()
        msg = (f"Đã cập nhật lên bản {v}.\nBản mới có hiệu lực từ lần mở tiếp theo.", None)
    except Exception as e:  # noqa: BLE001
        msg = (None, f"Cập nhật thất bại:\n{e}")

    def show():
        if msg[0]:
            messagebox.showinfo("VideoTool", msg[0], parent=root)
        else:
            messagebox.showerror("VideoTool", msg[1], parent=root)
        if then_quit:
            root.destroy()
    root.after(0, show)


def manual_update(root):
    import updater
    root.withdraw()
    try:
        r = updater.check(force=True)
    except Exception as e:  # noqa: BLE001
        messagebox.showerror("VideoTool", f"Không kết nối được GitHub:\n{e}")
        return root.destroy()
    if not r:
        messagebox.showinfo("VideoTool", f"Bạn đang dùng bản mới nhất ({updater.local_version()}).")
        return root.destroy()
    ver, notes = r
    if messagebox.askyesno("VideoTool", f"Có bản mới {ver} (đang dùng {updater.local_version()}).\n\n"
                                        f"{notes}\n\nCập nhật ngay?"):
        threading.Thread(target=lambda: do_update(root, then_quit=True), daemon=True).start()
    else:
        root.destroy()


# ============================================================ main
def main():
    args = sys.argv[1:]
    mode = args[0] if args else "merge"
    paths = args[1:]

    if mode == "update":
        root = tk.Tk()
        manual_update(root)
        root.mainloop()
        return

    if mode == "merge":
        paths = gather_paths(mode, paths)
        if paths is None:
            return
    elif mode in ("merge-folder", "compress-folder"):
        folder = paths[0] if paths else os.getcwd()
        paths = core.videos_in_folder(folder)
        mode = mode.split("-")[0]
    elif mode == "compress":
        paths = gather_paths(mode, paths)
        if paths is None:
            return

    root = tk.Tk()
    setup_style(root)
    try:
        root.iconbitmap(os.path.join(core.APP_DIR, "videotool.ico"))
    except Exception:
        pass
    if not check_ffmpeg():
        return
    if mode == "edit":
        path = paths[0] if paths else filedialog.askopenfilename(
            title="Chọn video", filetypes=[("Video", " ".join("*" + e for e in core.VIDEO_EXT))])
        if not path:
            return
        win = EditWindow(root, path)
    elif mode == "compress":
        if not paths:
            paths = list(filedialog.askopenfilenames(
                title="Chọn video cần nén", filetypes=[("Video", " ".join("*" + e for e in core.VIDEO_EXT))]))
        win = CompressWindow(root, paths)
    else:
        if not paths:
            paths = list(filedialog.askopenfilenames(
                title="Chọn các video cần ghép", filetypes=[("Video", " ".join("*" + e for e in core.VIDEO_EXT))]))
        win = MergeWindow(root, paths)
    try:
        import updater
        root.title(root.title() + f"  (v{updater.local_version()})")
    except Exception:
        pass
    auto_update_check(root, lambda: win._busy)
    root.lift()
    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        try:
            messagebox.showerror("VideoTool", traceback.format_exc())
        except Exception:
            pass
