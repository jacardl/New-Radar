---
name: daily-news-report
description: 每日早间新闻推送技能。自动生成包含黄金价格、AI圈新闻、国际大事件的日报。包含完整的自我检查和修复机制：联网检测、新闻时效性验证、网络故障处理。触发条件：用户请求生成日报、新闻推送、每日早间推送任务。
---

# 每日早间新闻推送

## 快速索引

| 场景 | 操作 |
|------|------|
| 生成完整日报 | 执行 ## 第三步：日报生成流程 |
| 网络故障 | 执行 ## 故障处理流程 |
| 新闻过期修复 | 执行 ## 第二步：新闻时效性自检 修复流程 |
| 查询历史日报 | 读取 `daily-reports/YYYY-MM-DD.md` |

---

## 核心工具

> ⚠️ **工具优先级**：9Router Web Fetch > mmx > Tavily/其他。优先使用 9Router 的 `web_search` / `web_fetch`（需配置 9Router MCP server，见 `references/wechat-fetch.md`）。

- **浏览器 CDP**（黄金价格页面、RSS 页面）
  ```bash
  browser(action="open", url="https://www.kitco.com/charts/livegold.html")
  browser(action="snapshot")  # 获取页面内容
  ```
- **Tavily（英文搜索）** - 国际新闻/AI新闻的一手国际来源（Reuters/AP/BBC/FT等）
  ```bash
  TAVILY_API_KEY="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"
  curl -s -X POST "https://api.tavily.com/search" \
    -H "Authorization: Bearer $TAVILY_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query":"<英文关键词>","search_depth":"basic","max_results":5}'
  ```
- **mmx search（中文搜索）** - 中文媒体的国内/中文报道
- **RSS 订阅**（国际政治优先）
  - Reuters：`https://www.reutersagency.com/feed/?best-topics=world-news`
  - BBC：`https://feeds.bbci.co.uk/news/world/rss.xml`
  - AP News：`https://feeds.apnews.com/apnews/topnews`
- **exec** - 执行 shell 命令

## 数据源优先级

| 内容 | 首选数据源 | 备选 | 兜底 |
|------|-----------|------|------|
| 黄金价格 | Kitco CDP（`kitco.com/charts/livegold.html`） | 新浪财经 CDP | mmx search |
| AI新闻 | Tavily英文搜索 + Hacker News API | mmx中文搜索 | - |
| 国际政治 | Reuters/BBC/AP RSS | Tavily英文搜索 | mmx英中搜索 |

---

## 第一步：联网检测 + 确定今日日期

**必须首先执行**

> ⚠️ **日期计算规则（必读）**：本任务运行于 UTC 时区，判断"今日"时必须使用北京时间。
> 在执行任何步骤前，**必须先执行**以下命令确定今日日期：
> ```bash
> date -d '+8 hour' '+%Y-%m-%d'
> ```
> 将此日期用于：
> - 日报标题（如"2026年5月2日"）
> - 存档文件名（`daily-reports/YYYY-MM-DD.md`）
> - 落款日期
> - 所有日期相关判断（节日、自驾游推荐等）
>
> **禁止**直接使用 UTC 日期或 shell 默认 `date` 命令的结果。

执行命令测试网络：
```bash
mmx search query "测试网络连通性"
```

**判断规则：**
- 返回结果 → 网络可用，继续执行第二步
- 报错或超时 → 触发 ## 故障处理流程

---

## 第二步：新闻时效性自检

每次搜索后**必须检查新闻日期**：

| 日期状态 | 处理方式 |
|----------|----------|
| 当天日期 | ✅ 正常输出 |
| 昨天日期 | ❌ **直接移除，不展示** |
| 更早日期 | ❌ **直接移除**，触发修复流程 |

**修复流程：**
1. 重新搜索，添加日期限定词：`"2026年4月28日"` 或 `"今天"`
2. 重试后仍无今日新闻 → 在自我检查报告中说明情况

---

## 第三步：日报生成流程

按顺序执行以下内容：

### 1. 今日黄金价格

**数据源选择（优先级）：**

**国际金价（美元/盎司）：**
1. CDP 抓取 Kitco：`browser(action="open", url="https://www.kitco.com/charts/livegold.html")` → `browser(action="snapshot")`

