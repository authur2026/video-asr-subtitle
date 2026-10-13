---
name: video-asr-subtitle
description: Extract subtitles/transcripts from video links (Bilibili, Xiaohongshu, YouTube, Douyin, Kuaishou, Weibo, etc.) and local media files, producing SRT subtitles plus plain-text and timestamped transcripts. Can then turn the polished text into an illustrated PDF story album. Use when the user provides a video link or BV id and asks to "下载字幕" "提取文案" "转写视频文字" "提取解说词" "生成SRT字幕" "做成画册" "出图文PDF", or mentions ASR / whisper / faster-whisper / 语音识别. Native Bilibili subtitle download is blocked by v20 encryption and minute-level CDN signatures, so this skill downloads the audio track and runs local ASR instead.
version: 1.0.0
author: video-asr-subtitle contributors
license: MIT
compatibility: "Requires Python 3.8+, ffmpeg on PATH, network access. Optional: yt-dlp (non-Bilibili platforms), Node.js + playwright-core + chromium (PDF stage only)."
metadata:
  spec: agent-skills
  runtime: python3, node
  tested-platforms: windows, macos, linux
---

# 视频 ASR 字幕提取与画册生成

把视频音轨转成本地字幕（SRT + 纯文本 + 带时间戳），可选继续做成带插图的 PDF 故事画册。

## 何时使用

用户提供视频链接 / BV 号 / 本地视频文件，并希望得到字幕、文案、解说词、SRT，或要求把这些文字做成画册、图文 PDF。

| 输入形态 | 处理方式 | 是否需要登录 |
|---|---|---|
| B站 BV 号 / `bilibili.com` / `b23.tv` 短链 | 内置匿名 API 取 DASH 音频 | 否 |
| 小红书笔记链接 | yt-dlp，**URL 必须含 `xsec_token`** | 否（匿名 session 即可） |
| YouTube / 抖音 / 快手 / 微博 等 | yt-dlp | 视平台 |
| 本地音视频文件（15 种扩展名） | 直接转 WAV | — |

**小红书注意**：URL **必须含 `xsec_token`**，否则 yt-dlp 报 `No video formats found`。
获取方式：**App 打开笔记 → 分享 → 复制链接**。不要从浏览器地址栏复制，那里没有 token。

## 依赖准备

```bash
pip install requests faster-whisper yt-dlp Pillow
```

**建议先跑体检**（一次说清缺什么、怎么补）：

```bash
python scripts/doctor.py
```

逐项检查 Python 版本、四个第三方库、ffmpeg、whisper 模型缓存、Node.js、playwright-core、chromium，
缺失项直接给出可复制的修复命令。退出码 0 = 核心流程（字幕提取）可运行。

- **ffmpeg 必须在 PATH**（用于转 WAV）。找不到时 `doctor.py` 会给出对应系统的安装命令
- **PDF 阶段另需 Node.js + playwright-core**：
  ```bash
  npm i playwright-core && npx playwright install chromium
  ```
  脚本按 `PW_CORE` 环境变量 → 本 skill 的 `node_modules` → 全局 npm 顺序探测
- 若机器走代理导致 HuggingFace 官方源 502，先联网跑一次让模型缓存，再设 `HF_HUB_OFFLINE=1` 走离线。
  **未缓存时不要设该变量**，否则模型加载失败（`doctor.py` 会检测并提示）

## 执行流程

### 第 1 步：下载音频

```bash
python scripts/fetch_audio.py BV1xxxxxxxxx -o ./output
```

脚本自动判断平台，也可手动指定：

```bash
# 小红书（URL 需带 xsec_token）
python scripts/fetch_audio.py "https://www.xiaohongshu.com/explore/xxx?xsec_token=AAA"

# 其他平台走 yt-dlp
python scripts/fetch_audio.py "https://www.youtube.com/watch?v=xxx" --platform generic

# 本地文件直接转 WAV
python scripts/fetch_audio.py ./video.mp4
```

自动流程：取音频流 → 下载 → ffmpeg 转 16kHz 单声道 WAV → 删除中间文件（`--keep-src` 可保留）。
B站多 P 视频加 `-p 2` 选分 P。成功后打印 WAV 绝对路径。

### 第 2 步：ASR 转写

