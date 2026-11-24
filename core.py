"""MergenCut core: ffmpeg/ffprobe helpers (không phụ thuộc GUI)."""
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
VIDEO_EXT = (".mp4", ".mkv", ".mov", ".avi", ".ts", ".m2ts", ".mts", ".flv",
             ".webm", ".wmv", ".m4v", ".3gp", ".mpg", ".mpeg", ".vob")
AUDIO_EXT = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".ac3",
             ".amr", ".aiff", ".aif", ".mka")
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# ---------------------------------------------------------------- binaries
def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def find_bin(name):
    """Tìm ffmpeg/ffprobe/ffplay: config.json -> thư mục bin cạnh tool -> PATH -> WinGet."""
    exe = name + (".exe" if os.name == "nt" else "")
    cfg = _load_config().get(name)
    if cfg and os.path.isfile(cfg):
        return cfg
    for p in (os.path.join(APP_DIR, "bin", exe), os.path.join(APP_DIR, exe)):
        if os.path.isfile(p):
            return p
    p = shutil.which(name)
    if p:
        return p
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        cands = [os.path.join(local, "Microsoft", "WinGet", "Links", exe)]
        cands += glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages",
                                        "*FFmpeg*", "**", "bin", exe), recursive=True)
        cands += [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "ffmpeg", "bin", exe),
                  r"C:\ffmpeg\bin\\" + exe]
        for c in cands:
            if os.path.isfile(c):
                return c
    return None


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, creationflags=CREATE_NO_WINDOW, **kw)


# ---------------------------------------------------------------- helpers
def natural_key(path):
    s = os.path.basename(path).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def is_video(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXT


def is_audio(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXT


def videos_in_folder(folder):
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
    return sorted([f for f in files if os.path.isfile(f) and is_video(f)], key=natural_key)


def fmt_time(t, ms=True):
    t = max(0.0, float(t))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}" if ms else f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def parse_time(text):
    """'1:23.5', '00:01:23', '83.5' -> giây."""
    parts = text.strip().replace(",", ".").split(":")
    val = 0.0
    for p in parts:
        val = val * 60 + float(p or 0)
    return val


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{base} ({i}){ext}"):
        i += 1
    return f"{base} ({i}){ext}"


def suggest_merged_name(paths):
    stems = [os.path.splitext(os.path.basename(p))[0] for p in paths]
    prefix = os.path.commonprefix(stems) if len(stems) > 1 else stems[0]
    prefix = re.sub(r"[\s_\-.(\[]*(part|phan|phần|p|cd|disc|tap|tập|ep)?[\s_\-.(\[]*\d*$", "",
                    prefix, flags=re.I).strip(" _-.([")
    name = (prefix or "merged") + "_merged"
    ext = os.path.splitext(paths[0])[1].lower() or ".mp4"
    if ext in (".ts", ".m2ts", ".mts", ".vob", ".mpg", ".mpeg"):
        ext = ".mp4"
    return unique_path(os.path.join(os.path.dirname(paths[0]), name + ext))


# ---------------------------------------------------------------- probe
def probe(path):
    """Trả về dict: duration, video{codec,w,h,pix,fps}, audio{codec,rate,ch} hoặc None."""
    ffprobe = find_bin("ffprobe")
    r = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path])
    data = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    info = {"path": path, "duration": 0.0, "video": None, "audio": None}
    try:
        info["duration"] = float(data.get("format", {}).get("duration", 0) or 0)
    except ValueError:
        pass
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["video"] is None and \
                not s.get("disposition", {}).get("attached_pic"):
            fps = 30.0
            try:
                n, d = s.get("avg_frame_rate", "0/1").split("/")
                fps = float(n) / float(d) if float(d) and float(n) else fps
            except Exception:
                pass
            info["video"] = {"codec": s.get("codec_name"), "w": s.get("width"), "h": s.get("height"),
                             "pix": s.get("pix_fmt"), "fps": round(fps, 3)}
        elif s.get("codec_type") == "audio" and info["audio"] is None:
            try:
                abr = int(s.get("bit_rate") or 0)
            except ValueError:
                abr = 0
            info["audio"] = {"codec": s.get("codec_name"), "rate": s.get("sample_rate"),
                             "ch": s.get("channels"), "bitrate": abr}
    return info


