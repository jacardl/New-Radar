---
name: zhili-publish
description: >
  微信公众号草稿箱发布技能，专为「直隶按察使」公众号定制。
  支持：AI 封面图生成（Sensenova 首选，MiniMax 备选）、创建草稿、设置原创、分类标签、自动排版。
  触发条件：用户说「发布公众号」「推送草稿」「发布到公众号」「生成草稿」或直接说「发布直隶按察使」（注意：要先判断内容格式，见下方路由规则）。
---

# 直隶按察使 · 公众号发布技能

## ⚠️ 短评 vs 长文的路由规则（先判断再发布）

| | zhili-publish（长文） | zhilicomments-publish（短评） |
|--|----------------------|-------------------------------|
| 字数 | **4000-8000字** | 500-800字 |
| 结构 | Evolver 六段式或自定义深度结构，有章节标题 | 轻量三段式（事件+观点+一句话收尾） |
| 配图 | 项目截图+封面（正文必须有 mmbiz 图） | 1-2张评论配图（可选） |
| 用途 | 项目介绍/教程/深度分析/行业观察 | 热评/观点/Reaction |
| 内容来源 | khazix-writer 长文输出 | khazix-writer 短评输出 |

**khazix-writer → zhili-publish 交接规范**：

khazix-writer 产出**纯文本**，含【一、章节名】标注。zhili-publish 接收后：
1. 将【一、xxx】转为 `<h2>` 标签（18px bold 左对齐）
2. 正常段落转为 `<p>` 标签（16px 行高1.6 左对齐）
3. `【重点】句子` 转为 `<strong style="color:#e63946;">`
4. 嵌入 mmbiz 图片（正文必须至少一张）

**判断标准**：

**判断标准**：

## 工作流

```
获取文章内容（用户粘贴 / mmx vision） → 生成封面图 → 准备内容图 → 上传封面（thumb） → 上传内容图（mmbiz） → 写文章（含 mxbiz URL） → 创建草稿 → 完成
```

### 获取微信文章内容

> ⚠️ **重要更新（2026-05-17）**：9Router 两个实例均已下线，Anspire API (`api.anspire.cn`) DNS 从服务器环境不可达。Bocha Search API (`open.bocha.cn/api/v1/search`) 是当前最有希望的 Web 搜索备选，需用户提供 API Key。详见 `references/wechat-fetch-fallbacks.md`。

**当前可用方案（按可靠性排序）：**

1. **用户复制粘贴**（最可靠）：请用户打开微信文章 → 全选 → 复制正文 → 粘贴。不需要格式，纯文字即可
2. **mmx vision describe**：用户截图发给你 → AI 分析截图内容 → 作为写作参考
3. **Bocha Web Search API**（需要用户提供 key）：调用 `POST https://open.bocha.cn/api/v1/search`，可搜索到微信文章的标题/摘要/引用内容。格式：`{"query": "site:mp.weixin.qq.com <关键词>", "count": 10, "summary": true}`，Header：`Authorization: Bearer <BOCHA-API-KEY>`
4. **自己重写**（信息不完整）：根据标题/主题从 GitHub/官网/其他信息源重建内容

**已知无效方案（不要再试）：**
- 9Router fetch-combo / jina/fetch — 两个实例均返回 404
- Anspire Search — `api.anspire.cn` DNS 从服务器环境不可达（浏览器可访问 www.anspire.cn 但 API 域名无法解析）
- 搜狗微信搜索 — 超时不可用
- Scrapling StealthyFetcher / Browserbase CDP — WeChat 滑块验证码无法绕过
- Google Cache / Wayback Machine — 无缓存

> ⚠️ **微信滑块验证码是最后一层墙**：微信「混元AI」反爬系统在服务端直接拦截所有自动化请求，无需任何人机交互即可判断并返回验证页。**不要浪费时间尝试新工具**。

**⚠️ WeChat URL 项目识别陷阱（republish 场景）**：

当用户说「zhili publish [WeChat URL]」时，不要假设 URL 标题就是文章主题。**必须先用 `mmx search` 交叉验证实际项目名**：

```
# 错误假设：URL 路径中的关键词就是项目名
# 例：https://mp.weixin.qq.com/s/6SkupSxgM9618Y-O7ZJUbA
#     → 误以为是 CodeGraph（上一个项目）
#     → 实际是 academic-research-skills

# 正确做法：用 mmx search 查询文章标题
mmx search query "文章标题 全文"
# 从搜索摘要中提取真实项目名和 GitHub 地址
```

工作流：
1. 用 `mmx search` 搜索微信文章标题
2. 从搜索摘要中识别真实项目（很多微信文章标题不直接提 GitHub 地址）
3. 用 GitHub API 查真实项目的 stars / description / README
4. 以真实项目信息为准写文章，不要用上一个项目的上下文

**republish 场景的正确处理：** 用户粘贴已有公众号文章内容后，需要用自己的话重写核心观点（避免抄袭），按 format-guide.md 的 Evolver 六段式重组文章结构。

**获取内容后的处理：**
- 纯文字内容 → 按 format-guide.md 转换为公众号文章
- 如果用户粘贴的是已发布公众号文章 → 了解核心观点和结构 → 用自己的话重写（避免抄袭）

## 标准发布流程（重要经验）

### 完整顺序（必须按此顺序执行）

> 🚫 **图片 Gate 规则（已硬编码到 publish_zhili.py）**：
> HTML 正文中必须包含 `mmbiz` 图片 URL，否则脚本拒绝发布并报错退出。
> 这意味着：**必须在写 HTML 之前准备好图片，图片必须在 HTML 里可见才能发布**。

**第一步：准备图片**
1. 📝 标题 + 🏷️ 分类 + 🏷️ 原创
2. 🖼️ **封面图**（AI生成或项目README图）→ 上传 `material/add_material?type=image` → 获取 `media_id`（**不是 thumb_media_id**）
3. 📷 **内容图**（项目截图）→ 上传 `media/uploadimg` → 获取 `mmbiz URL`（公网URL）

**第二步：下载项目素材（发布前必须完成，不可跳过）**
项目截图/GIF 是文章的重要组成部分，**必须在写文章之前下载并上传**：
1. 用 GitHub API 查项目目录：`GET /repos/{owner}/{repo}/contents/` — 找 `screenshot`、`demo`、`assets` 等图片文件
2. 下载到 `/tmp/`：用 `?raw=1` 或 base64 解码 GitHub API 响应
3. 上传到微信永久素材：`upload_article_image()` → 获得 mmbiz URL
4. **记录每个 mmbiz URL 对应的插入位置**（如「section 二项目banner用」）
5. 写 HTML 时在对应位置嵌入 `<img src="mmbiz_url" ...>`

