#!/usr/bin/env python3
"""ASR 转写精校引擎：修正错字、清理幻觉、重写不可用段落、保证字幕格式合法。

设计为配置驱动—— 复制一份 config.py 填写规则，本脚本负责通用逻辑。

用法：
    python clean_subtitle.py --config my_video.py
    python clean_subtitle.py --config my_video.py --dry-run   # 只报告不写文件

config.py 需提供：
    NAME        输出文件名前缀
    SRC_TXT / SRC_TS / SRC_SRT   原始文件路径
    OUT_TXT / OUT_TS / OUT_SRT   输出路径
    REPLACE=[(错, 对), ...]                字符串替换表
    REWRITE=[(起秒, 止秒, [重写句子...]), ...]  整段重写（英文演讲/音译乱码）
    MALE_RANGES=[(起,止), ...]   这些区间内把「她」改「他」
    FEMALE_RANGES=[(起,止), ...]  这些区间内保留「她」（优先级更高）
"""
import argparse
import importlib.util
import os
import re
import sys

TS_RE = re.compile(r"^\[(\d+\.\d+)-(\d+\.\d+)\]\s*(.*)$")


def load_config(path):
    spec = importlib.util.spec_from_file_location("cfg", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_ts(path):
    """读取带时间戳文件 → [(start, end, text), ...]"""
    items = []
    for line in open(path, encoding="utf-8").read().rstrip("\n").split("\n"):
        m = TS_RE.match(line)
        if m:
            items.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return items


def dedupe(items, min_len=2, hot_threshold=4, window=80):
    """删除重复幻觉行。

    三层：
    1) 连续重复 —— 同一段话循环 2-N 遍（最常见）
    2) 全局高频重复 —— 同一短句在全文反复出现（如 31x「Roger that」）。
       出现次数 > hot_threshold 且在附近窗口内已出现过 → 判为幻觉删除。
    3) 连续同短句成块 —— 2 个以上相同的短句（如 5x「这些人」）。
       min_len 须含短句，纯过滤词（「这些人」）重复即属幻觉。

    注意：min_len 不能设太大，否则「这些人」这类 3 字幻觉会漏网。
    """
    import collections

    counter = collections.Counter(
        b.strip() for _, _, b in items if len(b.strip()) >= min_len
    )
    hot = {t for t, n in counter.items() if n > hot_threshold}

    out, prev = [], None
    recent = []
    for s, e, b in items:
        text = b.strip()
        if text == prev and len(text) >= min_len:
            continue                      # 层1：连续重复
        if text in hot and text in recent:
            continue                      # 层2：高频且近期出现过
        out.append((s, e, b))
        prev = text
        recent.append(text)
        if len(recent) > window:
            recent.pop(0)
    return out


def detect_traditional(text):
    """检测繁体字残留（whisper 偶发输出繁体，需统一为简体）。"""
    mapping = "凱薩蘭麗亞歐華爾費觀學國會時們這個來後發關點動務體實戰樣顯認說話頭臉門問開東馬鳥魚龍"
    return {ch for ch in text if ch in mapping}


def in_ranges(ts, ranges):
    return any(a <= ts <= b for a, b in (ranges or []))


def fix_pronoun(ts, text, male, female):
    """按时间区间判定性别：ASR 小模型分不出性别，只能用时间轴当上下文锚点。"""
    if in_ranges(ts, female):
        return text
    if in_ranges(ts, male):
        if "母亲" in text:
            return text
        return text.replace("她", "他")
    return text


def apply_rewrite(items, rewrite_spec):
    """按时间区间整段重写（如英文演讲被识别为乱码时）。"""
    if not rewrite_spec:
        return items
    out, i = [], 0
    while i < len(items):
        ts = items[i][0]
        hit = next((r for r in rewrite_spec if r[0] <= ts <= r[1]), None)
        if not hit:
            out.append(items[i])
            i += 1
            continue
        t0, t1, content = hit
        end_time, j = t1, i
        while j < len(items) and t0 <= items[j][0] <= t1:
            end_time = max(end_time, items[j][1])
            j += 1
        i = j
        n = len(content)
        span = (end_time - t0) / n
        for k, sent in enumerate(content):
            out.append((t0 + k * span, t0 + (k + 1) * span, sent))
    return out


def enforce_monotonic(items, min_dur=0.4):
    """消除时间轴重叠—— 重写段与前后行常有 0.2s 级残留，播放器上表现为字幕闪跳。"""
    out, prev_end = [], 0.0
    for s, e, b in items:
        if s < prev_end:
            s = prev_end
        if e < s + min_dur:
            e = s + min_dur
        out.append((s, e, b))
        prev_end = e
    return out


def apply_replace(text, table):
    for a, b in (table or []):
        text = text.replace(a, b)
    return text


def srt_time(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser(description="ASR 字幕精校引擎")
    ap.add_argument("--config", required=True, help="配置文件路径")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    args = ap.parse_args()

    cfg = load_config(args.config)
    name = cfg.NAME

    items = parse_ts(cfg.SRC_TS)
    n0 = len(items)

    items = dedupe(items)
    n1 = len(items)

    items = apply_rewrite(items, getattr(cfg, "REWRITE", None))
    n2 = len(items)

    male = getattr(cfg, "MALE_RANGES", None)
    female = getattr(cfg, "FEMALE_RANGES", None)
    processed = []
    for s, e, b in items:
        body = apply_replace(b, getattr(cfg, "REPLACE", None))
        body = fix_pronoun(s, body, male, female)
        processed.append((s, e, body))

    processed = enforce_monotonic(processed)

    print(f"精校统计：{n0} 行 → 去重 {n1} → 重写 {n2} → 输出 {len(processed)}")
    if n0 - n1:
        print(f"  删除重复幻觉 {n0 - n1} 行")
    if getattr(cfg, "REWRITE", None):
        print(f"  重写段落 {len(cfg.REWRITE)} 处")

    # 残留错字自检
    # 只检查「错字」且未被其他规则的「正确字」覆盖的情况。
    # 例：REPLACE 里有 ("林丹","林丹") 这类占位，或某词的正确字恰好等于另一条的错字。
    correct_targets = {b for _, b in (getattr(cfg, "REPLACE", None) or [])}
    remain = {}
    all_text = "".join(b for _, _, b in processed)
    for a, b in (getattr(cfg, "REPLACE", None) or []):
        if a == b or b in correct_targets:
            continue          # 恒等替换或目标字被别的规则覆盖，不算残留
        c = all_text.count(a)
        if c:
            remain[a] = c
    if remain:
        print("\n[!] 替换后仍残留（可能是误伤，也可能是漏网）：")
        for k, v in sorted(remain.items(), key=lambda x: -x[1])[:15]:
            print(f"  {v}x  {k}")

    # 繁体残留自检
    trad = detect_traditional(all_text)
    if trad:
        print(f"\n[!] 检测到繁体字残留：{''.join(sorted(trad))}")
        print("    → 建议在 REPLACE 中加入对应简体字，或从 replace_library.EXTRA 导入繁简表")

    if args.dry_run:
        print("\n[dry-run] 未写入文件")
        return 0

    with open(cfg.OUT_TS, "w", encoding="utf-8") as f:
        f.write("\n".join(f"[{s:06.1f}-{e:06.1f}] {b}" for s, e, b in processed))
    with open(cfg.OUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(b for _, _, b in processed))
    with open(cfg.OUT_SRT, "w", encoding="utf-8") as f:
        f.write("\n\n".join(
            f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{b}"
            for i, (s, e, b) in enumerate(processed, 1)
        ) + "\n")

    print(f"\n[done] {name}")
    for p in (cfg.OUT_TXT, cfg.OUT_TS, cfg.OUT_SRT):
        print(f"  {p}")
    print(f"\n下一步校验：python validate_srt.py \"{cfg.OUT_SRT}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
