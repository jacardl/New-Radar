#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database initialization script for New Radar
Creates the crawled_data table with pgvector support for embeddings
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def init_database():
    """Initialize database schema"""

    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_USER = os.getenv("DB_USER", "radar")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "radar")
    DB_NAME = os.getenv("DB_NAME", "radar")

    url = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    print(f"Connecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    engine = create_async_engine(url, echo=True)

    try:
        async with engine.connect() as conn:
            # Create extension for vector support
            print("Creating pgvector extension...")
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # Create crawled_data table
            print("Creating crawled_data table...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS crawled_data (
                    id SERIAL PRIMARY KEY,
                    platform VARCHAR(50) NOT NULL,
                    content_type VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    source_keyword VARCHAR(255),
                    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    nickname VARCHAR(255),
                    liked_count INTEGER DEFAULT 0,
                    embedding JSONB,
                    metadata JSONB
                )
            """))

            # Create index on platform
            print("Creating index on platform...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawled_data_platform
                ON crawled_data(platform)
            """))

            # Create index on create_time
            print("Creating index on create_time...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawled_data_create_time
                ON crawled_data(create_time DESC)
            """))

            # Create index on source_keyword
            print("Creating index on source_keyword...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawled_data_source_keyword
                ON crawled_data(source_keyword)
            """))

            # Create GIN index for full-text search on content
            print("Creating GIN index for content search...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_crawled_data_content
                ON crawled_data USING gin(to_tsvector('chinese', content))
            """))

            # Create index on embedding for vector similarity search
            print("Creating index for vector search...")
            try:
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_crawled_data_embedding
                    ON crawled_data USING ivfflat(embedding jsonb_path_ops)
                    WITH (lists = 100)
                """))
            except Exception as e:
                print(f"Note: Vector index creation failed (this is normal if data is sparse): {e}")

            await conn.commit()
            print("\n✅ Database initialization completed successfully!")

            # Verify table exists
            result = await conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'crawled_data'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print("\nTable columns:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]}")

    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_database())
