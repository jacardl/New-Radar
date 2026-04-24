ï»¿"""
ä¸ä¸º AI Agent è®¾è®¡çæ¬å°èææ°æ®åºæ¥è¯¢å·¥å·ï¿½?(MediaCrawlerDB)

çæ¬: 3.0
æåæ´ï¿½? 2025-08-23

æ­¤èæ¬å°å¤æçæ¬å°MySQLæ°æ®åºæ¥è¯¢åè½å°è£æä¸ç³»åç®æ æç¡®ãåæ°æ¸æ°çç¬ç«å·¥å·ï¿½?
ä¸ä¸ºAI Agentè°ç¨èè®¾è®¡gentåªéæ ¹æ®ä»»å¡æå¾ï¼å¦æç´¢ç­ç¹ãå¨å±æç´¢è¯é¢ï¿½?
ææ¶é´èå´åæãè·åè¯è®ºï¼éæ©åéçå·¥å·ï¼æ éç¼åå¤æçSQLè¯­å¥ï¿½?

V3.0 æ ¸å¿æ´æ°:
- æºè½ç­åº¦è®¡ç®: `search_hot_content`ä¸åéè¦`sort_by`åæ°ï¼æ¹ä¸ºåé¨ä½¿ç¨ç»ä¸çå æç­åº¦ç®æ³ï¼
  ç»¼åç¹èµãè¯è®ºãåäº«ãè§çç­æ°æ®è®¡ç®ç­åº¦åå¼ï¼ä½¿ç»ææ´æºè½ãæ´ç¬¦åç»¼åç­åº¦ï¿½?
- æ°å¢å¹³å°ç²¾æå·¥å·: æ°å¢ `search_topic_on_platform` å·¥å·ï¼ä½ä¸ºç¹ä¾ï¼
  åè®¸Agentå¨ç¹å®å¹³å°ï¼Bç«ãå¾®åç­ä¸å¤§å¹³å°ï¼ä¸å¯¹æä¸è¯é¢è¿è¡ç²¾ç¡®æç´¢ï¼å¹¶æ¯ææ¶é´ç­éï¿½?
- ç»æä¼å: è°æ´äºæ°æ®ç»æä¸å½æ°ææ¡£ï¼ä»¥éåºæ°åè½ï¿½?

ä¸»è¦å·¥å·:
- search_hot_content: æ¥æ¾æå®æ¶é´èå´åçç»¼åç­åº¦æé«çåå®¹ï¿½?
- search_topic_globally: å¨æ´ä¸ªæ°æ®åºä¸­å¨å±æç´¢ä¸ç¹å®è¯é¢ç¸å³çææåå®¹åè¯è®ºï¿½?
- search_topic_by_date: å¨æå®çåå²æ¥æèå´åæç´¢ä¸ç¹å®è¯é¢ç¸å³çåå®¹ï¿½?
- get_comments_for_topic: ä¸é¨æåå¬ä¼å¯¹äºæä¸ç¹å®è¯é¢çè¯è®ºæ°æ®ï¿½?
- search_topic_on_platform: å¨æå®çåä¸ªç¤¾äº¤åªä½å¹³å°ä¸æç´¢ç¹å®è¯é¢ï¿½?
"""

import os
import json
import requests
from loguru import logger
import asyncio
from typing import List, Dict, Any, Optional, Literal, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from backend.config import settings
from dotenv import load_dotenv

load_dotenv()

# --- 1. æ°æ®ç»æå®ä¹ ---

@dataclass
class QueryResult:
    """ç»ä¸çæ°æ®åºæ¥è¯¢ç»ææ°æ®ï¿½?""
    platform: str
    content_type: str
    title_or_content: str
    author_nickname: Optional[str] = None
    url: Optional[str] = None
    publish_time: Optional[datetime] = None
    engagement: Dict[str, int] = field(default_factory=dict)
    source_keyword: Optional[str] = None
    hotness_score: float = 0.0
    source_table: str = ""

@dataclass
class DBResponse:
    """å°è£å·¥å·çå®æ´è¿åç»ï¿½?""
    tool_name: str
    parameters: Dict[str, Any]
    results: List[QueryResult] = field(default_factory=list)
    results_count: int = 0
    error_message: Optional[str] = None

