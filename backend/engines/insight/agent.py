# -*- coding: utf-8 -*-
"""
Deep Search Agent - Insight Engine
Inherits from BaseHermesAgent for Hermes AIAgent integration.
Searches crawled_data table via LocalDatabaseSearchTool.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans

from backend.core.base_agent import BaseHermesAgent
from .llms import LLMClient
from .nodes import (
 FirstSearchNode,
 FirstSummaryNode,
 ReflectionNode,
 ReflectionSummaryNode,
 ReportFormattingNode,
 ReportStructureNode,
)
from .state import State
from .tools import (
 DBResponse,
 QueryResult,
 keyword_optimizer,
 multilingual_sentiment_analyzer,
)
from .utils import format_search_results_for_prompt
from .utils.config import Settings, settings

ENABLE_CLUSTERING: bool = False # Clustering disabled; API returns high-quality sorted results
MAX_CLUSTERED_RESULTS: int = 50
RESULTS_PER_CLUSTER: int = 5

INSIGHT_ENGINE_ROLE_INSTRUCTION = """You are a professional opinion analysis assistant. Your responsibilities are:

1. Understand topic/theme and search the local knowledge base for relevant crawled content
2. Use keyword_search and vector_search for semantic retrieval from crawled_data table
3. Analyze sentiment tendency (positive/negative/neutral) of content
4. Calculate engagement metrics (likes, comments, reposts) to evaluate content influence
5. Identify trending content and key dissemination nodes

All data comes from local PostgreSQL crawled_data table.

Local database search results include: platform, content_type, content text, source_url, keyword, timestamp, engagement metrics (liked_count, collected_count, comment_count, share_count), ip_location, user_id, nickname.

