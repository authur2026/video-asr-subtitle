#!/usr/bin/env python3
"""用 faster-whisper 把 WAV 转成带时间戳的文本 + SRT 字幕。

用法：
    python transcribe.py audio_BV1xxx.wav --name 视频标题
    python transcribe.py audio.wav --name 标题 --prompt "关于马来西亚羽毛球运动员李宗伟的励志故事"

关键点：
- initial_prompt 写明人物与领域，可显著提升专名/术语准确率（实测有效）
- 模型已缓存时可设 HF_HUB_OFFLINE=1 走离线（避免代理环境下 HF 官方源502）；
  本脚本不强制设置，由调用方通过环境变量决定
"""
import argparse
import os
import re
import sys

# 已缓存模型的用户可 export HF_HUB_OFFLINE=1 走完全离线。
# 未缓存时若强制离线会导致模型加载失败，因此这里不默认开启。
if os.environ.get("ASR_FORCE_OFFLINE") == "1":
    os.environ["HF_HUB_OFFLINE"] = "1"


def check_dup(path):
    """检测 whisper 重复幻觉：连续相同行 + 全文高频重复行。"""
    import collections

    lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
    cores = [re.sub(r"^\[\d+\.\d+-\d+\.\d+\]\s*", "", x).strip() for x in lines]

    run, worst, worst_pos = 1, 1, -1
    for i in range(1, len(cores)):
        if cores[i] == cores[i - 1]:
            run += 1
            if run > worst:
                worst, worst_pos = run, i
        else:
            run = 1

    counter = collections.Counter(c for c in cores if len(c) >= 5)
    dups = [(t, n) for t, n in counter.most_common(20) if n > 1]

    print(f"总行数 {len(lines)}")
    if worst > 1:
        print(f"\n[!] 检测到连续重复 {worst} 次（位置 {worst_pos}）：{cores[worst_pos]}")
        print("    → 精校时必须整段删除，否则字幕会出现循环幻觉")
    else:
        print("\n[OK] 无连续重复幻觉")
    if dups:
        print(f"\n全文重复出现的行（共 {len(dups)} 条，重复多为口语连接词属正常）：")
        for t, n in dups:
            print(f"  {n}x  {t}")
    return worst


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser(description="WAV → 文本 + SRT")
    ap.add_argument("wav", nargs="?", help="16k单声道 WAV 路径")
    ap.add_argument("-n", "--name", help="输出文件名前缀（用视频标题）")
    ap.add_argument("-o", "--outdir", default=None, help="输出目录，默认与 wav 同目录")
    ap.add_argument("--prompt", default="", help="initial_prompt：题材/人物/领域描述")
    ap.add_argument("--model", default="small", help="small / medium / large-v3")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--check-dup", metavar="TS_FILE", help="仅检测指定带时间戳文件的重复幻觉")
    args = ap.parse_args()

    if args.check_dup:
        return 0 if check_dup(args.check_dup) == 1 else 1

    if not args.wav or not args.name:
        ap.error("需要 wav 路径与 --name（或使用 --check-dup）")

    wav = os.path.abspath(args.wav)
    if not os.path.exists(wav):
        raise SystemExit(f"找不到 {wav}")
    outdir = args.outdir or os.path.dirname(wav)
    os.makedirs(outdir, exist_ok=True)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "缺少 faster-whisper。安装：\n"
            "  python -m pip install faster-whisper"
        )

    print(f"[model] {args.model} / int8 / cpu")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    print("[asr]   转写中…（后台运行，约需 音频时长 × 0.44 分钟）", flush=True)
    kwargs = dict(language=args.language, beam_size=5, vad_filter=True)
    if args.prompt:
        kwargs["initial_prompt"] = args.prompt
    segments, info = model.transcribe(wav, **kwargs)
    print(f"[lang]  {info.language} ({info.language_probability:.2f})", flush=True)

    lines, ts_lines, srt_blocks = [], [], []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        lines.append(text)
        ts_lines.append(f"[{seg.start:06.1f}-{seg.end:06.1f}] {text}")
        srt_blocks.append(
            f"{len(srt_blocks)+1}\n{srt_time(seg.start)} --> {srt_time(seg.end)}\n{text}\n"
        )

    base = os.path.join(outdir, args.name)
    paths = {
        "纯文本": base + "_转写_纯文本.txt",
        "带时间戳": base + "_转写_带时间戳.txt",
        "SRT": base + "_转写.srt",
    }
    with open(paths["纯文本"], "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(paths["带时间戳"], "w", encoding="utf-8") as f:
        f.write("\n".join(ts_lines))
    with open(paths["SRT"], "w", encoding="utf-8") as f:
        f.write("\n".join(srt_blocks))

    print(f"\n[done]  {len(ts_lines)} 段/ {sum(len(l) for l in lines)} 字")
    for k, v in paths.items():
        print(f"  {k:8} {v}")

    #幻觉检测提示
    print("\n[提示] 精校前先查重复幻觉：")
    print(f'  python {os.path.basename(__file__)} --check-dup "{paths["带时间戳"]}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