**常见项目素材路径（优先查这些目录）**：
```
README.md 同级的 .png/.gif/.jpg
assets/ 目录
docs/images/ 目录
screenshots/ 目录
/demo.gif 或 /demo.mp4
```

> ⚠️ 如果项目完全没有图片（只有 shields.io 徽章和文字），则：
> 1. 用 GitHub OG 图代替：`https://opengraph.githubassets.com/1/{owner}/{repo}`
> 2. 或 AI 生成一张技术示意图
> 3. 在 HTML 中明确标注「项目暂无截图，用 OG 图代替」
>
> **无项目素材时的备选方案：Python PIL 绘制信息结构图作为文章配图**
>
> 适用场景：概念解析类文章（如工作流、思维模型）而非项目介绍帖，无需真实项目截图。
> 方法：用 Python + Pillow 绘制包含图标、色块、标注的工作流示意图（见下方模板），保存为 PNG → 转 JPEG → `curl uploadimg` 上传。
>
> ```python
> # 核心模板：横向三阶段工作流 + 顶部标注 + 底部总结
> from PIL import Image, ImageDraw
> W, H = 900, 400
> img = Image.new('RGB', (W, H), (255, 255, 255))
> d = ImageDraw.Draw(img)
> # 背景网格：for y in range(0, H, 30): d.line([(0,y),(W,y)], fill=(245,245,250), width=1)
> # 三个圆角矩形：d.rounded_rectangle([x1,y1,x2,y2], radius=12, fill=颜色)
> # 箭头：d.polygon([(x,y1),(x+w,y2),(x,y2),(x,y1)], fill=颜色)  # 三角箭头
> # 底部总结框：d.rounded_rectangle([x1,y1,x2,y2], radius=10, fill=(255,245,220))
> img.save('/tmp/diagram.png', 'PNG', quality=95)
> ```
>
> **完整示例（prototype→rewind→summarize三阶段图）**：
> 见 `references/pil-workflow-diagram-example.py` — 可直接复制修改颜色和文案。

**第三步：写文章**
- HTML 中直接嵌入内容图的 mmbiz URL
- `<img src="http://mmbiz.qpic.cn/..." style="width:100%;border-radius:6px;" />`
- ⚠️ 如果用了带 `id="screenshot"` 的占位图（如 `<img src="placeholder" id="screenshot" />`），**替换时必须替换整个 attribute 字符串** `src="..." id="screenshot"`，不能只替换 `src` 值，否则会残留重复 style 属性或孤立的 id 属性。正确做法：`html = html.replace('src="placeholder" id="screenshot"', f'src="{mmbiz_url}" style="width:100%;border-radius:6px;"')`

**第四步：同步创建草稿**
- 封面用 `material/add_material?type=thumb` 返回的 `media_id`，传给 `draft/add` 的 `thumb_media_id` 字段
- 一次性传入：标题 + 作者 + 摘要 + 正文HTML + thumb_media_id
- 调用 `/cgi-bin/draft/add` → 获取草稿 `media_id`

> ⚠️ **已踩坑（2026-05-17 验证）**：`media/upload?type=thumb` 返回的 `thumb_media_id` 不兼容 `draft/add`，报 `40007 invalid media_id`。必须用 `material/add_material?type=thumb`，取其返回的 `media_id` 字段作为 `thumb_media_id`。

```
下载项目图 → 上传到微信获取mmbiz → 写HTML（嵌入mmbiz） → 图片Gate检查 → 创建草稿
```

---

## 凭证配置

在 `references/config.md` 中配置：

| 字段 | 说明 | 获取方式 |
|------|------|----------|
| `APPID` | 公众号 AppID | 微信公众平台 → 设置 → 基本配置 |
| `APPSECRET` | 公众号 AppSecret | 同上页面 |
| `CATEGORY_ID` | 分类 ID | 发布一次后从返回的 media_id 反推 |
| `SENSENOVA_KEY` | Sensenova API Key | 存储在 `TOOLS.md`，脚本自动读取（封面图首选） |
| `MINIMAX_API_KEY` | MiniMax API Key | platform.minimaxi.com 获取（封面图备选） |

> ⚠️ 凭证信息仅存储在 `references/config.md`，绝不输出到对话中。

## 封面图生成

### 封面图生成

> ⚠️ **9Router 路径不可用于 MiniMax 图片生成**：`POST /v1/images/generations` via 9Router 需要 OpenAI key server-side（`No active credentials for provider: openai`）。MiniMax 图片生成必须走**直接 API**。

### 方式一：MiniMax 直接 API（推荐）

MiniMax 图片生成走 `api.minimaxi.com/v1/image_generation`，需要从 `/root/.openclaw/openclaw.json` 读取 key：

```python
import json, re, ssl, urllib.request

with open('/root/.openclaw/openclaw.json') as f:
    raw = f.read()
m = re.search(r'"minimax"\s*:\s*\{.*?"apiKey"\s*:\s*"([^"]+)"', raw, re.DOTALL)
api_key = m.group(1)

url = "https://api.minimaxi.com/v1/image_generation"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
payload = {
    "model": "image-01",
    "prompt": "封面图描述，浅色背景+强对比",
    "aspect_ratio": "1:1",
    "response_format": "url",
}
req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
ctx = ssl.create_default_context()
ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
resp = urllib.request.urlopen(req, timeout=120, context=ctx)
data = json.loads(resp.read())
img_url = data["data"]["image_urls"][0]

# 下载并裁剪为 900x900
urllib.request.urlretrieve(img_url, "/tmp/cover_raw.jpg")
from PIL import Image
img = Image.open("/tmp/cover_raw.jpg")
w, h = img.size
cropped = img.crop(((w-900)//2, (h-900)//2, (w-900)//2+900, (h-900)//2+900))
cropped.save("/tmp/cover_900.jpg", "JPEG", quality=90)
```

**Key 来源**：`/root/.openclaw/openclaw.json` 中 `providers.minimax.apiKey`（注意是 `minimax` provider，不是 `MINIMAX_API_KEY` 环境变量）。

### 方式二：Sensenova（备用）

Sensenova key 从 TOOLS.md 读取（路径在 skill 配置中）。API 端点：`https://token.sensenova.cn/v1/images/generations`，model：`sensenova-u1-fast`。成功率不稳定，优先用 MiniMax 直接 API。

### 方式三：PIL 纯代码生成（无 API 依赖）

当 AI 图片生成 API 不可用时（如 9Router 图片模型返回 401、MiniMax 直连 404），用 Python + Pillow 生成技术信息图风格封面，**完全离线、零外部依赖**：

