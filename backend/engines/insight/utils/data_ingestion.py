ï»¿import os
import json
import asyncio
import requests
from datetime import datetime
from pathlib import Path
from loguru import logger
from backend.db.connection import execute_write, fetch_all
from backend.config import settings

def _run_async(coro):
    """å®å¨çå¼æ­¥æ§è¡åè£å¨ï¼å¼å®¹å¤çº¿ç¨ä¸äºä»¶å¾ªç¯ç¯ï¿½?""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)

def ingest_seed_data(seed_id: str):
    """å°ç¨æ·ä¸ä¼ ç seed æä»¶åå®¹è§£æå¹¶æä¹åå°æ¬å°æ°æ®åºï¿½?""
    root_dir = Path(__file__).parent.parent.parent
    seed_path_json = root_dir / 'final_reports' / 'seeds' / f"{seed_id}.json"
    seed_path_txt = root_dir / 'final_reports' / 'seeds' / f"{seed_id}.txt"
    
    seed_text = ""
    title = "ç¨æ·ä¸ä¼ çåèèµï¿½?Seed)"
    url = f"seed://{seed_id}/attachment"
    
    if seed_path_json.exists():
        try:
            data = json.loads(seed_path_json.read_text(encoding='utf-8'))
            seed_text = data.get('text', '')
            title = data.get('filename', title)
            url = data.get('fake_url', url)
        except Exception as e:
            logger.error(f"è§£æ Seed JSON å¤±è´¥: {e}")
    elif seed_path_txt.exists():
        seed_text = seed_path_txt.read_text(encoding='utf-8')
        
    if not seed_text:
        return
        
    # é«çº§è¯­ä¹åçï¼åºäºæ®µè½åå¥å­çéå åï¿½?(Overlap Chunking)
    import re
    
    def smart_chunking(text: str, max_chunk_len: int = 1000, overlap: int = 150) -> list:
        # 1. åææ®µè½åå
        paragraphs = re.split(r'\n\s*\n', text)
        
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            # å¦æå ä¸è¿ä¸ªæ®µè½è¿æ²¡è¶é¿ï¼å°±å ä¸ï¿½?            if len(current_chunk) + len(p) + 2 <= max_chunk_len:
                current_chunk += ("\n\n" if current_chunk else "") + p
            else:
                # å·²ç»æä¸ä¸ªè¶³å¤å¤§ï¿½?chunkï¼åä¿å­
                if current_chunk:
                    chunks.append(current_chunk)
                    
                    # æå overlap ä½ä¸ºä¸ä¸ï¿½?chunk çå¼ï¿½?                    # å°½éä»æ ç¹ç¬¦å·å¤åå overlap
                    overlap_text = current_chunk[-overlap:]
                    match = re.search(r'[ãï¼ï¿½?!?\n]', overlap_text)
                    if match:
                        overlap_start = match.end()
                        current_chunk = overlap_text[overlap_start:].strip()
                    else:
                        current_chunk = overlap_text.strip()
                
                # å¦æåä¸ªæ®µè½ç¹å«é¿ï¼è¶è¿ max_chunk_lenï¼ï¼æå¥å­å¼ºè¡åï¿½?                if len(p) > max_chunk_len:
                    sentences = re.split(r'([ãï¼ï¿½?!?])', p)
                    
                    temp_sent = current_chunk
                    for i in range(0, len(sentences) - 1, 2):
                        sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")
                        if len(temp_sent) + len(sentence) > max_chunk_len and temp_sent:
                            chunks.append(temp_sent)
                            
                            overlap_text = temp_sent[-overlap:]
                            match = re.search(r'[ãï¼ï¿½?!?\n]', overlap_text)
                            if match:
                                temp_sent = overlap_text[match.end():].strip() + " " + sentence
                            else:
                                temp_sent = overlap_text.strip() + " " + sentence
                        else:
                            temp_sent += (" " if temp_sent else "") + sentence
                    
                    current_chunk = temp_sent
                else:
                    current_chunk += ("\n\n" if current_chunk else "") + p
                    
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks if chunks else [text]
        
    # è°ç¨æºè½åçï¼çæ³åå¤§å°ï¿½?00å­ï¼éå 100ï¿½?    chunks = smart_chunking(seed_text, max_chunk_len=800, overlap=100)
    
    now_ts = int(datetime.now().timestamp() * 1000)
    crawl_date = datetime.now().date()
    
    from utils.embedding import get_embeddings
    
    # æ¹éè®¡ç® Embedding ä»¥æå¤§æåéåº¦
    texts_to_embed = [f"{title}_çæ®µ{idx+1} {chunk}" for idx, chunk in enumerate(chunks)]
    try:
        embeddings = get_embeddings(texts_to_embed)
    except Exception as e:
        logger.error(f"Batch calculate embedding failed: {e}")
        embeddings = [None] * len(chunks)
    
    sql = """
        INSERT INTO daily_news (news_id, source_platform, title, description, url, crawl_date, add_ts, last_modify_ts, rank_position, embedding)
        VALUES (:nid, :platform, :title, :desc, :url, :cdate, :add_ts, :add_ts, 1, :emb)
    """
    
    inserted_count = 0
    all_params = []
    from backend.db.connection import execute_write_many
    
    for idx, chunk in enumerate(chunks):
        chunk_title = f"{title}_çæ®µ{idx+1}"
        news_id = f"seed_{seed_id[:8]}_{now_ts}_{idx}"
        
        emb = embeddings[idx]
        if emb:
            emb_str = f"[{','.join(map(str, emb))}]"
        else:
            emb_str = None
        
        params = {
            "nid": news_id,
            "platform": "seed_document",
            "title": chunk_title,
            "desc": chunk,
            "url": url,
            "cdate": crawl_date,
            "add_ts": now_ts + idx,  # ä¿è¯æ¶é´æ³å¯ä¸ï¿½?            "emb": emb_str
        }
        all_params.append(params)
        
        # åæ¡è®°å½éä¸åå¥ crawler.log
        log_file = root_dir / "logs" / "crawler.log"
        if log_file.parent.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                ts_str = datetime.now().strftime('%H:%M:%S')
                short_title = chunk_title[:40] + '...' if len(chunk_title) > 40 else chunk_title
                f.write(f"[{ts_str}] [RECORD] ð æåæå¥ [seed] -> [seed_document] {short_title}\n")
                
    try:
        if all_params:
            _run_async(execute_write_many(sql, all_params))
            inserted_count = len(all_params)
    except Exception as e:
        logger.error(f"ï¿½?æ¹éæå¥ Seed æ°æ®åçå¤±è´¥: {e}")
    finally:
        from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
        db_utils._engine = None  # Prevent event loop reuse issues
            
    logger.info(f"ï¿½?Seed æä»¶ ({seed_id}) å·²æåä¸º {len(chunks)} ä¸ªçæ®µå¹¶æä¹åè³ daily_news ï¿½? æåæå¥ {inserted_count} ï¿½?)
    
    # ï¿½?seed æ»ä½å¥åºè¡ä¸ºè®°å½ï¿½?crawler.log
    log_file = root_dir / "logs" / "crawler.log"
    if log_file.parent.exists():
        with open(log_file, "a", encoding="utf-8") as f:
            ts_str = datetime.now().strftime('%H:%M:%S')
            f.write(f"[{ts_str}] [SYSTEM] ð¥ [Seedå¥åº] æåå°ç¨æ·ä¸ä¼ çéä»¶ '{title}' (ID: {seed_id}) æåï¿½?{len(chunks)} æ¡è®°å½å¹¶åå¥æ¬å°æ°æ®åºn")


def _insert_results_into_db(results, now_ts, source_name):
    """å°æåç»æåè¡¨ç»ä¸åå¥æ¬å°æ°æ®ï¿½?""
    inserted_count = 0
    platform_stats = {"bilibili": 0, "xiaohongshu": 0, "douyin": 0, "weibo": 0, "web_news": 0}
    
    from utils.embedding import get_embeddings
    
    # æåææææ¬åå¤è¿è¡æ¹éåéå
    texts_to_embed = []
    for r in results:
        title = r.get("title", "") or ""
        content = r.get("content", "") or r.get("snippet", "") or r.get("raw_content", "") or ""
        texts_to_embed.append(title + " " + content)
        
    try:
        embeddings = get_embeddings(texts_to_embed)
    except Exception as e:
        logger.error(f"Batch calculate embedding failed: {e}")
        embeddings = [None] * len(results)
    
    from backend.db.connection import execute_write_many
    
    # Collect statements and params by table/sql
    sql_batches = {}
    platform_keys = []
    
    for idx, r in enumerate(results):
        url = r.get("url", "")
        title = r.get("title", "") or ""
        content = r.get("content", "") or r.get("snippet", "") or r.get("raw_content", "") or ""
        date_str = r.get("date") or r.get("published_date") or r.get("time")
        
        # è§£ææ¶é´ï¿½?        ts = now_ts
        if date_str:
            try:
                # å°è¯å¤ç§æ¶é´æ ¼å¼
                if 'T' in date_str:
                    dt = datetime.fromisoformat(date_str.split('+')[0].strip().replace('Z', ''))
                else:
                    from dateutil import parser
                    dt = parser.parse(date_str)
                ts = int(dt.timestamp() * 1000)
            except Exception:
                pass
                
        # å¤æ­è·¯ç±
        sql = ""
        params = {}
        platform_key = ""
        import json
        extra_info_str = json.dumps(r, ensure_ascii=False)
        
        emb = embeddings[idx]
        if emb:
            emb_str = f"[{','.join(map(str, emb))}]"
        else:
            emb_str = None
        
        if "bilibili.com" in url:
            # è§£å³ bilibili_video ï¿½?video_id ï¿½?BigInteger çé®ï¿½?            # Web-Access ï¿½?Bç«è§ï¿½?ID æä»¬å­æè´çåå¸æ°å¼ï¼æèåªåå¶åççæ°å­aidï¼å¦æè½æåçè¯ï¿½?            # æç®åçæ¹æ¡æ¯æ video_id è½¬ä¸ºéæºå¤§æ´æ°æå©ç¨ url æå aid
            import re
            aid_match = re.search(r'av(\d+)', url)
            bvid_match = re.search(r'BV([a-zA-Z0-9]+)', url)
            
            # ç±äº MediaCrawler ï¿½?video_id å¯¹åºçæ¯ B ç«ç aid (int)
            # å¦ææ²¡æ¾å°ï¼æä»¬å¯ä»¥éæºçæä¸ä¸ªå¤§çè´æ´æ°ï¼é¿åå²ï¿½?            if aid_match:
                video_id = int(aid_match.group(1))
            else:
                # ï¿½?URL hash æä¸ï¿½?15 ä½çæ´æ°
                import hashlib
                hash_int = int(hashlib.md5(url.encode()).hexdigest()[:12], 16)
                # è½¬ä¸ºè´æ°ï¼é²æ­¢åçå®ï¿½?aid å²çª
                video_id = -hash_int
                
            sql = "INSERT INTO bilibili_video (title, \"desc\", video_id, video_url, create_time, nickname, extra_info, embedding) VALUES (:t, :d, :vid, :u, :ts, :a, :ei, :emb) ON CONFLICT (video_id) DO NOTHING"
            params = {"t": title, "d": content, "vid": video_id, "u": url, "ts": ts, "a": "Bç«ç¨ï¿½?, "ei": extra_info_str, "emb": emb_str}
            platform_key = "bilibili"
        elif "xiaohongshu.com" in url:
            sql = "INSERT INTO xhs_note (title, \"desc\", note_url, time, nickname, extra_info, embedding) VALUES (:t, :d, :u, :ts, :a, :ei, :emb) ON CONFLICT (note_id) DO NOTHING"
            params = {"t": title, "d": content, "u": url, "ts": ts, "a": "å°çº¢ä¹¦ç¨ï¿½?, "ei": extra_info_str, "emb": emb_str}
            platform_key = "xiaohongshu"
        elif "douyin.com" in url:
            sql = "INSERT INTO douyin_aweme (title, \"desc\", aweme_url, create_time, nickname, extra_info, embedding) VALUES (:t, :d, :u, :ts, :a, :ei, :emb) ON CONFLICT (aweme_id) DO NOTHING"
            params = {"t": title, "d": content, "u": url, "ts": ts, "a": "æé³ç¨æ·", "ei": extra_info_str, "emb": emb_str}
            platform_key = "douyin"
        elif "weibo.com" in url:
            sql = "INSERT INTO weibo_note (content, note_url, create_time, nickname, extra_info, embedding) VALUES (:d, :u, :ts, :a, :ei, :emb) ON CONFLICT (note_id) DO NOTHING"
            params = {"d": content, "u": url, "ts": ts, "a": "å¾®åç¨æ·", "ei": extra_info_str, "emb": emb_str}
            platform_key = "weibo"
        else:
            import hashlib
            news_id = f"{source_name}_" + hashlib.md5(url.encode()).hexdigest()[:16]
            crawl_date = datetime.now().date()
            # å¶ä»å¨é¨å¥æ¯æ¥ç­ç¹è¡¨ï¼æ è®°å¹³å°ä¸º web
            sql = "INSERT INTO daily_news (news_id, source_platform, title, description, url, crawl_date, add_ts, last_modify_ts, rank_position, extra_info, embedding) VALUES (:nid, 'web', :t, :d, :u, :cdate, :ts, :ts, 99, :ei, :emb) ON CONFLICT (news_id, source_platform, crawl_date) DO NOTHING"
            params = {"nid": news_id, "t": title, "d": content, "u": url, "cdate": crawl_date, "ts": ts, "ei": extra_info_str, "emb": emb_str}
            platform_key = "web_news"
            
        if sql not in sql_batches:
            sql_batches[sql] = []
        sql_batches[sql].append(params)
        
        platform_stats[platform_key] += 1
        platform_keys.append((platform_key, title, content))

    try:
        # æ§è¡æ¹éæå¥
        for sql, params_list in sql_batches.items():
            _run_async(execute_write_many(sql, params_list))
            inserted_count += len(params_list)
            
        # æ¹éåæ¥ï¿½?        log_file = Path("logs/crawler.log")
        if log_file.parent.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                for platform_key, title, content in platform_keys:
                    ts_str = datetime.now().strftime('%H:%M:%S')
                    short_title = title[:30] + '...' if len(title) > 30 else title
                    if not short_title:
                        short_title = content[:30] + '...' if len(content) > 30 else content
                    f.write(f"[{ts_str}] [RECORD] ð æåæå¥ [{source_name}] -> [{platform_key}] {short_title}\n")
    except Exception as e:
        err_msg = f"ï¿½?æ¹éæå¥æ°æ®å¤±è´¥: {e}"
        logger.error(err_msg)
        _write_to_crawler_log("ERROR", err_msg)
    finally:
        from backend.db.connection import fetch_all as db_fetch_all, execute_write as db_execute
        db_utils._engine = None

    details = ", ".join([f"{k}: {v}ï¿½? for k, v in platform_stats.items() if v > 0])
    return inserted_count, details


def ingest_incremental_mediacrawler_data(query: str, platforms: list = None):
    """
    éè¿åé¨ MediaCrawler å­æ¨¡åå®æ¶æåå°çº¢ä¹¦ãæé³ç­å¹³å°æ°æ®ï¿½?    è°ç¨ PlatformCrawler æ§è¡ä»»å¡ï¼å®ä¼å°æ°æ®å­å¥æ¬å°æ°æ®åºï¼
    æ­¤æ¶æ°æ®æ²¡æ embeddingãæä»¬éè¦å°åæå¥çæ°æ®è¿è¡åéåï¿½?    """
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    try:
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        sys.path.append(str(project_root))
        
        from MindSpider.DeepSentimentCrawling.platform_crawler import PlatformCrawler
        crawler = PlatformCrawler()
    except Exception as e:
        err_msg = f"æ æ³åå§ï¿½?MediaCrawlerï¼è·³è¿ç¤¾äº¤åªä½å¹³å°æï¿½? {e}"
        logger.warning(err_msg)
        _write_to_crawler_log("WARNING", err_msg)
        return 0, f"MediaCrawleråå§åå¤±ï¿½? {e}"
        
    logger.info(f"ð æ­£å¨éè¿ MediaCrawler è·å '{query}' çå¢éæ°ï¿½?..")
    total_inserted = 0
    details = []
    
    # æ ¹æ®éç½®æéæ±å¢åå¹³ï¿½?    platforms_to_crawl = platforms if platforms else ['xhs', 'dy']
    
    try:
        # ä¸ºäºé¿åé»å¡è¿ä¹ï¼è¿ééï¿½?max_notes=5 ï¿½?10
        stats = crawler.run_multi_platform_crawl_by_keywords(
            keywords=[query],
            platforms=platforms_to_crawl,
            login_type="qrcode",
            max_notes_per_keyword=5
        )
        
        for p in platforms_to_crawl:
            p_stats = stats.get("platform_summary", {}).get(p, {})
            notes_count = p_stats.get("total_notes", 0)
            if notes_count > 0:
                total_inserted += notes_count
                details.append(f"{p}:{notes_count}")
                
        # MediaCrawler æ§è¡å®æåï¼æ°æ®å·²ç»åå¥æ¬å°æ°æ®åºï¼ä¾å¦ xhs_note, douyin_aweme ç­è¡¨ï¿½?        # ä½æ¯è¿äºæ°æ°æ®æ²¡ï¿½?embeddingï¼æä»¬éè¦å¨è¿éè§¦ååååå¡«ï¼backfillï¿½?        log_file = Path("logs/crawler.log")
        if total_inserted > 0:
            logger.info("ï¿½?MediaCrawler æåå®æ¯ï¼åå¤ä¸ºæ°æå¥çæ°æ®çæåé...")
            if log_file.parent.exists():
                with open(log_file, "a", encoding="utf-8") as f:
                    ts_str = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts_str}] [SYSTEM] ð·ï¿½?MediaCrawler æåå®æï¼åå¤åï¿½?{total_inserted} æ¡æ°æ®çåén")
            
            import asyncio
            from utils.embedding import embedding_service
            from backend.db.connection import get_async_engine
            from sqlalchemy import text
            
            async def backfill_embeddings():
                engine = get_async_engine()
                async with engine.begin() as conn:
                    # æ£æ¥ææåæ¯æçè¡¨
                    tables_content_cols = {
                        'xhs_note': 'desc',
                        'douyin_aweme': 'desc',
                        'bilibili_video': 'desc',
                        'kuaishou_video': 'desc',
                        'weibo_note': 'desc',
                        'zhihu_content': 'content',
                        'tieba_note': 'content'
                    }
                    
                    for tb_name, col_name in tables_content_cols.items():
                        # æ¾åºæ²¡æ embedding çè®°ï¿½?                        query_sql = text(f"SELECT id, title, {col_name} as content FROM {tb_name} WHERE embedding IS NULL LIMIT 100")
                        try:
                            res = await conn.execute(query_sql)
                            rows = res.fetchall()
                            if not rows:
                                continue
                                
                            logger.info(f"ï¿½?{tb_name} åç° {len(rows)} æ¡æ åéè®°å½ï¼å¼å§çï¿½?..")
                            texts_to_embed = []
                            ids = []
                            for r in rows:
                                t = r.title or ""
                                c = r.content or ""
                                combined = f"{t} {c}".strip()
                                texts_to_embed.append(combined)
                                ids.append(r.id)
                                
                                # åæ¥ï¿½?                                if log_file.parent.exists():
                                    with open(log_file, "a", encoding="utf-8") as f:
                                        ts_time = datetime.now().strftime('%H:%M:%S')
                                        short_title = t[:30] + '...' if len(t) > 30 else t
                                        if not short_title:
                                            short_title = c[:30] + '...' if len(c) > 30 else c
                                        f.write(f"[{ts_time}] [RECORD] ð æåæå¥ [MediaCrawler] -> [{tb_name}] {short_title}\n")
                                
                            embeddings = embedding_service.get_embeddings(texts_to_embed)
                            
                            # æ´æ°åæ°æ®åº
                            for idx, emb in zip(ids, embeddings):
                                # pgvector expects string representation like '[0.1, 0.2, ...]'
                                emb_str = "[" + ",".join(map(str, emb)) + "]"
                                update_sql = text(f"UPDATE {tb_name} SET embedding = :emb WHERE id = :id")
                                await conn.execute(update_sql, {"emb": emb_str, "id": idx})
                                
                            logger.info(f"ï¿½?ï¿½?{tb_name} æåæ´æ° {len(rows)} æ¡åéè®°ï¿½?)
                        except Exception as table_err:
                            # è¡¨å¯è½ä¸å­å¨ï¼è·³ï¿½?                            continue
                            
            # è¿è¡åååå¡«ä»»å¡
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(backfill_embeddings())
                else:
                    loop.run_until_complete(backfill_embeddings())
            except Exception as e:
                asyncio.run(backfill_embeddings())
                
    except Exception as e:
        err_msg = f"ï¿½?MediaCrawler å¢éæåè¯·æ±å¤±è´¥: {e}"
        logger.error(err_msg)
        _write_to_crawler_log("ERROR", err_msg)
        return 0, f"æåå¤±è´¥: {e}"
        
    return total_inserted, ", ".join(details) if details else "æ æ°å¢æ°ï¿½?

def ingest_incremental_anspire_data(query: str):
    """éè¿ Anspire API å®æ¶æåå¢éæ°æ®ï¼å¹¶æå¥å°æ¬å°å¯¹åºçæ°æ®è¡¨ä¸­
    è¿å: (æå¥æ»è¡ï¿½? int, åå¹³å°æï¿½? str)
    """
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    anspire_key = os.getenv("ANSPIRE_API_KEY") or getattr(settings, "ANSPIRE_API_KEY", None)
    if not anspire_key:
        logger.warning("æªéï¿½?ANSPIRE_API_KEYï¼æ æ³æ§è¡å¢éæï¿½?)
        return 0, "æªéï¿½?API Key"
        
    use_pro = str(os.getenv("ANSPIRE_USE_PRO", "True")).lower() in ("true", "1", "yes", "t")
    target_url = getattr(settings, "ANSPIRE_PRO_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/prosearch") if use_pro else getattr(settings, "ANSPIRE_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/search")
    
    headers = {
        'Authorization': f'Bearer {anspire_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "query": query,
        "top_k": 100, # å°½å¯è½å¤å°è·åæ°ï¿½?        "detail": True # å¼ºå¶è·åè¯¦ç»ä¿¡æ¯ï¼å®ï¿½?raw dataï¿½?    }
    
    logger.info(f"ð æ­£å¨ï¿½?Anspire è·å '{query}' çå¢éæ°ï¿½?..")
    try:
        response = requests.get(target_url, headers=headers, params=payload, timeout=45)
        response.raise_for_status()
        results = response.json().get("results", [])
    except Exception as e:
        logger.error(f"ï¿½?å¢éæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"è¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("æªæåå°ä»»ä½å¢éæ°æ®")
        return 0, "API è¿å 0 æ¡ç»ï¿½?
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    # ãæ°å¢æºå¶ï¼ä¿å­å®æ´ï¿½?raw dataï¿½?    import json
    from pathlib import Path
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_anspire_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "anspire", "results": results}, f, ensure_ascii=False, indent=2)
        logger.info(f"ð¾ å®æ´ Raw Data å·²ä¿å­è³: {raw_file}")
    except Exception as e:
        logger.error(f"ï¿½?ä¿å­ Raw Data å¤±è´¥: {e}")

    inserted_count, details = _insert_results_into_db(results, now_ts, "anspire")
    
    logger.info(f"ï¿½?[Anspire] å¢éæ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details

def ingest_incremental_duckduckgo_data(query: str):
    """ååºæ¹æ¡ï¼å½æ²¡æä»»ä½ API Key æ¶ï¼ä½¿ç¨åè´¹ï¿½?DuckDuckGo HTML æåæå¶åºç¡çæ°ï¿½?""
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    logger.info(f"ð æªéç½®ä»»ä½é«ï¿½?APIï¼å¯å¨ååºæ¹ï¿½? ï¿½?DuckDuckGo è·å '{query}' çåºç¡æ°æ®...")
    import requests
    from bs4 import BeautifulSoup
    import re
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    results = []
    try:
        # ä¸ºäºé²å°ç¦ï¼æ¢ä¸ä¸ªå½åå¯ä»¥è®¿é®ä¸æ éAPI Keyçæ¿ä»£æ¹æ¡ï¼æ¯å¦ Sogou æç´æ¥ä½¿ç¨åç½®çæ¨¡ææ°æ®ä½ä¸ºååº
        url = "https://sogou.com/web"
        response = requests.get(url, headers=headers, params={"query": query}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        for div in soup.find_all('div', class_='vrwrap'):
            title_elem = div.find('h3', class_='vtit')
            if not title_elem:
                title_elem = div.find('h3', class_='vr-title')
            
            snippet_elem = div.find('div', class_='star-wiki')
            if not snippet_elem:
                snippet_elem = div.find('p', class_='str_info')
                
            if title_elem and title_elem.a:
                title = title_elem.get_text(strip=True)
                link = title_elem.a['href']
                if not link.startswith('http'):
                    link = "https://sogou.com" + link
                    
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else title
                
                results.append({
                    "title": title,
                    "url": link,
                    "content": snippet,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "original_data": {"source": "sogou_fallback"}
                })
                
        # å¦æç¬åå¤±è´¥ï¼è¢«æ¦æªç­ï¼ï¼è¿åä¸¤æ¡æå¶åºç¡çæ¨¡ææ°æ®ä»¥é²ç³»ç»å´©ï¿½?        if not results:
            results = [
                {
                    "title": f"å³äº {query} çå¨ç½åºç¡åæ",
                    "url": "local://fallback/1",
                    "content": f"ç³»ç»æªéç½®é«ï¿½?API Keyï¼å½åä¸ºåºç¡åå¤æç´¢ç»æãåå«å³é®å­ï¼{query}ï¿½?,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "original_data": {"source": "mock_fallback"}
                },
                {
                    "title": f"æï¿½?{query} è¶å¿æ¥å",
                    "url": "local://fallback/2",
                    "content": f"è¿æ¯åºç¡æç´¢ä¸ºæ¨è¿åçååºæ°æ®ï¼ä»¥ç¡®ä¿æµç¨ä¸ä¸­æ­ãå¦éæ·±åº¦æ°æ®ï¼è¯·éç½®å¤é¨ APIï¿½?,
                    "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "original_data": {"source": "mock_fallback"}
                }
            ]
    except Exception as e:
        logger.error(f"ï¿½?ååºæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"ååºè¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("ååºæ¹æ¡æªæåå°ä»»ä½æ°æ®")
        return 0, "ååº API è¿å 0 æ¡ç»ï¿½?
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_fallback_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "duckduckgo_fallback", "results": results}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    inserted_count, details = _insert_results_into_db(results, now_ts, "fallback_ddg")
    logger.info(f"ï¿½?[ååºæ¹æ¡] æ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details

def ingest_incremental_tavily_data(query: str):
    """éè¿ Tavily API æåå¢éæ°æ®ï¼æå¥æ¬å°æ°æ®è¡¨"""
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    tavily_key = os.getenv("TAVILY_API_KEY") or getattr(settings, "TAVILY_API_KEY", None)
    if not tavily_key:
        logger.warning("æªéï¿½?TAVILY_API_KEYï¼è·³ï¿½?Tavily æå")
        return 0, "æªéï¿½?API Key"
        
    logger.info(f"ð æ­£å¨ï¿½?Tavily è·å '{query}' çå¢éæ°ï¿½?..")
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=tavily_key)
        # å¼ºå¶å¼å¯è·åå¨æéé¡¹ï¼ä»¥è·å¾ raw_content
        response_dict = client.search(query=query, topic="general", include_raw_content=True, max_results=100)
        results = response_dict.get("results", [])
    except Exception as e:
        logger.error(f"ï¿½?Tavily å¢éæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"è¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("Tavily æªæåå°ä»»ä½å¢éæ°æ®")
        return 0, "API è¿å 0 æ¡ç»ï¿½?
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_tavily_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "tavily", "results": results}, f, ensure_ascii=False, indent=2)
        logger.info(f"ð¾ å®æ´ Tavily Raw Data å·²ä¿å­è³: {raw_file}")
    except Exception as e:
        pass

    inserted_count, details = _insert_results_into_db(results, now_ts, "tavily")
    logger.info(f"ï¿½?[Tavily] å¢éæ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details

def ingest_incremental_bocha_data(query: str):
    """éè¿ Bocha API æåå¢éæ°æ®ï¼æå¥æ¬å°æ°æ®è¡¨"""
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    bocha_key = os.getenv("BOCHA_API_KEY") or os.getenv("BOCHA_WEB_API_KEY") or getattr(settings, "BOCHA_WEB_SEARCH_API_KEY", None)
    if not bocha_key:
        logger.warning("æªéï¿½?BOCHA_API_KEY ï¿½?BOCHA_WEB_API_KEYï¼è·³ï¿½?Bocha æå")
        return 0, "æªéï¿½?API Key"
        
    logger.info(f"ð æ­£å¨ï¿½?Bocha è·å '{query}' çå¢éæ°ï¿½?..")
    url = os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn/v1/web-search")
    headers = {
        "Authorization": f"Bearer {bocha_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "count": 100
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        json_resp = response.json()
        results = json_resp.get("data", {}).get("webPages", {}).get("value", [])
    except Exception as e:
        logger.error(f"ï¿½?Bocha å¢éæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"è¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("Bocha æªæåå°ä»»ä½å¢éæ°æ®")
        return 0, "API è¿å 0 æ¡ç»ï¿½?
        
    # éé Bocha çè¿åå­æ®µå°ç»ä¸æ ¼å¼
    formatted_results = []
    for r in results:
        formatted_results.append({
            "title": r.get("name", ""),
            "url": r.get("url", ""),
            "content": r.get("snippet", ""),
            "date": r.get("dateLastCrawled", ""),
            "siteName": r.get("siteName", ""),
            "original_data": r
        })
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_bocha_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "bocha", "results": formatted_results}, f, ensure_ascii=False, indent=2)
        logger.info(f"ð¾ å®æ´ Bocha Raw Data å·²ä¿å­è³: {raw_file}")
    except Exception as e:
        pass

    inserted_count, details = _insert_results_into_db(formatted_results, now_ts, "bocha")
    logger.info(f"ï¿½?[Bocha] å¢éæ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details

def ingest_incremental_web_access_data(query: str):
    """éè¿ Web-Access (ï¿½?Firecrawl æèªå®ä¹ç¬è«æå¡) æåå¢éæ°æ®"""
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
    if not firecrawl_key:
        logger.info("æªéï¿½?FIRECRAWL_API_KEYï¼è·³ï¿½?Web-Access æ·±åº¦æå")
        return 0, "æªéï¿½?Firecrawl API Key"
        
    logger.info(f"ð æ­£å¨éè¿ Web-Access æå¡è·å '{query}' çå¢éæ°ï¿½?..")
    try:
        import requests
        base_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1")
        # å¼å®¹åç¼
        if not base_url.endswith("/v1") and not base_url.endswith("/v0"):
            if base_url.endswith("/"):
                base_url = base_url + "v1"
            else:
                base_url = base_url + "/v1"
                
        url = f"{base_url}/search"
        headers = {
            "Authorization": f"Bearer {firecrawl_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "limit": 100
        }
        response = requests.post(url, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        json_resp = response.json()
        results = json_resp.get("data", [])
    except Exception as e:
        logger.error(f"ï¿½?Web-Access å¢éæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"è¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("Web-Access æªæåå°ä»»ä½å¢éæ°æ®")
        return 0, "API è¿å 0 æ¡ç»ï¿½?
        
    formatted_results = []
    for r in results:
        formatted_results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("description", "") or r.get("markdown", ""),
            "date": r.get("publishedDate", ""),
            "original_data": r
        })
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_webaccess_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "web_access", "results": formatted_results}, f, ensure_ascii=False, indent=2)
        logger.info(f"ð¾ å®æ´ Web-Access Raw Data å·²ä¿å­è³: {raw_file}")
    except Exception as e:
        pass

    inserted_count, details = _insert_results_into_db(formatted_results, now_ts, "web_access")
    logger.info(f"ï¿½?[Web-Access] å¢éæ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details
    """éè¿ Anspire API å®æ¶æåå¢éæ°æ®ï¼å¹¶æå¥å°æ¬å°å¯¹åºçæ°æ®è¡¨ä¸­
    è¿å: (æå¥æ»è¡ï¿½? int, åå¹³å°æï¿½? str)
    """
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"
        
    anspire_key = os.getenv("ANSPIRE_API_KEY") or getattr(settings, "ANSPIRE_API_KEY", None)
    if not anspire_key:
        logger.warning("æªéï¿½?ANSPIRE_API_KEYï¼æ æ³æ§è¡å¢éæï¿½?)
        return 0, "æªéï¿½?API Key"
        
    use_pro = str(os.getenv("ANSPIRE_USE_PRO", "True")).lower() in ("true", "1", "yes", "t")
    target_url = getattr(settings, "ANSPIRE_PRO_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/prosearch") if use_pro else getattr(settings, "ANSPIRE_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/search")
    
    headers = {
        'Authorization': f'Bearer {anspire_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "query": query,
        "top_k": 100, # å°½å¯è½å¤å°è·åæ°ï¿½?        "detail": True # å¼ºå¶è·åè¯¦ç»ä¿¡æ¯ï¼å®ï¿½?raw dataï¿½?    }
    
    logger.info(f"ð æ­£å¨ï¿½?Anspire è·å '{query}' çå¢éæ°ï¿½?..")
    try:
        response = requests.get(target_url, headers=headers, params=payload, timeout=45)
        response.raise_for_status()
        results = response.json().get("results", [])
    except Exception as e:
        logger.error(f"ï¿½?å¢éæåè¯·æ±å¤±è´¥: {e}")
        return 0, f"è¯·æ±å¤±è´¥: {e}"
        
    if not results:
        logger.info("æªæåå°ä»»ä½å¢éæ°æ®")
        return 0, "API è¿å 0 æ¡ç»ï¿½?
        
    now_ts = int(datetime.now().timestamp() * 1000)
    
    # ãæ°å¢æºå¶ï¼ä¿å­å®æ´ï¿½?raw dataï¿½?    import json
    from pathlib import Path
    try:
        raw_dir = Path("logs/raw_data")
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"crawler_raw_anspire_{now_ts}.json"
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"query": query, "timestamp": now_ts, "source": "anspire", "results": results}, f, ensure_ascii=False, indent=2)
        logger.info(f"ð¾ å®æ´ Raw Data å·²ä¿å­è³: {raw_file}")
    except Exception as e:
        logger.error(f"ï¿½?ä¿å­ Raw Data å¤±è´¥: {e}")

    inserted_count, details = _insert_results_into_db(results, now_ts, "anspire")
    
    logger.info(f"ï¿½?[Anspire] å¢éæ°æ®æåå®æ: æååæ¬å°æ°æ®åºæå¥ {inserted_count} æ¡ææ°è®°ï¿½? åå¸: {details}")
    return inserted_count, details

def _write_to_crawler_log(level: str, message: str):
    """
    å°æ¥å¿å®æ¶åå¥å° crawler.log ä¸­ï¼ä»¥ä¾¿ Web UI æ¾ç¤ºï¿½?    """
    try:
        log_file = Path("logs/crawler.log")
        if log_file.parent.exists():
            with open(log_file, "a", encoding="utf-8") as f:
                ts_str = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts_str}] [{level}] {message}\n")
    except Exception:
        pass

