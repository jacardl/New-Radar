# -*- coding: utf-8 -*-
"""
FIRECRAWL 数据采集器
通过 FIRECRAWL API 抓取页面内容
"""

import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from ..config import settings
from ..db_writer import get_db_writer


class FirecrawlCollector:
    """FIRECRAWL 数据采集器"""

    def __init__(self):
        self.base_url = f"{settings.FIRECRAWL_API_URL}/scrape"
        self.api_key = settings.FIRECRAWL_API_KEY

    def _convert_response(self, data: Dict, url: str, keyword: str) -> List[Dict[str, Any]]:
        """转换 FIRECRAWL API 响应为统一格式"""
        records = []

        if not data:
            return records

        markdown = data.get("data", {}).get("markdown", "")

        if markdown:
            record = {
                "platform": "firecrawl",
                "content_type": "article",
                "content": markdown,
                "source_url": url,
                "source_keyword": keyword,
                "title": data.get("data", {}).get("title", ""),
            }
            records.append(record)

        return records

    async def collect(self, url: str, keyword: str = "") -> int:
        """
        采集数据（抓取单个页面）

        Args:
            url: 页面 URL
            keyword: 采集关键词（用于关联）

        Returns:
            写入的记录数
        """
        if not self.api_key:
            logger.warning("FIRECRAWL API 密钥未配置")
            return 0

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "url": url,
                    "formats": ["markdown"]
                }

                logger.info(f"FIRECRAWL 抓取: {url}")
                response = await client.post(self.base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                records = self._convert_response(data, url, keyword)
                logger.info(f"FIRECRAWL 获取到 {len(records)} 条原始数据")

                if records:
                    writer = get_db_writer()
                    inserted = await writer.write_batch(records)
                    return inserted

        except Exception as e:
            logger.error(f"FIRECRAWL 采集失败: {e}")

        return 0

    async def collect_urls(self, urls: List[str], keyword: str = "") -> int:
        """
        批量采集多个页面

        Args:
            urls: 页面 URL 列表
            keyword: 采集关键词

        Returns:
            写入的记录总数
        """
        total = 0
        for url in urls:
            inserted = await self.collect(url, keyword)
            total += inserted
        return total
