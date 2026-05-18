# 微信文章 HTML 格式反模式 & 已解决问题记录

## 2026-05-15 发现：图片上传格式错误（40137）+ curl 优于 urllib

**错误**：`{"errcode":40137,"errmsg":"invalid image format hint"}`

**根因**：WeChat `uploadimg` 接口只接受 JPEG，不接受 PNG。

**实测**：
| 文件 | 格式 | 上传结果 |
|------|------|----------|
| `supertonic_hero.png`（708KB） | PNG | ❌ 40137 |
| `supertonic_og.png`（52KB） | PNG | ❌ 40137 |
| `supertonic_body.jpg` | JPEG | ✅ 成功 |

**解决**：PNG 转 JPEG，或找其他 JPEG 图片。若 PIL 报 `OSError: image file is truncated`，说明图片文件损坏，需另找来源。

**附加发现**：`urllib.request` multipart 上传报 `41005 media data missing`，用 subprocess + curl 则正常：
```bash
curl -s -F 'media=@/path/to/image.jpg' \
  'https://api.weixin.qq.com/cgi-bin/media/uploadimg?access_token=TOKEN&type=image'
```

---

## 2026-05-15 发现：`<ol><li>` 内含 `<strong>` 导致渲染异常

**现象**：有序列表 `<ol>` 中，部分 `<li>` 序号后无内容（源码完整）。

**根因**：`<li>` 内含 `<strong>` 标签时，WeChat 编辑器渲染异常。

```html
<!-- ❌ 渲染异常：li 内含 strong -->
<li><strong>文本正则化（TN）</strong>：将数字...</li>

<!-- ✅ 正常：去掉 strong -->
<li>文本正则化（TN）：将数字...</li>
```

**结论**：列表项内容不要用 `<strong>` 加粗，改用纯文本。

---

## 2026-05-15 发现：session 脚本 `publish_html.py` 的双重错误

### 问题
`/tmp/publish_html.py` 生成微信草稿时：
1. HTML block 拼接用 `'\n\n'.join(blocks)` → JSON payload content 字段携带 `\n`
2. 每个 block 内部写成多行字符串 → 块内部有换行符

### 症状
微信文章预览中出现多余空白段落（视觉上表现为间隔点、段落间空白行）。

### 根因分析
`cleanup_html.py` 只能移除「整行为空」的行（`line.strip() == ''`），无法移除：
- JSON payload 中 block 间的 `\n\n`（这是 JSON 字符串值的一部分，不是文件中的独立空行）
- HTML 块内部的多行字符串换行（`'<p>...\n...</p>'` 的内部 `\n`）

### 修复
生成阶段必须遵守：
```python
# 每个块完全内联写成一行
blocks = [
    '<p style="...">第一段内容</p>',  # 单行，无内部换行
    '<p style="...">第二段内容</p>',
]
html_content = ''.join(blocks)  # 零分隔符
```

验证：
```bash
grep -n '^$' /tmp/article.html  # 应返回空
```

---

## 已知问题模式

| 模式 | 结果 | 正确做法 |
|------|------|----------|
| `''.join()` 无分隔符拼接 | block 直接拼接，零换行 | ✅ 标准做法 |
| `'\n\n'.join(blocks)` | JSON payload 带 `\n`，微信渲染多段落 | `''.join(blocks)` |
| 多行字符串块 | 块内部换行无法被 cleanup 移除 | block 完全内联单行 |
| `**bold**` 直接写在 HTML 里 | WeChat 原样显示 `**` 符号 | 生成 HTML 前先将 `**text**` 转为 `<strong>text</strong>` |
| `### 三级标题` 直接写在 HTML 里 | WeChat 原样显示 `###` 符号 | 去掉 `###` 前缀，用 `<p style="font-weight:bold">` |
| `<p bold>` 内嵌套 `<strong>**text**</strong>` | 双重加粗 | 纯文本 p bold 标签内直接放文字，不加 strong |

## 2026-05-15 发现：Markdown 语法写在 HTML 里被微信原样显示

### 正确转换规则

| 内容格式 | HTML 写法 |
|----------|-----------|
| `**粗体文字**` | `<strong style="color:#e63946;">粗体文字</strong>` |
| `**一、痛点切入**`（章节标题） | `<h2 style="...">一、痛点切入</h2>` |
| `**核心概念**`（小节 bold 标题） | `<p style="font-weight:bold;">核心概念</p>`（不要嵌套 `<strong>`） |
| `### 环境要求`（子标题） | `<p style="font-weight:bold;">环境要求</p>`（去掉 `###`） |
| `• **需求**：描述`（列表项） | `<li style="margin:0 0 4px 0;"><strong>需求</strong>：描述</li>`（不要手动加 `•`，WeChat 自带） |

### ⚠️ 双重加粗陷阱
```html
<!-- ❌ 双重加粗 -->
<p style="font-weight:bold;"><strong>**核心概念**</strong></p>

<!-- ✅ 正确 -->
<p style="font-weight:bold;">核心概念</p>
```

### 验证命令
```bash
# 检查是否还有未转换的 ** 和 ###
grep -n '\*\*\|###' /tmp/article.html  # 应返回空

# 检查是否有 • 符号出现在 <li> 内
grep -n '<li[^>]*>[^<]*•' /tmp/article.html  # 应返回空
```

---

## WeChat 渲染器行为备注

WeChat 公众平台的 HTML 渲染器会对以下情况产生额外段落：
- `content` 字段 JSON 值中连续出现的 `\n`（即使在 JSON 字符串内部）
- HTML 源码中的连续空行（`<p>...</p>\n\n<p>...</p>`）

**结论**：生成阶段零换行是唯一可靠方案，cleanup 是辅助验证而非主要修复手段。
