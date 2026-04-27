# -*- coding: utf-8 -*-
"""
data-storage MCP Server - 数据存储层
提供数据库查询、写入、向量搜索、统计分析能力

能力归属:
- 数据查询: keyword_search, vector_search, get_recent_data
- 数据写入: save_crawled_data
- 统计: get_stats
"""

import os
import json
from typing import Any, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("mcp>=1.2.0 is required. Install with: pip install mcp")

import asyncpg

# MCP Server 实例
mcp = FastMCP("data-storage")

# 数据库配置
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "radar")
DB_PASSWORD = os.getenv("DB_PASSWORD", "radar")
DB_NAME = os.getenv("DB_NAME", "radar")


async def get_pool() -> asyncpg.Pool:
    """获取数据库连接池"""
    return await asyncpg.create_pool(
        host=DB_HOST,
        port=int(DB_PORT),
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        min_size=2,
        max_size=10,
    )


@mcp.tool()
async def keyword_search(keyword: str, limit: int = 50) -> dict[str, Any]:
    """
    关键词搜索 - 在 crawled_data 表中搜索关键词

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量 (默认 50)

    Returns:
        匹配的记录列表
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, platform, content_type, content, source_url,
                   source_keyword, create_time, nickname, liked_count,
                   collected_count, comment_count, share_count
            FROM crawled_data
            WHERE content LIKE $1 OR source_keyword LIKE $1
            ORDER BY create_time DESC
            LIMIT $2
            """,
            f"%{keyword}%",
            limit
        )

        results = [dict(row) for row in rows]
        for r in results:
            if r.get("create_time"):
                r["create_time"] = r["create_time"].isoformat()

        return {
            "count": len(results),
            "results": results,
        }


@mcp.tool()
async def vector_search(query_embedding: list, limit: int = 50) -> dict[str, Any]:
    """
    向量搜索 - 使用 pgvector 进行语义相似度搜索

    Args:
        query_embedding: 查询向量 (embedding)
        limit: 返回结果数量 (默认 50)

    Returns:
        相似度最高的记录列表
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        embedding_json = json.dumps(query_embedding)

        rows = await conn.fetch(
            """
            SELECT id, platform, content_type, content, source_url,
                   source_keyword, create_time, nickname,
                   (embedding <=> $1::jsonb) AS distance
            FROM crawled_data
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::jsonb
            LIMIT $2
            """,
            embedding_json,
            limit
        )

        results = [dict(row) for row in rows]
        for r in results:
            if r.get("create_time"):
                r["create_time"] = r["create_time"].isoformat()
            if r.get("distance"):
                r["similarity"] = 1 - float(r["distance"])

        return {
            "count": len(results),
            "results": results,
        }


@mcp.tool()
async def get_recent_data(platform: str = None, hours: int = 24, limit: int = 100) -> dict[str, Any]:
    """
    获取最近数据

    Args:
        platform: 平台筛选 (可选，如 tavily/bocha 等)
        hours: 时间范围 (小时，默认 24)
        limit: 返回结果数量 (默认 100)

    Returns:
        最近的数据记录
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        if platform:
            rows = await conn.fetch(
                """
                SELECT id, platform, content_type, content, source_url,
                       source_keyword, create_time, nickname, liked_count
                FROM crawled_data
                WHERE platform = $1
                  AND create_time >= NOW() - INTERVAL '1 hour' * $2
                ORDER BY create_time DESC
                LIMIT $3
                """,
                platform,
                hours,
                limit
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, platform, content_type, content, source_url,
                       source_keyword, create_time, nickname, liked_count
                FROM crawled_data
                WHERE create_time >= NOW() - INTERVAL '1 hour' * $1
                ORDER BY create_time DESC
                LIMIT $2
                """,
                hours,
                limit
            )

        results = [dict(row) for row in rows]
        for r in results:
            if r.get("create_time"):
                r["create_time"] = r["create_time"].isoformat()

        return {
            "count": len(results),
            "results": results,
        }


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """
    获取数据库统计信息

    Returns:
        统计信息 (总记录数、按平台统计、按内容类型统计)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM crawled_data")

        platform_stats = await conn.fetch(
            """
            SELECT platform, COUNT(*) as count
            FROM crawled_data
            GROUP BY platform
            ORDER BY count DESC
            """
        )

        content_type_stats = await conn.fetch(
            """
            SELECT content_type, COUNT(*) as count
            FROM crawled_data
            GROUP BY content_type
            ORDER BY count DESC
            """
        )

        return {
            "total": total,
            "by_platform": [dict(row) for row in platform_stats],
            "by_content_type": [dict(row) for row in content_type_stats],
        }


@mcp.tool()
async def save_crawled_data(
    platform: str,
    content_type: str,
    content: str,
    source_url: str = "",
    source_keyword: str = "",
    nickname: str = "",
    liked_count: int = 0,
    collected_count: int = 0,
    comment_count: int = 0,
    share_count: int = 0,
    metadata: dict = None,
) -> dict[str, Any]:
    """
    保存爬取的数据到数据库

    Args:
        platform: 平台标识
        content_type: 内容类型 (text/article/image/video)
        content: 正文内容
        source_url: 来源链接
        source_keyword: 采集关键词
        nickname: 作者/昵称
        liked_count: 点赞数
        collected_count: 收藏数
        comment_count: 评论数
        share_count: 分享数
        metadata: 额外元数据

    Returns:
        保存结果
    """
    pool = await get_pool()
    embedding = json.dumps([])

    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO crawled_data (
                    platform, content_type, content, source_url, source_keyword,
                    embedding, nickname, liked_count, collected_count,
                    comment_count, share_count, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
                """,
                platform,
                content_type,
                content,
                source_url,
                source_keyword,
                embedding,
                nickname,
                liked_count,
                collected_count,
                comment_count,
                share_count,
                json.dumps(metadata or {}),
            )
            return {
                "success": True,
                "id": row["id"],
                "message": f"Record saved successfully with id {row['id']}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


if __name__ == "__main__":
    print("data-storage MCP Server - 数据存储层")
    mcp.run()