```python
from PIL import Image, ImageDraw, ImageFont
import math

W, H = 900, 383  # 信息结构图比例
img = Image.new('RGB', (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)

# 颜色常量
C = {
    'hub': (255, 185, 0),        # 金色中心
    'wechat': (0, 182, 84),
    'youtube': (255, 45, 45),
    'web': (0, 120, 212),
    'podcast': (142, 36, 170),
    'ppt': (250, 100, 0),
    'mindmap': (0, 150, 136),
}

# 中心 hub（发光效果）
hx, hy, HR = 450, 191, 48
for i in range(6):
    r = HR + 18 - i*3
    d.ellipse([hx-r, hy-r, hx+r, hy+r], fill=C['hub'])
d.ellipse([hx-HR, hy-HR, hx+HR, hy+HR], fill=C['hub'])
d.text((hx, hy), 'qiaomu', fill=(255,255,255), font=hub_font, anchor='mm')

# 输入节点（左）
for (cx, cy, icon, label, color) in inputs:
    R = 38
    d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=color)
    d.ellipse([cx-R+4, cy-R+4, cx+R-4, cy+R-4], outline=(255,255,255), width=2)

# 输出节点（右）
for (cx, cy, icon, label, color) in outputs:
    R = 34
    d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=color)
    d.ellipse([cx-R+3, cy-R+3, cx+R-3, cy+R-3], fill=(255,255,255))

# 连接线（带箭头）
def draw_arrow(d, x1, y1, x2, y2, color):
    d.line([(x1, y1), (x2, y2)], fill=color, width=2)

draw_arrow(d, 162, 191, hx-HR-4, hy, (180, 190, 210))  # 输入→hub
draw_arrow(d, hx+HR+4, hy, 740, 191, (180, 190, 210))   # hub→输出

img.save('/tmp/cover.png', 'PNG', quality=95)
```

**常用尺寸**：
- 信息结构图封面（横向）：900×383
- 标准方图封面：900×900

**高对比配色板**（适合技术产品封面）：
```python
C = {
    'hub':    (255, 185, 0),   # 金色（品牌色）
    'blue':   (0, 120, 212),   # 输入蓝
    'red':    (255, 45, 45),   # YouTube红
    'green':  (0, 182, 84),    # WeChat绿
    'purple': (142, 36, 170),  # Podcast紫
    'orange': (250, 100, 0),   # PPT橙
    'teal':   (0, 150, 136),   # 思维导图青
    'line':   (180, 190, 210), # 连接线灰
}
```

**上传封面到微信（mmbiz）**：
```python
import urllib.request, json, ssl, os

APPID = 'wx38a91c353554588a'
APPSECRET = '07b4dc2d64ddbe6f53707977dbabdbbe'

# 1. 获取 access_token
req = urllib.request.urlopen(
    f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}',
    timeout=10
)
access_token = json.loads(req.read())['access_token']

# 2. 上传封面（type=image，返回 media_id + url）
boundary = '----PythonFormBoundary123'
file_path = '/tmp/cover.png'
with open(file_path, 'rb') as f:
    file_data = f.read()
body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="media"; filename="cover.png"\r\n'
    f'Content-Type: image/png\r\n\r\n'
).encode() + file_data + f'\r\n--{boundary}--\r\n'.encode()

upload_url = f'https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={access_token}&type=image'
req = urllib.request.Request(upload_url, data=body, method='POST')
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
    result = json.loads(resp.read())
    print('mmbiz URL:', result['url'])       # 用于 img src
    print('media_id:', result['media_id'])   # 用于 draft.add thumb_media_id
```

### 方式四：跳过封面图

⚠️ `--skip-cover` 会创建无封面草稿，后台体验差。**推荐改用预生成封面图方案**（见下方）。

### 方式四：预生成封面图 + 创建草稿（推荐）

封面图和草稿分两次执行（封面图可复用）：

```bash
# ① 先生成封面图（保存到 /tmp/cover-thumb.jpg）
python3 skills/zhili-publish/scripts/publish_zhili.py --cover-only --cover-prompt "AI封面描述"

# ② 创建草稿（用 --cover-path 指定预生成封面）
python3 skills/zhili-publish/scripts/publish_zhili.py \
  "文章标题" \
  "作者（≤2个中文字）" \
  "摘要" \
  "$(cat /tmp/article.html)" \
  --cover-path /tmp/cover-thumb.jpg
```

> ⚠️ **重要**：`--title`、`--author` 等命名参数**只能配合 `--cover-prompt`（自动生成封面）**使用，不支持与 `--cover-path` 混用。必须用**位置参数**顺序传入。

> ⚠️ **标题长度警告**：脚本会提示「标题较长（XX字符），建议≤10个中文字」，这只是警告，实测超过 20 个中文字（~60 字节限制）才会真正报错（45003）。

### 封面图规格

- **生成尺寸**：1024×1024（MiniMax 限制）
- **上传尺寸**：裁剪为 900×900（中心裁剪，JPEG，85% 质量）
- **格式**：JPG/JPEG
- **用途**：永久素材，media_id 存入草稿

### 格式指南不是写作范本（重要警示）

`references/format-guide.md` 描述的是**格式元素清单**（标题公式、数据卡片、列表格式等），**不包含写作风格、语气、行文节奏、结构数量**。如果用户说「学习某篇文章的风格」，必须：

1. 用 `9Router /v1/web/fetch` + `fetch-combo` 抓取那篇文章的**正文全文**（不只是标题）
2. 分析那篇文章的**实际章节结构**（几段？每段主题？长短？节奏？）
3. 对照格式清单补齐结构元素
4. **同时学习那篇文章的写作风格**：语气（亲切/犀利/冷静）、句式长度、段落节奏、收尾方式

**Telegraf 风格是典型 7 段式**（非 format-guide 默认的 6 段）：
```
一、痛点切入（3-4个具体场景）
二、项目介绍 + 数据卡片 + 核心概念列表
三、架构设计 + 工作流图（代码块箭头流）
四、快速上手（Step 1/2/3 分层）
五、实战场景（多个真实案例，含失败→介入→成功弧线）
六、与竞品对比表
七、总结 + 收尾金句 + Star号召
```

**format-guide 是格式清单，不是行文模板**——具体写几段、每段多长，要跟着参考文章的实际结构走，不能套用死板的 6 段式。

### 封面图 Prompt 技巧

**核心原则：浅色背景 + 强对比 + 高辨识度**

微信卡片封面在浅色列表页展示，浅色背景 + 强对比色能让主体更突出、在封面序列中更抓眼。

