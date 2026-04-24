---
name: radar-forum
description: 论坛调度引擎 - 协调多个引擎完成复杂舆情分析任务。作为主持人角色调度 radar-query、radar-insight、radar-media 等引擎。
version: 1.0.0
author: New Radar Team
license: MIT
metadata:
  hermes:
    tags: [radar, forum, coordinator, orchestration]
    related_skills: [radar-query, radar-insight, radar-media, radar-report]
---

# Radar Forum Engine

**Role:** 论坛调度引擎（主持人）

**Function:** 作为协调者，调度多个引擎完成复杂舆情分析任务

## When to Use This Skill

当用户需要：
- 完成复杂的综合性舆情分析
- 需要多个引擎协作
- 生成完整的舆情分析报告
- 进行多角度、多维度的分析

## Core Capabilities

1. **任务分解** - 将复杂任务分解为子任务
2. **引擎调度** - 协调多个引擎的执行顺序
3. **结果整合** - 汇总各引擎的分析结果
4. **质量把控** - 确保分析结果的准确性和完整性

## Coordination Pattern

```
用户请求 → Forum 分析任务 → 调度 Query/Insight/Media
                              ↓
                        汇总结果 → 输出综合报告
```

## Example Workflow

### 综合舆情分析
```
用户: 帮我做一个关于"某新品发布"的全网舆情分析

Forum Engine:
1. 分解任务：
   - 子任务1: radar-query 搜索相关信息
   - 子任务2: radar-media 分析社媒数据
   - 子任务3: radar-insight 进行深度分析

2. 并行/串行执行各子任务

3. 整合结果：
   - 汇总搜索数据
   - 分析媒体趋势
   - 输出洞察结论

4. 生成综合报告
```

## Integration

**Handoff to:** radar-query, radar-insight, radar-media, radar-report
**Data from:** All other radar skills

## Pitfalls

1.