```bash
python scripts/transcribe.py "./output/audio_BV1xxx.wav" \
  -n "视频标题" \
  --prompt "以下是一段关于XXX的中文解说，涉及XXX、XXX。"
```

**`--prompt` 是最重要的杠杆** —— 必须写明**人物 + 领域 + 场景**。
写明「李宗伟、羽毛球、奥运会」比泛泛写「体育励志」准确率明显更高。

产出三个文件：`<标题>_转写_纯文本.txt`、`<标题>_转写_带时间戳.txt`、`<标题>_转写.srt`。

**耗时预估**：`small/int8/cpu` 下 ≈ 音频时长 × 0.44（20 分钟视频约 9 分钟）。建议后台运行。

### 第 3 步：查重复幻觉

```bash
python scripts/transcribe.py --check-dup "./output/标题_转写_带时间戳.txt"
```

whisper 会出现整段话循环 2-4 遍的幻觉。**精校前必查**，否则字幕会出现明显重复。

### 第 4 步：精校（必须做，不要跳过）

**逐段通读全文**（用 Agent 具备的文件读取能力分段读），找出四类问题：

1. **错字** —— 人名、术语、同音字。见 `references/replace_library.py`（229 条实战积累，按题材分组）
2. **重复幻觉** —— 第 3 步会报告位置，`clean_subtitle.py` 自动删除
3. **代词性别** —— 小模型分不出性别，男性主角常被写成「她」。**必须按时间戳区间判定**，绝不能全局替换
4. **音译乱码** —— 英文演讲会被识别成无意义中文，只能按语境整段重写

复制 `references/config_template.py` 改成本片配置：

```bash
cp references/config_template.py my_video_config.py
# 编辑 my_video_config.py：填路径、补REPLACE、按需写 REWRITE / MALE_RANGES / FEMALE_RANGES
python scripts/clean_subtitle.py --config my_video_config.py --dry-run   # 先看统计
python scripts/clean_subtitle.py --config my_video_config.py
```

`--dry-run` 会报告「删除多少幻觉行、重写几处、哪些替换后仍残留、是否有繁体残留」，确认无误再去掉 `--dry-run`。

### 第 5 步：校验 SRT

```bash
python scripts/validate_srt.py "./output/标题_精校.srt"
```

检查序号连续、时间轴格式、无倒置、无重叠。**退出码 0 = 通过**。必须通过后再交付。

### 第 6 步：交付字幕 + 询问是否进入第二阶段

**先把字幕文件交付出去，再询问。** 顺序不能反——用户必须先拿到东西。

1. 把三个文件的绝对路径告知用户，并说明用途差异：

| 文件 | 用途 |
|---|---|
| `<标题>_精校.srt` | 喂播放器 / 剪辑软件（PR / 剪映 / Final Cut） |
| `<标题>_精校_带时间戳.txt` | 精校时定位问题用 |
| `<标题>_精校.txt` | 二次创作、翻译、改写用 |

2. 紧接着**主动询问**是否要做图文画册。这一步**必须问，不能擅自开始**：

```
字幕已完成。要继续把它做成带插图的 PDF 画册吗？

· 成品：A4 故事画册，10 页左右，含章节标题 + 配图 + 引文
· 耗时：插图生成是主要开销，每章 1 张，约 4-6 张
· 成本：需要调用图像生成模型，按张计费（各工具单价不同）
· 用法：确认后我会先跟你对一遍画册形态、插图风格和配图数量，再开始生成

如果只需要字幕，到这里就完成了。
```

3. **必须等用户明确同意**才能进第二阶段。用户说「不用」「就到这」「先这样」之类的，立即收尾，不要再劝。

> **为什么要问**：插图生成要花钱（每张 5-10 积分不等）且耗时不可控。
> 不问就做等于替用户做消费决策。用户只要字幕却被迫等画册，是严重的体验问题。

---

# 第二阶段：图文画册 PDF

字幕精校完成后，可继续把文案做成带插图的精美 PDF（故事画册形态）。

## 何时进入这一阶段

**两个入口，都必须先拿到用户确认：**

| 入口 | 条件 |
|---|---|
| **主动推荐** | 第一阶段交付字幕后，按第 6 步的模板询问；用户同意即进入 |
| **用户直接要求** | 用户说了「做成画册」「配上插图」「出 PDF」「做成图文版」「排版成册」等 |

