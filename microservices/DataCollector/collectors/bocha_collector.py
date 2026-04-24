# -*- coding: utf-8 -*-
"""
BOCHA 数据采集器
通过 BOCHA API 获取数据
"""

import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from ..config import settings
from ..db_writer import get_db_writer


class BochaCollector:
    """BOCHA 数据采集器"""

    def __init__(self):
        self.base_url = settings.BOCHA_BASE_URL
        self.api_key = settings.BOCHA_API_KEY
        self.limit = settings.DEFAULT_LIMIT

    def _convert_response(self, data: Any, keyword: str) -> List[Dict[str, Any]]:
        """转换 BOCHA API 响应为统一格式"""
        records = []

        if not data:
            return records

        items = data.get("data", {}).get("webPages", {}).get("value", []) if isinstance(data, dict) else []

        for item in items:
            record = {
                "platform": "bocha",
                "content_type": "text",
                "content": item.get("snippet", item.get("summary", "")),
                "source_url": item.get("url", ""),
                "source_keyword": keyword,
                "title": item.get("name", ""),
                "author": item.get("author", ""),
            }
            records.append(record)

        return records

    async def collect(self, keyword: str, limit: Optional[int] = None) -> int:
        """
        采集数据

        Args:
            keyword: 搜索关键词
            limit: 采集数量限制

        Returns:
            写入的记录数
        """
        if not self.api_key:
            logger.warning("BOCHA API 密钥未配置")
            return 0

        fetch_limit = limit or self.limit

        try:
            async with httpx.AsyncClient(timeout=settings.DEFAULT_TIMEOUT) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "query": keyword,
                    "count": fetch_limit
                }

                logger.info(f"BOCHA 采集: {keyword}")
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                records = self._convert_response(data, keyword)
                logger.info(f"BOCHA 获取到 {len(records)} 条原始数据")

                if records:
                    writer = get_db_writer()
                    inserted = await writer.write_batch(records)
                    return inserted

        except Exception as e:
            logger.error(f"BOCHA 采集失败: {e}")

        return 0
