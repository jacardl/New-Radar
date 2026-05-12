---
name: scrapling-web-scraper
description: D4Vinci/Scrapling 自适应Web爬虫框架 — 内置Cloudflare绕过、反检测、自适应解析。触发条件：用户询问 Scrapling、反爬虫技术、Selenium替代方案时加载。
---

# Scrapling — 自适应Web爬虫框架

## 核心定位

**Scrapling** 是 Python 自适应 Web 爬虫框架，一站式处理从单次请求到大规模爬取。
- GitHub: D4Vinci/Scrapling (48k+ stars)
- 文档: scrapling.readthedocs.io
- Python 3.10+

## 反爬与隐身技术

### Fetcher 分层架构

| 类 | 用途 | 反爬能力 |
|----|------|---------|
| `Fetcher` | HTTP请求，快速 | TLS指纹 + HTTP/3 |
| `DynamicFetcher` | Playwright浏览器 | 基础隐身 |
| `StealthyFetcher` | 高级隐身 | **Cloudflare Turnstile/Interstitial bypass** |

```python
from scrapling.fetchers import StealthyFetcher

page = StealthyFetcher.fetch(
    'https://example.com',
    headless=True,
    network_idle=True  # 等待动态内容加载
)
```

### 浏览器反检测技术

- **Pre-navigation hook** (2026.04 新增)：页面导航前执行自定义设置
- **Chromium 完整伪装**：伪造真实浏览器指纹
- **Residential IPs**：住宅IP支持
- **Auto CAPTCHA solving**：自动绕过验证码
- **~3500 广告/追踪器域名屏蔽**
- **DNS-over-HTTPS** (Cloudflare)

### 代理轮换

```python
from scrapling.fetchers import ProxyRotator, StealthyFetcher

rotator = ProxyRotator(
    proxies=['http://p1', 'http://p2'],
    strategy='cyclic'  # 或 'custom'
)
page = StealthyFetcher.fetch('https://example.com', proxy=rotator)
```

## 自适应解析 (Adaptive Parsing)

### 核心问题解决

| 问题 | 解决方案 |
|------|---------|
| 网站结构变化导致选择器失效 | `adaptive=True` 自动重新定位元素 |
| Class名/ID随机化 | 文本/正则/过滤选择替代CSS |
| 需要AI识别字段 | 正则模式匹配（免费替代AI） |

### 选择器方法优先级

```python
# 1. CSS/XPath（最快）
page.css('.product h2::text').get()
page.xpath('//div[@class="product"]//h2/text()')

# 2. 文本匹配（防class变化）
page.find_by_text('Next')['href']
page.find_by_regex(r'£[\d\.,]+', first_match=True)

# 3. 过滤匹配
page.filter(lambda el: el.has_class('active') and el.has_attr('data-id'))

# 4. 自适应追踪（网站变结构时救星）
products = page.css('.product', auto_save=True)  # 保存元素唯一属性
products = page.css('.product', adaptive=True)   # 用相似度重新定位
```

### 元素相似度查找

```python
# 找到一个元素，自动找相似元素
similar = page.find_similar(element)
```

## 爬虫框架 (Spider)

### 类Scrapy的API

```python
from scrapling.spiders import Spider, Request, Response

class MySpider(Spider):
    name = "demo"
    start_urls = ["https://example.com/"]
    concurrent_requests = 10
    crawl_delay = 1.0  # 延迟秒数
    robots_txt_obey = True  # 遵守robots.txt

    async def parse(self, response: Response):
        for item in response.css('.product'):
            yield {"title": item.css('h2::text').get()}
        
        # 追踪下一页
        next_page = response.find_by_text('Next')
        if next_page:
            yield response.follow(next_page)

result = MySpider(crawldir="./data").start()
result.items.to_jsonl("output.jsonl")
```

### 核心特性

- **暂停/恢复**：Ctrl+C 优雅退出，重启从断点继续
- **流式模式**：`async for item in spider.stream()` 实时统计
- **多会话**：按ID路由到不同session
- **开发模式**：首次请求缓存到磁盘，后续重放
- **自动重试被阻止请求**
- **域名级并发限制**

## 安装与依赖

```bash
# 核心（仅解析器）
pip install scrapling

# + HTTP/浏览器功能（常用）
pip install "scrapling[fetchers]"
scrapling install  # 下载浏览器

# + AI/MCP功能
pip install "scrapling[ai]"

# + Shell工具
pip install "scrapling[shell]"

# 全量安装
pip install "scrapling[all]"
```

### Docker

```bash
docker pull pyd4vinci/scrapling
# 或
docker pull ghcr.io/d4vinci/scrapling:latest
```

### 依赖安装顺序（避坑）

> ⚠️ `pip install scrapling[fetchers]` 因依赖多会超时。正确顺序：

```bash
# 1. 核心（成功）
pip install scrapling -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. TLS指纹（必须，否则 import 报错）
pip install curl_cffi -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 浏览器支持（可选，DynamicFetcher/StealthyFetcher 需要）
pip install playwright browserforge msgspec patchright -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 下载 Chromium（约300MB，可能超时，需单独执行）
python3 -m playwright install chromium
# 或用 patchright（网络更稳定）：
patchright install chromium
```

