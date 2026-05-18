# 发布前强制检查 Gate 机制

## 背景

历史问题：format-guide 中明确规定「正文（二、项目介绍）至少放置一张项目截图」，但 agent 仍多次跳过，导致发布的草稿缺少项目截图。

根因：规则存在于文档中，但无自动化拦截。agent 可以「计划稍后放图」然后实际跳过了发布。

## 解决方案：check_article_images() Gate

位置：`scripts/publish_zhili.py`

```python
def check_article_images(content):
    """发布前强制检查：HTML 正文中必须包含 mmbiz 图片，否则拒绝发布"""
    if 'mmbiz' not in content:
        print("[ERROR] 发布被拦截：HTML 正文中未找到任何 mmbiz 图片！")
        print("       必须先上传项目截图到 WeChat（media/uploadimg），获取 mmbiz URL 后嵌入 HTML。")
        sys.exit(1)
    count = content.count('mmbiz')
    print(f"[INFO] 检测到 mmbiz 关键词 {count} 次（1次即满足最低要求）")
```

Gate 触发位置：`main()` 函数中，任何 `create_draft()` 调用之前。

## 效果

| 场景 | 旧行为 | 新行为 |
|------|--------|--------|
| HTML 无 mmbiz 图片 | 发布成功（草稿缺图） | 脚本 `exit(1)`，拒绝发布 |
| HTML 有 mmbiz 图片 | 发布成功 | 发布成功 |

## 图片缺失时的修复流程

```
1. 下载项目截图/GIF（GitHub API + raw 文件）
2. 上传到微信：upload_article_image() → mmbiz URL
3. 在 HTML 对应位置嵌入：<img src="mmbiz_url" style="width:100%;border-radius:6px;" />
4. 重新执行发布脚本
```

## 常见项目素材路径（优先查这些目录）

```
README.md 同级的 .png/.gif/.jpg
assets/ 目录
docs/images/ 目录
screenshots/ 目录
/demo.gif 或 /demo.mp4
```

## 概念类文章（无 GitHub 项目）的配图策略

当文章主题是概念解析（如 GEO、AI 优化方法论）而非具体开源项目时：

1. **PIL 自绘信息结构图**（首选）：用 Python + Pillow 绘制概念对比图、工作流图、维度矩阵等，作为正文章节的核心配图。完全离线，与文章内容高度匹配。
2. **AI 封面图复用**：封面图如果包含可识别的概念元素，可裁剪出一部分作为正文配图。
3. **在 HTML 中明确标注**：如果确实无图，在正文（二、项目介绍）开头注明「本文为概念解析类文章，配图为自制信息结构图」，满足 check_article_images() Gate 对 mmbiz 图片的要求。

**PIL 信息图合格标准**：
- 包含实际内容（色块分区、对比列、流程箭头、文字标注），非纯装饰
- 尺寸 ≥ 600px 宽
- 必须通过 `media/uploadimg` 上传获得 mmbiz URL 后嵌入 HTML

**验证**：`grep -c 'mmbiz' /tmp/article.html` ≥ 1

---

## 无图项目的 Fallback

若项目完全没有图片：
1. GitHub OG 图：`https://opengraph.githubassets.com/1/{owner}/{repo}`
2. AI 生成技术示意图
3. 在 HTML 中标注「项目暂无截图，用 OG 图代替」

## 验证命令

```bash
# 发布前手动检查 HTML 是否含 mmbiz 图片
grep -c 'mmbiz' /tmp/article.html
# 应返回 ≥1

# 发布后检查草稿
grep -n 'mmbiz\|img src' /tmp/article_draft.html
```

## 关联规则

- format-guide.md：「文章插图规范」
- SKILL.md：「完整顺序（必须按此顺序执行）」中的图片 Gate 说明
