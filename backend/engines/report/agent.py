"""
Report Agent主类--

该模 串 模 设计 章 IR 订 HTML渲 ?
 Report Engine 度中 核 责 
1. 管 个 论 模 ?
2. 顺 驱 模 -> -> ->章 -> 订渲 
3. 责 误 件 --
"""

import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Tuple

from loguru import logger

from .core import (
 ChapterStorage,
 DocumentComposer,
 TemplateSection,
 parse_template_sections,
)
from .ir import IRValidator
from .llms import LLMClient
from .nodes import (
 TemplateSelectionNode,
 ChapterGenerationNode,
 ChapterJsonParseError,
 ChapterContentError,
 ChapterValidationError,
 DocumentLayoutNode,
 WordBudgetNode,
 FactCheckerNode,
)
from .renderers import HTMLRenderer
from .state import ReportState
from .utils.config import settings, Settings


class StageOutputFormatError(ValueError):
 """ --""


class FileCountBaseline:
 """
 件 管 --

 该工 
 - 任 记 Insight/Media/Query 个 导 ?Markdown ?
 - 续轮询中快 
 - ?Flask " " --
 """
 
 def __init__(self):
 """
 读 快 --

 ?`logs/report_baseline.json` 建 份空快 ?
 以便 续 `initialize_baseline` 次 --
 """
 self.baseline_file = 'logs/report_baseline.json'
 self.baseline_data = self._load_baseline()
 
 def _load_baseline(self) -> Dict[str, int]:
 """
 载 --

 - 快 件 解 JSON ?
 - 载 常并 空 --
 """
 try:
 if os.path.exists(self.baseline_file):
 with open(self.baseline_file, 'r', encoding='utf-8') as f:
 return json.load(f)
 except Exception as e:
 logger.exception(f" 载 失败: {e}")
 return {}
 
 def _save_baseline(self):
 """
 --

 `ensure_ascii=False` + 缩 格 便人工 
 缺失 建--
 """
 try:
 os.makedirs(os.path.dirname(self.baseline_file), exist_ok=True)
 with open(self.baseline_file, 'w', encoding='utf-8') as f:
 json.dump(self.baseline_data, f, ensure_ascii=False, indent=2)
 except Exception as e:
 logger.exception(f" 失败: {e}")
 
 def initialize_baseline(self, directories: Dict[str, str]) -> Dict[str, int]:
 """
 件 --

 个 并 ?`.md` 件 为
 ?`check_new_files` 此对 --
 """
 current_counts = {}
 
 for engine, directory in directories.items():
 if os.path.exists(directory):
 md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
 current_counts[engine] = len(md_files)
 else:
 current_counts[engine] = 0
 
 # 
 self.baseline_data = current_counts.copy()
 self._save_baseline()
 
 logger.info(f" 件 已 : {current_counts}")
 return current_counts
 
 def check_new_files(self, directories: Dict[str, str]) -> Dict[str, Any]:
 """
 件--

 对 件 ?
 - 计 并 已 就绪 
 - 详 计 缺失 表 ?Web 示 --
 """
 current_counts = {}
 new_files_found = {}
 all_have_new = True
 
 for engine, directory in directories.items():
 if os.path.exists(directory):
 md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
 current_counts[engine] = len(md_files)
 baseline_count = self.baseline_data.get(engine, 0)
 
 if current_counts[engine] > baseline_count:
 new_files_found[engine] = current_counts[engine] - baseline_count
 else:
 new_files_found[engine] = 0
 all_have_new = False
 else:
 current_counts[engine] = 0
 new_files_found[engine] = 0
 all_have_new = False
 
 return {
 'ready': all_have_new,
 'baseline_counts': self.baseline_data,
 'current_counts': current_counts,
 'new_files_found': new_files_found,
 'missing_engines': [engine for engine, count in new_files_found.items() if count == 0]
 }
 
 def get_latest_files(self, directories: Dict[str, str]) -> Dict[str, str]:
 """
 个 件--

 `os.path.getmtime` Markdown ?
 以确 永 使 --
 """
 latest_files = {}
 
 for engine, directory in directories.items():
 if os.path.exists(directory):
 md_files = [f for f in os.listdir(directory) if f.endswith('.md')]
 if md_files:
 latest_file = max(md_files, key=lambda x: os.path.getmtime(os.path.join(directory, x)))
 latest_files[engine] = os.path.join(directory, latest_file)
 
 return latest_files


class ReportAgent:
 """
 Report Agent主类--

 责 ?
 - LLM客 端 个 
 - 章 IR 订 渲 产 路 
 - 管 校 --
 """
 _CONTENT_SPARSE_MIN_ATTEMPTS = 3
 _CONTENT_SPARSE_WARNING_TEXT = " 章LLM 容 以 --
 _STRUCTURAL_RETRY_ATTEMPTS = 2
 
 def __init__(self, config: Optional[Settings] = None):
 """
 Report Agent--
 
 Args:
 config: 置对象 ?
 
 步骤 ?
 1. 解 置并 ?LLM/渲 核 件 
 2. 个 模 章 ?
 3. 件 章 ?
 4. 建 容 询--
 """
 # 
 self.config = config or settings
 
 # 
 self.file_baseline = FileCountBaseline()
 
 # ?
 self._setup_logging()
 
 # LLM ?
 self.llm_client = self._initialize_llm()
 self.json_rescue_clients = self._initialize_rescue_llms()
 
 # ? / 
 self.chapter_storage = ChapterStorage(self.config.CHAPTER_OUTPUT_DIR)
 self.document_composer = DocumentComposer()
 self.validator = IRValidator()
 self.renderer = HTMLRenderer()
 
 # ?
 self._initialize_nodes()
 
 # ?
 self._initialize_file_baseline()
 
 # ?
 self.state = ReportState()
 
 # 
 os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
 os.makedirs(self.config.DOCUMENT_IR_OUTPUT_DIR, exist_ok=True)
 
 logger.info("Report Agent已 ")
 logger.info(f"使 LLM: {self.llm_client.get_model_info()}")
 
 def _setup_logging(self):
 """
 设置 --

 - 确 ?
 - 使 ?loguru sink Report Engine log 件 ?
 系 混 --
 - 修 置 确 端 ?
 - 修 止 添 handler
 """
 # 
 log_dir = os.path.dirname(self.config.LOG_FILE)
 os.makedirs(log_dir, exist_ok=True)

 def _exclude_other_engines(record):
 """
 滤 ?Insight/Media/Query/Forum)产 --

 使 路 为主 路 模 --
 """
 excluded_keywords = ("InsightEngine", "MediaEngine", "QueryEngine", "ForumEngine")
 try:
 file_path = record["file"].path
 if any(keyword in file_path for keyword in excluded_keywords):
 return False
 except Exception:
 pass

 try:
 module_name = record.get("module", "")
 if isinstance(module_name, str):
 lowered = module_name.lower()
 if any(keyword.lower() in lowered for keyword in excluded_keywords):
 return False
 except Exception:
 pass

 return True

 # handler ?
 # loguru 
 log_file_path = str(Path(self.config.LOG_FILE).resolve())

 # handlers
 handler_exists = False
 for handler_id, handler_config in logger._core.handlers.items():
 if hasattr(handler_config, 'sink'):
 sink = handler_config.sink
 # sink ?
 if hasattr(sink, '_name') and sink._name == log_file_path:
 handler_exists = True
 logger.debug(f" handler已 跳 添 : {log_file_path}")
 break

 if not handler_exists:
 # logger ?
 # - enqueue=False: ?
 # - buffering=1: ?
 # - level="DEBUG": 
 # - encoding="utf-8": UTF-8 
 # - mode="a": ?
 handler_id = logger.add(
 self.config.LOG_FILE,
 level="DEBUG",
 enqueue=False, # 步 步 ?
 buffering=1, # 
 serialize=False, # 格 为JSON
 encoding="utf-8", # 确UTF-8 
 mode="a", # 追 模 
 filter=_exclude_other_engines # 滤 ?Engine 信 
 )
 logger.debug(f"已添 handler (ID: {handler_id}): {self.config.LOG_FILE}")

 # ?
 try:
 with open(self.config.LOG_FILE, 'a', encoding='utf-8') as f:
 f.write('') # 空 符串 
 f.flush() # 
 except Exception as e:
 logger.error(f" 件 : {self.config.LOG_FILE}, 误: {e}")
 raise
 
 def _initialize_file_baseline(self):
 """
 件 --

 ?Insight/Media/Query 个 传 `FileCountBaseline` ?
 次 产 --
 """
 directories = {
 'insight': 'insight_engine_streamlit_reports',
 'media': 'media_engine_streamlit_reports',
 'query': 'query_engine_streamlit_reports'
 }
 self.file_baseline.initialize_baseline(directories)
 
 def _initialize_llm(self) -> LLMClient:
 """
 LLM客 端--

 置中 API Key / 模 / Base URL 建 ?
 `LLMClient` 为 --
 """
 return LLMClient(
 api_key=self.config.REPORT_ENGINE_API_KEY,
 model_name=self.config.REPORT_ENGINE_MODEL_NAME,
 base_url=self.config.REPORT_ENGINE_BASE_URL,
 )

 def _initialize_rescue_llms(self) -> List[Tuple[str, LLMClient]]:
 """
 跨 章 修 LLM客 端 表--

 顺 循"Report ?Forum ?Insight ?Media" 缺失 置 被 跳 --
 """
 clients: List[Tuple[str, LLMClient]] = []
 if self.llm_client:
 clients.append(("report_engine", self.llm_client))
 fallback_specs = [
 (
 "forum_engine",
 self.config.FORUM_HOST_API_KEY,
 self.config.FORUM_HOST_MODEL_NAME,
 self.config.FORUM_HOST_BASE_URL,
 ),
 (
 "insight_engine",
 self.config.INSIGHT_ENGINE_API_KEY,
 self.config.INSIGHT_ENGINE_MODEL_NAME,
 self.config.INSIGHT_ENGINE_BASE_URL,
 ),
 (
 "media_engine",
 self.config.MEDIA_ENGINE_API_KEY,
 self.config.MEDIA_ENGINE_MODEL_NAME,
 self.config.MEDIA_ENGINE_BASE_URL,
 ),
 ]
 for label, api_key, model_name, base_url in fallback_specs:
 if not api_key or not model_name:
 continue
 try:
 client = LLMClient(api_key=api_key, model_name=model_name, base_url=base_url)
 except Exception as exc:
 logger.warning(f"{label} LLM 失败 跳 该修 : {exc}")
 continue
 clients.append((label, client))
 return clients
 
 def _initialize_nodes(self):
 """
 --

 顺 模 档 章 个 
 中章 IR 校 章 --
 """
 self.template_selection_node = TemplateSelectionNode(
 self.llm_client,
 self.config.TEMPLATE_DIR
 )
 self.document_layout_node = DocumentLayoutNode(self.llm_client)
 self.word_budget_node = WordBudgetNode(self.llm_client)
 self.chapter_generation_node = ChapterGenerationNode(
 self.llm_client,
 self.validator,
 self.chapter_storage,
 fallback_llm_clients=self.json_rescue_clients,
 error_log_dir=self.config.JSON_ERROR_LOG_DIR,
 )
 self.fact_checker_node = FactCheckerNode(self.llm_client)
 
 def generate_report(self, query: str, reports: List[Any], forum_logs: str = "",
 custom_template: str = "", save_report: bool = True,
 stream_handler: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> str:
 """
 综 章 JSON ?IR ?HTML --

 主 段 ?
 1. + 论 并 件 ?
 2. 模 ?模 ? 档 ? ?
 3. 章 LLM 解 误 ?
 4. 章 订 Document IR 交 HTML渲 
 5. HTML/IR/ 并 传路 信 --

 :
 query: 主 语 --
 reports: Query/Media/Insight 许传 符串 对象--
 forum_logs: 论 / 记 LLM 解 人讨论 --
 custom_template: Markdown模 为空 交 模 --
 save_report: HTML IR --
 stream_handler: 件 段 签 payload UI 示--

 :
 dict: `html_content` 以 HTML/IR/ 件路 `save_report=False` HTML 符串--

 常:
 Exception: 任 渲 段失败 责 --
 """
 start_time = datetime.now()
 report_id = self.state.task_id if self.state.task_id else f"report-{uuid4().hex[:8]}"
 self.state.task_id = report_id
 self.state.query = query
 self.state.metadata.query = query
 self.state.mark_processing()

 normalized_reports = self._normalize_reports(reports)
 
 # ?
 self.state.query_engine_report = normalized_reports.get("query_engine", "")
 self.state.media_engine_report = normalized_reports.get("media_engine", "")
 self.state.insight_engine_report = normalized_reports.get("insight_engine", "")
 self.state.forum_logs = self._stringify(forum_logs)

 def emit(event_type: str, payload: Dict[str, Any]):
 """ Report Engine --""
 if not stream_handler:
 return
 try:
 stream_handler(event_type, payload)
 except Exception as callback_error:
 # CancelGenerationException ?
 if type(callback_error).__name__ == "CancelGenerationException":
 raise callback_error
 logger.warning(f" 件 失败: {callback_error}")

 logger.info(f" ?{report_id}: {query}")
 logger.info(f" - : {len(reports)}, 论 度: {len(str(forum_logs))}")
 emit('stage', {'stage': 'agent_start', 'report_id': report_id, 'query': query})

 try:
 template_result = self._select_template(query, reports, forum_logs, custom_template)
 template_result = self._ensure_mapping(
 template_result,
 "模 ",
 expected_keys=["template_name", "template_content"],
 )
 self.state.metadata.template_used = template_result.get('template_name', '')
 emit('stage', {
 'stage': 'template_selected',
 'template': template_result.get('template_name'),
 'reason': template_result.get('selection_reason')
 })
 emit('progress', {'progress': 10, 'message': '模 '})
 sections = self._slice_template(template_result.get('template_content', ''))
 if not sections:
 raise ValueError("模 解 章 请 模 容--)
 emit('stage', {'stage': 'template_sliced', 'section_count': len(sections)})

 template_text = template_result.get('template_content', '')
 template_overview = self._build_template_overview(template_text, sections)
 # + 
 layout_design = self._run_stage_with_retry(
 " 档设计",
 lambda: self.document_layout_node.run(
 sections,
 template_text,
 normalized_reports,
 forum_logs,
 query,
 template_overview,
 ),
 # toc tocPlan Schema ? 
 expected_keys=["title", "hero", "tocPlan", "tocTitle"],
 )
 emit('stage', {
 'stage': 'layout_designed',
 'title': layout_design.get('title'),
 'toc': layout_design.get('tocTitle')
 })
 emit('progress', {'progress': 15, 'message': ' 档 / 设计 '})
 # 
 word_plan = self._run_stage_with_retry(
 "章 ",
 lambda: self.word_budget_node.run(
 sections,
 layout_design,
 normalized_reports,
 forum_logs,
 query,
 template_overview,
 ),
 expected_keys=["chapters", "totalWords", "globalGuidelines"],
 postprocess=self._normalize_word_plan,
 )
 emit('stage', {
 'stage': 'word_plan_ready',
 'chapter_targets': len(word_plan.get('chapters', []))
 })
 emit('progress', {'progress': 20, 'message': '章 已 ?})
 # ? LLM
 chapter_targets = {
 entry.get("chapterId"): entry
 for entry in word_plan.get("chapters", [])
 if entry.get("chapterId")
 }

 generation_context = self._build_generation_context(
 query,
 normalized_reports,
 forum_logs,
 template_result,
 layout_design,
 chapter_targets,
 word_plan,
 template_overview,
 )
 # IR/ / / / 
 manifest_meta = {
 "query": query,
 "title": layout_design.get("title") or (f"{query} - " if query else template_result.get("template_name")),
 "subtitle": layout_design.get("subtitle"),
 "tagline": layout_design.get("tagline"),
 "templateName": template_result.get("template_name"),
 "selectionReason": template_result.get("selection_reason"),
 "themeTokens": generation_context.get("theme_tokens", {}),
 "toc": {
 "depth": 3,
 "autoNumbering": True,
 "title": layout_design.get("tocTitle") or " ",
 },
 "hero": layout_design.get("hero"),
 "layoutNotes": layout_design.get("layoutNotes"),
 "wordPlan": {
 "totalWords": word_plan.get("totalWords"),
 "globalGuidelines": word_plan.get("globalGuidelines"),
 },
 "templateOverview": template_overview,
 }
 if layout_design.get("themeTokens"):
 manifest_meta["themeTokens"] = layout_design["themeTokens"]
 if layout_design.get("tocPlan"):
 manifest_meta["toc"]["customEntries"] = layout_design["tocPlan"]
 # manifest ?
 run_dir = self.chapter_storage.start_session(report_id, manifest_meta)
 self._persist_planning_artifacts(run_dir, layout_design, word_plan, template_overview)
 emit('stage', {'stage': 'storage_ready', 'run_dir': str(run_dir)})

 chapters = []
 chapter_max_attempts = max(
 self._CONTENT_SPARSE_MIN_ATTEMPTS, self.config.CHAPTER_JSON_MAX_ATTEMPTS
 )
 total_chapters = len(sections) # 章 
 completed_chapters = 0 # 已 章 
 
 # =======================
 # : AI Memory ?
 # =======================
 chapter_memories = []
 generation_context["chapter_memories"] = chapter_memories

 for section in sections:
 logger.info(f" 章 : {section.title}")
 emit('chapter_status', {
 'chapterId': section.chapter_id,
 'title': section.title,
 'status': 'running'
 })
 # LLM delta SSE ?
 def chunk_callback(delta: str, meta: Dict[str, Any], section_ref: TemplateSection = section):
 """
 章 容 --

 Args:
 delta: LLM --
 meta: 传 章 使 --
 section_ref: 认 章 缺失 信 --
 """
 emit('chapter_chunk', {
 'chapterId': meta.get('chapterId') or section_ref.chapter_id,
 'title': meta.get('title') or section_ref.title,
 'delta': delta
 })

 chapter_payload: Dict[str, Any] | None = None
 attempt = 1
 best_sparse_candidate: Dict[str, Any] | None = None
 best_sparse_score = -1
 fallback_used = False
 while attempt <= chapter_max_attempts:
 try:
 chapter_payload = self.chapter_generation_node.run(
 section,
 generation_context,
 run_dir,
 stream_callback=chunk_callback
 )
 break
 except (ChapterJsonParseError, ChapterContentError, ChapterValidationError) as structured_error:
 if isinstance(structured_error, ChapterContentError):
 error_kind = "content_sparse"
 readable_label = " 容 度 常"
 elif isinstance(structured_error, ChapterValidationError):
 error_kind = "validation"
 readable_label = " 校 失败"
 else:
 error_kind = "json_parse"
 readable_label = "JSON解 失败"
 if isinstance(structured_error, ChapterContentError):
 candidate = getattr(structured_error, "chapter_payload", None)
 candidate_score = getattr(structured_error, "body_characters", 0) or 0
 if isinstance(candidate, dict) and candidate_score >= 0:
 if candidate_score > best_sparse_score:
 best_sparse_candidate = deepcopy(candidate)
 best_sparse_score = candidate_score
 will_fallback = (
 isinstance(structured_error, ChapterContentError)
 and attempt >= chapter_max_attempts
 and attempt >= self._CONTENT_SPARSE_MIN_ATTEMPTS
 and best_sparse_candidate is not None
 )
 logger.warning(
 "章 {title} {label} 第 {attempt}/{total} 次 : {error}",
 title=section.title,
 label=readable_label,
 attempt=attempt,
 total=chapter_max_attempts,
 error=structured_error,
 )
 status_value = 'retrying' if attempt < chapter_max_attempts or will_fallback else 'error'
 status_payload = {
 'chapterId': section.chapter_id,
 'title': section.title,
 'status': status_value,
 'attempt': attempt,
 'error': str(structured_error),
 'reason': error_kind,
 }
 if isinstance(structured_error, ChapterValidationError):
 validation_errors = getattr(structured_error, "errors", None)
 if validation_errors:
 status_payload['errors'] = validation_errors
 if will_fallback:
 status_payload['warning'] = 'content_sparse_fallback_pending'
 emit('chapter_status', status_payload)
 if will_fallback:
 logger.warning(
 "章 {title} 达 大 次 ?{score} 为 ?,
 title=section.title,
 score=best_sparse_score,
 )
 chapter_payload = self._finalize_sparse_chapter(best_sparse_candidate)
 fallback_used = True
 break
 if attempt >= chapter_max_attempts:
 raise
 attempt += 1
 continue
 except (AttributeError, TypeError, KeyError, IndexError, ValueError, json.JSONDecodeError) as structure_error:
 # ?JSON ?
 # ?
 # - AttributeError: ?list.get() 
 # - TypeError: ?
 # - KeyError: ?
 # - IndexError: 
 # - ValueError: ?LLM 
 # - json.JSONDecodeError: JSON ?
 error_type = type(structure_error).__name__
 logger.warning(
 "章 {title} 中 ?{error_type} 第 {attempt}/{total} 次 : {error}",
 title=section.title,
 error_type=error_type,
 attempt=attempt,
 total=chapter_max_attempts,
 error=structure_error,
 )
 emit('chapter_status', {
 'chapterId': section.chapter_id,
 'title': section.title,
 'status': 'retrying' if attempt < chapter_max_attempts else 'error',
 'attempt': attempt,
 'error': str(structure_error),
 'reason': 'structure_error',
 'error_type': error_type
 })
 if attempt >= chapter_max_attempts:
 # ?ChapterJsonParseError 
 raise ChapterJsonParseError(
 f"{section.title} 章 ?{error_type} ?{chapter_max_attempts} 次 ? {structure_error}"
 ) from structure_error
 attempt += 1
 continue
 except Exception as chapter_error:
 if not self._should_retry_inappropriate_content_error(chapter_error):
 raise
 logger.warning(
 "章 {title} 触 容 第 {attempt}/{total} 次 ? {error}",
 title=section.title,
 attempt=attempt,
 total=chapter_max_attempts,
 error=chapter_error,
 )
 emit('chapter_status', {
 'chapterId': section.chapter_id,
 'title': section.title,
 'status': 'retrying' if attempt < chapter_max_attempts else 'error',
 'attempt': attempt,
 'error': str(chapter_error),
 'reason': 'content_filter'
 })
 if attempt >= chapter_max_attempts:
 raise
 attempt += 1
 continue
 if chapter_payload is None:
 raise ChapterJsonParseError(
 f"{section.title} 章 JSON ?{chapter_max_attempts} 次 解 ?
 )
 
 # =======================
 # : Memory
 # =======================
 try:
 chapter_summary = self._extract_chapter_memory(chapter_payload)
 if chapter_summary:
 chapter_memories.append({
 "title": section.title,
 "summary": chapter_summary
 })
 except Exception as e:
 logger.warning(f" 章 {section.title}记 失败 跳 ? {e}")

 chapters.append(chapter_payload)
 completed_chapters += 1 # 已 章 
 # ?0% + 80% * ( / ) ?
 chapter_progress = 20 + round(80 * completed_chapters / total_chapters)
 emit('progress', {
 'progress': chapter_progress,
 'message': f'章 {completed_chapters}/{total_chapters} 已 ?
 })
 
 # HTML " ?
 try:
 import copy
 temp_chapters = copy.deepcopy(chapters)
 temp_ir = self.document_composer.build_document(
 report_id,
 manifest_meta,
 temp_chapters
 )
 # ?HTML
 temp_ir = self.fact_checker_node.run(temp_ir, normalized_reports)
 temp_html = self.renderer.render(temp_ir)
 self.state.html_content = temp_html
 emit('stage', {'stage': 'chapter_html_ready', 'chapter_id': section.chapter_id, 'task_id': report_id})
 except Exception as render_err:
 logger.warning(f" 渲 章 HTML 失败: {render_err}")
 
 completion_status = {
 'chapterId': section.chapter_id,
 'title': section.title,
 'status': 'completed',
 'attempt': attempt,
 }
 if fallback_used:
 completion_status['warning'] = 'content_sparse_fallback'
 completion_status['warningMessage'] = self._CONTENT_SPARSE_WARNING_TEXT
 emit('chapter_status', completion_status)

 document_ir = self.document_composer.build_document(
 report_id,
 manifest_meta,
 chapters
 )
 emit('stage', {'stage': 'chapters_compiled', 'chapter_count': len(chapters)})
 
 # --- ---
 emit('progress', {'progress': 95, 'message': '正 交 核 ?})
 document_ir = self.fact_checker_node.run(document_ir, normalized_reports)
 emit('stage', {'stage': 'fact_checked'})
 
 html_report = self.renderer.render(document_ir)
 emit('stage', {'stage': 'html_rendered', 'html_length': len(html_report)})

 self.state.html_content = html_report
 self.state.mark_completed()

 saved_files = {}
 if save_report:
 saved_files = self._save_report(html_report, document_ir, report_id)
 emit('stage', {'stage': 'report_saved', 'files': saved_files})

 generation_time = (datetime.now() - start_time).total_seconds()
 self.state.metadata.generation_time = generation_time
 logger.info(f" : {generation_time:.2f} ?)
 emit('metrics', {'generation_seconds': generation_time})
 return {
 'html_content': html_report,
 'report_id': report_id,
 **saved_files
 }

 except Exception as e:
 self.state.mark_failed(str(e))
 logger.exception(f" 中 ? {str(e)}")
 emit('error', {'stage': 'agent_failed', 'message': str(e)})
 raise
 
 def _select_template(self, query: str, reports: List[Any], forum_logs: str, custom_template: str):
 """
 模 --

 使 模 询 论 ?
 为 交 ?TemplateSelectionNode LLM ?
 模 称 容 并 记 中--

 :
 query: 主 示 / 件--
 reports: 帮 LLM 度--
 forum_logs: 对 论 讨论 补 --
 custom_template: CLI/ 端传 Markdown模 空 --

 :
 dict: `template_name` `template_content` ?`selection_reason` 续 费--
 """
 logger.info(" 模 ...")
 
 # ?
 if custom_template:
 logger.info("使 模 ?)
 return {
 'template_name': 'custom',
 'template_content': custom_template,
 'selection_reason': ' 模 '
 }
 
 # ?
 truncated_reports = []
 for report in reports:
 content = str(report)
 truncated_reports.append(content[:15000] if len(content) > 15000 else content)
 
 truncated_forum_logs = str(forum_logs)[:15000] if forum_logs else ""

 template_input = {
 'query': query,
 'reports': truncated_reports,
 'forum_logs': truncated_forum_logs
 }
 
 try:
 template_result = self.template_selection_node.run(template_input)
 
 # ?
 self.state.metadata.template_used = template_result['template_name']
 
 logger.info(f" 模 : {template_result['template_name']}")
 logger.info(f" : {template_result['selection_reason']}")
 
 return template_result
 except Exception as e:
 logger.error(f"模 失败 使 认模 ? {str(e)}")
 # 
 fallback_template = {
 'template_name': '社 件 模 ',
 'template_content': self._get_fallback_template_content(),
 'selection_reason': '模 失败 使 认社 件 模 ?
 }
 self.state.metadata.template_used = fallback_template['template_name']
 return fallback_template
 
 def _extract_chapter_memory(self, chapter_payload: Dict[str, Any]) -> str:
 """
 章 JSON中 核 容 为记 导 章 容 --
 核 论 --
 """
 memory_parts = []
 blocks = chapter_payload.get("blocks", [])
 
 for block in blocks:
 b_type = block.get("type")
 if b_type == "paragraph":
 text = block.get("content", {}).get("text", "")
 if len(text) > 100:
 memory_parts.append(text[:100] + "...") # 段 100 ?
 else:
 memory_parts.append(text)
 elif b_type == "kpiGrid":
 items = block.get("content", {}).get("items", [])
 for item in items:
 memory_parts.append(f"KPI: {item.get('label')}={item.get('value')}")
 elif b_type == "callout":
 memory_parts.append(f" 示: {block.get('content', {}).get('text', '')}")
 
 # ?
 if len("\n".join(memory_parts)) > 800:
 break
 
 summary = "\n".join(memory_parts)
 if len(summary) > 800:
 return summary[:800] + "...( )"
 return summary

 def _slice_template(self, template_markdown: str) -> List[TemplateSection]:
 """
 模 章 表 为空 fallback--

 `parse_template_sections` Markdown / 解 ?
 `TemplateSection` 表 确 续章 稳 章 ID--
 模 格 常 置 骨 崩 --

 :
 template_markdown: 模 Markdown --

 :
 list[TemplateSection]: 解 章 解 失败 章 --
 """
 sections = parse_template_sections(template_markdown)
 if sections:
 return sections
 logger.warning("模 解 章 使 认章 骨 ?)
 fallback = TemplateSection(
 title="1.0 综 ",
 slug="section-1-0",
 order=10,
 depth=1,
 raw_title="1.0 综 ",
 number="1.0",
 chapter_id="S1",
 outline=["1.1 ", "1.2 亮 ", "1.3 示"],
 )
 return [fallback]

 def _build_generation_context(
 self,
 query: str,
 reports: Dict[str, str],
 forum_logs: str,
 template_result: Dict[str, Any],
 layout_design: Dict[str, Any],
 chapter_directives: Dict[str, Any],
 word_plan: Dict[str, Any],
 template_overview: Dict[str, Any],
 ) -> Dict[str, Any]:
 """
 章 享 --

 模 称 设计 主 论 
 次 为 `generation_context` 续 章 ?LLM ?
 确 章 享 语 约 --

 :
 query: 询 --
 reports: ?query/media/insight --
 forum_logs: 讨论记 --
 template_result: 模 模 信 --
 layout_design: 档 产 ? /主 设计--
 chapter_directives: 章 令 --
 word_plan: 约 --
 template_overview: 模 章 骨 --

 :
 dict: LLM章 主 约 --
 """
 # ?
 theme_tokens = (
 layout_design.get("themeTokens")
 if layout_design else None
 ) or self._default_theme_tokens()

 return {
 "query": query,
 "template_name": template_result.get("template_name"),
 "reports": reports,
 "forum_logs": self._stringify(forum_logs),
 "theme_tokens": theme_tokens,
 "style_directives": {
 "tone": "analytical",
 "audience": "executive",
 "language": "zh-CN",
 },
 "data_bundles": [],
 "max_tokens": min(self.config.MAX_CONTENT_LENGTH, 6000),
 "layout": layout_design or {},
 "template_overview": template_overview or {},
 "chapter_directives": chapter_directives or {},
 "word_plan": word_plan or {},
 }

 def _normalize_reports(self, reports: List[Any]) -> Dict[str, str]:
 """
 转为 符串--

 约 顺 ?Query/Media/Insight 对象 ?
 类 此 ?`_stringify` 容 --

 :
 reports: 任 类 表 许缺失 顺 混乱--

 :
 dict: `query_engine`/`media_engine`/`insight_engine` 个 符串 段 --
 """
 keys = ["query_engine", "media_engine", "insight_engine"]
 normalized: Dict[str, str] = {}
 for idx, key in enumerate(keys):
 value = reports[idx] if idx < len(reports) else ""
 normalized[key] = self._stringify(value)
 return normalized

 def _should_retry_inappropriate_content_error(self, error: Exception) -> bool:
 """
 LLM 常 容 ? 容导 --

 误 许章 ?
 以便 容审 触 --

 :
 error: LLM客 端 常对象--

 :
 bool: 容审 True 为False--
 """
 message = str(error) if error else ""
 if not message:
 return False
 normalized = message.lower()
 keywords = [
 "inappropriate content",
 "content violation",
 "content moderation",
 "model-studio/error-code",
 ]
 return any(keyword in normalized for keyword in keywords)

 def _run_stage_with_retry(
 self,
 stage_name: str,
 fn: Callable[[], Any],
 expected_keys: Optional[List[str]] = None,
 postprocess: Optional[Callable[[Dict[str, Any], str], Dict[str, Any]]] = None,
 ) -> Dict[str, Any]:
 """
 个LLM 段并 常 次 --

 该 对 类 误 修 / 个Agent --
 """
 last_error: Optional[Exception] = None
 for attempt in range(1, self._STRUCTURAL_RETRY_ATTEMPTS + 1):
 try:
 raw_result = fn()
 result = self._ensure_mapping(raw_result, stage_name, expected_keys)
 if postprocess:
 result = postprocess(result, stage_name)
 return result
 except StageOutputFormatError as exc:
 last_error = exc
 logger.warning(
 "{stage} 常 第 {attempt}/{total} 次 修 ? {error}",
 stage=stage_name,
 attempt=attempt,
 total=self._STRUCTURAL_RETRY_ATTEMPTS,
 error=exc,
 )
 if attempt >= self._STRUCTURAL_RETRY_ATTEMPTS:
 break
 raise last_error # type: ignore[misc]

 def _ensure_mapping(
 self,
 value: Any,
 context: str,
 expected_keys: Optional[List[str]] = None,
 ) -> Dict[str, Any]:
 """
 确 段 为dict 表 佳 素--
 """
 if isinstance(value, dict):
 return value

 if isinstance(value, list):
 candidates = [item for item in value if isinstance(item, dict)]
 if candidates:
 best = candidates[0]
 if expected_keys:
 candidates.sort(
 key=lambda item: sum(1 for key in expected_keys if key in item),
 reverse=True,
 )
 best = candidates[0]
 logger.warning(
 "{context} 表 已 素继续 ?,
 context=context,
 )
 return best
 raise StageOutputFormatError(f"{context} 表 缺 对象 素")

 if value is None:
 raise StageOutputFormatError(f"{context} 空 ?)

 raise StageOutputFormatError(
 f"{context} 类 {type(value).__name__} ?
 )

 def _normalize_word_plan(self, word_plan: Dict[str, Any], stage_name: str) -> Dict[str, Any]:
 """
 确 ?chapters/globalGuidelines/totalWords 类 --
 """
 raw_chapters = word_plan.get("chapters", [])
 if isinstance(raw_chapters, dict):
 chapters_iterable = raw_chapters.values()
 elif isinstance(raw_chapters, list):
 chapters_iterable = raw_chapters
 else:
 chapters_iterable = []

 normalized: List[Dict[str, Any]] = []
 for idx, entry in enumerate(chapters_iterable):
 if isinstance(entry, dict):
 normalized.append(entry)
 continue
 if isinstance(entry, list):
 dict_candidate = next((item for item in entry if isinstance(item, dict)), None)
 if dict_candidate:
 logger.warning(
 "{stage} ?{idx} 个章 为 表 已 个对象 续 ",
 stage=stage_name,
 idx=idx + 1,
 )
 normalized.append(dict_candidate)
 continue
 logger.warning(
 "{stage} 跳 解 章 ?{idx} 类 ? {type_name} ?,
 stage=stage_name,
 idx=idx + 1,
 type_name=type(entry).__name__,
 )

 if not normalized:
 raise StageOutputFormatError(f"{stage_name} 缺 章 继续")

 word_plan["chapters"] = normalized

 guidelines = word_plan.get("globalGuidelines")
 if not isinstance(guidelines, list):
 if guidelines is None or guidelines == "":
 word_plan["globalGuidelines"] = []
 else:
 logger.warning(
 "{stage} globalGuidelines 类 常 已转 为 表 ?,
 stage=stage_name,
 )
 word_plan["globalGuidelines"] = [guidelines]

 if not isinstance(word_plan.get("totalWords"), (int, float)):
 logger.warning(
 "{stage} totalWords 类 常 使 认 ?10000",
 stage=stage_name,
 )
 word_plan["totalWords"] = 10000

 return word_plan

 def _finalize_sparse_chapter(self, chapter: Optional[Dict[str, Any]]) -> Dict[str, Any]:
 """
 容 章 payload并 温馨 示段 --
 """
 safe_chapter = deepcopy(chapter or {})
 if not isinstance(safe_chapter, dict):
 safe_chapter = {}
 self._ensure_sparse_warning_block(safe_chapter)
 return safe_chapter

 def _ensure_sparse_warning_block(self, chapter: Dict[str, Any]) -> None:
 """
 示段 章 读 该章 --
 """
 warning_block = {
 "type": "paragraph",
 "inlines": [
 {
 "text": self._CONTENT_SPARSE_WARNING_TEXT,
 "marks": [{"type": "italic"}],
 }
 ],
 "meta": {"role": "content-sparse-warning"},
 }
 blocks = chapter.get("blocks")
 if isinstance(blocks, list) and blocks:
 inserted = False
 for idx, block in enumerate(blocks):
 if isinstance(block, dict) and block.get("type") == "heading":
 blocks.insert(idx + 1, warning_block)
 inserted = True
 break
 if not inserted:
 blocks.insert(0, warning_block)
 else:
 chapter["blocks"] = [warning_block]
 meta = chapter.get("meta")
 if isinstance(meta, dict):
 meta["contentSparseWarning"] = True
 else:
 chapter["meta"] = {"contentSparseWarning": True}

 def _stringify(self, value: Any) -> str:
 """
 对象转 符串--

 - dict/list 为格 ?JSON 便 示 费 ?
 - 类 ?`str()` None 空串 None 传 --

 :
 value: 任 Python对象--

 :
 str: 示 ? 符串表 --
 """
 if value is None:
 return ""
 if isinstance(value, str):
 return value
 if isinstance(value, (dict, list)):
 try:
 return json.dumps(value, ensure_ascii=False, indent=2)
 except Exception:
 return str(value)
 return str(value)

 def _default_theme_tokens(self) -> Dict[str, Any]:
 """
 认主 渲 /LLM --

 使 该 格 --

 :
 dict: 渲 主 --
 """
 return {
 "colors": {
 "bg": "#f8f9fa",
 "text": "#212529",
 "primary": "#007bff",
 "secondary": "#6c757d",
 "card": "#ffffff",
 "border": "#dee2e6",
 "accent1": "#17a2b8",
 "accent2": "#28a745",
 "accent3": "#ffc107",
 "accent4": "#dc3545",
 },
 "fonts": {
 "body": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif",
 "heading": "'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
 },
 "spacing": {"container": "1200px", "gutter": "24px"},
 "vars": {
 "header_sticky": True,
 "toc_depth": 3,
 "enable_dark_mode": True,
 },
 }

 def _build_template_overview(
 self,
 template_markdown: str,
 sections: List[TemplateSection],
 ) -> Dict[str, Any]:
 """
 模 章 骨 设 ? --

 记 章 ID/slug/order 段 对 --

 :
 template_markdown: 模 解 --
 sections: `TemplateSection` 表 为章 骨 --

 :
 dict: 模 章 --
 """
 fallback_title = sections[0].title if sections else ""
 overview = {
 "title": self._extract_template_title(template_markdown, fallback_title),
 "chapters": [],
 }
 for section in sections:
 overview["chapters"].append(
 {
 "chapterId": section.chapter_id,
 "title": section.title,
 "rawTitle": section.raw_title,
 "number": section.number,
 "slug": section.slug,
 "order": section.order,
 "depth": section.depth,
 "outline": section.outline,
 }
 )
 return overview

 @staticmethod
 def _extract_template_title(template_markdown: str, fallback: str = "") -> str:
 """
 Markdown中 个 --

 个 `#` 语 模 就 正 ?
 第 空 fallback--

 :
 template_markdown: 模 --
 fallback: 档缺 使 --

 :
 str: 解 --
 """
 for line in template_markdown.splitlines():
 stripped = line.strip()
 if not stripped:
 continue
 if stripped.startswith("#"):
 return stripped.lstrip("#").strip()
 if stripped:
 fallback = fallback or stripped
 return fallback or " "
 
 def _get_fallback_template_content(self) -> str:
 """
 模 容--

 模 LLM 失败 使 该 Markdown 模 ?
 续 章 --
 """
 return """# 

## 
 对 社 件 综 信 --

## 
### 
- 件 质 {event_nature}
- {event_time}
- {event_scope}

## 
### 
{sentiment_analysis}

### 
{opinion_distribution}

## 
### 
{media_analysis}

### 
{report_focus}

## 
### 
{direct_impact}

### 
{potential_impact}

## 
### 
{immediate_actions}

### 
{long_term_strategy}

## ?
{conclusion}

---
* 类 社 件 ?
* {generation_time}*
"""
 
 def _save_report(self, html_content: str, document_ir: Dict[str, Any], report_id: str) -> Dict[str, Any]:
 """
 HTML IR 件并 路 信 --

 询 读 件 
 `ReportState` JSON 便 游 续 --

 :
 html_content: 渲 HTML正 --
 document_ir: Document IR --
 report_id: 任 ID 建 件 --

 :
 dict: 记 HTML/IR/State 件 对 对路 信 --
 """
 query_safe = "".join(
 c for c in self.state.metadata.query if c.isalnum() or c in (" ", "-", "_")
 ).rstrip()
 query_safe = query_safe.replace(" ", "_")[:30] or "report"

 # task_id ?query ?
 try:
 for old_file in Path(self.config.OUTPUT_DIR).glob(f"*{report_id}*"):
 if old_file.is_file():
 old_file.unlink()
 for old_ir in Path(self.config.DOCUMENT_IR_OUTPUT_DIR).glob(f"*{report_id}*"):
 if old_ir.is_file():
 old_ir.unlink()
 except Exception as e:
 logger.warning(f" 件失 ? {e}")

 html_filename = f"final_report_{query_safe}_{report_id}.html"
 html_path = Path(self.config.OUTPUT_DIR) / html_filename
 html_path.write_text(html_content, encoding="utf-8")
 html_abs = str(html_path.resolve())
 html_rel = os.path.relpath(html_abs, os.getcwd())

 ir_path = self._save_document_ir(document_ir, query_safe, report_id)
 ir_abs = str(ir_path.resolve())
 ir_rel = os.path.relpath(ir_abs, os.getcwd())

 state_filename = f"report_state_{query_safe}_{report_id}.json"
 state_path = Path(self.config.OUTPUT_DIR) / state_filename
 self.state.save_to_file(str(state_path))
 state_abs = str(state_path.resolve())
 state_rel = os.path.relpath(state_abs, os.getcwd())

 logger.info(f"HTML 已 ? {html_path}")
 logger.info(f"Document IR已 ? {ir_path}")
 logger.info(f" 已 ? {state_path}")
 
 return {
 'report_filename': html_filename,
 'report_filepath': html_abs,
 'report_relative_path': html_rel,
 'ir_filename': ir_path.name,
 'ir_filepath': ir_abs,
 'ir_relative_path': ir_rel,
 'state_filename': state_filename,
 'state_filepath': state_abs,
 'state_relative_path': state_rel,
 }

 def _save_document_ir(self, document_ir: Dict[str, Any], query_safe: str, timestamp: str) -> Path:
 """
 IR --

 `Document IR` ?HTML 解 便 渲 差 以 
 ?LLM 次渲 导 格 --

 :
 document_ir: IR --
 query_safe: 已 询 语 件 --
 timestamp: 件 --

 :
 Path: IR 件路 --
 """
 filename = f"report_ir_{query_safe}_{timestamp}.json"
 ir_path = Path(self.config.DOCUMENT_IR_OUTPUT_DIR) / filename
 ir_path.write_text(
 json.dumps(document_ir, ensure_ascii=False, indent=2),
 encoding="utf-8",
 )
 return ir_path
 
 def _persist_planning_artifacts(
 self,
 run_dir: Path,
 layout_design: Dict[str, Any],
 word_plan: Dict[str, Any],
 template_overview: Dict[str, Any],
 ):
 """
 档设计稿 模 JSON--

 中 件 件 document_layout/word_plan/template_overview ?
 便 快 / /主 确 --
 以便 续人工校正--

 :
 run_dir: 章 根 --
 layout_design: 档 --
 word_plan: --
 template_overview: 模 JSON--
 """
 artifacts = {
 "document_layout": layout_design,
 "word_plan": word_plan,
 "template_overview": template_overview,
 }
 for name, payload in artifacts.items():
 if not payload:
 continue
 path = run_dir / f"{name}.json"
 try:
 path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
 except Exception as exc:
 logger.warning(f" {name}失败: {exc}")
 
 def get_progress_summary(self) -> Dict[str, Any]:
 """ API --""
 return self.state.to_dict()
 
 def load_state(self, filepath: str):
 """ state --""
 self.state = ReportState.load_from_file(filepath)
 logger.info(f" 已 ?{filepath} 载")
 
 def save_state(self, filepath: str):
 """ --""
 self.state.save_to_file(filepath)
 logger.info(f" 已 ?{filepath}")
 
 def check_input_files(self, insight_dir: str, media_dir: str, query_dir: str, forum_log_path: str, task_id: str = None) -> Dict[str, Any]:
 """
 件 就绪--
 
 ?task_id 个 ?task_id 件 --
 没 task_id 件 管 件--
 
 Args:
 insight_dir: InsightEngine 
 media_dir: MediaEngine 
 query_dir: QueryEngine 
 forum_log_path: 论 件路 
 task_id: 任 ID 
 
 Returns:
 件计 缺失 表 件路 
 """
 directories = {
 'insight': insight_dir,
 'media': media_dir,
 'query': query_dir
 }
 
 # ?
 forum_ready = os.path.exists(forum_log_path)
 
 if task_id:
 # task_id ?
 missing_files = []
 files_found = []
 latest_files = {}
 ready = True
 
 for engine, directory in directories.items():
 dir_path = Path(directory)
 if not dir_path.exists():
 ready = False
 missing_files.append(engine)
 continue
 
 # task_id ?
 matching_files = list(dir_path.glob(f"*{task_id}*"))
 if matching_files:
 # ?
 latest_file = max(matching_files, key=os.path.getmtime)
 files_found.append(latest_file.name)
 latest_files[engine] = str(latest_file.resolve())
 else:
 ready = False
 missing_files.append(f"{engine} 中 任 {task_id} ?)
 
 return {
 'ready': ready and forum_ready,
 'baseline_counts': {},
 'current_counts': {},
 'new_files_found': {},
 'missing_files': missing_files,
 'files_found': files_found,
 'latest_files': latest_files
 }
 
 # 
 check_result = self.file_baseline.check_new_files(directories)
 
 # ?
 forum_ready = os.path.exists(forum_log_path)
 
 # 
 result = {
 'ready': check_result['ready'] and forum_ready,
 'baseline_counts': check_result['baseline_counts'],
 'current_counts': check_result['current_counts'],
 'new_files_found': check_result['new_files_found'],
 'missing_files': [],
 'files_found': [],
 'latest_files': {}
 }
 
 # 
 for engine, new_count in check_result['new_files_found'].items():
 current_count = check_result['current_counts'][engine]
 baseline_count = check_result['baseline_counts'].get(engine, 0)
 
 if new_count > 0:
 result['files_found'].append(f"{engine}: {current_count}个 ?( {new_count} ?")
 else:
 result['missing_files'].append(f"{engine}: {current_count}个 ?( {baseline_count}个 ?")
 
 # ?
 if forum_ready:
 result['files_found'].append(f"forum: {os.path.basename(forum_log_path)}")
 else:
 result['missing_files'].append("forum: 件 ?)
 
 # ?
 if result['ready']:
 result['latest_files'] = self.file_baseline.get_latest_files(directories)
 if forum_ready:
 result['latest_files']['forum'] = forum_log_path
 
 return result
 
 def load_input_files(self, file_paths: Dict[str, str]) -> Dict[str, Any]:
 """
 载 件 容
 
 Args:
 file_paths: 件路 
 
 Returns:
 载 容 `reports` 表 ?`forum_logs` 符 ?
 """
 content = {
 'reports': [],
 'forum_logs': ''
 }
 
 # 
 engines = ['query', 'media', 'insight']
 for engine in engines:
 if engine in file_paths:
 try:
 with open(file_paths[engine], 'r', encoding='utf-8') as f:
 report_content = f.read()
 content['reports'].append(report_content)
 logger.info(f"已 ?{engine} : {len(report_content)} 符")
 except Exception as e:
 logger.exception(f" 载 {engine} 失败: {str(e)}")
 content['reports'].append("")
 
 # 
 if 'forum' in file_paths:
 try:
 with open(file_paths['forum'], 'r', encoding='utf-8') as f:
 content['forum_logs'] = f.read()
 logger.info(f"已 载论 ? {len(content['forum_logs'])} 符")
 except Exception as e:
 logger.exception(f" 载论 失败: {str(e)}")
 
 return content


def create_agent(config_file: Optional[str] = None) -> ReportAgent:
 """
 建Report Agent 便 --
 
 Args:
 config_file: 置 件路 
 
 Returns:
 ReportAgent 

 以 驱 ?`Settings` ?`config_file` 便 --
 """
 
 config = Settings() # 以空 置 
 return ReportAgent(config)
