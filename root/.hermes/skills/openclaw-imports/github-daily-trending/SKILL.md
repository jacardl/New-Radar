---
name: github-daily-trending
description: >
  黑马发现引擎 · 多源项目选题 → 公众号文章全流程工具。
  当用户说"今天GitHub有什么"、"帮我找选题"、"写公众号"、"生成今日推送"、"黑马"、"找项目"时触发。
  覆盖：多源采集 → 分类探索 → 黑马报告 → 用户选题 → 输出文章 → 存档 → 互动反馈。
---

# 黑马发现引擎 · 公众号全流程

## 核心理念

> 黑马项目：关注度不高，但真实地解决了某一个场景的问题。

不是热度排行，是**场景发现**。每天探索不同分类，覆盖不同领域，推送有差异化。

## 工作流总览

```
定时任务触发（每日 06:50 UTC）
  → 判断今日类型：日报 / 周六周报 / 月末月报
  → 多源采集
  → 黑马候选池（10条，不同分类）
  → 格式化推送报告
  → 用户选题
  → 六段式文章输出
  → 存档 + 互动反馈
```

---

## 报告类型与触发规则

| 日期条件 | 报告类型 | 内容 | 发送 |
|---------|---------|------|------|
| 平常日（周一~周五） | **黑马日报** | 今日 10 条黑马项目 | ✅ 发送 |
| 每周六 | **黑马周报** | 本周 10 条黑马项目 | ✅ 发送 |
| 每月最后一天 | **黑马月报** | 本月 10 条黑马项目 | ✅ 发送 |
| 每周六（且是月末最后一天） | **黑马月报**（优先） | 本月 10 条 | 仅发月报 |

**注意**：当"周六"与"月末最后一天"重叠时，只发月报，不发周报。

---

## Step 1：每日采集

### 采集工具
- **OpenClaw CDP Browser**：GitHub Trending 页面（JS 渲染，必须用 CDP，不能用 requests）
- **Python urllib**：HN Algolia API、Dev.to API、GitHub REST API（查项目创建时间）

### 数据源矩阵

#### ① GitHub Trending（3个页面）

| 维度 | URL | 说明 |
|------|-----|------|
| 今日 | `https://github.com/trending` | 无参数 |
| 本周-All | `https://github.com/trending?since=weekly` | 本周全语言 |
| 本月-All | `https://github.com/trending?since=monthly` | 本月全语言 |

#### GitHub Trending CDP 抓取 SOP（必须遵守！）

**⚠️ 核心原则：每个维度用新开 Tab + browser open，绝对不要在已有 Tab 里 navigate！**

原因：在已有 Tab 里 navigate 到新 URL 会触发 GitHub 反爬保护，导致 ERR_CONNECTION_TIMED_OUT 卡死。

**抓取步骤（按日期条件抓）**：
1. `browser start`
2. 每天都要抓今日：Tab1: `browser open` → `https://github.com/trending` → 等待 snapshot 返回（约 18 秒）
3. 如果今天是周六：追加 Tab2: `browser open` → `https://github.com/trending?since=weekly`
4. 如果今天是月末最后一天：追加 Tab3: `browser open` → `https://github.com/trending?since=monthly`
5. `browser stop`

**关键参数**：`timeoutMs: 25000ms`。

**⚠️ navigate 必死**：在同一个 Tab 里用 `navigate` 切换 URL = 必卡死。只能用 `open` 开新 Tab。

**⚠️ 注意**：
- `?since=daily` 返回 0 条，**今日用无参数 URL**
- `?since=weekly` / `?since=monthly` 只在主页面有效

#### ② HN Show HN（重要！项目源）

**这是黑马软件/产品项目的最佳来源**。发帖者发布自己做的东西，不是讨论新闻。

| 标签 | API URL | 说明 |
|------|---------|------|
| Show HN | `https://hn.algolia.com/api/v1/search?tags=show_hn&hitsPerPage=30` | **主力项目源**，有真实项目链接 |
| Ask HN | `https://hn.algolia.com/api/v1/search?tags=ask_hn&hitsPerPage=10` | 洞察真实需求，不是项目，价值低 |

**Show HN 过滤规则：** 只保留有外部项目链接的内容（排除纯 HN 讨论帖），优先 GitHub 链接。

#### ③ Dev.to（项目/工具文章源）

| 标签 | API URL | 说明 |
|------|---------|------|
| showdev | `https://dev.to/api/articles?per_page=10&tag=showdev` | 用户发布的工具/项目 |
| opensource | `https://dev.to/api/articles?per_page=10&tag=opensource` | 开源项目介绍 |
| cli | `https://dev.to/api/articles?per_page=10&tag=cli` | CLI 工具 |
| tools | `https://dev.to/api/articles?per_page=10&tag=tools` | 效率工具 |

