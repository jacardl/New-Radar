# 配图工作流：先拿 URL，后写 HTML

## 核心原则（一句话）

> **永远不要在拿到 mmbiz URL 之前写 HTML。**

发布脚本的 `check_article_images()` Gate 会拦截无图发布，但这意味着你会在最后一步被打回来重新上传图片、重新写 HTML、重新发布——浪费时间。

**正确的顺序是把图片工作做在前面**，这样写 HTML 时直接填入 URL，不用返工。

---

## 强制执行顺序

```
Step 1  下载项目截图/GIF/视频
Step 2  上传到微信 media/uploadimg，获取 mmbiz URL
Step 3  记录每个 URL 对应的「插入位置」（如：section 二 banner、section 五 demo）
Step 4  写 HTML — 在对应位置直接嵌入 <img src="mmbiz_url">
Step 5  发布 — Gate 会检查 HTML 中的 mmbiz URL（这时一定有了）
```

**违反这个顺序 = 被 Gate 拦截 = 返工**

---

## 具体操作

### Step 1: 下载项目截图

```bash
# 查项目有哪些图片
curl -s "https://api.github.com/repos/{owner}/{repo}/contents" | python3 -c "import sys,json; data=json.load(sys.stdin); [print(f['name'], f.get('download_url','')) for f in data if isinstance(f,dict) and f.get('type')=='file' and any(f['name'].endswith(ext) for ext in ['.png','.gif','.jpg','.jpeg'])]"

# 备选：GitHub OG 图（总有，除非项目私有）
curl -s "https://github.com/{owner}/{repo}" | grep -o 'https://opengraph.githubassets.com[^"]*' | head -1

# 下载到 /tmp/
curl -s "https://opengraph.githubassets.com/.../{owner}/{repo}" -o /tmp/project_og.png
```

**常见项目图片目录**（优先查这些）：
```
README.md 同级
assets/
docs/images/
screenshots/
demo.gif / demo.mp4
```

**项目完全没有图片时**：用 GitHub OG 图（见上面 curl 命令），在 HTML 中标注「项目暂无截图，用 GitHub OG 图代替」。

### Step 2: 上传到微信获取 mmbiz URL

```python
import sys
sys.path.insert(0, '/root/.hermes/skills/openclaw-imports/zhili-publish/scripts')
import publish_zhili as pz

config = pz.load_config()
token = pz.get_access_token(config['APPID'], config['APPSECRET'])

# 项目截图 → mmbiz URL（正文用）
img_url = pz.upload_article_image(token, '/tmp/project_og.png')
print(img_url)  # http://mmbiz.qpic.cn/mmbiz_png/...

# 封面图（单独流程）→ media_id
thumb_media_id = pz.upload_thumb_material(token, '/tmp/cover.jpg')
```

### Step 3: 记录插入位置

用简单注释记录，不要凭记忆：

```
kiuyle4KZHC7JK...  →  section 二、项目介绍 banner
kiuyle4KZHC7JK...  →  section 五、实战场景 demo GIF
```

### Step 4: 写 HTML 时直接嵌入

```html
<h2 style="...">二、xxx 是什么？</h2>
<img src="http://mmbiz.qpic.cn/mmbiz_png/kiuyle4KZHC7JK.../0?from=appmsg" style="width:100%;border-radius:6px;margin:12px 0;" />
<p style="...">项目简介正文...</p>
```

### Step 5: 发布

```bash
python3 scripts/publish_zhili.py "标题" "作者" "摘要" "$(cat /tmp/article.html)" --cover-path /tmp/cover.jpg
```

输出中确认：
```
[INFO] 检测到 N 张正文图片（mmbiz URL）
[OK] 草稿创建成功!
```

---

## Gate 拦截的错误长什么样

如果跳过 Step 1-3，直接写 HTML 然后发布，会看到：

```
[INFO] 检测到 0 张正文图片（mmbiz URL）
[ERROR] 发布被拦截：HTML 正文中未找到任何 mmbiz 图片！
       必须先上传项目截图到 WeChat（media/uploadimg），获取 mmbiz URL 后嵌入 HTML。
```

遇到这个 = 返工 = 浪费时间。

---

## 快速自检（发布前必查）

```bash
# 检查 HTML 中有没有 mmbiz
grep -c 'mmbiz' /tmp/article.html
# 应该 ≥ 1

# 检查有没有未转换的 Markdown bold
grep -n '\*\*' /tmp/article.html
# 应该返回空
```
