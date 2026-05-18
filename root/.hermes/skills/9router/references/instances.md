# 9Router 实例配置记录

## 已知实例

| 实例 | URL | 用途 | 状态 |
|------|-----|------|------|
| 佳哥 ABC Tunnel | `https://rsgl3eb.abc-tunnel.us/v1` | AI 网关（chat/search/fetch） | ❌ **已下线** — 所有路径返回 404，tunnel 已断开 |
| 9Router 营销站 | `https://rsgl3eb.9router.com/v1` | 营销网站（所有 API 均 404） | ❌ |

## 常见错误

### 1. URL 指错站点（all API return 404）
**症状：** 所有请求返回 `<!DOCTYPE html><title>404: This page could not be found.</title>`

**原因：** `NINEROUTER_URL` 设置为 `https://rsgl3eb.9router.com/v1`（营销站）而非实际的 AI 网关。

**修复：** 确认 NINEROUTER_URL 为 `https://rsgl3eb.abc-tunnel.us/v1`

### 2. 路径重复加 /v1（all API return 404）
**症状：** 请求返回 404，URL 中出现 `/v1/v1/`

**原因：** `NINEROUTER_URL` 已含 `/v1`，拼接时又加了 `/v1`

**修复：** 拼接时用 `$NINEROUTER_URL/chat/completions` 不要加 `/v1`

### 3. search-combo / fetch-combo 报 no active credentials
**症状：** `{"error":{"message":"No active credentials for provider: openai"}}`

**原因：** `search-combo` / `fetch-combo` 服务端内部调 OpenAI API 做 LLM 编排，**需要 9Router 服务端配置 OpenAI API Key**，不是 Tavily Key。

**解决：**
- 推荐：直接用 provider 级别模型（`tavily/search`、`jina/fetch`），走独立端点 `/v1/search` 和 `/v1/web/fetch`，**不需要 OpenAI Key**
- 若必须用 combo 模型：需在 9Router 服务端配置 OpenAI API Key

### 5. 所有实例均下线（当前状态 — 2026-05-17）
**症状：** 所有 9Router 实例（abc-tunnel.us、9router.com）所有路径均返回 404 HTML

**影响：** `fetch-combo`、`jina/fetch`、`tavily/fetch` 等所有 web-fetch 模型均不可用

**处理：** 见「直隶按察使」公众号技能的 `references/wechat-fetch-fallbacks.md」

## 调试命令

```bash
# 验证 NINEROUTER_URL 是否指向正确的 AI 网关
curl "$NINEROUTER_URL/api/health"
# 期望返回: {"ok":true}  或类似 JSON，不是 404 HTML

# 验证 chat API 可用（不需要 provider key 的模型）
curl -s "$NINEROUTER_URL/chat/completions" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax-cn/MiniMax-M2.7","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
# 期望: JSON 响应，不是 404 HTML

# 查看可用 web 模型
curl -s "$NINEROUTER_URL/v1/models/web" -H "Authorization: Bearer $NINEROUTER_KEY"
# 期望: 包含 search-combo, fetch-combo 等

# 测试 web search（通过 /v1/search 端点，无需 OpenAI Key）
curl -s -X POST "$NINEROUTER_URL/v1/search" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tavily/search","query":"测试 query","max_results":3}'
# 期望: JSON 含 results 数组；无需 OpenAI Key

# 测试 web fetch（通过 /v1/web/fetch 端点）
curl -s -X POST "$NINEROUTER_URL/v1/web/fetch" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"jina/fetch","url":"https://example.com","format":"markdown"}'
# 期望: JSON 含 content.text

# 测试 combo 模型（需要服务端 OpenAI Key）
curl -s "$NINEROUTER_URL/chat/completions" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"search-combo","messages":[{"role":"user","content":"test"}],"max_tokens":50}'
# 无 OpenAI Key 时返回: {"error":{"message":"No active credentials for provider: openai"}}
```