**国内金价（元/克）：**
1. CDP 抓取新浪财经（**首选**）：`browser(action="open", url="https://finance.sina.com.cn/futuremarket/")` → `browser(action="snapshot")`
2. CDP 抓取金十数据（**备选**）：`browser(action="open", url="https://www.jin10.com/")`
3. 兜底：`mmx search query "国内黄金价格 今日 元/克"`

**日报中同时展示国际金价+国内金价**，分开标注来源。

**判断标准：**
- 偏离近3日均价 >2% → 详细分析模式
- 偏离 ≤2% → 简洁模式

**买入建议逻辑：**
- 月内相对低位 → 建议买入较多克数（5-7克）
- 月内相对高位 → 建议少量买入（2-3克）或观望
- 本月总买入量不超过10克

### 2. AI·人工智能新闻（近24小时）

**英文搜索（Tavily）** + **中文搜索（mmx）** 双口径：
- 命令1（Tavily英文）：
  ```bash
  curl -s -X POST "https://api.tavily.com/search" \
    -H "Authorization: Bearer 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" \
    -H "Content-Type: application/json" \
    -d '{"query":"AI artificial intelligence latest news today May 2026","search_depth":"basic","max_results":5}'
  ```
- 命令2（mmx中文）：`mmx search query "AI人工智能最新新闻 今天"`

- 每条包含：标题、核心内容、来源
- **必须验证新闻日期**
- **Tavily来源优先**：Reuters、AP、TechCrunch、Wired、Ars Technica、Stanford HAI
- mmx中文来源作补充参考（36氪、机器之心）

### 3. 国际政治（近24小时）

**RSS 订阅优先**：
- BBC World News RSS：`https://feeds.bbci.co.uk/news/world/rss.xml`
- Reuters RSS：`https://www.reutersagency.com/feed/?best-topics=world-news`
- AP News RSS：`https://feeds.apnews.com/apnews/topnews`

**搜索备选**：
- 命令1（Tavily英文）：
  ```bash
  curl -s -X POST "https://api.tavily.com/search" \
    -H "Authorization: Bearer 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" \
    -H "Content-Type: application/json" \
    -d '{"query":"international politics geopolitics world news today May 2026","search_depth":"basic","max_results":5}'
  ```
- 命令2（mmx英文）：`mmx search query "international politics latest news today"`
- 命令3（mmx中文）：`mmx search query "国际政治最新新闻 今天"`

- 每条包含：标题、核心内容、来源
- **必须验证新闻日期**
- **按区域整合输出**，分为三个板块：
  - 🔴 **亚太**：中国周边、朝鲜半岛、南海、台海等
  - 🔵 **中东·欧洲**：俄乌、中东、欧盟等
  - 🟢 **美洲·其他**：美国内政、拉美等
- 昨日及更早的旧闻**直接移除，不展示**

### 4. 节假日前自驾游推荐

**触发条件：** 未来3天内有国家重大节日

国家重大节日：元旦、春节、清明节、劳动节、端午节、中秋节、国庆节

**【核心原则 - 必读】**
每次推荐必须**避免重复**，遵循以下规则：
1. **不能重复推荐同一个城市**：每次推荐前先确认上次推荐过哪里，不要重复
2. **禁止推荐著名旅游城市**：北京/上海/成都/杭州/西安/厦门/南京/重庆/青岛等知名城市一律不推荐（用户随时可去，不需要节假日推荐）
3. **优先推荐小众目的地**：县级市、老城、古镇、边境小城、有独特烟火气的城市
4. **两个城市风格互补**：一个偏自然山水/乡村风，一个偏人文/工业/遗址风

**推荐格式：**
> **🚗 节假日前自驾游推荐**
>
> 假期将至，推荐两个从北京出发、**自驾5小时以内**、可玩**2-3天**的小众目的地：
>
> **推荐一：[城市名+特色标签]**
> - 距离/车程：约X小时
> - 适合游玩天数：2-3天
> - 推荐理由：（一句话突出独特性，烟火气/小众/历史感优先）
>
> **推荐二：[城市名+特色标签]**
> - 距离/车程：约X小时
> - 适合游玩天数：2-3天
> - 推荐理由：（同上）

