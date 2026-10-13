# book.json 数据结构

`build_book.py` 的输入。用来把逐句字幕组织成有章节、有插图的故事画册。

## 完整示例

```json
{
  "title": "没有人会记住第二名",
  "subtitle": "除非他是李宗伟",
  "year": "2026",
  "cover_image": "images/cover.png",
  "meta": "<p>马来西亚羽毛球运动员李宗伟的励志传记</p><p>文字整理自 B站 视频字幕</p>",
  "chapters": [
    {
      "num": "第一章",
      "title": "买不起球拍的孩子",
      "image": "images/ch1.png",
      "image_caption": "1990年代的马来西亚，普通家庭的孩子的羽毛球梦",
      "paragraphs": [
        "第一天见面的场景，只用一两句话概括即可，不要照抄字幕",
        "这里是合并后的第二段，3 到 6 句为一个自然段"
      ],
      "side_image": "images/ch1_side.png",
      "side_paragraphs": ["图文交错时的正文内容"],
      "pull_quote": {
        "text": "没有人会记住第二名，除非他是李宗伟。",
        "source": "—— 广为流传的一句话"
      },
      "facts": [
        {"label": "出生", "text": "1979 年，马来西亚霹雳州"],
        {"label": "结局", "text": "四枚奥运银牌，一枚铜牌"}
      ]
    }
  ],
  "colophon": "<p>本册文字整理自 B站 视频字幕……</p>"
}
```

## 字段说明

### 顶层

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | 是 | 书名 |
| `subtitle` | 否 | 副标题 |
| `year` | 否 | 年份，用于默认 meta |
| `cover_image` | 否 | 封面插图路径 |
| `meta` | 否 | 封面底部信息，**支持 HTML**（用 `<p>` 换行） |
| `chapters` | 是 | 章节数组 |
| `colophon` | 否 | 结尾说明，**支持 HTML** |
| `css_path` | 否 | 自定义 CSS 路径（一般用 `--css` 参数覆盖） |

### 章节（`chapters[]`）

| 字段 | 必填 | 说明 |
|---|---|---|
| `num` | 否 | 章节序号，如「第一章」 |
| `title` | 是 | 章节标题 |
| `paragraphs` | 是 | 段落字符串数组，**必须合并成段**，不能照抄字幕短句 |
| `image` | 否 | 章首大图 |
| `image_caption` | 否 | 图注文案 |
| `side_image` + `side_paragraphs` | 否 | 图右文左的交错版式 |
| `pull_quote` | 否 | `{"text": "...", "source": "..."}` |
| `facts` | 否 | `[{"label": "...", "text": "..."}]`，渲染为浅色小块 |

## 图片路径

- **推荐绝对路径**：`build_book.py` 自动转 `file:///`，chromium 能加载
- 也可直接写 `file:///D:/xxx.png`
- 相对路径按 `cwd` 解析，建议先 `cd` 到工作目录

## 章节拆分原则

20 分钟视频（~5000 字）分 **4-6 章**，每章约 800-1200 字。

按叙事节奏切，不要按字数硬切：

| 切点 | 信号 |
|---|---|
| 场景转换 | 时间跳跃、地点变化（如「多年以后」「来到德国」） |
| 身份转换 | 从被动到主动、从低谷到转折 |
| 核心冲突解决 | 引文金句常在此处 |

## 段落合并

字幕是逐句短句，**必须合并**。判断标准：

- 一段讲完一个意思
- 3-6 句为宜
- 保留原文措辞，但删掉口语连接词（「就这样」「然后」「与此同时」可适度精简）
- 数字与专名要核对原文

## 配色改法

改 `assets/book.css` 的 `:root` 变量：

```css
:root {
  --ink:        #3d4a4a;   /* 正文墨色 */
  --accent:     #7ba6a0;   /* 主色 */
  --accent-warm:#c9a88a;   /* 暖色点缀 */
  --paper:      #fdfcf8;   /* 纸底 */
}
```

已内置配色：
- **水彩淡彩**（默认）：`--accent: #7ba6a0` + `--accent-warm: #c9a88a`
- **新中式**：`--accent: #1B4B6B` + `--accent-warm: #C4502E` + `--paper: #ECE4D2`
- **黑白纪实**：`--accent: #444` + `--accent-warm: #888` + `--paper: #fafafa`
