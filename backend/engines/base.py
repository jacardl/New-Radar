# -*- coding: utf-8 -*-
"""
Multi-engine dispatcher for OpenAI-compatible API.

Routes chat completion requests to the appropriate engine (Query/Insight/Media)
and synthesizes results via ForumAgent.
"""
import json
import uuid
import time
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Generator, Optional, Dict, Any

from loguru import logger

DEFAULT_MODEL_NAME = "new-radar-agent"

# åå¼æ chunk å¤§å°ï¼æ¯ N ä¸ªå­ç¬¦ yield ä¸ä¸ª deltaï¼
CHUNK_SIZE = 20


class MultiEngineDispatcher:
    """
    Unified dispatcher that routes queries to Query, Insight, or Media engines,
    then synthesizes results via ForumAgent.

    When streaming:
    1. Classifies user intent to determine primary engine
    2. Runs ALL three engines in parallel for maximum coverage
    3. Each engine's result streams in as it completes
    4. After all engines done, ForumAgent streams a synthesized summary
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._executor = ThreadPoolExecutor(max_workers=4)

    def _classify_intent(self, user_message: str) -> str:
        """
        Keyword-based intent classification.
        Returns: "insight" | "media" | "query"
        """
        msg_lower = user_message.lower()

        insight_keywords = ["èæ", "ææ", "è¶å¿", "åæ", "è§ç¹", "è¯è®º", "ç­ç¹", "sentiment", "opinion", "trend", "analyze", "insight"]
        for kw in insight_keywords:
            if kw in msg_lower:
                return "insight"

        media_keywords = ["è§é¢", "å¾ç", "å¤åªä½", "video", "image", "media", "multimedia", "ç´æ­", "ç­è§é¢"]
        for kw in media_keywords:
            if kw in msg_lower:
                return "media"

        return "insight"

    def _stream_text(self, text: str, chunk_size: int = CHUNK_SIZE) -> Generator[str, None, None]:
        """Split text into small chunks for typewriter streaming effect."""
        for i in range(0, len(text), chunk_size):
            yield text[i:i + chunk_size]

    def _run_forum_synthesis(
        self,
        user_message: str,
        engine_results: Dict[str, str]
    ) -> str:
        """
        Use ForumAgent to synthesize results from all three engines.
        Calls ForumAgent.chat() with a structured prompt.
        """
        try:
            from backend.engines.forum.agent import ForumAgent
            forum_agent = ForumAgent(session_id=f"forum_dispatch_{uuid.uuid4().hex[:6]}")

            synthesis_prompt = self._build_synthesis_prompt(user_message, engine_results)
            return forum_agent.chat(synthesis_prompt)
        except Exception as e:
            logger.exception("ForumAgent synthesis failed")
            return f"\n\n## ç»¼ååæ\n\n[ForumAgent ç»¼ååæå¤±è´¥: {str(e)}]\n"

    def _build_synthesis_prompt(
        self,
        user_message: str,
        engine_results: Dict[str, str]
    ) -> str:
        """Build a structured prompt for ForumAgent to synthesize engine results."""
        sections = [f"## ç¨æ·åæè¯·æ±\n{user_message}\n"]

        sections.append("## åå¼æåå§åæç»æ\n")

        for eng in ["insight", "media", "query"]:
            result = engine_results.get(eng, "")
            if result:
                labels = {
                    "insight": "### Insight å¼æï¼æ¬å°èææ°æ®åº + ææåæï¼",
                    "media": "### Media å¼æï¼å¤åªä½åå®¹åæï¼",
                    "query": "### Query å¼æï¼ç½ç»æç´¢ï¼",
                }
                sections.append(f"{labels.get(eng, eng)}\n\n{result[:4000]}\n")

        sections.append("""## ç»¼ååæè¦æ±

è¯·ä½ä¸ºå®¢è§åæå©æï¼åºäºä»¥ä¸ä¸ä¸ªå¼æçæ°æ®è¿è¡ç»¼ååæï¼