| 文章类型 | Prompt 方向 | 示例 |
|----------|-------------|------|
| AI 工具 | **浅底科技感** + 工具图标 | A clean light-themed tech illustration with a glowing robot brain icon, vibrant blue and orange accents on a white background, minimal, modern style... |
| 教程类 | **浅色示意** + 操作界面 | A bright minimalist illustration of a terminal with colorful code on a clean light background, friendly and approachable... |
| 人物 IP | **浅色背景** + 有记忆点的形象 | Portrait illustration on a soft light gradient background, a developer at a futuristic desk, warm colors with sharp contrast... |
| 数据分析 | **白底图表** + 数字感 | Clean white background data visualization with vibrant glowing charts and sharp contrast, professional dashboard aesthetic... |

**通用 Prompt 模板（可叠加到任意类型）：**
```
on a clean white/light gray background, high contrast, vibrant accent colors (blue, orange, purple), minimalist modern style, flat design, no dark backgrounds
```

### ⚠️ CSS margin 规范（防止微信叠加空行的关键）

**所有 block 元素只能设 `margin-bottom`，不能用 `margin-top`**：
```html
<!-- ✅ 正确：只设 bottom，微信叠加后依然只有 16px；全文左对齐 -->
<p style="margin:0 0 16px 0;line-height:1.6;text-align:left;">正文内容</p>

<!-- ⚠️ 危险：上下都设时，微信容器级 margin 会叠加，产生非预期大间距 -->
<p style="margin:16px 0;line-height:1.6;text-align:left;">正文内容</p>

<!-- ✅ h2 标题：bottom 控制下方间距，top 为 0 防止被上方撑开，左对齐 -->
<h2 style="margin:24px 0 12px 0;font-size:18px;font-weight:bold;color:#111;text-align:left;">二、项目介绍</h2>

<!-- ✅ 图片：margin 控制与上下文的间距 -->
<img src="..." style="width:100%;border-radius:6px;margin:16px 0;" />
```

### ⚠️ HTML 格式规范（zhili-publish 强制标准）

发布任何文章到「直隶按察使」时，必须严格遵守以下 CSS 规格：

| 属性 | 值 | 说明 |
|------|-----|------|
| 行高 | `1.6` | 正文 line-height |
| 两侧间距 | `0 8px` | 容器 padding |
| 大标题 h2 | `font-size:18px;font-weight:bold` | 章节标题 |
| 正文字号 | `font-size:16px` | 所有正文段落 |
| 对齐方式 | `text-align:left` | **全部左对齐**，严禁居中或两端对齐 |
| 关键词高亮 | `<strong style="color:#e63946;">` | 重点语句红色 |
| 容器 | `max-width:678px;margin:0 auto;padding:0 8px;font-size:16px;line-height:1.6;color:#333;text-align:left;` | 文章正文外层 div |

> ⚠️ 2026-05-18 用户明确要求：所有文字格式左对齐。这不是可选的样式偏好，是强制要求。

### ⚠️ 代码块换行必须用 `<br>`，不能用真实换行符

```html
<!-- ✅ 正确：多行命令用 <br> 分隔 -->
<pre style="background:#1e1e1e;border-radius:6px;padding:14px 16px;margin:12px 0;overflow-x:auto;"><code style="font-family:Consolas,Monaco,Courier New,monospace;color:#e8e8e8;font-size:14px;line-height:1.5;">git clone https://github.com/nexu-io/html-anything&lt;br&gt;cd html-anything&lt;br&gt;pnpm install&lt;br&gt;pnpm dev</code></pre>

<!-- ❌ 错误：代码中有真实换行符会在草稿 JSON payload 里产生 \\n，微信渲染产生多余段落 -->
<pre style="..."><code style="...">git clone https://...
cd html-anything
pnpm install
pnpm dev</code></pre>
```

### ⚠️ execute_code sandbox 无法读取 config.md 凭证

`execute_code` 的 Python sandbox 与文件系统隔离，**看不到** `references/config.md` 中的 APPSECRET。遇到需要调用微信 API 的 Python 脚本时：

```bash
# ✅ 正确：写脚本到 /tmp，用 terminal python3 执行（能读取 config.md）
python3 /tmp/publish_article.py

# ❌ 错误：用 execute_code 内联包含 APPSECRET 的代码（sandbox 看不到 config.md）
```

**凭证必须从 terminal 中读取 config.md 后内联进脚本**，或用 `scripts/publish_zhili.py`（它已内置 `load_config()`）。

### ⚠️ 标题安全长度

微信限制标题 **≤60字节**（UTF-8 中文 = 3字节/字）：
- **安全范围**：≤50 字节（约 16 个中文字）
- 超过 60 字节会报 `errcode: 45003`（`title size out of limit`）
- 建议中文标题 ≤20 个字，英文 ≤50 字符

### ⚠️ cleanup_html.py 清理盲区

`cleanup_html.py` 只能移除**整行都是空白**的行。无法清除嵌在 HTML 标签**内部**的换行符：

```html
<!-- cleanup_html.py 处理不了这种块内部的换行 -->
<p style="margin:0 0 16px 0;line-height:1.6;">
  这是段落内容
</p>
```

**预防胜于清理**：生成阶段就不要在块内部写换行（inline 单行块 + `''.join()`）。

### 验证命令
```bash
# 统计纯空行数量（应为 0）
grep -c '^$' /tmp/article_draft.html

# 验证 JSON payload 不含意外换行（发布前最后一道检查）
python3 -c "
import json
with open('/tmp/article_draft.html') as f:
    html = f.read()
payload = {'content': html}
data = json.dumps(payload, ensure_ascii=False)
newlines = data.count('\\n')
print(f'JSON payload 换行符数量: {newlines} (应为 0)')
"
```

### ⚠️ 内容写作 → HTML 转换规则（format-guide 与草稿 HTML 的区别）

format-guide.md 中的 `**标题**` 和 `### 子标题` 是**内容写作阶段**的格式指引（用 Markdown 语法组织内容）。微信编辑器不会将 Markdown 转换为 HTML，**必须由 agent 在生成 HTML 时主动转换**：

| 内容写法（format-guide） | HTML 转换结果 |
|--------------------------|---------------|
| `**粗体文字**` | `<strong style="color:#e63946;">粗体文字</strong>` |
| `**一、项目名称**`（章节标题） | `<h2 style="font-size:18px;font-weight:bold;margin:24px 0 12px 0;color:#111;">一、项目名称</h2>` |
| `**小节标题**`（bold p 标签内） | `<p style="font-weight:bold;">小节标题</p>` — **不要嵌套 `<strong>`** |
| `### 子标题` | `<p style="font-weight:bold;">子标题</p>` — **去掉 `###` 前缀** |
| `• **概念名**：描述`（列表项） | `<li style="margin:0 0 4px 0;"><strong>概念名</strong>：描述</li>` — **不要手动加 `•`** |