#### ④ Product Hunt RSS（产品发布源）

| 用途 | URL |
|------|-----|
| 主页 Feed | `https://www.producthunt.com/feed` |

- 格式：Atom XML（`application/atom+xml`）
- 条目数：50 条
- 特点：产品都是历史热门，但都是真实发布的产品，描述质量高
- 用途：补充有「产品感」的软件产品，和 HN Show HN 互为补充
- **⚠️ 注意：** PH RSS 里很多是付费/SaaS 产品，写文章时需确认是否开源或可免费使用。

#### ⑤ GitHub REST API（新项目挖掘）

| 用途 | URL 模板 |
|------|---------|
| 按 topic 找新项目 | `https://api.github.com/search/repositories?q=topic:{topic}+created:>{date}&sort=stars&per_page=5` |
| 按语言找新项目 | `https://api.github.com/search/repositories?q=language:{lang}+created:>{date}&sort=stars&per_page=5` |

日期格式：`YYYY-MM-DD`，查询近 30 天内创建的项目。

常用 topic：`tui`, `cli-tool`, `devtool`, `agent`, `ai-agent`, `automation`, `privacy-tool`

#### ⑥ 其他补充源

| 源 | 类型 | 说明 |
|---|------|------|
| TechCrunch RSS | `https://techcrunch.com/feed/` | 科技产品新闻 |
| Lobsters | HTML `https://lobste.rs` | 开发者社区小众项目 |

#### ⑥ HuggingFace / ModelScope 模型动态

| 源 | 方式 | 说明 |
|---|------|------|
| HuggingFace | Tavily 搜索 `HuggingFace trending model release` | 热门模型、近期新发布 |
| ModelScope | Tavily 搜索 `ModelScope hot model new LLM` | 国内大模型动态 |

- 采集方式：使用 Tavily 英文搜索获取近24小时模型动态
- 注意：HuggingFace 和 ModelScope 官网 API 在当前环境网络不通，优先用搜索方式获取
- 如果搜索无结果，标记为空，不要反复重试

### ⚠️ 已知陷阱

**sub-agent 数据不准**：delegate_task 的子 agent 调用 GitHub REST API 时可能返回错误数据（例如把 Swift 项目报成 Go、把 4491 stars 报成 47 stars）。**所有项目数据必须用 terminal/curl 直接调用 GitHub API 二次验证**，不得直接信任子 agent 返回的原始 API 结果。

---

### 采集策略（每日轮换）

**10 个探索分类，每天覆盖 3-4 个**，确保不重复推送相同领域：

| 分类 | 主源 | 探索方式 |
|------|------|---------|
| 🔁 AI 基础设施 | GH API topic:agent | 找 Agent/ML 框架 |
| 🛠️ 开发者工具 | GH API topic:devtool | 找新 CLI/编辑器插件 |
| 🚀 效率工具 | Dev.to #tools | 找自动化/提速工具 |
| 📦 开源项目 | HN Show HN | 找真实发布的开源项目 |
| 🌐 垂直场景 | HN Show HN（过滤） | 找医疗/教育/硬件项目 |
| 💡 概念验证 | HN Show HN（低票） | 找新出现的 Demo/原型 |
| 🔧 基础设施 | GH API 新项目 | 找数据库/缓存/网络工具 |
| 🎨 创意/媒体 | Dev.to #showdev | 找设计/音视频工具 |
| 🔒 安全/隐私 | HN Show HN（过滤） | 找安全/加密工具 |
| 📱 终端/桌面 | GH API topic:tui | 找 TUI/终端/桌面工具 |

**轮换逻辑：** 每天随机选 3-4 个分类，确保 3 天内覆盖所有 10 个分类。

### 黑马拉分算法

```python
def blackhorse_score(total_stars, period_stars, is_new=False):
    """黑马分数：新项目加权 + 小项目加成"""
    if total_stars < 5000:   mult = 2.0   # 最强黑马相
    elif total_stars < 20000: mult = 1.5   # 较强黑马相
    elif total_stars < 100000: mult = 1.0  # 正常
    else:                    mult = 0.8   # 大项目压制
    
    base = int(period_stars * mult)
    
    # 新项目加权（创建 <30 天）
    if is_new:
        base = int(base * 1.5)
    
    return base
```

---

## Step 2：推送选题报告

> ⚠️ **【时区警告 必读】** 本任务由 cron 调度在 isolated session 中执行，session 内部默认 UTC 时区。
> **必须**先执行以下命令获取北京时区的真实日期，再判断报告类型：
> ```bash
> date -d '+8 hour' '+%Y-%m-%d'
> date -d '+8 hour' '+%u'  # 1=周一 ~ 7=周日
> ```
> - `%u` 为 1-5 → 黑马日报（平常日）
> - `%u` 为 6 → 黑马周报（周六）
> - 每月最后一天 → 黑马月报（月末）
> **绝对不要**直接用 UTC 日期判断。

