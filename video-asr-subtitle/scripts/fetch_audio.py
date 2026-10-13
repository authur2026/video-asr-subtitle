#!/usr/bin/env python3
"""下载视频音频并转成 ASR 友好的 WAV（16k单声道）。

支持平台：
  bilibili      B站（默认）——匿名可取，无需登录
  xiaohongshu   小红书   —— 走 yt-dlp，URL 必须含 xsec_token
  generic       其他平台 —— 走 yt-dlp（YouTube / 抖音 / 快手 / 微博等）
  local         本地文件 —— 直接转 WAV

用法：
    python fetch_audio.py BV1xxxxxxxxx
    python fetch_audio.py "https://www.bilibili.com/video/BV1xxx/" -o D:/out
    python fetch_audio.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=AAA"
    python fetch_audio.py "https://www.youtube.com/watch?v=xxx"
    python fetch_audio.py ./video.mp4

关于登录态：
  - B站：音频 DASH 流匿名可取（登录态只影响「枚举字幕列表」，不影响取流）
  - 小红书：必须带 xsec_token（从 App 分享按钮复制，不要从浏览器地址栏复制）
    匿名即可拿到音频；私密笔记才需真正登录
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

try:
    import requests
except ImportError:
    raise SystemExit(
        "缺少 requests。安装：\n"
        "  python -m pip install requests\n"
        "（非B站平台还需：python -m pip install yt-dlp）"
    )

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


# 常见音视频扩展名——用于识别本地文件（即使文件不存在也能判定意图）
MEDIA_EXTS = (
    ".mp4", ".m4a", ".m4s", ".mp3", ".wav", ".flac", ".aac", ".ogg",
    ".wma", ".mov", ".mkv", ".webm", ".avi", ".flv", ".ts",
)


def detect_platform(target):
    """自动判断平台。"""
    t = target.lower().strip()
    if t.startswith("bv") or "bilibili.com" in t or "b23.tv" in t:
        return "bilibili"
    if "xiaohongshu.com" in t or "xhslink.com" in t:
        return "xiaohongshu"
    if t.endswith(MEDIA_EXTS):
        return "local"
    try:
        if os.path.isfile(target):
            return "local"
    except (OSError, ValueError):
        pass
    return "generic"


def extract_bvid(arg):
    """从 BV 号或完整链接中解析 BV 号。"""
    arg = arg.strip()
    if arg.startswith("BV"):
        return arg[:12]
    for token in arg.replace("/", " ").replace("?", " ").split():
        if token.startswith("BV") and len(token) >= 12:
            return token[:12]
    raise SystemExit(f"无法解析 BV 号: {arg}")


def find_ffmpeg():
    """定位 ffmpeg：先查 PATH，再查各平台常见安装位置。"""
    for name in ("ffmpeg", "ffmpeg.exe"):
        path = shutil.which(name)
        if path:
            return path
    exe = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    home = os.path.expanduser("~")
    for base in (
        os.path.join(home, ".local", "bin"),
        os.path.join(home, "bin"),
        os.path.join(home, ".ffmpeg", "bin"),
        "/opt/homebrew/bin",            # macOS Apple Silicon
        "/usr/local/bin",               # macOS Intel / Linux
        "/usr/bin",
        r"C:\ffmpeg\bin",
        r"C:\ProgramData\chocolatey\bin",
    ):
        cand = os.path.join(base, exe)
        if os.path.exists(cand):
            return cand
    raise SystemExit(
        "找不到 ffmpeg。请安装后加入 PATH：\n"
        "  Windows: winget install Gyan.FFmpeg  或从 ffmpeg.org 下载后加 bin 到 PATH\n"
        "  macOS:   brew install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg"
    )


# ────────────────────────── B站 ──────────────────────────

def fetch_bilibili(target, outdir, page=1):
    bvid = extract_bvid(target)
    r = requests.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid}, headers=UA, timeout=20,
    ).json()
    if r.get("code") != 0:
        raise SystemExit(f"view 接口失败: {r.get('code')} {r.get('message')}")
    video = r["data"]

    cid = video["cid"]
    if video.get("videos", 1) > 1:
        pl = requests.get(
            "https://api.bilibili.com/x/player/pagelist",
            params={"bvid": bvid}, headers=UA, timeout=20,
        ).json()
        pages = pl.get("data") or []
        if not 1 <= page <= len(pages):
            raise SystemExit(f"分P 越界，共 {len(pages)} 个分P")
        cid = pages[page - 1]["cid"]

    print(f"[video] {video['title']}")
    print(f"        时长 {video['duration']}s ({round(video['duration']/60,1)} min)  cid={cid}")

    headers = dict(UA)
    headers["Referer"] = f"https://www.bilibili.com/video/{bvid}/"
    p = requests.get(
        "https://api.bilibili.com/x/player/playurl",
        params={"bvid": bvid, "cid": cid, "fnval": 16, "qn": 64},
        headers=headers, timeout=20,
    ).json()
    if p.get("code") != 0:
        raise SystemExit(f"playurl 失败: {p.get('code')} {p.get('message')}")
    dash = p["data"].get("dash")
    if not dash or not dash.get("audio"):
        raise SystemExit("未取到音频流（该视频可能需要登录或为付费内容）")
    audio = max(dash["audio"], key=lambda x: x["bandwidth"])

    m4s_path = os.path.join(outdir, f"audio_{bvid}.m4s")
    print(f"[下载] {audio['bandwidth']//1000} kbps -> {os.path.basename(m4s_path)}")
    resp = requests.get(audio["baseUrl"], headers=headers, timeout=300, stream=True)
    resp.raise_for_status()
    n = 0
    with open(m4s_path, "wb") as f:
        for chunk in resp.iter_content(1 << 16):
            f.write(chunk)
            n += len(chunk)
    print(f"        {round(n/1024/1024,2)} MB")
    return m4s_path, bvid


# ─────────────────────── 通用 / 小红书（yt-dlp） ───────────────────────

def fetch_ytdlp(url, outdir, platform):
    """用 yt-dlp 只下音频。"""
    try:
        import yt_dlp
    except ImportError:
        raise SystemExit("缺少 yt-dlp，请安装：python -m pip install yt-dlp")

    if platform == "xiaohongshu" and "xsec_token=" not in url:
        raise SystemExit(
            "小红书 URL 缺少 xsec_token 参数。\n"
            "  获取方式：用小红书 App 打开笔记 → 分享 → 复制链接\n"
            "  注意：不要从浏览器地址栏复制，那里的链接没有 xsec_token"
        )

    outtmpl = os.path.join(outdir, "audio_%(id)s.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "http_headers": {"User-Agent": UA["User-Agent"]},
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise SystemExit(
                f"yt-dlp 解析失败：{type(e).__name__}: {e}\n"
                "  小红书：确认 URL 含 xsec_token，且笔记未被删除/设为私密"
            )
        if info is None:
            raise SystemExit("yt-dlp 无法解析该链接（可能是链接失效或需要登录）")
        print(f"[video] {info.get('title', '(未知标题)')}")
        dur = info.get("duration")
        if dur:
            print(f"        时长 {dur}s ({round(dur/60,1)} min)")
        print(f"[平台]  {info.get('extractor', '?')}")
        try:
            ydl.download([url])
        except Exception as e:
            raise SystemExit(f"下载失败：{type(e).__name__}: {e}")

    # 找出实际下载的文件
    files = sorted(
        (os.path.join(outdir, f) for f in os.listdir(outdir)
         if f.startswith("audio_") and not f.endswith(".wav")),
        key=os.path.getmtime, reverse=True,
    )
    if not files:
        raise SystemExit("未找到下载的音频文件")
    return files[0], os.path.splitext(files[0])[0].split("audio_")[-1]


# ─────────────────────────── 本地文件 ───────────────────────────

def fetch_local(path):
    name = os.path.splitext(os.path.basename(path))[0]
    # 已有 audio_ 前缀则不重复添加
    if name.startswith("audio_"):
        name = name[6:]
    return path, name


# ───────────────────────────── 主流程 ─────────────────────────────

def to_wav(src, outdir, name):
    """转16k 单声道 WAV。"""
    wav_path = os.path.join(outdir, f"audio_{name}.wav")
    if src.endswith(".wav") and os.path.abspath(src) == os.path.abspath(wav_path):
        return wav_path
    ffmpeg = find_ffmpeg()
    print(f"[转换] {os.path.basename(wav_path)} (16kHz mono)")
    subprocess.run(
        [ffmpeg, "-y", "-i", src, "-ar", "16000", "-ac", "1", "-vn", wav_path],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return wav_path


def main():
    ap = argparse.ArgumentParser(description="下载音频并转 WAV（支持 B站/小红书/通用平台）")
    ap.add_argument("target", help="BV号 / 视频链接 / 本地文件路径")
    ap.add_argument("-o", "--outdir", default=os.getcwd(), help="输出目录")
    ap.add_argument("-p", "--page", type=int, default=1, help="分P 序号（B站，从 1 开始）")
    ap.add_argument("--platform", default="auto",
                    choices=["auto", "bilibili", "xiaohongshu", "generic", "local"],
                    help="平台类型，默认 auto 自动判断")
    ap.add_argument("--keep-src", action="store_true", help="保留中间音频文件")
    ap.add_argument("--wav-only", action="store_true", help="只做 WAV 转换")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    platform = detect_platform(args.target) if args.platform == "auto" else args.platform
    print(f"[平台]  {platform}\n")

    if args.wav_only:
        src, name = args.target, extract_bvid(args.target)
    elif platform == "bilibili":
        src, name = fetch_bilibili(args.target, args.outdir, args.page)
    elif platform == "local":
        if not os.path.isfile(args.target):
            raise SystemExit(f"找不到本地文件：{args.target}")
        src, name = fetch_local(args.target)
    else:
        src, name = fetch_ytdlp(args.target, args.outdir, platform)

    wav_path = to_wav(src, args.outdir, name)

    if not args.keep_src and src != args.target and os.path.exists(src):
        try:
            os.remove(src)
        except OSError:
            pass

    size = os.path.getsize(wav_path) / 1024 / 1024
    print(f"        {round(size,2)} MB")

    print("\n" + "=" * 56)
    print("下一步 —— 运行 ASR：")
    print(f'  python transcribe.py "{wav_path}" -n "标题" --prompt "题材描述"')
    print(f"  预估耗时 ≈ {round(size*0.6)} 分钟（small/int8/cpu）")
    print("=" * 56)
    print(wav_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
