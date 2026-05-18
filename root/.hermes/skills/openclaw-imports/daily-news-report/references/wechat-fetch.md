# 微信公众号文章抓取

## 已知限制：验证码墙

从服务器 IP（39.102.x.x）访问微信文章页面 `mp.weixin.qq.com` 会触发 **TCaptcha 安全验证**（环境异常 → 需要完成验证才能访问）。

**受影响场景**：抓取任意公众号文章 URL（用于日报内容采集、或 zhili-publish 再发布）。

**不影响**：浏览器 CDP 在本地环境下访问普通网页（但同样会被微信验证码拦截）。

---

## 工具优先级

| 优先级 | 工具 | 用途 |
|--------|------|------|
| **首选** | 9Router Web Fetch | 抓取微信文章内容（需配置 9Router MCP server） |
| 次选 | 微信草稿 API | 若文章在草稿箱，可直接读取 |
| 备选 | mmx search | 用文章标题搜索，间接获取摘要 |
| 兜底 | 用户转发全文 | 请用户直接粘贴文章内容 |

---

## 9Router MCP Server 配置（首选方案）

有两种配置方式，按需选用：

### 方式一：MCP Server（推荐，用于 Hermite Agent 工具调用）

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  9router:
    command: "uvx"
    args: ["--from", "decolua/9router-mcp"]
    env:
      NINEROUTER_URL: "http://your-9router-instance:20128"
      NINEROUTER_KEY: "sk-your-key-here"   # 仅 requireApiKey=true 时需要
```

### 方式二：直接环境变量（绕过 MCP，shell 中直接 curl 调用）

```bash
export NINEROUTER_URL="http://your-9router-instance:20128"
export NINEROUTER_KEY="sk-your-key-here"
```

**验证连通性**：
```bash
curl $NINEROUTER_URL/api/health
# 期望返回：{"ok":true}
```

**验证工具可用**：
```bash
curl -s $NINEROUTER_URL/v1/models/web | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data'] if m.get('kind') in ('webSearch','webFetch')]"
# 期望看到：tavily/search, firecrawl/fetch, jina/fetch 等
```

---

## 微信草稿 API 备选方案

若目标文章曾在草稿箱出现过，可直接通过 API 读取：

```python
import requests, json

APPID = "wx38a91c353554588a"
APPSECRET = "07b4dc2d64ddbe6f53707977dbabdbbe"

# 获取 access_token
token_resp = requests.get(
    "https://api.weixin.qq.com/cgi-bin/token",
    params={"grant_type": "client_credential", "appid": APPID, "secret": APPSECRET}
)
token = token_resp.json()["access_token"]

# 获取草稿列表
drafts = requests.post(
    f"https://api.weixin.qq.com/cgi-bin/draft/batchget?access_token={token}",
    json={"offset": 0, "count": 5, "no_content": 0}
).json()
```

**注意**：`access_token` 有 2 小时有效期，需重新获取。

---

## 当所有方案均失败时

请用户直接转发/粘贴文章全文。这是**最可靠**的降级方案。

```
无法从服务器抓取微信文章内容（验证码墙限制）。
请直接粘贴文章全文，我将帮您排版发布到草稿箱。
```
