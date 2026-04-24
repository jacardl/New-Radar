---
name: radar-report
description: 报告生成引擎 - 将舆情分析结果生成为结构化报告。支持 Markdown、HTML、PDF 格式输出。
version: 1.0.0
author: New Radar Team
license: MIT
metadata:
  hermes:
    tags: [radar, report, export, document]
    related_skills: [radar-query, radar-insight, radar-forum]
---

# Radar Report Engine

**Role:** 报告生成引擎

**Function:** 将舆情分析结果生成为结构化报告文档

## When to Use This Skill

当用户需要：
- 生成舆情分析报告
- 导出分析结果为文档
- 创建定期报告模板
- 制作可视化报告

## Core Capabilities

1. **结构化报告** - 按标准模板生成报告
2. **多格式导出** - 支持 Markdown、HTML、PDF
3. **图表生成** - 自动生成数据可视化图表
4. **模板定制** - 支持自定义报告模板

## Report Structure

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

## Integration

**Handoff from:** radar-insight, radar-forum
**Output to:** File system, API response

## Example

```
用户: 生成一份关于"人工智能"的分析报告

Report Engine:
1. 接收来自 radar-insight 的分析数据
2. 按模板结构组织内容
3. 生成 Markdown 格式报告
4. 可选：转换为 HTML/PDF
```

## Pitfalls

1. **数据完整性** - 报告质量依赖输入数据
2. **格式兼容性** - 不同格式有不同限制
3. **大文件** - PDF 生成可能较慢
