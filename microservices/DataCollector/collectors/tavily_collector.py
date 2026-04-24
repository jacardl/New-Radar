# -*- coding: utf-8 -*-
"""
TAVILY 数据采集器
通过 TAVILY API 获取数据
"""

import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from ..config import settings
from ..db_writer import get_db_writer


class TavilyCollector:
    """TAVILY 数据采集器"""

    def __init__(self):
        self.base_url = settings.TAVILY_API_URL
        self.api_key = settings.TAVILY_API_KEY
        self.limit = settings.DEFAULT_LIMIT

    def _convert_response(self, data: Dict, keyword: str) -> List[Dict[str, Any]]:
        """转换 TAVILY API 响应为统一格式"""
        records = []

        if not data:
            return records

        items = data.get("results", [])

        for item in items:
            record = {
                "platform": "tavily",
                "content_type": "text",
                "content": item.get("content", ""),
                "source_url": item.get("url", ""),
                "source_keyword": keyword,
                "title": item.get("title", ""),
            }
            records.append(record)

        return records

    async def collect(self, keyword: str, limit: Optional[int] = None, search_depth: str = "basic") -> int:
        """
        采集数据

        Args:
            keyword: 搜索关键词
            limit: 采集数量限制
            search_depth: 搜索深度 (basic/inDepth)

        Returns:
            写入的记录数
        """
        if not self.api_key:
            logger.warning("TAVILY API 密钥未配置")
            return 0

        fetch_limit = limit or self.limit

        try:
            async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
                payload = {
                    "api_key": self.api_key,
                    "query": keyword,
                    "search_depth": search_depth,
                    "include_answer": True,
                    "max_results": fetch_limit,
                }

                logger.info(f"TAVILY 采集: {keyword}")
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                data = response.json()

                records = self._convert_response(data, keyword)
                logger.info(f"TAVILY 获取到 {len(records)} 条原始数据")

                if records:
                    writer = get_db_writer()
                    inserted = await writer.write_batch(records)
                    return inserted

        except Exception as e:
            logger.error(f"TAVILY 采集失败: {e}")

        return 0
