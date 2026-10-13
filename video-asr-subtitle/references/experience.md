# B站视频 ASR 字幕提取 —— 实战经验与踩坑记录

## 为什么走ASR 而不是 B站原生字幕

原生字幕下不来，三重墙（均已实测确认）：

| 墙 | 证据 | 结论 |
|---|---|---|
| 登录态v20 加密 | 浏览器 cookie 库中的 B站 cookie 全部为 `v20` 前缀 = Chrome/Edge 127+ **App-Bound Encryption**，密钥由浏览器特权服务保管且只认自身进程 | yt-dlp `--cookies-from-browser` 与自写 DPAPI+AES-GCM 脚本**均无法解密** |
| **auth_key 分钟级过期** | CDN 响应头 `X-Tengine-Error: denied by req auth: invalid md5hash`，auth_key 内嵌 Unix 时间戳 | 签名校验失败，改 UA/Referer/Origin **全无效** |
| **CDN 无 CORS 头** | 字幕CDN 不返回 `Access-Control-Allow-Origin` | 浏览器控制台 fetch 也被拦（`credentials:'include'` 时） |

**但下音频完全不需要登录**——登录态只影响"枚举字幕列表"，按 cid 取 DASH 流是匿名的。这是整个流程成立的基础。

---

## 完整流程

```
1. fetch_audio.py      BV → 音频 m4s → 16k单声道 WAV
2. transcribe.py       WAV → 纯文本 + 带时间戳 + SRT
3. 查重复幻觉
4. clean_subtitle.py   精校（配置驱动）
5. validate_srt.py     格式校验
```

### 环境依赖

```bash
python -m venv .venv                      # 建议用虚拟环境隔离
# Windows
.venv\Scripts\python.exe -m pip install requests faster-whisper yt-dlp Pillow
# macOS / Linux
./.venv/bin/pip install requests faster-whisper yt-dlp Pillow

# ffmpeg 需在 PATH
#   Windows: winget install Gyan.FFmpeg
#   macOS:   brew install ffmpeg
#   Linux:   sudo apt install ffmpeg
```

**关于 `HF_HUB_OFFLINE`**：若你的网络能直连 HuggingFace，不用设。
若走代理导致 HF 官方源 502（常见报错 `Connection to huggingface.co timed out`），
先成功跑一次让模型缓存到 `~/.cache/huggingface/hub/`，之后设 `HF_HUB_OFFLINE=1` 即可完全离线。
本skill 的 `transcribe.py` **不强制**设该变量——未缓存时强制离线会导致模型加载失败。

---

## 关键技巧

### initial_prompt 是最重要的杠杆

写明**人物 + 领域 + 场景**，专名准确率显著提升：

```bash
--prompt "以下是一段关于马来西亚羽毛球运动员李宗伟的励志故事中文解说，涉及奥运会、世界排名、受伤与退役。"
```

对比：泛泛写"体育励志故事"vs 写明"李宗伟、羽毛球、奥运会"，后者把「林丹」以外的多处术语错误清零。

### 耗时预估

`small / int8 / cpu` 下 **ASR 耗时 ≈ 音频时长 × 0.44**

| 音频时长 | 实测耗时 |
|---|---|
| 19:02 | 8分52秒 |
| 20:00 | 8分41秒 |
| 22:27 | 11分22秒 |

---

## 精校的三大坑

### 坑1：重复幻觉（whisper 循环）

表现为整段话重复 2-4 遍。检测：

```bash
python transcribe.py --check-dup 输出_带时间戳.txt
```

处理：`clean_subtitle.py` 的 `dedupe()` 自动删除连续重复行。实测三个视频：
- BV1HabU62EFn 有 39 行循环（02:22-02:36 同一段重复 3 遍）
- BV1ykb16GEnR 无
- BV1Vp3w6xEaE 轻微 2 处

### 坑 2：代词性别错乱

小模型分不出性别，李宗伟（男）被写成 39 处「她」。

**错误做法**：
- ❌ 全局替换「她」→「他」→ 会把真实的母亲、教练妻子一起改错
- ❌ 按整句 replace → ASR 每行仅几字，整句永远匹配不上
- ❌ 按行判断「行内是否含主角名」→ 漏掉大量跨行指代

**正确做法：按时间戳区间判定**

```python
MALE_RANGES   = [(524.0, 772.0)]              # 主角（男性）
FEMALE_RANGES = [(478.0, 505.0), (770.0, 800.0)]  # 母亲、教练妻子
```

落在男性区间且不在女性区间 → 「她」改「他」。精校后剩余 16 处「她」经人工核对全部正确。

