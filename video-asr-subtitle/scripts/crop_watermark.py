#!/usr/bin/env python3
"""裁掉AI 生成图右下角的水印区域，并重命名为语义化文件名。

AI 生成的图右下角常带"AI生成"水印，在 PDF 里很扎眼。
本脚本按比例裁掉右下角一块区域，再重命名。

用法：
    python crop_watermark.py book_images/            # 处理目录下所有图
    python crop_watermark.py book_images/ --keep 0.06
"""
import argparse
import os

try:
    from PIL import Image
except ImportError:
    raise SystemExit(
        "缺少 Pillow。安装：\n"
        "  python -m pip install Pillow"
    )

# 语义化命名：(关键词匹配, 输出文件名)
RENAMES = [
    ("A_lone_Malaysian", "cover.png"),
    ("A_young_boy", "ch1_球拍墙.png"),
    ("A_dim_underground", "ch2_地下赌场.png"),
    ("An_empty_indoor", "ch3_空荡训练馆.png"),
    ("Two_badminton_players", "ch4_宿敌.png"),
    ("A_badminton_player_alone", "ch5_一个人的赛场.png"),
]


def crop_watermark(src, dst, keep_ratio=0.055):
    """裁掉右下角 keep_ratio 比例的区域（宽、高各占）。"""
    im = Image.open(src)
    w, h = im.size
    dx = int(w * keep_ratio)
    dy = int(h * keep_ratio)
    # 保留 96% 宽高
    im.crop((0, 0, w - dx, h - dy)).save(dst, quality=95)
    return im.size, (w - dx, h - dy)


def main():
    ap = argparse.ArgumentParser(description="裁掉AI水印并重命名")
    ap.add_argument("dir", help="图片目录")
    ap.add_argument("--keep", type=float, default=0.055,
                    help="裁掉的边距比例（默认 0.055）")
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(".png"))
    print(f"发现 {len(files)} 张图\n")

    for f in files:
        src = os.path.join(args.dir, f)
        # 匹配语义名
        out_name = None
        for key, name in RENAMES:
            if key in f:
                out_name = name
                break
        dst = os.path.join(args.dir, out_name or f)

        orig, new = crop_watermark(src, dst, args.keep)
        action = f"→ {out_name}" if out_name else "（保持原名）"
        print(f"  {f[:46]:48} {action}")
        print(f"      {orig[0]}×{orig[1]} → {new[0]}×{new[1]}")

        # 原图（非重命名的）删除
        if dst != src:
            os.remove(src)

    print("\n完成。水印已裁除，可用于排版。")


if __name__ == "__main__":
    main()
