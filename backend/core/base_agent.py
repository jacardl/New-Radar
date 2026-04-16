# -*- coding: utf-8 -*-
"""
Based on Hermes Agent core Agent base class and local database search tool.
Hermes intelligent agent framework is embedded in the backend code flow,
directly responsible for reasoning and tool scheduling.
"""
import os
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import asyncpg
from hermes_agent import AIAgent, Tool
import logging

from backend.core.external_tools import ExternalSearchTools

logger = logging.getLogger(__name__)


class LocalDatabaseSearchTool:
    """
    General-purpose local database search tool (supports keyword and vector search).
    Only fetches data from local PostgreSQL/PGVector crawled_data table.
    The embedding column stores JSON text strings [0.1, 0.2, ...], using ::vector cast for L2 distance calculation.
    """
    _pool: Optional[asyncpg.Pool] = None

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._get_pool()  # lazy init pool

    def _get_pool(self) -> asyncpg.Pool:
        if LocalDatabaseSearchTool._pool is None:
            async def _create_pool():
                LocalDatabaseSearchTool._pool = await asyncpg.create_pool(
                    host=os.getenv("DB_HOST", "127.0.0.1"),
                    port=int(os.getenv("DB_PORT", "5444")),
                    user=os.getenv("DB_USER", "radar"),
                    password=os.getenv("DB_PASSWORD", "radar"),
                    database=os.getenv("DB_NAME", "radar"),
                    min_size=2,
                    max_size=10,
                )
            asyncio.run(_create_pool())
        return LocalDatabaseSearchTool._pool

    async def _keyword_search(self, keyword: str, limit: int = 10) -> dict:
        """Keyword-based local search (async)"""
        pool = self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT platform, content_type, content, source_url, source_keyword,
                       create_time, ip_location, user_id, nickname,
                       liked_count, collected_count, comment_count, share_count
                FROM crawled_data
                WHERE content ILIKE $1
                ORDER BY create_time DESC
                LIMIT $2
                """,
                f"%{keyword}%",
                limit,
            )
            if not rows:
                return {"results": [], "total": 0}
            results = [dict(r) for r in rows]
            return {"results": results, "total": len(results)}

    async def _vector_search(self, query_embedding: list, limit: int = 10) -> dict:
        """pgvector-based semantic similarity search (async).
        The embedding column stores JSON text [0.1, ...], using ::vector cast for L2 distance.
        """
        pool = self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT platform, content_type, content, source_url, source_keyword,
                       create_time, ip_location, user_id, nickname,
                       liked_count, collected_count, comment_count, share_count
                FROM crawled_data
                WHERE embedding IS NOT NULL AND embedding != ''
                ORDER BY embedding::vector <-> $1::vector
                LIMIT $2
                """,
                query_embedding,
                limit,
            )
            if not rows:
                return {"results": [], "total": 0}
            results = [dict(r) for r in rows]
            return {"results": results, "total": len(results)}

    def keyword_search(self, keyword: str, limit: int = 10) -> str:
        """Keyword-based local search (sync wrapper for Hermes tool)"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        future = self._executor.submit(loop.run_until_complete, self._keyword_search(keyword, limit))
        result = future.result()
        return json.dumps(result, ensure_ascii=False)

    def vector_search(self, query_embedding: list, limit: int = 10) -> str:
        """pgvector semantic similarity search (sync wrapper for Hermes tool)"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        future = self._executor.submit(loop.run_until_complete, self._vector_search(query_embedding, limit))
        result = future.result()
        return json.dumps(result, ensure_ascii=False)


class BaseHermesAgent:
    """
    Embedded Hermes Agent base class.
    Hermes comes with native FTS5 memory retrieval, behavior modeling, and automated skill extraction.
    Each Engine can inherit this class to implement its own Prompt and specific tool logic.
    """
    def __init__(self, name: str, role_instruction: str, session_id: str):
        self.name = name
        self.session_id = session_id

        # Initialize local database tool
        self.db_tool = LocalDatabaseSearchTool()

        # Wrap as Hermes Tool format
        keyword_tool = Tool(
            name="keyword_search",
            description="Search crawled opinion data from local PostgreSQL using keyword (ILIKE)",
            func=self.db_tool.keyword_search
        )

        vector_tool = Tool(
            name="vector_search",
            description="Search crawled opinion data from local database using pgvector semantic similarity (L2 distance)",
            func=self.db_tool.vector_search
        )

        tools_list = [keyword_tool, vector_tool]

        # Mount sentiment analysis tool if enabled
        if os.getenv("ENABLE_SENTIMENT_TOOL") == "True":
            from backend.core.sentiment_tool import SentimentAnalysisTool
            sentiment_tool_instance = SentimentAnalysisTool()
            tools_list.append(Tool(
                name="sentiment_analysis",
                description=sentiment_tool_instance.description,
                func=sentiment_tool_instance
            ))

        # Dynamically mount external tools based on .env
        if os.getenv("ENABLE_ANSPIRE") == "True":
            tools_list.append(Tool(
                name="anspire_search",
                description="Use Anspire API for deep web search (suitable for Insight Engine private domain expansion)",
                func=ExternalSearchTools.anspire_search
            ))

        if os.getenv("ENABLE_BOCHA") == "True":
            tools_list.append(Tool(
                name="bocha_search",
                description="Use Bocha API to get search results, suitable for multimodal and structured Modal Card (Media Engine only)",
                func=ExternalSearchTools.bocha_search
            ))

        if os.getenv("ENABLE_TAVILY") == "True":
            tools_list.append(Tool(
                name="tavily_search",
                description="Use Tavily API to get latest news and trending content across the web (suitable for Query Engine broad search)",
                func=ExternalSearchTools.tavily_search
            ))

        if os.getenv("ENABLE_FIRECRAWL") == "True":
            tools_list.append(Tool(
                name="firecrawl_scrape",
                description="Given any URL, use Firecrawl to scrape deep content and convert to Markdown",
                func=ExternalSearchTools.firecrawl_scrape
            ))

        # Initialize Hermes AIAgent with system prompt, tools, and persistent memory
        self.agent = AIAgent(
            name=self.name,
            system_prompt=role_instruction,
            tools=tools_list,
            session_id=self.session_id,
            enable_memory=True,
            enable_skills=True
        )

    def chat(self, user_message: str) -> str:
        """
        Send message to Hermes Agent.
        Hermes will automatically perform context compression, memory retrieval (RAG + behavior modeling),
        and tool call decisions.
        """
        try:
            response = self.agent.chat(user_message)
            return response
        except Exception as e:
            logger.error(f"Hermes Agent {self.name} execution failed: {e}")
            return f"[{self.name} analysis failed]: {str(e)}"
