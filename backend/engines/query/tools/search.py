ï»¿"""
ä¸ä¸º AI Agent è®¾è®¡çèææç´¢å·¥å·é (æ¬å°æ°æ®ï¿½?

çæ¬: 2.0
æåæ´ï¿½? 2025-08-22

æ­¤èæ¬å°æç´¢åè½éæä¸ºä»æ¬å° SQLite æ°æ®åºä¸­æ£ç´¢æ°æ®ï¼
ä¿æäºä¸åæ Tavily æ¥å£ç¸åçç­¾ååè¿åç»æï¼ä»¥ï¿½?Agent æ ç¼åæ¢ï¿½?

æ°ç¹ï¿½?
- å½»åºç§»é¤ Tavily ä¾èµï¼æ¹ä¸ºæ£ç´¢æ¬å°æ¯æ¥æ°é»åç¤¾åªè¡¨ï¿½?
- æå extra_info ä¸­çå¤æ¨¡ææ°æ®ï¿½?
"""

import os
import sys
import datetime
import asyncio
from typing import List, Dict, Any, Optional, Tuple

# æ·»å utilsç®å½å°Pythonè·¯å¾
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG
from dataclasses import dataclass, field

# å¼å¥æ¬å°æ°æ®åºæ¥è¯¢å·¥ï¿½?
sys.path.insert(0, root_dir)
from backend.db.connection import fetch_all, _run_async
import logging

logger = logging.getLogger(__name__)

# --- 1. æ°æ®ç»æå®ä¹ ---

@dataclass
class SearchResult:
    """
    ç½é¡µæç´¢ç»ææ°æ®ï¿½?
    åå« published_date å±æ§æ¥å­å¨æ°é»åå¸æ¥æ
    """
    title: str
    url: str
    content: str
    score: Optional[float] = None
    raw_content: Optional[str] = None
    published_date: Optional[str] = None

