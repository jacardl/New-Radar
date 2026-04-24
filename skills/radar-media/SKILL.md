---
name: radar-media
description: 多模态媒体分析引擎 - 分析包含图片、视频、音频的多模态舆情内容。用于社媒内容分析、多媒体趋势发现。
version: 1.0.0
author: New Radar Team
license: MIT
metadata:
  hermes:
    tags: [radar, media, multimedia, social, video]
    related_skills: [radar-query, radar-insight, radar-forum, radar-report]
---

# Radar Media Engine

**Role:** 多模态媒体分析引擎

**Function:** 分析包含图片、视频、音频的舆情内容，提取多媒体趋势和热点

## When to Use This Skill

当用户需要：
- 分析社交媒体上的视频内容
- 研究图文内容的传播规律
- 发现多媒体热点话题
- 分析平台特色的内容形式

## Core Capabilities

1. **视频内容分析** - 分析抖音、B站等视频平台内容
2. **图片舆情分析** - 分析小红书、微博图片内容
3. **互动数据分析** - 分析点赞、评论、收藏、分享数据
4. **平台特色分析** - 针对不同平台特点分析

## Supported Platforms

| 平台 | 内容类型 | 特色数据 |
|------|----------|----------|
| 抖音 | 短视频 | 点赞、收藏、评论、分享 |
| B站 | 中长视频 | 点赞、投币、收藏、分享 |
| 小红书 | 图文/短视频 | 点赞、收藏、评论 |
| 微博 | 图文/视频 | 点赞、转发、评论 |
| 知乎 | 图文 | 点赞、收藏、评论 |

## Data Flow

```
用户查询 → radar-query 获取媒体数据 → radar-media 分析 → 输出媒体洞察
                    ↓
             crawled_data 表 (含 media 类型)
```

## Integration

**Handoff to:** radar-insight, radar-report
**Data from:** radar-query, MediaCrawler

## Pitfalls

1. **数据完整性** - 部分平台可能缺少某些字段
2. **视频内容** - 无法直接分析视频内容，只能依赖元数据
3. **图片分析** - 需要外部 AI 服务支持图片理解