### 推送规则（三种报告）

- **黑马日报**：平常日（周一~周五），10 条今日黑马项目
- **黑马周报**：每周六，10 条本周（since=weekly）黑马项目
- **黑马月报**：每月最后一天，10 条本月（since=monthly）黑马项目
- **优先级**：月报 > 周报（月末周六只发月报）；周六且非月末发周报

### 报告样式一：黑马日报（平常日）

```
🌙 **黑马日报 · 直隶按察使**
📅 {{date}} · 平常日
━━━━━━━━━━
🔍 数据：GitHub Trending · HN Show HN · Dev.to · GH API
🎯 今日探索：{{分类列表}}

━━ 🏆 TOP 10 黑马项目 ━━━

{% for item in items %}
{{loop.index}}️⃣ 【{{item.category}}】{{item.name}}
💬 {{item.description}}
📊 ⭐{{item.total_stars}} | {% if item.today_stars %}+{{item.today_stars}} ⭐ {% endif%}{% if item.growth_rate %}{{item.growth_rate}}{% endif %}
🔗 {{item.url}}
🏷️ {% if item.source=='hn-showhn' %}HN{% else %}{{item.source}}{% endif %}
💡 {{item.angle}}

{% endfor %}

━━ 📌 选题优先级 ━━━
🥇 最高优先：{{top1.name}} — {{top1.reason}}
🥈 次高优先：{{top2.name}} — {{top2.reason}}
🥉 第三优先：{{top3.name}} — {{top3.reason}}

━━━━━━━━━━
💬 回复序号（1-10）选择项目开写
　「全部」生成完整10篇
━━━━━━━━━━
```

### 报告样式二：黑马周报（每周六）

```
🌅 **黑马周报 · 直隶按察使**
📅 {{date}} · {{week_range}}（本周）
━━━━━━━━━━
🔍 数据：GitHub Trending 本周 · HN Show HN · Dev.to
📌 说明：本周黑马 = 2026年{{week_num}}周增长最快的开源项目

━━ 🏆 本周 10 条黑马 ━━━

{% for item in items %}
{{loop.index}}️⃣ 【{{item.category}}】{{item.name}}
💬 {{item.description}}
📊 ⭐{{item.total_stars}} | {% if item.week_stars %}+{{item.week_stars}} 本周新增{% endif %}
🔗 {{item.url}}
💡 {{item.angle}}

{% endfor %}

━━ 📌 本周黑马趋势洞察 ━━━
{{trend_summary}}

━━━━━━━━━━
💬 回复序号（1-10）选项目开写
━━━━━━━━━━
```

### 报告样式三：黑马月报（每月最后一天）

```
🌕 **黑马月报 · 直隶按察使**
📅 {{date}} · {{month}} 月报
━━━━━━━━━━
🔍 数据：GitHub Trending 本月 · HN Show HN · Dev.to
📌 说明：本月黑马 = {{month}}月增长最快的开源项目

━━ 🏆 本月 10 条黑马 ━━━

{% for item in items %}
{{loop.index}}️⃣ 【{{item.category}}】{{item.name}}
💬 {{item.description}}
📊 ⭐{{item.total_stars}} | {% if item.month_stars %}+{{item.month_stars}} 本月新增{% endif %}
🔗 {{item.url}}
💡 {{item.angle}}

{% endfor %}

━━ 📌 {{month}}月黑马全景 ━━━
{{month_summary}}

━━━━━━━━━━
💬 回复序号（1-10）选项目开写
━━━━━━━━━━
```

### 推送规范（通用）
- **每日/每周/每月 10 条**，不允许少
- 选 `blackhorse_score` 最高 + 增长率高的项目
- 每个项目必须标注**分类标签**和**数据来源**
- 项目简介：1句话说明项目是干什么的
- 切入点提示：为什么值得写（解决什么场景问题）
- **差异化要求**：同分类项目不连续出现，确保多分类覆盖

---

## Step 3：输出文章（内容 + HTML）

> ⚠️ **技能协调**：`github-daily-trending` 负责内容写作（六段式），`zhili-publish` 负责微信 HTML 渲染（内联样式、mmbiz 图）。写完文章后必须加载 `zhili-publish` 生成微信草稿，禁止直接发布 markdown 或未按内联样式转换的 HTML。

### 标题公式
```
数字 + 感叹 + 核心洞察 + 团队/语言背景 + 未来感结尾
例：「49k stars！把终端变成 AI 开发环境：Warp 让我重新理解了什么叫"下一代 IDE"」
```

### 六段式结构

**一、痛点/现状切入**
- 描述 3 种常见现状（各 1-2 句），用一句话总结核心问题
- 结尾直接点出项目要解决什么
- 关键：要有具体场景，让读者"对号入座"

