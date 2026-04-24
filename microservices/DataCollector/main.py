# -*- coding: utf-8 -*-
"""
DataCollector 主入口
支持通过 ANSPIRE、BOCHA、TAVILY、FIRECRAWL 采集数据并存入本地数据库
"""

import asyncio
import argparse
from typing import Optional

from loguru import logger

from .collectors import (
    AnspireCollector,
    BochaCollector,
    TavilyCollector,
    FirecrawlCollector,
)
from .db_writer import get_db_writer


async def collect_from_source(
    source: str,
    keyword: str,
    limit: Optional[int] = None,
    urls: Optional[list] = None
) -> int:
    """
    从指定数据源采集数据

    Args:
        source: 数据源 (anspire/bocha/tavily/firecrawl)
        keyword: 搜索关键词
        limit: 采集数量限制
        urls: URL列表（仅 firecrawl 使用）

    Returns:
        写入的记录数
    """
    if source == "anspire":
        collector = AnspireCollector()
        return await collector.collect(keyword, limit)

    elif source == "bocha":
        collector = BochaCollector()
        return await collector.collect(keyword, limit)

    elif source == "tavily":
        collector = TavilyCollector()
        return await collector.collect(keyword, limit)

    elif source == "firecrawl":
        if not urls:
            logger.error("FIRECRAWL 需要提供 URLs")
            return 0
        collector = FirecrawlCollector()
        return await collector.collect_urls(urls, keyword)

    elif source == "all":
        total = 0

        logger.info("=" * 50)
        logger.info("开始全量采集 (ANSPIRE + BOCHA + TAVILY)")
        logger.info("=" * 50)

        # ANSPIRE
        collector = AnspireCollector()
        count = await collector.collect(keyword, limit)
        total += count
        logger.info(f"ANSPIRE 写入: {count} 条")

        # BOCHA
        collector = BochaCollector()
        count = await collector.collect(keyword, limit)
        total += count
        logger.info(f"BOCHA 写入: {count} 条")

        # TAVILY
        collector = TavilyCollector()
        count = await collector.collect(keyword, limit)
        total += count
        logger.info(f"TAVILY 写入: {count} 条")

        logger.info("=" * 50)
        logger.info(f"全量采集完成，总计写入: {total} 条")
        logger.info("=" * 50)

        return total

    else:
        logger.error(f"未知的数据源: {source}")
        return 0


async def main_async(keyword: str, source: str, limit: Optional[int], urls: Optional[list]):
    """异步主函数"""
    writer = get_db_writer()

    try:
        total = await collect_from_source(source, keyword, limit, urls)
        logger.info(f"采集任务完成，共写入 {total} 条记录")
    finally:
        await writer.close()


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="DataCollector - 外部API数据采集服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从 ANSPIRE 采集
  python -m microservices.DataCollector.main --source anspire --keyword "人工智能"

  # 从所有源采集
  python -m microservices.DataCollector.main --source all --keyword "新能源汽车"

  # 从 FIRECRAWL 抓取特定页面
  python -m microservices.DataCollector.main --source firecrawl --keyword "AI" --urls https://example.com/article1 https://example.com/article2
        """
    )

    parser.add_argument(
        "--keyword", "-k",
        type=str,
        required=True,
        help="搜索关键词"
    )

    parser.add_argument(
        "--source", "-s",
        type=str,
        default="all",
        choices=["anspire", "bocha", "tavily", "firecrawl", "all"],
        help="数据源 (默认: all)"
    )

    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="采集数量限制 (默认: 10)"
    )

    parser.add_argument(
        "--urls", "-u",
        nargs="+",
        default=None,
        help="URL列表 (仅 firecrawl 使用)"
    )

    args = parser.parse_args()

    asyncio.run(main_async(args.keyword, args.source, args.limit, args.urls))


if __name__ == "__main__":
    main()