**⚠️ 双重加粗陷阱**：`<p style="font-weight:bold;"><strong>**文字**</strong></p>` 会产生 `<strong>**文字**</strong>`（冗余）。正确做法是 p bold 标签内直接放纯文本。

**生成后必查**：
```bash
# 检查是否还有未转换的 ** 和 ###
grep -n '\*\*\|###' /tmp/article.html
# 应返回空
```

### 诊断工具：mmx CLI 图片分析（排查草稿截图）

`mmx vision describe` 是诊断微信草稿格式问题的首选工具（比内置 `vision_analyze` 更可靠）。

完整排版问题诊断参考：`references/wechat-draft-debug.md`（含有序列表渲染异常、多余空行、Markdown 残留、双重加粗、thumb_media_id invalid 等常见问题的根因和解决方案）。

```bash
# 安装 mmx CLI（全局）
npm install -g mmx-cli

# 登录（API key 从 ~/.hermes/.env 读取 MINIMAX_API_KEY）
bash -c 'source ~/.hermes/.env && mmx auth login --api-key "$MINIMAX_API_KEY"'

# 分析微信草稿截图
mmx vision describe "/path/to/screenshot.jpg" --prompt "分析这张微信公众号草稿截图，找出所有多余的空行、空白段落或格式问题。精确描述具体位置。" --output json
```

- 正文：`font-size:16px; line-height:1.6; margin:0 0 16px 0; padding:0 8px`
- 标题 h2：`font-size:18px; font-weight:bold`
- 小标题 h3：`font-size:17px; font-weight:bold`
- 代码块：深色背景 `#1e1e1e`，白色等宽字体
- 内联代码：`background:#f6f8fa; border-radius:3px; padding:1px 4px`
- 重点词红色高亮：`color:#e63946`
- 链接：`<a href="...">...</a>`
- 图片：`width:100%;border-radius:6px`

## 脚本使用

### 标准发布（无封面图）

```bash
python3 skills/zhili-publish/scripts/publish_zhili.py "<title>" "<author>" "<digest>" "<html_content>"
```

⚠️ **字段长度限制（超限会报 45003 错误，必须严格执行）**：
- 标题：**≤60字节**（UTF-8 中文 = 3字节/字，所以约 ≤20 个中文字；60字节约 8~10 个中文字安全）
- 作者：**≤2个中文字**（超出必报 `author size out of limit`）
- 摘要：建议≤50字

**常见报错**：
- `errcode: 45003` = 标题超长，必须缩短后重试
- `errcode: 0` + `media_id` = 成功

**实测结论（大段 HTML 的两种可行传参方式）：**

```python
# ✅ 方式一：Python API（推荐，sandbox 可见 config.md）
import sys
sys.path.insert(0, '/root/.hermes/skills/openclaw-imports/zhili-publish/scripts')
import publish_zhili as pz
token = pz.get_access_token(appid, appsecret)
thumb_media_id = pz.upload_thumb_material(token, '/tmp/cover.jpg')
with open('/tmp/article.html', encoding='utf-8') as f:
    content = f.read()
result = pz.create_draft(token, title, author, digest, content, thumb_media_id)

# ✅ 方式二：CLI + bash 命令替换（实测可用）
# 原理：$(python3 -c ...) 在 shell 层展开为 HTML 文本，作为第4个位置参数传入
python3 /path/to/publish_zhili.py \
  "文章标题" \
  "作者（≤2个中文字）" \
  "摘要" \
  "$(python3 -c \"import sys; sys.stdout.write(open('/tmp/article.html', encoding='utf-8').read())\")"
```

**更新已有草稿的正确顺序**：
1. 调用 `draft/delete?access_token=...` 删除旧草稿（必须先删）
2. 重新上传封面图 `add_material?type=image`（每次新建都要重新上传，不能复用旧 thumb_media_id）
3. 上传内容图 `media/uploadimg`
4. 调用 `draft/add` 创建新草稿
```

### 自动生成封面图发布

```bash
python3 skills/zhili-publish/scripts/publish_zhili.py \
  --title "文章标题" \
  --author "作者" \
  --digest "摘要" \
  --content "<html内容>" \
  --cover-prompt "AI 封面图描述"
```

### 仅生成封面图（不上传）

```bash
python3 skills/zhili-publish/scripts/publish_zhili.py --cover-only --cover-prompt "描述"
```

脚本自动完成：
1. **封面图生成**：调用 MiniMax image-01，1024×1024
2. **裁剪**：Pillow 中心裁剪为 900×900 JPEG
3. **上传**：微信永久素材 API（type=thumb）
4. **创建草稿**：含原创标志、封面 media_id

## ⚠️ format-guide 是格式清单，不是写作范本

`references/format-guide.md` 描述的是**格式元素清单**（标题公式、数据卡片、列表格式等），但**不包含写作风格、语气、行文节奏**。如果用户要求「按某篇文章的风格重写」，必须：

1. 先获取那篇文章的**正文内容**（不只是格式）
2. 对照格式清单补齐结构元素
3. **同时学习那篇文章的写作风格**：语气（亲切/犀利/冷静）、句式长度、段落节奏、收尾方式

**无法获取文章内容时的处理：**
- ⚠️ **微信文章有「混元AI」滑块验证码墙**：直接 curl / 浏览器 / Browserbase CDP 均无法绕过，会卡在"环境异常 → 去验证 → 滑块拼图"页面。这是微信的主动反爬，无法自动化突破。
- 备选：搜狗微信搜索（部分可查，但本次 session 测试超时不可用）
- **唯一可行方案：请用户把文章内容复制粘贴过来**（纯文字即可，不需要格式）

## ⚠️ 已发布草稿的自我检查清单（发布前必查）

- [ ] **先查格式指南**，对照清单补齐所有结构元素
- [ ] **再对标参考文章**，学习写作风格（不是只抄格式）
- [ ] 正文（二、项目介绍）中至少一张项目截图
- [ ] `**` Markdown 语法全部转为 HTML `<strong>`，无残留
- [ ] block 元素之间无换行符
- [ ] 代码块用 `<br>` 换行，不用真实换行符
- [ ] 所有间距只设 `margin-bottom`，不用 `margin-top`
- [ ] `grep -n '^$'` 确认 0 个空行

⚠️ **关键发现**：微信公众平台会过滤 `<style>` 标签和 CSS 类选择器，所有样式必须在 HTML 元素上直接用 `style="..."` 内联，否则格式全部失效。

### 正确的 HTML 结构（全部内联样式）

```html
<div style="max-width:678px;margin:0 auto;padding:0 8px;font-size:16px;line-height:1.6;color:#333;text-align:left;">
  <!-- 正文用内联 style，不使用 class，全部左对齐 -->
  <h2 style="font-size:18px;font-weight:bold;margin:24px 0 16px 0;padding-top:8px;text-align:left;">标题</h2>
  <p style="margin:0 0 16px 0;line-height:1.6;text-align:left;">正文内容</p>
  <pre style="background:#1e1e1e;border-radius:6px;padding:14px 16px;margin:16px 0;overflow-x:auto;"><code style="font-family:'Consolas','Monaco','Courier New',monospace;color:#e8e8e8;font-size:14px;line-height:1.5;">代码内容</code></pre>
  <strong style="color:#e63946;">重点强调</strong>