**没拿到确认就不要开始。** 图像生成要花钱且耗时不可控，这是消费决策，必须由用户拍板。

## 确认后：先对三件事

用户同意后，**一次性问完**（不要来回打断）：

1. **PDF 形态**：故事画册 / 逐句图文版 / 故事画册 + 字幕附录
2. **插图风格**：水彩淡彩 / 新中式扁平 / 黑底电影感 / 黑白纪实
3. **插图数量**：按章节自动决定（推荐，通常 4-6 张）还是用户指定

三件事确认后再开始拆分章节。**不要在没确认风格的情况下先生成插图**——风格错了整本白费。

## 前置：拆分章节

精校后的纯文本是逐句短句，直接排版会碎成流水账。**必须先合并成段落**。

通读全文后按叙事节奏划分：

- 通常 20 分钟视频分 **4-6 章**
- 每章一个核心事件或转折
- 合并相邻短句为完整段落（每段 3-6 句）
- 挑出 1-2 处金句做引文块

产出 `book.json`，结构见 `references/book_schema.md`：

```json
{
  "title": "没有人会记住第二名",
  "subtitle": "除非他是李宗伟",
  "chapters": [
    {
      "num": "第一章",
      "title": "咖啡壶上的字",
      "image": "images/ch1.png",
      "image_caption": "1961年的美国，种族隔离渗透进每一处细节",
      "paragraphs": ["……", "……"],
      "pull_quote": { "text": "……", "source": "——" },
      "facts": [{"label": "出生地", "text": "…"}]
    }
  ]
}
```

## 插图生成

用当前环境中可用的图像生成工具逐章生成。**各家工具能力不同**：Claude 有图像生成、ChatGPT 有 DALL·E / GPT Image，而多数 IDE 内置模型没有。若当前环境无图像生成能力，明确告知用户并改为占位图或跳过插图，不要假装已生成。

**prompt 要素**（缺一不可）：

```
{题材} + {主体人物/场景} + {水彩淡彩/新中式/电影感等风格}
+ 配色约束 + 构图要求 + 排除项
```

示例（水彩淡彩风）：

```
一位黑人女性在六十年代的白人航天大楼里独自使用隔间，
铅笔素描质感，淡雅水彩，低饱和莫兰迪配色，柔和留白，
安静而克制的氛围，情绪内敛，不要夸张表情，
横向构图，电影感光线，中等细节
```

**尺寸**：`1536x1024`（横向，适合页内插图）或 `1024x1536`（纵向，适合跨页）

**成本提醒**：调用前必须告知用户单张消耗的积分 / 费用。

生成后**逐张检查**，不合格的重生成。图不对就别往下走。
部分生成器会在右下角加「AI生成」水印，用 `scripts/crop_watermark.py` 裁掉并语义化重命名。

## 生成 HTML

```bash
python scripts/build_book.py book.json -o 画册.html
python scripts/build_book.py book.json -o 画册.html --css 自定义.css
```

样式来自 `assets/book.css`（改 `:root` 变量即可换配色）。要点：

- 图片用绝对路径，脚本自动转 `file:///`（chromium 能正常加载）
- `@page` 设 A4，边距 18-20mm
- `printBackground` 已在 html2pdf.js 开启，背景色不会丢
- **章节默认不强制分页**（避免半空白页）；需要严格分章时在 book.json 顶层加 `"chapter_break": true`

## 转 PDF

```bash
node scripts/html2pdf.js book.html 画册.pdf A4
```

`html2pdf.js` 已处理三个坑：
1. playwright-core 版本与本地 chromium 缓存版本可能不匹配 → 自动扫缓存目录取最高版本并显式传 `executablePath`
2. Windows 下不能用 `/tmp/...` 拼 file URL → 用 `pathToFileURL()`
3. playwright-core 装在哪不确定 → 多路径探测 + `PW_CORE` 环境变量兜底

若报「找不到 playwright-core」，设环境变量指向实际安装位置：
```bash
export PW_CORE=/path/to/node_modules/playwright-core     # macOS / Linux
set PW_CORE=C:\path\to\node_modules\playwright-core     # Windows
```

## 验证（必做）

PDF 不能直接读取，必须导出页面为图片检查：

