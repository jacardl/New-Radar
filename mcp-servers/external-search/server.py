# -*- coding: utf-8 -*-
"""
external-search MCP Server - 外部搜索 API 封装
提供 Anspire/Bocha/Tavily/Firecrawl 搜索能力
"""

import os
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("mcp>=1.2.0 is required. Install with: pip install mcp")

import httpx

# MCP Server 实例
mcp = FastMCP("external-search")

# API 配置
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

    headers = {
        "Authorization": f"Bearer {ANSPIRE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"query": query, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(base_url, headers=headers, json=payload)
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

            results = data.get("results", data.get("data", []))
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
    Firecrawl 网页抓取

    Args:
        url: 要抓取的 URL

    Returns:
        页面内容
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


if __name__ == "__main__":
    print("external-search MCP Server")
    mcp.run()
