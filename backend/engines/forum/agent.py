# -*- coding: utf-8 -*-
"""
ForumEngine Agent - Multi-Agent Collaboration Scheduler
Inherits from BaseHermesAgent for Hermes AIAgent integration.
Orchestrates Query/Insight/Media agents for collaborative discussion.
"""

import json
import os
import time
import uuid
import logging
from typing import Optional, Dict, Any, List, Generator
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Lock

from backend.core.base_agent import BaseHermesAgent
from backend.config import settings

logger = logging.getLogger(__name__)

FORUM_HOST_ROLE_INSTRUCTION = """You are an objective analysis moderator (Forum Host). Your responsibilities are:

1. **Intent Decomposition**: When given a complex analysis request, break it down into sub-tasks appropriate for each engine:
   - QuerySearchAgent: Network search data, latest news, public opinion trends
   - InsightSearchAgent: Local database sentiment analysis, engagement metrics, topic clustering
   - MediaSearchAgent: Multimodal content (images/videos), platform-specific media analysis

2. **Collaborative Orchestration**: Guide the three agents to discuss and debate:
   - Assign specific perspectives or questions to each agent
   - Gather their findings and identify consensus and disagreements
   - Ask follow-up questions to eliminate blind spots

3. **Cross-Validation**: Check if different agents' findings conflict; mark low-confidence content but do NOT discard it - preserve it with source attribution for users to judge.

4. **Hard Stop (Zero-Shot Constraint)** [Highest Priority]: If the context does NOT contain sufficient information, you MUST directly output 'æ°æ®ä¸è¶³ï¼æ æ³åæ' (Insufficient data, cannot analyze). You are ABSOLUTELY PROHIBITED from role-playing, inferring, or fabricating data based on your own knowledge.

5. **Anti-Hallucination**: All conclusions must be sourced from the Agent records above. Do not speculate or invent content.

**Output Requirements**:
1. Pure factual guidance - only summarize based on provided data, never add subjective emotions
2. Source attribution - all factual viewpoints must cite which Agent provided the data
3. Concise and objective - keep each analysis under 1000 characters
4. Avoid cyber forensics and over-professionalism - use plain language (e.g., "these 100+ posts were almost all sent at the same time with highly similar content - likely bots")
5. **CRITICAL**: If data from different sources conflicts, explicitly mark it as "ä½ç½®ä¿¡åº¦" (low confidence) but still include it with the original source URL for user verification

**Agent Information Sources**:
- INSIGHT Agent: Private opinion database data (local PostgreSQL crawled_data)
- MEDIA Agent: Multimodal content data
- QUERY Agent: Web search data

**Your Tools**:
- keyword_search / vector_search: Search local database for crawled social media content
- tavily_search (if enabled): Search latest news across the web
- bocha_search (if enabled): Get structured multimodal analysis
- anspire_search (if enabled): Private domain knowledge search
"""


