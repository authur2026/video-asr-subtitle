#!/usr/bin/env python3
"""严格校验 SRT 格式合法性。退出码 0 = 通过，1 = 有问题。

用法：
    python validate_srt.py subtitle.srt

检查项：
- 序号从 1 连续递增
- 时间轴格式 HH:MM:SS,mmm --> HH:MM:SS,mmm
- 结束时间 > 开始时间（无倒置）
- 无重叠（start不早于上一条的 end）
- 最短显示时长
"""
import re
import sys

LINE_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> "
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3})$"
)


def to_sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def validate(path, min_dur=0.1, overlap_tol=0.002):
    raw = open(path, encoding="utf-8").read()
    blocks = [b for b in re.split(r"\n\s*\n", raw.strip()) if b.strip()]
    errors, warnings = [], []
    prev_end = 0.0

    for i, b in enumerate(blocks, 1):
        lines = b.split("\n")
        if len(lines) < 3:
            errors.append(f"#{i} 结构不完整（少于3行）：{lines[0]!r}")
            continue
        try:
            if int(lines[0]) != i:
                errors.append(f"#{i} 序号错误，实际为 {lines[0]}")
        except ValueError:
            errors.append(f"#{i} 序号非数字：{lines[0]!r}")
            continue

        m = LINE_RE.match(lines[1])
        if not m:
            errors.append(f"#{i} 时间轴格式错误：{lines[1]!r}")
            continue

        st = to_sec(*m.group(1, 2, 3, 4))
        en = to_sec(*m.group(5, 6, 7, 8))

        if en <= st:
            errors.append(f"#{i} 时间倒置：{lines[1]}")
        if st < prev_end - overlap_tol:
            errors.append(f"#{i} 与上条重叠 {round(prev_end - st, 3)}s"
                          f"（start={round(st,3)} < prev_end={round(prev_end,3)}）")
        if en - st < min_dur:
            warnings.append(f"#{i} 显示过短 {round(en - st, 3)}s")
        prev_end = en

    print(f"文件：{path}")
    print(f"条目：{len(blocks)}")
    if errors:
        print(f"\n错误 {len(errors)} 处：")
        for e in errors[:30]:
            print("  " + e)
        if len(errors) > 30:
            print(f"  ... 另有 {len(errors)-30} 处")
    if warnings:
        print(f"\n警告 {len(warnings)} 处：")
        for w in warnings[:10]:
            print("  " + w)
    if not errors:
        print("\n[OK] SRT 格式完全合法")
    return 1 if errors else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a not in ("-h", "--help")]
    if not args or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] else 2)
    sys.exit(validate(args[0]))