</div>
```

**⚠️ 代码块关键规则：**
- `<code>` 必须设置 `color:#e8e8e8`（浅灰白），否则微信渲染时文字与深色背景融为一体看不见
- 必须设置等宽字体：`font-family:'Consolas','Monaco',monospace`
- 字号 14px，行高 1.5
- 禁止裸 `<code>` 没有外层 `<pre>` 包裹

### 文章模板文件（强制使用）

⚠️ 写新文章时，**必须**从 `references/article-template.html` 复制模板作为起点，不要从零写 HTML。

模板路径：`references/article-template.html`

### ⚠️ 写文章前必读：Evolver 六段式格式对照（先读再写，不要写完再查）

⚠️ **本 session 教训**：写完文章后再查格式清单 = 被用户打回重写。正确做法是**写之前**就读一遍，写完立刻对照。

- `references/enforcement-gate.md` — 发布前强制图片检查 Gate 机制（check_article_images 函数 + 拦截逻辑）
- `references/project-screenshot-workflow.md` — 配图强制工作流：Step1下载→Step2上传→Step3记录位置→Step4写HTML嵌URL→Step5发布。核心原则：先拿mmbiz URL，后写HTML，不要倒过来。
- `references/format-guide.md`（Evolver 文章格式规范）

| 规范元素 | 格式要求 |
|----------|----------|
| 标题 | 数字 + 感叹 + 核心洞察 + 开源背景，如「8.9k stars！AI Agent 终于会自我进化了？中国团队开源的这个项目让我看到了智能体的未来！」 |
| 数据卡片 | `**GitHub**: url \| **Stars**: Xk \| **License**: XXX \| **Language**: XXX`（同行排列） |
| 核心概念列表 | `• **概念名（加粗）**：一句话定义 + 举例说明`，用 `•` 不要用 `<ul>` |
| 引擎职责列表 | `1. 2. 3. 4. 5.` 编号，每条 `**职责名**：描述` |
| 工作流图示 | `[步骤1] → [步骤2] → [步骤3]`，放在代码块中 |
| 实战案例 | `• **第N次尝试（状态）**：动作 + 结果`，含失败→介入→成功→创新弧线 |
| 技术亮点 | `**1. 标题**：解释文字`（编号列表，不是纯段落） |
| 收尾金句 | 有洞察力的判断句，用类比或行业判断收尾 |
| Star 号召 | `如果你觉得这个XXX有意思，欢迎 Star 支持开源 🧬` |
| 数据来源 | `📌 数据来源：GitHub Trending，YYYY-MM-DD | 项目：xxx` |

**⚠️ 高频踩坑：`**` Markdown 粗体残留（两种形态）**
生成 HTML 时，内容中的 `**文字**` 会被 agent 误写成 HTML 字符串 `**文字**` 而不是 `<strong>文字</strong>`。

**形态一（块级，容易发现）**：`**一、章节标题**` 写成 `<strong>**一、章节标题**</strong>` → grep 能查到
**形态二（行内，难发现）**：`这是段落内容**加粗**也是正文` 写成 `<p>这是段落内容**加粗**也是正文</p>` → grep 查不到，因为 `**` 不在行首

写完 HTML 后必查两步：
```bash
# 查块级残留
grep -n '\\*\\*' /tmp/article.html          # 应返回空

# 查行内残留（检查 content 属性中是否有未被 <strong> 包裹的 **）
python3 -c "
import re
with open('/tmp/article.html') as f:
    html = f.read()
# 找所有 ** 出现位置及上下文
for m in re.finditer(r'.{20}\*{2}.{20}', html):
    print(f'行内残留: ...{m.group()}...')
"
# 应返回空
```

**预防方法**：写 HTML 时用 Python 列表 + `''.join(blocks)` 拼接，不要在块内写任何 `**`。


### ⚠️ 格式合规必须在写文章之前检查，不是写完之后

**核心教训（本session深刻教训）**：格式检查必须在**提笔之前**做，不是在写完之后才检查。正确顺序：

```
获取项目信息（GitHub API + README）
    ↓
格式合规预检（对照下方清单确认格式要素齐全）
    ↓
开始写 HTML
    ↓
写完后验证 Markdown 残留（`**` 和 `###`）
    ↓
空行检查
    ↓
发布
```

**格式预检清单（下笔前必读）：**
- [ ] 标题公式：数字 + 感叹 + 核心洞察（参考格式指南）
- [ ] 数据卡片：GitHub · Stars · Language · License 同行
- [ ] 核心概念列表：5项 `• **概念名**：定义+举例
- [ ] 工作流图示：`[步骤1] → [步骤2] → [步骤3]`
- [ ] 实战案例：三次尝试弧线（失败→介入→成功→创新）
- [ ] 技术亮点：编号列表 `1. 2. 3. 4. 5.`
- [ ] 收尾金句 + Star号召 + 数据来源

### 格式检查清单（发布前必查）

- [ ] **写之前已读** `references/format-guide.md` 并对照六段式结构
- [ ] 从 `references/article-template.html` 模板开始写文章
- [ ] HTML 中无 `**`（Markdown bold 残留），`grep -n '\*\*' /tmp/article.html` 返回空
- [ ] 不使用 `<style>` 标签，全部样式内联
- [ ] 正文包裹容器：`style="max-width:678px;margin:0 auto;padding:0 8px;font-size:16px;line-height:1.6;"`
- [ ] 发布前必须执行空行清理（见下方「强制清理流程」，这一步不可跳过）
- [ ] **生成脚本检查**：确认脚本使用 `''.join(blocks)` 拼接 block，不使用 `'\n\n'.join()` 或多行字符串块
- [ ] block 元素（h2/h3/p/ul/ol/div/pre/blockquote）之间不能有换行，微信会识别为段落加间距——全部写成一行，无换行符
- [ ] 正文字号 16px，标题 h2 18px，h3 17px
- [ ] 行高 1.6，段间距 16px
- [ ] 列表禁止用 `<ul><li>` 和 `<ol><li>`（微信对两者都有渲染 bug），改用 `•` 符号 + `<p style="text-indent:-16px;padding-left:16px;">` 或 `①②③` + `<p>` 段落
- [ ] 所有间距只使用 `margin-bottom`，不使用 `margin-top` 或 `padding-top`
- [ ] block 元素之间无任何换行符
- [ ] 重点强调用 `<strong style="color:#e63946;">`
- [ ] 链接：`style="color:#1a73e8;"`
- [ ] **代码块 `<code>` 必须设置 `color:#e8e8e8` + 等宽字体**，不能用默认颜色（深色背景+默认黑色文字会看不见）
- [ ] **正文（二、项目介绍）中至少插入一张项目截图**（mmbiz URL 必须嵌入 HTML，脚本 Gate 会强制检查，无图则拒绝发布）

