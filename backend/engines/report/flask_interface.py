ï»¿"""
Report Engine Flaskæ¥å£ï¿½?

è¯¥æ¨¡åä¸ºåç«¯/CLIæä¾ç»ä¸HTTP/SSEå¥å£ï¼è´è´£ï¼
1. åå§ï¿½?ReportAgent å¹¶ä¸²èåå°çº¿ç¨ï¼
2. ç®¡çä»»å¡æéãè¿åº¦æ¥è¯¢ãæµå¼æ¨éä¸æ¥å¿ä¸è½½ï¿½?
3. æä¾æ¨¡æ¿åè¡¨ãè¾å¥æä»¶æ£æ¥ç­å¨è¾¹è½åï¿½?
"""

import os
import json
import threading
import time
from collections import deque, defaultdict
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from flask import Blueprint, request, jsonify, Response, send_file, stream_with_context
from typing import Dict, Any, List, Optional
from loguru import logger
from .agent import ReportAgent, create_agent
from .nodes import ChapterJsonParseError
from .utils.config import settings


from werkzeug.utils import secure_filename
import docx
import fitz  # PyMuPDF

# åå»ºBlueprint
report_bp = Blueprint('report_engine', __name__)

# å¨å±åé
report_agent = None
current_task = None
task_lock = threading.Lock()

# ====== æµå¼æ¨éä¸ä»»å¡åå²ç®¡ç ======
# éè¿æçdequeç¼å­æè¿çäºä»¶ï¼æ¹ä¾¿SSEæ­çº¿åå¿«éè¡¥ï¿½?
MAX_TASK_HISTORY = 5
STREAM_HEARTBEAT_INTERVAL = 15  # å¿è·³é´éï¿½?
STREAM_IDLE_TIMEOUT = 120  # ç»æåæé¿ä¿æ´»æ¶é´ï¼é¿åå­¤å¿SSEé»å¡
STREAM_TERMINAL_STATUSES = {"completed", "error", "cancelled"}
stream_lock = threading.Lock()
stream_subscribers = defaultdict(list)
tasks_registry: Dict[str, 'ReportTask'] = {}
LOG_STREAM_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
log_stream_handler_id: Optional[int] = None

EXCLUDED_ENGINE_PATH_KEYWORDS = ("backend/engines/forum", "backend/engines/insight", "backend/engines/media", "backend/engines/query")

def _is_excluded_engine_log(record: Dict[str, Any]) -> bool:
    """
    å¤æ­æ¥å¿æ¯å¦æ¥èªå¶ä»å¼æï¼Insight/Media/Query/Forumï¼ï¼ç¨äºè¿æ»¤æ··å¥çæ¥å¿ï¿½?

    è¿å:
        bool: True è¡¨ç¤ºåºå½è¿æ»¤ï¼å³ä¸åï¿½?ä¸è½¬åï¼ï¿½?
    """
    try:
        file_path = record["file"].path
        if any(keyword in file_path for keyword in EXCLUDED_ENGINE_PATH_KEYWORDS):
            return True
    except Exception:
        pass

    # ååºï¼å°è¯ææ¨¡ååè¿æ»¤ï¼é²æ­¢fileä¿¡æ¯ç¼ºå¤±æ¶è¯¯æ··å¥
    try:
        module_name = record.get("module", "")
        if isinstance(module_name, str):
            lowered = module_name.lower()
            return any(keyword.lower() in lowered for keyword in EXCLUDED_ENGINE_PATH_KEYWORDS)
    except Exception:
        pass

    return False


def _stream_log_to_task(message):
    """
    å°loguruæ¥å¿åæ­¥å°å½åä»»å¡çSSEäºä»¶ï¼ä¿è¯åç«¯å®æ¶å¯è§ï¿½?

    ä»å¨å­å¨è¿è¡ä¸­çä»»å¡æ¶æ¨éï¼é¿åæ å³æ¥å¿å·å±ï¿½?
    """
    try:
        record = message.record
        level_name = record["level"].name
        if level_name not in LOG_STREAM_LEVELS:
            return
        if _is_excluded_engine_log(record):
            return

        with task_lock:
            task = current_task

        if not task or task.status not in ("running", "pending"):
            return

        timestamp = record["time"].strftime("%H:%M:%S.%f")[:-3]
        formatted_line = f"[{timestamp}] [{level_name}] {record['message']}"
        task.publish_event(
            "log",
            {
                "line": formatted_line,
                "level": level_name.lower(),
                "timestamp": timestamp,
                "message": record["message"],
                "module": record.get("module", ""),
                "function": record.get("function", ""),
            },
        )
    except Exception:
        # é¿åå¨æ¥å¿é©å­éäº§çæ¥å¿éå½
        pass


def _setup_log_stream_forwarder():
    """ä¸ºå½åè¿ç¨æè½½ä¸æ¬¡æ§çlogurué©å­ï¼ç¨äºSSEå®æ¶è½¬åï¿½?""
    global log_stream_handler_id
    if log_stream_handler_id is not None:
        return
    log_stream_handler_id = logger.add(
        _stream_log_to_task,
        level="DEBUG",
        enqueue=False,
        catch=True,
    )


def _register_stream(task_id: str) -> Queue:
    """
    ä¸ºæå®ä»»å¡æ³¨åä¸ä¸ªäºä»¶éåï¼ä¾SSEçå¬å¨æ¶è´¹ï¿½?

    è¿åï¿½?Queue ä¼å­ï¿½?`stream_subscribers`ï¼SSE çæå¨å°ä¸æ­è¯»åï¿½?

    åæ°:
        task_id: éè¦çå¬çä»»å¡IDï¿½?

    è¿å:
        Queue: çº¿ç¨å®å¨çäºä»¶éåï¿½?
    """
    queue = Queue()
    with stream_lock:
        stream_subscribers[task_id].append(queue)
    return queue


def _unregister_stream(task_id: str, queue: Queue):
    """
    å®å¨ç§»é¤äºä»¶éåï¼é¿ååå­æ³æ¼ï¿½?

    éè¦å¨finallyä¸­è°ç¨ï¼ä¿è¯å¼å¸¸æåµä¸èµæºä¹è½éæ¾ï¿½?

    åæ°:
        task_id: ä»»å¡IDï¿½?
        queue: ä¹åæ³¨åçäºä»¶éåï¿½?
    """
    with stream_lock:
        listeners = stream_subscribers.get(task_id, [])
        if queue in listeners:
            listeners.remove(queue)
        if not listeners and task_id in stream_subscribers:
            stream_subscribers.pop(task_id, None)


def _broadcast_event(task_id: str, event: Dict[str, Any]):
    """
    å°äºä»¶æ¨éç»ææçå¬èï¼å¤±è´¥æ¶åå¥½å¼å¸¸æè·ï¿½?

    éç¨æµæ·è´çå¬åè¡¨ï¼é²æ­¢å¹¶åç§»é¤å¯¼è´éåå¼å¸¸ï¿½?

    åæ°:
        task_id: å¾æ¨éçä»»å¡IDï¿½?
        event: ç»æåäºä»¶payloadï¿½?
    """
    with stream_lock:
        listeners = list(stream_subscribers.get(task_id, []))
    for queue in listeners:
        try:
            queue.put(event, timeout=0.1)
        except Exception:
            logger.exception("æ¨éæµå¼äºä»¶å¤±è´¥ï¼è·³è¿å½åçå¬éå")


def _prune_task_history_locked():
    """
    å¨task_lockæææé´è°ç¨ï¼æ¸çè¿å¤çåå²ä»»å¡ï¿½?

    ä»ä¿çæï¿½?`MAX_TASK_HISTORY` ä¸ªä»»å¡ï¼é¿åé¿æ¶é´è¿è¡å ç¨è¿å¤åå­ï¿½?

    è¯´æ:
        è¯¥å½æ°åè®¾è°ç¨æ¹å·²è·ï¿½?`task_lock`ï¼å¦åå­å¨ç«æé£é©ï¿½?
    """
    if len(tasks_registry) <= MAX_TASK_HISTORY:
        return
    # æåå»ºæ¶é´æåºï¼ç§»é¤ææ§çä»»å¡
    sorted_tasks = sorted(tasks_registry.values(), key=lambda t: t.created_at)
    for task in sorted_tasks[:-MAX_TASK_HISTORY]:
        tasks_registry.pop(task.task_id, None)


def _get_task(task_id: str) -> Optional['ReportTask']:
    """
    ç»ä¸çä»»å¡æ¥æ¾æ¹æ³ï¼ä¼åè¿åå½åä»»å¡ï¿½?

    é¿åéå¤åéé»è¾ï¼ä¾¿äºå¤ä¸ªAPIå±äº«ï¿½?

    åæ°:
        task_id: ä»»å¡IDï¿½?

    è¿å:
        ReportTask | None: å½ä¸­æ¶è¿åä»»å¡å®ä¾ï¼å¦åä¸ºNoneï¿½?
    """
    with task_lock:
        if current_task and current_task.task_id == task_id:
            return current_task
        task = tasks_registry.get(task_id)
        if task:
            return task
            
    # å¦ææ¯åºäºæä»¶æ¢å¤çåå²ä»»å¡ï¼ä¸´æ¶æå»ºä¸ä¸ªTaskå¯¹è±¡è¿å
    if task_id.startswith('recovered_file_') and report_agent:
        output_dir = Path(report_agent.config.OUTPUT_DIR)
        if output_dir.exists():
            filename = task_id.replace('recovered_file_', '')
            target_html = output_dir / filename
            
            if target_html.exists():
                temp_task = ReportTask("åå²ä»»å¡ (ä»æä»¶æ¢ï¿½?", task_id)
                temp_task.status = "completed"
                temp_task.progress = 100
                temp_task.report_file_ready = True
                temp_task.report_file_path = str(target_html.resolve())
                temp_task.report_file_name = target_html.name
                temp_task.created_at = datetime.fromtimestamp(target_html.stat().st_ctime)
                temp_task.updated_at = datetime.fromtimestamp(target_html.stat().st_mtime)
                
                try:
                    temp_task.html_content = target_html.read_text(encoding="utf-8")
                except Exception:
                    pass
                    
                base_name_parts = target_html.stem.replace('final_report_', '').split('_')
                if len(base_name_parts) >= 2:
                    timestamp = f"{base_name_parts[-2]}_{base_name_parts[-1]}"
                    query_safe = '_'.join(base_name_parts[:-2])
                    
                    ir_filename = f"report_ir_{query_safe}_{timestamp}.json"
                    ir_path = Path(report_agent.config.DOCUMENT_IR_OUTPUT_DIR) / ir_filename
                    if ir_path.exists():
                        temp_task.ir_file_ready = True
                        temp_task.ir_file_path = str(ir_path.resolve())
                        
                    state_filename = f"report_state_{query_safe}_{timestamp}.json"
                    state_path = output_dir / state_filename
                    if state_path.exists():
                        temp_task.state_file_ready = True
                        temp_task.state_file_path = str(state_path.resolve())
                        try:
                            state_data = json.loads(state_path.read_text(encoding="utf-8"))
                            
                            # å°è¯ä»stateä¸­è·ï¿½?
                            insight_report = state_data.get('insight_engine_report', '')
                            media_report = state_data.get('media_engine_report', '')
                            query_report = state_data.get('query_engine_report', '')
                            forum_logs = state_data.get('forum_logs', '')
                            
                            # å¦æä¸ºç©ºï¼å°è¯å»ä¸ä¸ªå¼æçç®å½éæ¾å¯¹åºçæä»¶
                            # query_safe çæ ¼å¼å¦ï¼æ¸¸æè¾¾å·´_æ°´çä¹å°
                            # åå¼æç®å½çæ¥ååç¼ï¿½?deep_search_report_ï¼å¹éæ¥è¯¢è¯å¼ï¿½?
                            if not insight_report:
                                insight_report = _find_engine_report('insight', query_safe)
                            if not media_report:
                                media_report = _find_engine_report('media', query_safe)
                            if not query_report:
                                query_report = _find_engine_report('query', query_safe)

                            temp_task.history_inputs = {
                                'insight': insight_report,
                                'media': media_report,
                                'query': query_report,
                                'forum': forum_logs
                            }
                        except Exception as e:
                            logger.warning(f"è¯»ååå²ä»»å¡ç¶ææä»¶å¤±ï¿½?{state_path}: {e}")
                        
                return temp_task
    return None

def _find_engine_report(engine_name: str, query_safe: str) -> str:
    """
    æ ¹æ®å¼æåç§°åæ¥è¯¢è¯åç¼ï¼å¨å¯¹åºçç®å½ä¸­å¯»æ¾ææ°ç md æ¥åå¹¶è¯»ååå®¹ï¿½?
    """
    engine_dir = Path(f"{engine_name}_engine_streamlit_reports")
    if not engine_dir.exists():
        return ""
        
    md_files = list(engine_dir.glob(f"deep_search_report_{query_safe}*.md"))
    if md_files:
        # å¦ææ¾å°å¤ä¸ªï¼æä¿®æ¹æ¶é´åææ°ç
        latest_file = max(md_files, key=lambda p: p.stat().st_mtime)
        try:
            return latest_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"è¯»å {engine_name} å¼ææ¥åæä»¶å¤±è´¥ {latest_file}: {e}")
    return ""


def _format_sse(event: Dict[str, Any]) -> str:
    """
    æSSEåè®®æ ¼å¼åæ¶æ¯ï¿½?

    è¾åºå½¢å¦ `id:/event:/data:` çä¸æ®µææ¬ï¼ä¾æµè§å¨ç«¯ç´æ¥æ¶è´¹ï¿½?

    åæ°:
        event: äºä»¶payloadï¼è³å°åï¿½?id/typeï¿½?

    è¿å:
        str: SSEåè®®è¦æ±çå­ç¬¦ä¸²ï¿½?
    """
    payload = json.dumps(event, ensure_ascii=False)
    event_id = event.get('id', 0)
    event_type = event.get('type', 'message')
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


def _safe_filename_segment(value: str, fallback: str = "report") -> str:
    """
    çæå¯ç¨äºæä»¶åçå®å¨çæ®µï¼ä¿çå­æ¯æ°å­ä¸å¸¸è§åéç¬¦ï¿½?

    åæ°:
        value: åå§å­ç¬¦ä¸²ï¿½?
        fallback: ååºææ¬ï¼å½valueä¸ºç©ºææ¸æ´åä¸ºç©ºæ¶ä½¿ç¨ï¿½?
    """
    sanitized = "".join(c for c in str(value) if c.isalnum() or c in (" ", "-", "_")).strip()
    sanitized = sanitized.replace(" ", "_")
    return sanitized or fallback


def initialize_report_engine():
    """
    åå§åReport Engineï¿½?

    åä¾ï¿½?ReportAgentï¼æ¹ï¿½?API å¯å¨åç´æ¥æ¥æ¶ä»»å¡ï¿½?

    è¿å:
        bool: åå§åæåè¿åTrueï¼å¼å¸¸æ¶è¿åFalseï¿½?
    """
    global report_agent
    try:
        report_agent = create_agent()
        logger.info("Report Engineåå§åæï¿½?)
        _setup_log_stream_forwarder()

        # æ£ï¿½?PDF çæä¾èµï¼Pangoï¿½?
        try:
            from .utils.dependency_check import log_dependency_status
            log_dependency_status()
        except Exception as dep_err:
            logger.warning(f"ä¾èµæ£æµå¤±ï¿½? {dep_err}")

        return True
    except Exception as e:
        logger.exception(f"Report Engineåå§åå¤±ï¿½? {str(e)}")
        return False


class CancelGenerationException(Exception):
    """ç¨æ·ä¸»å¨åæ¶çæçå¼ï¿½?""
    pass

