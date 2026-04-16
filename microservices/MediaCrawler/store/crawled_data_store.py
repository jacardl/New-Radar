# -*- coding: utf-8 -*-
"""
Unified crawled_data store for cross-platform semantic search.

Writes normalized content/comment data to the crawled_data table
with pre-computed embedding vectors for pgvector-based semantic search.
"""

import json
import logging
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.db_session import get_session
from database.models import CrawledData
from tools.embedding import compute_embedding
from tools.time_util import get_current_timestamp

logger = logging.getLogger(__name__)


async def _build_content_text(item: Dict, platform: str, content_type: str) -> str:
    """
    Build a unified searchable text from platform-specific fields.

    Args:
        item: Platform-specific content item dict.
        platform: Platform name (xhs, dy, wb, bili, ks, tieba, zhihu).
        content_type: 'content' or 'comment'.

    Returns:
        Combined text string (title + desc/content).
    """
    parts = []

    # Title-like fields
    if item.get("title"):
        parts.append(str(item["title"]))
    if item.get("desc"):
        parts.append(str(item["desc"]))
    if item.get("content"):
        parts.append(str(item["content"]))

    return " ".join(parts)


async def _get_source_url(item: Dict, platform: str, content_type: str) -> Optional[str]:
    """Get source URL from platform-specific fields."""
    if item.get("note_url"):
        return item["note_url"]
    if item.get("aweme_url"):
        return item["aweme_url"]
    if item.get("video_url"):
        return item["video_url"]
    if item.get("content_url"):
        return item["content_url"]
    return None


async def store_crawled_data(
    item: Dict,
    platform: str,
    content_type: str,
) -> None:
    """
    Store a normalized content/comment entry to the crawled_data table
    with pre-computed embedding.

    Args:
        item: Platform-specific content/comment item dict.
        platform: Platform name (xhs, dy, wb, bili, ks, tieba, zhihu).
        content_type: 'content' or 'comment'.
    """
    try:
        # Build combined searchable text
        text = await _build_content_text(item, platform, content_type)
        if not text.strip():
            logger.warning(f"[store_crawled_data] Empty text for {platform} {content_type}, skipping embedding.")
            return

        # Compute embedding
        embedding_str = compute_embedding(text)

        # Get/create a unique source identifier
        source_url = await _get_source_url(item, platform, content_type)
        source_keyword = item.get("source_keyword", "")

        # Normalize timestamps
        now_ts = int(get_current_timestamp())
        create_time = item.get("create_time") or item.get("time") or now_ts
        add_ts = item.get("add_ts", now_ts)
        last_modify_ts = item.get("last_modify_ts", now_ts)

        async with get_session() as session:
            # Upsert: check if source_url already exists
            if source_url:
                stmt = select(CrawledData).where(
                    CrawledData.platform == platform,
                    CrawledData.content_type == content_type,
                    CrawledData.source_url == source_url,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
            else:
                existing = None

            if existing:
                # Update
                existing.embedding = embedding_str
                existing.liked_count = str(item.get("liked_count", ""))
                existing.collected_count = str(item.get("collected_count", ""))
                existing.comment_count = str(item.get("comment_count", ""))
                existing.share_count = str(item.get("share_count", ""))
                existing.last_modify_ts = last_modify_ts
                existing.raw_data = json.dumps(item, ensure_ascii=False)
                logger.info(f"[store_crawled_data] Updated {platform}/{content_type}: {source_url}")
            else:
                # Insert
                entry = CrawledData(
                    platform=platform,
                    content_type=content_type,
                    content=text,
                    source_url=source_url or "",
                    source_keyword=source_keyword,
                    create_time=create_time,
                    ip_location=str(item.get("ip_location", "")),
                    user_id=str(item.get("user_id", "")),
                    nickname=str(item.get("nickname", "")),
                    liked_count=str(item.get("liked_count", "")),
                    collected_count=str(item.get("collected_count", "")),
                    comment_count=str(item.get("comment_count", "")),
                    share_count=str(item.get("share_count", "")),
                    embedding=embedding_str,
                    raw_data=json.dumps(item, ensure_ascii=False),
                    add_ts=add_ts,
                    last_modify_ts=last_modify_ts,
                )
                session.add(entry)
                logger.info(f"[store_crawled_data] Inserted {platform}/{content_type}: {source_url}")

            await session.commit()

    except Exception as e:
        logger.error(f"[store_crawled_data] Error storing {platform}/{content_type}: {e}")
