# -*- coding: utf-8 -*-
"""
Unified database connection layer

SQLAlchemy 2.x async engine for MySQL and PostgreSQL.
"""

from __future__ import annotations
from urllib.parse import quote_plus
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy import text
from backend.config import settings


_engine: Optional[AsyncEngine] = None


def _build_database_url() -> str:
    dialect: str = (settings.DB_DIALECT or "mysql").lower()
    host: str = settings.DB_HOST or ""
    port: str = str(settings.DB_PORT or "")
    
    if os.path.exists("/.dockerenv") and host in ("localhost", "127.0.0.1"):
        host = "db"
        if port == "5444":
            port = "5432"

    user: str = settings.DB_USER or ""
    password: str = settings.DB_PASSWORD or ""
    db_name: str = settings.DB_NAME or ""

    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    password = quote_plus(password)

    if dialect in ("postgresql", "postgres"):
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

    return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{db_name}"


def get_async_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        database_url: str = _build_database_url()
        _engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
    return _engine


def get_async_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    engine = get_async_engine()
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return session_maker()


async def fetch_all(query: str, params: dict = None) -> list:
    engine = get_async_engine()
    async with engine.connect() as conn:
        if params:
            result = await conn.execute(text(query), params)
        else:
            result = await conn.execute(text(query))
        return [dict(row._mapping) for row in result]


async def execute_write(query: str, params: dict = None) -> int:
    engine = get_async_engine()
    async with engine.begin() as conn:
        if params:
            result = await conn.execute(text(query), params)
        else:
            result = await conn.execute(text(query))
        return result.rowcount


async def execute_write_many(query: str, params_list: list) -> int:
    engine = get_async_engine()
    async with engine.begin() as conn:
        for params in params_list:
            await conn.execute(text(query), params)
        return len(params_list)


__all__ = [
    "get_async_engine",
    "get_async_session",
    "fetch_all",
    "execute_write",
    "execute_write_many",
]
