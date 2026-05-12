# 公开数据 API 使用指南

用于竞品实体识别时的**别名补全**和**英文名查询**。

---

## Wikipedia API（首选）

无需 API Key，直接调用。

### 查询品牌英文名

```bash
curl "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={BRAND_NAME_CN}&format=json"
```

返回搜索结果列表，取第一个结果的 title 即为英文名。

### 查询中文名对应实体

```bash
curl "https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={BRAND_NAME_EN}&format=json"
```

### 提取页面别名

```bash
curl "https://www.wikidata.org/w/api.php?action=wbgetentities&ids={ENTITY_ID}&props=aliases|labels&format=json"
```

> 如何获取 ENTITY_ID：
> 1. 先用 srsearch 找到实体
> 2. 从搜索结果中取 page_id
> 3. 用 page_id 查询 Wikidata

---

## Wikidata SPARQL（结构化关系）

### 查询某品牌的竞品（基于 Wikidata 知识图谱）

```sparql
SELECT ?brand ?brandLabel WHERE {
  ?brand (wdt:P279|wdt:P1056) wd:QXXXXX.  # P279=subclass, P1056=product
  SERVICE wikibase:label { bd:serviceParam wikibase:language "zh,en". }
}
```

> QXXXXX 替换为品牌的 Wikidata ID（数字部分）

### 查询品牌别名

```sparql
SELECT ?alias WHERE {
  wd:QXXXXX rdfs:alias ?alias.
  FILTER(LANG(?alias) = "zh" || LANG(?alias) = "en")
}
```

---

## 百度百科（非结构化，需解析）

### 搜索页面

```
https://baike.baidu.com/search/word?word={BRAND_NAME}
```

> 返回 HTML，需正则提取：
> - 品牌名
> - 别名/曾用名
> - 所属公司
> - 产品线

### 解析页面内容

关键正则：
```regex
<h1[^>]*>([^<]+)</h1>                              # 词条名
<div[^>]*class="alias"[^>]*>([^<]+)</div>         # 别名
<div[^>]*class="abstract"[^>]*>([^<]+)</div>       # 摘要
```

---

## 天眼查/企查查

> ⚠️ 需要登录，部分数据有反爬限制

```
https://www.tianyancha.com/search?key={BRAND_NAME}
```

---

## 实用工具：品牌别名自动补全流程

```
输入：目标品牌中文名（如"果栗"）

Step 1: Wikipedia 英文搜索
→ "Guozili" → 英文名 + Wikipedia 页面

Step 2: Wikidata 别名查询
→ 获取所有已知别名（中/英）

Step 3: Wikipedia 竞品关系
→ 从 Wikipedia 页面的 "Competitors" 段落提取竞品

Step 4: 百度百科中文信息
→ 补充中文别名、公司信息

Step 5: 汇总输出
→ {标准名, 英文名, 别名[], 竞品候选[]}
```

---

## 调用频率注意

- Wikipedia API：无明确限制，但建议加缓存（同一品牌 24h 内不重复请求）
- Wikidata SPARQL：每分钟不超过 60 次请求
- 百度百科：建议加 1s 间隔，避免触发反爬

---

## 缓存策略

```
memory/competitor-kb/cache/
├── wikipedia-{brand-slug}.json   # 缓存 24h
├── wikidata-{brand-slug}.json    # 缓存 24h
└── baidu-{brand-slug}.json       # 缓存 24h
```

缓存命中时直接读缓存文件，不重复请求 API。