# --- 2. æ ¸å¿å®¢æ·ç«¯ä¸ä¸ç¨å·¥å·ï¿½?---
import concurrent.futures
from backend.db.connection import fetch_all

def _run_async(coro):
    """å®å¨çå¼æ­¥æ§è¡åè£å¨ï¼å¼å®¹å¤çº¿ç¨ä¸äºä»¶å¾ªç¯ç¯ï¿½?""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)

class MediaCrawlerDB:
    """æ¬å°æ°æ®åºèææ£ç´¢å·¥ï¿½?""
    
    def __init__(self):
        """åå§åï¼æ éå¤é¨API"""
        pass

    @staticmethod
    def _parse_timestamp(ts: Any) -> Optional[datetime]:
        if not ts: return None
        try:
            if isinstance(ts, datetime):
                return ts
            if isinstance(ts, str) and ts.isdigit():
                ts = int(ts)
            if isinstance(ts, int):
                if ts > 1e11:  # 13ä½æ¯«ç§æ¶é´æ³
                    return datetime.fromtimestamp(ts / 1000)
                return datetime.fromtimestamp(ts)
            if isinstance(ts, str):
                return datetime.fromisoformat(ts.split('+')[0].strip().replace(' ', 'T'))
        except Exception:
            return None
        return None
        
    def _safe_query(self, sql: str, params: dict) -> List[dict]:
        """å®å¨æ¥è¯¢åè¡¨ï¼å¦æè¡¨ä¸å­å¨åéé»å¿½ç¥"""
        try:
            res = _run_async(fetch_all(sql, params))
            from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
            db_utils._engine = None  # Prevent event loop reuse issues
            return res
        except Exception as e:
            # æè·è¡¨ä¸å­å¨ç­å¼å¸¸ï¼ä¸å½±åå¶ä»è¡¨æ¥è¯¢
            logger.debug(f"æ¥è¯¢è·³è¿ (å¯è½è¡¨ä¸å­å¨): {e}")
            from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
            db_utils._engine = None
            return []

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
            # Postgres pgvector: `<=>` represents cosine distance. We want cosine similarity, which is 1 - distance.
            # But for ORDER BY, distance ASC is exactly what we want (smaller distance = more similar).
            # If embedding is null, distance will be null.
            order_sql = "embedding <=> :query_vector"
            return order_sql, {"query_vector": emb_str}
        except Exception as e:
            logger.error(f"Generate embedding for query failed: {e}")
            return "1", {} # fallback

    def search_hot_content(
        self,
        time_period: Literal['24h', 'week', 'year'] = 'week',
        limit: int = 50
    ) -> DBResponse:
        """
        ãå·¥å·ãæ¥æ¾ç­ç¹åï¿½? æåæ°æ®åºä¸­ MindSpider æåçæ¯æ¥ç­ç¹ï¿½?
        """
        params_for_log = {'time_period': time_period, 'limit': limit}
        logger.info(f"--- TOOL: æ¥æ¾æ¬å°ç­ç¹åå®¹ (params: {params_for_log}) ---")
        
        now = datetime.now()
        days = {'24h': 1, 'week': 7, 'year': 365}.get(time_period, 7)
        start_ts = int((now - timedelta(days=days)).timestamp() * 1000)
        
        sql = """
            SELECT source_platform as platform, title, description as content, url, add_ts as publish_time
            FROM daily_news
            WHERE add_ts >= :start_ts
            ORDER BY rank_position ASC, add_ts DESC
            LIMIT :limit
        """
        raw_results = self._safe_query(sql, {"start_ts": start_ts, "limit": limit})
        
        formatted = []
        for r in raw_results:
            formatted.append(QueryResult(
                platform=r.get('platform', 'web'),
                content_type="hot_news",
                title_or_content=f"{r.get('title', '')} - {r.get('content', '')}",
                url=r.get('url'),
                publish_time=self._parse_timestamp(r.get('publish_time')),
                source_table="daily_news"
            ))
            
        return DBResponse("search_hot_content", params_for_log, results=formatted, results_count=len(formatted))

    def search_topic_globally(self, topic: str, limit_per_table: int = 10) -> DBResponse:
        """
        ãå·¥å·ãå¨å±è¯é¢æç´¢: å¨æ¬å°å¤å¹³å°æ°æ®è¡¨ä¸­æ¨¡ç³æ£ç´¢è¯é¢ï¿½?
        """
        params_for_log = {'topic': topic, 'limit_per_table': limit_per_table}
        logger.info(f"--- TOOL: æ¬å°å¨åºè¯é¢æç´¢ (params: {params_for_log}) ---")
        
        table_config = {
            "seed": ("daily_news", "add_ts", ["title", "description"], "source_platform = 'seed_document'"),
            "xhs": ("xhs_note", "time", ["title", "\"desc\""], None),
            "bilibili": ("bilibili_video", "create_time", ["title", "\"desc\""], None),
            "douyin": ("douyin_aweme", "create_time", ["title", "\"desc\""], None),
            "weibo": ("weibo_note", "create_time", ["content"], None),
            "zhihu": ("zhihu_content", "created_time", ["title", "content_text"], None),
            "kuaishou": ("kuaishou_video", "create_time", ["title", "\"desc\""], None),
            "tieba": ("tieba_note", "add_ts", ["title", "\"desc\""], None)
        }
        
        all_results = []
        for platform, (tb_name, col_time, cols, extra_cond) in table_config.items():
            order_sql, params = self._build_vector_conditions(topic)
            params["limit"] = limit_per_table
            
            # ä½¿ç¨ embedding IS NOT NULL æ¥ç¡®ä¿æä»¬åªæç´¢å·²åéåçæ°æ®ï¼æèä½ å¯ä»¥éåå° LIKE
            if "query_vector" in params:
                cond_sql = f"embedding IS NOT NULL"
                order_clause = f"{order_sql} ASC"
            else:
                # éçº§å¤ç
                cond_sql, fallback_params = self._build_keyword_conditions(topic, cols)
                params.update(fallback_params)
                order_clause = f"{col_time} DESC"
            
            if extra_cond:
                sql = f"SELECT * FROM {tb_name} WHERE {extra_cond} AND ({cond_sql}) ORDER BY {order_clause} LIMIT :limit"
            else:
                sql = f"SELECT * FROM {tb_name} WHERE {cond_sql} ORDER BY {order_clause} LIMIT :limit"
                
            rows = self._safe_query(sql, params)
            for r in rows:
                title = r.get('title', '')
                content = r.get('desc', '') or r.get('content_text', '') or r.get('description', '') or r.get('content', '')
                time_val = r.get('time') or r.get('created_time') or r.get('add_ts') or r.get('create_time')
                url = r.get('note_url') or r.get('video_url') or r.get('content_url') or r.get('aweme_url') or r.get('url')
                
                # æåé¢å¤æ ¼å¼æ°æ®
                extra_info_str = r.get('extra_info', '')
                if extra_info_str:
                    try:
                        import json
                        extra_data = json.loads(extra_info_str)
                        if 'images' in extra_data and extra_data['images']:
                            content += f" [åå« {len(extra_data['images'])} å¼ å¾ç]"
                        if 'video_url' in extra_data and extra_data['video_url']:
                            content += f" [åå«è§é¢]"
                        # å¯ä»¥æåæ´å¤çç¹èµç­äºå¨æ°æ®
                    except Exception:
                        pass
                
                all_results.append(QueryResult(
                    platform=platform,
                    content_type="news",
                    title_or_content=f"{title} - {content}",
                    url=url,
                    publish_time=self._parse_timestamp(time_val),
                    source_keyword=topic,
                    source_table=f"{platform}_table"
                ))
                
        return DBResponse("search_topic_globally", params_for_log, results=all_results, results_count=len(all_results))

    def search_topic_by_date(self, topic: str, start_date: str, end_date: str, limit_per_table: int = 10) -> DBResponse:
        """
        ãå·¥å·ãææ¥ææç´¢è¯é¢: å¨éå®çæ¶é´æ®µåæ¥è¯¢æ¬å°åºï¿½?
        """
        params_for_log = {'topic': topic, 'start_date': start_date, 'end_date': end_date, 'limit_per_table': limit_per_table}
        logger.info(f"--- TOOL: æ¬å°ææ¥ææç´¢è¯ï¿½?(params: {params_for_log}) ---")
        
        try:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
            end_ts = int((datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).timestamp() * 1000)
        except Exception:
            return DBResponse("search_topic_by_date", params_for_log, error_message="æ¥ææ ¼å¼éè¯¯ï¼éï¿½?YYYY-MM-DD")
            
        table_config = {
            "xhs": ("xhs_note", "time", ["title", "\"desc\""]),
            "bilibili": ("bilibili_video", "create_time", ["title", "\"desc\""]),
            "douyin": ("douyin_aweme", "create_time", ["title", "\"desc\""]),
            "weibo": ("weibo_note", "create_time", ["content"]),
            "tieba": ("tieba_note", "add_ts", ["title", "\"desc\""])
        }
        
        all_results = []
        for platform, (tb_name, col_time, cols) in table_config.items():
            order_sql, params = self._build_vector_conditions(topic)
            params["start_ts"] = start_ts
            params["end_ts"] = end_ts
            params["limit"] = limit_per_table
            
            if "query_vector" in params:
                cond_sql = f"embedding IS NOT NULL"
                order_clause = f"{order_sql} ASC"
            else:
                cond_sql, fallback_params = self._build_keyword_conditions(topic, cols)
                params.update(fallback_params)
                order_clause = f"{col_time} DESC"
            
            sql = f"SELECT *, extra_info FROM {tb_name} WHERE ({cond_sql}) AND {col_time} >= :start_ts AND {col_time} <= :end_ts ORDER BY {order_clause} LIMIT :limit"
            
            rows = self._safe_query(sql, params)
            for r in rows:
                title = r.get('title', '')
                content = r.get('desc', '') or r.get('content_text', '')
                time_val = r.get('time') or r.get('created_time') or r.get('add_ts')
                
                # æåé¢å¤æ ¼å¼æ°æ®
                extra_info_str = r.get('extra_info', '')
                if extra_info_str:
                    try:
                        import json
                        extra_data = json.loads(extra_info_str)
                        if 'images' in extra_data and extra_data['images']:
                            content += f" [åå« {len(extra_data['images'])} å¼ å¾ç]"
                        if 'video_url' in extra_data and extra_data['video_url']:
                            content += f" [åå«è§é¢]"
                    except Exception:
                        pass

                all_results.append(QueryResult(
                    platform=platform,
                    content_type="news",
                    title_or_content=f"{title} - {content}",
                    url=r.get('note_url') or r.get('video_url') or r.get('content_url') or r.get('aweme_url') or r.get('url'),
                    publish_time=self._parse_timestamp(time_val),
                    source_keyword=topic,
                    source_table=f"{platform}_table"
                ))
                
        return DBResponse("search_topic_by_date", params_for_log, results=all_results, results_count=len(all_results))
        
    def get_comments_for_topic(self, topic: str, limit: int = 50) -> DBResponse:
        """
        ãå·¥å·ãè·åè¯é¢è®¨ï¿½? ç´æ¥ä»æ¬å°åå¹³å°çè¯è®ºè¡¨ä¸­ææç½æ°åè¯ï¿½?
        """
        params_for_log = {'topic': topic, 'limit': limit}
        logger.info(f"--- TOOL: æ¬å°ææè¯é¢è®¨è®º (params: {params_for_log}) ---")
        
        table_config = {
            "xhs": ("xhs_note_comment", "create_time"),
            "douyin": ("douyin_aweme_comment", "create_time"),
            "bilibili": ("bilibili_video_comment", "create_time"),
            "weibo": ("weibo_note_comment", "create_time"),
            "zhihu": ("zhihu_comment", "publish_time"),
            "tieba": ("tieba_comment", "publish_time"),
        }
        
        formatted = []
        for platform, (tb_name, col_time) in table_config.items():
            order_sql, params = self._build_vector_conditions(topic)
            params["limit"] = limit
            
            if "query_vector" in params:
                cond_sql = f"embedding IS NOT NULL"
                order_clause = f"{order_sql} ASC"
            else:
                cond_sql, fallback_params = self._build_keyword_conditions(topic, ["content"])
                params.update(fallback_params)
                order_clause = f"{col_time} DESC"
                
            sql = f"SELECT content, {col_time} as time, nickname FROM {tb_name} WHERE {cond_sql} ORDER BY {order_clause} LIMIT :limit"
            # å¼å®¹ç¥ä¹è´´å§å­æ®µï¿½?
            if platform in ["zhihu", "tieba"]:
                sql = sql.replace("nickname", "user_nickname as nickname")
                
            rows = self._safe_query(sql, params)
            for r in rows:
                formatted.append(QueryResult(
                    platform=platform,
                    content_type="comment",
                    title_or_content=r.get('content', ''),
                    author_nickname=r.get('nickname', 'ç½å'),
                    publish_time=self._parse_timestamp(r.get('time')),
                    source_table=f"{platform}_comment"
                ))
                
        return DBResponse("get_comments_for_topic", params_for_log, results=formatted, results_count=len(formatted))

    def search_topic_on_platform(
        self,
        platform: Literal['bilibili', 'weibo', 'douyin', 'kuaishou', 'xhs', 'zhihu', 'tieba'],
        topic: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20
    ) -> DBResponse:
        """
        ãå·¥å·ãå¹³å°å®åæï¿½? ç²¾ç¡®æ¥è¯¢æ¬å°æåä¸å¹³å°çæ°æ®è¡¨ï¿½?
        """
        params_for_log = {'platform': platform, 'topic': topic, 'start_date': start_date, 'end_date': end_date, 'limit': limit}
        logger.info(f"--- TOOL: æ¬å°å®åå¹³å°æç´¢ (params: {params_for_log}) ---")

        table_map = {
            'xhs': ('xhs_note', 'title', 'desc', 'time'),
            'bilibili': ('bilibili_video', 'title', 'desc', 'create_time'),
            'douyin': ('douyin_aweme', 'title', 'desc', 'create_time'),
            'weibo': ('weibo_note', 'content', 'content', 'create_time'), # å¾®åéå¸¸ç¨contentä»£æ¿titleådesc
            'kuaishou': ('kuaishou_video', 'title', 'desc', 'create_time'),
            'zhihu': ('zhihu_content', 'title', 'content_text', 'created_time'),
            'tieba': ('tieba_note', 'title', 'desc', 'add_ts')
        }
        
        if platform not in table_map:
            return DBResponse("search_topic_on_platform", params_for_log, error_message=f"ä¸æ¯æçå¹³å°: {platform}")

        tb_name, col_title, col_desc, col_time = table_map[platform]
        
        order_sql, params = self._build_vector_conditions(topic)
        params["limit"] = limit
        
        if "query_vector" in params:
            cond_sql = f"embedding IS NOT NULL"
            order_clause = f"{order_sql} ASC"
        else:
            cond_sql, fallback_params = self._build_keyword_conditions(topic, [col_title, f'"{col_desc}"'])
            params.update(fallback_params)
            order_clause = f"{col_time} DESC"
            
        # æå»ºæ¶é´è¿æ»¤
        time_filter = ""
        if start_date and end_date:
            try:
                start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
                end_ts = int((datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).timestamp() * 1000)
                time_filter = f" AND {col_time} >= :start_ts AND {col_time} <= :end_ts"
                params["start_ts"] = start_ts
                params["end_ts"] = end_ts
            except Exception:
                pass
                
        sql = f"SELECT * FROM {tb_name} WHERE ({cond_sql}) {time_filter} ORDER BY {order_clause} LIMIT :limit"
        
        rows = self._safe_query(sql, params)
        
        all_results = []
        for r in rows:
            title = r.get(col_title, '') if col_title != 'desc' else ''
            content = r.get(col_desc, '')
            
            all_results.append(QueryResult(
                platform=platform,
                content_type="news",
                title_or_content=f"{title} - {content}",
                url=r.get('note_url') or r.get('video_url') or r.get('content_url') or r.get('aweme_url') or r.get('url'),
                publish_time=self._parse_timestamp(r.get(col_time)),
                source_keyword=topic,
                source_table=tb_name
            ))
            
        return DBResponse("search_topic_on_platform", params_for_log, results=all_results, results_count=len(all_results))