**⚠️ 系统依赖陷阱（Playwright Chromium）：**

即使 `playwright install --with-deps chromium` 显示完成，运行时仍可能报：
```
libnspr4.so: cannot open shared object file
libglib-2.0.so.0: cannot open shared object file
```

**解法**：手动补充安装缺失库：
```bash
apt-get update && apt-get install -y --no-install-recommends \
  libnspr4 libglib2.0-0 libnss3 libdbus-1-3 libatk1.0-0 \
  libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
  libgbm1 libasound2
```

> 注意：`apt-get install` 单次60s超时限制，多次重试后仍超时 → 改用 `playwright install --with-deps chromium` **一次执行**，后台运行（120-300s）。

### API 用法（已验证）

```python
# ✅ Fetcher — HTTP层（实例方法，curl_cffi驱动）
from scrapling import Fetcher
f = Fetcher()
r = f.get('https://httpbin.org/get')
print(r.status)        # 200
print(r.text[:200])

# ✅ StealthyFetcher — 浏览器层（类方法，Playwright驱动）
#   ⚠️ 用 .fetch() 类方法，不是 .get() 或 .configure()
from scrapling import StealthyFetcher
r = StealthyFetcher.fetch(
    'https://httpbin.org/get',
    headless=True,
    network_idle=True
)
print(r.status)        # 200
print(r.body[:200])    # 原始HTML
print(r.xpath('//title/text()'))  # adaptive解析

# ⚠️ 常见错误：
#   r.status_code   ❌ (不存在)
#   r.status        ✅ (正确)
#   StealthyFetcher.get()   ❌ (不存在)
#   StealthyFetcher.fetch() ✅ (正确)
```

## 疑难排障：Chromium 缺库（ldd 诊断法）

`playwright install --with-deps` 表面成功但运行 Chromium 仍报缺库时，用 `ldd` 精确定位：

```bash
# 一步查出所有缺失的 .so 文件
ldd /root/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome | grep "not found"
```

输出示例：
```
libpixman-1.so.0 => not found
libxcb-shm.so.0 => not found
libxcb-render.so.0 => not found
```

然后有针对性地安装缺失项（多数可通过 `apt-get install` 解决，apt 超时时用手动 `dpkg -x` 解压 deb）。

**解法优先级：**
1. `apt-get install -y --no-install-recommends <缺失库>` — 首选，apt 后台运行耐心等待（deb.debian.org 约 24KB/s）
2. `dpkg -x xxx.deb /tmp/extracted` + 手动复制 `.so*` 文件到 `/usr/lib/x86_64-linux-gnu/` — apt 超时时兜底

**已验证环境：** Python 3.11, GLIBC 2.36, scrapling 0.4.7
**Fetcher：** ✅ 可用（HTTP层，curl_cffi TLS指纹伪装，UA自动轮换）
**StealthyFetcher：** ✅ 完全可用（Chromium Headless + JS渲染 + Cloudflare绕过 + adaptive解析）
**系统依赖（已全部安装）：** libnspr4 libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libcairo2 libpango-1.0-0 libpixman-1-0 libxcb-shm0 libxcb-render0

## CLI 用法

```bash
# 无需写代码，直接提取
scrapling extract https://example.com --css '.title::text'

# 安装浏览器
scrapling install --force
```

## 性能与架构

| 指标 | 表现 |
|------|------|
| 速度 | 优于大多数Python爬虫库 |
| 内存 | 懒加载 + 优化数据结构 |
| JSON序列化 | 比标准库快10x |
| 测试覆盖 | 92% + 完整类型提示 |

## 与Selenium/Playwright对比

| 维度 | Scrapling | Selenium | Playwright |
|------|-----------|----------|------------|
| 反检测 | 内置StealthyFetcher | 需手动配置 | 有限 |
| Cloudflare | 原生支持 | 困难 | 困难 |
| 自适应解析 | ✅ | ❌ | ❌ |
| 速度 | 快 | 慢 | 中等 |
| API复杂度 | 低 | 中 | 中 |

## 局限与注意事项

1. **Pagination**：无自动处理，需手动写逻辑
2. **浏览器资源**：DynamicFetcher/StealthyFetcher 需要 Chromium
3. **Python版本**：仅支持 3.10+
4. **adaptive 性能**：自适应追踪有额外开销，非必要时不用

## 适用场景

✅ **强烈推荐：**
- 需要绕过 Cloudflare/Turnstile 的网站
- 结构频繁变化的网站（如电商列表页）
- 需要规模爬取但不想运维 Scrapy

❌ **不推荐：**
- 纯静态页面（用 `requests + BeautifulSoup` 更快）
- 需要复杂鼠标交互（用 Playwright）

---

*参考：scrapling.readthedocs.io, github.com/D4Vinci/Scrapling*
