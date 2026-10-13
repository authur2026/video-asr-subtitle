#!/usr/bin/env python3
"""把 book.json 渲染成故事画册 HTML（无需模板引擎）。

用法：
    python build_book.py book.json -o 画册.html
    python build_book.py book.json -o 画册.html --css 自定义.css

book.json 结构见 references/book_schema.md。
图片路径建议用 file:/// 绝对路径，chromium 能正常加载。
"""
import argparse
import html
import json
import os
import sys

CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "book.css")

DEFAULT_META = "{subtitle}\n{title} · 视频解说文案\n\n文字整理自 B站 视频字幕\n出品年份 · {year}"

DEFAULT_COLOPHON = """<p>本册文字整理自 B站 视频字幕，由语音识别后经人工精校而成。</p>
<p>文中插图为 AI 生成，仅作意境示意。</p>
<p>—— 完——</p>"""


def esc(s):
    return html.escape(str(s), quote=False)


def to_file_url(path):
    """把本地路径转成 file:/// URL。"""
    if not path:
        return ""
    p = str(path).replace("\\", "/")
    if p.startswith("file://"):
        return p
    if os.path.isabs(p):
        return "file:///" + p.lstrip("/")
    # 相对路径：相对于 cwd
    absp = os.path.abspath(p).replace("\\", "/")
    return "file:///" + absp.lstrip("/")


def render(data):
    parts = ['<!DOCTYPE html>', '<html lang="zh-CN">', '<head>',
             '<meta charset="utf-8">',
             f'<title>{esc(data.get("title", ""))}</title>', '<style>']

    with open(data.get("css_path", CSS_PATH), encoding="utf-8") as f:
        parts.append(f.read())
    parts.append('</style></head><body>')

    # —— 封面 ——
    parts.append('<section class="cover">')
    if data.get("cover_image"):
        parts.append(f'<img class="cover-art" src="{esc(to_file_url(data["cover_image"]))}" alt="">')
    parts.append(f'<h1>{esc(data.get("title", ""))}</h1>')
    if data.get("subtitle"):
        parts.append(f'<div class="subtitle">{esc(data["subtitle"])}</div>')
    meta = data.get("meta") or DEFAULT_META.format(
        subtitle=esc(data.get("subtitle", "")),
        title=esc(data.get("title", "")),
        year=data.get("year", ""),
    )
    parts.append(f'<div class="meta">{meta}</div>')
    parts.append('</section>')

    # —— 章节 ——
    for ch in data.get("chapters", []):
        # chapter_break=true 时强制另起一页（全局开关或单章指定）
        brk = data.get("chapter_break") or ch.get("break")
        cls = "chapter chapter-break" if brk else "chapter"
        parts.append(f'<section class="{cls}">')
        if ch.get("num"):
            parts.append(f'<div class="chapter-num">{esc(ch["num"])}</div>')
        parts.append(f'<h2>{esc(ch.get("title", ""))}</h2>')

        if ch.get("image"):
            parts.append('<figure class="illustration">')
            parts.append(f'<img src="{esc(to_file_url(ch["image"]))}" alt="">')
            if ch.get("image_caption"):
                parts.append(f'<figcaption>{esc(ch["image_caption"])}</figcaption>')
            parts.append('</figure>')

        for i, para in enumerate(ch.get("paragraphs", [])):
            cls = ' class="first"' if i == 0 else ''
            parts.append(f'<p{cls}>{esc(para)}</p>')

        if ch.get("side_image"):
            parts.append('<div class="illustration-side">')
            parts.append(f'<img src="{esc(to_file_url(ch["side_image"]))}" alt="">')
            parts.append('<div class="text">')
            for p in ch.get("side_paragraphs", []):
                parts.append(f'<p>{esc(p)}</p>')
            parts.append('</div></div>')

        pq = ch.get("pull_quote")
        if pq:
            parts.append('<blockquote class="pull-quote">')
            parts.append(esc(pq.get("text", "")))
            if pq.get("source"):
                parts.append(f'<span class="source">{esc(pq["source"])}</span>')
            parts.append('</blockquote>')

        if ch.get("facts"):
            parts.append('<dl class="fact">')
            for f in ch["facts"]:
                parts.append(f'<dt>{esc(f.get("label", ""))}</dt>')
                parts.append(f'<dd>{esc(f.get("text", ""))}</dd>')
            parts.append('</dl>')

        parts.append('</section>')

    # —— 结尾 ——
    colophon = data.get("colophon", DEFAULT_COLOPHON)
    parts.append(f'<section class="colophon">{colophon}</section>')

    parts.append('</body></html>')
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description="book.json → 画册 HTML")
    ap.add_argument("json_file", help="book.json 路径")
    ap.add_argument("-o", "--output", required=True, help="输出 HTML 路径")
    ap.add_argument("--css", default=None, help="自定义 CSS（默认用 assets/book.css）")
    args = ap.parse_args()

    with open(args.json_file, encoding="utf-8") as f:
        data = json.load(f)
    if args.css:
        data["css_path"] = args.css

    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(data))

    chapters = len(data.get("chapters", []))
    paras = sum(len(c.get("paragraphs", [])) for c in data.get("chapters", []))
    imgs = sum(1 for c in data.get("chapters", []) if c.get("image")) \
        + sum(1 for c in data.get("chapters", []) if c.get("side_image")) \
        + (1 if data.get("cover_image") else 0)
    print(f"HTML 完成: {out}")
    print(f"  章节 {chapters} 个 / 段落 {paras} 段 / 插图引用 {imgs} 张")
    print("\n下一步：node scripts/html2pdf.js "
          f'"{out}" "{os.path.splitext(out)[0]}.pdf" A4')
    return 0


if __name__ == "__main__":
    sys.exit(main())
