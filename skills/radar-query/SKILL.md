---
name: radar-query
description: 舆情查询引擎 - 从本地 PostgreSQL 数据库搜索和分析舆情数据。用于关键词搜索、热点分析和趋势追踪。
version: 1.0.0
author: New Radar Team
license: MIT
metadata:
  hermes:
    tags: [radar, query, search, sentiment, trends]
    related_skills: [radar-insight, radar-media, radar-forum, radar-report]
---

# Radar Query Engine

**Role:** 舆情数据查询与分析引擎

**Function:** 从本地 PostgreSQL 数据库搜索舆情数据，提供关键词搜索、趋势分析和热点发现

## When to Use This Skill

当用户需要：
- 查询特定主题的舆情数据
- 分析热点话题和趋势
- 搜索特定平台的内容
- 获取最近时间段的数据
- 进行舆情分析和研究

## Core Capabilities

1. **关键词搜索** - 在 crawled_data 表中搜索关键词匹配的内容
2. **多平台搜索** - 支持微博、抖音、B站、小红书、知乎等平台
3. **时间范围过滤** - 支持按最近24小时/一周/一月筛选
4. **内容类型筛选** - 支持图文、视频、评论等类型

## Available Tools

### keyword_search
```python
keyword_search(keyword: str, limit: int = 10) -> dict
```
搜索本地数据库中的舆情数据

**Parameters:**
- `keyword`: 搜索关键词
- `limit`: 返回结果数量 (默认 10)

**Returns:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "platform": "微博",
      "content_type": "text",
      "content": "内容...",
      "source_url": "https://...",
      "source_keyword": "人工智能",
      "create_time": 1713964800000,
      "nickname": "用户昵称"
    }
  ]
}
```

### get_recent_data
```python
get_recent_data(platform: str = "", hours: int = 24) -> dict
```
获取最近 N 小时的数据

**Parameters:**
- `platform`: 平台筛选 (空字符串表示所有平台)
- `hours`: 小时数 (默认 24)

### get_stats
```python
get_stats() -> dict
```
获取数据库统计信息

**Returns:**
```json
{
  "total_records": 1000,
  "by_platform": {"微博": 500, "抖音": 300},
  "by_content_type": {"text": 800, "video": 200}
}
```

## Search Patterns

### 基础搜索
```
用户: 搜索关于"人工智能"的内容
Agent: 调用 keyword_search(keyword="人工智能")
```

### 平台特定搜索
```
用户: 搜索微博上的"新能源汽车"讨论
Agent: 调用 get_recent_data(platform="微博", hours=168)
```

### 趋势分析
```
用户: 最近一周人工智能相关的热点有哪些
Agent:
1. 调用 get_recent_data(hours=168) 获取最近一周数据
2. 分析数据中的热点话题
3. 汇总成趋势报告
```

## Data Flow

```
用户查询 → keyword_search/get_recent_data → crawled_data 表 → 返回结果
                ↓
         Hermes MCP Tools (db-query server)
```

## Integration with Other Skills

**Handoff to:**
- **radar-insight** - 需要深度分析时
- **radar-media** - 需要多媒体内容分析时
- **radar-report** - 需要生成报告时

**Data from:**
- **DataCollector** - 外部 API 采集的数据写入 crawled_data 表
- **MediaCrawler** - 社媒爬虫数据写入

## Example Queries

### 1. 基础舆情搜索
```
用户: 帮我搜索最近关于"芯片国产化"的内容
Agent:
  results = await keyword_search("芯片国产化", limit=20)
  返回找到的舆情数据列表
```

### 2. 热点趋势分析
```
用户: 最近有哪些科技领域的热点话题？
Agent:
  1. get_recent_data(hours=72) - 获取最近3天数据
  2. 统计各平台内容分布
  3. 识别高频关键词
  4. 输出热点话题分析
```

### 3. 竞品分析
```
用户: 对比一下"特斯拉"和"比亚迪"的舆情
Agent:
  1. keyword_search("特斯拉", limit=50)
  2. keyword_search("比亚迪", limit=50)
  3. 分析两组数据的情感倾向和互动数据
```

## Limitations

- 只查询本地 PostgreSQL 数据库，不调用外部搜索 API
- 向量搜索需要数据已有 embedding 向量
- 部分平台数据可能不完整（取决于爬虫采集情况）

## Pitfalls

1. **数据库为空** - 首次使用需要先通过 DataCollector 采集数据
2. **关键词模糊** - 使用精确关键词可获得更好结果
3. **时间范围过大** - 大量数据查询可能较慢

## Verification

- `keyword_search("test", limit=1)` 应返回格式正确的 JSON
- `get_stats()` 应返回包含 total_records 的统计信息
- 数据查询延迟应 < 1秒（小数据量）