### ⚠️ HTML 拼接技术规范（防止多余空行的根本方法）

**问题根因**：用 Python 字符串列表 + `'\n\n'.join()` 或 `'\n'.join()` 拼接 HTML，会在每个 block 之间插入换行符，导致 JSON payload 的 `content` 字段携带 `\n`，微信渲染时将连续换行识别为段落分隔符，产生多余空白段落（视觉上表现为间隔点和空白行）。

**清理脚本的局限性**：`cleanup_html.py` 只能移除「纯空行」（整行都是空白），无法移除嵌在多行 HTML 块内部的新行。例如下面这段 HTML：
```html
<p style="margin:0 0 16px 0;">
  这是第一段内容
</p>

<p style="margin:0 0 16px 0;">
  这是第二段内容
</p>
```
`cleanup_html.py` 只能去掉 `}\n\n<p` 之间的空行，但块内部的 `\n  这是第一段内容\n` 依然存在。

**正确做法**：生成 HTML 时每个 block 完全写成一行，用 `''.join(blocks)` 直接拼接（零分隔符）。

```python
# ✅ 正确：每个块完全内联一行，块之间零分隔符
blocks = [
    '<p style="margin:0 0 16px 0;font-size:16px;line-height:1.8;color:#333;">第一段内容</p>',
    '<p style="margin:0 0 16px 0;font-size:16px;line-height:1.8;color:#333;">第二段内容</p>',
    '<h2 style="margin:24px 0 12px 0;font-size:20px;font-weight:bold;color:#111;">二、项目名是什么？</h2>',
    '<img src="..." style="width:100%;border-radius:6px;margin:16px 0;" />',
]
html_content = ''.join(blocks)  # ← 无任何分隔符，所有间距通过 style 属性控制

# ❌ 错误1：'\n\n'.join() —— JSON payload 携带 \n，微信渲染产生多余段落
html_content = '\n\n'.join(blocks)

# ❌ 错误2：多行字符串块 —— 块内部换行无法被 cleanup 移除
blocks = [
    '<p style="margin:0 0 16px 0;font-size:16px;">\n  第一段内容\n</p>',  # ← 块内部有换行
    '<p style="margin:0 0 16px 0;font-size:16px;">\n  第二段内容\n</p>',
]
html_content = '\n\n'.join(blocks)  # ← 双重错误

# ❌ 错误3：字符串列表 + '\n\n' 拼接后再写成多行
html = (
    '<p style="...">第一段</p>'
    + '\n\n'
    + '<p style="...">第二段</p>'
)
```

**所有间距通过 CSS `style` 属性的 `margin`/`padding` 控制**，不要依赖源码换行来产生间距。

**验证**：生成后用 `grep -n '^$' article.html` 检查是否有纯空行（应为 0）。如有，再用 `cleanup_html.py` 处理。

### ⚠️ 强制空行清理流程（预防为主，清理为辅）

**核心原则**：空行问题要预防在生成阶段，不要依赖清理作为主要手段。生成脚本必须遵守「inline 单行块 + `''.join()`」规范。

**生成后验证（必须执行）**：

```bash
# 检查是否有纯空行（应为 0）
grep -n '^$' /tmp/article_draft.html

# 如果有，执行清理（自动备份 .bak）
python3 scripts/cleanup_html.py /tmp/article_draft.html

# 再次验证
grep -n '^$' /tmp/article_draft.html  # 应仍为 0
python3 scripts/cleanup_html.py --check /tmp/article_draft.html  # 应返回 [OK] 0 空行
```

**验证通过标准**：0 个纯空行（`grep -n '^$'` 返回空，或 `--check` 返回 `[OK] ... 0 空行，干净`）

**重要**：`cleanup_html.py` 只能移除整行都是空白的行，无法移除 HTML 块内部的新行。如果生成阶段用了多行字符串块（错误写法），清理后依然会有新行残留，这时必须修复生成脚本重新生成。

## 发送图片到飞书

调用 `send_message` 时必须用**完整 target ID**（飞书 OC ID），不能用裸平台名：

```
# ✅ 正确
target="feishu:oc_034bc08420a2daed53561bfceba5b3bf"

# ❌ 错误（会报 invalid receive_id）
target="feishu"
```

先查 ID：`send_message(action='list')` → 返回 `feishu:oc_...` 格式。

## 典型完整流程

1. **从模板开始**：写新文章前，先复制 `references/article-template.html` 作为起点
2. 用户确认文章内容，选择发布
3. **检查文章 HTML 格式**（见上方格式检查清单）
4. 生成封面图 + 创建草稿
5. 告知用户 media_id，建议手动选择分类后发布

## 凭证配置

发布文章时，图片必须通过以下两步才能在草稿中正常显示：

### 配图位置：多图按章节嵌入，不是只有一张封面

| 文章章节 | 配图类型 | 插入位置 |
|----------|----------|----------|
| 二、项目介绍 | 项目截图 / banner | 项目简介段落下方 |
| 三、架构设计 | 架构图 / 工作流图 | 架构文字说明前 |
| 五、实战场景 | demo GIF / 操作视频 | 场景描述下方 |

**流程**：先上传所有正文图获取 mmbiz URL → 按位置写入 HTML → 最后发布草稿（封面图单独走 add_material）。

### 第一步：上传图片获取公网 URL

⚠️ **不要**用 `add_material?type=image`（返回 media_id，无法直接渲染）
✅ **正确做法**：用 `media/uploadimg` 接口（返回公网 URL，可直接用于 img src）

```python
# 正确方式：返回公网 URL（用于 img src）
POST /cgi-bin/media/uploadimg?access_token=...
→ {"url": "http://mmbiz.qpic.cn/mmbiz_png/.../0?from=appmsg"}

# 注意：add_material?type=image 返回的是 media_id，不适合直接做 img src
# 只有 thumb 用 add_material?type=thumb（返回 media_id）
# 内容图必须用 media/uploadimg（返回公网 URL）
```

