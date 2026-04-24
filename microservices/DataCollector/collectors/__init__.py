# -*- coding: utf-8 -*-
"""
数据采集器模块
"""

from .anspire_collector import AnspireCollector
from .bocha_collector import BochaCollector
from .tavily_collector import TavilyCollector
from .firecrawl_collector import FirecrawlCollector

__all__ = [
    "AnspireCollector",
    "BochaCollector",
    "TavilyCollector",
    "FirecrawlCollector",
]