def get_search_tools():
    """è¿åä¾LLMè°ç¨çå·¥å·åï¿½?""
    search_db = MediaCrawlerDB()
    return [
        search_db.search_hot_content,
        search_db.search_topic_globally,
        search_db.search_topic_by_date,
        search_db.get_comments_for_topic,
        search_db.search_topic_on_platform
    ]

# --- 3. æµè¯ä¸ä½¿ç¨ç¤ºï¿½?---
def print_response_summary(response: DBResponse):
    """ç®åçæå°å½æ°ï¼ç¨äºå±ç¤ºæµè¯ç»ï¿½?""
    if response.error_message:
        logger.info(f"å·¥å· '{response.tool_name}' æ§è¡åºé: {response.error_message}")
        return

    params_str = ", ".join(f"{k}='{v}'" for k, v in response.parameters.items())
    logger.info(f"æ¥è¯¢: å·¥å·='{response.tool_name}', åæ°=[{params_str}]")
    logger.info(f"æ¾å° {response.results_count} æ¡ç¸å³è®°å½ï¿½?)
    
    # ç»ä¸ä¸ºä¸ä¸ªæ¶æ¯è¾ï¿½?
    output_lines = []
    output_lines.append("==== æ¥è¯¢ç»æé¢è§ï¼æå¤å5æ¡ï¼ ====")
    if response.results and len(response.results) > 0:
        for idx, res in enumerate(response.results[:5], 1):
            content_preview = (res.title_or_content.replace('\n', ' ')[:70] + '...') if res.title_or_content and len(res.title_or_content) > 70 else (res.title_or_content or '')
            author_str = res.author_nickname or "N/A"
            publish_time_str = res.publish_time.strftime('%Y-%m-%d %H:%M') if res.publish_time else "N/A"
            hotness_str = f", hotness: {res.hotness_score:.2f}" if getattr(res, "hotness_score", 0) > 0 else ""
            engagement_dict = getattr(res, "engagement", {}) or {}
            engagement_str = ", ".join(f"{k}: {v}" for k, v in engagement_dict.items() if v)
            output_lines.append(
                f"{idx}. [{res.platform.upper()}/{res.content_type}] {content_preview}\n"
                f"   ä½ï¿½? {author_str} | æ¶é´: {publish_time_str}"
                f"{hotness_str} | æºå³é®è¯: '{res.source_keyword or 'N/A'}'\n"
                f"   é¾æ¥: {res.url or 'N/A'}\n"
                f"   äºå¨æ°æ®: {{{engagement_str}}}"
            )
    else:
        output_lines.append("ææ ç¸å³åå®¹ï¿½?)
    output_lines.append("=" * 60)
    logger.info('\n'.join(output_lines))

if __name__ == "__main__":
    
    try:
        db_agent_tools = MediaCrawlerDB()
        logger.info("æ°æ®åºå·¥å·åå§åæåï¼å¼å§æ§è¡æµè¯åºï¿½?..\n")
        
        # åºæ¯1: (ï¿½? æ¥æ¾è¿å»ä¸å¨ç»¼åç­åº¦æé«çåå®¹ (ä¸åéè¦sort_by)
        response1 = db_agent_tools.search_hot_content(time_period='week', limit=5)
        print_response_summary(response1)

        # åºæ¯2: æ¥æ¾è¿å»24å°æ¶åç»¼åç­åº¦æé«çåå®¹
        response2 = db_agent_tools.search_hot_content(time_period='24h', limit=5)
        print_response_summary(response2)

        # åºæ¯3: å¨å±æç´¢"ç½æ°¸ï¿½?
        response3 = db_agent_tools.search_topic_globally(topic="ç½æ°¸ï¿½?, limit_per_table=2)
        print_response_summary(response3)

        # åºæ¯4: (æ°å¢) å¨Bç«ä¸ç²¾ç¡®æç´¢"è®ºæ"
        response4 = db_agent_tools.search_topic_on_platform(platform='bilibili', topic="è®ºæ", limit=5)
        print_response_summary(response4)

        # åºæ¯5: (æ°å¢) å¨å¾®åä¸ç²¾ç¡®æç´¢ "è®¸å¯" å¨ç¹å®ä¸å¤©åçåï¿½?
        response5 = db_agent_tools.search_topic_on_platform(platform='weibo', topic="è®¸å¯", start_date='2025-08-22', end_date='2025-08-22', limit=5)
        print_response_summary(response5)

    except ValueError as e:
        logger.exception(f"åå§åå¤±ï¿½? {e}")
        logger.exception("è¯·ç¡®ä¿ç¸å³çæ°æ®åºç¯å¢åéå·²æ­£ç¡®è®¾ç½®, æå¨ä»£ç ä¸­ç´æ¥æä¾è¿æ¥ä¿¡æ¯ï¿½?)
    except Exception as e:
        logger.exception(f"æµè¯è¿ç¨ä¸­åçæªç¥éï¿½? {e}")
