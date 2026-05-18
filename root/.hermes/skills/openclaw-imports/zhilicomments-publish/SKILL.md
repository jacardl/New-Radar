---
name: zhilicomments-publish
description: >
  微信公众号短评论发布技能，专为「直隶按察使」公众号定制。
  适用：一事一议的短观点、热评reaction、资讯点评（500-800字，1-2张图）。
  触发条件：用户说「评论」「热评」「观点」「点评」「说两句」。
---

# 直隶按察使 · 短评论发布技能

## 与 zhili-publish 的区别

| | zhili-publish | zhilicomments-publish |
|--|---------------|----------------------|
| 字数 | 1500-2500字 | 500-800字 |
| 结构 | Evolver 六段式 | 轻量三段式 |
| 配图 | 项目截图+封面 | 1-2张评论配图 |
| 用途 | 项目介绍/教程 | 热评/观点/Reaction |

## 内容格式（轻量三段式）

### 写作引擎：khazix-writer

> ⚠️ 短评论内容由 **khazix-writer** skill 生成。不是写 prompt，是直接调用 skill。用法：`skill_view(name='khazix-writer')` 后，让 AI 以卡兹克的风格写一篇 500-800 字的短评论。
>
> 卡兹克短评论的核心特征：
> - 619字左右的轻量篇幅（长文是 2000-4000字）
> - 一句话断裂成段制造节奏感
> - 观点鲜明，有立场不做理中客
> - 结尾用反问或金句收，不求 Star/转发
>
> 本 session 实例（2026-05-17）：黄仁勋 CS 专业观点文，619字，风格=卡兹克口语+短句断裂+明确立场。

### 一、事件/现象（100-150字）
一句话描述要评论的事件，2-3句背景，让读者知道发生了什么。

### 二、核心观点（300-400字）
- 一句话亮出观点（加粗）
- 2-3个支撑点（用列表）
- 举一个具体例子或反例

### 三、一句话收尾（50字以内）
用金句或反问收尾，不需要号召行动。

## HTML 格式规范（强制标准）

发布任何短评到「直隶按察使」时，必须遵守以下 CSS 规格：

| 属性 | 值 |
|------|-----|
| 行高 | `1.6` |
| 两侧间距 | `0 8px` |
| 大标题 h2 | `font-size:18px;font-weight:bold` |
| 正文字号 | `font-size:16px` |
| 对齐方式 | `text-align:left`（2026-05-18 用户明确要求） |
| 关键词高亮 | `<strong style="color:#e63946;">` |
| 容器 | `max-width:678px;margin:0 auto;padding:0 8px;font-size:16px;line-height:1.6;color:#333;text-align:left;` |

## 发布流程

```
获取内容 → 生成/下载配图 → 上传封面 → 写HTML → 创建草稿 → 完成
```

### 第一步：获取内容
用户提供：
- 评论对象（链接/标题/截图）
- 核心观点（一句话）
- 支撑素材（可选）

### 第二步：配图（可选）
短评论可以无图，但如果配图：
1. 用 PIL 生成信息图（900×383 或 900×900）：`/tmp/cover.jpg`
2. 上传获取 `media_id`：

```bash
# 必须用 type=thumb，返回的 media_id 才能用于 draft/add
curl -F "media=@/tmp/cover.jpg" \
  "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=${TOKEN}&type=thumb"
```

返回字段中的 `media_id` 即为 `thumb_media_id`。

> ⚠️ **不能用 `type=image`**：用 `type=image` 上传返回的 media_id 在 `draft/add` 时会报 `40007 invalid media_id`。必须 `type=thumb`。

### 第三步：写 HTML

```html
<div style="max-width:678px;margin:0 auto;padding:0 8px;font-size:16px;line-height:1.6;color:#333;text-align:left;">
  <h2 style="font-size:18px;font-weight:bold;margin:24px 0 12px 0;text-align:left;">一、事件</h2>
  <p style="margin:0 0 16px 0;text-align:left;">描述内容...</p>
  <h2 style="font-size:18px;font-weight:bold;margin:24px 0 12px 0;text-align:left;">二、观点</h2>
  <p style="margin:0 0 16px 0;text-align:left;"><strong style="color:#e63946;">核心观点一句话。</strong>展开描述...</p>
  <ul style="margin:0 0 16px 0;padding-left:20px;text-align:left;">
    <li style="margin:0 0 8px 0;"><strong>观点1：</strong>支撑内容</li>
    <li style="margin:0 0 8px 0;"><strong>观点2：</strong>支撑内容</li>
  </ul>
  <h2 style="font-size:18px;font-weight:bold;margin:24px 0 12px 0;text-align:left;">三、一句话</h2>
  <p style="margin:0 0 16px 0;font-style:italic;text-align:left;">金句收尾。</p>
</div>
```

### 第四步：创建草稿

调用微信 API：
```bash
# 获取 access_token
curl "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=${APPID}&secret=${APPSECRET}"

# 上传封面（type=image）
curl -F "media=@/tmp/cover.jpg" "https://api.weixin.qq.com/cgi-bin/material/add_material?access_token=${TOKEN}&type=image"

# 创建草稿
curl -X POST "https://api.weixin.qq.com/cgi-bin/draft/add?access_token=${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "articles": [{
      "title": "标题",
      "author": "卡兹克",
      "digest": "摘要",
      "content": "<div>...</div>",
      "thumb_media_id": "media_id",
      "need_open_comment": 1,
      "only_fans_can_comment": 0
    }]
  }'
```

## 凭证配置

同 `zhili-publish`，从 `references/config.md` 读取：
- APPID
- APPSECRET
- CATEGORY_ID

## 封面图规格

- 尺寸：900×383（信息图比例）或 900×900（方图）
- 风格：深色背景 + 高对比文字，观点鲜明
- 可用 PIL 纯代码生成

## 注意事项

- 标题 ≤20个字
- 正文配图可选（zhili-publish 强制要图，comments 可选）
- 观点要有立场，不做理中客
- 结尾不求 Star/项目地址，纯观点文
