# -*- coding: utf-8 -*-
"""精校配置模板 —— 复制一份改名为<视频>_config.py 后填写。

三步：
1. 跑 fetch_audio.py + transcribe.py，拿到 _转写_*.txt / .srt
2. 通读全文找出：错字、重复幻觉段、不可用的音译段
3. 把路径填好，REPLACE 补该片专属规则，REWRITE 处理乱码段，RANGES 修代词
"""
import os

# ── 基本信息 ──
# 工作目录：改成你自己的路径。也可用环境变量 ASR_BASE 覆盖
BASE = os.environ.get("ASR_BASE") or os.path.expanduser("~/video-asr-output")
NAME = os.path.join(BASE, "视频标题")    # 完整输出前缀（改这里）

# ── 路径 ──
SRC_TXT = NAME + "_转写_纯文本.txt"
SRC_TS = NAME + "_转写_带时间戳.txt"
SRC_SRT = NAME + "_转写.srt"
OUT_TXT = NAME + "_精校.txt"
OUT_TS = NAME + "_精校_带时间戳.txt"
OUT_SRT = NAME + "_精校.srt"

# ── 替换表：[ASR错字, 正确字] ──
# 先从 references/replace_library.py 拷对应题材的分组，再补本片专属：
#
#   from replace_library import build
#   REPLACE = build("inspiring") + [ ...本片专属... ]
#
# 方向必须是「错 → 对」。注意别误伤：
#   "挪威老" 是人名绰号，不是错字
#   同音字在不同语境可能对应不同词
REPLACE = [
    ("海豹", "滑雪板"),
    ("憋弃", "憋气"),
    ("敢忙", "赶紧"),
    # ... 本片专属
]

# ── 整段重写：[(起秒, 止秒, [重写后的句子列表]), ...] ──
# 仅用于英文演讲 / 音译乱码等替换表修不了的段落。
# 时间轴会在 [起秒, 止秒] 区间内按句子数均分。
# REWRITE = []

# ── 代词性别区间（仅当视频含大量「她/他」误用时才需要） ──
# MALE_RANGES：这些区间内「她」是误用 → 改成「他」
# FEMALE_RANGES：这些区间内「她」是正确的 → 保留（优先级高于 MALE）
# 排查方法：精校后 grep 所有含「她」的行，逐条核对语境
#
# MALE_RANGES = [(524.0, 772.0)]
# FEMALE_RANGES = [(478.0, 505.0), (770.0, 800.0)]
