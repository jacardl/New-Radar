---
name: lightpanda-web-fetch
description: Use LightPanda headless browser to fetch and dump web pages (HTML/markdown)
---
# LightPanda Web Fetch Skill

## Key Commands

### Fetch a URL and dump HTML
```bash
lightpanda fetch --dump html https://example.com --wait-ms 8000
```

### Fetch markdown instead
```bash
lightpanda fetch --dump markdown https://example.com --wait-ms 8000
```

### Fetch with frames
```bash
lightpanda fetch --dump html --with-frames https://example.com --wait-ms 8000
```

### Strip JS/CSS for cleaner output
```bash
lightpanda fetch --dump html --strip-mode js,css https://example.com --wait-ms 8000
```

## Common Pitfalls

- **Wrong command `open`**: LightPanda does NOT have an `open` command. Using `lightpanda open URL` raises `TooManyPositionalArguments`. Use `lightpanda fetch <url>` instead.
- **Wrong subcommand**: Valid commands are `fetch`, `serve`, `mcp`, `version`, `help` — not `open`.
- **Short wait time**: Heavy JS pages (e.g. zhihu.com) may need `--wait-ms 8000` or higher.

## Verified Working Example
```bash
lightpanda fetch --dump html https://www.zhihu.com --wait-ms 8000
```
Successfully returns rendered HTML of the login page.

## Additional Insights from Testing

### Dump Formats
| Format | Use Case |
|--------|----------|
| `html` | Full rendered HTML |
| `markdown` | Simplified text content |
| `semantic_tree_text` | Accessibility tree / page structure view |
| `semantic_tree` | Raw semantic tree JSON |

```bash
# Good for seeing page structure at a glance
lightpanda fetch --dump semantic_tree_text https://www.xiaohongshu.com/xxx --wait-ms 15000
```

### Known JS Warnings (Non-Fatal)
- **zhihu.com**: Page renders fine despite `TypeError: object is not iterable` in zhihu's own JS (`fromEntries` in `heifetz` app). This is a zhihu-side bug and does not affect page rendering.
- **xiaohongshu.com**: Heavily JS-rendered; increase `--wait-ms` to 15000+ for full content. Parts may still show "加载中" (loading) in unauthenticated state.

### Useful Fetch Options
```bash
# Wait for specific element
lightpanda fetch --dump html --wait-selector ".main-content" https://example.com

# Wait for network idle
lightpanda fetch --dump html --wait-until networkidle https://example.com

# Strip JS/CSS for cleaner text extraction
lightpanda fetch --dump markdown --strip-mode js,css https://example.com

# Block private networks (sandboxing)
lightpanda fetch --dump html --block-private-networks https://example.com
```