### 坑 3：英文演讲 / 音译乱码

含英文台词或英文演讲的视频，小模型输出无意义音译：

```
[0889.3] 我认为,
[0890.3] 有很多战士,        ← 原文："I think there are athletes"
[0892.3] 都比我更值得的,
[0896.3] 在他们的证据中,
[0897.3] 被连续起来,
```

这类**替换表修不了**，必须按语境整段重写：

```python
REWRITE = [
    (888.0, 900.0, [
        "面对记者的提问,爱迪这样回答,",
        "他认为,有很多运动员都比他更值得那块金牌,",
    ]),
]
```

### 附带坑：重写段的时间轴重叠

`apply_rewrite` 之后**必须**过一遍 `enforce_monotonic()`。否则重写段与前后行有 0.2s 级残留重叠，播放器上表现为字幕闪跳。这个 bug 修了两轮才对。

---

## SRT 格式校验（必做）

ASR 产出直接喂播放器前，务必跑校验：

```bash
python validate_srt.py subtitle.srt
```

检查：序号连续、时间轴格式、结束>开始、无重叠、最短显示时长。退出码 0 = 通过。

---

## 三部实战横向对比（UP主：小余的电影独白）

| BV号 | 题材 | 时长 | ASR耗时 | 原始段数 | 精校后 | 幻觉 | 特殊处理 |
|---|---|---|---|---|---|---|---|
| BV1HabU62EFn | 隐藏人物（NASA/黑人女数学家） | 22:27 | 11:22 | 659 | 631 | 39行循环 | 大量代词 |
| BV1ykb16GEnR | 李宗伟（羽毛球） | 19:02 | 8:52 | 652 | 652 | 无 | 39处代词 |
| BV1Vp3w6xEaE | 飞鹰艾迪（脑瘫/跳台滑雪） | 20:00 | 8:41 | 544 | 530 | 2处 | 5段英文乱码重写 |

**规律**：同一 UP 主的电影解说，ASR 错字模式高度相似（人名、术语、同音字），替换库可跨片复用。三部精校后总计约 1.77 万字。

---

## 同音字错识的高频样本（做替换库时的思路来源）

| ASR 输出 | 正确 | 说明 |
|---|---|---|
| 海豹 | 滑雪板 | 同音 |
| 与毛球 | 羽毛球 | 音近 |
| 灵丹 | 林丹 | 同音 |
| 感同深受 | 感同身受 | 形近 |
| 顺序万遍 | 瞬息万变 | 同音 |
| 博二之选 | 不二之选 | 同音 |
| 功亏一亏 | 功亏一篑 | 同音 |
| 挪威老 | 挪威佬 | **注意**：这是人名绰号，不要误改 |

---

# 第二阶段实战：图文画册 PDF（BV1ykb16GEnR 李宗伟）

## 环境结论

- **reportlab 不推荐装** —— 中文排版和图文混排 HTML 天然更强
- **playwright-core + chromium 可用**，HTML 转 PDF 链路完全跑通（版本号会随时间变化，别写死）
- pymupdf 用于验证 PDF 效果（导出页面为 PNG 后逐张查看）

## 三个必须显式处理的坑

### 坑 1：chromium 版本不匹配

playwright-core 的版本要求与本地 chromium 缓存版本不一定一致，直接 launch 会报：

```
Executable doesn't exist at ...\chromium_headless_shell-1234\chrome-headless-shell.exe
```

**解法**：显式指定 `executablePath`，并**自动探测**缓存目录里的最高版本（`chromium-*` 按版本号排序），不要写死路径。
不同平台的缓存目录不同：Windows `%LOCALAPPDATA%\ms-playwright`、macOS `~/Library/Caches/ms-playwright`、Linux `~/.cache/ms-playwright`。

### 坑 2：Windows 下 file:// URL

Node 在 Windows 里不能用 `/tmp/xxx.html` 拼 `file://` —— 会被当成相对路径，报 `ERR_FILE_NOT_FOUND`。

**解法**：用 `require('url').pathToFileURL()` 转换。

### 坑 3：playwright-core 装在哪不固定

不同项目、不同的包管理器（npm / pnpm / yarn / 全局 / 内置托管运行时），安装位置都不一样。

**解法**：多路径探测 + `PW_CORE` 环境变量兜底，见 `scripts/html2pdf.js` 的 `PW_PATHS`。

## 水印处理

部分图像生成器产出的图右下角带「AI生成」水印，直接进 PDF 很扎眼。

`crop_watermark.py` 处理：
1. 按比例裁掉右下角（默认各 5.5%）
2. 同时做语义化重命名（长英文文件名 → `ch1_球拍墙.png`）

