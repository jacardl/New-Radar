# -*- coding: utf-8 -*-
"""
Deep Search Agent - Media Engine
Inherits from BaseHermesAgent for Hermes AIAgent integration.
Searches crawled_data table via LocalDatabaseSearchTool.
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from loguru import logger
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
from .tools import BochaResponse, WebpageResult
from .utils import settings, Settings, format_search_results_for_prompt

MEDIA_ENGINE_ROLE_INSTRUCTION = """You are a professional multimedia content analysis assistant. Your responsibilities are:

1. Search the local knowledge base for multimedia content (videos, images, text+image posts)
2. Use keyword_search and vector_search for cross-platform content retrieval from crawled_data table
3. Evaluate content dissemination scope and influence
4. Identify content source platform and creator information

All data comes from local PostgreSQL crawled_data table.

Local database search results include: platform, content_type, content text, source_url, keyword, timestamp, engagement metrics (liked_count, collected_count, comment_count, share_count), ip_location, user_id, nickname.
"""


class DeepSearchAgent(BaseHermesAgent):
    """Deep Search Agent for Media Engine"""

    def __init__(self, config: Optional[Settings] = None, session_id: Optional[str] = None):
        """
        Initialize Deep Search Agent.

        Args:
            config: Configuration object. Auto-loaded if not provided.
            session_id: Session ID for Hermes AIAgent.
        """
        self.config = config or settings
        self.session_id = session_id or f"media_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Initialize BaseHermesAgent (Hermes AIAgent + LocalDatabaseSearchTool)
        super().__init__(
            name="MediaSearchAgent",
            role_instruction=MEDIA_ENGINE_ROLE_INSTRUCTION,
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

        logger.info(f"Media Agent initialized (BaseHermesAgent + Hermes AIAgent)")
        logger.info(f"Using LLM: {self.llm_client.get_model_info()}")
        logger.info(f"Search: LocalDatabaseSearchTool only (crawled_data table)")
    
    def _initialize_llm(self) -> LLMClient:
        """初始化LLM客户�?""
        return LLMClient(
            api_key=(self.config.MEDIA_ENGINE_API_KEY or self.config.MINDSPIDER_API_KEY),
            model_name=(self.config.MEDIA_ENGINE_MODEL_NAME or self.config.MINDSPIDER_MODEL_NAME),
            base_url=(self.config.MEDIA_ENGINE_BASE_URL or self.config.MINDSPIDER_BASE_URL),
        )
    
    def _initialize_nodes(self):
        """初始化处理节�?""
        self.first_search_node = FirstSearchNode(self.llm_client)
        self.reflection_node = ReflectionNode(self.llm_client)
        self.first_summary_node = FirstSummaryNode(self.llm_client)
        self.reflection_summary_node = ReflectionSummaryNode(self.llm_client)
        self.report_formatting_node = ReportFormattingNode(self.llm_client)
    
    def _validate_date_format(self, date_str: str) -> bool:
        """
        验证日期格式是否为YYYY-MM-DD
        
        Args:
            date_str: 日期字符�?
            
        Returns:
            是否为有效格�?
        """
        if not date_str:
            return False
        
        # 检查格�?
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, date_str):
            return False
        
        # 检查日期是否有�?
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> BochaResponse:
        """
        Execute search via LocalDatabaseSearchTool only (no external API).
        All data comes from local crawled_data table.

        Args:
            tool_name: Tool name. Options:
                - "comprehensive_search": Comprehensive search (default)
                - "web_search_only": Web search only
                - "search_for_structured_data": Structured data search
                - "search_last_24_hours": Latest 24h info
                - "search_last_week": This week info
            query: Search query
            **kwargs: Extra params (e.g. max_results)

        Returns:
            BochaResponse object
        """
        logger.info(f"  -> Executing search tool: {tool_name} (local only)")

        max_results = kwargs.get("max_results", 10)
        return self._search_local_crawled_data(query, max_results)

    def _search_local_crawled_data(self, query: str, limit: int = 10) -> BochaResponse:
        """
        Search local crawled_data table via LocalDatabaseSearchTool.
        Returns results in BochaResponse format for pipeline compatibility.
        """
        try:
            raw = self.db_tool.keyword_search(query, limit)
            data = json.loads(raw)

            webpages = []
            for row in data.get("results", []):
                webpages.append(WebpageResult(
                    name=f"[{row.get('platform', 'unknown').upper()}] {row.get('content', '')[:50]}",
                    url=row.get('source_url', ''),
                    snippet=row.get('content', '')[:200],
                    display_url=row.get('source_url', ''),
                ))

            return BochaResponse(
                query=query,
                webpages=webpages,
                images=[],
            )
        except Exception as e:
            logger.warning(f"  Local DB search failed: {e}")
            return BochaResponse(query=query, webpages=[], images=[])

    def _bocha_fallback(self, tool_name: str, query: str, **kwargs) -> BochaResponse:
        """Fall back to BochaMultimodalSearch for external search."""
        if tool_name == "comprehensive_search":
            max_results = kwargs.get("max_results", 10)
            return self.search_agency.comprehensive_search(query, max_results)
        elif tool_name == "web_search_only":
            max_results = kwargs.get("max_results", 15)
            return self.search_agency.web_search_only(query, max_results)
        elif tool_name == "search_for_structured_data":
            return self.search_agency.search_for_structured_data(query)
        elif tool_name == "search_last_24_hours":
            return self.search_agency.search_last_24_hours(query)
        elif tool_name == "search_last_week":
            return self.search_agency.search_last_week(query)
        else:
            logger.info(f"  Unknown search tool {tool_name}, using default comprehensive search")
            return self.search_agency.comprehensive_search(query)
    
    def research(self, query: str, save_report: bool = True) -> str:
        """
        执行深度研究
        
        Args:
            query: 研究查询
            save_report: 是否保存报告到文�?
            
        Returns:
            最终报告内�?
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"开始深度研�? {query}")
        logger.info(f"{'='*60}")
        
        try:
            # Step 1: 生成报告结构
            self._generate_report_structure(query)
            
            # Step 2: 处理每个段落
            self._process_paragraphs()
            
            # Step 3: 生成最终报�?
            final_report = self._generate_final_report()
            
            # Step 4: 保存报告
            if save_report:
                self._save_report(final_report)
            
            logger.info(f"\n{'='*60}")
            logger.info("深度研究完成�?)
            logger.info(f"{'='*60}")
            
            return final_report
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"研究过程中发生错�? {str(e)} \n错误堆栈: {error_traceback}")
            raise e
    
    def _generate_report_structure(self, query: str):
        """生成报告结构"""
        logger.info(f"\n[步骤 1] 生成报告结构...")

        # 提取种子文件（如果有�?
        seed_context = ""
        if hasattr(self.state, 'seed_id') and self.state.seed_id:
            try:
                import os
                from pathlib import Path
                root_dir = Path(__file__).parent.parent
                seed_path = root_dir / 'output' / 'seeds' / f"{self.state.seed_id}.txt"
                if seed_path.exists():
                    seed_context = seed_path.read_text(encoding='utf-8')
                    logger.info(f"读取到种子文件内容，长度: {len(seed_context)}")
            except Exception as e:
                logger.warning(f"读取种子文件失败: {e}")

        # 增强 query
        if seed_context:
            enhanced_query = f"{query}\n\n==========================\n【用户上传的参考资�?种子文件（请作为高优先级事实分析参考）�?\n{seed_context[:10000]}\n=========================="
            self.state.query = enhanced_query
            query = enhanced_query

        # 创建报告结构节点
        report_structure_node = ReportStructureNode(self.llm_client, query)
        
        # 生成结构并更新状�?
        self.state = report_structure_node.mutate_state(state=self.state)
        
        _message = f"报告结构已生成，�?{len(self.state.paragraphs)} 个段�?"
        for i, paragraph in enumerate(self.state.paragraphs, 1):
            _message += f"\n  {i}. {paragraph.title}"
        logger.info(_message)
    
    def _process_paragraphs(self):
        """处理所有段�?""
        total_paragraphs = len(self.state.paragraphs)
        
        for i in range(total_paragraphs):
            logger.info(f"\n[步骤 2.{i+1}] 处理段落: {self.state.paragraphs[i].title}")
            logger.info("-" * 50)
            
            # 初始搜索和总结
            self._initial_search_and_summary(i)
            
            # 反思循�?
            self._reflection_loop(i)
            
            # 标记段落完成
            self.state.paragraphs[i].research.mark_completed()
            
            progress = (i + 1) / total_paragraphs * 100
            logger.info(f"段落处理完成 ({progress:.1f}%)")
    
    def _initial_search_and_summary(self, paragraph_index: int):
        """执行初始搜索和总结"""
        paragraph = self.state.paragraphs[paragraph_index]
        
        # 准备搜索输入
        search_input = {
            "title": paragraph.title,
            "content": paragraph.content
        }
        
        # 生成搜索查询和工具选择
        logger.info("  - 生成搜索查询...")
        search_output = self.first_search_node.run(search_input)
        search_query = search_output["search_query"]
        search_tool = search_output.get("search_tool", "comprehensive_search")  # 默认工具
        reasoning = search_output["reasoning"]
        
        logger.info(f"  - 搜索查询: {search_query}")
        logger.info(f"  - 选择的工�? {search_tool}")
        logger.info(f"  - 推理: {reasoning}")
        
        # 执行搜索
        logger.info("  - 执行网络搜索...")
        
        # 处理特殊参数（新的工具集不需要日期参数处理）
        search_kwargs = {}
        if search_tool in ["comprehensive_search", "web_search_only"]:
            # 这些工具支持max_results参数
            search_kwargs["max_results"] = 10
        
        search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
        
        # 转换为兼容格�?
        search_results = []
        if search_response and search_response.webpages:
            # 每种搜索工具都有其特定的结果数量，这里取�?0个作为上�?
            max_results = min(len(search_response.webpages), 10)
            for result in search_response.webpages[:max_results]:
                search_results.append({
                    'title': result.name,
                    'url': result.url,
                    'content': result.snippet,
                    'score': None,  # Bocha API不提供score
                    'raw_content': result.snippet,
                    'published_date': result.date_last_crawled  # 使用爬取日期
                })
        
        if search_results:
            _message = f"  - 找到 {len(search_results)} 个搜索结�? 
            for j, result in enumerate(search_results, 1):
                date_info = f" (发布�? {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
                _message += f"\n    {j}. {result['title'][:50]}...{date_info}"
            logger.info(_message)
        else:
            logger.info("  - 未找到搜索结�?)
        
        # 更新状态中的搜索历�?
        paragraph.research.add_search_results(
            search_query,
            search_results,
            search_tool=search_tool,
            paragraph_title=paragraph.title,
        )
        
        # 生成初始总结
        logger.info("  - 生成初始总结...")
        summary_input = {
            "title": paragraph.title,
            "content": paragraph.content,
            "search_query": search_query,
            "search_results": format_search_results_for_prompt(
                search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
            )
        }
        
        # 更新状�?
        self.state = self.first_summary_node.mutate_state(
            summary_input, self.state, paragraph_index
        )
        
        logger.info("  - 初始总结完成")
    
    def _reflection_loop(self, paragraph_index: int):
        """执行反思循�?""
        paragraph = self.state.paragraphs[paragraph_index]
        
        for reflection_i in range(self.config.MAX_REFLECTIONS):
            logger.info(f"  - 反�?{reflection_i + 1}/{self.config.MAX_REFLECTIONS}...")
            
            # 准备反思输�?
            reflection_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "paragraph_latest_state": paragraph.research.latest_summary
            }
            
            # 生成反思搜索查�?
            reflection_output = self.reflection_node.run(reflection_input)
            search_query = reflection_output["search_query"]
            search_tool = reflection_output.get("search_tool", "comprehensive_search")  # 默认工具
            reasoning = reflection_output["reasoning"]
            
            logger.info(f"    反思查�? {search_query}")
            logger.info(f"    选择的工�? {search_tool}")
            logger.info(f"    反思推�? {reasoning}")
            
            # 执行反思搜�?
            # 处理特殊参数
            search_kwargs = {}
            if search_tool in ["comprehensive_search", "web_search_only"]:
                # 这些工具支持max_results参数
                search_kwargs["max_results"] = 10
            
            search_response = self.execute_search_tool(search_tool, search_query, **search_kwargs)
            
            # 转换为兼容格�?
            search_results = []
            if search_response and search_response.webpages:
                # 每种搜索工具都有其特定的结果数量，这里取�?0个作为上�?
                max_results = min(len(search_response.webpages), 10)
                for result in search_response.webpages[:max_results]:
                    search_results.append({
                        'title': result.name,
                        'url': result.url,
                        'content': result.snippet,
                        'score': None,  # Bocha API不提供score
                        'raw_content': result.snippet,
                        'published_date': result.date_last_crawled
                    })
            
            if search_results:
                _message = f"    找到 {len(search_results)} 个反思搜索结�?
                for j, result in enumerate(search_results, 1):
                    date_info = f" (发布�? {result.get('published_date', 'N/A')})" if result.get('published_date') else ""
                    _message += f"\n      {j}. {result['title'][:50]}...{date_info}"
                logger.info(_message)
            else:
                logger.info("    未找到反思搜索结�?)
            
            # 更新搜索历史
            paragraph.research.add_search_results(
                search_query,
                search_results,
                search_tool=search_tool,
                paragraph_title=paragraph.title,
            )
            
            # 生成反思总结
            reflection_summary_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "search_query": search_query,
                "search_results": format_search_results_for_prompt(
                    search_results, self.config.SEARCH_CONTENT_MAX_LENGTH
                ),
                "paragraph_latest_state": paragraph.research.latest_summary
            }
            
            # 更新状�?
            self.state = self.reflection_summary_node.mutate_state(
                reflection_summary_input, self.state, paragraph_index
            )
            
            logger.info(f"    反�?{reflection_i + 1} 完成")
    
    def _generate_final_report(self) -> str:
        """生成最终报�?""
        logger.info(f"\n[步骤 3] 生成最终报�?..")
        
        # 准备报告数据
        report_data = []
        for paragraph in self.state.paragraphs:
            report_data.append({
                "title": paragraph.title,
                "paragraph_latest_state": paragraph.research.latest_summary
            })
        
        # 格式化报�?
        try:
            final_report = self.report_formatting_node.run(report_data)
        except Exception as e:
            logger.info(f"LLM格式化失败，使用备用方法: {str(e)}")
            final_report = self.report_formatting_node.format_report_manually(
                report_data, self.state.report_title
            )
        
        # 更新状�?
        self.state.final_report = final_report
        self.state.mark_completed()
        
        logger.info("最终报告生成完�?)
        return final_report
    
    def _save_report(self, report_content: str):
        """保存报告到文�?""
        # 生成文件�?
        query_safe = "".join(c for c in self.state.query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        query_safe = query_safe.replace(' ', '_')[:30]
        
        # 使用统一�?task_id 如果存在，否则使用时间戳
        task_id = self.state.task_id if getattr(self.state, 'task_id', '') else datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = f"deep_search_report_{query_safe}_{task_id}.md"
        filepath = os.path.join(self.config.OUTPUT_DIR, filename)
        
        # 保存报告
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        logger.info(f"报告已保存到: {filepath}")
        
        # 保存状态（如果配置允许�?
        if self.config.SAVE_INTERMEDIATE_STATES:
            state_filename = f"state_{query_safe}_{task_id}.json"
            state_filepath = os.path.join(self.config.OUTPUT_DIR, state_filename)
            self.state.save_to_file(state_filepath)
            logger.info(f"状态已保存�? {state_filepath}")
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return self.state.get_progress_summary()
    
    def load_state(self, filepath: str):
        """从文件加载状�?""
        self.state = State.load_from_file(filepath)
        logger.info(f"状态已�?{filepath} 加载")
    
    def save_state(self, filepath: str):
        """保存状态到文件"""
        self.state.save_to_file(filepath)
        logger.info(f"状态已保存�?{filepath}")

class AnspireSearchAgent(DeepSearchAgent):
    """Deep Search Agent using Anspire search engine"""

    def __init__(self, config: Settings | None = None, session_id: Optional[str] = None):
        self.config = config or settings
        self.session_id = session_id or f"anspire_engine_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Initialize BaseHermesAgent
        super().__init__(
            name="AnspireSearchAgent",
            role_instruction=MEDIA_ENGINE_ROLE_INSTRUCTION,
            session_id=self.session_id
        )

        # Initialize LLM client
        self.llm_client = self._initialize_llm()

        # Initialize search agency (Anspire fallback)
        self.search_agency = AnspireAISearch(api_key=self.config.ANSPIRE_API_KEY)

        # Initialize processing nodes
        self._initialize_nodes()

        # State
        self.state = State()

        # Ensure output directory exists
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)

        logger.info(f"AnspireSearchAgent initialized (BaseHermesAgent + Hermes AIAgent)")
        logger.info(f"Using LLM: {self.llm_client.get_model_info()}")
        logger.info(f"Primary search: LocalDatabaseSearchTool (crawled_data table)")
        logger.info(f"Fallback search: AnspireAISearch")

    def execute_search_tool(self, tool_name: str, query: str, **kwargs) -> AnspireResponse:
        """
        Execute search using Anspire. Primary: LocalDatabaseSearchTool, Fallback: Anspire.

        Args:
            tool_name: Tool name.
            query: Search query.
            **kwargs: Extra params.

        Returns:
            AnspireResponse object
        """
        logger.info(f"  -> Executing Anspire search tool: {tool_name}")

        # Try local crawled_data first
        max_results = kwargs.get("max_results", 10)
        local_response = self._search_local_crawled_data(query, max_results)

        if local_response.webpages:
            logger.info(f"  -> Local DB returned {len(local_response.webpages)} results (primary)")
            # Convert BochaResponse to AnspireResponse format if needed
            return local_response  # type: ignore
        else:
            logger.info(f"  -> Local DB returned no results, falling back to Anspire")
            if tool_name == "comprehensive_search":
                max_results = kwargs.get("max_results", 10)
                return self.search_agency.comprehensive_search(query, max_results)
            elif tool_name == "search_last_24_hours":
                return self.search_agency.search_last_24_hours(query)
            elif tool_name == "search_last_week":
                return self.search_agency.search_last_week(query)
            else:
                logger.info(f"  Unknown tool {tool_name}, using default")
                return self.search_agency.comprehensive_search(query)


def create_agent(config_file: Optional[str] = None) -> DeepSearchAgent:
    """
    创建Deep Search Agent实例的便捷函�?
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        DeepSearchAgent实例
    """
    settings = Settings()
    if settings.SEARCH_TOOL_TYPE == "AnspireAPI":
        return AnspireSearchAgent(settings)
    return DeepSearchAgent(settings)
