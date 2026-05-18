# 微信草稿排版问题诊断手册

## 有序列表（`<ol>`）渲染异常

**现象**：HTML 源码中 `<ol>` 的所有 `<li>` 项完整，但微信编辑器预览中部分序号后无内容显示。

**典型案例**（Supertonic 草稿）：
```
预览显示：
1.                    ← 内容为空
2. 文本正则化          ← 正常
3.                    ← 内容为空
4. Grapheme-to-Phoneme ← 正常
5. 流式输出            ← 正常

源码（完整）：
<ol>
  <li>文本正则化（TN）：将数字...<li>
  <li>Grapheme-to-Phoneme（G2P）...
  <li>声学模型推理：将音素序列...
  <li>声码器（Vocoder）：将 mel 频谱...
  <li>流式输出：支持分块合成...
</ol>
```

**根因（已确认）**：`<li>` 内含 `<strong>` 标签时，WeChat 编辑器渲染异常，导致序号后内容为空。

**修复方法**：去掉所有 `<li>` 内的 `<strong>` 标签，改用纯文本。

```html
<!-- ❌ 有 <strong> 导致渲染异常 -->
<ol>
  <li><strong>文本正则化（TN）</strong>：将数字、缩写...→ 预览中显示为空</li>
  <li><strong>Grapheme-to-Phoneme（G2P）</strong>：将文字转化为音素...→ 正常</li>
</ol>

<!-- ✅ 纯文本，正常显示 -->
<ol>
  <li>文本正则化（TN）：将数字、缩写...→ 预览正常</li>
  <li>Grapheme-to-Phoneme（G2P）：将文字转化为音素...→ 预览正常</li>
</ol>
```

**排查步骤**：
1. 读取草稿 HTML 源码，确认所有 `<li>` 项在源码层面完整
2. 检查 `<li>` 内是否有 `<strong>` 标签——这是渲染异常的根因
3. 若有 → 去掉 `<strong>`，保留纯文本 → 重建草稿
4. 若无 → 可能是其他 WeChat 编辑器 bug，尝试重建草稿

**mmx vision describe 诊断命令**：
```bash
bash -c 'source ~/.hermes/.env && mmx vision describe "/path/to/screenshot.jpg" --prompt "精确描述这张微信公众号草稿截图里，哪些列表项（有序或无序）只有序号/圆点但没有文字内容。列出具体序号。" --output json'
```

---

## 多余空行（blank lines between blocks）

**根因**：Python 生成 HTML 时 block 元素间用了 `'\\n\\n'.join()` 或多行字符串块，导致 JSON payload 携带 `\\n`，微信将连续换行渲染为额外段落。

**表现**：
- `<p>` 标签之间出现孤立圆点 `•`（微信把空段落渲染成了列表项符号）
- 本应是紧凑段落的区域出现大段空白

**排查**：
```bash
# 1. 检查 HTML 源码是否有纯空行
grep -n '^$' /tmp/article.html

# 2. 检查 JSON payload 中的换行符数量
python3 -c "
import json
with open('/tmp/article.html') as f:
    html = f.read()
payload = json.dumps({'content': html}, ensure_ascii=False)
print(f'换行符: {payload.count(chr(10))} (应为 0)')
"
```

**解决方案**：
- 生成阶段：每个 HTML block 完全写成一行，用 `''.join(blocks)` 拼接
- 清理阶段：`cleanup_html.py` 移除纯空行（但无法清除块内部换行）
- 最干净方案：inline 单行块 + `''.join()`

---

## Markdown 语法残留（`**`、`###`、`•`）

**现象**：草稿预览中 `**文字**` 原样显示、`### 标题` 显示为普通文本、`•` 出现在列表项内形成双重 bullet。

**根因**：format-guide.md 使用 Markdown 语法写内容，但微信编辑器不转换 Markdown，必须 agent 主动转 HTML。

**生成后必查**：
```bash
# 应返回空
grep -n '\\*\\*\\|#\#\\|#•' /tmp/article.html
```

| 内容写法 | 正确 HTML |
|----------|-----------|
| `**粗体**` | `<strong>粗体</strong>` |
| `### 子标题` | `<p style="font-weight:bold;">子标题</p>` |
| `• **概念**：描述` | `<li><strong>概念</strong>：描述</li>` |

---

## 双重加粗陷阱

**现象**：预览中 `**<strong>文字</strong>**` 原样显示。

**根因**：p 已有 `font-weight:bold`，内部又套了 `<strong>`，导致 Markdown `**` 未被解析为标签的一部分直接输出。

**正确做法**：
```html
<!-- ✅ p bold 标签内直接放纯文本 -->
<p style="font-weight:bold;margin:0 0 8px 0;font-size:16px;">核心概念</p>

<!-- ❌ 嵌套 strong -->
<p style="font-weight:bold;margin:0 0 8px 0;font-size:16px;"><strong>核心概念</strong></p>

<!-- ❌ Markdown 未转义，** 原样显示 -->
<p style="font-weight:bold;margin:0 0 8px 0;font-size:16px;">**核心概念**</p>
```

---

## draft/add 返回值误判（item/ad_count 不是错误）

**现象**：调用 `draft/add` 返回如下 JSON，agent 误判为失败：
```json
{
  "media_id": "kiuyle4KZ...",
  "item": [{"index": 0, "ad_count": 2}]
}
```

**正确理解**：
- `errcode: 0`（隐含）= API 调用成功
- `media_id` 存在 = 草稿已创建
- `item` 数组含 `ad_count` = 广告素材计数（正常返回，不代表失败）

**正确判断**：
```python
# ✅ 正确
if draft_result.get('errcode') == 0 and draft_result.get('media_id'):
    print(f"✅ 草稿创建成功，media_id: {draft_result['media_id']}")

# ❌ 误判：检查 'item' in draft_result → 永远为 True（item 存在=失败？）
if 'item' in draft_result:
    print("失败")  # 错误判断
```

**备用验证**：调用 `draft/count` 确认草稿总数是否增加。

---

## thumb_media_id 报错 invalid（40007）

**错误**：`errcode: 40007, errmsg: invalid media_id hint`

**常见原因**：

| 上传接口 | type 参数 | 返回字段 | 能否用于 draft/add thumb_media_id |
|----------|-----------|----------|-----------------------------------|
| `media/upload` | `type=thumb` | `thumb_media_id` | ❌ 不兼容 |
| `material/add_material` | `type=thumb` | `media_id` | ❌ 不兼容 |
| `material/add_material` | `type=image` | `media_id` | ✅ 正确 |

**正确做法**：
```python
# 用 type=image 上传封面图
resp = requests.post(
    f'https://api.weixin.qq.com/cgi-bin/material/add_material'
    f'?access_token={token}&type=image',
    files={'media': ('cover.jpg', img_data, 'image/jpeg')}
)
media_id = resp.json()['media_id']  # ← 拿这个当 thumb_media_id

# 创建草稿
draft_payload = {
    "articles": [{
        "title": "...",
        "thumb_media_id": media_id,  # ← 传入上面的 media_id
        ...
    }]
}
```
