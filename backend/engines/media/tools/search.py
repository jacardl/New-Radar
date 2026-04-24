ï»¿"""
ä¸ä¸º AI Agent è®¾è®¡çæ¬å°èææ°æ®åºæ¥è¯¢å·¥å·ï¿½?(ï¿½?Bocha/Anspire æ¥å£)

çæ¬: 2.0
æåæ´ï¿½? 2025-08-23

æ­¤èæ¬å·²éæä¸ºç´æ¥æ¥è¯¢æ¬ï¿½?MySQL æ°æ®åºï¼ä¸åä¾èµå¤é¨ï¿½?Bocha ï¿½?Anspire APIï¿½?ä»¥è§£ï¿½?API è°ç¨ææ¬é«ãè¯·æ±é¢ç¹çé®é¢ï¿½?åæ¶ä¿æäºåææ°æ®ç»ï¿½?(BochaResponse, WebpageResult ï¿½? çå¼å®¹æ§ï¼
ä½¿å¾ MediaEngine/agent.py æ éä¿®æ¹å³å¯æ ç¼åæ¢å°æ¬å°æ°æ®åºï¿½?"""

import os
import json
import sys
import datetime
import asyncio
import concurrent.futures
from typing import List, Dict, Any, Optional, Literal, Tuple
from dataclasses import dataclass, field

from loguru import logger
from ..utils.config import settings

# æ·»å utilsç®å½å°Pythonè·¯å¾

# å¯¼å¥å±äº«çæ°æ®åºå·¥å·
try:
    from backend.db.connection import fetch_all
except ImportError:
    # å¼å®¹ç´æ¥è¿è¡æµè¯
    sys.path.append(root_dir)
    from backend.db.connection import fetch_all

def _run_async(coro):
    """å®å¨çå¼æ­¥æ§è¡åè£å¨"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)

# --- 1. æ°æ®ç»æå®ä¹ (ä¿æå¼å®¹) ---

@dataclass
class WebpageResult:
    """ç½é¡µæç´¢ç»æ"""
    name: str
    url: str
    snippet: str
    display_url: Optional[str] = None
    date_last_crawled: Optional[str] = None

@dataclass
class ImageResult:
    """å¾çæç´¢ç»æ"""
    name: str
    content_url: str
    host_page_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class ModalCardResult:
    """æ¨¡æå¡ç»æåæ°æ®ç»ï¿½?""
    card_type: str
    content: Dict[str, Any]

