---
name: scrapling
description: >
  Scrapling — adaptive web scraping framework for Python. Handles everything from
  single requests to full-scale crawls. Supports anti-bot bypass (Cloudflare
  Turnstile), browser automation (Playwright), and adaptive element parsing.
  Use as fallback when 9Router web-fetch fails.
---

# Scrapling — Adaptive Web Scraping

**Stars**: 49.5k · **Install**: `pip install scrapling`

## When to Use

Fallback chain for URL → content:
1. **9Router fetch-combo** (primary)
2. **Scrapling StealthyFetcher** (fallback — handles Cloudflare/Turnstile)
3. **Minimax MCP** (last resort)

Also use directly when you know the target site has anti-bot protection.

## Core Fetchers

| Class | Best for |
|---|---|
| `Fetcher` | Fast HTTP, impersonates Chrome TLS fingerprint |
| `StealthyFetcher` | Anti-bot bypass (Cloudflare Turnstile/Interstitial) |
| `DynamicFetcher` | JS-rendered pages via Playwright Chromium |

```python
from scrapling.fetchers import StealthyFetcher, DynamicFetcher

# Simple fetch (auto-closes browser)
page = StealthyFetcher.fetch('https://example.com', headless=True)

# Keep browser open (persistent session)
with StealthySession(headless=True, solve_cloudflare=True) as session:
    page = session.fetch('https://nopecha.com/demo/cloudflare')
    data = page.css('#content a').getall()

# Dynamic/JS-rendered pages
page = DynamicFetcher.fetch('https://example.com', headless=True)
```

## Parsing — CSS / XPath / Text

```python
# CSS selectors (Scrapy/Parsel-style pseudo-elements)
title = page.css('h1::text').get()          # first text
titles = page.css('h2::text').getall()       # all texts
links = page.css('a::attr(href)').getall()   # href attrs
imgs = page.css('img::attr(src)').getall()  # src attrs

# XPath
content = page.xpath('//div[@class="content"]//text()').getall()

# Text search (finds elements containing text)
results = page.find_all(text='Claude')

# Adaptive — survives page structure changes
items = page.css('.product', adaptive=True)
```

## Spider Framework (Large Crawls)

```python
from scrapling.spiders import Spider, Response

class MySpider(Spider):
    name = 'demo'
    start_urls = ['https://example.com/']

    async def parse(self, response: Response):
        for item in response.css('.product'):
            yield {'title': item.css('h2::text').get()}

MySpider().start()
```

## CLI (No-Code)

```bash
scrapling https://example.com                    # GET request
scrapling https://example.com --method POST     # POST request
scrapling https://example.com --js             # Enable JS rendering
scrapling https://example.com --stealth         # Stealth/anti-bot mode
```

## Key Parameters

- `headless`: Run browser without GUI (default True)
- `solve_cloudflare`: Attempt Cloudflare Turnstile bypass
- `network_idle`: Wait until network stops requests
- `adaptive`: Auto-relocate elements when page structure changes
- `impersonate`: Browser to impersonate (`chrome`, `firefox`, etc.)

## WeChat Article Scraping (Practical)

```python
from scrapling.fetchers import StealthyFetcher

# Try stealth first (bypasses most anti-bot)
try:
    page = StealthyFetcher.fetch(
        'https://mp.weixin.qq.com/s/PdnzdlANDDDrMrTMYhahvw',
        headless=True,
        solve_cloudflare=True,
        network_idle=True
    )
    # Extract article content
    title = page.css('#activity-name::text').get()
    author = page.css('#js_name::text').get()
    content = page.css('#js_content::text').getall()
    print('\n'.join(content))
except Exception as e:
    print(f'StealthyFetcher failed: {e}')
    # Fall back to DynamicFetcher with full browser
    try:
        from scrapling.fetchers import DynamicFetcher
        page = DynamicFetcher.fetch(
            'https://mp.weixin.qq.com/s/PdnzdlANDDDrMrTMYhahvw',
            headless=True,
            network_idle=True
        )
        content = page.css('#js_content').get()
    except Exception as e2:
        print(f'DynamicFetcher also failed: {e2}')
```

## Gotchas

- `StealthyFetcher` needs Chromium/Chrome installed (auto-installed by playwright)
- On first run of `DynamicFetcher`/`StealthyFetcher`, Playwright downloads browsers (one-time ~100MB)
- Anti-bot bypass is best-effort — some sites may still block
- For Cloudflare specifically: `solve_cloudflare=True` enables Turnstile challenge solving