For sentiment analysis, feed content text to the analyze_sentiment tool.
For clustering analysis, enable_kmeans=true parameter can be passed to group similar content.
"""


class DeepSearchAgent(BaseHermesAgent):
 """Deep Search Agent for Insight Engine"""

 def __init__(self, config: Optional[Settings] = None, session_id: Optional[str] = None):
 """
 Initialize Deep Search Agent.

 Args:
 config: Optional config object (defaults to global settings).
 session_id: Session ID for Hermes AIAgent.
 """
 self.config = config or settings
 self.session_id = session_id or f"insight_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

 # Initialize BaseHermesAgent (Hermes AIAgent + LocalDatabaseSearchTool)
 super().__init__(
 name="InsightSearchAgent",
 role_instruction=INSIGHT_ENGINE_ROLE_INSTRUCTION,
 session_id=self.session_id
 )

 # Initialize LLM client
 self.llm_client = self._initialize_llm()

 # Initialize clustering model (lazy load)
 self._clustering_model = None

 # Initialize sentiment analyzer
 self.sentiment_analyzer = multilingual_sentiment_analyzer

 # Initialize processing nodes
 self._initialize_nodes()

 # State
 self.state = State()

 # Ensure output directory exists
 os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)

 logger.info(f"Insight Agent initialized (BaseHermesAgent + Hermes AIAgent)")
 logger.info(f"Using LLM: {self.llm_client.get_model_info()}")
 logger.info(f"Search: LocalDatabaseSearchTool only (crawled_data table)")
 logger.info(f"Sentiment analysis: WeiboMultilingualSentiment (22 languages)")

 def _initialize_llm(self) -> LLMClient:
 """Initialize LLM client."""
 return LLMClient(
 api_key=self.config.INSIGHT_ENGINE_API_KEY,
 model_name=self.config.INSIGHT_ENGINE_MODEL_NAME,
 base_url=self.config.INSIGHT_ENGINE_BASE_URL,
 )

 def _initialize_nodes(self):
 """ ?""
 self.first_search_node = FirstSearchNode(self.llm_client)
 self.reflection_node = ReflectionNode(self.llm_client)
 self.first_summary_node = FirstSummaryNode(self.llm_client)
 self.reflection_summary_node = ReflectionSummaryNode(self.llm_client)
 self.report_formatting_node = ReportFormattingNode(self.llm_client)

 def _get_clustering_model(self):
 """ ?""
 if self._clustering_model is None:
 logger.info(" 载 类模 (paraphrase-multilingual-MiniLM-L12-v2)...")
 self._clustering_model = SentenceTransformer(
 "paraphrase-multilingual-MiniLM-L12-v2"
 )
 return self._clustering_model

 def _validate_date_format(self, date_str: str) -> bool:
 """
 格 为YYYY-MM-DD

 Args:
 date_str: 符 ?

 Returns:
 为 格 ?
 """
 if not date_str:
 return False

 # ?
 pattern = r"^\d{4}-\d{2}-\d{2}$"
 if not re.match(pattern, date_str):
 return False

 # ?
 try:
 datetime.strptime(date_str, "%Y-%m-%d")
 return True
 except ValueError:
 return False

 def _cluster_and_sample_results(
 self,
 results: List,
 max_results: int = MAX_CLUSTERED_RESULTS,
 results_per_cluster: int = RESULTS_PER_CLUSTER,
 ) -> List:
 """
 对 索 类并 样

 Args:
 results: 索 表
 max_results: 大 
 results_per_cluster: 个 类 

 Returns:
 样 表
 """
 if len(results) <= max_results:
 return results

 try:
 # 
 texts = [r.title_or_content[:500] for r in results]

 # ?
 model = self._get_clustering_model()
 embeddings = model.encode(texts, show_progress_bar=False)

 # ?
 n_clusters = min(max(2, max_results // results_per_cluster), len(results))

 # KMeans 
 kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
 labels = kmeans.fit_predict(embeddings)

 # ?
 sampled_results = []
 for cluster_id in range(n_clusters):
 cluster_indices = np.flatnonzero(labels == cluster_id)
 cluster_results = [(results[i], i) for i in cluster_indices]
 cluster_results.sort(
 key=lambda x: x[0].hotness_score or 0, reverse=True
 )

 for result, _ in cluster_results[:results_per_cluster]:
 sampled_results.append(result)
 if len(sampled_results) >= max_results:
 break

 if len(sampled_results) >= max_results:
 break

 logger.info(
 f" 类 : {len(results)} ?-> {n_clusters} 个主 ?-> {len(sampled_results)} 代表 ?
 )
 return sampled_results

 except Exception as e:
 logger.warning(f" 类失败 {max_results} ? {str(e)}")
 return results[:max_results]

 def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> DBResponse:
 """
 Execute search via LocalDatabaseSearchTool only (no external API).
 All data comes from local crawled_data table.

 Args:
 tool_name: Tool name. Options:
 - "search_hot_content": Find trending content
 - "search_topic_globally": Global topic search
 - "search_topic_by_date": Date-range topic search
 - "get_comments_for_topic": Get topic comments
 - "search_topic_on_platform": Platform-specific search
 - "analyze_sentiment": Sentiment analysis
 query: Search keyword/topic
 **kwargs: Extra params (e.g. start_date, end_date, platform, limit, enable_sentiment)

 Returns:
 DBResponse object (may include sentiment analysis results)
 """
 logger.info(f" -> Executing database query tool: {tool_name} (local only)")

 # Independent sentiment analysis tool
 if tool_name == "analyze_sentiment":
 texts = kwargs.get("texts", query)
 sentiment_result = self.analyze_sentiment_only(texts)
 return DBResponse(
 tool_name="analyze_sentiment",
 parameters={
 "texts": texts if isinstance(texts, list) else [texts],
 **kwargs,
 },
 results=[],
 results_count=0,
 metadata=sentiment_result,
 )

 # Keyword optimization
 optimized_response = keyword_optimizer.optimize_keywords(
 original_query=query, context=f"using {tool_name} tool for search"
 )

 logger.info(f" Original query: '{query}'")
 logger.info(f" Optimized keywords: {optimized_response.optimized_keywords}")

 # Search local crawled_data for each keyword
 limit = self.config.DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE
 local_all_results = []
 for keyword in optimized_response.optimized_keywords:
 local_resp = self._search_local_crawled_data(keyword, limit)
 if local_resp.results:
 local_all_results.extend(local_resp.results)

 unique_results = self._deduplicate_results(local_all_results) if local_all_results else []
 logger.info(f" Local DB returned {len(unique_results)} unique results")

 if ENABLE_CLUSTERING:
 unique_results = self._cluster_and_sample_results(
 unique_results,
 max_results=MAX_CLUSTERED_RESULTS,
 results_per_cluster=RESULTS_PER_CLUSTER,
 )

 # Build integrated response
 integrated_response = DBResponse(
 tool_name=f"{tool_name}_optimized",
 parameters={
 "original_query": query,
 "optimized_keywords": optimized_response.optimized_keywords,
 "optimization_reasoning": optimized_response.reasoning,
 **kwargs,
 },
 results=unique_results,
 results_count=len(unique_results),
 )

 # Sentiment analysis
 enable_sentiment = kwargs.get("enable_sentiment", True)
 if enable_sentiment and unique_results:
 logger.info(f" Performing sentiment analysis...")
 sentiment_analysis = self._perform_sentiment_analysis(unique_results)
 if sentiment_analysis:
 integrated_response.parameters["sentiment_analysis"] = sentiment_analysis
 logger.info(f" Sentiment analysis complete")

 return integrated_response

 def _deduplicate_results(self, results: List) -> List:
 """
 索 
 """
 seen = set()
 unique_results = []

 for result in results:
 # URL ?
 identifier = result.url if result.url else result.title_or_content[:100]
 if identifier not in seen:
 seen.add(identifier)
 unique_results.append(result)

 return unique_results

 def _search_local_crawled_data(self, query: str, limit: int = 50) -> DBResponse:
 """
 Search local crawled_data table via LocalDatabaseSearchTool.
 Returns results in DBResponse format (with QueryResult objects).
 """
 try:
 raw = self.db_tool.keyword_search(query, limit)
 data = json.loads(raw)

 results = []
 for row in data.get("results", []):
 engagement = {}
 for field_key in ("liked_count", "collected_count", "comment_count", "share_count"):
 val = row.get(field_key)
 if val is not None:
 try:
 engagement[field_key] = int(val)
 except (ValueError, TypeError):
 engagement[field_key] = 0

 results.append(QueryResult(
 platform=row.get('platform', 'unknown'),
 content_type=row.get('content_type', 'content'),
 title_or_content=row.get('content', ''),
 author_nickname=row.get('nickname'),
 url=row.get('source_url'),
 publish_time=datetime.fromtimestamp(row['create_time'] / 1000) if row.get('create_time') else None,
 engagement=engagement,
 source_keyword=row.get('source_keyword'),
 hotness_score=sum(engagement.values()) if engagement else 0.0,
 source_table="crawled_data",
 ))

 return DBResponse(
 tool_name="search_local_crawled_data",
 parameters={"query": query, "limit": limit},
 results=results,
 results_count=len(results),
 )
 except Exception as e:
 logger.warning(f" Local crawled_data search failed: {e}")
 return DBResponse(
 tool_name="search_local_crawled_data",
 parameters={"query": query, "limit": limit},
 results=[],
 results_count=0,
 error_message=str(e),
 )

 def _media_crawler_fallback(self, tool_name: str, query: str, **kwargs) -> DBResponse:
 """Fall back to MediaCrawlerDB for platform-specific searches."""
 optimized_response = keyword_optimizer.optimize_keywords(
 original_query=query, context=f"using {tool_name} tool"
 )
 all_results = []
 for keyword in optimized_response.optimized_keywords:
 try:
 if tool_name == "get_comments_for_topic":
 limit = self.config.DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT // len(
 optimized_response.optimized_keywords
 )
 limit = max(limit, 50)
 response = self.search_agency.get_comments_for_topic(topic=keyword, limit=limit)
 elif tool_name == "search_topic_on_platform":
 platform = kwargs.get("platform")
 start_date = kwargs.get("start_date")
 end_date = kwargs.get("end_date")
 limit = self.config.DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT // len(
 optimized_response.optimized_keywords
 )
 limit = max(limit, 30)
 if not platform:
 logger.warning("search_topic_on_platform missing platform, falling back to global")
 response = self.search_agency.search_topic_globally(topic=keyword, limit_per_table=limit)
 else:
 response = self.search_agency.search_topic_on_platform(
 platform=platform, topic=keyword,
 start_date=start_date, end_date=end_date, limit=limit,
 )
 else:
 response = self.search_agency.search_topic_globally(
 topic=keyword,
 limit_per_table=self.config.DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE,
 )

 if response.results:
 all_results.extend(response.results)
 except Exception as e:
 logger.error(f" MediaCrawlerDB error for '{keyword}': {e}")
 continue

 unique_results = self._deduplicate_results(all_results)
 return DBResponse(
 tool_name=f"{tool_name}_fallback",
 parameters={"original_query": query, "optimized_keywords": optimized_response.optimized_keywords, **kwargs},
 results=unique_results,
 results_count=len(unique_results),
 )

 def _perform_sentiment_analysis(self, results: List) -> Optional[Dict[str, Any]]:
 """
 对 索 ?

 Args:
 results: 索 表

 Returns:
 失败 None
 """
 try:
 # 
 if (
 not self.sentiment_analyzer.is_initialized
 and not self.sentiment_analyzer.is_disabled
 ):
 logger.info(" 模 ?..")
 if not self.sentiment_analyzer.initialize():
 logger.info(" 模 失败 传 ")
 elif self.sentiment_analyzer.is_disabled:
 logger.info(" 已 传 ")

 # 
 results_dict = []
 for result in results:
 result_dict = {
 "content": result.title_or_content,
 "platform": result.platform,
 "author": result.author_nickname,
 "url": result.url,
 "publish_time": str(result.publish_time)
 if result.publish_time
 else None,
 }
 results_dict.append(result_dict)

 # 
 sentiment_analysis = self.sentiment_analyzer.analyze_query_results(
 query_results=results_dict, text_field="content", min_confidence=0.5
 )

 return sentiment_analysis.get("sentiment_analysis")

 except Exception as e:
 logger.exception(f" ? 中 ? {str(e)}")
 return None

 def analyze_sentiment_only(self, texts: Union[str, List[str]]) -> Dict[str, Any]:
 """
 工 ?

 Args:
 texts: 个 ?

 Returns:
 
 """
 logger.info(f" ? ")

 try:
 # 
 if (
 not self.sentiment_analyzer.is_initialized
 and not self.sentiment_analyzer.is_disabled
 ):
 logger.info(" 模 ?..")
 if not self.sentiment_analyzer.initialize():
 logger.info(" 模 失败 传 ")
 elif self.sentiment_analyzer.is_disabled:
 logger.warning(" 已 传 ")

 # 
 if isinstance(texts, str):
 result = self.sentiment_analyzer.analyze_single_text(texts)
 result_dict = result.__dict__
 response = {
 "success": result.success and result.analysis_performed,
 "total_analyzed": 1
 if result.analysis_performed and result.success
 else 0,
 "results": [result_dict],
 }
 if not result.analysis_performed:
 response["success"] = False
 response["warning"] = (
 result.error_message or " 已 ?
 )
 return response
 else:
 texts_list = list(texts)
 batch_result = self.sentiment_analyzer.analyze_batch(
 texts_list, show_progress=True
 )
 response = {
 "success": batch_result.analysis_performed
 and batch_result.success_count > 0,
 "total_analyzed": batch_result.total_processed
 if batch_result.analysis_performed
 else 0,
 "success_count": batch_result.success_count,
 "failed_count": batch_result.failed_count,
 "average_confidence": batch_result.average_confidence
 if batch_result.analysis_performed
 else 0.0,
 "results": [result.__dict__ for result in batch_result.results],
 }
 if not batch_result.analysis_performed:
 warning = next(
 (
 r.error_message
 for r in batch_result.results
 if r.error_message
 ),
 " 已 ?,
 )
 response["success"] = False
 response["warning"] = warning
 return response

 except Exception as e:
 logger.exception(f" ? 中 ? {str(e)}")
 return {"success": False, "error": str(e), "results": []}

 def research(self, query: str, save_report: bool = True) -> str:
 """
 深度 究

 Args:
 query: 究 询
 save_report: ?

 Returns:
 ?
 """
 logger.info(f"\n{'=' * 60}")
 logger.info(f" 深度 ? {query}")
 logger.info(f"{'=' * 60}")

 try:
 # Step 1: 
 self._generate_report_structure(query)

 # Step 2: 
 self._process_paragraphs()

 # Step 3: ?
 final_report = self._generate_final_report()

 # Step 4: 
 if save_report:
 self._save_report(final_report)

 logger.info("深度 究 ?)

 return final_report

 except Exception as e:
 logger.exception(f" 究 中 ? {str(e)}")
 raise e

 def _generate_report_structure(self, query: str):
 """ """
 logger.info(f"\n[步骤 1] ...")

 # ?
 seed_context = ""
 seed_data_dict = {}
 if hasattr(self.state, 'seed_id') and self.state.seed_id:
 try:
 import os
 from pathlib import Path
 # output ?
 root_dir = Path(__file__).parent.parent
 seed_path_json = root_dir / 'output' / 'seeds' / f"{self.state.seed_id}.json"
 seed_path_txt = root_dir / 'output' / 'seeds' / f"{self.state.seed_id}.txt"
 if seed_path_json.exists():
 import json
 seed_data_dict = json.loads(seed_path_json.read_text(encoding='utf-8'))
 seed_context = seed_data_dict.get('text', '')
 logger.info(f"读 ?JSON) 容 ? {len(seed_context)}")
 elif seed_path_txt.exists():
 seed_context = seed_path_txt.read_text(encoding='utf-8')
 seed_data_dict = {
 "text": seed_context,
 "filename": " 传 ?,
 "fake_url": f"seed://{self.state.seed_id}/attachment",
 "timestamp": datetime.now().isoformat()
 }
 logger.info(f"读 ?TXT) 容 ? {len(seed_context)}")
 except Exception as e:
 logger.warning(f"读 件失败: {e}")
 
 self._seed_data_dict = seed_data_dict

 # query
 if seed_context:
 enhanced_query = f"{query}\n\n==========================\n 传 ? 件 请 为 级 ?\n{seed_context[:10000]}\n=========================="
 self.state.query = enhanced_query
 query = enhanced_query

 # 
 report_structure_node = ReportStructureNode(self.llm_client, query)

 # ?
 self.state = report_structure_node.mutate_state(state=self.state)

 _message = f" 已 ?{len(self.state.paragraphs)} 个段 ?"
 for i, paragraph in enumerate(self.state.paragraphs, 1):
 _message += f"\n {i}. {paragraph.title}"
 logger.info(_message)

 def _process_paragraphs(self):
 """ ?""
 total_paragraphs = len(self.state.paragraphs)

 for i in range(total_paragraphs):
 logger.info(
 f"\n[步骤 2.{i + 1}] 段 : {self.state.paragraphs[i].title}"
 )
 logger.info("-" * 50)

 # 
 self._initial_search_and_summary(i)

 # ?
 self._reflection_loop(i)

 # 
 self.state.paragraphs[i].research.mark_completed()

 progress = (i + 1) / total_paragraphs * 100
 # 
 if i == total_paragraphs - 1:
 logger.info(f" 段 ?({progress:.1f}%)")

 def _initial_search_and_summary(self, paragraph_index: int):
 """ """
 paragraph = self.state.paragraphs[paragraph_index]

 # 
 search_input = {
 "report_topic": self.state.query,
 "title": paragraph.title,
 "content": paragraph.content
 }

 # 
 logger.info(" - 索 询...")
 search_output = self.first_search_node.run(search_input)
 search_query = search_output["search_query"]
 search_tool = search_output.get(
 "search_tool", "search_topic_globally"
 ) # 认工 
 reasoning = search_output["reasoning"]

 logger.info(f" - 索 询: {search_query}")
 logger.info(f" - 工 ? {search_tool}")
 logger.info(f" - : {reasoning}")

 # 
 logger.info(" - ?..")

 # 
 search_kwargs = {}

 # 
 if search_tool in ["search_topic_by_date", "search_topic_on_platform"]:
 start_date = search_output.get("start_date")
 end_date = search_output.get("end_date")

 if start_date and end_date:
 # 
 if self._validate_date_format(
 start_date
 ) and self._validate_date_format(end_date):
 search_kwargs["start_date"] = start_date
 search_kwargs["end_date"] = end_date
 logger.info(f" - : {start_date} ?{end_date}")
 else:
 logger.info(f" 格 误 为YYYY-MM-DD 索")
 logger.info(
 f" ? start_date={start_date}, end_date={end_date}"
 )
 search_tool = "search_topic_globally"
 elif search_tool == "search_topic_by_date":
 logger.info(f" search_topic_by_date工 缺 索")
 search_tool = "search_topic_globally"

 # 
 if search_tool == "search_topic_on_platform":
 platform = search_output.get("platform")
 if platform:
 search_kwargs["platform"] = platform
 logger.info(f" - 平 : {platform}")
 else:
 logger.warning(
 f" search_topic_on_platform工 缺 平 索"
 )
 search_tool = "search_topic_globally"

 # agent ?
 if search_tool == "search_hot_content":
 time_period = search_output.get("time_period", "week")
 limit = self.config.DEFAULT_SEARCH_HOT_CONTENT_LIMIT
 search_kwargs["time_period"] = time_period
 search_kwargs["limit"] = limit
 elif search_tool in ["search_topic_globally", "search_topic_by_date"]:
 if search_tool == "search_topic_globally":
 limit_per_table = (
 self.config.DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE
 )
 else: # search_topic_by_date
 limit_per_table = (
 self.config.DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE
 )
 search_kwargs["limit_per_table"] = limit_per_table
 elif search_tool in ["get_comments_for_topic", "search_topic_on_platform"]:
 if search_tool == "get_comments_for_topic":
 limit = self.config.DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT
 else: # search_topic_on_platform
 limit = self.config.DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT
 search_kwargs["limit"] = limit

 search_response = self.execute_search_tool(
 search_tool, search_query, **search_kwargs
 )

 # ?
 search_results = []
 if search_response and search_response.results:
 # LLM 0 ?
 if self.config.MAX_SEARCH_RESULTS_FOR_LLM > 0:
 max_results = min(
 len(search_response.results), self.config.MAX_SEARCH_RESULTS_FOR_LLM
 )
 else:
 max_results = len(search_response.results) # 传 ?
 for result in search_response.results[:max_results]:
 search_results.append(
 {
 "title": result.title_or_content,
 "url": result.url or "",
 "content": result.title_or_content,
 "score": result.hotness_score,
 "raw_content": result.title_or_content,
 "published_date": result.publish_time.isoformat()
 if result.publish_time
 else None,
 "platform": result.platform,
 "content_type": result.content_type,
 "author": result.author_nickname,
 "engagement": result.engagement,
 }
 )

 if search_results:
 _message = f" - {len(search_results)} 个 索 ?
 for j, result in enumerate(search_results, 1):
 date_info = (
 f" ( ? {result.get('published_date', 'N/A')})"
 if result.get("published_date")
 else ""
 )
 _message += f"\n {j}. {result['title'][:50]}...{date_info}"
 logger.info(_message)
 else:
 logger.info(" - 索 ?)

 # ?Seed " " ?
 if paragraph_index == 0 and getattr(self, '_seed_data_dict', {}):
 logger.info(" - 注 Seed 件 为 段 ...")
 seed_text = self._seed_data_dict.get('text', '')
 seed_title = self._seed_data_dict.get('filename', ' 传 ?)
 seed_url = self._seed_data_dict.get('fake_url', f"seed://attachment")
 
 # 500-1000 " ?
 seed_chunks = []
 paragraphs = [p.strip() for p in seed_text.split('\n') if p.strip()]
 current_chunk = []
 current_len = 0
 for p in paragraphs:
 current_chunk.append(p)
 current_len += len(p)
 if current_len > 800:
 seed_chunks.append("\n".join(current_chunk))
 current_chunk = []
 current_len = 0
 if current_chunk:
 seed_chunks.append("\n".join(current_chunk))
 
 if not seed_chunks:
 seed_chunks = [seed_text]

 # ?
 seed_results = []
 for i, chunk in enumerate(seed_chunks):
 seed_results.append({
 "title": f" 传 件 {seed_title} ( 段 {i+1}/{len(seed_chunks)})",
 "url": seed_url,
 "content": chunk,
 "score": 100.0,
 "raw_content": chunk,
 "published_date": datetime.now().isoformat(),
 "platform": "seed_file",
 "content_type": "document",
 "author": " 传",
 "engagement": 0,
 })
 
 # ?seed 
 search_results = seed_results + search_results

 # ?
 paragraph.research.add_search_results(search_query, search_results)

 # 
 logger.info(" - ...")
 summary_input = {
 "title": paragraph.title,
 "content": paragraph.content,
 "search_query": search_query,
 "search_results": format_search_results_for_prompt(
 search_results, self.config.MAX_CONTENT_LENGTH
 ),
 }

 # ?
 self.state = self.first_summary_node.mutate_state(
 summary_input, self.state, paragraph_index
 )

 logger.info(" - ")

 def _reflection_loop(self, paragraph_index: int):
 """ ?""
 paragraph = self.state.paragraphs[paragraph_index]

 for reflection_i in range(self.config.MAX_REFLECTIONS):
 logger.info(f" - ?{reflection_i + 1}/{self.config.MAX_REFLECTIONS}...")

 # ?
 reflection_input = {
 "report_topic": self.state.query,
 "title": paragraph.title,
 "content": paragraph.content,
 "paragraph_latest_state": paragraph.research.latest_summary,
 }

 # ?
 reflection_output = self.reflection_node.run(reflection_input)
 search_query = reflection_output["search_query"]
 search_tool = reflection_output.get(
 "search_tool", "search_topic_globally"
 ) # 认工 
 reasoning = reflection_output["reasoning"]

 logger.info(f" ? {search_query}")
 logger.info(f" 工 ? {search_tool}")
 logger.info(f" ? {reasoning}")

 # ?
 # 
 search_kwargs = {}

 # 
 if search_tool in ["search_topic_by_date", "search_topic_on_platform"]:
 start_date = reflection_output.get("start_date")
 end_date = reflection_output.get("end_date")

 if start_date and end_date:
 # 
 if self._validate_date_format(
 start_date
 ) and self._validate_date_format(end_date):
 search_kwargs["start_date"] = start_date
 search_kwargs["end_date"] = end_date
 logger.info(f" : {start_date} ?{end_date}")
 else:
 logger.info(
 f" 格 误 为YYYY-MM-DD 索"
 )
 logger.info(
 f" ? start_date={start_date}, end_date={end_date}"
 )
 search_tool = "search_topic_globally"
 elif search_tool == "search_topic_by_date":
 logger.warning(
 f" search_topic_by_date工 缺 索"
 )
 search_tool = "search_topic_globally"

 # 
 if search_tool == "search_topic_on_platform":
 platform = reflection_output.get("platform")
 if platform:
 search_kwargs["platform"] = platform
 logger.info(f" 平 : {platform}")
 else:
 logger.warning(
 f" search_topic_on_platform工 缺 平 索"
 )
 search_tool = "search_topic_globally"

 # 
 if search_tool == "search_hot_content":
 time_period = reflection_output.get("time_period", "week")
 # agent limit 
 limit = self.config.DEFAULT_SEARCH_HOT_CONTENT_LIMIT
 search_kwargs["time_period"] = time_period
 search_kwargs["limit"] = limit
 elif search_tool in ["search_topic_globally", "search_topic_by_date"]:
 # agent limit_per_table 
 if search_tool == "search_topic_globally":
 limit_per_table = (
 self.config.DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE
 )
 else: # search_topic_by_date
 limit_per_table = (
 self.config.DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE
 )
 search_kwargs["limit_per_table"] = limit_per_table
 elif search_tool in ["get_comments_for_topic", "search_topic_on_platform"]:
 # agent limit 
 if search_tool == "get_comments_for_topic":
 limit = self.config.DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT
 else: # search_topic_on_platform
 limit = self.config.DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT
 search_kwargs["limit"] = limit

 search_response = self.execute_search_tool(
 search_tool, search_query, **search_kwargs
 )

 # ?
 search_results = []
 if search_response and search_response.results:
 # LLM 0 ?
 if self.config.MAX_SEARCH_RESULTS_FOR_LLM > 0:
 max_results = min(
 len(search_response.results),
 self.config.MAX_SEARCH_RESULTS_FOR_LLM,
 )
 else:
 max_results = len(search_response.results) # 传 ?
 for result in search_response.results[:max_results]:
 search_results.append(
 {
 "title": result.title_or_content,
 "url": result.url or "",
 "content": result.title_or_content,
 "score": result.hotness_score,
 "raw_content": result.title_or_content,
 "published_date": result.publish_time.isoformat()
 if result.publish_time
 else None,
 "platform": result.platform,
 "content_type": result.content_type,
 "author": result.author_nickname,
 "engagement": result.engagement,
 }
 )

 if search_results:
 _message = f" {len(search_results)} 个 索 ?
 for j, result in enumerate(search_results, 1):
 date_info = (
 f" ( ? {result.get('published_date', 'N/A')})"
 if result.get("published_date")
 else ""
 )
 _message += f"\n {j}. {result['title'][:50]}...{date_info}"
 logger.info(_message)
 else:
 logger.info(" 索 ?)

 # 
 paragraph.research.add_search_results(search_query, search_results)

 # 
 reflection_summary_input = {
 "title": paragraph.title,
 "content": paragraph.content,
 "search_query": search_query,
 "search_results": format_search_results_for_prompt(
 search_results, self.config.MAX_CONTENT_LENGTH
 ),
 "paragraph_latest_state": paragraph.research.latest_summary,
 }

 # ?
 self.state = self.reflection_summary_node.mutate_state(
 reflection_summary_input, self.state, paragraph_index
 )

 logger.info(f" ?{reflection_i + 1} ")

 def _generate_final_report(self) -> str:
 """ ?""
 logger.info(f"\n[步骤 3] ?..")

 # 
 report_data = []
 for paragraph in self.state.paragraphs:
 report_data.append(
 {
 "title": paragraph.title,
 "paragraph_latest_state": paragraph.research.latest_summary,
 }
 )

 # ?
 try:
 final_report = self.report_formatting_node.run(report_data)
 except Exception as e:
 logger.exception(f"LLM格 失败 使 : {str(e)}")
 final_report = self.report_formatting_node.format_report_manually(
 report_data, self.state.report_title
 )

 # ?
 self.state.final_report = final_report
 self.state.mark_completed()

 logger.info(" ?)
 return final_report

 def _save_report(self, report_content: str):
 """ ?""
 # ?
 query_safe = "".join(
 c for c in self.state.query if c.isalnum() or c in (" ", "-", "_")
 ).rstrip()
 query_safe = query_safe.replace(" ", "_")[:30]

 # ?task_id 
 task_id = self.state.task_id if getattr(self.state, 'task_id', '') else datetime.now().strftime("%Y%m%d_%H%M%S")

 filename = f"deep_search_report_{query_safe}_{task_id}.md"
 filepath = os.path.join(self.config.OUTPUT_DIR, filename)

 # 
 with open(filepath, "w", encoding="utf-8") as f:
 f.write(report_content)

 logger.info(f" 已 : {filepath}")

 # ?
 if self.config.SAVE_INTERMEDIATE_STATES:
 state_filename = f"state_{query_safe}_{task_id}.json"
 state_filepath = os.path.join(self.config.OUTPUT_DIR, state_filename)
 self.state.save_to_file(state_filepath)
 logger.info(f" 已 ? {state_filepath}")

 def get_progress_summary(self) -> Dict[str, Any]:
 """ """
 return self.state.get_progress_summary()

 def load_state(self, filepath: str):
 """ ?""
 self.state = State.load_from_file(filepath)
 logger.info(f" 已 ?{filepath} 载")

 def save_state(self, filepath: str):
 """ """
 self.state.save_to_file(filepath)
 logger.info(f" 已 ?{filepath}")


def create_agent(config_file: Optional[str] = None) -> DeepSearchAgent:
 """
 建Deep Search Agent 便 ?

 Args:
 config_file: 置 件路 

 Returns:
 DeepSearchAgent 
 """
 config = Settings() # 以空 置 
 return DeepSearchAgent(config)
