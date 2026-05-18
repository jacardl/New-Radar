# 微信公众号文章获取 · 已知限制与备选方案

> 本文档记录微信文章获取的各种方案实测结果，供发布公众号文章时快速查阅。

## 方案实测结果（2026-05-17）

| 方案 | 路径/工具 | 结果 | 备注 |
|------|----------|------|------|
| 9Router fetch-combo | `$NINEROUTER_URL/v1/web/fetch` | ❌ | 实例均已下线（abc-tunnel.us、9router.com 返回 404） |
| 9Router jina/fetch | `$NINEROUTER_URL/v1/web/fetch` | ❌ | 同上，端点 404 |
| 搜狗微信搜索 | `weixin.sogou.com` | ❌ | 超时不可用 |
| Google Cache | `webcache.googleusercontent.com` | ❌ | 空响应 |
| Archive.org | Wayback Machine | ❌ | 无存档 |
| Scrapling StealthyFetcher | browser CDP | ❌ | WeChat 滑块验证码（混元AI）无法绕过 |
| Browserbase CDP | Browserbase Stealth | ❌ | WeChat 滑块验证码（混元AI）无法绕过 |
| 用户复制粘贴 | — | ✅ | 最可靠方案，纯文字即可 |
| 请用户截图后 AI 描述 | — | ✅ | 备选，但信息损失大 |

## 微信滑块验证码（混元AI）说明

微信公众平台使用「混元AI」滑块验证码系统，是 WeChat 特有的主动反爬机制：

- **现象**：访问微信文章 URL 时出现「环境异常 → 去验证 → 滑块拼图」页面
- **影响范围**：所有自动化工具（curl、requests、Playwright、StealthyFetcher、Browserbase）均被拦截
- **根因**：这是微信的主动反爬 JS 挑战，需要在真实浏览器环境中人工完成验证
- **状态**：**无已知绕过方案**（2026-05-17 实测确认）

## 推荐流程

**发布已有微信文章时（如 republish 场景）：**

1. **首选**：请用户把文章正文复制粘贴过来（纯文字即可，不需要格式）
2. **次选**：用户截图发给你，用 `mmx vision describe` 分析截图内容
3. **下策**：根据文章标题/主题自己重写（信息不完整，质量差）

**发布全新文章时：**
- 使用项目 GitHub 页面、README、官网作为一手信息源（不受微信限制）

## 为什么不能靠 9Router 抓微信

即使 9Router 实例在线，`fetch-combo` / `jina/fetch` 也依赖目标 URL 可被公开访问——而 mp.weixin.qq.com 在网络层面对自动化请求返回验证码页，内容本身不会出现在响应中。这是目标站点的访问控制，不是 API Key 或工具配置问题。