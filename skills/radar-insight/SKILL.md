---
name: radar-insight
description: 深度洞察引擎 - 对舆情数据进行深度分析，挖掘趋势、情感和洞察。用于深度分析报告、趋势研判和决策支持。
version: 1.0.0
author: New Radar Team
license: MIT
metadata:
  hermes:
    tags: [radar, insight, analysis, sentiment, trends]
    related_skills: [radar-query, radar-media, radar-forum, radar-report]
---

# Radar Insight Engine

**Role:** 深度洞察与分析引擎

**Function:** 对舆情数据进行深度分析，挖掘隐藏趋势、情感倾向和关键洞察

## When to Use This Skill

当用户需要：
- 进行深度舆情分析
- 挖掘话题趋势和规律
- 分析情感倾向（正面/负面/中性）
- 生成深度研究报告
- 决策支持分析

## Core Capabilities

1. **趋势分析** - 识别话题随时间的变化趋势
2. **情感分析** - 判断舆情的情感倾向
3. **热点挖掘** - 从数据中发现热点话题
4. **对比分析** - 多话题/多平台的对比分析
5. **洞察生成** - 从数据中提炼有价值的信息

## Data Flow

```
用户请求深度分析 → radar-query 获取原始数据 → radar-insight 分析 → 输出洞察
                          ↓
                   crawled_data 表
```

## Integration with Other Skills

**Handoff to:**
- **radar-report** - 生成结构化报告时
- **radar-query** - 需要更多原始数据时

**Data from:**
- **radar-query** - 查询得到的原始数据
- **DataCollector** - 外部采集的补充数据

## Example Workflows

### 1. 深度趋势分析
```
用户: 分析最近一个月"新能源汽车"的发展趋势
Agent:
  1. 调用 radar-query 获取最近30天数据
  2. 按时间聚合数据
  3. 识别增长/下降趋势
  4. 输出趋势分析报告
```

### 2. 情感倾向分析
```
用户: 用户对某品牌新产品的反应是正面的还是负面的？
Agent:
  1. 调用 radar-query 获取相关数据
  2. 调用 sentiment_analyzer 进行情感分析
  3. 统计正面/负面/中性比例
  4. 给出情感倾向结论
```

### 3. 竞品深度对比
```
用户: 对比分析华为和小米在社交媒体上的表现
Agent:
  1. 分别查询两个品牌的数据
  2. 分析互动数据（点赞、评论、转发）
  3. 识别各自的优势和劣势
  4. 生成对比分析报告
```

## Limitations

- 依赖 radar-query 提供的数据
- 情感分析的准确性受限于数据质量
- 深度分析需要足够的数据量

## Pitfalls

1. **数据不足** - 分析结果可能不够准确
2. **噪声数据** - 爬虫数据可能包含噪声
3. **时间跨度** - 长期趋势分析需要持续的数据积累

## Verification

- 相同的查询应产生一致的分析结果
- 趋势判断应与数据相符
- 情感分析应在合理范围内
