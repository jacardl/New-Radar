# -*- coding: utf-8 -*-
"""
last30days-cn Data Import Adapter
Import search results from last30days to New Radar PostgreSQL database

Integration plan:
- last30days as crawler engine, fetches fresh data from last 30 days
- Data stored directly to local database (daily_news + platform tables)
- Three engines (Query/Media/Insight) only read from local database

Author: New Radar Team
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from loguru import logger

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from backend.config import settings

from backend.db.connection import get_async_engine


PLATFORM_MAPPING = {
    "weibo": ("weibo_note", "weibo"),
    "xiaohongshu": ("xhs_note", "xiaohongshu"),
    "bilibili": ("bilibili_video", "bilibili"),
    "zhihu": ("zhihu_content", "zhihu"),
    "douyin": ("douyin_aweme", "douyin"),
    "toutiao": ("daily_news", "toutiao"),
    "baidu": ("daily_news", "baidu"),
    "wechat": ("daily_news", "wechat"),
}


class Last30DaysImporter:
    """last30days-cn Data Importer"""
    
    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent.parent
        self.last30days_script_path = str(
            project_root / "microservices" / "last30days" / "scripts" / "last30days.py"
        )
        self.engine = get_async_engine()
        
    def run_search(self, keyword: str, days: int = 30, deep: bool = False) -> List[Dict[str, Any]]:
        """Run last30days search, return results list"""
        cmd = [
            sys.executable,
            self.last30days_script_path,
            keyword,
            "--days", str(days),
            "--emit", "json",
        ]
        if deep:
            cmd.append("--deep")
            
        logger.info(f"Running last30days search: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=Path(__file__).resolve().parent.parent.parent)
        
        if result.returncode != 0:
            logger.error(f"last30days search failed: {result.stderr}")
            raise Exception(f"last30days search failed: {result.stderr}")
        
        try:
            data = json.loads(result.stdout)
            logger.info(f"last30days search returned {len(data)} results")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {result.stdout[:500]}")
            raise Exception(f"Failed to parse last30days output: {e}")
    
    async def import_to_database(
        self,
        search_results: List[Dict[str, Any]],
        topic_id: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> int:
        """Import search results to database, return count"""
        imported_count = 0
        
        async with self.engine.begin() as conn:
            for result in search_results:
                try:
                    await self._import_single_result(conn, result, topic_id, task_id)
                    imported_count += 1
                except Exception as e:
                    logger.error(f"Import failed: {e}, result: {result}")
                    continue
                    
        logger.info(f"Import complete, {imported_count} records")
        return imported_count
    
    async def _import_single_result(
        self,
        conn: AsyncConnection,
        result: Dict[str, Any],
        topic_id: Optional[str],
        task_id: Optional[str]
    ) -> bool:
        """Import single result to database"""
        
        source = result.get("source", "unknown")
        table_name, platform = PLATFORM_MAPPING.get(source, ("daily_news", source))
        
        news_id = f"last30_{source}_{result.get('id', '')}"
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "") or result.get("abstract", "") or ""
        score = result.get("score", 0.0)
        publish_time = result.get("publish_time", 0)
        
        extra_info = json.dumps({
            "last30days_score": score,
            "engagement": result.get("engagement", {}),
            "author": result.get("author", ""),
            "avatar": result.get("avatar", ""),
            "last30days_raw": result,
        }, ensure_ascii=False)
        
        now_ts = int(time.time() * 1000)
        crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        # Insert to daily_news
        await conn.execute(text("""
            INSERT INTO daily_news (
                news_id, source_platform, title, url, description, 
                extra_info, crawl_date, add_ts, last_modify_ts,
                topic_id, crawling_task_id
            ) VALUES (
                :news_id, :source_platform, :title, :url, :description,
                :extra_info, :crawl_date, :add_ts, :last_modify_ts,
                :topic_id, :crawling_task_id
            )
            ON CONFLICT (news_id, source_platform) 
            DO UPDATE SET
                description = EXCLUDED.description,
                extra_info = EXCLUDED.extra_info,
                last_modify_ts = EXCLUDED.last_modify_ts
        """), {
            "news_id": news_id,
            "source_platform": platform,
            "title": title,
            "url": url,
            "description": content,
            "extra_info": extra_info,
            "crawl_date": crawl_date,
            "add_ts": now_ts,
            "last_modify_ts": now_ts,
            "topic_id": topic_id,
            "crawling_task_id": task_id,
        })
        
        # Insert to platform-specific table
        if table_name != "daily_news":
            await self._insert_to_platform_table(conn, table_name, result, news_id, topic_id, task_id)
        
        return True
    
    async def _insert_to_platform_table(
        self,
        conn: AsyncConnection,
        table_name: str,
        result: Dict[str, Any],
        news_id: str,
        topic_id: Optional[str],
        task_id: Optional[str]
    ):
        """Insert to platform-specific table"""
        
        result_id = str(result.get("id", ""))
        title = result.get("title", "")
        content = result.get("content", "") or result.get("abstract", "") or ""
        url = result.get("url", "")
        publish_time = result.get("publish_time", 0)
        create_time = int(publish_time * 1000) if publish_time else int(time.time() * 1000)
        engagement = result.get("engagement", {})
        now_ts = int(time.time() * 1000)
        
        if table_name == "weibo_note":
            await conn.execute(text(f"""
                INSERT INTO weibo_note (
                    note_id, url, content, create_time, 
                    like_count, comment_count, repost_count,
                    topic_id, crawling_task_id
                ) VALUES (
                    :note_id, :url, :content, :create_time,
                    :like_count, :comment_count, :repost_count,
                    :topic_id, :crawling_task_id
                )
                ON CONFLICT (note_id) DO UPDATE SET
                    content = EXCLUDED.content
            """), {
                "note_id": result_id, "url": url, "content": content,
                "create_time": create_time,
                "like_count": engagement.get("like", 0),
                "comment_count": engagement.get("comment", 0),
                "repost_count": engagement.get("share", 0),
                "topic_id": topic_id, "crawling_task_id": task_id,
            })
            
        elif table_name == "xhs_note":
            await conn.execute(text(f"""
                INSERT INTO xhs_note (
                    note_id, url, title, content, create_time,
                    liked_count, collected_count, commented_count,
                    topic_id, crawling_task_id
                ) VALUES (
                    :note_id, :url, :title, :content, :create_time,
                    :liked_count, :collected_count, :commented_count,
                    :topic_id, :crawling_task_id
                )
                ON CONFLICT (note_id) DO UPDATE SET content = EXCLUDED.content
            """), {
                "note_id": result_id, "url": url, "title": title,
                "content": content, "create_time": create_time,
                "liked_count": engagement.get("like", 0),
                "collected_count": engagement.get("collect", 0),
                "commented_count": engagement.get("comment", 0),
                "topic_id": topic_id, "crawling_task_id": task_id,
            })
            
        elif table_name == "bilibili_video":
            await conn.execute(text(f"""
                INSERT INTO bilibili_video (
                    bvid, url, title, description, create_time,
                    play, video_pic, owner_name,
                    topic_id, crawling_task_id
                ) VALUES (
                    :bvid, :url, :title, :description, :create_time,
                    :play, :video_pic, :owner_name,
                    :topic_id, :crawling_task_id
                )
                ON CONFLICT (bvid) DO UPDATE SET description = EXCLUDED.description
            """), {
                "bvid": result_id, "url": url, "title": title,
                "description": content, "create_time": create_time,
                "play": engagement.get("play", 0),
                "video_pic": result.get("image", ""),
                "owner_name": result.get("author", ""),
                "topic_id": topic_id, "crawling_task_id": task_id,
            })
            
        elif table_name == "douyin_aweme":
            await conn.execute(text(f"""
                INSERT INTO douyin_aweme (
                    aweme_id, url, desc, create_time,
                    digg_count, comment_count, share_count,
                    topic_id, crawling_task_id
                ) VALUES (
                    :aweme_id, :url, :desc, :create_time,
                    :digg_count, :comment_count, :share_count,
                    :topic_id, :crawling_task_id
                )
                ON CONFLICT (aweme_id) DO UPDATE SET desc = EXCLUDED.desc
            """), {
                "aweme_id": result_id, "url": url, "desc": content,
                "create_time": create_time,
                "digg_count": engagement.get("like", 0),
                "comment_count": engagement.get("comment", 0),
                "share_count": engagement.get("share", 0),
                "topic_id": topic_id, "crawling_task_id": task_id,
            })
            
        elif table_name == "zhihu_content":
            await conn.execute(text(f"""
                INSERT INTO zhihu_content (
                    content_id, url, title, content, create_time,
                    voteup_count, comment_count,
                    topic_id, crawling_task_id
                ) VALUES (
                    :content_id, :url, :title, :content, :create_time,
                    :voteup_count, :comment_count,
                    :topic_id, :crawling_task_id
                )
                ON CONFLICT (content_id) DO UPDATE SET content = EXCLUDED.content
            """), {
                "content_id": result_id, "url": url, "title": title,
                "content": content, "create_time": create_time,
                "voteup_count": engagement.get("agree", 0),
                "comment_count": engagement.get("comment", 0),
                "topic_id": topic_id, "crawling_task_id": task_id,
            })
    
    async def search_and_import(
        self,
        keyword: str,
        days: int = 30,
        deep: bool = False,
        topic_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """One-stop: search and import"""
        task_id = f"last30_{int(time.time())}"
        results = self.run_search(keyword, days, deep)
        imported_count = await self.import_to_database(results, topic_id, task_id)
        
        platform_stats = {}
        for r in results:
            source = r.get("source", "unknown")
            platform_stats[source] = platform_stats.get(source, 0) + 1
        
        return {
            "success": True,
            "keyword": keyword,
            "days": days,
            "deep": deep,
            "total_results": len(results),
            "imported_count": imported_count,
            "task_id": task_id,
            "topic_id": topic_id,
            "platform_stats": platform_stats,
        }
    
    def diagnose(self) -> Dict[str, Any]:
        """Run last30days diagnose"""
        cmd = [sys.executable, self.last30days_script_path, "--diagnose"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse diagnose output",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }


async def main():
    """CLI entry point"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword", nargs="?", help="Search keyword")
    parser.add_argument("--days", type=int, default=30, help="Days to look back")
    parser.add_argument("--deep", action="store_true", help="Deep search")
    parser.add_argument("--topic-id", help="Related topic ID")
    parser.add_argument("--diagnose", action="store_true", help="Run diagnose")
    args = parser.parse_args()
    
    importer = Last30DaysImporter()
    
    if args.diagnose:
        result = importer.diagnose()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    if not args.keyword:
        print("Please provide a search keyword, or use --diagnose")
        return
    
    result = await importer.search_and_import(
        args.keyword,
        days=args.days,
        deep=args.deep,
        topic_id=args.topic_id
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
