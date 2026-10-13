#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video-asr-subtitle skill 通用安装器。

自动探测本机已安装的 AI 工具，把skill 装到对应目录，并建立软链接/副本。

用法：
    python install.py                # 自动探测 + 安装到所有检测到的工具
    python install.py --list         # 只列出检测结果，不安装
    python install.py --target claude --target cursor
    python install.py --project .    # 装到当前项目（.claude/skills/ 等）
    python install.py --link         # 用软链接代替复制（便于后续更新）

支持的目标：
    claude    Claude Code / Claude Desktop  → ~/.claude/skills/
    cursor    Cursor                       → ~/.cursor/skills/
    codex     OpenAI Codex                 → ~/.codex/skills/
    agents    通用 agents目录              → ~/.agents/skills/
    gemini    Gemini CLI                   → ~/.gemini/skills/
    windsurf  Windsurf                     → ~/.codeium/windsurf/skills/
    project   当前项目                     → ./.claude/skills/ 等

装完后重启对应工具的会话即可让Agent 发现该 skill。
"""
import argparse
import os
import shutil
import subprocess
import sys

SKILL_NAME = "video-asr-subtitle"
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), SKILL_NAME)


# 目标定义：(名称, 用户级相对路径, 项目级相对路径, 项目级 .mdc 路径或 None)
TARGETS = [
    ("claude",   "~/.claude/skills",       ".claude/skills",       None),
    ("cursor",   "~/.cursor/skills",       ".cursor/skills",       None),
    ("codex",    "~/.codex/skills",        ".codex/skills",        None),
    ("agents",   "~/.agents/skills",       ".agents/skills",       None),
    ("gemini",   "~/.gemini/skills",       ".gemini/skills",       None),
    ("windsurf", "~/.codeium/windsurf/skills", ".windsurf/skills", ".cursor/rules/video-asr-subtitle.mdc"),
]


def is_windows():
    return os.name == "nt"


def symlink(src, dst):
    """尽量用软链接；Windows 无权限时退回复制。"""
    try:
        if is_windows():
            # Windows 需要管理员或开发者模式才能建目录联接
            r = subprocess.run(
                ["cmd", "/c", "mklink", "/J", os.path.abspath(dst), os.path.abspath(src)],
                capture_output=True,          # 不用 text=True：cmd 输出是本地编码，解码会抛异常
            )
            if r.returncode == 0:
                return "symlink"
        else:
            os.symlink(os.path.abspath(src), os.path.abspath(dst), target_is_directory=True)
            return "symlink"
    except (OSError, subprocess.SubprocessError):
        pass
    # 退回复制
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return "copy"


def install_to(base_dir, project=False):
    """把 skill 装到 base_dir 下的 <base>/<SKILL_NAME>。"""
    target = os.path.join(os.path.abspath(os.path.expanduser(base_dir)), SKILL_NAME)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    mode = symlink(SRC, target)
    return target, mode


def install_mdc(src_text, path):
    """Cursor 项目级 .mdc 规则文件。"""
    dst = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"description: 视频 ASR 字幕提取与图文画册生成流程\n")
        f.write("alwaysApply: false\n")
        f.write("---\n\n")
        f.write(src_text)
    return dst


def probe():
    """检测各工具的安装痕迹。"""
    home = os.path.expanduser("~")
    markers = {
        "claude":   ["~/.claude", "~/.claude.json"],
        "cursor":   ["~/.cursor", "~/AppData/Roaming/Cursor"],
        "codex":    ["~/.codex"],
        "agents":   ["~/.agents"],
        "gemini":   ["~/.gemini"],
        "windsurf": ["~/.codeium", "~/AppData/Roaming/Windsurf"],
    }
    found = []
    for name, paths in markers.items():
        hit = next((p for p in paths if os.path.exists(os.path.expanduser(p))), None)
        found.append((name, hit))
    return found


def main():
    ap = argparse.ArgumentParser(description="安装 video-asr-subtitle skill 到本机 AI 工具")
    ap.add_argument("--list", action="store_true", help="只列出检测结果")
    ap.add_argument("--target", action="append", help="指定目标（可重复），如 claude / cursor")
    ap.add_argument("--project", metavar="DIR", help="装到指定项目目录（默认当前目录用 --project .）")
    ap.add_argument("--user", action="store_true", help="强制装到用户级目录（默认行为）")
    ap.add_argument("--link", action="store_true", help="用链接代替复制（便于本仓库更新后自动生效）")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        raise SystemExit(f"找不到 skill 源目录：{SRC}")
    if not os.path.exists(os.path.join(SRC, "SKILL.md")):
        raise SystemExit(f"源目录缺少 SKILL.md：{SRC}")

    detected = probe()
    print("=" * 60)
    print("检测到的 AI 工具")
    print("=" * 60)
    for name, hit in detected:
        mark = f"✓ {hit}" if hit else "· 未检测到安装痕迹"
        print(f"  {name:10} {mark}")

    if args.list:
        print("\n可用 --target 指定目标，或用 --project DIR 装到项目。")
        return 0

    targets = args.target or [n for n, h in detected if h]
    if not targets:
        print("\n[!] 未检测到任何已安装的 AI 工具。")
        print("    可手动指定目标，例如：python install.py --target claude")
        return 1

    print()
    installed = []
    for tname in targets:
        row = next((r for r in TARGETS if r[0] == tname), None)
        if not row:
            print(f"  [skip] 未知目标：{tname}")
            continue
        name, user_rel, proj_rel, mdc_rel = row

        if args.project:
            base = os.path.join(args.project, proj_rel)
            target, mode = install_to(base, project=True)
            if mdc_rel:
                with open(os.path.join(SRC, "SKILL.md"), encoding="utf-8") as f:
                    install_mdc(f.read(), os.path.join(args.project, mdc_rel))
        else:
            target, mode = install_to(user_rel)

        installed.append((name, target, mode))
        print(f"  [ok]   {name:10} → {target}  ({mode})")

    print("\n" + "=" * 60)
    print(f"安装完成（{len(installed)} 个目标）")
    print("=" * 60)
    print("\n后续步骤：")
    print("  1. 安装运行时依赖（首次）：")
    print("     pip install requests faster-whisper yt-dlp Pillow")
    print("     并确保 ffmpeg 在 PATH 中")
    print("  2. 重启对应工具的会话，让 Agent 重新扫描 skill")
    print("  3. 试一句：帮我提取这个视频的字幕 https://www.bilibili.com/video/BV...")
    print("\n若工具没自动发现，试试显式点名：")
    print("  「用 video-asr-subtitle skill 处理 BV...」")
    return 0


if __name__ == "__main__":
    sys.exit(main())