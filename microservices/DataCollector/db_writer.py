# -*- coding: utf-8 -*-
"""
数据库写入器
将采集的数据写入 PostgreSQL crawled_data 表
"""

import json
import time
import asyncpg
from typing import List, Dict, Any, Optional
from loguru import logger

from .config import settings


class DatabaseWriter:
    """数据库写入器"""

    _pool: Optional[asyncpg.Pool] = None

    def __init__(self):
        self._pool = None

    async def _get_pool(self) -> asyncpg.Pool:
        """获取数据库连接池"""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=settings.DB_HOST,
                port=settings.DB_PORT,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def write_batch(self, records: List[Dict[str, Any]]) -> int:
        """
        批量写入数据到 crawled_data 表

        Args:
            records: 记录列表，每条记录包含:
                - platform: str, 平台标识
                - content: str, 正文内容
                - content_type: str, 内容类型 (text/article/image/video)
                - source_url: str, 来源链接
                - source_keyword: str, 采集关键词
                - title: str (optional), 标题
                - author: str (optional), 作者
                - ip_location: str (optional), IP属地
                - liked_count: int (optional), 点赞数
                - collected_count: int (optional), 收藏数
                - comment_count: int (optional), 评论数
                - share_count: int (optional), 分享数

        Returns:
            写入的记录数
        """
        if not records:
            return 0

        pool = await self._get_pool()
        inserted = 0

        async with pool.acquire() as conn:
            for record in records:
                try:
                    embedding = json.dumps([])  # 向量可后续生成

                    await conn.execute(
                        """
                        INSERT INTO crawled_data (
                            platform, content_type, content, source_url, source_keyword,
                            embedding, ip_location, user_id, nickname,
                            liked_count, collected_count, comment_count, share_count
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT DO NOTHING
                        """,
                        record.get("platform", "unknown"),
                        record.get("content_type", "text"),
                        record.get("content", ""),
                        record.get("source_url", ""),
                        record.get("source_keyword", ""),
                        embedding,
                        record.get("ip_location", ""),
                        record.get("user_id", ""),
                        record.get("author", ""),
                        record.get("liked_count", 0),
                        record.get("collected_count", 0),
                        record.get("comment_count", 0),
                        record.get("share_count", 0),
                    )
                    inserted += 1
                except Exception as e:
                    logger.warning(f"写入记录失败: {e}")

        logger.info(f"成功写入 {inserted}/{len(records)} 条记录")
        return inserted

    async def close(self):
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None


# 全局实例
_db_writer: Optional[DatabaseWriter] = None


def get_db_writer() -> DatabaseWriter:
    """获取数据库写入器实例"""
    global _db_writer
    if _db_writer is None:
        _db_writer = DatabaseWriter()
    return _db_writer