1. **äº¤åéªè¯**ï¼å¯¹æ¯ä¸ä¸ªå¼æçç»æï¼æ¾åºå±è¯ååæ­§
2. **äºå®æ æ³¨**ï¼å¯¹ä½ç½®ä¿¡åº¦åå®¹ï¼å¦æ°æ®å²çªï¼ï¼æ æ³¨æ¥æºå¹¶ä¿çåæ URL
3. **æ°æ®ä¸è¶³æ¶**ï¼ç´æ¥å£°æ"æ°æ®ä¸è¶³ï¼æ æ³åæ"ï¼ç¦æ­¢ç¼é 
4. **è¾åºæ ¼å¼**ï¼ä½¿ç¨ Markdown æ é¢ç»æï¼å®¢è§ä¸¥è°¨

è¯·å¼å§ç»¼ååæï¼
""")
        return "\n".join(sections)

    def stream_analyze(self, user_message: str) -> Generator[str, None, None]:
        """
        Stream analysis results from all engines + ForumAgent synthesis.
        Yields SSE-formatted chunks compatible with OpenAI chat completions API.
        """
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        model = self.model_name
        created = int(time.time())
        primary_engine = self._classify_intent(user_message)

        result_queue: queue.Queue = queue.Queue()

        def run_all_engines():
            """Run all three engines in parallel, put results in queue as they complete."""
            futures: Dict[str, Future] = {
                "insight": self._executor.submit(self._run_engine, "insight", user_message),
                "media": self._executor.submit(self._run_engine, "media", user_message),
                "query": self._executor.submit(self._run_engine, "query", user_message),
            }

            pending = set(futures.keys())
            completed: Dict[str, str] = {}

            while pending:
                for eng in list(pending):
                    f = futures[eng]
                    if f.done():
                        pending.remove(eng)
                        try:
                            result = f.result(timeout=1)
                            completed[eng] = result
                            result_queue.put((eng, result))
                        except Exception as e:
                            logger.exception(f"Engine {eng} failed: {e}")
                            result_queue.put((eng, f"[{eng.upper()} Error]: {str(e)}"))
                if pending:
                    time.sleep(0.1)

            result_queue.put(("__done__", completed))

        thread = threading.Thread(target=run_all_engines, daemon=True)
        thread.start()

        # Yield opening
        yield self._sse_chunk(completion_id, model, created, "assistant",
            f"ð æ­£å¨å¯å¨å¨å¼æåæï¼ä¸»å¼æ: {primary_engine}ï¼...\n\n",
            index=0)

        received_results: Dict[str, bool] = {}
        last_heartbeat = time.time()
        engine_results: Dict[str, str] = {}

        while True:
            try:
                item = result_queue.get(timeout=120)
                eng, result = item

                if eng == "__done__":
                    engine_results = result
                    break

                if eng in received_results:
                    continue
                received_results[eng] = True
                engine_results[eng] = result

                icons = {"insight": "ð§ ", "media": "ð¬", "query": "ð"}
                labels = {
                    "insight": "Insight Engineï¼èæåæï¼",
                    "media": "Media Engineï¼å¤åªä½åæï¼",
                    "query": "Query Engineï¼ç½ç»æç´¢ï¼",
                }
                icon = icons.get(eng, "ð")
                label = labels.get(eng, eng.upper())

                header = f"\n\n{icon} **{label}**\n\n"
                for chunk in self._stream_text(header, chunk_size=CHUNK_SIZE):
                    yield self._sse_chunk(completion_id, model, created, "assistant", chunk, index=0)

                if result:
                    for chunk in self._stream_text(result, chunk_size=CHUNK_SIZE):
                        yield self._sse_chunk(completion_id, model, created, "assistant", chunk, index=0)

                yield self._sse_chunk(completion_id, model, created, "assistant", "\n\n---\n\n", index=0)
                last_heartbeat = time.time()

            except queue.Empty:
                elapsed = time.time() - last_heartbeat
                if elapsed > 4.0:
                    pending_count = 3 - len(received_results)
                    if pending_count > 0:
                        pending_names = [k for k in ["insight", "media", "query"] if k not in received_results]
                        names_str = "/".join(pending_names)
                        heartbeat_msg = f"â³ {names_str} engine(s) still running...\n\n"
                        yield self._sse_chunk(completion_id, model, created, "assistant", heartbeat_msg, index=0)
                    last_heartbeat = time.time()

        thread.join(timeout=5)

        # ForumAgent synthesis
        yield self._sse_chunk(completion_id, model, created, "assistant",
            "\n\nð¤ **ForumAgent ç»¼ååæ**ï¼æ­£å¨æ´åä¸å¼æè§ç¹...ï¼\n\n",
            index=0)
        last_heartbeat = time.time()

        try:
            synthesis = self._run_forum_synthesis(user_message, engine_results)
            for chunk in self._stream_text(synthesis, chunk_size=CHUNK_SIZE):
                yield self._sse_chunk(completion_id, model, created, "assistant", chunk, index=0)
        except Exception as e:
            logger.exception("ForumAgent synthesis streaming failed")
            error_msg = f"\n\n[ForumAgent ç»¼ååæå¤±è´¥: {str(e)}]\n"
            for chunk in self._stream_text(error_msg, chunk_size=CHUNK_SIZE):
                yield self._sse_chunk(completion_id, model, created, "assistant", chunk, index=0)

        # Final stop chunk
        yield self._sse_chunk(completion_id, model, created, "assistant", "", index=0,
                              finish_reason="stop")
        yield "data: [DONE]\n\n"

    def analyze(self, user_message: str) -> str:
        """
        Non-streaming analysis - runs all engines + ForumAgent synthesis.
        """
        primary_engine = self._classify_intent(user_message)

        futures = {
            "insight": self._executor.submit(self._run_engine, "insight", user_message),
            "media": self._executor.submit(self._run_engine, "media", user_message),
            "query": self._executor.submit(self._run_engine, "query", user_message),
        }

        results = {}
        pending = set(futures.keys())

        while pending:
            for eng in list(pending):
                f = futures[eng]
                if f.done():
                    pending.remove(eng)
                    try:
                        results[eng] = f.result(timeout=1)
                    except Exception as e:
                        logger.exception(f"Engine {eng} failed: {e}")
                        results[eng] = f"[{eng.upper()} Error]: {str(e)}"
            if pending:
                time.sleep(0.05)

        # ForumAgent synthesis
        synthesis = self._run_forum_synthesis(user_message, results)

        icons = {"insight": "ð§ ", "media": "ð¬", "query": "ð"}
        labels = {"insight": "Insight Engine", "media": "Media Engine", "query": "Query Engine"}

        output_parts = []
        for eng in ["insight", "media", "query"]:
            result = results.get(eng, "")
            if result:
                icon = icons.get(eng, "ð")
                label = labels.get(eng, eng.upper())
                output_parts.append(f"{icon} **{label}**\n\n{result}\n\n---\n")

        output_parts.append(f"ð¤ **ForumAgent ç»¼ååæ**\n\n{synthesis}\n")
        return "\n".join(output_parts)

    def _run_engine(self, engine_name: str, user_message: str) -> str:
        """Run the selected engine and return the research result."""
        engine_map = {
            "insight": "backend.engines.insight.agent",
            "media": "backend.engines.media.agent",
            "query": "backend.engines.query.agent",
        }

        import importlib
        agent_module = importlib.import_module(engine_map[engine_name])
        agent = agent_module.DeepSearchAgent()
        return agent.research(user_message)

    @staticmethod
    def _sse_chunk(completion_id: str, model: str, created: int,
                  role: str, content: str, index: int = 0,
                  finish_reason: Optional[str] = None) -> str:
        """Format a SSE data chunk for OpenAI chat completions stream."""
        delta = {"role": role, "content": content} if content else {"role": role, "content": ""}
        choice = {"index": index, "delta": delta}
        if finish_reason:
            choice["finish_reason"] = finish_reason

        payload = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "model": model,
            "created": created,
            "choices": [choice],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _build_non_stream_response(completion_id: str, model: str, created: int,
                                   content: str) -> dict:
        """Build a non-streaming OpenAI chat completion response."""
        return {
            "id": completion_id,
            "object": "chat.completion",
            "model": model,
            "created": created,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": len(content),
                "total_tokens": len(content),
            },
        }
