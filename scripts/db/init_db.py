# -*- coding: utf-8 -*-
"""
数据库初始化脚本
创建 crawled_data 表和 pgvector 扩展

使用方式:
    python scripts/db/init_db.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5444")
DB_USER = os.getenv("DB_USER", "radar")
DB_PASSWORD = os.getenv("DB_PASSWORD", "radar")
DB_NAME = os.getenv("DB_NAME", "radar")


async def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    # 连接默认 postgres 数据库
    server_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/postgres"

    engine = create_async_engine(server_url, echo=False, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{DB_NAME}'")
        )
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {DB_NAME}"))
            print(f"✅ 数据库 {DB_NAME} 创建成功")
        else:
            print(f"ℹ️  数据库 {DB_NAME} 已存在")

    await engine.dispose()


async def enable_pgvector():
    """启用 pgvector 扩展"""
    engine_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_async_engine(engine_url, echo=False)

    async with engine.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        print("✅ pgvector 扩展已启用")

    await engine.dispose()


async def create_crawled_data_table():
    """创建 crawled_data 表"""
    engine_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_async_engine(engine_url, echo=False)

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS crawled_data (
        id SERIAL PRIMARY KEY,
        platform VARCHAR(32) NOT NULL,
        content_type VARCHAR(16) NOT NULL,
        content TEXT NOT NULL,
        source_url TEXT,
        source_keyword TEXT,
        create_time BIGINT,
        ip_location VARCHAR(128),
        user_id VARCHAR(128),
        nickname VARCHAR(256),
        liked_count VARCHAR(32),
        collected_count VARCHAR(32),
        comment_count VARCHAR(32),
        share_count VARCHAR(32),
        embedding TEXT,
        raw_data TEXT,
        add_ts BIGINT,
        last_modify_ts BIGINT
    );
    """

    create_index_sql = """
    CREATE INDEX IF NOT EXISTS idx_crawled_data_platform_content_type
        ON crawled_data (platform, content_type);
    CREATE INDEX IF NOT EXISTS idx_crawled_data_source_keyword
        ON crawled_data (source_keyword);
    CREATE INDEX IF NOT EXISTS idx_crawled_data_create_time
        ON crawled_data (create_time DESC);
    """

    async with engine.connect() as conn:
        await conn.execute(text(create_table_sql))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_data_platform_content_type ON crawled_data (platform, content_type)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_data_source_keyword ON crawled_data (source_keyword)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_crawled_data_create_time ON crawled_data (create_time DESC)"))
        await conn.commit()
        print("✅ crawled_data 表创建成功")

    await engine.dispose()


async def verify_tables():
    """验证表创建成功"""
    engine_url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_async_engine(engine_url, echo=False)

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('crawled_data', 'xhs_note', 'douyin_aweme',
                               'bilibili_video', 'weibo_note', 'zhihu_content')
            ORDER BY table_name
        """))
        tables = [row[0] for row in result.fetchall()]
        print(f"\n📋 当前数据库中的表:")
        for t in tables:
            print(f"   - {t}")

    await engine.dispose()


async def main():
    print("=" * 50)
    print("New Radar 数据库初始化")
    print("=" * 50)

    try:
        # 1. 创建数据库
        print("\n[1/4] 检查数据库...")
        await create_database_if_not_exists()

        # 2. 启用 pgvector
        print("\n[2/4] 启用 pgvector...")
        await enable_pgvector()

        # 3. 创建表
        print("\n[3/4] 创建 crawled_data 表...")
        await create_crawled_data_table()

        # 4. 验证
        print("\n[4/4] 验证表结构...")
        await verify_tables()

        print("\n" + "=" * 50)
        print("✅ 数据库初始化完成!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