@dataclass
class ImageResult:
    """å¾çæç´¢ç»ææ°æ®ï¿½?""
    url: str
    description: Optional[str] = None

@dataclass
class TavilyResponse:
    """å°è£æç´¢ API çå®æ´è¿åç»æï¼ä¿æåæå½åä»¥ä¾¿å¼å®¹"""
    query: str
    answer: Optional[str] = None
    results: List[SearchResult] = field(default_factory=list)
    images: List[ImageResult] = field(default_factory=list)
    response_time: Optional[float] = None


# --- 2. æ ¸å¿å®¢æ·ç«¯ä¸ä¸ç¨å·¥å·ï¿½?---

class TavilyNewsAgency:
    """
    ä¸ä¸ªåå«å¤ç§ä¸ç¨æ°é»èææç´¢å·¥å·çå®¢æ·ç«¯ï¿½?
    åºå±å·²éæä¸ºæ¬å°æ°æ®åºæ¥è¯¢ï¿½?
    """

    def __init__(self, api_key: Optional[str] = None):
        """åå§åå®¢æ·ç«¯ï¼API Keyåæ°ä¿çä»¥å¼å®¹æ§ä»£ç ï¼ä½ä¸åä½¿ç¨ï¿½?""
        pass

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
        ä½¿ç¨æ¬å° Embedding è¿è¡åéç¸ä¼¼åº¦å¹éï¿½?
        è¿å: SQL æåº/è®¡ç®çæ®µ ï¿½?params (åå« query_vector å­ç¬¦ï¿½?
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

    def _parse_timestamp(self, ts) -> str:
        """å°æ¯«ç§æ¶é´æ³è½¬æ¢ï¿½?YYYY-MM-DD HH:MM:SS æ ¼å¼"""
        if not ts:
            return ""
        try:
            return datetime.datetime.fromtimestamp(int(ts) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(ts)

    async def _search_local_db_async(self, query: str, limit: int = 10, start_ts: int = 0, end_ts: int = 0):
        """å¼æ­¥æ¥è¯¢æ¬å°æ°æ®åºçåä¸ªï¿½?""
        time_filter = ""
        time_params = {}
        if start_ts > 0:
            time_params["start_ts"] = start_ts
            time_filter += " AND {time_col} >= :start_ts"
        if end_ts > 0:
            time_params["end_ts"] = end_ts
            time_filter += " AND {time_col} <= :end_ts"
            
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
                    # Weibo has no title column
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
                    
                    raw_content = content
                    if extra_info_str:
                        try:
                            import json
                            extra_data = json.loads(extra_info_str)
                            if 'images' in extra_data and isinstance(extra_data['images'], list):
                                for img_url in extra_data['images']:
                                    if img_url:
                                        images_results.append(ImageResult(
                                            description=f"[{platform.upper()}] å¾ç",
                                            url=img_url
                                        ))
                            if 'video_url' in extra_data and extra_data['video_url']:
                                raw_content += f"\n[è§é¢é¾æ¥: {extra_data['video_url']}]"
                            
                            # å°å®ï¿½?JSON å­å¥ raw_content ä»¥ä¾æ·±åº¦åæ
                            raw_content += f"\n[éå æ°æ®: {json.dumps(extra_data, ensure_ascii=False)}]"
                        except Exception:
                            pass
                    
                    results.append(SearchResult(
                        title=f"[{platform.upper()}] {title}" if title else f"[{platform.upper()}] ç½åè®¨è®º",
                        url=url or f"local://{platform}/{time_val}",
                        content=content[:300] + "..." if len(content) > 300 else content,
                        raw_content=raw_content,
                        published_date=self._parse_timestamp(time_val)
                    ))
        finally:
            from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
            db_utils._engine = None  # Clear global engine to prevent event loop issues
        
        # æç§æ¶é´éåºæåºï¼å¹¶æªåï¿½?limit ï¿½?
        results.sort(key=lambda x: x.published_date or "", reverse=True)
        return results[:limit], images_results

    def _search_local_db(self, query: str, limit: int = 10, start_ts: int = 0, end_ts: int = 0):
        return _run_async(self._search_local_db_async(query, limit, start_ts, end_ts))

    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return=TavilyResponse(query="æç´¢å¤±è´¥"))
    def _search_internal(self, query: str, max_results: int = 10, start_ts: int = 0, end_ts: int = 0) -> TavilyResponse:
        """åé¨éç¨çæç´¢æ§è¡å¨ï¼ææå·¥å·æç»é½è°ç¨æ­¤æ¹ï¿½?""
        try:
            results, images = self._search_local_db(query, limit=max_results, start_ts=start_ts, end_ts=end_ts)
            return TavilyResponse(
                query=query, 
                answer=None,
                results=results, 
                images=images,
                response_time=0.1
            )
        except Exception as e:
            print(f"æç´¢æ¶åçéï¿½? {str(e)}")
            raise e

    # --- Agent å¯ç¨çå·¥å·æ¹ï¿½?---

    def basic_search_news(self, query: str, max_results: int = 7) -> TavilyResponse:
        """
        ãå·¥å·ãåºç¡æ°é»æç´¢: æ§è¡ä¸æ¬¡æ åãå¿«éçæ°é»æç´¢ï¿½?
        """
        print(f"--- TOOL: åºç¡æ°é»æç´¢ (query: {query}) ---")
        return self._search_internal(query=query, max_results=max_results)

    def deep_search_news(self, query: str) -> TavilyResponse:
        """
        ãå·¥å·ãæ·±åº¦æ°é»åï¿½? å¯¹ä¸ä¸ªä¸»é¢è¿è¡æå¨é¢ãææ·±å¥çæç´¢ï¿½?
        """
        print(f"--- TOOL: æ·±åº¦æ°é»åæ (query: {query}) ---")
        return self._search_internal(query=query, max_results=20)

    def search_news_last_24_hours(self, query: str) -> TavilyResponse:
        """
        ãå·¥å·ãæï¿½?4å°æ¶åæ°ï¿½? è·åå³äºæä¸ªä¸»é¢çææ°å¨æï¿½?
        """
        print(f"--- TOOL: æç´¢24å°æ¶åæ°ï¿½?(query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(days=1)).timestamp() * 1000)
        return self._search_internal(query=query, max_results=10, start_ts=start_ts)

    def search_news_last_week(self, query: str) -> TavilyResponse:
        """
        ãå·¥å·ãæç´¢æ¬å¨æ°ï¿½? è·åå³äºæä¸ªä¸»é¢è¿å»ä¸å¨åçä¸»è¦æ°é»æ¥éï¿½?
        """
        print(f"--- TOOL: æç´¢æ¬å¨æ°é» (query: {query}) ---")
        start_ts = int((datetime.datetime.now() - datetime.timedelta(weeks=1)).timestamp() * 1000)
        return self._search_internal(query=query, max_results=10, start_ts=start_ts)

    def search_images_for_news(self, query: str) -> TavilyResponse:
        """
        ãå·¥å·ãæ¥æ¾æ°é»å¾ï¿½? æç´¢ä¸æä¸ªæ°é»ä¸»é¢ç¸å³çå¾çï¿½?
        """
        print(f"--- TOOL: æ¥æ¾æ°é»å¾ç (query: {query}) ---")
        return self._search_internal(query=query, max_results=5)

    def search_news_by_date(self, query: str, start_date: str, end_date: str) -> TavilyResponse:
        """
        ãå·¥å·ãææå®æ¥æèå´æç´¢æ°é»ï¿½?
        """
        print(f"--- TOOL: ææå®æ¥æèå´æç´¢æ°ï¿½?(query: {query}, from: {start_date}, to: {end_date}) ---")
        try:
            start_ts = int(datetime.datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
            end_ts = int(datetime.datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
        except Exception:
            start_ts = 0
            end_ts = 0
        return self._search_internal(query=query, max_results=15, start_ts=start_ts, end_ts=end_ts)


# --- 3. æµè¯ä¸ä½¿ç¨ç¤ºï¿½?---

def print_response_summary(response: TavilyResponse):
    """ç®åçæå°å½æ°ï¼ç¨äºå±ç¤ºæµè¯ç»æï¼ç°å¨ä¼æ¾ç¤ºåå¸æ¥ï¿½?""
    if not response or not response.query:
        print("æªè½è·åææååºï¿½?)
        return
        
    print(f"\næ¥è¯¢: '{response.query}' | èæ¶: {response.response_time}s")
    if response.answer:
        print(f"AIæè¦: {response.answer[:120]}...")
    print(f"æ¾å° {len(response.results)} æ¡ç½ï¿½? {len(response.images)} å¼ å¾çï¿½?)
    if response.results:
        first_result = response.results[0]
        date_info = f"(åå¸ï¿½? {first_result.published_date})" if first_result.published_date else ""
        print(f"ç¬¬ä¸æ¡ç»ï¿½? {first_result.title} {date_info}")
    print("-" * 60)


if __name__ == "__main__":
    # å¨è¿è¡åï¼è¯·ç¡®ä¿æ¨å·²è®¾ç½® TAVILY_API_KEY ç¯å¢åé
    
    try:
        # åå§å"æ°é»ç¤¾"å®¢æ·ç«¯ï¼å®åé¨åå«äºææå·¥ï¿½?
        agency = TavilyNewsAgency()

        # åºæ¯1: Agent è¿è¡ä¸æ¬¡å¸¸è§ãå¿«éçæç´¢
        response1 = agency.basic_search_news(query="å¥¥è¿ä¼ææ°èµï¿½?, max_results=5)
        print_response_summary(response1)

        # åºæ¯2: Agent éè¦å¨é¢äºè§£"å¨çè¯çææ¯ç«äº"çèæ¯
        response2 = agency.deep_search_news(query="å¨çè¯çææ¯ç«ï¿½?)
        print_response_summary(response2)

        # åºæ¯3: Agent éè¦è¿½è¸ª"GTCå¤§ä¼"çææ°æ¶ï¿½?
        response3 = agency.search_news_last_24_hours(query="Nvidia GTCå¤§ä¼ ææ°åï¿½?)
        print_response_summary(response3)
        
        # åºæ¯4: Agent éè¦ä¸ºä¸ç¯å³äº"èªå¨é©¾é©¶"çå¨æ¥æ¥æ¾ç´ æ
        response4 = agency.search_news_last_week(query="èªå¨é©¾é©¶åä¸åè½ï¿½?)
        print_response_summary(response4)
        
        # åºæ¯5: Agent éè¦æ¥æ¾"é¦ä¼¯å¤ªç©ºæè¿é"çæ°é»å¾ç
        response5 = agency.search_images_for_news(query="é¦ä¼¯å¤ªç©ºæè¿éææ°åï¿½?)
        print_response_summary(response5)

        # åºæ¯6: Agent éè¦ç ï¿½?025å¹´ç¬¬ä¸å­£åº¦å³äº"äººå·¥æºè½æ³è§"çæ°é»
        response6 = agency.search_news_by_date(
            query="äººå·¥æºè½æ³è§",
            start_date="2025-01-01",
            end_date="2025-03-31"
        )
        print_response_summary(response6)

    except ValueError as e:
        print(f"åå§åå¤±ï¿½? {e}")
        print("è¯·ç¡®ï¿½?TAVILY_API_KEY ç¯å¢åéå·²æ­£ç¡®è®¾ç½®ï¿½?)
    except Exception as e:
        print(f"æµè¯è¿ç¨ä¸­åçæªç¥éï¿½? {e}")