**二、项目介绍 + 核心概念**
- 第一句：一句话定位（项目名 + 团队 + 核心定位）
- 第二句：一句话描述（用"一句话描述：XXX"的句式）
- 数据卡片：Stars / Forks / License / 语言
- 核心概念列表（加粗）：每个概念名 + 定义 + 举例
- 典型工作流图示：`[步骤1] → [步骤2] → [步骤3]`

**三、怎么用？**
- 环境要求
- 快速上手 3 步（代码块）
- 实战案例（失败→介入→成功完整弧线）

**四、技术亮点**
- 1. 2. 3. 4. 5. 编号
- 每条：加粗标题（一句话概括）+ 正文（2-3句解释原理）

**五、行业观察**
- 描述行业现状或争议
- 给不同立场的信息
- 一句锐利结论收尾（加粗）
- **关键：要有立场，不只是客观陈述**

**六、总结**
- 核心判断（加粗）
- 列表总结项目价值
- 收尾金句（类比或洞察）
- Star号召固定句式 + 项目地址 + 数据来源固定格式

### 必须元素清单
| 元素 | 格式 |
|------|------|
| 数据卡片 | `**GitHub**: url \| **Stars**: Xk \| **Forks**: X \| **语言**: XXX` |
| GitHub链接 | 数据卡片同行 |
| 核心概念列表 | `• **概念名（加粗）**：定义 + 举例` |
| 工作流图示 | `[步骤1] → [步骤2] → ...` |
| 实战案例弧线 | `• **第N次尝试（状态）**：动作 + 结果` |
| 技术亮点 | `**1. 标题**：解释` |
| 收尾金句 | 有洞察力的判断句 |
| Star号召 | `如果你觉得这个 XXX 有意思，欢迎 Star 支持开源 🧬` |
| 数据来源 | `📌 数据来源：GitHub Trending，YYYY-MM-DD | 项目：xxx` |

### ⚠️ 内容写作 → HTML 转换规则（必须遵守）

六段式内容写完后，**交给 `zhili-publish` 技能生成微信 HTML**，自己不要手动拼 HTML。但写作时要注意：

| 内容写法（六段式） | 微信 HTML 要求 |
|-------------------|---------------|
| `**粗体文字**` | 必须转换为 `<strong style="color:#e63946;">粗体文字</strong>`，禁止保留 `**` |
| `• **概念名**：描述` | 概念名加粗用 `<strong>`，列表符号 `•` 直接写文字不要用 `<ul>` |
| `1. 2. 3. 4. 5.` 技术亮点 | 编号列表在 HTML 中用 `**1. 标题**：解释` 的 `<p>` 段落，不可用 `<ol>` |
| 代码块 | 用三个反引号包裹，HTML 阶段会转换为 `<pre><code>...</code></pre>` |

⚠️ **最高频踩坑——`**`** Markdown 粗体残留**：写作时写 `**文字**` 是给内容加粗的正确方式，但进入 HTML 阶段如果直接写入 HTML 文件，会变成字符串 `**文字**` 而不是 `<strong>文字</strong>`。发布前必须 `grep -n '\*\*' /tmp/article.html` 确认返回空。

生成微信草稿的完整流程见 `zhili-publish` 技能。

---

## Step 4：存档记录

文章发出后：
1. 更新 `references/article-index.md`
2. 存档文章到 `articles/YYYY-MM-DD-[项目名].md`

---

## Step 5：互动数据反馈优化

收到互动数据后：
1. 读取 `references/article-index.md` 找到文章
2. 读取 `references/profiles/account-zhili.md`
3. 分析数据，更新 index
4. 将优化建议追加到 `references/profiles/account-zhili.md` 和 `MEMORY.md`
5. 调整后续推荐逻辑

---

## Step 6：定时任务配置

| 时间 | 任务 | 说明 |
|------|------|------|
| 每天 06:50 UTC | 采集 + 判断日期类型 | 判断今日是日报/周报/月报 |
| 06:55 UTC | 推送报告 | 根据类型发送对应报告 |
| 每周六 06:50 | 采集 + 周报推送 | 本周黑马 10 条 |
| 每月最后一天 06:50 | 采集 + 月报推送 | 本月黑马 10 条 |

**同天不重复规则**：
- 周六 + 月末最后一天 → 只发月报，不发周报
- 月末非周六 → 发月报
- 周六非月末 → 发周报
- 平常日 → 发日报

**数据文件：**
- `trending/YYYY-MM-DD.json`（原始采集）
- `trending/report-YYYY-MM-DD.json`（结构化报告）
- `articles/YYYY-MM-DD-[项目名].md`（文章存档）
- `references/article-index.md`（文章索引）

---

## 参考文件
- 完整格式规范：`references/format-guide.md`
- 账号画像：`references/profiles/account-zhili.md`（直隶按察使）
