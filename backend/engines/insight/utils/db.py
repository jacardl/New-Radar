ï»¿"""
éç¨æ°æ®åºå·¥å·ï¼å¼æ­¥ï¿½?

æ­¤æ¨¡åæä¾åºï¿½?SQLAlchemy 2.x å¼æ­¥å¼æçæ°æ®åºè®¿é®å°è£ï¼æ¯ï¿½?MySQL ï¿½?PostgreSQLï¿½?
æ°æ®æ¨¡åå®ä¹ä½ç½®ï¿½?
- æ ï¼æ¬æ¨¡åä»æä¾è¿æ¥ä¸æ¥è¯¢å·¥å·ï¼ä¸å®ä¹æ°æ®æ¨¡åï¼
"""

from __future__ import annotations
from urllib.parse import quote_plus
import asyncio
import os
from typing import Any, Dict, Iterable, List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy import text
from backend.config import settings

__all__ = [
    "get_async_engine",
    "fetch_all",
    "execute_write",
    "execute_write_many",
    "_run_async"
]


_engine: Optional[AsyncEngine] = None

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


def _build_database_url() -> str:
    dialect: str = (settings.DB_DIALECT or "mysql").lower()
    host: str = settings.DB_HOST or ""
    port: str = str(settings.DB_PORT or "")
    
    # èªå¨æ¢æµ Docker ç¯å¢ï¼ä¿®æ­£æ¬å°åç¯å°å
    if os.path.exists("/.dockerenv") and host in ("localhost", "127.0.0.1"):
        host = "db"
        if port == "5444":
            port = "5432"

    user: str = settings.DB_USER or ""
    password: str = settings.DB_PASSWORD or ""
    db_name: str = settings.DB_NAME or ""

    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")  # ç´æ¥ä½¿ç¨å¤é¨æä¾çå®æ´URL

    password = quote_plus(password)

    if dialect in ("postgresql", "postgres"):
        # PostgreSQL ä½¿ç¨ asyncpg é©±å¨
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

    # é»è®¤ MySQL ä½¿ç¨ aiomysql é©±å¨
    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"


def get_async_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        database_url: str = _build_database_url()
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine


async def fetch_all(query: str, params: Optional[Union[Iterable[Any], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    æ§è¡åªè¯»æ¥è¯¢å¹¶è¿åå­å¸åè¡¨ï¿½?
    """
    engine: AsyncEngine = get_async_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text(query), params or {})
        rows = result.mappings().all()
        # ï¿½?RowMapping è½¬æ¢ä¸ºæ®éå­ï¿½?
        return [dict(row) for row in rows]

async def execute_write(query: str, params: Optional[Union[Iterable[Any], Dict[str, Any]]] = None) -> int:
    """
    æ§è¡åæä½ï¼INSERT/UPDATE/DELETEï¼å¹¶è¿ååå½±åçè¡æ°ï¿½?
    """
    engine: AsyncEngine = get_async_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(query), params or {})
        return result.rowcount

async def execute_write_many(query: str, params: List[Dict[str, Any]]) -> int:
    """
    æ¹éæ§è¡åæä½ï¼INSERT/UPDATE/DELETEï¼ä»¥æå¤§æåæ§è½ï¿½?
    """
    if not params:
        return 0
    engine: AsyncEngine = get_async_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(query), params)
        return result.rowcount


