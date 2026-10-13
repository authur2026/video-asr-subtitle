# video-asr-subtitle

从视频链接提取字幕（SRT + 纯文本 + 带时间戳），并可进一步做成带插图的 PDF 故事画册。

**遵循 [Agent Skills 开放规范](https://code.claude.com/docs/en/skills)**：纯 `SKILL.md` + `scripts/` + `references/` + `assets/` 结构，零厂商专有 API，可安装到 Claude Code、Cursor、Codex、Gemini CLI、Windsurf 及任何兼容该规范的 Agent 工具。

---

## 让你的 Agent 帮你装

如果你在用带终端权限的 Agent 工具（Claude Code / Codex / Cursor / Gemini CLI / Windsurf），
直接把下面这句话发给它就行：

```
帮我安装这个 skill：https://github.com/authur2026/video-asr-subtitle
```

Agent 会自己 clone 仓库、运行 `python install.py`、并报告装到了哪个目录。
你也可以手动操作：

```bash
git clone https://github.com/authur2026/video-asr-subtitle.git
cd video-asr-subtitle
python install.py
```

> **网页版对话工具**（豆包 / 百度搭子 / 千问办公网页版等）没有终端权限，装不了。
> 这类工具请看下方[手动运行](#手动运行不依赖-agent)——把脚本跑在本机，产物再拿回去用。

---

## 为什么不用平台原生字幕

B站原生字幕有三堵墙，全部实测确认**不可逾越**：

| 墙 | 证据 |
|---|---|
| 登录态 v20 加密 | Chrome/Edge 127+ App-Bound Encryption，密钥由浏览器特权服务保管，外部工具无法解密 |
| auth_key 分钟级过期 | CDN 返回 `X-Tengine-Error: denied by req auth: invalid md5hash`，改 UA/Referer/Origin 全无效 |
| CDN 无 CORS 头 | 浏览器控制台 `fetch` 也被拦 |

**但下载音频完全不需要登录** —— 登录态只影响「枚举字幕列表」，按 `cid` 取 DASH 音频流是匿名的。所以本skill 走「下音频 → 本地 ASR」路线。

---

## 安装

### 一键安装（推荐）

```bash
python install.py
```

自动探测本机已安装的 AI 工具，装到对应目录（Windows 无软链接权限时自动退回复制）。

```bash
python install.py --list                  # 只看检测结果
python install.py --target claude         # 指定单个目标
python install.py --project .             # 装到当前项目而非用户级
```

支持目标与安装路径：

| 目标 | 用户级路径 | 项目级路径 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` + `.cursor/rules/*.mdc` |
| OpenAI Codex | `~/.codex/skills/` | `.codex/skills/` |
| 通用 agents | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Windsurf | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` |

### 手动安装

把 `video-asr-subtitle/` 整个目录拷到上面任一路径即可。

### 运行时依赖

**先体检，一次看清缺什么**：

```bash
python video-asr-subtitle/scripts/doctor.py
```

逐项检查 Python 版本、四个第三方库、ffmpeg、whisper 模型缓存、Node.js、playwright-core、chromium，
缺失项直接给出可复制的修复命令。退出码 0 = 字幕提取流程可运行。

手动安装：

```bash
pip install requests faster-whisper yt-dlp Pillow
```

- **ffmpeg 必须在 PATH**
  - Windows `winget install Gyan.FFmpeg`
  - macOS `brew install ffmpeg`
  - Linux `sudo apt install ffmpeg`
- **PDF 阶段另需**：`npm i playwright-core && npx playwright install chromium`

---

## 使用

装好后直接对 Agent 说：

> 帮我提取这个视频的字幕 https://www.bilibili.com/video/BV1y8411x778

或显式点名（某些工具需要）：

> 用 video-asr-subtitle skill 处理 BV1y8411x778

### 会产出什么

| 你说的| 产出 |
|---|---|
| 「提取字幕」 | **字幕三件套**：`标题_精校.srt` + `_精校.txt` + `_精校_带时间戳.txt` |
| 「做成画册」 | 三件套 **+** PDF 画册+ 插图 + `book.json` |

**第一阶段完成后，Agent 会主动问你要不要做PDF 画册**，并说明耗时和成本，你同意才会继续。
这是有意设计的：插图生成要调用图像模型花钱，且耗时不可控，Agent 不会替你做消费决策。

第二阶段的做法见 `SKILL.md`。

### 手动运行（不依赖 Agent）

适合网页版对话工具等没有终端权限的场景——脚本在本机跑，产物再拿回去用。

```bash
# 0. 环境体检
python video-asr-subtitle/scripts/doctor.py

# 1. 下载音频 → 16k 单声道 WAV
python video-asr-subtitle/scripts/fetch_audio.py BV1y8411x778 -o ./out

# 2. ASR 转写（--prompt 写明人物+领域，显著提升准确率）
python video-asr-subtitle/scripts/transcribe.py ./out/audio_BV1y8411x778.wav \
  -n "标题" --prompt "关于XXX的中文解说，涉及XXX"

# 3. 查重复幻觉
python video-asr-subtitle/scripts/transcribe.py --check-dup "./out/标题_转写_带时间戳.txt"

# 4. 精校（复制 config_template.py 改路径与规则后）
python video-asr-subtitle/scripts/clean_subtitle.py --config my_config.py --dry-run
python video-asr-subtitle/scripts/clean_subtitle.py --config my_config.py

# 5. 校验（退出码 0 = 通过）
python video-asr-subtitle/scripts/validate_srt.py "./out/标题_精校.srt"
```

画册 PDF 的手动流程见 `SKILL.md` 的第二阶段。

---

## 支持的平台

| 平台 | 方式 | 登录态 |
|---|---|---|
| B站 | 内置匿名 API 取 DASH | **不需要** |
| 小红书 | yt-dlp，URL **必须含 `xsec_token`** | 匿名 session 即可 |
| YouTube / 微博 / 快手 | yt-dlp | 视平台 |
| 抖音 | yt-dlp 内置 extractor 多已失效，需专用脚本 | — |
| 本地音视频文件（15 种扩展名） | 直接转 WAV | — |

小红书 token 获取：**App 打开笔记 → 分享 → 复制链接**。不要从浏览器地址栏复制。

---

## 环境变量

| 变量 | 作用 |
|---|---|
| `HF_HUB_OFFLINE` | 离线加载已缓存的 whisper 模型（走代理导致 HF 502 时用） |
| `ASR_FORCE_OFFLINE` | 强制离线加载（等价于设上面那个，但只对本skill 生效） |
| `PW_CORE` | playwright-core 安装目录（自动探测失败时手动指定） |
| `PW_BROWSERS` | chromium 缓存目录（自动探测失败时手动指定） |
| `ASR_BASE` | 精校配置里的默认工作目录 |

---

## 目录结构

```
video-asr-subtitle/
├── LICENSE                      MIT
├── README.md                    本文件
├── install.py                   通用安装器（自动探测 6 家工具）
└── video-asr-subtitle/          skill 本体
    ├── SKILL.md                 入口：流程说明 + 踩坑清单
    ├── scripts/
    │   ├── fetch_audio.py       下载音频 + 转 WAV（4 类输入）
    │   ├── transcribe.py        ASR 转写 + 幻觉检测器
    │   ├── clean_subtitle.py    精校引擎（配置驱动）
    │   ├── validate_srt.py      SRT 严格校验
    │   ├── build_book.py        book.json → 画册 HTML
    │   ├── html2pdf.js          HTML → PDF
    │   ├── crop_watermark.py    裁 AI 水印 + 语义化重命名
    │   └── doctor.py            环境体检（先跑这个）
    ├── references/
    │   ├── experience.md        实战经验与踩坑证据（先读这个）
    │   ├── replace_library.py   替换库 229 条，按题材分组
    │   ├── config_template.py   精校配置模板
    │   └── book_schema.md       book.json 结构 + 章节拆分原则
    └── assets/
        └── book.css             画册样式（改 :root 换配色）
```

> 外层目录名与内层 skill 目录名相同是刻意的——`install.py` 依赖这个相对路径定位 skill 源。

---

## 核心经验（详见 `references/experience.md`）

1. **代词性别必须按时间戳区间判定** —— ASR 小模型分不出男女。定义 `MALE_RANGES` / `FEMALE_RANGES`，全局替换会把真实的母亲、女教练一起改错。
2. **音译乱码只能整段重写** —— 英文演讲会被识别成无意义中文，替换表修不了。
3. **重写后必须单调化时间轴** —— 否则与前后行有 0.2s 级重叠，播放器上字幕闪跳。
4. **去重过滤条件不能设太严** —— 无意义幻觉往往只有 2-3 字（「这些人」×5），`min_len` 设 5 会全部漏网。
5. **`initial_prompt` 是准确率的最大杠杆** —— 写明人物+领域比泛泛描述提升明显。

---

## License

MIT