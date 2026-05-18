# 黄金价格分析逻辑

### 国内金价（基准）
**直接查询国内报价，不做汇率换算**

| 数据源 | 说明 |
|--------|------|
| 新浪财经（国内黄金） | `https://finance.sina.com.cn/futuremarket/` - **首选**，查国内现货金价/沪金主力，直接是元/克 |
| 金十数据 | `https://www.jin10.com/` - 实时国内金价 |
| mmx search（兜底）| 搜索"国内黄金价格 今日 元/克" |

**采集方式（CDP 浏览器抓取 JS 渲染页面）：**
```bash
browser(action="open", url="https://finance.sina.com.cn/futuremarket/")
browser(action="snapshot")
```

### 国际金价（参考）
仅供参考，不参与国内定价决策：

| 数据源 | 说明 |
|--------|------|
| Kitco Gold Price Chart | `https://www.kitco.com/charts/livegold.html` - 国际现货金价（美元/盎司），仅作参考 |
| 伦敦金属交易所（LME）| 现货金价参考 |

## 买入建议核心原则

用户每月计划买入10克黄金，应根据价格位置合理分配：
- 若当月金价处于月内相对低位 → 建议一次性买入较多克数（如5-7克）
- 若当月金价处于月内相对高位 → 建议少量买入（如2-3克）或观望
- 核心原则：本月总买入量不超过10克，分批布局降低成本

## 简洁模式（价格平稳）

触发条件：今日价格与近3日均价的偏离幅度 ≤2%

```
**黄金价格**
- 国内金价（沪金现货）：XXX 元/克
- 今日建议：建议买入 / 可暂时观望
- 本月已买入：X 克 / 目标：10克
```

## 详细分析模式（波动较大）

触发条件：今日价格与近3日均价的偏离幅度 >2%

```
**黄金价格**
- 国内金价（沪金现货）：XXX 元/克（较昨日涨跌：+/-XX元，涨跌幅X%）
- 参考国际金价（伦敦现货）：XXX 美元/盎司
- 简要分析（不超过3句）：……
- 今日建议：建议买入 / 可暂时观望 / 建议分批买入
- 本月已买入：X 克 / 目标：10克
```

## 本月累计买入记录

| 日期 | 买入克数 | 当月累计 |
|------|----------|----------|
| - | 0克 | 0克 |

> 注意：本月累计数据需根据实际情况更新

---

## 国际政治数据源（RSS + CDP）

| 来源 | 类型 | URL |
|------|------|-----|
| Reuters World News | RSS | `https://www.reutersagency.com/feed/?best-topics=world-news` |
| BBC World News | RSS | `https://feeds.bbci.co.uk/news/world/rss.xml` |
| AP News | RSS | `https://feeds.apnews.com/apnews/topnews` |
| Al Jazeera | RSS | `https://www.aljazeera.com/xml/rss/all.xml` |

采集方式：优先 RSS 订阅，RSS 失效时用 CDP 抓取对应官网。

## AI新闻数据源

| 来源 | 类型 | URL |
|------|------|-----|
| Hacker News (AI) | API | `https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=10` |
| TechCrunch AI | RSS | `https://techcrunch.com/category/artificial-intelligence/feed/` |
| Stanford HAI | Web | `https://hai.stanford.edu/news` |
| mmx search（英文）| 搜索 | 补充来源 |
| Tavily 英文搜索 | 搜索 | 优先国际来源（Reuters/TechCrunch/Wired） |

---

## 数据源补充原则

1. **遇到超时/失败 → 立刻换源**，不要死等
2. **专业数据优先于搜索**：RSS > CDP > 搜索
3. **英文来源优先**：国际新闻优先 Reuters/AP/AFP/BBC
4. **时效性一票否决**：非当日新闻直接移除，不展示