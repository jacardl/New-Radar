# -*- coding: utf-8 -*-
"""
DataCollector - 外部API数据采集服务
通过 ANSPIRE、BOCHA、TAVILY、FIRECRAWL 获取数据并存入本地 PostgreSQL 数据库
"""

from .collectors import (
    AnspireCollector,
    BochaCollector,
    TavilyCollector,
    FirecrawlCollector,
)

__all__ = [
    "AnspireCollector",
    "BochaCollector",
    "TavilyCollector",
    "FirecrawlCollector",
]
