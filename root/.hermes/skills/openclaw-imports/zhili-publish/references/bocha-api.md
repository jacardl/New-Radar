# Bocha Search API 参考

> Bocha（博查）Web Search API，可用于搜索微信文章内容摘要和引用。实测可用（2026-05-17）。

## 基础信息

- **Base URL**: `https://open.bocha.cn/api/v1`
- **文档**: `https://bocha.cn` → API开放平台 → API开发文档
- **状态**: 需要 API Key（用户需自行注册 https://open.bocha.cn 获取）

## Web Search 端点

```
POST https://open.bocha.cn/api/v1/search
```

### 请求格式

```bash
curl -X POST "https://open.bocha.cn/api/v1/search" \
  -H "Authorization: Bearer <YOUR-API-KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "site:mp.weixin.qq.com CodeGraph Claude Code",
    "count": 10,
    "summary": true
  }'
```

### 响应字段

| 字段 | 说明 |
|------|------|
| `results[].title` | 网页标题 |
| `results[].url` | 网页 URL |
| `results[].snippet` | 网页摘要 |
| `results[].siteName` | 网站名称 |
| `results[].publishTime` | 发布时间（如有） |

### 搜索微信文章的用法

```python
import urllib.request, json, ssl

def search_wechat_article(keyword, api_key):
    """搜索微信文章（通过 site:mp.weixin.qq.com 限定）"""
    url = "https://open.bocha.cn/api/v1/search"
    payload = {
        "query": f"site:mp.weixin.qq.com {keyword}",
        "count": 10,
        "summary": True
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return json.loads(resp.read())

# 使用示例
results = search_wechat_article("CodeGraph Claude Code 知识图谱", "<YOUR-KEY>")
for r in results.get("results", []):
    print(r["title"])
    print(r["url"])
    print(r.get("snippet", ""))
    print("---")
```

## 已知限制

- Bocha 搜索的是**网页索引**，不是微信文章全文。微信正文内容依然无法直接获取。
- 只能获取标题、URL、摘要，完整正文仍需用户复制粘贴或通过其他方式获取。
- API Key 需要用户自己到 https://open.bocha.cn 注册获取（网站有免费调用额度）。

## 获取免费额度

1. 访问 https://open.bocha.cn 注册账号
2. 登录后在控制台获取 API Key
3. 网站标注有免费领取调用资源包入口