@dataclass
class BochaResponse:
    """å°è£æç´¢ç»æï¼å¼ï¿½?Bocha API ç»æ"""
    query: str
    conversation_id: Optional[str] = None
    answer: Optional[str] = None
    follow_ups: List[str] = field(default_factory=list)
    webpages: List[WebpageResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    modal_cards: List[ModalCardResult] = field(default_factory=list)

@dataclass
class AnspireResponse:
    """å°è£æç´¢ç»æï¼å¼ï¿½?Anspire API ç»æ"""
    query: str
    conversation_id: Optional[str] = None
    score: Optional[float] = None
    webpages: List[WebpageResult] = field(default_factory=list)


# --- 2. æ ¸å¿å®¢æ·ç«¯ä¸ä¸ç¨å·¥å·ï¿½?(æ¬å°æ°æ®åºç) ---

class LocalDatabaseSearch:
    """
    æ¬å°æ°æ®åºæç´¢æ ¸å¿ç±»ï¿½?    å®ç°éç¨ï¿½?SQL æ¥è¯¢é»è¾ï¼ä¾ BochaMultimodalSearch ï¿½?AnspireAISearch è°ç¨ï¿½?    """
    
    @staticmethod
    def _parse_timestamp(ts: Any) -> Optional[str]:
        if not ts: return None
        try:
            if isinstance(ts, datetime.datetime):
                return ts.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(ts, str) and ts.isdigit():
                ts = int(ts)
            if isinstance(ts, int):
                if ts > 1e11:  # 13ä½æ¯«ç§æ¶é´æ³
                    return datetime.datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
                return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(ts, str):
                return ts
        except Exception:
            return None
        return None

    def _build_keyword_conditions(self, topic: str, columns: List[str]) -> Tuple[str, dict]:
        """
        (ä¸åä½¿ç¨ï¿½?LIKE æ¨¡ç³å¹éï¼ä¿çæ­¤å½æ°ä»¥é²å¶ä»å°æ¹è°ç¨)
        """
        keywords = [k.strip() for k in topic.replace('+', ' ').split() if k.strip()][:5]
        if not keywords:
            keywords = [topic]
            
        conditions = []
        params = {}
        for i, kw in enumerate(keywords):
            kw_key = f"kw_{i}"
            params[kw_key] = f"%{kw}%"
            col_conds = [f"{col} LIKE :{kw_key}" for col in columns]
            conditions.append("(" + " OR ".join(col_conds) + ")")
            
        return " AND ".join(conditions), params

    def _build_vector_conditions(self, topic: str) -> Tuple[str, dict]:
        """
        ä½¿ç¨æ¬å° Embedding è¿è¡åéç¸ä¼¼åº¦å¹éï¿½?        è¿å: SQL æåº/è®¡ç®çæ®µ ï¿½?params (åå« query_vector å­ç¬¦ï¿½?
        """
        from utils.embedding import get_embedding
        try:
            emb = get_embedding(topic)
            emb_str = f"[{','.join(map(str, emb))}]"
            order_sql = "embedding <=> :query_vector"
            return order_sql, {"query_vector": emb_str}
        except Exception as e:
            logger.error(f"Generate embedding for query failed: {e}")
            return "1", {} # fallback

    def _safe_query(self, sql: str, params: dict) -> List[dict]:
        try:
            return _run_async(fetch_all(sql, params))
        except Exception as e:
            logger.debug(f"æ¥è¯¢æ¬å°åºåºéæè¡¨ä¸å­å¨: {e}")
            return []

    def _search_local_db(self, query: str, limit: int = 10, start_ts: int = 0, end_ts: int = 0):
        return _run_async(self._search_local_db_async(query, limit, start_ts, end_ts))

    async def _search_local_db_async(self, query: str, limit: int = 10, start_ts: int = 0, end_ts: int = 0) -> List[WebpageResult]:
        """
        æ§è¡è·¨è¡¨èåæ¥è¯¢ï¼è¿åæ ååï¿½?WebpageResult åè¡¨
        """
        time_filter = ""
        time_params = {}
        if start_ts > 0 and end_ts > 0:
            time_filter = " AND {time_col} >= :start_ts AND {time_col} <= :end_ts"
            time_params["start_ts"] = start_ts
            time_params["end_ts"] = end_ts
        elif start_ts > 0:
            time_filter = " AND {time_col} >= :start_ts"
            time_params["start_ts"] = start_ts
            
        table_config = {
            "seed": ("daily_news", "add_ts", ["title", "description"], "source_platform = 'seed_document'"),
            "xhs": ("xhs_note", "time", ["title", "\"desc\""], None),
            "bilibili": ("bilibili_video", "create_time", ["title", "\"desc\""], None),
            "douyin": ("douyin_aweme", "create_time", ["title", "\"desc\""], None),
            "weibo": ("weibo_note", "create_time", ["content"], None),
            "zhihu": ("zhihu_content", "created_time", ["title", "content_text"], None),
            "tieba": ("tieba_note", "add_ts", ["title", "\"desc\""], None)
        }
        
        results = []
        images_results = []
        try:
            tasks = []
            platform_order = []
            for platform, (tb_name, col_time, cols, extra_cond) in table_config.items():
                order_sql, params = self._build_vector_conditions(query)
                params.update(time_params)
                params["limit"] = limit
                
                if "query_vector" in params:
                    cond_sql = f"embedding IS NOT NULL"
                    order_clause = f"{order_sql} ASC"
                else:
                    cond_sql, fallback_params = self._build_keyword_conditions(query, cols)
                    params.update(fallback_params)
                    order_clause = f"{col_time} DESC"
                
                if platform == 'seed':
                    url_col = 'url'
                elif platform in ('xhs', 'tieba', 'weibo'):
                    url_col = 'note_url'
                elif platform == 'bilibili':
                    url_col = 'video_url'
                elif platform == 'douyin':
                    url_col = 'aweme_url'
                elif platform == 'zhihu':
                    url_col = 'content_url'
                else:
                    url_col = 'url'

                if extra_cond:
                    sql = f"SELECT title, {cols[-1]} as content, {col_time} as time, {url_col} as url, extra_info FROM {tb_name} WHERE {extra_cond} AND ({cond_sql}){time_filter.format(time_col=col_time)} ORDER BY {order_clause} LIMIT :limit"
                else:
                    if platform == "weibo":
                        sql = f"SELECT '' as title, content, {col_time} as time, {url_col} as url, extra_info FROM {tb_name} WHERE ({cond_sql}){time_filter.format(time_col=col_time)} ORDER BY {order_clause} LIMIT :limit"
                    else:
                        sql = f"SELECT title, {cols[-1]} as content, {col_time} as time, {url_col} as url, extra_info FROM {tb_name} WHERE ({cond_sql}){time_filter.format(time_col=col_time)} ORDER BY {order_clause} LIMIT :limit"
                
                tasks.append(fetch_all(sql, params))
                platform_order.append(platform)
                
            all_rows = await asyncio.gather(*tasks, return_exceptions=True)
            for i, rows in enumerate(all_rows):
                if isinstance(rows, Exception):
                    logger.debug(f"æ¥è¯¢æ¬å°åºåºéæè¡¨ä¸å­å¨: {rows}")
                    continue
                platform = platform_order[i]
                for r in rows:
                    title = r.get('title', '')
                    content = r.get('content', '')
                    time_val = r.get('time')
                    url = r.get('url')
                    extra_info_str = r.get('extra_info', '')
                    
                    extra_data = {}
                    if extra_info_str:
                        try:
                            import json
                            extra_data = json.loads(extra_info_str)
                            # æåå¾çå¹¶æ·»å å° images_results ï¿½?                            if 'images' in extra_data and isinstance(extra_data['images'], list):
                                for img_url in extra_data['images']:
                                    if img_url:
                                        images_results.append(ImageResult(
                                            name=f"[{platform.upper()}] å¾ç",
                                            content_url=img_url,
                                            host_page_url=url
                                        ))
                            # ä¹å°è¯æåä¸äºå¶ä»æ ¼å¼çåªä½
                            if 'video_url' in extra_data and extra_data['video_url']:
                                content += f" [è§é¢é¾æ¥: {extra_data['video_url']}]"
                        except Exception:
                            pass
                    
                    results.append(WebpageResult(
                        name=f"[{platform.upper()}] {title}" if title else f"[{platform.upper()}] ç½åè®¨è®º",
                        url=url or f"local://{platform}/{time_val}",
                        snippet=content,
                        date_last_crawled=self._parse_timestamp(time_val)
                    ))
        finally:
            from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
            db_utils._engine = None  # Clear global engine to prevent event loop issues
        
        # æç§æ¶é´éåºæåºï¼å¹¶æªåï¿½?limit ï¿½?        results.sort(key=lambda x: x.date_last_crawled or "", reverse=True)
        return results[:limit], images_results


class BochaMultimodalSearch(LocalDatabaseSearch):
    """
    å¼å®¹ï¿½?Bocha API çæ¥å£ï¼åºå±åæ¢ä¸ºæ¬å°æ°æ®åºæ¥è¯¢ï¿½?    """
    def __init__(self, api_key: Optional[str] = None):
        pass # å¿½ç¥ API Keyï¼ä½¿ç¨æ¬å°åº

    def comprehensive_search(self, query: str, max_results: int = 10) -> BochaResponse:
        logger.info(f"--- TOOL: å¨é¢ç»¼åæç´¢ (æ¬å°DB) (query: {query}) ---")
        results, images = self._search_local_db(query, limit=max_results)
        return BochaResponse(query=query, webpages=results, images=images, answer="ï¼æ¬å°æ°æ®åºæ£ç´¢ï¼ä¸æä¾æ»ç»ï¿½?)

    def web_search_only(self, query: str, max_results: int = 15) -> BochaResponse:
        logger.info(f"--- TOOL: çº¯ç½é¡µæï¿½?(æ¬å°DB) (query: {query}) ---")
        results, _ = self._search_local_db(query, limit=max_results)
        return BochaResponse(query=query, webpages=results)

    def search_for_structured_data(self, query: str) -> BochaResponse:
        logger.info(f"--- TOOL: ç»æåæ°æ®æ¥ï¿½?(æ¬å°DB) (query: {query}) ---")
        results, _ = self._search_local_db(query, limit=5)
        return BochaResponse(query=query, webpages=results)

    def search_last_24_hours(self, query: str) -> BochaResponse:
        logger.info(f"--- TOOL: æç´¢24å°æ¶åä¿¡ï¿½?(æ¬å°DB) (query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        results, images = self._search_local_db(query, limit=15, start_ts=start_ts)
        return BochaResponse(query=query, webpages=results, images=images)

    def search_last_week(self, query: str) -> BochaResponse:
        logger.info(f"--- TOOL: æç´¢æ¬å¨ä¿¡æ¯ (æ¬å°DB) (query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(weeks=1)).timestamp() * 1000)
        results, images = self._search_local_db(query, limit=15, start_ts=start_ts)
        return BochaResponse(query=query, webpages=results, images=images)


class AnspireAISearch(LocalDatabaseSearch):
    """
    å¼å®¹ï¿½?Anspire API çæ¥å£ï¼åºå±åæ¢ä¸ºæ¬å°æ°æ®åºæ¥è¯¢ï¿½?    """
    def __init__(self, api_key: Optional[str] = None):
        pass

    def comprehensive_search(self, query: str, max_results: int = 10) -> AnspireResponse:
        logger.info(f"--- TOOL: ç»¼åæç´¢ (æ¬å°DB) (query: {query}) ---")
        results, _ = self._search_local_db(query, limit=max_results)
        return AnspireResponse(query=query, webpages=results)

    def search_last_24_hours(self, query: str, max_results: int = 10) -> AnspireResponse:
        logger.info(f"--- TOOL: æç´¢24å°æ¶åä¿¡ï¿½?(æ¬å°DB) (query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        results, _ = self._search_local_db(query, limit=max_results, start_ts=start_ts)
        return AnspireResponse(query=query, webpages=results)

    def search_last_week(self, query: str, max_results: int = 10) -> AnspireResponse:
        logger.info(f"--- TOOL: æç´¢æ¬å¨ä¿¡æ¯ (æ¬å°DB) (query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(weeks=1)).timestamp() * 1000)
        results, _ = self._search_local_db(query, limit=max_results, start_ts=start_ts)
        return AnspireResponse(query=query, webpages=results)

# --- 3. æµè¯ä¸ä½¿ç¨ç¤ºï¿½?---
def print_response_summary(response):
    if not response or not response.query:
        logger.error("æªè½è·åææååºï¿½?)
        return

    logger.info(f"\næ¥è¯¢: '{response.query}'")
    logger.info(f"æ¾å° {len(response.webpages)} ä¸ªç»ï¿½?)

    if response.webpages:
        for idx, result in enumerate(response.webpages[:5], 1):
            logger.info(f" {idx}. {result.name}")
            logger.info(f"    {result.snippet[:50]}...")
            logger.info(f"    [{result.date_last_crawled}] {result.url}")

    logger.info("-" * 60)

if __name__ == "__main__":
    search_client = BochaMultimodalSearch()
    response1 = search_client.comprehensive_search(query="äººå·¥æºè½å¯¹æªæ¥æè²çå½±å")
    print_response_summary(response1)