**优秀推荐参考：**
- 河北昌黎（海岸线+红酒庄园+长城遗址）
- 山西大同（云冈石窟+北岳恒山+刀削面）
- 内蒙古乌兰浩特（成吉思汗庙+阿尔山边境）
- 山东青州（古九州+范公亭+井塘古村）
- 河南开封（清明上河园+夜市烟火气）
- 辽宁锦州（笔架山+烧烤江湖+辽西古城）
- 贵州黔东南（肇兴侗寨+梯田+鼓楼）
- 云南建水（古城+米轨火车+豆腐）
- 甘肃张掖（七彩丹霞+马蹄寺+裕固族）
- 吉林延吉（边境风情+朝鲜族美食+长白山）

**严禁推荐：** 知名旅游城市（北京/上海/成都/杭州/西安/厦门/南京/重庆/青岛等）、上次已推荐过的城市

### 5. 每月人物传记推荐

**触发条件：** 每月1日

---

## 第四步：存档（日报生成完毕后将内容写入文件）

**必须执行**：将本次生成的完整日报内容存档到 `daily-reports/YYYY-MM-DD.md`。

```bash
REPORT_DATE=$(date +%Y-%m-%d)
REPORT_DIR="/root/.openclaw/workspace/daily-reports"
mkdir -p "$REPORT_DIR"

cat > "$REPORT_DIR/$REPORT_DATE.md" << 'REPORT_EOF'
# 每日早间新闻日报 — YYYY年MM月DD日

（此处粘贴本日报的全部内容，包括黄金价格、AI圈新闻、国际政治（按区域整合）、自驾游推荐等所有模块）
REPORT_EOF
```

**⚠️ 实际操作**：将上方占位符替换为本次生成的实际完整日报文本（包含所有模块），然后执行写文件。

---

## 第五步：三消息推送格式（重要！）

**必须分成三条独立消息发送，每条之间用分隔线隔开：**

### 消息一：💰 生活服务板块
```
━━━━━━━━━━━━━━
📅 {日期} · 生活服务
━━━━━━━━━━━━━━

💰 黄金价格
[内容：国际金价/人民币金价/今日建议/本月进度]

🚗 节假日前自驾游推荐（如有）
[内容]

📚 本月读书推荐（如有）
[内容]

━━━━━━━━━━━━━━
🦞 独立小扎 · {日期}
━━━━━━━━━━━━━━
```

### 消息二：🌐 资讯板块
```
━━━━━━━━━━━━━━
📅 {日期} · 资讯速递
━━━━━━━━━━━━━━

🤖 AI·人工智能（近24小时）
[3条新闻，标题+核心内容+来源]

🌍 国际政治
🔴 亚太：[新闻]
🔵 中东·欧洲：[新闻]
🟢 美洲·其他：[新闻]

━━━━━━━━━━━━━━
🦞 独立小扎 · {日期}
━━━━━━━━━━━━━━
```

### 消息三：💻 黑马日报板块
```
━━━━━━━━━━━━━━
📅 {日期} · 黑马日报
━━━━━━━━━━━━━━

[黑马日报完整内容：Top 10项目+本周亮点]

━━━━━━━━━━━━━━
🦞 独立小扎 · {日期}
━━━━━━━━━━━━━━
```

**推送规则：**
- 每条消息**必须独立发送**，不要合并
- 三条消息**按顺序发送**（生活服务 → 资讯 → 黑马）
- 推送目标：飞书用户 `user:ou_5859d0efc971feb5462a3aea501b7fb6`
- 三条消息之间间隔合理，让用户有时间阅读

---

## 故障处理流程

当所有网络工具均失败时：

1. 停止生成日报
2. 输出以下内容：

```
⚠️ **网络故障，日报生成失败**

抱歉，当前无法访问网络获取实时新闻。
已记录此问题，将在网络恢复后重新推送。

**可能原因：**
- 网络连接异常
- 搜索服务暂时不可用

如需帮助，请告知。
```

---

## 第六步：自我检查报告（添加到日报存档末尾）

```
---

**📋 自我检查报告**
- 网络状态：✅ 正常 / ❌ 故障
- AI新闻时效性：✅ 全部当日最新 / ❌ 有旧闻（已移除）
- 国际新闻时效性：✅ 全部当日最新 / ❌ 有旧闻（已移除）
- 如有任何❌，请告知，我将立即修复。
```

---

## 详细参考

- 完整日报模板和示例：See [references/report-template.md](references/report-template.md)
- 黄金价格分析逻辑：See [references/gold-analysis.md](references/gold-analysis.md)
- 微信公众号文章抓取（含验证码墙处理）：See [references/wechat-fetch.md](references/wechat-fetch.md)