### 第二步：用返回的 URL 嵌入文章 HTML

```html
<img src="http://mmbiz.qpic.cn/mmbiz_png/.../0?from=appmsg" style="width:100%;border-radius:6px;" />
```

### 完整流程（Python）

```python
import json, urllib.request, ssl

def upload_article_image(token, image_path):
    """上传文章内容图片，返回公网 URL"""
    url = f"https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token={token}"
    boundary = "----PythonFormBoundary123456789"
    with open(image_path, 'rb') as f:
        file_data = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="img.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
        resp = json.loads(r.read())
        return resp['url']  # 直接返回公网 URL

# 用法
img_url = upload_article_image(token, '/path/to/image.png')
html = f'<img src="{img_url}" style="width:100%;border-radius:6px;" />'
```

### 内容图获取技巧

- **GitHub OG 社交预览图（最通用）**：`https://opengraph.githubassets.com/1/{owner}/{repo}` — 无需认证，直接返回 1200×600 PNG，适合做正文配图/项目 banner。**优先使用**，即使 README 无图也能获取。
- **GitHub user-attachments 公开资产**：`https://github.com/user-attachments/assets/<hash>` 是 GitHub 公开 CDN，curl 直接可下载（无需认证），通常是 README 内嵌的截图/GIF。例：`curl -s -L "https://github.com/user-attachments/assets/f168182f-4d9a-44e0-94d7-08d018cc8a3a" -o /tmp/demo.png --max-time 30`。**这类图片质量高、与项目内容高度相关，优先于 OG 图使用。**
- **GitHub 项目 README 图**：用 `https://api.github.com/repos/{owner}/{repo}/contents/{path}` + `Accept: application/vnd.github.raw+json` 获取 raw URL
- **GitHub 社交预览图备选**：`https://opengraph.github.com/?repo=owner%2Frepo`（可能返回 404）
- **截图 fallback**：若项目既无 README 图也无 OG 图，用 AI 生成一张技术示意图代替
- 裁剪封面图：`Pillow` 中心裁剪 + 缩放到 900×900

### 封面图 vs 内容图片

| 类型 | 接口 | 返回值 | 用途 |
|------|------|--------|------|
| 封面图（缩略图） | `material/add_material?type=image` | **media_id**（注意不是 thumb_media_id 字段） | 草稿封面，传给 draft/add 的 `thumb_media_id` 字段 |
| 文章内容图 | `media/uploadimg` | url（公网） | 草稿正文 img src |

> ⚠️ **封面图必须用 `type=image`（不是 `type=thumb`）**：`media/upload?type=thumb` 返回的 `thumb_media_id` 格式不兼容 `draft/add`，会报 `invalid media_id`。正确做法是用 `material/add_material?type=image` 上传 JPEG/PNG，将返回的 `media_id` 字段作为 `thumb_media_id` 传入草稿。

## 已知限制

| 功能 | 状态 | 解决方案 |
|------|------|----------|
| 部分分类 | ⚠️ category_id 不稳定 | 手动在后台选择「GitHub好项目推荐合集」 |
| 直接群发 | ❌ 个人号无权限 | 草稿箱手动发布 |
| 格式丢失 | ⚠️ HTML 无内联样式时平台渲染异常 | 发布前按格式规范检查文章 HTML 结构 |
| 草稿图片不显示 | ⚠️ API 返回的 media_id 直接用无法渲染 | 必须用 `media/uploadimg` 返回的公网 URL |
| 中文乱码 | ⚠️ 读取 HTML 文件时必须指定 `encoding="utf-8"`，否则中文变 Unicode 转义序列 | 用 `json.dumps(ensure_ascii=False)` + `encode("utf-8")` |
| raw.githubusercontent.com 超时 | ⚠️ GitHub raw 文件无法直接下载 | 用 `api.github.com/repos/{owner}/{repo}/contents/{path}` + base64 解码 |
| mmx vision describe 替代 vision_analyze | `vision_analyze` 工具返回 401 时，`mmx vision describe` CLI 仍可用 | `mmx vision describe "/path/to/screenshot.jpg" --prompt "..."` |
| 微信草稿有序列表（`<ol>`）渲染异常 | 有序列表第 1、3 项在预览中显示为空，但 HTML 源码所有 `<li>` 完整；去掉 `<strong>` 后仍无法解决 | **根因**：WeChat 编辑器对 `<ol><li>...</li></ol>` 结构有渲染 bug，原因不明。**已验证的 definitive 解决方案**：将整个 `<ol>` 替换为 `①②③④⑤` 前缀的 `<p>` 段落。示例：`<ol><li>文本正则化（TN）...</li><li>Grapheme-to-Phoneme（G2P）...</li>...</ol>` → `<p style="margin:0 0 6px 0;font-size:15px;line-height:1.6;">① 文本正则化（TN）...</p><p style="margin:0 0 6px 0;font-size:15px;line-height:1.6;">② Grapheme-to-Phoneme（G2P）...</p>`。每项 `margin:0 0 6px 0`，行高 `line-height:1.6`。**不要再用 `<ol>` 或 `<ul>`**，一律用带圈数字前缀的 `<p>` 段落代替有序列表。 |
| WeChat `uploadimg` 返回 40137 格式错误 | PNG 图片上传失败 | WeChat `uploadimg` 只接受 JPEG，PNG 一律转 JPEG 再上传。若 PIL 报 `image file is truncated`，说明源文件损坏，需找其他图片 |
| `urllib.request` multipart 上传报 41005 | Python urllib.request 上传图片返回 `media data missing` | 改用 subprocess + curl：`curl -s -F 'media=@img.jpg' 'https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN&type=image'` |
| execute_code 的 Python sandbox 看不到 `~/.hermes/.env` 中的 API Key | `os.environ.get('MINIMAX_API_KEY')` 返回空（sandbox 环境隔离） | 用 `bash -c 'source ~/.hermes/.env && python3 -c "import os; print(os.environ[...])"'` 或直接用 `terminal` 执行含凭证的脚本 |
| WeChat `access_token` 缓存路径 | sandbox 内写 `~/.hermes/mp_token_cache.json` 后，sandbox 下次运行看不到（路径重置） | WeChat API 调用必须在 `terminal` 执行，或通过 `scripts/publish_zhili.py`（它从 `load_config()` 读取 APPSECRET 后内联进脚本）调用 |
| mmx CLI 读取 `~/.hermes/.env` | mmx CLI 用 Node.js 读取环境变量，直接 `mmx auth login` 会报 key 无效 | 用 `bash -c 'source ~/.hermes/.env && mmx auth login --api-key "$MINIMAX_API_KEY"'` 确保环境变量展开 |
