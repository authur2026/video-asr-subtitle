#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""环境体检 —— 检查 skill 的全部运行时依赖，并给出可执行的修复建议。

用法：
    python scripts/doctor.py           # 完整检查
    python scripts/doctor.py --json    # 机器可读输出

退出码：0 = 核心依赖齐全；1 = 有缺失
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

OK, WARN, MISS = "OK", "WARN", "MISS"


def check_python():
    v = sys.version_info
    if v < (3, 8):
        return MISS, f"Python {v.major}.{v.minor}", "需要 Python 3.8+"
    return OK, f"Python {v.major}.{v.minor}.{v.micro}", None


def check_module(name, pkg=None, purpose=""):
    try:
        __import__(name)
        ver = ""
        if pkg:
            try:
                ver = f" {pkg.__version__}"
            except AttributeError:
                pass
        return OK, f"{name}{ver}", None
    except ImportError:
        return MISS, f"{name} 未安装", f"pip install {pkg and _dist_name(name) or name}" + (
            f"   # {purpose}" if purpose else "")


def _dist_name(mod):
    return {"PIL": "Pillow", "cv2": "opencv-python", "sklearn": "scikit-learn",
            "yaml": "PyYAML"}.get(mod, mod)


def check_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        try:
            r = subprocess.run([p, "-version"], capture_output=True, text=True, timeout=10)
            line = (r.stdout or "").split("\n")[0]
            return OK, f"ffmpeg  {line[:52]}", None
        except (OSError, subprocess.SubprocessError):
            return WARN, f"ffmpeg  {p}", "无法执行版本查询，请手动确认可用"
    for base in (os.path.expanduser("~/.local/bin"), "/opt/homebrew/bin",
                 "/usr/local/bin", "/usr/bin", r"C:\ffmpeg\bin"):
        cand = os.path.join(base, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if os.path.exists(cand):
            return WARN, f"ffmpeg  {cand}", \
                "不在 PATH 中，已按常见位置找到。建议加入 PATH 以免其他工具报错"
    return MISS, "ffmpeg 未找到", (
        "Windows: winget install Gyan.FFmpeg\n"
        "  macOS:   brew install ffmpeg\n"
        "  Linux:   sudo apt install ffmpeg")


def check_whisper_model():
    """检查 faster-whisper 模型是否已缓存（决定要不要设 HF_HUB_OFFLINE）。"""
    roots = [
        os.environ.get("HF_HUB_CACHE"),
        os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
    ]
    for r in roots:
        if not r or not os.path.isdir(r):
            continue
        for d in os.listdir(r):
            if d.startswith("models--Systran--faster-whisper"):
                return OK, f"模型已缓存  {d}", None
    if os.environ.get("HF_HUB_OFFLINE") == "1":
        return MISS, "未找到缓存模型但 HF_HUB_OFFLINE=1", \
            "离线模式会导致模型加载失败。请先 unset HF_HUB_OFFLINE 联网跑一次"
    return WARN, "模型未缓存", "首次运行会联网下载（约 500MB）。若网络受限，缓存后可设 HF_HUB_OFFLINE=1"


def check_node():
    p = shutil.which("node")
    if not p:
        return WARN, "Node.js 未找到", "仅 PDF 阶段需要：https://nodejs.org"
    try:
        r = subprocess.run([p, "-v"], capture_output=True, text=True, timeout=10)
        return OK, f"Node.js{r.stdout.strip()}", None
    except (OSError, subprocess.SubprocessError):
        return WARN, f"Node.js  {p}", "无法查询版本"


def check_playwright():
    """定位 playwright-core；找不到就给出 PW_CORE 指引。"""
    cands = [
        os.environ.get("PW_CORE"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "node_modules", "playwright-core"),
        os.path.join(os.getcwd(), "node_modules", "playwright-core"),
        os.path.join(process_npm_prefix(), "playwright-core"),
        "/usr/local/lib/node_modules/playwright-core",
        "/opt/homebrew/lib/node_modules/playwright-core",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return OK, f"playwright-core  {c}", None
    try:
        subprocess.run(["npm", "ls", "-g", "playwright-core"],
                       capture_output=True, timeout=20)
        import importlib
        r = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            g = os.path.join(r.stdout.strip(), "playwright-core")
            if os.path.exists(g):
                return OK, f"playwright-core  {g}", None
    except (OSError, subprocess.SubprocessError, ImportError):
        pass
    return MISS, "playwright-core 未找到", (
        "npm i playwright-core && npx playwright install chromium\n"
        "  或设 PW_CORE 环境变量指向已安装目录")


def process_npm_prefix():
    if os.name == "nt":
        return os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules")
    return "/usr/local/lib/node_modules"


def check_chromium():
    """按平台推断缓存目录并验证有可执行文件。"""
    if os.environ.get("PW_BROWSERS"):
        base = os.environ["PW_BROWSERS"]
    elif os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
    else:
        base = os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")
    if not os.path.isdir(base):
        return WARN, f"chromium 缓存目录不存在  {base}", "运行 npx playwright install chromium"
    sub = [d for d in os.listdir(base) if d.startswith("chromium")]
    if not sub:
        return WARN, f"{base} 下无 chromium", "运行 npx playwright install chromium"
    return OK, f"chromium  {base}/{sorted(sub)[-1]}", None


def main():
    ap = argparse.ArgumentParser(description="video-asr-subtitle 环境体检")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    results = []
    st, name, fix = check_python(); results.append(("python", st, name, fix))
    for mod, purpose in (("requests", "下载音频"), ("faster_whisper", "ASR 转写"),
                         ("yt_dlp", "小红书/通用平台"), ("PIL", "裁水印")):
        st, name, fix = check_module(mod, purpose=purpose)
        results.append((mod, st, name, fix))
    st, name, fix = check_ffmpeg();       results.append(("ffmpeg", st, name, fix))
    st, name, fix = check_whisper_model(); results.append(("whisper_model", st, name, fix))
    st, name, fix = check_node();         results.append(("node", st, name, fix))
    st, name, fix = check_playwright();   results.append(("playwright", st, name, fix))
    st, name, fix = check_chromium();     results.append(("chromium", st, name, fix))

    if args.json:
        print(json.dumps([{"name": n, "status": s, "detail": d, "fix": f}
                          for n, s, d, f in results], ensure_ascii=False, indent=2))
    else:
        icon = {OK: "[ OK ]", WARN: "[WARN]", MISS: "[MISS]"}
        print("=" * 66)
        print("video-asr-subtitle 环境体检")
        print("=" * 66)
        for n, s, d, f in results:
            print(f"{icon[s]} {n:15} {d}")
            if s != OK and f:
                for line in f.split("\n"):
                    print(f"                → {line}")
        print("=" * 66)
        core_miss = [n for n, s, _, _ in results
                     if s == MISS and n not in ("node", "playwright", "chromium")]
        if core_miss:
            print(f"\n核心依赖缺失：{', '.join(core_miss)}\n核心流程（字幕提取）无法运行，请先安装。")
        else:
            print("\n核心依赖齐全，字幕提取流程可运行。")
        warns = [n for n, s, _, _ in results if s == WARN]
        if warns:
            print(f"提示：{', '.join(warns)} 需要关注（不影响核心流程）。")

    return 1 if any(s == MISS and n not in ("node", "playwright", "chromium")
                    for n, s, _, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())