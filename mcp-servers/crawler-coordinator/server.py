# -*- coding: utf-8 -*-
"""
crawler-coordinator MCP Server - 爬虫协调器
调用 DataCollector / MediaCrawler / MindSpider 进行数据采集
"""

import os
import subprocess
import sys
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("mcp>=1.2.0 is required. Install with: pip install mcp")

# MCP Server 实例
mcp = FastMCP("crawler-coordinator")

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

    # 添加平台过滤
    if "all" not in platforms:
        source = platforms[0] if platforms else "all"
        cmd.extend(["--source", source])

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
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
    # MediaCrawler 路径
    media_crawler_path = os.path.join(PROJECT_ROOT, "microservices", "MediaCrawler")

    # 检查是否存在
    if not os.path.exists(media_crawler_path):
        return {"error": f"MediaCrawler not found at {media_crawler_path}"}

    # 构造命令 (根据 MediaCrawler 的实际接口调整)
    cmd = [
        sys.executable, "-m", "mc_daemon",
        "--platform", platform,
        "--keyword", keyword,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=media_crawler_path,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:1000],
            "stderr": result.stderr[:500] if result.stderr else "",
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
    # MindSpider 路径
    mind_spider_path = os.path.join(PROJECT_ROOT, "microservices", "MindSpider")

    if not os.path.exists(mind_spider_path):
        return {"error": f"MindSpider not found at {mind_spider_path}"}

    # 构造命令
    cmd = [
        sys.executable, "DeepSentimentCrawling",
        "--keyword", keyword,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=mind_spider_path,
            capture_output=True,
            text=True,
            timeout=600,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:1000],
            "stderr": result.stderr[:500] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": "Deep crawl timed out after 600 seconds"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
async def get_crawler_status() -> dict[str, Any]:
    """
    获取爬虫运行状态

    Returns:
        状态信息
    """
    # TODO: 实现真实的状态检查
    # 目前返回占位信息
    return {
        "status": "unknown",
        "message": "Status check not yet implemented",
        "services": {
            "datacollector": "available",
            "mediacrawler": "available",
            "mindspider": "available",
        }
    }


if __name__ == "__main__":
    print("crawler-coordinator MCP Server")
    mcp.run()
