# -*- coding: utf-8 -*-
"""
db-query MCP Server - 数据库查询工具
提供对 crawled_data 表的关键词搜索和向量检索
"""

import json
import os
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise ImportError("mcp>=1.2.0 is required. Install with: pip install mcp")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# MCP Server 实例
mcp = FastMCP("db-query")

# 数据库配置
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5444")
DB_USER = os.getenv("DB_USER", "radar")
DB_PASSWORD = os.getenv("DB_PASSWORD", "radar")
DB_NAME = os.getenv("DB_NAME", "radar")


def get_engine() -> AsyncEngine:
    """获取数据库引擎"""
    url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_async_engine(url, echo=False)


@mcp.tool()
async def keyword_search(keyword: str, limit: int = 10) -> dict[str, Any]:
    """
    关键词搜索 crawled_data 表

    Args:
        keyword: 搜索关键词
        limit: 返回结果数量限制 (默认 10)

    Returns:
        包含搜索结果的字典
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, platform, content_type, content, source_url,
                           source_keyword, create_time, nickname, liked_count
                    FROM crawled_data
                    WHERE content LIKE :keyword
                       OR source_keyword LIKE :keyword
                    ORDER BY create_time DESC
                    LIMIT :limit
                """),
                {"keyword": f"%{keyword}%", "limit": limit}
            )
            rows = result.fetchall()
            return {
                "count": len(rows),
                "results": [
                    {
                        "id": row[0],
                        "platform": row[1],
                        "content_type": row[2],
                        "content": row[3],
                        "source_url": row[4],
                        "source_keyword": row[5],
                        "create_time": row[6],
                        "nickname": row[7],
                        "liked_count": row[8],
                    }
                    for row in rows
                ]
            }
    finally:
        await engine.dispose()


@mcp.tool()
async def vector_search(query_embedding: list[float], limit: int = 10) -> dict[str, Any]:
    """
    pgvector 语义检索

    Args:
        query_embedding: 查询向量 (浮点数数组)
        limit: 返回结果数量限制 (默认 10)

    Returns:
        包含相似结果的字典
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            embedding_json = json.dumps(query_embedding)
            result = await conn.execute(
                text("""
                    SELECT id, platform, content_type, content, source_url,
                           source_keyword, create_time,
                           embedding::text,
                           (embedding::jsonb <-> :embedding::jsonb) as distance
                    FROM crawled_data
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding::jsonb <-> :embedding::jsonb
                    LIMIT :limit
                """),
                {"embedding": embedding_json, "limit": limit}
            )
            rows = result.fetchall()
            return {
                "count": len(rows),
                "results": [
                    {
                        "id": row[0],
                        "platform": row[1],
                        "content_type": row[2],
                        "content": row[3],
                        "source_url": row[4],
                        "source_keyword": row[5],
                        "create_time": row[6],
                        "distance": float(row[8]) if row[8] else None,
                    }
                    for row in rows
                ]
            }
    finally:
        await engine.dispose()


@mcp.tool()
async def get_recent_data(platform: str = "", hours: int = 24) -> dict[str, Any]:
    """
    获取最近 N 小时的数据

    Args:
        platform: 平台筛选 (空字符串表示所有平台)
        hours: 小时数 (默认 24)

    Returns:
        包含最近数据的字典
    """
    import time
    engine = get_engine()
    cutoff_time = int(time.time() * 1000) - (hours * 60 * 60 * 1000)

    try:
        async with engine.connect() as conn:
            if platform:
                result = await conn.execute(
                    text("""
                        SELECT id, platform, content_type, content, source_url,
                               source_keyword, create_time
                        FROM crawled_data
                        WHERE platform = :platform AND create_time >= :cutoff
                        ORDER BY create_time DESC
                    """),
                    {"platform": platform, "cutoff": cutoff_time}
                )
            else:
                result = await conn.execute(
                    text("""
                        SELECT id, platform, content_type, content, source_url,
                               source_keyword, create_time
                        FROM crawled_data
                        WHERE create_time >= :cutoff
                        ORDER BY create_time DESC
                    """),
                    {"cutoff": cutoff_time}
                )
            rows = result.fetchall()
            return {
                "count": len(rows),
                "platform": platform or "all",
                "hours": hours,
                "results": [
                    {
                        "id": row[0],
                        "platform": row[1],
                        "content_type": row[2],
                        "content": row[3],
                        "source_url": row[4],
                        "source_keyword": row[5],
                        "create_time": row[6],
                    }
                    for row in rows
                ]
            }
    finally:
        await engine.dispose()


@mcp.tool()
async def get_stats() -> dict[str, Any]:
    """
    获取数据库统计信息

    Returns:
        统计信息字典
    """
    engine = get_engine()
    try:
        async with engine.connect() as conn:
            # 总记录数
            total_result = await conn.execute(text("SELECT COUNT(*) FROM crawled_data"))
            total = total_result.scalar() or 0

            # 各平台数量
            platform_result = await conn.execute(text("""
                SELECT platform, COUNT(*) as count
                FROM crawled_data
                GROUP BY platform
                ORDER BY count DESC
            """))
            platforms = {row[0]: row[1] for row in platform_result.fetchall()}

            # 各内容类型数量
            type_result = await conn.execute(text("""
                SELECT content_type, COUNT(*) as count
                FROM crawled_data
                GROUP BY content_type
                ORDER BY count DESC
            """))
            content_types = {row[0]: row[1] for row in type_result.fetchall()}

            return {
                "total_records": total,
                "by_platform": platforms,
                "by_content_type": content_types,
            }
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import sys
    # 支持直接运行: python server.py
    # 或通过 hermes mcp add 调用
    print("db-query MCP Server")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    mcp.run()