class ForumAgent(BaseHermesAgent):
    """
    Forum Agent - Multi-Agent Collaboration Scheduler.

    Inherits from BaseHermesAgent to get Hermes AIAgent capabilities plus
    local database search tools. Acts as the "forum moderator" to:
    1. Decompose complex analysis requests
    2. Dispatch to Query/Insight/Media engines (via direct API calls)
    3. Collect and synthesize debate results
    4. Output final consolidated analysis
    """

    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize Forum Agent.

        Args:
            session_id: Optional session identifier for Hermes memory
        """
        session_id = session_id or f"forum_{uuid.uuid4().hex[:8]}"
        super().__init__(
            name="ForumAgent",
            role_instruction=FORUM_HOST_ROLE_INSTRUCTION,
            session_id=session_id
        )

        # Thread pool for parallel engine dispatch
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._dispatch_lock = Lock()

        # Engine endpoints (configured via settings)
        self._engine_base_url = f"http://{settings.HOST}:{settings.PORT}"

    def _dispatch_to_engine(self, engine_name: str, query: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Dispatch a query to a specific engine via internal API call.

        Args:
            engine_name: One of 'query', 'insight', 'media'
            query: The search/query string
            timeout: Request timeout in seconds

        Returns:
            Dict with 'success', 'content', 'error' keys
        """
        import requests

        # Map engine names to their Flask routes
        engine_routes = {
            'query': '/api/query/search',
            'insight': '/api/insight/search',
            'media': '/api/media/search',
        }

        route = engine_routes.get(engine_name.lower())
        if not route:
            return {'success': False, 'error': f'Unknown engine: {engine_name}', 'content': ''}

        url = f"{self._engine_base_url}{route}"

        try:
            response = requests.post(
                url,
                json={'query': query, 'stream': False},
                timeout=timeout,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'content': data.get('content', data.get('result', '')),
                    'error': ''
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'content': ''
                }
        except requests.exceptions.Timeout:
            return {'success': False, 'error': f'{engine_name} timeout', 'content': ''}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': f'{engine_name} connection error', 'content': ''}
        except Exception as e:
            logger.exception(f"ForumAgent: Failed to dispatch to {engine_name}")
            return {'success': False, 'error': str(e), 'content': ''}

    def orchestrate(
        self,
        user_query: str,
        enable_query: bool = True,
        enable_insight: bool = True,
        enable_media: bool = True
    ) -> Dict[str, Any]:
        """
        Orchestrate multi-agent discussion on a complex topic.

        This method:
        1. Breaks down the user query into sub-tasks
        2. Dispatches to Query/Insight/Media engines in parallel
        3. Collects all results
        4. Returns a structured synthesis

        Args:
            user_query: The user's analysis request
            enable_query: Whether to enable QuerySearchAgent
            enable_insight: Whether to enable InsightSearchAgent
            enable_media: Whether to enable MediaSearchAgent

        Returns:
            Dict with engine results and synthesized summary
        """
        results = {
            'query': None,
            'insight': None,
            'media': None,
            'synthesis': None,
            'errors': []
        }

        # Build sub-queries for each engine based on the main query
        sub_queries = {
            'query': f"ç½ç»æç´¢ææ°ç¸å³èµè®¯åèæå¨æï¼{user_query}",
            'insight': f"åææ¬å°æ°æ®åºä¸­å³äºè¯¥è¯é¢çèææ°æ®åææå¾åï¼{user_query}",
            'media': f"åæè¯¥è¯é¢ç¸å³çå¤åªä½åå®¹ï¼å¾çãè§é¢ãå¾æï¼ä¼ æ­æåµï¼{user_query}",
        }

        # Dispatch to enabled engines in parallel
        futures: Dict[str, Future] = {}

        if enable_query:
            futures['query'] = self._executor.submit(self._dispatch_to_engine, 'query', sub_queries['query'])

        if enable_insight:
            futures['insight'] = self._executor.submit(self._dispatch_to_engine, 'insight', sub_queries['insight'])

        if enable_media:
            futures['media'] = self._executor.submit(self._dispatch_to_engine, 'media', sub_queries['media'])

        # Collect results as they complete
        for engine_name, future in futures.items():
            try:
                result = future.result(timeout=150)
                results[engine_name] = result
                if not result.get('success'):
                    results['errors'].append(f"{engine_name}: {result.get('error', 'unknown error')}")
            except Exception as e:
                logger.exception(f"ForumAgent: {engine_name} execution failed")
                results['errors'].append(f"{engine_name}: {str(e)}")
                results[engine_name] = {'success': False, 'error': str(e), 'content': ''}

        # Synthesize results using Hermes agent
        synthesis_input = self._build_synthesis_prompt(user_query, results)
        try:
            synthesis = self.chat(synthesis_input)
            results['synthesis'] = synthesis
        except Exception as e:
            logger.exception("ForumAgent: Synthesis failed")
            results['synthesis'] = f"ç»¼ååæå¤±è´¥: {str(e)}"

        return results

    def stream_orchestrate(
        self,
        user_query: str,
        enable_query: bool = True,
        enable_insight: bool = True,
        enable_media: bool = True
    ) -> Generator[str, None, None]:
        """
        Orchestrate multi-agent discussion with streaming output.

        Yields SSE-formatted chunks for real-time frontend display.

        Args:
            user_query: The user's analysis request
            enable_query: Whether to enable QuerySearchAgent
            enable_insight: Whether to enable InsightSearchAgent
            enable_media: Whether to enable MediaSearchAgent

        Yields:
            SSE-formatted string chunks
        """
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        model = getattr(settings, 'OPENAI_MODEL_NAME', 'new-radar-agent')

        # Step 1: Announce intent decomposition
        yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"ð æ­£å¨åè§£ä»»å¡...\"}},\"finish_reason\":null}}]}}\n\n"
        yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"\\n\"}},\"finish_reason\":null}}]}}\n\n"

        # Step 2: Dispatch to engines in parallel, stream progress
        sub_queries = {
            'query': f"ç½ç»æç´¢ææ°ç¸å³èµè®¯åèæå¨æï¼{user_query}",
            'insight': f"åææ¬å°æ°æ®åºä¸­å³äºè¯¥è¯é¢çèææ°æ®åææå¾åï¼{user_query}",
            'media': f"åæè¯¥è¯é¢ç¸å³çå¤åªä½åå®¹ï¼å¾çãè§é¢ãå¾æï¼ä¼ æ­æåµï¼{user_query}",
        }

        futures = {}
        engine_labels = []

        if enable_query:
            yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"ð¡ æ­£å¨è°ç¨ Query å¼æ...\"}},\"finish_reason\":null}}]}}\n\n"
            futures['query'] = self._executor.submit(self._dispatch_to_engine, 'query', sub_queries['query'])
            engine_labels.append('Query')

        if enable_insight:
            yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"ð æ­£å¨è°ç¨ Insight å¼æ...\"}},\"finish_reason\":null}}]}}\n\n"
            futures['insight'] = self._executor.submit(self._dispatch_to_engine, 'insight', sub_queries['insight'])
            engine_labels.append('Insight')

        if enable_media:
            yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"ð¬ æ­£å¨è°ç¨ Media å¼æ...\"}},\"finish_reason\":null}}]}}\n\n"
            futures['media'] = self._executor.submit(self._dispatch_to_engine, 'media', sub_queries['media'])
            engine_labels.append('Media')

        # Wait for all engines with heartbeat
        results = {}
        import time as time_module
        last_heartbeat = time_module.time()
        pending = list(futures.keys())

        while pending:
            time_module.sleep(0.5)

            for engine_name in list(pending):
                future = futures[engine_name]
                if future.done():
                    try:
                        results[engine_name] = future.result(timeout=1)
                    except Exception as e:
                        results[engine_name] = {'success': False, 'error': str(e), 'content': ''}
                    pending.remove(engine_name)

                    # Announce completion
                    label = engine_name.capitalize()
                    success = results[engine_name].get('success', False)
                    icon = "â" if success else "â ï¸"
                    yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"{icon} {label} å¼æå®æ\\n\"}},\"finish_reason\":null}}]}}\n\n"
                elif time_module.time() - last_heartbeat > 3:
                    # Heartbeat progress update
                    done_count = len(futures) - len(pending)
                    yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"â³ {done_count}/{len(futures)} å¼æè¿è¡ä¸­...\\n\"}},\"finish_reason\":null}}]}}\n\n"
                    last_heartbeat = time_module.time()

        # Step 3: Synthesize with Hermes agent
        yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"\\nð§  æ­£å¨ç»¼ååæ...\\n\\n\"}},\"finish_reason\":null}}]}}\n\n"

        synthesis_input = self._build_synthesis_prompt(user_query, results)
        try:
            synthesis = self.chat(synthesis_input)
            # Stream synthesis in chunks (split by lines for nicer display)
            for line in synthesis.split('\n'):
                if line.strip():
                    yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"{line}\\n\"}},\"finish_reason\":null}}]}}\n\n"
                else:
                    yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"\\n\"}},\"finish_reason\":null}}]}}\n\n"
        except Exception as e:
            logger.exception("ForumAgent: Stream synthesis failed")
            yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{\"content\":\"ç»¼ååæå¤±è´¥: {str(e)}\"}},\"finish_reason\":null}}]}}\n\n"

        # Final chunk
        yield f"data: {{\"id\":\"{completion_id}\",\"object\":\"chat.completion.chunk\",\"model\":\"{model}\",\"choices\":[{{\"index\":0,\"delta\":{{}},\"finish_reason\":\"stop\"}}]}}\n\n"
        yield "data: [DONE]\n\n"

    def _build_synthesis_prompt(self, user_query: str, results: Dict[str, Any]) -> str:
        """
        Build a synthesis prompt from engine results.

        Args:
            user_query: Original user query
            results: Dict with 'query', 'insight', 'media' results

        Returns:
            Formatted prompt string for Hermes chat
        """
        sections = [f"## ç¨æ·åæè¯·æ±\n{user_query}\n"]

        sections.append("## åå¼æåæç»æ\n")

        if results.get('query', {}).get('success'):
            content = results['query'].get('content', '')
            sections.append(f"### Query å¼æï¼ç½ç»æç´¢ï¼\n{content[:3000]}\n")
        elif results.get('query', {}).get('error'):
            sections.append(f"### Query å¼æï¼ç½ç»æç´¢ï¼\nâ ï¸ æ¥è¯¢å¤±è´¥: {results['query']['error']}\n")

        if results.get('insight', {}).get('success'):
            content = results['insight'].get('content', '')
            sections.append(f"### Insight å¼æï¼æ¬å°èæï¼\n{content[:3000]}\n")
        elif results.get('insight', {}).get('error'):
            sections.append(f"### Insight å¼æï¼æ¬å°èæï¼\nâ ï¸ æ¥è¯¢å¤±è´¥: {results['insight']['error']}\n")

        if results.get('media', {}).get('success'):
            content = results['media'].get('content', '')
            sections.append(f"### Media å¼æï¼å¤åªä½åæï¼\n{content[:3000]}\n")
        elif results.get('media', {}).get('error'):
            sections.append(f"### Media å¼æï¼å¤åªä½åæï¼\nâ ï¸ æ¥è¯¢å¤±è´¥: {results['media']['error']}\n")

        sections.append("""## ç»¼ååæè¦æ±

è¯·ä½ä¸ºå®¢è§åæå©æï¼åºäºä»¥ä¸åå¼æçæ°æ®è¿è¡äº¤åéªè¯åç»¼ååæï¼

1. **äºä»¶æ¢³ç**ï¼æåå³é®äºä»¶ãäººç©ãæ¶é´èç¹ï¼æ´çäºå®èç»
2. **æ°æ®æ´å**ï¼ç»¼åä¸ä¸ªä¿¡æ¯æºï¼æåºå±è¯ä¸åæ­§
3. **ç½®ä¿¡åº¦æ æ³¨**ï¼å¦æåç°ä¿¡æ¯æºä¹é´å­å¨äºå®å²çªï¼æç¡®æ æ³¨ä¸º"ä½ç½®ä¿¡åº¦"å¹¶ä¿çåå§æ¥æº
4. **é²å¹»è§**ï¼å¦æ°æ®ä¸è¶³ï¼ç´æ¥å£°æ"æ°æ®ä¸è¶³ï¼æ æ³åæ"
5. **è¾åºæ ¼å¼**ï¼ä½¿ç¨æ¸æ°çæ é¢ç»æï¼ä¿æå®¢è§ä¸¥è°¨çåææ¥åé£æ ¼
""")

        return "\n".join(sections)


# Factory function for creating ForumAgent instances
def create_forum_agent(session_id: Optional[str] = None) -> ForumAgent:
    """Create a new ForumAgent instance."""
    return ForumAgent(session_id=session_id)