```bash
pip install pymupdf
python -c "
import pymupdf
d = pymupdf.open('画册.pdf')
print('页数', d.page_count)
for i in range(d.page_count):
    d[i].get_pixmap(dpi=62).save(f'_p{i+1:02d}.png')
"
```

然后逐张查看。**网页预览 ≠ PDF 效果**。

**页密度量化**（低于 60% 说明留白过多）：

```bash
python -c "
import pymupdf
d = pymupdf.open('画册.pdf')
for i in range(d.page_count):
    b = d[i].get_text('blocks')
    m = max([x[3] for x in b] + [0])
    print(f'P{i+1:02d} {m/d[i].rect.height*100:.0f}%')
"
```

## 排版避坑

| 症状 | 原因 | 解法 |
|---|---|---|
| PDF 里背景色丢失 | 未开 `printBackground` | 已在校验器开启 |
| 中文变方块 | 字体未嵌入 | 用「Microsoft YaHei」/「PingFang SC」等系统字体 |
| 章节挤在上一页 | 未分页 | `book.json` 加 `"chapter_break": true` |
| 图被切断 | 分页符落图中间 | `.illustration { page-break-inside: avoid }` |
| 段落碎片化 | 没做章节拆分 | 先合并成段落再排版 |
| 图片不显示 | 路径不对 | 用绝对路径 + `file:///` |

## 交付

把 PDF 与生成的插图路径告知用户。

---

## 精校的三个核心原则

详见 `references/experience.md`（含完整实战记录与踩坑证据）。

1. **代词性别按时间区间判定** —— 定义 `MALE_RANGES` / `FEMALE_RANGES`，落在男性区间且不在女性区间才替换。全局替换会把真实的母亲、女教练一起改错。

2. **音译乱码整段重写** —— 用 `REWRITE = [(起秒, 止秒, [句子...]), ...]`，时间轴在区间内均分。替换表修不了这类。

3. **重写后必须单调化时间轴** —— `clean_subtitle.py` 内置 `enforce_monotonic()`，否则重写段与前后行有 0.2s 级重叠，播放器上字幕会闪跳。

## 事实性错字要纠正

ASR 只听发音，不懂语义。遇到与影片实际不符的表述要按事实改：

- 例：「残疾的儿子」→ 实际是「脑瘫的儿子」（影片角色患脑瘫）
- 判断依据：影片名、题材常识、上下文逻辑

## 资源文件

| 文件 | 用途 |
|---|---|
| `scripts/fetch_audio.py` | 下载音频 + 转 WAV（B站/小红书/通用平台/本地文件）|
| `scripts/transcribe.py` | ASR 转写；兼作幻觉检测器 |
| `scripts/clean_subtitle.py` | 精校引擎（配置驱动） |
| `scripts/validate_srt.py` | SRT 格式校验 |
| `scripts/build_book.py` | book.json → 画册 HTML |
| `scripts/html2pdf.js` | HTML → PDF（chromium 版本探测、Windows 路径处理） |
| `scripts/crop_watermark.py` | 裁掉 AI 水印 + 语义化重命名 |
| `scripts/doctor.py` | 环境体检：逐项检查依赖并给出修复命令 |
| `assets/book.css` | 故事画册样式（改 `:root` 变量换配色） |
| `references/book_schema.md` | book.json 数据结构 + 章节拆分原则 |
| `references/experience.md` | 实战经验与踩坑记录（**先读这个**） |
| `references/replace_library.py` | 共用替换库，229 条，按题材分组 |
| `references/config_template.py` | 精校配置模板 |

## 两阶段工作流

```
第一阶段（字幕）                      第二阶段（画册）
fetch_audio.py                        拆分章节 → 生成插图
transcribe.py                         组装 HTML
clean_subtitle.py          ──────►     html2pdf.js → 校验 → 交付
validate_srt.py
```

第二阶段依赖第一阶段的精校纯文本，可独立启动。

## 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `HF_HUB_OFFLINE` | 离线加载已缓存的 whisper 模型 | 未设（走网络） |
| `PW_CORE` | playwright-core 安装路径 | 自动探测 |
| `PW_BROWSERS` | chromium 缓存目录 | 按平台推断 |
| `ASR_BASE` | 精校配置里的默认工作目录 | 当前目录 |
| `ASR_FORCE_OFFLINE` | 强制 whisper 离线加载 | 未设 |