def compatible(infos):
    """Kiểm tra các file có thể ghép nhanh (stream copy) không. Trả về (ok, lý do)."""
    base = infos[0]
    for i in infos[1:]:
        name = os.path.basename(i["path"])
        if (base["video"] is None) != (i["video"] is None):
            return False, f"{name}: có/không có hình khác nhau"
        if base["video"] and i["video"]:
            for k in ("codec", "w", "h", "pix"):
                if base["video"][k] != i["video"][k]:
                    return False, f"{name}: video {k} khác ({base['video'][k]} ≠ {i['video'][k]})"
        if (base["audio"] is None) != (i["audio"] is None):
            return False, f"{name}: có/không có tiếng khác nhau"
        if base["audio"] and i["audio"]:
            for k in ("codec", "rate", "ch"):
                if base["audio"][k] != i["audio"][k]:
                    return False, f"{name}: audio {k} khác ({base['audio'][k]} ≠ {i['audio'][k]})"
    return True, "Các file cùng định dạng — ghép nhanh không mất chất lượng."


# ---------------------------------------------------------------- ffmpeg runner
class Cancelled(Exception):
    pass


def run_ffmpeg(args, total_dur, on_progress=None, cancel=None):
    """Chạy ffmpeg với -progress, gọi on_progress(0..1). Raise RuntimeError khi lỗi."""
    ffmpeg = find_bin("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-y", "-nostdin", "-progress", "pipe:1", "-nostats"] + args
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=CREATE_NO_WINDOW)
    err_lines = []

    import threading
    def read_err():
        for line in proc.stderr:
            err_lines.append(line.decode("utf-8", "replace"))
            del err_lines[:-40]
    t = threading.Thread(target=read_err, daemon=True)
    t.start()
    for raw in proc.stdout:
        if cancel and cancel():
            proc.kill()
            proc.wait()
            raise Cancelled()
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                us = int(line.split("=")[1])
                if on_progress and total_dur > 0:
                    on_progress(min(1.0, us / 1e6 / total_dur))
            except ValueError:
                pass
    proc.wait()
    t.join(timeout=2)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg lỗi:\n" + "".join(err_lines[-15:]))
    if on_progress:
        on_progress(1.0)


def _concat_list(paths):
    fd, lst = tempfile.mkstemp(suffix=".txt", prefix="videotool_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for p in paths:
            f.write("file '" + os.path.abspath(p).replace("\\", "/").replace("'", "'\\''") + "'\n")
    return lst


def _out_flags(out):
    return ["-movflags", "+faststart"] if os.path.splitext(out)[1].lower() in (".mp4", ".mov", ".m4v") else []


def encoder_args(crf=20):
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k"]


# ---------------------------------------------------------------- merge
def merge_fast(paths, out, total, on_progress=None, cancel=None):
    lst = _concat_list(paths)
    try:
        run_ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-map", "0:v?", "-map", "0:a?",
                    "-c", "copy", "-avoid_negative_ts", "make_zero"] + _out_flags(out) + [out],
                   total, on_progress, cancel)
    finally:
        os.remove(lst)


