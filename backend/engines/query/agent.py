# -*- coding: utf-8 -*-
"""
Deep Search Agent - Query Engine
Inherits from BaseHermesAgent for Hermes AIAgent integration.
Searches crawled_data table via LocalDatabaseSearchTool.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.core.base_agent import BaseHermesAgent
from .llms import LLMClient
from .nodes import (
 ReportStructureNode,
 FirstSearchNode,
 ReflectionNode,
 FirstSummaryNode,
 ReflectionSummaryNode,
 ReportFormattingNode
)
from .state import State
from .tools import TavilyResponse, SearchResult
from .utils import Settings, format_search_results_for_prompt
from loguru import logger

QUERY_ENGINE_ROLE_INSTRUCTION = """You are a professional query assistant. Your main responsibilities are:

1. Understand user query intent and construct search queries
2. Use local knowledge base search (keyword_search / vector_search) to retrieve crawled content from crawled_data table
3. Organize search results into structured format for subsequent report generation

Local knowledge base search results contain: platform, content_type, content text, source URL, keyword, timestamp, engagement metrics (liked/collected/commented/shared counts).

When using keyword_search, provide a clear search query string.
When using vector_search, provide a query embedding vector for semantic similarity search.

All data comes from local PostgreSQL database - real crawled social media and news data from multiple platforms.
"""


class DeepSearchAgent(BaseHermesAgent):
 """Deep Search Agent """
 
 def __init__(self, config: Optional[Settings] = None, session_id: Optional[str] = None):
 """
 Initialize Deep Search Agent.

 Args:
 config: Configuration object. If not provided, auto-loaded from settings.
 session_id: Session ID for Hermes AIAgent. Defaults to a generated ID.
 """
 # Load config
 from .utils.config import settings
 self.config = config or settings

 # Session ID for Hermes agent
 self.session_id = session_id or f"query_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

 # Initialize BaseHermesAgent (provides Hermes AIAgent + LocalDatabaseSearchTool)
 super().__init__(
 name="QuerySearchAgent",
 role_instruction=QUERY_ENGINE_ROLE_INSTRUCTION,
 session_id=self.session_id
 )

 # Initialize LLM client
 self.llm_client = self._initialize_llm()

 # Initialize processing nodes
 self._initialize_nodes()

 # State
 self.state = State()

 # Ensure output directory exists
 os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)

 logger.info(f"Query Agent initialized (BaseHermesAgent + Hermes AIAgent)")
 logger.info(f"Using LLM: {self.llm_client.get_model_info()}")
 logger.info(f"Search: LocalDatabaseSearchTool only (crawled_data table)")
 
 def _initialize_llm(self) -> LLMClient:
 """ LLM ?""
 return LLMClient(
 api_key=self.config.QUERY_ENGINE_API_KEY,
 model_name=self.config.QUERY_ENGINE_MODEL_NAME,
 base_url=self.config.QUERY_ENGINE_BASE_URL,
 )
 
 def _initialize_nodes(self):
 """ ?""
 self.first_search_node = FirstSearchNode(self.llm_client)
 self.reflection_node = ReflectionNode(self.llm_client)
 self.first_summary_node = FirstSummaryNode(self.llm_client)
 self.reflection_summary_node = ReflectionSummaryNode(self.llm_client)
 self.report_formatting_node = ReportFormattingNode(self.llm_client)
 
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
 pattern = r'^\d{4}-\d{2}-\d{2}$'
 if not re.match(pattern, date_str):
 return False
 
 # ?
 try:
 datetime.strptime(date_str, '%Y-%m-%d')
 return True
 except ValueError:
 return False
 
 def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> TavilyResponse:
 """
 Execute search via LocalDatabaseSearchTool only.
 All data comes from local crawled_data table (no external API).

 Args:
 tool_name: Tool name. Options:
 - "basic_search_news": Basic news search
 - "deep_search_news": Deep news analysis
 - "search_news_last_24_hours": Latest news within 24 hours
 - "search_news_last_week": This week's news
 - "search_images_for_news": News image search
 - "search_news_by_date": Date range news search
 query: Search query
 **kwargs: Extra params (e.g. start_date, end_date, max_results)

 Returns:
 TavilyResponse object (compatible with existing pipeline)
 """
 logger.info(f" -> Executing search tool: {tool_name} (local only)")

 max_results = kwargs.get("max_results", 7) if tool_name == "basic_search_news" else 10
 return self._search_local_crawled_data(query, max_results)

 def _search_local_crawled_data(self, query: str, limit: int = 10) -> TavilyResponse:
 """
 Search local crawled_data table via LocalDatabaseSearchTool.
 Returns results in TavilyResponse format for pipeline compatibility.
 """
 try:
 raw = self.db_tool.keyword_search(query, limit)
 data = json.loads(raw)

 results = []
 for row in data.get("results", []):
 results.append(SearchResult(
 title=f"[{row.get('platform', 'unknown').upper()}] {row.get('content', '')[:50]}",
 url=row.get('source_url', ''),
 content=row.get('content', ''),
 score=None,
 raw_content=json.dumps(row, ensure_ascii=False),
 published_date=str(row.get('create_time', '')) if row.get('create_time') else None
 ))

 return TavilyResponse(
 query=query,
 answer=None,
 results=results,
 images=[],
 response_time=0.1
 )
 except Exception as e:
 logger.warning(f" Local DB search failed: {e}")
 return TavilyResponse(query=query, results=[], images=[])

 def _tavily_fallback(self, tool_name: str, query: str, **kwargs) -> TavilyResponse:
 """Fall back to TavilyNewsAgency for external search."""
 if tool_name == "basic_search_news":
 max_results = kwargs.get("max_results", 7)
 return self.search_agency.basic_search_news(query, max_results)
 elif tool_name == "deep_search_news":
 return self.search_agency.deep_search_news(query)
 elif tool_name == "search_news_last_24_hours":
 return self.search_agency.search_news_last_24_hours(query)
 elif tool_name == "search_news_last_week":
 return self.search_agency.search_news_last_week(query)
 elif tool_name == "search_images_for_news":
 return self.search_agency.search_images_for_news(query)
 elif tool_name == "search_news_by_date":
 start_date = kwargs.get("start_date")
 end_date = kwargs.get("end_date")
 if not start_date or not end_date:
 raise ValueError("search_news_by_date tool requires start_date and end_date params")
 return self.search_agency.search_news_by_date(query, start_date, end_date)
 else:
 logger.warning(f" Unknown search tool {tool_name}, using basic search")
 return self.search_agency.basic_search_news(query)
 
 def research(self, query: str, save_report: bool = True) -> str:
 """
 深度 究
 
 Args:
 query: 究 询
 save_report: ?
 
 Returns:
 ?
 """
 logger.info(f"\n{'='*60}")
 logger.info(f" 深度 ? {query}")
 logger.info(f"{'='*60}")
 
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
 
 logger.info(f"\n{'='*60}")
 logger.info("深度 究 ?)
 logger.info(f"{'='*60}")
 
 return final_report
 
 except Exception as e:
 import traceback
 error_traceback = traceback.format_exc()
 logger.error(f" 究 中 ? {str(e)} \n 误 : {error_traceback}")
 raise e
 
 def _generate_report_structure(self, query: str):
 """ """
 logger.info(f"\n[步骤 1] ...")

 # ?
 seed_context = ""
 if hasattr(self.state, 'seed_id') and self.state.seed_id:
 try:
 import os
 from pathlib import Path
 root_dir = Path(__file__).parent.parent
 seed_path = root_dir / 'output' / 'seeds' / f"{self.state.seed_id}.txt"
 if seed_path.exists():
 seed_context = seed_path.read_text(encoding='utf-8')
 logger.info(f"读 件 容 度: {len(seed_context)}")
 except Exception as e:
 logger.warning(f"读 件失败: {e}")

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
 logger.info(f"\n[步骤 2.{i+1}] 段 : {self.state.paragraphs[i].title}")
 logger.info("-" * 50)
 
 # 
 self._initial_search_and_summary(i)
 
 # ?
 self._reflection_loop(i)
 
 # 
 self.state.paragraphs[i].research.mark_completed()
 
 progress = (i + 1) / total_paragraphs * 100
 logger.info(f"段 ({progress:.1f}%)")
 
 def _initial_search_and_summary(self, paragraph_index: int):
 """ """
 paragraph = self.state.paragraphs[paragraph_index]
 
 # 
 search_input = {
 "title": paragraph.title,
 "content": paragraph.content
 }
 
 # 
 logger.info(" - 索 询...")
 search_output = self.first_search_node.run(search_input)
 search_query = search_output["search_query"]
 search_tool = search_output.get("search_tool", "basic_search_news") # 认工 
 reasoning = search_output["reasoning"]
 
 logger.info(f" - 索 询: {search_query}")
 logger.info(f" - 工 ? {search_tool}")
 logger.info(f" - : {reasoning}")
 
 # 
 logger.info(" - 索...")
 
 # search_news_by_date ?
 search_kwargs = {}
 if search_tool == "search_news_by_date":
 start_date = search_output.get("start_date")
 end_date = search_output.get("end_date")
 
 if start_date and end_date:
 # 
 if self._validate_date_format(start_date) and self._validate_date_format(end_date):
 search_kwargs["start_date"] = start_date
 search_kwargs["end_date"] = end_date
 logger.info(f" - : {start_date} ?{end_date}")
 else:
 logger.info(f" 格 误 为YYYY-MM-DD 索")
 logger.info(f" ? start_date={start_date}, end_date={end_date}")
 search_tool = "basic_search_news"
 else:
 logger.info(f" search_news_by_date工 缺 索")
 search_tool = "basic_search_news"
 
 search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
 
 # ?
 search_results = []
 if search_response and search_response.results:
 # ?0 ?
 max_results = min(len(search_response.results), 10)
 for result in search_response.results[:max_results]:
 search_results.append({
 'title': result.title,
 'url': result.url,
 'content': result.content,
 'score': result.score,
 'raw_content': result.raw_content,
 'published_date': result.published_date # 段
 })
 
 if search_results:
 _message = f" - {len(search_results)} 个 索 ?
 for j, result in enumerate(search_results, 1):
 date_info = f" ( ? {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
 _message += f"\n {j}. {result['title'][:50]}...{date_info}"
 logger.info(_message)
 else:
 logger.info(" - 索 ?)
 # ?
 paragraph.research.add_search_results(search_query, search_results)
 
 # 
 logger.info(" - ...")
 summary_input = {
 "title": paragraph.title,
 "content": paragraph.content,
 "search_query": search_query,
 "search_results": format_search_results_for_prompt(
 search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
 )
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
 "title": paragraph.title,
 "content": paragraph.content,
 "paragraph_latest_state": paragraph.research.latest_summary
 }
 
 # ?
 reflection_output = self.reflection_node.run(reflection_input)
 search_query = reflection_output["search_query"]
 search_tool = reflection_output.get("search_tool", "basic_search_news") # 认工 
 reasoning = reflection_output["reasoning"]
 
 logger.info(f" ? {search_query}")
 logger.info(f" 工 ? {search_tool}")
 logger.info(f" ? {reasoning}")
 
 # ?
 # search_news_by_date ?
 search_kwargs = {}
 if search_tool == "search_news_by_date":
 start_date = reflection_output.get("start_date")
 end_date = reflection_output.get("end_date")
 
 if start_date and end_date:
 # 
 if self._validate_date_format(start_date) and self._validate_date_format(end_date):
 search_kwargs["start_date"] = start_date
 search_kwargs["end_date"] = end_date
 logger.info(f" : {start_date} ?{end_date}")
 else:
 logger.info(f" 格 误 为YYYY-MM-DD 索")
 logger.info(f" ? start_date={start_date}, end_date={end_date}")
 search_tool = "basic_search_news"
 else:
 logger.info(f" search_news_by_date工 缺 索")
 search_tool = "basic_search_news"
 
 search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
 
 # ?
 search_results = []
 if search_response and search_response.results:
 # ?0 ?
 max_results = min(len(search_response.results), 10)
 for result in search_response.results[:max_results]:
 search_results.append({
 'title': result.title,
 'url': result.url,
 'content': result.content,
 'score': result.score,
 'raw_content': result.raw_content,
 'published_date': result.published_date
 })
 
 if search_results:
 logger.info(f" {len(search_results)} 个 索 ?)
 for j, result in enumerate(search_results, 1):
 date_info = f" ( ? {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
 logger.info(f" {j}. {result['title'][:50]}...{date_info}")
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
 search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
 ),
 "paragraph_latest_state": paragraph.research.latest_summary
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
 report_data.append({
 "title": paragraph.title,
 "paragraph_latest_state": paragraph.research.latest_summary
 })
 
 # ?
 try:
 final_report = self.report_formatting_node.run(report_data)
 except Exception as e:
 logger.error(f"LLM格 失败 使 : {str(e)}")
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
 query_safe = "".join(c for c in self.state.query if c.isalnum() or c in (' ', '-', '_')).rstrip()
 query_safe = query_safe.replace(' ', '_')[:30]
 
 # ?task_id 
 task_id = self.state.task_id if getattr(self.state, 'task_id', '') else datetime.now().strftime("%Y%m%d_%H%M%S")
 
 filename = f"deep_search_report_{query_safe}_{task_id}.md"
 filepath = os.path.join(self.config.OUTPUT_DIR, filename)
 
 # 
 with open(filepath, 'w', encoding='utf-8') as f:
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


def create_agent() -> DeepSearchAgent:
 """
 建Deep Search Agent 便 ?
 
 Returns:
 DeepSearchAgent 
 """
 from .utils.config import Settings
 config = Settings()
 return DeepSearchAgent(config)