def ingest_all_sources_data(query: str):
    """
    ç»ä¸çæ°æ®ééå¥å£ï¿½?    å¹¶è¡è°ç¨éç½®çæææ°æ®æºï¼Anspire, Bocha ç­ï¼ï¿½?    å¹¶å°ææç»æèååå¥æ¬å°æ°æ®åºåæ¥å¿ï¿½?    """
    if not query:
        return 0, "æ¥è¯¢ä¸ºç©º"

    logger.info(f"ð å¼å§å¨ç½å¤æºèåééï¼å³é®ï¿½? '{query}'")
    _write_to_crawler_log("SYSTEM", f"ð å¼å§å¨ç½å¤æºèåééï¼å³é®ï¿½? '{query}'")
    
    total_inserted = 0
    all_details = []
    
    # è·åéç½®ä¸­çå¼å³ç¶ï¿½?    enable_anspire = str(os.getenv("ENABLE_ANSPIRE", getattr(settings, "ENABLE_ANSPIRE", "True"))).lower() in ("true", "1", "yes", "t")
    enable_tavily = str(os.getenv("ENABLE_TAVILY", getattr(settings, "ENABLE_TAVILY", "True"))).lower() in ("true", "1", "yes", "t")
    enable_bocha = str(os.getenv("ENABLE_BOCHA", getattr(settings, "ENABLE_BOCHA", "True"))).lower() in ("true", "1", "yes", "t")
    enable_firecrawl = str(os.getenv("ENABLE_FIRECRAWL", getattr(settings, "ENABLE_FIRECRAWL", "True"))).lower() in ("true", "1", "yes", "t")
    enable_mediacrawler = str(os.getenv("ENABLE_MEDIACRAWLER", getattr(settings, "ENABLE_MEDIACRAWLER", "True"))).lower() in ("true", "1", "yes", "t")
    enable_web_access = str(os.getenv("ENABLE_WEB_ACCESS", getattr(settings, "ENABLE_WEB_ACCESS", "True"))).lower() in ("true", "1", "yes", "t")

    if enable_anspire:
        try:
            anspire_count, anspire_detail = ingest_incremental_anspire_data(query)
            if anspire_count > 0:
                total_inserted += anspire_count
                all_details.append(f"[Anspire] {anspire_detail}")
        except Exception as e:
            err_msg = f"Anspire ééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    else:
        logger.info("Anspire ç¬è«å·²è¢«ç¦ç¨ï¼è·³è¿ééï¿½?)

    if enable_tavily:
        try:
            tavily_count, tavily_detail = ingest_incremental_tavily_data(query)
            if tavily_count > 0:
                total_inserted += tavily_count
                all_details.append(f"[Tavily] {tavily_detail}")
        except Exception as e:
            err_msg = f"Tavily ééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    else:
        logger.info("Tavily ç¬è«å·²è¢«ç¦ç¨ï¼è·³è¿ééï¿½?)

    if enable_bocha:
        try:
            bocha_count, bocha_detail = ingest_incremental_bocha_data(query)
            if bocha_count > 0:
                total_inserted += bocha_count
                all_details.append(f"[Bocha] {bocha_detail}")
        except Exception as e:
            err_msg = f"Bocha ééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    else:
        logger.info("Bocha ç¬è«å·²è¢«ç¦ç¨ï¼è·³è¿ééï¿½?)

    # Web-Access (Firecrawl)
    if enable_firecrawl:
        try:
            web_count, web_detail = ingest_incremental_web_access_data(query)
            if web_count > 0:
                total_inserted += web_count
                all_details.append(f"[Firecrawl] {web_detail}")
        except Exception as e:
            err_msg = f"Firecrawl ééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    else:
        logger.info("Firecrawl ç¬è«å·²è¢«ç¦ç¨ï¼è·³è¿ééï¿½?)

    # MediaCrawler (å°çº¢ä¹¦ãæé³ç­ç¤¾äº¤åªä½)
    if enable_mediacrawler:
        try:
            mc_count, mc_detail = ingest_incremental_mediacrawler_data(query)
            if mc_count > 0:
                total_inserted += mc_count
                all_details.append(f"[MediaCrawler] {mc_detail}")
        except Exception as e:
            err_msg = f"MediaCrawler ééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    else:
        logger.info("MediaCrawler ç¬è«å·²è¢«ç¦ç¨ï¼è·³è¿ééï¿½?)

    # ååºæ¹æ¡
    if enable_web_access and total_inserted == 0 and not all_details:
        logger.warning("â ï¸ è­¦å: æªè½éè¿é«çº§ API è·åæ°æ®ï¼å°ä½¿ç¨ Web-Access (DuckDuckGo) ååºæ¹æ¡ï¿½?)
        _write_to_crawler_log("SYSTEM", "â ï¸ è­¦å: æªè½éè¿é«çº§ API è·åæ°æ®ï¼å°ä½¿ç¨ Web-Access (DuckDuckGo) ååºæ¹æ¡ï¿½?)
        try:
            ddg_count, ddg_detail = ingest_incremental_duckduckgo_data(query)
            if ddg_count > 0:
                total_inserted += ddg_count
                all_details.append(f"[Web-Access] {ddg_detail}")
        except Exception as e:
            err_msg = f"Web-Access ååºééå¼å¸¸: {e}"
            logger.error(err_msg)
            _write_to_crawler_log("ERROR", f"ï¿½?{err_msg}")
    elif not enable_web_access and total_inserted == 0:
        logger.info("Web-Access ååºæ¹æ¡å·²è¢«ç¦ç¨ï¿½?)

    final_detail = " | ".join(all_details) if all_details else "æ æ°å¢æ°ï¿½?
    return total_inserted, final_detail
