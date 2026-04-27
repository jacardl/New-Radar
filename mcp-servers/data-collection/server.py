# -*- coding: utf-8 -*-
"""
data-collection MCP Server - 数据采集层
整合外部搜索、URL抓取、爬虫调度、社交媒体采集能力

能力归属:
- 外部搜索 API: anspire_search, bocha_search, tavily_search
- URL 内容抓取: firecrawl_scrape
- 爬虫调度: crawl_keyword, crawl_media, crawl_deep
"""

import os
import subprocess
import sys
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("mcp>=1.2.0 is required. Install with: pip install mcp")

import httpx

# MCP Server 实例
mcp = FastMCP("data-collection")

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==================== 外部搜索 API ====================

ANSPIRE_API_KEY = os.getenv("ANSPIRE_API_KEY", "")
ANSPIRE_BASE_URL = os.getenv("ANSPIRE_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/search")
ANSPIRE_PRO_BASE_URL = os.getenv("ANSPIRE_PRO_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/prosearch")
ANSPIRE_USE_PRO = os.getenv("ANSPIRE_USE_PRO", "True").lower() == "true"

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_BASE_URL = "https://api.tavily.com/v1"

BOCHA_API_KEY = os.getenv("BOCHA_WEB_API_KEY", "")
BOCHA_BASE_URL = os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn/v1/web-search")

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_API_URL = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1")


@mcp.tool()
async def anspire_search(query: str, limit: int = 10) -> dict[str, Any]:
    """
    Anspire 深度搜索

    Args:
        query: 搜索查询
        limit: 返回结果数量 (默认 10)

    Returns:
        搜索结果
    """
    if not ANSPIRE_API_KEY:
        return {"error": "ANSPIRE_API_KEY not configured"}

    base_url = ANSPIRE_PRO_BASE_URL if ANSPIRE_USE_PRO else ANSPIRE_BASE_URL

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                base_url,
                headers={"Authorization": f"Bearer {ANSPIRE_API_KEY}"},
                params={"query": query, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", data) if isinstance(data, dict) else data
            return {
                "count": len(results) if isinstance(results, list) else 0,
                "results": results[:limit] if isinstance(results, list) else [],
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def bocha_search(query: str, limit: int = 10) -> dict[str, Any]:
    """
    Bocha 多模态搜索

    Args:
        query: 搜索查询
        limit: 返回结果数量 (默认 10)

    Returns:
        搜索结果
    """
    if not BOCHA_API_KEY:
        return {"error": "BOCHA_WEB_API_KEY not configured"}

    headers = {
        "Authorization": f"Bearer {BOCHA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(BOCHA_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            web_pages = data.get("data", {}).get("webPages", {})
            results = web_pages.get("value", []) if isinstance(web_pages, dict) else []
            return {
                "count": len(results) if isinstance(results, list) else 0,
                "results": results[:limit] if isinstance(results, list) else [],
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def tavily_search(query: str, depth: str = "basic") -> dict[str, Any]:
    """
    Tavily 新闻搜索

    Args:
        query: 搜索查询
        depth: 搜索深度 "basic" 或 "advanced" (默认 "basic")

    Returns:
        搜索结果
    """
    if not TAVILY_API_KEY:
        return {"error": "TAVILY_API_KEY not configured"}

    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "search_depth": depth,
        "max_results": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{TAVILY_BASE_URL}/search",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return {
                "count": len(data.get("results", [])),
                "results": data.get("results", []),
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def firecrawl_scrape(url: str) -> dict[str, Any]:
    """
    Firecrawl 网页抓取 - 获取指定 URL 的完整内容

    Args:
        url: 要抓取的 URL

    Returns:
        页面内容 (title, content, markdown, metadata 等)
    """
    if not FIRECRAWL_API_KEY:
        return {"error": "FIRECRAWL_API_KEY not configured"}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"urls": [url]}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{FIRECRAWL_API_URL}/scrape",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "data": data,
            }
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


# ==================== 爬虫调度 ====================

@mcp.tool()
async def crawl_keyword(keyword: str, platforms: list[str] = None) -> dict[str, Any]:
    """
    关键词采集 - 通过 DataCollector 采集外部 API 数据

    Args:
        keyword: 搜索关键词
        platforms: 平台列表 (anspire/bocha/tavily/firecrawl，默认 all)

    Returns:
        采集结果
    """
    if platforms is None:
        platforms = ["all"]

    cmd = [
        sys.executable, "-m", "microservices.DataCollector.main",
        "--keyword", keyword,
        "--limit", "10",
    ]

    if "all" not in platforms:
        source = platforms[0] if platforms else "all"
        cmd.extend(["--source", source])

    env = os.environ.copy()
    env.update({
        "DB_HOST": "db",
        "DB_PORT": "5432",
        "DB_USER": "radar",
        "DB_PASSWORD": "radar",
        "DB_NAME": "radar",
        "ANSPIRE_API_KEY": os.getenv("ANSPIRE_API_KEY", ""),
        "BOCHA_API_KEY": os.getenv("BOCHA_WEB_API_KEY", ""),
        "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
        "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY", ""),
    })

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr[:500] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Crawl timed out after 120 seconds"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def crawl_media(platform: str, keyword: str) -> dict[str, Any]:
    """
    社媒平台采集 - 调用 MediaCrawler

    Args:
        platform: 平台 (xhs/douyin/weibo/bilibili/zhihu)
        keyword: 搜索关键词

    Returns:
        采集结果
    """
    media_crawler_path = os.path.join(PROJECT_ROOT, "microservices", "MediaCrawler")

    if not os.path.exists(media_crawler_path):
        return {"error": f"MediaCrawler not found at {media_crawler_path}"}

    env = os.environ.copy()
    env.update({
        "PLATFORM": platform,
        "CRAWLER_TYPE": "search",
        "KEYWORD": keyword,
        "SAVE_DATA_OPTION": "db",
        "ENABLE_GET_WORDCLOUD": "false",
    })

    cmd = [
        sys.executable, "main.py",
        "crawl",
        "--platform", platform,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=media_crawler_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:1000],
            "stderr": result.stderr[:500] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Media crawl timed out after 300 seconds"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def crawl_deep(keyword: str) -> dict[str, Any]:
    """
    深度舆情采集 - 调用 MindSpider

    Args:
        keyword: 搜索关键词

    Returns:
        采集结果
    """
    deep_crawl_path = os.path.join(PROJECT_ROOT, "MindSpider", "DeepSentimentCrawling")

    if not os.path.exists(deep_crawl_path):
        return {"error": f"MindSpider/DeepSentimentCrawling not found at {deep_crawl_path}"}

    main_py = os.path.join(deep_crawl_path, "main.py")
    if not os.path.exists(main_py):
        return {"error": f"main.py not found at {main_py}"}

    cmd = [
        sys.executable, "main.py",
        "--keyword", keyword,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=deep_crawl_path,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:1000] if result.stdout else "",
            "stderr": result.stderr[:500] if result.stderr else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Deep crawl timed out after 600 seconds"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("data-collection MCP Server - 数据采集层")
    mcp.run()
