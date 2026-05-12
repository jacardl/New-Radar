---
name: 9router
description: 9Router — 本地/远程 AI 网关，OpenAI 兼容 REST 接口，一个 Key 调用多个 Provider，自动容灾切换。触发条件：用户提及 9Router、NINEROUTER_URL，或需要聚合多个 AI Provider（Chat、图像、TTS、Embedding、联网搜索、网页抓取）时使用。
---

# 9Router

本地/远程 AI 网关，OpenAI 兼容 REST，一个 Key 调用多个 Provider，支持自动容灾切换。

## 环境变量

```bash
export NINEROUTER_URL="http://localhost:20128"   # 或 VPS / tunnel URL
export NINEROUTER_KEY="sk-..."                  # Dashboard → Keys（requireApiKey=true 时必填）
```

## 健康检查

```bash
curl $NINEROUTER_URL/api/health  # → {"ok":true}
```

## 模型发现

```bash
# Chat / LLM（默认）
curl $NINEROUTER_URL/v1/models

# 图像生成
curl $NINEROUTER_URL/v1/models/image

# 语音合成 TTS
curl $NINEROUTER_URL/v1/models/tts

# 语音转文字 STT
curl $NINEROUTER_URL/v1/models/stt

# 向量嵌入
curl $NINEROUTER_URL/v1/models/embedding

# 联网搜索 + 网页抓取
curl $NINEROUTER_URL/v1/models/web
```

返回的 `data[].id` 即为请求时的 `model` 字段值。Combo 模型通过 `owned_by:"combo"` 识别。

响应示例：
```json
{
  "object": "list",
  "data": [
    { "id": "openai/gpt-5", "object": "model", "owned_by": "openai", "created": 1735000000 },
    { "id": "tavily/search", "object": "model", "kind": "webSearch", "owned_by": "tavily" }
  ]
}
```

## 能力对应 Skill

| 能力 | Skill 路径 |
|------|-----------|
| Chat / 代码生成 | `9router-chat/SKILL.md` |
| 图像生成 | `9router-image/SKILL.md` |
| TTS | `9router-tts/SKILL.md` |
| STT | `9router-stt/SKILL.md` |
| Embeddings | `9router-embeddings/SKILL.md` |
| **联网搜索** | `9router-web-search/SKILL.md` |
| **网页抓取** | `9router-web-fetch/SKILL.md` |

## 常见错误

| 错误 | 处理方式 |
|------|----------|
| 401 Unauthorized | 重新从 Dashboard → Keys 获取 Key |
| 400 `Invalid model format` | 确认 model 存在于 `/v1/models/` 列表 |
| 503 `All accounts unavailable` | 等待 `retry-after` 时间或添加更多 Provider 账号 |

## 请求格式

所有请求：`${NINEROUTER_URL}/v1/...`

Header：`Authorization: Bearer ${NINEROUTER_KEY}`（认证关闭时可省略）

## Provider 列表（联网能力）

### Web Search
`tavily/search` · `exa/search` · `brave-search` · `serper` · `perplexity` · `linkup` · `google-pse` · `searchapi` · `youcom` · `searxng`

### Web Fetch（网页抓取）
`firecrawl/fetch` · `jina/fetch` · `tavily/extract` · `exa/contents`

Combo：`search-combo`（自动切换）· `fetch-combo`（自动切换）