def merge_reencode(infos, out, on_progress=None, cancel=None, crf=20):
    """Ghép các video khác định dạng/độ phân giải: scale + pad về khung của file đầu."""
    v0 = next((i["video"] for i in infos if i["video"]), None)
    W, H = (v0["w"] // 2 * 2, v0["h"] // 2 * 2) if v0 else (1280, 720)
    fps = v0["fps"] if v0 else 30
    args, fl, pairs = [], [], ""
    for n, i in enumerate(infos):
        args += ["-i", i["path"]]
        d = i["duration"] or 0.1
        if i["video"]:
            fl.append(f"[{n}:v:0]scale={W}:{H}:force_original_aspect_ratio=decrease,"
                      f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p[v{n}]")
        else:
            fl.append(f"color=c=black:s={W}x{H}:r={fps}:d={d},format=yuv420p[v{n}]")
        if i["audio"]:
            fl.append(f"[{n}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{n}]")
        else:
            fl.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{d}[a{n}]")
        pairs += f"[v{n}][a{n}]"
    fl.append(f"{pairs}concat=n={len(infos)}:v=1:a=1[v][a]")
    total = sum(i["duration"] for i in infos)
    run_ffmpeg(args + ["-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]"]
               + encoder_args(crf) + _out_flags(out) + [out], total, on_progress, cancel)


# ---------------------------------------------------------------- cut / edit
def normalize(ranges, duration):
    rs = sorted((max(0.0, a), min(duration, b)) for a, b in ranges if b > a)
    merged = []
    for a, b in rs:
        if merged and a <= merged[-1][1] + 1e-3:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return [(a, b) for a, b in merged if b - a > 0.01]


def keep_ranges(ranges, duration, mode="remove"):
    """mode='remove': ranges là đoạn bị xoá. mode='keep': ranges là đoạn giữ lại."""
    ranges = normalize(ranges, duration)
    if mode == "keep":
        return ranges
    keep, pos = [], 0.0
    for a, b in ranges:
        if a > pos:
            keep.append((pos, a))
        pos = b
    if duration - pos > 0.01:
        keep.append((pos, duration))
    return keep


def export_fast(src, keep, out, on_progress=None, cancel=None):
    """Cắt bằng stream copy (rất nhanh, điểm cắt bám keyframe gần nhất)."""
    tmpdir = tempfile.mkdtemp(prefix="videotool_")
    ext = os.path.splitext(src)[1] or ".mp4"
    total = sum(b - a for a, b in keep)
    done = 0.0
    parts = []
    try:
        for n, (a, b) in enumerate(keep):
            part = os.path.join(tmpdir, f"part{n:03d}{ext}")
            seg = b - a
            run_ffmpeg(["-ss", f"{a:.3f}", "-i", src, "-t", f"{seg:.3f}", "-map", "0:v?", "-map", "0:a?",
                        "-c", "copy", "-avoid_negative_ts", "make_zero", part], seg,
                       (lambda p, d=done, s=seg: on_progress((d + p * s) / total * 0.9)) if on_progress else None,
                       cancel)
            done += seg
            parts.append(part)
        if len(parts) == 1 and not _out_flags(out) and \
                os.path.splitext(out)[1].lower() == ext.lower():
            shutil.move(parts[0], out)
        else:
            merge_fast(parts, out, total, None, cancel)
        if on_progress:
            on_progress(1.0)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def export_accurate(src, info, keep, out, on_progress=None, cancel=None, crf=18):
    """Cắt chính xác tới từng frame (encode lại)."""
    total = sum(b - a for a, b in keep)
    fl, pairs = [], ""
    has_v, has_a = info["video"] is not None, info["audio"] is not None
    for n, (a, b) in enumerate(keep):
        if has_v:
            fl.append(f"[0:v:0]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{n}]")
            pairs += f"[v{n}]"
        if has_a:
            fl.append(f"[0:a:0]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{n}]")
            pairs += f"[a{n}]"
    fl.append(f"{pairs}concat=n={len(keep)}:v={int(has_v)}:a={int(has_a)}"
              + ("[v]" if has_v else "") + ("[a]" if has_a else ""))
    maps = (["-map", "[v]"] if has_v else []) + (["-map", "[a]"] if has_a else [])
    run_ffmpeg(["-i", src, "-filter_complex", ";".join(fl)] + maps + encoder_args(crf)
               + _out_flags(out) + [out], total, on_progress, cancel)


def grab_frame_png(path, t, width=720):
    """Lấy 1 frame tại thời điểm t, trả về bytes PNG (để preview)."""
    r = run([find_bin("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0, t):.3f}",
             "-i", path, "-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe",
             "-vcodec", "png", "-"])
    return r.stdout or None


def play(path, t=0.0):
    ffplay = find_bin("ffplay")
    if ffplay:
        subprocess.Popen([ffplay, "-hide_banner", "-loglevel", "quiet", "-ss", f"{t:.3f}",
                          "-window_title", os.path.basename(path), path],
                         creationflags=CREATE_NO_WINDOW)
        return True
    if os.name == "nt":
        os.startfile(path)
    return False


# ---------------------------------------------------------------- compress
# Mỗi codec: (encoder, tham số chất lượng theo mức) — số càng lớn file càng nhỏ.
QUALITY_LEVELS = ("near", "balanced", "small")
QUALITY_LABELS = {"near": "Gần như nguyên bản", "balanced": "Cân bằng (khuyên dùng)", "small": "Nhỏ nhất (giảm nhẹ chất lượng)"}
SPEED_LEVELS = ("fast", "medium", "slow")
SPEED_LABELS = {"fast": "Nhanh", "medium": "Vừa", "slow": "Chậm (nhỏ hơn ~5-10%)"}

CODECS = {
    # key: (nhãn, encoder CPU, {GPU: encoder})
    "hevc": ("H.265 / HEVC — nhỏ hơn H.264 ~40-50%, xem được hầu hết mọi nơi", "libx265",
             {"nvenc": "hevc_nvenc", "qsv": "hevc_qsv", "amf": "hevc_amf"}),
    "av1": ("AV1 — nhỏ nhất (thêm ~20-30% so với H.265), máy/TV cũ có thể không xem được", "libsvtav1",
            {"nvenc": "av1_nvenc", "qsv": "av1_qsv", "amf": "av1_amf"}),
    "h264": ("H.264 — tương thích tuyệt đối, nén kém nhất", "libx264",
             {"nvenc": "h264_nvenc", "qsv": "h264_qsv", "amf": "h264_amf"}),
}
GPU_LABELS = {"nvenc": "NVIDIA", "qsv": "Intel", "amf": "AMD"}

_CRF = {"libx265": (20, 24, 28), "libx264": (18, 22, 26), "libsvtav1": (27, 33, 39)}
_HWQ = {"hevc": (22, 26, 30), "h264": (20, 24, 28), "av1": (28, 34, 40)}


def available_encoders():
    """Trả về set encoder dùng được thật (GPU được thử encode 1 khung hình)."""
    ffmpeg = find_bin("ffmpeg")
    listed = run([ffmpeg, "-hide_banner", "-encoders"]).stdout.decode("utf-8", "replace")
    ok = set()
    for key, (_, sw, hw) in CODECS.items():
        if f" {sw} " in listed:
            ok.add(sw)
        for enc in hw.values():
            if f" {enc} " not in listed:
                continue
            r = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                     "color=c=gray:s=640x360:r=30:d=0.2", "-c:v", enc, "-f", "null", "-"], timeout=20)
            if r.returncode == 0:
                ok.add(enc)
    return ok


def video_encode_args(codec, quality="balanced", speed="medium", gpu=None):
    q = QUALITY_LEVELS.index(quality)
    s = SPEED_LEVELS.index(speed)
    _, sw, hw = CODECS[codec]
    if gpu:
        enc = hw[gpu]
        v = _HWQ[codec][q]
        if gpu == "nvenc":
            args = ["-c:v", enc, "-preset", ("p4", "p6", "p7")[s], "-tune", "hq", "-rc", "vbr",
                    "-cq", str(v), "-b:v", "0", "-spatial_aq", "1", "-temporal_aq", "1"]
        elif gpu == "qsv":
            args = ["-c:v", enc, "-preset", ("faster", "medium", "veryslow")[s], "-global_quality", str(v)]
        else:  # amf
            args = ["-c:v", enc, "-quality", ("speed", "balanced", "quality")[s], "-rc", "cqp",
                    "-qp_i", str(v), "-qp_p", str(v + 2)] + (["-qp_b", str(v + 4)] if codec != "av1" else [])
        args += ["-pix_fmt", "nv12" if gpu == "qsv" else "yuv420p"]
    else:
        crf = _CRF[sw][q]
        if sw == "libx265":
            args = ["-c:v", sw, "-preset", ("fast", "medium", "slow")[s], "-crf", str(crf),
                    "-pix_fmt", "yuv420p10le", "-x265-params", "log-level=error:aq-mode=3"]
        elif sw == "libsvtav1":
            args = ["-c:v", sw, "-preset", ("8", "6", "4")[s], "-crf", str(crf),
                    "-pix_fmt", "yuv420p10le", "-svtav1-params", "tune=0:enable-overlays=1"]
        else:
            args = ["-c:v", sw, "-preset", ("fast", "medium", "slow")[s], "-crf", str(crf),
                    "-pix_fmt", "yuv420p"]
    if codec == "hevc":
        args += ["-tag:v", "hvc1"]   # để Windows Photos / iPhone / Mac mở được
    return args


def compress_args(info, codec, quality, speed, gpu, max_h=0, audio="aac128"):
    """Tham số ffmpeg (sau -i) để nén 1 file."""
    args = ["-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0", "-sn", "-dn"]
    v = info.get("video") or {}
    if max_h and v.get("w") and v.get("h") and min(v["w"], v["h"]) > max_h:
        if v["w"] >= v["h"]:
            args += ["-vf", f"scale=-2:{max_h}:flags=lanczos"]
        else:
            args += ["-vf", f"scale={max_h}:-2:flags=lanczos"]
    args += video_encode_args(codec, quality, speed, gpu)
    if audio == "copy":
        args += ["-c:a", "copy"]
    else:
        args += ["-c:a", "aac", "-b:a", {"aac96": "96k", "aac128": "128k", "aac192": "192k"}[audio]]
    return args


def compress_out_name(path):
    base = os.path.splitext(path)[0]
    return unique_path(base + "_compressed.mp4")


def compress(info, out, opts, on_progress=None, cancel=None):
    src = info["path"]
    run_ffmpeg(["-i", src] + compress_args(info, **opts) + ["-movflags", "+faststart", out],
               info["duration"], on_progress, cancel)


def estimate(info, opts, sample=4.0, points=(0.15, 0.5, 0.85), cancel=None):
    """Nén thử vài đoạn ngắn → (dung lượng ước tính bytes, thời gian ước tính giây)."""
    dur = info["duration"]
    if dur <= sample * len(points) * 1.5:
        points, sample = (0.0,), max(0.5, dur)
    tmpdir = tempfile.mkdtemp(prefix="videotool_est_")
    total_size, total_len, t0 = 0, 0.0, None
    import time as _t
    try:
        t0 = _t.time()
        for n, p in enumerate(points):
            if cancel and cancel():
                raise Cancelled()
            out = os.path.join(tmpdir, f"s{n}.mp4")
            start = max(0.0, min(dur - sample, dur * p))
            run_ffmpeg(["-ss", f"{start:.3f}", "-i", info["path"], "-t", f"{sample:.3f}"]
                       + compress_args(info, **opts) + [out], sample)
            total_size += os.path.getsize(out)
            total_len += min(sample, dur - start)
        el = _t.time() - t0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    if total_len <= 0:
        return 0, 0
    return total_size / total_len * dur, el / total_len * dur


def fmt_size(b):
    b = float(b)
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024 or u == "GB":
            return f"{b:.0f} {u}" if u in ("B", "KB") else f"{b:.1f} {u}"
        b /= 1024


# ---------------------------------------------------------------- video -> audio
# key: (nhãn, đuôi file, tham số encoder, có lossy/bitrate không)
AUDIO_FORMATS = {
    "mp3": ("MP3 — phổ biến nhất, mở được ở mọi nơi", ".mp3", ["-c:a", "libmp3lame"], True),
    "m4a": ("M4A (AAC) — hay hơn MP3 cùng dung lượng, hợp iPhone / Mac", ".m4a", ["-c:a", "aac"], True),
    "opus": ("Opus — nhỏ nhất cho cùng chất lượng, hợp giọng nói / podcast", ".opus", ["-c:a", "libopus"], True),
    "ogg": ("OGG Vorbis — định dạng mở, dùng cho game / web", ".ogg", ["-c:a", "libvorbis"], True),
    "flac": ("FLAC — không mất chất lượng, nhỏ hơn WAV ~40-60%", ".flac", ["-c:a", "flac"], False),
    "wav": ("WAV — không nén, file rất lớn, dùng để biên tập", ".wav", ["-c:a", "pcm_s16le"], False),
    "copy": ("Giữ nguyên âm thanh gốc — nhanh nhất, không giảm chất lượng", None, ["-c:a", "copy"], False),
}
AUDIO_BITRATES = ("96k", "128k", "192k", "256k", "320k")
_VORBIS_Q = {"96k": 2, "128k": 4, "192k": 6, "256k": 8, "320k": 9}
# Đuôi file phù hợp khi giữ nguyên luồng âm thanh gốc (theo codec).
_COPY_EXT = {"aac": ".m4a", "alac": ".m4a", "mp3": ".mp3", "opus": ".opus", "vorbis": ".ogg",
             "flac": ".flac", "ac3": ".ac3", "eac3": ".eac3", "dts": ".dts", "mp2": ".mp2",
             "wmav2": ".wma", "wmav1": ".wma", "amr_nb": ".amr"}


def audio_encoder_missing(fmt):
    """Tên encoder mà ffmpeg đang thiếu cho định dạng này (None nếu đủ)."""
    enc = AUDIO_FORMATS[fmt][2][1]
    if enc in ("copy", "aac", "flac", "pcm_s16le"):
        return None
    listed = run([find_bin("ffmpeg"), "-hide_banner", "-encoders"]).stdout.decode("utf-8", "replace")
    return None if f" {enc} " in listed else enc


def audio_ext(info, fmt):
    ext = AUDIO_FORMATS[fmt][1]
    if ext:
        return ext
    codec = (info.get("audio") or {}).get("codec") or ""
    if codec.startswith("pcm_"):
        return ".wav"
    return _COPY_EXT.get(codec, ".mka")


def audio_out_name(info, fmt, folder=None):
    src = info["path"]
    base = os.path.splitext(os.path.basename(src))[0]
    return unique_path(os.path.join(folder or os.path.dirname(src), base + audio_ext(info, fmt)))


def audio_args(fmt, bitrate="192k", channels=0, rate=0):
    """Tham số ffmpeg (sau -i) để tách / chuyển âm thanh. channels/rate = 0 là giữ nguyên."""
    _, _, enc, lossy = AUDIO_FORMATS[fmt]
    args = ["-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "0"] + enc
    if fmt == "copy":
        return args
    if lossy:
        if fmt == "opus" and int(bitrate.rstrip("k")) > 256:
            bitrate = "256k"                  # libopus tối đa 256k/kênh; 256k đã là mức trong suốt
        if fmt == "ogg":                      # Vorbis: dùng VBR theo chất lượng (-b:a dễ lỗi với mono)
            args += ["-q:a", str(_VORBIS_Q.get(bitrate, 6))]
        else:
            args += ["-b:a", bitrate]
    if channels:
        args += ["-ac", str(channels)]
    if rate and fmt != "opus":            # Opus luôn 48 kHz
        args += ["-ar", str(rate)]
    if fmt == "m4a":
        args += ["-movflags", "+faststart"]
    return args


def estimate_audio_size(info, fmt, bitrate="192k", channels=0, rate=0):
    """Ước tính dung lượng file âm thanh (bytes), 0 nếu không đoán được."""
    a, dur = info.get("audio"), info.get("duration") or 0
    if not a or not dur:
        return 0
    ch = channels or a.get("ch") or 2
    sr = (rate if fmt != "opus" else 0) or int(a.get("rate") or 48000)
    if fmt == "copy":
        return a.get("bitrate", 0) * dur / 8
    if fmt == "wav":
        return sr * ch * 2 * dur
    if fmt == "flac":
        return sr * ch * 2 * dur * 0.55
    kbps = int(bitrate.rstrip("k"))
    if fmt == "opus":
        kbps = min(kbps, 256)
    return kbps * 1000 * dur / 8


def extract_audio(info, out, opts, on_progress=None, cancel=None):
    """opts: dict(fmt, bitrate, channels, rate)."""
    run_ffmpeg(["-i", info["path"]] + audio_args(**opts) + [out], info["duration"], on_progress, cancel)


# ---------------------------------------------------------------- nhập audio vào video
# Codec âm thanh được chép thẳng (không encode lại) theo từng loại file video.
_MUX_COPY = {".mp4": {"aac", "mp3"}, ".m4v": {"aac", "mp3"}, ".mov": {"aac", "mp3"}, ".3gp": {"aac"},
             ".webm": {"opus", "vorbis"}, ".ts": {"aac", "mp3", "ac3"}, ".m2ts": {"aac", "ac3"},
             ".mts": {"aac", "ac3"}, ".flv": {"aac", "mp3"}, ".mkv": None}   # None = nhận mọi codec


def mux_out_ext(video_path):
    ext = os.path.splitext(video_path)[1].lower()
    return ext if ext in _MUX_COPY else ".mkv"      # avi, wmv, mpg… → mkv (chứa được mọi codec)


def mux_out_name(vinfo, ainfo, folder=None):
    vbase = os.path.splitext(os.path.basename(vinfo["path"]))[0]
    abase = os.path.splitext(os.path.basename(ainfo["path"]))[0][:40].strip()
    return unique_path(os.path.join(folder or os.path.dirname(vinfo["path"]),
                                    f"{vbase} + {abase}{mux_out_ext(vinfo['path'])}"))


def mux_args(vinfo, ainfo, out, mode="replace", loop=False, vol_new=100, vol_orig=100):
    """Tham số ffmpeg ghép hình của video với âm thanh của file kia.
    mode: replace = thay tiếng gốc; mix = trộn với tiếng gốc (nếu video có tiếng)."""
    ext = os.path.splitext(out)[1].lower()
    vdur = vinfo.get("duration") or 0
    if mode == "mix" and not vinfo.get("audio"):
        mode = "replace"
    args = (["-stream_loop", "-1"] if loop else []) + ["-i", ainfo["path"]]
    args = ["-i", vinfo["path"]] + args
    args += ["-map", "0:v:0"]
    if mode == "mix":
        f = (f"[0:a:0]volume={vol_orig / 100:g}[a0];[1:a:0]volume={vol_new / 100:g}[a1];"
             f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        args += ["-filter_complex", f, "-map", "[aout]"]
    else:
        args += ["-map", "1:a:0"]
        if vol_new != 100:
            args += ["-af", f"volume={vol_new / 100:g}"]
    args += ["-c:v", "copy"]
    ok = _MUX_COPY.get(ext, None) if ext in _MUX_COPY else set()
    codec = (ainfo.get("audio") or {}).get("codec")
    can_copy = mode == "replace" and not loop and vol_new == 100 and (ok is None or codec in ok)
    if can_copy:
        args += ["-c:a", "copy"]
    elif ext == ".webm":
        args += ["-c:a", "libopus", "-b:a", "160k"]
    else:
        args += ["-c:a", "aac", "-b:a", "192k"]
    if vdur:
        args += ["-t", f"{vdur:.3f}"]               # luôn theo độ dài video
    args += ["-map_metadata", "0"] + _out_flags(out) + [out]
    return args


def mux(vinfo, ainfo, out, opts, on_progress=None, cancel=None):
    """opts: dict(mode, loop, vol_new, vol_orig)."""
    run_ffmpeg(mux_args(vinfo, ainfo, out, **opts), vinfo.get("duration") or ainfo.get("duration") or 0,
               on_progress, cancel)