class ReportTask:
    """
    æ¥åçæä»»å¡ï¿½?

    è¯¥å¯¹è±¡ä¸²èè¿è¡ç¶æãè¿åº¦ãäºä»¶åå²åæç»æä»¶è·¯å¾ï¼
    æ¢ä¾åå°çº¿ç¨æ´æ°ï¼ä¹ä¾HTTPæ¥å£è¯»åï¿½?
    """

    def __init__(self, query: str, task_id: str, custom_template: str = ""):
        """
        åå§åä»»å¡å¯¹è±¡ï¼è®°å½æ¥è¯¢è¯ãèªå®ä¹æ¨¡æ¿ä¸è¿è¡æåæ°æ®ï¿½?

        Args:
            query: æç»éè¦çæçæ¥åä¸»é¢
            task_id: ä»»å¡å¯ä¸IDï¼éå¸¸ç±æ¶é´æ³æï¿½?
            custom_template: å¯éçèªå®ä¹Markdownæ¨¡æ¿
        """
        self.task_id = task_id
        self.query = query
        self.custom_template = custom_template
        self.seed_context = ""
        self.seed_filename = ""
        self.seed_url = ""
        self.status = "pending"  # åç§ç¶æï¼pending/running/completed/errorï¿½?
        self.progress = 0
        self.result = None
        self.error_message = ""
        self.is_cancelled = False
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.html_content = ""
        self.report_file_path = ""
        self.report_file_relative_path = ""
        self.report_file_name = ""
        self.state_file_path = ""
        self.state_file_relative_path = ""
        self.ir_file_path = ""
        self.ir_file_relative_path = ""
        self.markdown_file_path = ""
        self.markdown_file_relative_path = ""
        self.markdown_file_name = ""
        self.history_inputs = {}  # ä¿å­ä»ç¶ææä»¶ä¸­æ¢å¤çä¸ä¸ªå¼æçåå²æ°æ®
        # ====== æµå¼äºä»¶ç¼å­ä¸å¹¶åä¿ï¿½?======
        # ä½¿ç¨dequeä¿å­æè¿çäºä»¶ï¼ç»åéä¿è¯å¤çº¿ç¨ä¸çå®å¨è®¿ï¿½?
        self.event_history: deque = deque(maxlen=1000)
        self._event_lock = threading.Lock()
        self.last_event_id = 0

    def update_status(self, status: str, progress: int = None, error_message: str = ""):
        """
        æ´æ°ä»»å¡ç¶æå¹¶å¹¿æ­äºä»¶ï¿½?

        ä¼èªå¨å·ï¿½?`updated_at`ãéè¯¯ä¿¡æ¯ï¼å¹¶è§¦ï¿½?`status` ç±»åï¿½?SSEï¿½?

        åæ°:
            status: ä»»å¡é¶æ®µï¼pending/running/completed/error/cancelledï¼ï¿½?
            progress: å¯éçè¿åº¦ç¾åæ¯ï¿½?
            error_message: åºéæ¶çäººç±»å¯è¯»è¯´æï¿½?
        """
        self.status = status
        if progress is not None:
            self.progress = progress
        if error_message:
            self.error_message = error_message
        self.updated_at = datetime.now()
        # æ¨éç¶æåæ´äºä»¶ï¼æ¹ä¾¿åç«¯å®æ¶å·æ°
        self.publish_event(
            'status',
            {
                'status': self.status,
                'progress': self.progress,
                'error_message': self.error_message,
                'hint': error_message or '',
                'task': self.to_dict(),
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼ï¼æ¹ä¾¿ç´æ¥è¿åç»JSON APIï¿½?""
        return {
            'task_id': self.task_id,
            'query': self.query,
            'status': self.status,
            'progress': self.progress,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'has_result': bool(self.html_content),
            'report_file_ready': bool(self.report_file_path),
            'report_file_name': self.report_file_name,
            'report_file_path': self.report_file_relative_path or self.report_file_path,
            'state_file_ready': bool(self.state_file_path),
            'state_file_path': self.state_file_relative_path or self.state_file_path,
            'ir_file_ready': bool(self.ir_file_path),
            'ir_file_path': self.ir_file_relative_path or self.ir_file_path,
            'markdown_file_ready': bool(self.markdown_file_path),
            'markdown_file_name': self.markdown_file_name,
            'markdown_file_path': self.markdown_file_relative_path or self.markdown_file_path,
            'history_inputs': self.history_inputs
        }

    def publish_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        å°ä»»æäºä»¶æ¾å¥ç¼å­å¹¶å¹¿æ­ï¼æææ°å¢é»è¾åéå¥ä¸­æè¯´æï¿½?

        åæ°:
            event_type: SSEä¸­çeventåç§°ï¿½?
            payload: å®éä¸å¡æ°æ®ï¿½?
        """
        timestamp = datetime.utcnow().isoformat() + 'Z'
        event: Dict[str, Any] = {
            'id': 0,
            'type': event_type,
            'task_id': self.task_id,
            'timestamp': timestamp,
            'payload': payload,
        }
        with self._event_lock:
            self.last_event_id += 1
            event['id'] = self.last_event_id
            self.event_history.append(event)
        _broadcast_event(self.task_id, event)

    def history_since(self, last_event_id: Optional[int]) -> List[Dict[str, Any]]:
        """
        æ ¹æ®Last-Event-IDè¡¥ååå²äºä»¶ï¼ç¡®ä¿æ­çº¿éè¿æ éæ¼ï¿½?

        åæ°:
            last_event_id: SSEå®¢æ·ç«¯è®°å½çæåä¸ä¸ªäºä»¶IDï¿½?

        è¿å:
            list[dict]: ï¿½?last_event_id ä¹åçäºä»¶åè¡¨ï¿½?
        """
        with self._event_lock:
            if last_event_id is None:
                return list(self.event_history)
            return [evt for evt in self.event_history if evt['id'] > last_event_id]


def check_engines_ready(task_id: str = None) -> Dict[str, Any]:
    """
    æ£æ¥ä¸ä¸ªå­å¼ææ¯å¦é½ææ°æä»¶ï¿½?

    è°ç¨ ReportAgent çåºåæ£æµé»è¾ï¼å¹¶éå¸¦è®ºåæ¥å¿å­å¨æ§ï¼
    ï¿½?/statusï¿½?generate çåç½®æ ¡éªï¿½?
    å¦ææä¾ï¿½?task_idï¼åæ£æ¥è¯¥ç¹å®ä»»å¡çæä»¶æ¯å¦å­å¨ï¿½?
    """
    directories = {
        'insight': 'insight_engine_streamlit_reports',
        'media': 'media_engine_streamlit_reports',
        'query': 'query_engine_streamlit_reports'
    }

    forum_log_path = 'logs/forum.log'

    if not report_agent:
        return {
            'ready': False,
            'error': 'Report Engineæªåå§å'
        }

    return report_agent.check_input_files(
        directories['insight'],
        directories['media'],
        directories['query'],
        forum_log_path,
        task_id=task_id
    )


def run_report_generation(task: ReportTask, query: str, custom_template: str = ""):
    """
    å¨åå°çº¿ç¨ä¸­è¿è¡æ¥åçæï¿½?

    åæ¬ï¼æ£æ¥è¾å¥->å è½½ææ¡£->è°ç¨ReportAgent->æä¹åè¾åºï¿½?
    æ¨éé¶æ®µæ§äºä»¶ãåºç°éè¯¯ä¼èªå¨æ¨éå¹¶åç¶æï¿½?

    åæ°:
        task: æ¬æ¬¡ä»»å¡å¯¹è±¡ï¼åé¨ææäºä»¶éåï¿½?
        query: æ¥åä¸»é¢ï¿½?
        custom_template: å¯éçèªå®ä¹æ¨¡æ¿å­ç¬¦ä¸²ï¿½?
    """
    global current_task

    try:
        # å¨å±é¨é­ååå°è£æ¨éé»è¾ï¼ä¾¿äºä¼ éç»ReportAgent
        def stream_handler(event_type: str, payload: Dict[str, Any]):
            if task.is_cancelled:
                raise CancelGenerationException("ç¨æ·å·²åæ¶çï¿½?)
            
            # åæ­¥è·åææ°çå¢éHTMLåå®¹å°ä»»å¡å¯¹è±¡ä¸­ï¼ä½¿ï¿½?/result æ¥å£è½è¯»ï¿½?
            if event_type == 'stage' and payload.get('stage') == 'chapter_html_ready':
                if hasattr(report_agent, 'state') and hasattr(report_agent.state, 'html_content'):
                    task.html_content = report_agent.state.html_content

            """ææé¶æ®µäºä»¶é½éè¿åä¸ä¸ªæ¥å£ååï¼ä¿è¯æ¥å¿ä¸è´ï¿½?""
            task.publish_event(event_type, payload)
            # å¦æäºä»¶åå«è¿åº¦ä¿¡æ¯ï¼åæ­¥æ´æ°ä»»å¡è¿ï¿½?
            if event_type == 'progress' and 'progress' in payload:
                task.update_status("running", payload['progress'])

        task.update_status("running", 5)
        task.publish_event('stage', {'message': 'ä»»å¡å·²å¯å¨ï¼æ­£å¨æ£æ¥è¾å¥æï¿½?, 'stage': 'prepare'})

        # æ£æ¥è¾å¥æï¿½?
        check_result = check_engines_ready(task_id=task.task_id)
        if not check_result['ready']:
            task.update_status("error", 0, f"è¾å¥æä»¶æªåå¤å°±ï¿½? {check_result.get('missing_files', [])}")
            return

        task.publish_event('stage', {
            'message': 'è¾å¥æä»¶æ£æ¥éè¿ï¼åå¤è½½å¥åï¿½?,
            'stage': 'io_ready',
            'files': check_result.get('latest_files', {})
        })

        # å è½½è¾å¥æä»¶
        content = report_agent.load_input_files(check_result['latest_files'])
        task.publish_event('stage', {'message': 'æºæ°æ®å è½½å®æï¼å¯å¨çææµç¨', 'stage': 'data_loaded'})

        # ï¿½?seed_context æ³¨å¥ï¿½?forum_logs ä¸­ï¼å¦æå­å¨ï¼ï¼ä½ä¸ºæé«ä¼åçº§çè¡¥åä¿¡ï¿½?
        if task.seed_context:
            logger.info(f"æ³¨å¥ç§å­æä»¶ä¸ä¸æå°æ¥åå¼æ, é¿åº¦: {len(task.seed_context)}")
            seed_supplement = (
                "\n\n=======================================================\n"
                "ãç³»ç»çº§è¡¥åï¼ç¨æ·ä¸ä¼ çç»å¯¹çå®ç§å­ææï¼æé«ä¼åçº§äºå®åºåï¼n"
                "æç¤ºï¼è¿é¨ååå®¹æ¯ç¨æ·æå¨ä¸ä¼ çç¡®åèµæï¼ä½ å¯ä»¥å°å¶ä½ä¸ºåèèµæå¼ç¨n"
                f"ä¿¡æ¯æºæ ï¿½?Title): {task.seed_filename}\n"
                f"åå§é¾æ¥(URL): {task.seed_url}\n"
                "=======================================================\n"
                f"{task.seed_context}\n\n"
            )
            content['forum_logs'] = seed_supplement + content.get('forum_logs', '')

        # çææ¥åï¼éå¸¦ååºéè¯ï¼ç¼è§£ç¬æ¶ç½ç»æå¨ï¿½?
        for attempt in range(1, 3):
            try:
                task.publish_event('stage', {
                    'message': f'æ­£å¨è°ç¨ReportAgentçææ¥åï¼ç¬¬{attempt}æ¬¡å°è¯ï¼',
                    'stage': 'agent_running',
                    'attempt': attempt
                })
                generation_result = report_agent.generate_report(
                    query=query,
                    reports=content['reports'],
                    forum_logs=content['forum_logs'],
                    custom_template=custom_template,
                    save_report=True,
                    stream_handler=stream_handler
                )
                break
            except ChapterJsonParseError as err:
                hint_message = "å°è¯å°Report EngineçAPIæ´æ¢ä¸ºç®åæ´å¼ºãä¸ä¸ææ´é¿çLLM"
                task.publish_event('warning', {
                    'message': hint_message,
                    'stage': 'agent_running',
                    'attempt': attempt,
                    'reason': 'chapter_json_parse',
                    'error': str(err),
                    'task': task.to_dict(),
                })
                raise ChapterJsonParseError(hint_message) from err
            except CancelGenerationException:
                # å¦ææ¯ç¨æ·åæ¶ï¼åä¸è¿è¡éè¯ï¼ç´æ¥æåºå°å¤å±å¤ç
                raise
            except Exception as err:
                # å°éè¯¯å³æ¶æ¨éè³åç«¯ï¼æ¹ä¾¿è§å¯éè¯ç­ï¿½?
                task.publish_event('warning', {
                    'message': f'ReportAgentæ§è¡å¤±è´¥: {str(err)}',
                    'stage': 'agent_running',
                    'attempt': attempt
                })
                if attempt == 2:
                    raise
                # ç®åçææ°éé¿ï¼é²æ­¢é¢ç¹è§¦åéæµï¼åä½ç§ï¿½?
                backoff = min(5 * attempt, 15)
                task.publish_event('stage', {
                    'message': f'{backoff} ç§åéè¯çæä»»å¡',
                    'stage': 'retry_wait',
                    'wait_seconds': backoff
                })
                time.sleep(backoff)

        if isinstance(generation_result, dict):
            html_report = generation_result.get('html_content', '')
        else:
            html_report = generation_result

        task.publish_event('stage', {'message': 'æ¥åçæå®æ¯ï¼åå¤æä¹å', 'stage': 'persist'})

        # ä¿å­ç»æ
        task.html_content = html_report
        if isinstance(generation_result, dict):
            task.report_file_path = generation_result.get('report_filepath', '')
            task.report_file_relative_path = generation_result.get('report_relative_path', '')
            task.report_file_name = generation_result.get('report_filename', '')
            task.state_file_path = generation_result.get('state_filepath', '')
            task.state_file_relative_path = generation_result.get('state_relative_path', '')
            task.ir_file_path = generation_result.get('ir_filepath', '')
            task.ir_file_relative_path = generation_result.get('ir_relative_path', '')
            
        # æ¥åçææååï¼æ´æ°æä»¶åºåï¼é²æ­¢åç«¯æ éå¾ªç¯è§¦åèªå¨çï¿½?
        try:
            if report_agent:
                report_agent._initialize_file_baseline()
        except Exception as e:
            logger.error(f"æ´æ°æä»¶åºåå¤±è´¥: {e}")

        task.publish_event('html_ready', {
            'message': 'HTMLæ¸²æå®æï¼å¯å·æ°é¢è§',
            'report_file': task.report_file_relative_path or task.report_file_path,
            'state_file': task.state_file_relative_path or task.state_file_path,
            'task': task.to_dict(),
        })
        task.update_status("completed", 100)
        task.publish_event('completed', {
            'message': 'ä»»å¡å®æ',
            'duration_seconds': (task.updated_at - task.created_at).total_seconds(),
            'report_file': task.report_file_relative_path or task.report_file_path,
            'task': task.to_dict(),
        })

    except CancelGenerationException:
        task.update_status("cancelled", 0, "ç¨æ·ä¸»å¨åæ¶äºçï¿½?)
        task.publish_event('stage', {'message': 'çæå·²åï¿½?, 'stage': 'cancelled'})
        logger.info(f"ä»»å¡ {task.task_id} å·²è¢«ç¨æ·åæ¶")
        with task_lock:
            if current_task and current_task.task_id == task.task_id:
                current_task = None
    except Exception as e:
        logger.exception(f"æ¥åçæè¿ç¨ä¸­åçéï¿½? {str(e)}")
        task.update_status("error", 0, str(e))
        task.publish_event('error', {
            'message': str(e),
            'stage': 'failed',
            'task': task.to_dict(),
        })
        # åªå¨åºéæ¶æ¸çä»»ï¿½?
        with task_lock:
            if current_task and current_task.task_id == task.task_id:
                current_task = None


import tempfile
from backend.engines.insight.tools.keyword_optimizer import KeywordOptimizer

@report_bp.route('/seed/<seed_id>', methods=['GET'])
def get_seed_content(seed_id: str):
    """
    æä¾å¨çº¿é¢è§ç¨æ·ä¸ä¼ ï¿½?Seed åå®¹çæ¥å£ï¿½?
    åç«¯å¯ä»¥éè¿å¼¹çªææ°æ ç­¾é¡µè°ç¨è¯¥æ¥å£æ¥ççº¯ææ¬æ°æ®ï¿½?
    """
    try:
        # å®å¨æ ¡éªï¼é²æ­¢ç®å½ç©¿ï¿½?
        if ".." in seed_id or "/" in seed_id or "\\" in seed_id:
            return jsonify({'success': False, 'error': 'æ æï¿½?seed_id'}), 400

        seed_path = Path(settings.OUTPUT_DIR) / 'seeds' / f"{seed_id}.json"
        if not seed_path.exists():
            # å¼å®¹æ§çï¿½?.txt
            old_path = Path(settings.OUTPUT_DIR) / 'seeds' / f"{seed_id}.txt"
            if not old_path.exists():
                return jsonify({'success': False, 'error': 'Seed æä»¶ä¸å­å¨æå·²è¿ï¿½?}), 404
            content = old_path.read_text(encoding='utf-8')
            return Response(content, mimetype='text/plain')

        try:
            data = json.loads(seed_path.read_text(encoding='utf-8'))
            content = data.get('text', '')
            return Response(content, mimetype='text/plain')
        except Exception as e:
            logger.error(f"è§£æ Seed JSON å¤±è´¥: {e}")
            return jsonify({'success': False, 'error': 'è§£ææ°æ®æ ¼å¼å¤±è´¥'}), 500
    except Exception as e:
        logger.error(f"è¯»å Seed åå®¹å¤±è´¥: {e}")
        return jsonify({'success': False, 'error': 'è¯»ååå®¹æ¶åçéï¿½?}), 500

@report_bp.route('/analyze_seed', methods=['POST'])
def analyze_seed():
    """
    å¤çä¸ä¼ çç§å­éä»¶ï¼æåææ¬å¹¶ç»ååæ¥è¯¢çæä¼åå³é®è¯ï¿½?
    æ¯æ .txt, .md, .pdf, .doc, .docx
    """
    try:
        query = request.form.get('query', '').strip()
        if not query:
            return jsonify({'success': False, 'error': 'æªæä¾åå§æ¥ï¿½?}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'error': 'æªæä¾éï¿½?}), 400

        combined_text = []
        for file in files:
            filename = file.filename.lower()
            ext = os.path.splitext(filename)[1]
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp:
                file.save(temp.name)
                temp_path = temp.name

            try:
                extracted = ""
                if ext in ['.txt', '.md']:
                    with open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
                        extracted = f.read()
                elif ext == '.pdf':
                    doc = fitz.open(temp_path)
                    for page in doc:
                        extracted += page.get_text() + "\n"
                    doc.close()
                elif ext in ['.doc', '.docx']:
                    doc = docx.Document(temp_path)
                    extracted = "\n".join([para.text for para in doc.paragraphs])
                else:
                    logger.warning(f"ä¸æ¯æçæä»¶æ ¼å¼: {ext}")
                    
                if extracted.strip():
                    # ç¹æä¸ºéä»¶æ¼è£ä¸ä¸ªåï¿½?URL æ ¼å¼ï¿½?LLM å¼ç¨
                    fake_url = f"file:///{file.filename}"
                    combined_text.append(f"--- éä»¶æ é¢: {file.filename} ---\nURL: {fake_url}\n{extracted.strip()}")
            except Exception as e:
                logger.error(f"è§£æéä»¶ {file.filename} å¤±è´¥: {e}")
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        seed_context = "\n\n".join(combined_text)
        if not seed_context:
            return jsonify({'success': False, 'error': 'æ æ³ä»éä»¶ä¸­æåä»»ä½ææ¬'}), 400

        # è·åæä»¶åç¨äºå±ï¿½?
        file_names = [f.filename for f in files]
        primary_filename = file_names[0] if file_names else "ä¸ä¼ çéï¿½?

        # æªæ­è¿é¿ææ¬ï¼é¿åå¤§æ¨¡åTokençç¸ï¼è¿éåï¿½?5000å­ç¬¦ä½ä¸ºä¸ä¸æåèï¼
        context_for_optimizer = seed_context[:15000]

        # è°ç¨å³é®è¯ä¼åå¨
        optimizer = KeywordOptimizer()
        prompt_context = (
            "ãä»¥ä¸æ¯ç¨æ·æä¾ççå®ç§å­éä»¶åå®¹ï¼è¯·éç¹æåå¶ä¸­çå®ä½åè¯ãäºä»¶åæ ¸å¿çç¹ï¿½?
            "ç¡®ä¿çæçå³é®è¯ä¸è±ç¦»è¿äºäºå®éç¹n\n" + context_for_optimizer
        )
        
        response = optimizer.optimize_keywords(query, prompt_context)
        
        if not response.success:
            return jsonify({'success': False, 'error': response.error_message}), 500

        # å°å®æ´ç seed_context ååæ°æ®ä¿å­å°ä¸´æ¶ç®å½ï¼ä¾åç»­çææ¥åæ¶è°ç¨
        seed_id = f"seed_{int(time.time()*1000)}"
        seed_dir = Path(settings.OUTPUT_DIR) / 'seeds'
        seed_dir.mkdir(parents=True, exist_ok=True)
        
        # ç»æåä¿å­ï¼æ¹ä¾¿åç»­æ³¨å¥ä¸ºåæ³ä¿¡æ¯æº
        seed_data = {
            "text": seed_context,
            "filename": primary_filename,
            "fake_url": f"seed://{seed_id}/{primary_filename}",
            "timestamp": datetime.now().isoformat()
        }
        
        seed_path = seed_dir / f"{seed_id}.json"
        seed_path.write_text(json.dumps(seed_data, ensure_ascii=False), encoding='utf-8')

        # è§¦å seed å¥åºï¼å°å¶åå¥æ¬ï¿½?daily_news è¡¨å¹¶è®°å½ crawler æ¥å¿
        try:
            from backend.engines.insight.utils.data_ingestion import ingest_seed_data
            import threading
            threading.Thread(target=ingest_seed_data, args=(seed_id,), daemon=True).start()
        except Exception as e:
            logger.error(f"å¼æ­¥è§¦å seed å¥åºå¤±è´¥: {e}")

        return jsonify({
            'success': True,
            'optimized_keywords': response.optimized_keywords,
            'reasoning': response.reasoning,
            'seed_id': seed_id
        })

    except Exception as e:
        logger.exception(f"åæç§å­æä»¶å¤±è´¥: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@report_bp.route('/cancel/<task_id>', methods=['POST'])
def cancel_report(task_id: str):
    """
    åæ¶æ­£å¨çæçæ¥åä»»å¡ï¿½?
    """
    global current_task
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({'success': False, 'error': 'ä»»å¡ä¸å­ï¿½?}), 404

        if task.status == 'completed':
            return jsonify({'success': False, 'error': 'æ¥åå·²ç»çæå®æï¼æ æ³åï¿½?}), 400

        # è®¾ç½®åæ¶æ å¿ä½ï¼åå°çº¿ç¨ä¼å¨ä¸ä¸ï¿½?stream äºä»¶ç¹æåºå¼å¸¸ä¸­ï¿½?
        task.is_cancelled = True
        task.update_status("cancelled", 0, "ç¨æ·ä¸»å¨åæ¶äºçï¿½?)
        task.publish_event('stage', {'message': 'çæå·²åï¿½?, 'stage': 'cancelled'})
        
        with task_lock:
            if current_task and current_task.task_id == task_id:
                current_task = None
                
        return jsonify({'success': True, 'message': 'å·²åéåæ¶æï¿½?})
    except Exception as e:
        logger.error(f"åæ¶ä»»å¡å¤±è´¥: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@report_bp.route('/history', methods=['GET'])
def get_history_tasks():
    """
    è·ååå²ä»»å¡åè¡¨ï¿½?
    æ«æè¾åºç®å½ä¸çæææ¥åæä»¶ï¼è§£æåæ°æ®ï¼ææ¶é´ååºè¿åï¿½?
    """
    try:
        if not report_agent:
            return jsonify({'success': False, 'error': 'Report Engineæªåå§å'}), 500
            
        output_dir = Path(report_agent.config.OUTPUT_DIR)
        tasks = []
        
        if output_dir.exists():
            # æ«æææçæçæ¥åæä»¶
            html_files = list(output_dir.glob("final_report_*.html"))
            
            for html_path in html_files:
                try:
                    # ä»æä»¶åè§£æä¿¡æ¯: final_report_{query_safe}_{timestamp}.html
                    stem = html_path.stem
                    parts = stem.replace('final_report_', '').split('_')
                    
                    if len(parts) >= 2:
                        timestamp = f"{parts[-2]}_{parts[-1]}"
                        query_safe = '_'.join(parts[:-2])
                        task_id = f"recovered_file_{html_path.name}"
                        
                        task_data = {
                            'task_id': task_id,
                            'query': query_safe.replace('_', ' ') or 'åå²ä»»å¡',
                            'status': 'completed',
                            'progress': 100,
                            'created_at': datetime.fromtimestamp(html_path.stat().st_ctime).isoformat(),
                            'updated_at': datetime.fromtimestamp(html_path.stat().st_mtime).isoformat(),
                            'report_file_name': html_path.name,
                            'report_file_path': str(html_path.resolve()),
                            'has_result': True,
                            'report_file_ready': True,
                            'state_file_ready': False,
                            'ir_file_ready': False
                        }
                        
                        # æ£æ¥ç¸å³æï¿½?
                        ir_filename = f"report_ir_{query_safe}_{timestamp}.json"
                        ir_path = Path(report_agent.config.DOCUMENT_IR_OUTPUT_DIR) / ir_filename
                        if ir_path.exists():
                            task_data['ir_file_ready'] = True
                            task_data['ir_file_path'] = str(ir_path.resolve())
                            
                        state_filename = f"report_state_{query_safe}_{timestamp}.json"
                        state_path = output_dir / state_filename
                        if state_path.exists():
                            task_data['state_file_ready'] = True
                            task_data['state_file_path'] = str(state_path.resolve())
                            
                        # æ£æ¥å­å¼æçæ¥åæï¿½?
                        task_data['related_reports'] = []
                        engine_dirs = {
                            'insight': 'insight_engine_streamlit_reports',
                            'media': 'media_engine_streamlit_reports',
                            'query': 'query_engine_streamlit_reports'
                        }
                        
                        for engine_name, engine_dir in engine_dirs.items():
                            engine_report_name = f"deep_search_report_{query_safe}_{timestamp}.md"
                            # å­å¼æçæ¥åçæå¨é¡¹ç®æ ¹ç®å½ä¸çåä¸ª engine_dir ä¸­ï¼èä¸æ¯å¨ final_reports ï¿½?
                            engine_report_path = Path(engine_dir) / engine_report_name
                            if engine_report_path.exists():
                                task_data['related_reports'].append({
                                    'engine': engine_name,
                                    'filename': engine_report_name,
                                    'path': str(engine_report_path.resolve())
                                })
                                
                        tasks.append(task_data)
                except Exception as e:
                    logger.warning(f"è§£æåå²ä»»å¡æä»¶å¤±è´¥ {html_path.name}: {e}")
                    
        # ææ´æ°æ¶é´ååºæå
        tasks.sort(key=lambda x: x['updated_at'], reverse=True)
        
        # å°åå­ä¸­è¿æ²¡æä¹åä½å·²å®æçä»»å¡ä¹åå¹¶è¿å»ï¼å»éï¿½?
        with task_lock:
            memory_tasks = [t.to_dict() for t in tasks_registry.values() if t.status == 'completed']
            
        # ç®åå»éï¼ä¼åä½¿ç¨åå­ä¸­çæ°æ®ï¼å¯è½åå«æ´å®æ´çåæ°æ®ï¿½?
        # ä½¿ç¨ report_file_name è¿è¡å»éï¼å ä¸ºä¸åç¯å¢ä¸çç»å¯¹è·¯å¾åç¸å¯¹è·¯å¾æ ¼å¼å¯è½ä¸å
        seen_names = {t.get('report_file_name'): t for t in memory_tasks if t.get('report_file_name')}
        final_tasks = memory_tasks.copy()
        
        for t in tasks:
            mem_task = seen_names.get(t.get('report_file_name'))
            if mem_task is None:
                final_tasks.append(t)
                seen_names[t.get('report_file_name')] = t
            else:
                # åå­ä¸­çä»»å¡å¯è½ç¼ºå° related_reports ä¿¡æ¯ï¼ä»ç£çè§£æçä»»å¡ä¸­è¡¥å
                if 'related_reports' not in mem_task or not mem_task['related_reports']:
                    mem_task['related_reports'] = t.get('related_reports', [])
                
        # åæ¬¡ææ¶é´æï¿½?
        final_tasks.sort(key=lambda x: x['updated_at'], reverse=True)

        return jsonify({
            'success': True,
            'tasks': final_tasks
        })
    except Exception as e:
        logger.exception(f"è·ååå²ä»»å¡åè¡¨å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/history/<task_id>', methods=['DELETE'])
def delete_history_task(task_id: str):
    """
    å é¤æå®çåå²ä»»å¡åå¶ç¸å³çæææ¥ååç¶ææä»¶ï¿½?
    
    åæ°:
        task_id: è¦å é¤çä»»å¡IDï¼å¦ææ¯æ¢å¤çä»»å¡ï¼åç¼éå¸¸ï¿½?'recovered_file_'
    """
    try:
        if not report_agent:
            return jsonify({'success': False, 'error': 'Report Engineæªåå§å'}), 500
            
        output_dir = Path(report_agent.config.OUTPUT_DIR)
        ir_output_dir = Path(report_agent.config.DOCUMENT_IR_OUTPUT_DIR)
        deleted_files = []
        
        # 1. å°è¯ä»åå­ä¸­è·åè¯¥ä»»å¡çä¿¡æ¯
        task = _get_task(task_id)
        
        # è·åæä»¶åæå®å¨åç¼
        html_file_name = ""
        if task and task.report_file_name:
            html_file_name = task.report_file_name
        elif task_id.startswith('recovered_file_'):
            html_file_name = task_id.replace('recovered_file_', '')
        
        if html_file_name:
            # æ¾å° HTML æ¥åæä»¶
            html_path = output_dir / html_file_name
            if html_path.exists():
                html_path.unlink()
                deleted_files.append(html_file_name)
            
            # è§£ææ¶é´æ³åæ¥è¯¢è¯ï¼å°è¯å é¤å³èï¿½?IR ï¿½?State æä»¶
            stem = Path(html_file_name).stem
            parts = stem.replace('final_report_', '').split('_')
            if len(parts) >= 2:
                timestamp = f"{parts[-2]}_{parts[-1]}"
                query_safe = '_'.join(parts[:-2])
                
                ir_filename = f"report_ir_{query_safe}_{timestamp}.json"
                ir_path = ir_output_dir / ir_filename
                if ir_path.exists():
                    ir_path.unlink()
                    deleted_files.append(ir_filename)
                    
                state_filename = f"report_state_{query_safe}_{timestamp}.json"
                state_path = output_dir / state_filename
                if state_path.exists():
                    state_path.unlink()
                    deleted_files.append(state_filename)
                
                # å é¤å­å¼æçæçå³èæ¥å
                engine_dirs = {
                    'insight': 'insight_engine_streamlit_reports',
                    'media': 'media_engine_streamlit_reports',
                    'query': 'query_engine_streamlit_reports'
                }
                for engine_name, engine_dir in engine_dirs.items():
                    engine_report_name = f"deep_search_report_{query_safe}_{timestamp}.md"
                    engine_report_path = Path(engine_dir) / engine_report_name
                    if engine_report_path.exists():
                        engine_report_path.unlink()
                        deleted_files.append(f"{engine_dir}/{engine_report_name}")
                    
                    # åæ¶å é¤å¯è½çç¶ææï¿½?
                    engine_state_name = f"state_{query_safe}_{timestamp}.json"
                    engine_state_path = Path(engine_dir) / engine_state_name
                    if engine_state_path.exists():
                        engine_state_path.unlink()
                        deleted_files.append(f"{engine_dir}/{engine_state_name}")
        
        # ä»åå­ä¸­ç§»é¤
        with task_lock:
            if task_id in tasks_registry:
                tasks_registry.pop(task_id)
        
        return jsonify({
            'success': True,
            'message': 'ä»»å¡åç¸å³æä»¶å·²å é¤',
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        logger.exception(f"å é¤åå²ä»»å¡å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/status', methods=['GET'])
def get_status():
    """
    è·åReport Engineç¶æï¼åæ¬å¼æå°±ç»ªæåµä¸å½åä»»å¡ä¿¡æ¯ï¿½?

    è¿å:
        Response: JSONç»æåå«initialized/engines_ready/å½åä»»å¡ç­ï¿½?
    """
    try:
        task_id = request.args.get('task_id')
        engines_status = check_engines_ready(task_id=task_id)

        # ç§»é¤èªå¨ååºææ°åå²æä»¶çé»è¾ï¼é¿åæ°ä»»å¡å¼å§åæ¾ç¤ºæ§æ¥ï¿½?
        # ï¼å¦æéè¦æ¥çåå²æ¥åï¼è¯·ä½¿ç¨åå²è®°å½åè¡¨åè½ï¼
        task_data = current_task.to_dict() if current_task else None

        return jsonify({
            'success': True,
            'initialized': report_agent is not None,
            'engines_ready': engines_status['ready'],
            'files_found': engines_status.get('files_found', []),
            'missing_files': engines_status.get('missing_files', []),
            'current_task': task_data
        })
    except Exception as e:
        logger.exception(f"è·åReport Engineç¶æå¤±ï¿½? {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/generate', methods=['POST'])
def generate_report():
    """
    å¼å§çææ¥åï¿½?

    è´è´£æéãåå»ºåå°çº¿ç¨ãæ¸ç©ºæ¥å¿å¹¶è¿åSSEå°åï¿½?

    è¯·æ±ï¿½?
        query: æ¥åä¸»é¢ï¼å¯éï¼ï¿½?
        custom_template: èªå®ä¹æ¨¡æ¿å­ç¬¦ä¸²ï¼å¯éï¼ï¿½?

    è¿å:
        Response: JSONï¼åï¿½?task_id ï¿½?SSE stream urlï¿½?
    """
    global current_task

    try:
        # æ£æ¥æ¯å¦æä»»å¡å¨è¿ï¿½?
        with task_lock:
            if current_task and current_task.status == "running":
                return jsonify({
                    'success': False,
                    'error': 'å·²ææ¥åçæä»»å¡å¨è¿è¡ä¸­',
                    'current_task': current_task.to_dict()
                }), 400

            # å¦ææå·²å®æçä»»å¡ï¼æ¸çï¿½?
            if current_task and current_task.status in ["completed", "error"]:
                current_task = None

        # è·åè¯·æ±åæ°
        data = request.get_json() or {}
        if not isinstance(data, dict):
            logger.warning("generate_report æ¥æ¶å°éå¯¹è±¡JSONè´è½½ï¼å·²å¿½ç¥åå§åå®¹")
            data = {}
        query = data.get('query', 'æºè½èæåææ¥å')
        custom_template = data.get('custom_template', '')
        seed_id = data.get('seed_id', '')
        
        # ç²¾ç®ä»»å¡IDçæé»è¾ï¿½?ä¸ªæ±ï¿½?+ 6ä¸ªæ¥ææ°ï¿½?+ 4ä¸ªéæºæ°ï¿½?
        import re
        import random
        import string
        
        # æåæ±å­ï¼ä¸ï¿½?ä¸ªç¨é»è®¤æ±å­è¡¥é½
        chinese_chars = re.sub(r'[^\u4e00-\u9fa5]', '', query)
        if len(chinese_chars) < 6:
            chinese_chars += 'èæåæç ç©¶æ¥å'
        short_name = chinese_chars[:6]
        
        # 6ä¸ªæ¥ææ°ï¿½? YYMMDD
        date_str = datetime.now().strftime('%y%m%d')
        
        # 4ä¸ªéæºæ°ï¿½?
        short_code = ''.join(random.choices(string.digits, k=4))
        
        default_task_id = f"{short_name}{date_str}{short_code}"
        
        task_id = data.get('task_id') or default_task_id

        # æ¸ç©ºæ¥å¿æä»¶
        clear_report_log()

        # æ£æ¥Report Engineæ¯å¦åå§ï¿½?
        if not report_agent:
            return jsonify({
                'success': False,
                'error': 'Report Engineæªåå§å'
            }), 500

        # æ£æ¥è¾å¥æä»¶æ¯å¦åå¤å°±ï¿½?
        engines_status = check_engines_ready(task_id=task_id)
        if not engines_status['ready']:
            return jsonify({
                'success': False,
                'error': 'è¾å¥æä»¶æªåå¤å°±ï¿½?,
                'missing_files': engines_status.get('missing_files', [])
            }), 400

        # åå»ºæ°ä»»ï¿½?
        task = ReportTask(query, task_id, custom_template)

        # å°è¯è¯»åç§å­æä»¶ä¸ä¸ï¿½?
        if seed_id:
            seed_path = Path(settings.OUTPUT_DIR) / 'seeds' / f"{seed_id}.json"
            try:
                if seed_path.exists():
                    seed_data = json.loads(seed_path.read_text(encoding='utf-8'))
                    task.seed_context = seed_data.get('text', '')
                    # ç»æåä¿å­æä»¶ååä¼ªé URLï¼ç¨äºåç»­åè£ä¸º Search ç»æ
                    task.seed_filename = seed_data.get('filename', 'ä¸ä¼ çéï¿½?)
                    task.seed_url = seed_data.get('fake_url', f"seed://{seed_id}/attachment")
                    logger.info(f"ä»»å¡ {task_id} å·²æåå è½½ç§å­ä¸ä¸æ {seed_id} (JSON)ï¼å¤§ï¿½? {len(task.seed_context)} å­ç¬¦")
                else:
                    # å¼å®¹æ§çï¿½?
                    old_path = Path(settings.OUTPUT_DIR) / 'seeds' / f"{seed_id}.txt"
                    if old_path.exists():
                        task.seed_context = old_path.read_text(encoding='utf-8')
                        task.seed_filename = "ä¸ä¼ çéï¿½?
                        task.seed_url = f"seed://{seed_id}/attachment"
                        logger.info(f"ä»»å¡ {task_id} å·²æåå è½½ç§å­ä¸ä¸æ {seed_id} (TXT)ï¼å¤§ï¿½? {len(task.seed_context)} å­ç¬¦")
            except Exception as e:
                logger.error(f"è¯»åç§å­ä¸ä¸ï¿½?{seed_id} å¤±è´¥: {e}")

        with task_lock:
            current_task = task
            tasks_registry[task_id] = task
            _prune_task_history_locked()

        # ï¿½?task_id éä¼ ï¿½?report_agent ï¿½?state
        if report_agent:
            report_agent.state.task_id = task_id

        # éè¿ä¸»å¨æ¨épendingäºä»¶åç¥åç«¯ä»»å¡å·²ç»æé
        task.publish_event(
            'status',
            {
                'status': task.status,
                'progress': task.progress,
                'message': 'ä»»å¡å·²æéï¼ç­å¾èµæºç©ºé²',
                'task': task.to_dict(),
            }
        )

        # å¨åå°çº¿ç¨ä¸­è¿è¡æ¥åçæ
        thread = threading.Thread(
            target=run_report_generation,
            args=(task, query, custom_template),
            daemon=True
        )
        thread.start()

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'æ¥åçæå·²å¯ï¿½?,
            'task': task.to_dict(),
            'stream_url': f"/api/report/stream/{task_id}"
        })

    except Exception as e:
        logger.exception(f"å¼å§çææ¥åå¤±ï¿½? {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/progress/<task_id>', methods=['GET'])
def get_progress(task_id: str):
    """
    è·åæ¥åçæè¿åº¦ï¼è¥ä»»å¡è¢«æ¸çåè¿åä¸ä¸ªå®ææååºï¿½?

    åæ°:
        task_id: ä»»å¡å¯ä¸æ è¯ï¿½?

    è¿å:
        Response: JSONåå«ä»»å¡å½åç¶æï¿½?
    """
    try:
        task = _get_task(task_id)
        if not task:
            # å¦æä»»å¡ä¸å­å¨ï¼å¯è½æ¯åå²è®°å½å·²è¢«æ¸çï¼åä¼ ä¸ä¸ªå®ææåï¿½?
            return jsonify({
                'success': True,
                'task': {
                    'task_id': task_id,
                    'status': 'completed',
                    'progress': 100,
                    'error_message': '',
                    'has_result': True,
                    'report_file_ready': False,
                    'report_file_name': '',
                    'report_file_path': '',
                    'state_file_ready': False,
                    'state_file_path': ''
                }
            })

        return jsonify({
            'success': True,
            'task': task.to_dict()
        })

    except Exception as e:
        logger.exception(f"è·åæ¥åçæè¿åº¦å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/stream/<task_id>', methods=['GET'])
def stream_task(task_id: str):
    """
    åºäºSSEçå®æ¶æ¨éæ¥å£ï¿½?

    - èªå¨è¡¥åLast-Event-IDä¹åçåå²äºä»¶ï¼
    - å¨ææ§åéå¿è·³ä»¥é²ä»£çä¸­æ­ï¼
    - ä»»å¡ç»æåèªå¨æ³¨éçå¬ï¿½?

    åæ°:
        task_id: ä»»å¡å¯ä¸æ è¯ï¿½?

    è¿å:
        Response: `text/event-stream` ç±»åååºï¿½?
    """
    task = _get_task(task_id)
    if not task:
        return jsonify({'success': False, 'error': 'ä»»å¡ä¸å­ï¿½?}), 404

    last_event_header = request.headers.get('Last-Event-ID')
    try:
        last_event_id = int(last_event_header) if last_event_header else None
    except ValueError:
        last_event_id = None

    def client_disconnected() -> bool:
        """
        å°½æ©æ¢æµå®¢æ·ç«¯æ¯å¦å·²ç»æ­å¼ï¼é¿åç»§ç»­åå¥è§¦åBrokenPipeï¿½?

        eventlet ï¿½?Windows ä¸ä¼å¨å³é­è¿æ¥æ¶æåº ConnectionAbortedErrorï¿½?
        æåéåºçæå¨å¯ä»¥ç¼©åæ æä¹çæ¥å¿ï¿½?
        """
        try:
            env_input = request.environ.get('wsgi.input')
            return bool(getattr(env_input, 'closed', False))
        except Exception:
            return False

    def event_generator():
        """
        SSEäºä»¶çæå¨ï¿½?

        - è´è´£æ³¨åå¹¶æ¶è´¹å¯¹åºä»»å¡çäºä»¶éåï¿½?
        - ååæ¾åå²äºä»¶åæç»­çå¬å®æ¶äºä»¶ï¿½?
        - å¨ææ§åéå¿è·³å¹¶å¨ä»»å¡ç»æåèªå¨æ³¨éçå¬ï¿½?
        """
        queue = _register_stream(task_id)
        last_data_ts = time.time()
        try:
            # æ­çº¿éè¿åºæ¯ä¸ï¼åè¡¥ååå²äºä»¶ï¼ä¿è¯çé¢ç¶æä¸ï¿½?
            history = task.history_since(last_event_id)
            for event in history:
                yield _format_sse(event)
                if event.get('type') != 'heartbeat':
                    last_data_ts = time.time()

            finished = task.status in STREAM_TERMINAL_STATUSES
            while True:
                if finished:
                    break
                if client_disconnected():
                    logger.info(f"SSEå®¢æ·ç«¯å·²æ­å¼ï¼åæ­¢æ¨ï¿½? {task_id}")
                    break
                event = None
                try:
                    event = queue.get(timeout=STREAM_HEARTBEAT_INTERVAL)
                except Empty:
                    if task.status in STREAM_TERMINAL_STATUSES:
                        logger.info(f"ä»»å¡ {task_id} å·²ç»æä¸æ æ°äºä»¶ï¼SSEèªå¨æ¶å£")
                        break
                    heartbeat = {
                        'id': f"hb-{int(time.time() * 1000)}",
                        'type': 'heartbeat',
                        'task_id': task_id,
                        'timestamp': datetime.utcnow().isoformat() + 'Z',
                        'payload': {'status': task.status}
                    }
                    event = heartbeat
                if event is None:
                    logger.warning(f"SSEæ¨éè·åäºä»¶å¤±è´¥ï¼task {task_id}ï¼ï¼æåç»æ")
                    break

                try:
                    yield _format_sse(event)
                    if event.get('type') != 'heartbeat':
                        last_data_ts = time.time()
                except GeneratorExit:
                    logger.info(f"SSEçæå¨å³é­ï¼åæ­¢ä»»å¡ {task_id} æ¨ï¿½?)
                    break
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as exc:
                    logger.warning(f"SSEè¿æ¥è¢«å®¢æ·ç«¯ä¸­æ­ï¼task {task_id}ï¿½? {exc}")
                    break
                except Exception as exc:
                    event_type = event.get('type') if isinstance(event, dict) else 'unknown'
                    logger.exception(f"SSEæ¨éå¤±è´¥ï¼task {task_id}, event {event_type}ï¿½? {exc}")
                    break

                if event.get('type') in ("completed", "error", "cancelled"):
                    finished = True
                else:
                    finished = finished or task.status in STREAM_TERMINAL_STATUSES

                # ç»æä¸æå¤ä¿æ´»ä¸æ®µæ¶é´ï¼é²æ­¢åç«¯æ©å·²ç»æä½åå°å¾ªç¯æªéï¿½?
                if task.status in STREAM_TERMINAL_STATUSES:
                    idle_for = time.time() - last_data_ts
                    if idle_for > STREAM_IDLE_TIMEOUT:
                        logger.info(f"ä»»å¡ {task_id} å·²ç»æä¸ç©ºé² {int(idle_for)}sï¼ä¸»å¨å³é­SSE")
                        break
        finally:
            _unregister_stream(task_id, queue)

    response = Response(
        stream_with_context(event_generator()),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@report_bp.route('/result/<task_id>', methods=['GET'])
def get_result(task_id: str):
    """
    è·åæ¥åçæç»æï¼æå¢éé¢è§ï¼ï¿½?

    åæ°:
        task_id: ä»»å¡IDï¿½?

    è¿å:
        Response: JSONï¼åå«HTMLé¢è§ä¸æä»¶è·¯å¾ï¿½?
    """
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'ä»»å¡ä¸å­ï¿½?
            }), 404

        # ä¼åè¿ååå­ä¸­çå·²æ¸²ï¿½?HTMLï¼å³ä½¿ä»»å¡æªå®æï¼å®ç°"çæä¸ç« çä¸ç« "ï¼
        if getattr(task, 'html_content', None):
            return Response(task.html_content, mimetype='text/html')

        if task.status != "completed":
            # å¦æä»»å¡è¢«åæ¶æåºéï¼å°è¯ä»ç¡¬çä¸­æç´¢å¹éçåå²æä»¶ååº
            if report_agent:
                output_dir = Path(report_agent.config.OUTPUT_DIR)
                base_id = task_id.replace('recovered_file_', '').replace('final_report_', '').replace('.html', '')
                html_files = list(output_dir.glob(f"*{base_id}*.html"))
                if html_files:
                    latest_html = max(html_files, key=lambda p: p.stat().st_mtime)
                    try:
                        with open(latest_html, 'r', encoding='utf-8') as f:
                            return Response(f.read(), mimetype='text/html')
                    except Exception as e:
                        pass
                        
            return jsonify({
                'success': False,
                'error': 'æ¥åå°æªçæä»»ä½åå®¹',
                'task': task.to_dict()
            }), 400

        return Response(
            task.html_content,
            mimetype='text/html'
        )

    except Exception as e:
        logger.exception(f"è·åæ¥åçæç»æå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/result/<task_id>/json', methods=['GET'])
def get_result_json(task_id: str):
    """è·åæ¥åçæç»æï¼JSONæ ¼å¼ï¿½?""
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'ä»»å¡ä¸å­ï¿½?
            }), 404

        if task.status != "completed":
            # ååºæ¥è¯¢ç¡¬ç
            if report_agent:
                output_dir = Path(report_agent.config.OUTPUT_DIR)
                base_id = task_id.replace('recovered_file_', '').replace('final_report_', '').replace('.html', '')
                html_files = list(output_dir.glob(f"*{base_id}*.html"))
                if html_files:
                    latest_html = max(html_files, key=lambda p: p.stat().st_mtime)
                    try:
                        with open(latest_html, 'r', encoding='utf-8') as f:
                            return jsonify({
                                'success': True,
                                'task': task.to_dict(),
                                'html_content': f.read()
                            })
                    except Exception as e:
                        pass
                        
            return jsonify({
                'success': False,
                'error': 'æ¥åå°æªå®æ',
                'task': task.to_dict()
            }), 400

        return jsonify({
            'success': True,
            'task': task.to_dict(),
            'html_content': task.html_content
        })

    except Exception as e:
        logger.exception(f"è·åæ¥åçæç»æå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@report_bp.route('/download/<task_id>', methods=['GET'])
def download_report(task_id: str):
    """
    ä¸è½½å·²çæçæ¥åHTMLæä»¶æä¸­é´äº§ç©ï¿½?
    å¦ææ¯åå²ä»»å¡ï¼ä»æ¬å°æä»¶ç³»ç»ä¸­å¹éï¿½?
    """
    try:
        task = _get_task(task_id)
        
        # å¦æåå­ä¸­æ²¡æè¿ä¸ªä»»å¡ï¼å°è¯ä»ç¡¬çä¸­æç´¢å¹éçåå²æï¿½?
        if not task:
            # ï¿½?final_reports ï¿½?document_ir ç®å½éæ¾
            # task_id å¨æ­¤å¤å¯è½æ¯ï¿½?ID ä¹å¯è½æ¯å®æ´æä»¶ï¿½?
            base_id = task_id.replace('report_state_', '').replace('final_report_', '').replace('.json', '').replace('.html', '')
            
            # æ¯æä¸è½½ JSON (IRæ°æ®/ç¶ææ°ï¿½?
            if task_id.endswith('.json'):
                json_path = os.path.join(REPORT_DIR, task_id)
                if not os.path.exists(json_path):
                    json_path = os.path.join(REPORT_DIR, 'document_ir', task_id)
                
                if os.path.exists(json_path):
                    return send_file(
                        json_path,
                        mimetype='application/json',
                        as_attachment=True,
                        download_name=task_id
                    )
                return jsonify({'success': False, 'error': 'æªæ¾å°å¯¹åºçJSONåå²æä»¶'}), 404
            
            # å¦åé»è®¤æç´¢ HTML æç»æ¥ï¿½?
            html_files = list(Path(REPORT_DIR).glob(f"*{base_id}*.html"))
            if html_files:
                return send_file(
                    str(html_files[0]),
                    mimetype='text/html',
                    as_attachment=True,
                    download_name=html_files[0].name
                )
                
            return jsonify({
                'success': False,
                'error': 'ä»»å¡ä¸å­å¨ä¸æªæ¾å°å¯¹åºçåå²æ¥åæä»¶'
            }), 404

        if task.status != "completed" or not task.report_file_path:
            return jsonify({
                'success': False,
                'error': 'æ¥åå°æªå®ææå°æªä¿ï¿½?
            }), 400

        if not os.path.exists(task.report_file_path):
            return jsonify({
                'success': False,
                'error': 'æ¥åæä»¶ä¸å­å¨æå·²è¢«å é¤'
            }), 404

        download_name = task.report_file_name or os.path.basename(task.report_file_path)
        return send_file(
            task.report_file_path,
            mimetype='text/html',
            as_attachment=True,
            download_name=download_name
        )

    except Exception as e:
        logger.error(f"ä¸è½½æ¥åå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




@report_bp.route('/templates', methods=['GET'])
def get_templates():
    """
    è·åå¯ç¨æ¨¡æ¿åè¡¨ï¼ä¾¿äºåç«¯å±ç¤ºå¯éMarkdownéª¨æ¶ï¿½?

    è¿å:
        Response: JSONï¼ååºæ¨¡æ¿åï¿½?æè¿°/å¤§å°ï¿½?
    """
    try:
        if not report_agent:
            return jsonify({
                'success': False,
                'error': 'Report Engineæªåå§å'
            }), 500

        template_dir = settings.TEMPLATE_DIR
        templates = []

        if os.path.exists(template_dir):
            for filename in os.listdir(template_dir):
                if filename.endswith('.md'):
                    template_path = os.path.join(template_dir, filename)
                    try:
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        templates.append({
                            'name': filename.replace('.md', ''),
                            'filename': filename,
                            'description': content.split('\n')[0] if content else 'æ æï¿½?,
                            'size': len(content)
                        })
                    except Exception as e:
                        logger.exception(f"è¯»åæ¨¡æ¿å¤±è´¥ {filename}: {str(e)}")

        return jsonify({
            'success': True,
            'templates': templates,
            'template_dir': template_dir
        })

    except Exception as e:
        logger.exception(f"è·åå¯ç¨æ¨¡æ¿åè¡¨å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# éè¯¯å¤ç
@report_bp.errorhandler(404)
def not_found(error):
    """404ååºå¤çï¼ä¿è¯æ¥å£ç»ä¸è¿åJSONç»æ"""
    logger.exception(f"APIç«¯ç¹ä¸å­ï¿½? {str(error)}")
    return jsonify({
        'success': False,
        'error': 'APIç«¯ç¹ä¸å­ï¿½?
    }), 404


@report_bp.errorhandler(500)
def internal_error(error):
    """500ååºå¤çï¼æè·æªè¢«ä¸»å¨æè·çå¼å¸¸"""
    logger.exception(f"æå¡å¨åé¨éï¿½? {str(error)}")
    return jsonify({
        'success': False,
        'error': 'æå¡å¨åé¨éï¿½?
    }), 500


def clear_report_log():
    """
    æ¸ç©ºreport.logæä»¶ï¼æ¹ä¾¿æ°ä»»å¡åªæ¥çæ¬æ¬¡è¿è¡æ¥å¿ï¿½?

    è¿å:
        None
    """
    try:
        log_file = settings.LOG_FILE

        # ãä¿®å¤ãä½¿ç¨truncateèééæ°æå¼ï¼é¿åä¸loggerçæä»¶å¥æå²ï¿½?
        # è¿½å æ¨¡å¼æå¼ï¼ç¶åtruncateï¼ä¿ææä»¶å¥ææï¿½?
        with open(log_file, 'r+', encoding='utf-8') as f:
            f.truncate(0)  # æ¸ç©ºæä»¶åå®¹ä½ä¸å³é­æä»¶
            f.flush()      # ç«å³å·æ°

        logger.info(f"å·²æ¸ç©ºæ¥å¿æï¿½? {log_file}")
    except FileNotFoundError:
        # æä»¶ä¸å­å¨ï¼åå»ºç©ºæï¿½?
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('')
            logger.info(f"åå»ºæ¥å¿æä»¶: {log_file}")
        except Exception as e:
            logger.exception(f"åå»ºæ¥å¿æä»¶å¤±è´¥: {str(e)}")
    except Exception as e:
        logger.exception(f"æ¸ç©ºæ¥å¿æä»¶å¤±è´¥: {str(e)}")


@report_bp.route('/log', methods=['GET'])
def get_report_log():
    """
    è·åreport.logåå®¹ï¼å¹¶æè¡å»é¤ç©ºç½è¿åï¿½?

    ãä¿®å¤ãä¼åå¤§æä»¶è¯»åï¼æ·»å éè¯¯å¤çåæä»¶ï¿½?

    è¿å:
        Response: JSONï¼åå«ææ°æ¥å¿è¡æ°ç»ï¿½?
    """
    try:
        log_file = settings.LOG_FILE

        if not os.path.exists(log_file):
            return jsonify({
                'success': True,
                'log_lines': []
            })

        # ãä¿®å¤ãæ£æ¥æä»¶å¤§å°ï¼é¿åè¯»åè¿å¤§æä»¶å¯¼è´åå­é®é¢
        file_size = os.path.getsize(log_file)
        max_size = 10 * 1024 * 1024  # 10MBéå¶

        if file_size > max_size:
            # æä»¶è¿å¤§ï¼åªè¯»åæï¿½?0MB
            with open(log_file, 'rb') as f:
                f.seek(-max_size, 2)  # ä»æä»¶æ«å°¾å¾ï¿½?0MB
                # è·³è¿å¯è½ä¸å®æ´çç¬¬ä¸ï¿½?
                f.readline()
                content = f.read().decode('utf-8', errors='replace')
            lines = content.splitlines()
            logger.warning(f"æ¥å¿æä»¶è¿å¤§ ({file_size} bytes)ï¼ä»è¿åæï¿½?{max_size} bytes")
        else:
            # æ­£å¸¸å¤§å°ï¼å®æ´è¯»ï¿½?
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()

        # æ¸çè¡å°¾çæ¢è¡ç¬¦åç©ºï¿½?
        log_lines = [line.rstrip('\n\r') for line in lines if line.strip()]

        return jsonify({
            'success': True,
            'log_lines': log_lines
        })

    except PermissionError as e:
        logger.error(f"è¯»åæ¥å¿æéä¸è¶³: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'è¯»åæ¥å¿æéä¸è¶³'
        }), 403
    except UnicodeDecodeError as e:
        logger.error(f"æ¥å¿æä»¶ç¼ç éè¯¯: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'æ¥å¿æä»¶ç¼ç éè¯¯'
        }), 500
    except Exception as e:
        logger.exception(f"è¯»åæ¥å¿å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'è¯»åæ¥å¿å¤±è´¥: {str(e)}'
        }), 500


@report_bp.route('/log/clear', methods=['POST'])
def clear_log():
    """
    æå¨æ¸ç©ºæ¥å¿ï¼æä¾RESTå¥å£ä¾åç«¯ä¸é®éç½®ï¿½?

    è¿å:
        Response: JSONï¼æ è®°æ¯å¦æ¸çæåï¿½?
    """
    try:
        clear_report_log()
        return jsonify({
            'success': True,
            'message': 'æ¥å¿å·²æ¸ï¿½?
        })
    except Exception as e:
        logger.exception(f"æ¸ç©ºæ¥å¿å¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'æ¸ç©ºæ¥å¿å¤±è´¥: {str(e)}'
        }), 500


@report_bp.route('/export/md/<task_id>', methods=['GET'])
def export_markdown(task_id: str):
    """
    å¯¼åºæ¥åï¿½?Markdown æ ¼å¼ï¿½?

    åºäºå·²ä¿å­ç Document IR è°ç¨ MarkdownRendererï¼çææä»¶å¹¶è¿åä¸è½½ï¿½?
    """
    try:
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'ä»»å¡ä¸å­ï¿½?
            }), 404

        if task.status != 'completed':
            return jsonify({
                'success': False,
                'error': f'ä»»å¡æªå®æï¼å½åç¶ï¿½? {task.status}'
            }), 400

        if not task.ir_file_path or not os.path.exists(task.ir_file_path):
            return jsonify({
                'success': False,
                'error': 'IRæä»¶ä¸å­å¨ï¼æ æ³çæMarkdown'
            }), 404

        with open(task.ir_file_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        from .renderers import MarkdownRenderer
        renderer = MarkdownRenderer()
        # ä¼ å¥ ir_file_pathï¼ä¿®å¤åçå¾è¡¨ä¼èªå¨ä¿å­ï¿½?IR æä»¶
        markdown_text = renderer.render(document_ir, ir_file_path=task.ir_file_path)

        metadata = document_ir.get('metadata') if isinstance(document_ir, dict) else {}
        topic = (metadata or {}).get('topic') or (metadata or {}).get('title') or (metadata or {}).get('query') or task.query
        safe_topic = _safe_filename_segment(topic or 'report')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"report_{safe_topic}_{timestamp}.md"

        output_dir = Path(settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / filename
        md_path.write_text(markdown_text, encoding='utf-8')

        task.markdown_file_path = str(md_path.resolve())
        task.markdown_file_relative_path = os.path.relpath(task.markdown_file_path, os.getcwd())
        task.markdown_file_name = filename

        logger.info(f"å¯¼åºMarkdownå®æ: {md_path}")

        return send_file(
            task.markdown_file_path,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.exception(f"å¯¼åºMarkdownå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'å¯¼åºMarkdownå¤±è´¥: {str(e)}'
        }), 500


@report_bp.route('/export/pdf/<task_id>', methods=['GET'])
def export_pdf(task_id: str):
    """
    å¯¼åºæ¥åä¸ºPDFæ ¼å¼ï¿½?

    ä»IR JSONæä»¶çæä¼åçPDFï¼æ¯æèªå¨å¸å±è°æ´ï¿½?

    åæ°:
        task_id: ä»»å¡ID

    æ¥è¯¢åæ°:
        optimize: æ¯å¦å¯ç¨å¸å±ä¼åï¼é»è®¤trueï¿½?

    è¿å:
        Response: PDFæä»¶æµæéè¯¯ä¿¡æ¯
    """
    try:
        # æ£ï¿½?Pango ä¾èµ
        from .utils.dependency_check import check_pango_available
        pango_available, pango_message = check_pango_available()
        if not pango_available:
            return jsonify({
                'success': False,
                'error': 'PDF å¯¼åºåè½ä¸å¯ç¨ï¼ç¼ºå°ç³»ç»ä¾èµ',
                'details': 'è¯·æ¥çæ ¹ç®å½ README.md "æºç å¯å¨"çç¬¬äºæ­¥ï¼PDF å¯¼åºä¾èµï¼äºè§£å®è£æ¹ï¿½?,
                'help_url': 'https://github.com/666ghj/BettaFish#2-å®è£-pdf-å¯¼åºæéç³»ç»ä¾èµå¯ï¿½?,
                'system_message': pango_message
            }), 503

        # è·åä»»å¡ä¿¡æ¯
        task = _get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'error': 'ä»»å¡ä¸å­ï¿½?
            }), 404

        # æ£æ¥ä»»å¡æ¯å¦å®ï¿½?
        if task.status != 'completed':
            return jsonify({
                'success': False,
                'error': f'ä»»å¡æªå®æï¼å½åç¶ï¿½? {task.status}'
            }), 400

        # è·åIRæä»¶è·¯å¾
        if not task.ir_file_path or not os.path.exists(task.ir_file_path):
            return jsonify({
                'success': False,
                'error': 'IRæä»¶ä¸å­ï¿½?
            }), 404

        # è¯»åIRæ°æ®
        with open(task.ir_file_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)

        # æ£æ¥æ¯å¦å¯ç¨å¸å±ä¼å
        optimize = request.args.get('optimize', 'true').lower() == 'true'

        # åå»ºPDFæ¸²æå¨å¹¶çæPDF
        from .renderers import PDFRenderer
        renderer = PDFRenderer()

        logger.info(f"å¼å§å¯¼åºPDFï¼ä»»å¡ID: {task_id}ï¼å¸å±ä¼å: {optimize}")

        # çæPDFå­èï¿½?
        pdf_bytes = renderer.render_to_bytes(document_ir, optimize_layout=optimize)

        # ç¡®å®ä¸è½½æä»¶ï¿½?
        topic = document_ir.get('metadata', {}).get('topic', 'report')
        pdf_filename = f"report_{topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # è¿åPDFæä»¶
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{pdf_filename}"',
                'Content-Type': 'application/pdf'
            }
        )

    except Exception as e:
        logger.exception(f"å¯¼åºPDFå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'å¯¼åºPDFå¤±è´¥: {str(e)}'
        }), 500


@report_bp.route('/export/pdf-from-ir', methods=['POST'])
def export_pdf_from_ir():
    """
    ä»IR JSONç´æ¥å¯¼åºPDFï¼ä¸éè¦ä»»å¡IDï¼ï¿½?

    éç¨äºåç«¯ç´æ¥ä¼ éIRæ°æ®çåºæ¯ï¿½?

    è¯·æ±ï¿½?
        {
            "document_ir": {...},  // Document IR JSON
            "optimize": true       // æ¯å¦å¯ç¨å¸å±ä¼åï¼å¯éï¼
        }

    è¿å:
        Response: PDFæä»¶æµæéè¯¯ä¿¡æ¯
    """
    try:
        # æ£ï¿½?Pango ä¾èµ
        from .utils.dependency_check import check_pango_available
        pango_available, pango_message = check_pango_available()
        if not pango_available:
            return jsonify({
                'success': False,
                'error': 'PDF å¯¼åºåè½ä¸å¯ç¨ï¼ç¼ºå°ç³»ç»ä¾èµ',
                'details': 'è¯·æ¥çæ ¹ç®å½ README.md "æºç å¯å¨"çç¬¬äºæ­¥ï¼PDF å¯¼åºä¾èµï¼äºè§£å®è£æ¹ï¿½?,
                'help_url': 'https://github.com/666ghj/BettaFish#2-å®è£-pdf-å¯¼åºæéç³»ç»ä¾èµå¯ï¿½?,
                'system_message': pango_message
            }), 503

        data = request.get_json() or {}
        if not isinstance(data, dict):
            logger.warning("export_pdf_from_ir è¯·æ±ä½ä¸æ¯JSONå¯¹è±¡")
            return jsonify({
                'success': False,
                'error': 'è¯·æ±ä½å¿é¡»æ¯JSONå¯¹è±¡'
            }), 400

        if not data or 'document_ir' not in data:
            return jsonify({
                'success': False,
                'error': 'ç¼ºå°document_iråæ°'
            }), 400

        document_ir = data['document_ir']
        optimize = data.get('optimize', True)

        # åå»ºPDFæ¸²æå¨å¹¶çæPDF
        from .renderers import PDFRenderer
        renderer = PDFRenderer()

        logger.info(f"ä»IRç´æ¥å¯¼åºPDFï¼å¸å±ä¼å: {optimize}")

        # çæPDFå­èï¿½?
        pdf_bytes = renderer.render_to_bytes(document_ir, optimize_layout=optimize)

        # ç¡®å®ä¸è½½æä»¶ï¿½?
        topic = document_ir.get('metadata', {}).get('topic', 'report')
        pdf_filename = f"report_{topic}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        # è¿åPDFæä»¶
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{pdf_filename}"',
                'Content-Type': 'application/pdf'
            }
        )

    except Exception as e:
        logger.exception(f"ä»IRå¯¼åºPDFå¤±è´¥: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'å¯¼åºPDFå¤±è´¥: {str(e)}'
        }), 500