一次搞定，比事后手改省事。

## 插图 prompt 要素（实测有效）

```
{主体人物/场景} + {风格} + {配色约束} + {构图要求} + 情绪词 + 排除项
```

水彩淡彩风范例：

```
A lone Malaysian badminton player standing at the edge of a simple outdoor
court at dusk, seen from behind, holding a racket loosely at his side.
Watercolor illustration style with soft pencil under-drawing, delicate washes
of muted teal, dusty terracotta and warm cream. Generous empty space in the
upper two thirds for text overlay, calm and restrained atmosphere, gentle
diffuse evening light, nostalgic and quiet mood, no text, no logos,
cinematic horizontal composition
```

要点：
- **明确说 watercolor + pencil under-drawing** —— 保证画风统一
- **指定具体配色**（muted teal / dusty terracotta / warm cream）—— 六张图风格才一致
- **给情绪词**（calm / nostalgic / uneasy / quietly triumphant）
- **写no text, no logos** —— 避免模型加文字
- 尺寸 `1536x1024`（横向，适合页内图）

## 排版避坑（实测数据）

| 症状 | 根因 | 解法 |
|---|---|---|
| 每章半空白页 | `.chapter { page-break-before: always }` | 去掉，改为大间距自然分隔；需要严格分章时加 `.chapter-break` |
| 章节标题孤立页底 | 默认允许分页 | `h2 { page-break-after: avoid }` |
| 插图被推到下页留白 | 图太高放不下剩余空间 | `.illustration img { max-height: 78mm; object-fit: cover }` |
| PDF 背景色丢失 | 未开 printBackground | html2pdf.js 已开启 |
| 中文变方块 | 字体未嵌入 | 用「Microsoft YaHei」等系统字体 |

**优化前后对比**：12 页 → 10 页，页面内容密度从 45%-92% 提升到 57%-92%，多数页 82%-92%。

## 验证方法

PDF 不能直接用文件读取工具打开，必须导出页面为图片检查：

```python
import pymupdf
d = pymupdf.open("book.pdf")
print("页数", d.page_count)
for i in range(d.page_count):
    d[i].get_pixmap(dpi=62).save(f"_p{i+1:02d}.png")
```

**网页预览 ≠ PDF 效果**，必须实际导出验证。页密度可量化：

```python
blocks = page.get_text("blocks")
maxy = max(b[3] for b in blocks)
print(f"内容到 {maxy/page.rect.height*100:.0f}%")
```

低于 60% 说明该页有明显留白，可查是否插图被推走。

---

# 多平台支持（15:30）

原 skill 只做B站（自己实现 API 取流）。实测扩展后确认各平台差异：

## 各平台可用性

| 平台 | 方式 | 登录态 | 备注 |
|---|---|---|---|
| B站 | 自研 API 取 DASH | **匿名即可** | 最稳|
| 小红书 | yt-dlp | **必须带 xsec_token** | 匿名 session 可用，私密笔记需真登录 |
| YouTube | yt-dlp | 推荐（绕限速） | |
| 抖音/快手 | yt-dlp 或专用脚本 | 多数无需 | 抖音 yt-dlp 内置 extractor 已失效 |
| 微博 | yt-dlp | 公开内容无需 | |
| 本地文件 | 直接转 WAV | — | |

## 小红书的关键限制（实测）

**URL 必须含 `xsec_token`**，否则 yt-dlp 直接报：
```
ERROR: [XiaoHongShu] xxx: No video formats found!
```
这不是工具问题，是小红书的设计——裸链接不带鉴权参数。

**获取方式**：小红书 App 打开笔记 → 分享 → 复制链接。
**不要**从浏览器地址栏复制，那里的链接没有 token。

画质档位（与 `video-downloader` skill 记录一致）：
- 裸 yt-dlp 无 cookie → 720p（音频足够用）
- 带 Chrome 匿名 `web_session` → 最高 4K
- **对 ASR 场景，720p 音频已足够，不需要折腾 cookie**

## 通用错误处理要点

写多平台分支时踩到的：
1. **yt-dlp 的异常必须 try/except** —— 否则原始 traceback 直接糊到用户脸上，要包成友好提示
2. **本地文件识别不能只靠 `os.path.isfile`** —— 加扩展名判断（`.mp4/.m4a/.mp3/.wav/...`），否则文件不存在时误判成 URL
3. **文件名不要重复加前缀** —— `audio_audio_xxx.wav` 这种很难看
4. **B站路径改完必须回归测试** —— 多平台改造最容易把原有平台搞坏
