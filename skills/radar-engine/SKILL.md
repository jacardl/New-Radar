---
name: radar-engine
description: 舆情分析引擎 - 完整的数据采集、存储、挖掘、分析、报告生成流程。触发条件：用户需要 (1) 采集外部数据 (2) 存储数据到数据库 (3) 挖掘分析数据 (4) 生成分析报告 时使用。
metadata:
  short-description: 舆情数据采集→存储→分析→报告完整流程
---

# Radar Engine - 舆情分析引擎

**Role:** 端到端舆情分析引擎

**Function:** 协调 data-collection、data-storage 完成数据采集存储，并提供 insight、media、query 引擎进行数据挖掘和分析，最终输出报告

---

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    数据采集层 (data-collection)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  外部搜索 API                    URL 抓取                  社交媒体爬虫    │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐  │
│  │ anspire_search  │     │ firecrawl_scrape│     │  crawl_media   │  │
│  │ bocha_search   │     │                 │     │                │  │
│  │ tavily_search  │     │ 获取完整网页内容  │     │ xhs/dy/wb/bili│  │
│  └────────┬────────┘     └────────┬────────┘     └────────┬────────┘  │
│           │                        │                        │           │
│           ▼                        ▼                        ▼           │
│      返回 URL 列表            返回完整内容                返回原始数据      │
│           │                        │                        │           │
└───────────┼────────────────────────┼────────────────────────┼───────────┘
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据存储层 (data-storage)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│              save_crawled_data → crawled_data 表                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ platform | content_type | content | source_url | metadata   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                     │                              │
└─────────────────────────────────────┼─────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    数据分析层 (radar-engine)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Insight    │  │    Media     │  │    Query     │          │
│  │   Engine    │  │   Engine    │  │   Engine    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                │                │                       │
│         ▼                ▼                ▼                       │
│  趋势/情感/洞察    视频/图片分析     数据库查询                    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              报告生成 (Markdown/HTML/PDF)
```

---

## Phase 1: 数据采集 (data-collection)

### 1.1 外部搜索 API

用于通过关键词获取 URL 列表：

| 工具 | 适用场景 | 说明 |
|------|---------|------|
| `anspire_search` | 中国深度搜索 | 返回相关性评分 |
| `bocha_search` | 多模态搜索 | 返回网页/图片/视频结果 |
| `tavily_search` | 海外搜索 | 新闻/文章搜索 |

```python
# 示例：使用 anspire_search 采集
anspire_search(query="人工智能", limit=10)
# 返回: [{title, url, content, score, date}, ...]
```

### 1.2 URL 内容抓取

使用 `firecrawl_scrape` 获取完整网页内容：

```python
firecrawl_scrape(url="https://example.com/article")
# 返回: {title, content, markdown, metadata, links}
```

### 1.3 社交媒体爬虫

使用 `crawl_media` 采集社交平台内容：

| 平台 | 代码 | 内容类型 |
|------|------|---------|
| 小红书 | xhs | 图文/短视频 |
| 抖音 | dy | 短视频 |
| 微博 | wb | 图文/视频 |
| B站 | bili | 中长视频 |
| 知乎 | zhihu | 图文 |

```python
# 示例：采集小红书数据
crawl_media(platform="xhs", keyword="AI 手机")
```

---

## Phase 2: 数据存储 (data-storage)

### 2.1 保存采集数据

使用 `save_crawled_data` 存入 crawled_data 表：

```python
save_crawled_data(
    platform="tavily",
    content_type="text",
    content="文章完整内容...",
    source_url="https://...",
    source_keyword="AI",
    nickname="作者名",
    liked_count=100,
    collected_count=50,
    comment_count=20,
    share_count=10,
)
```

### 2.2 数据库查询

用于获取已存储的数据：

| 工具 | 说明 |
|------|------|
| `keyword_search` | 关键词搜索 (LIKE 匹配) |
| `vector_search` | 向量相似度搜索 |
| `get_recent_data` | 获取最近 N 小时数据 |
| `get_stats` | 获取统计信息 |

```python
# 示例：查询相关数据
keyword_search(keyword="AI 手机", limit=50)
get_recent_data(platform="tavily", hours=24)
get_stats()
```

---

## Phase 3: 数据分析 (Insight / Media / Query Engines)

### 3.1 Insight Engine - 深度洞察分析

**能力：**
- 趋势分析 - 识别话题随时间变化
- 情感分析 - 判断正面/负面/中性倾向
- 热点挖掘 - 发现热门话题
- 对比分析 - 多话题/多平台对比

```python
# 分析流程
1. keyword_search 获取原始数据
2. 按时间聚合
3. 识别情感倾向
4. 挖掘热点关键词
5. 生成洞察结论
```

### 3.2 Media Engine - 多模态媒体分析

**能力：**
- 视频内容分析 - 抖音/B站视频
- 图片舆情分析 - 小红书/微博图片
- 互动数据分析 - 点赞/评论/收藏/分享

**平台数据：**

| 平台 | 互动指标 |
|------|---------|
| 抖音 | 点赞、收藏、评论、分享 |
| B站 | 点赞、投币、收藏、分享 |
| 小红书 | 点赞、收藏、评论 |
| 微博 | 点赞、转发、评论 |

### 3.3 Query Engine - 数据查询

**能力：**
- 按关键词查询数据
- 按平台筛选
- 按时间范围筛选
- 聚合统计

---

## Phase 4: 报告生成

### 4.1 报告结构

```
# 舆情分析报告

## 执行摘要
## 1. 背景与目的
## 2. 数据概况
   - 数据来源
   - 时间范围
   - 数据量
## 3. 主要发现
   - 热点话题
   - 趋势分析
   - 情感倾向
## 4. 详细分析
   - 平台分布
   - 内容类型
   - 互动分析
## 5. 结论与建议
## 附录
```

### 4.2 输出格式

支持 Markdown、HTML、PDF 三种格式

---

## Complete Example

```
用户: 帮我分析"新能源汽车"近一周的舆情

执行流程:
1. 采集阶段:
   - anspire_search("新能源汽车", limit=20)
   - bocha_search("新能源汽车", limit=20)
   - firecrawl_scrape(url)  # 抓取重点文章

2. 存储阶段:
   - save_crawled_data()  # 存入数据库

3. 分析阶段:
   - keyword_search("新能源汽车", limit=100)
   - get_recent_data(hours=168)  # 近7天
   - Insight Engine: 趋势分析 + 情感分析
   - Media Engine: 社媒互动分析

4. 报告生成:
   - 输出完整分析报告
```

---

## Tools Reference

| Phase | MCP | Tools |
|-------|-----|-------|
| 采集 | data-collection | anspire_search, bocha_search, tavily_search, firecrawl_scrape, crawl_media |
| 存储 | data-storage | save_crawled_data |
| 查询 | data-storage | keyword_search, vector_search, get_recent_data, get_stats |
| 分析 | radar-engine | Insight Engine, Media Engine, Query Engine |
| 报告 | radar-engine | 报告生成 |

---

## Pitfalls

1. **数据不足** - 确保采集足够的数据量进行分析
2. **重复数据** - 使用 source_url 去重
3. **平台限制** - 社媒平台可能需要登录态
4. **数据质量** - 爬虫数据可能包含噪声
