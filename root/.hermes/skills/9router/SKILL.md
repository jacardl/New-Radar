---
name: 9router
description: Entry point for 9Router — local/remote AI gateway with OpenAI-compatible REST for chat, image, TTS, embeddings, web search, web fetch. Use when the user mentions 9Router, NINEROUTER_URL, or wants AI without writing provider boilerplate. This skill covers setup + indexes capability skills; fetch the relevant capability SKILL.md from the URLs below when needed.
---

# 9Router

Local/remote AI gateway exposing OpenAI-compatible REST. One key, many providers, auto-fallback.

## Setup

```bash
export NINEROUTER_URL="http://localhost:20128"      # or VPS / tunnel URL
export NINEROUTER_KEY="sk-..."                      # from Dashboard → Keys (only if requireApiKey=true)
```

All requests: `${NINEROUTER_URL}/v1/...` with header `Authorization: Bearer ${NINE...EY}` (omit if auth disabled).

Verify: `curl $NINEROUTER_URL/api/health` → `{"ok":true}`

⚠️ **注意**：health check 有时返回 `{"ok":true}` 但实际 API 返回 530（如 Argo Tunnel 断线）。若 chat/search/fetch 均报错，即使 health ok 也说明网关已下线，需检查 tunnel 状态。

## Discover models

```bash
curl $NINEROUTER_URL/v1/models                  # chat/LLM (default)
curl $NINEROUTER_URL/v1/models/image            # image-gen
curl $NINEROUTER_URL/v1/models/tts              # text-to-speech
curl $NINEROUTER_URL/v1/models/embedding        # embeddings
curl $NINEROUTER_URL/v1/models/web              # web search + fetch (entries have `kind` field)
curl $NINEROUTER_URL/v1/models/stt              # speech-to-text
curl $NINEROUTER_URL/v1/models/image-to-text    # vision
```

Use `data[].id` as `model` field in requests. Combos appear with `owned_by:"combo"`.

Response shape:
```json
{ "object": "list", "data": [
  { "id": "openai/gpt-5", "object": "model", "owned_by": "openai", "created": 1735000000 },
  { "id": "tavily/search", "object": "model", "kind": "webSearch", "owned_by": "tavily", "created": 1735000000 }
]}
```

## Capability skills

When the user needs a specific capability, fetch that skill's `SKILL.md` from its raw URL:

| Capability | Raw URL |
|---|---|
| Chat / code-gen | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-chat/SKILL.md |
| Image generation | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-image/SKILL.md |
| Text-to-speech | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-tts/SKILL.md |
| Speech-to-text | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-stt/SKILL.md |
| Embeddings | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-embeddings/SKILL.md |
| Web search | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-web-search/SKILL.md |
| Web fetch (URL → markdown) | https://raw.githubusercontent.com/decolua/9router/refs/heads/master/skills/9router-web-fetch/SKILL.md |

**本地配置记录：** `references/instances.md` — 已知的 9Router 实例 URL、凭证状态、常见错误诊断

## ⚠️ URL 构造规则（关键）

**NINEROUTER_URL 格式：** 实际 AI 网关地址（不含 `/v1` 后缀）

```
# ✅ 正确：abc-tunnel.us 是 AI 网关
NINEROUTER_URL=https://rsgl3eb.abc-tunnel.us/v1

# ❌ 错误：9router.com 是营销网站，所有 API 均返回 404
NINEROUTER_URL=https://rsgl3eb.9router.com/v1
```

**实际请求时注意：** `NINEROUTER_URL` 已含 `/v1`，拼接路径不要再加 `/v1`：
```
# ✅ 正确
curl "$NINEROUTER_URL/chat/completions"   # → https://xxx/v1/chat/completions

# ❌ 错误（路径重复）
curl "${NINEROUTER_URL}/v1/chat/completions"  # → https://xxx/v1/v1/...
```

**Web search 端点（正确方式）：**
```
POST $NINEROUTER_URL/v1/search
Body: {"model":"tavily/search","query":"搜索内容","max_results":5}
```
不走 chat completions，是独立的 search 端点。

**Web fetch 端点：**
```
POST $NINEROUTER_URL/v1/web/fetch
Body: {"model":"jina/fetch","url":"https://...","format":"markdown"}
```

**Provider 级别模型（推荐，无需 OpenAI Key）：**
- 搜索：`tavily/search`、`exa/search`、`serper/search`、`jina/search`
- 抓取：`jina/fetch`、`firecrawl/fetch`、`tavily/fetch`

**Combo 模型（需要服务端配置 OpenAI Key）：**
- `search-combo`、`fetch-combo` — 服务端内部调 OpenAI API 做 LLM 编排
- 无 OpenAI Key 时返回：`{"error":{"message":"No active credentials for provider:openai"}}`

## Alternative Search APIs (9Router 不可用时的兜底)

当 9Router 完全下线时，使用以下备选：

### AnSpire Search
- **Endpoint**: `POST https://plugin.anspire.cn/api/ntsearch/search`
- **认证**: 需要 API Key（Header `X-API-Key` 或 URL param，格式待确认）
- **状态**: 当前返回 `403 Forbidden`，需要有效凭证
- **用途**: 通用网页搜索

### Bocha Search
- **状态**: 待探索，URL 和认证方式未知
- **来源**: 用户提示存在，endpoint `https://open.bocha.io/api/...`（推测）

**搜索兜底顺序（9Router 挂了时）：**
1. AnSpire（需 API Key）
2. Bocha（需 API Key）
3. 请用户复制粘贴内容

## Common pitfalls

- **`search-combo` / `fetch-combo` via `/v1/chat/completions` fails**: The combo models (`search-combo`, `fetch-combo`, `tavily/search`, `tavily/fetch`) when called via `/v1/chat/completions` internally call `api.openai.com:443` as an orchestration layer. Without an OpenAI key configured server-side in 9Router, these return `No active credentials for provider: openai` or 502. **Use the dedicated `/v1/search` and `/v1/web/fetch` endpoints instead** — they route to real providers (searchapi, tavily, firecrawl, jina) without the OpenAI dependency.
- **`NINEROUTER_KEY` not picked up in subshells**: If `curl` requests return `401 Invalid API key` but the key looks correct, re-source from `.env`: `export $(grep NINEROUTER_KEY ~/.hermes/.env | tr -d '\r')`. The variable may have been lost in a session boundary.
- **WeChat articles not accessible**: `fetch-combo` / `jina/fetch` against `mp.weixin.qq.com` URLs often return wrong content or nothing — WeChat uses authentication challenges (slider puzzles, 混元AI) that defeat headless fetchers. No reliable programmatic workaround exists; ask the user to copy-paste article text. Even 9Router's `fetch-combo` (which exa indexes WeChat directly) fails when the article has been access-logged from a bot IP and triggered the captcha wall.

## Errors

- 401 → set/refresh `NINEROUTER_KEY` (Dashboard → Keys)
- 400 `Invalid model format` → check `model` exists in `/v1/models/<kind>`
- 503 `All accounts unavailable` → wait `retry-after` or add another provider account
