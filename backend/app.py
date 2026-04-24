"""
Flaskä¸»åºç¨ - ç»ä¸ç®¡çä¸ä¸ªStreamlitåºç¨
"""

import os
import sys
import os
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
from dotenv import load_dotenv

# å è½½ç¯å¢åé
load_dotenv()

# ãä¿®å¤ãæ¶åºåæ­¥é®é¢
# 1. å¨ Windows æ¬å°è¿è¡æ¶ï¼ç§»é¤å¯è½è¢«éè¯¯æ³¨å¥ç UTC æ¶åº
if os.name == 'nt' and 'TZ' in os.environ:
    del os.environ['TZ']
# 2. å¨ Docker å®¹å¨ (Linux) ä¸­è¿è¡æ¶ï¼å¦ææ²¡ææ å°å®¿ä¸»æºæ¶åºï¼é»è®¤å°å¶è®¾ç½®ä¸ºä¸å«åºï¼åäº¬æ¶é´ï¼
elif os.name == 'posix':
    if 'TZ' not in os.environ or os.environ['TZ'] == 'UTC':
        os.environ['TZ'] = 'Asia/Shanghai'
        import time
        if hasattr(time, 'tzset'):
            time.tzset()

# ãä¿®å¤ãå°½æ©è®¾ç½®ç¯å¢åéï¼ç¡®ä¿æææ¨¡åé½ä½¿ç¨æ ç¼å²æ¨¡å¼
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'  # ç¦ç¨Pythonè¾åºç¼å²ï¼ç¡®ä¿æ¥å¿å®æ¶è¾åº

# ãä¿®å¤ãè®¾ç½® HF_ENDPOINTï¼ä¿è¯å½åä¸è½½ HuggingFace æ¨¡åä¸å¡æ­»
if os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT")
elif "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# ãä¿®å¤ãå±è½ transformers åºæ¼äººçåé¨ alias è­¦å
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
import warnings
warnings.filterwarnings("ignore", module="transformers")

import subprocess
import time
import threading
from datetime import datetime
from queue import Queue
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import atexit
import requests
from loguru import logger
import importlib
from pathlib import Path
from MindSpider.main import MindSpider

# å¯¼å¥ReportEngine
try:
    from backend.engines.report.flask_interface import report_bp, initialize_report_engine
    REPORT_ENGINE_AVAILABLE = True
except (ImportError, SyntaxError, UnicodeDecodeError, Exception) as e:
    logger.error(f"ReportEngineå¯¼å¥å¤±è´¥: {e}")
    REPORT_ENGINE_AVAILABLE = False

# å¯¼å¥OpenAIå¼å®¹API Blueprint
try:
    from backend.api.routes.openai_compat import openai_bp
    OPENAI_COMPAT_AVAILABLE = True
except (ImportError, SyntaxError, UnicodeDecodeError, Exception) as e:
    logger.error(f"OpenAIå¼å®¹APIå¯¼å¥å¤±è´¥: {e}")
    OPENAI_COMPAT_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'Dedicated-to-creating-a-concise-and-versatile-public-opinion-analysis-platform'
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# eventlet å¨å®¢æ·ç«¯ä¸»å¨æ­å¼æ¶å¶å°ä¼æåº ConnectionAbortedErrorï¼è¿éåä¸æ¬¡é²å¾¡æ§åè£¹ï¼
# é¿åæ æä¹çå æ æ±¡ææ¥å¿ï¼ä»å¨ eventlet å¯ç¨æ¶å¯ç¨ï¼def _patch_eventlet_disconnect_logging():
    if sys.version_info >= (3, 12):
        return
    try:
        import eventlet.wsgi  # type: ignore
    except Exception as exc:  # pragma: no cover - ä»å¨çäº§ç¯å¢ææ
        logger.debug(f"eventlet ä¸å¯ç¨ï¼è·³è¿æ­å¼è¡¥ä¸: {exc}")
        return

    try:
        original_finish = eventlet.wsgi.HttpProtocol.finish  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover
        logger.debug(f"eventlet ç¼ºå° HttpProtocol.finishï¼è·³è¿æ­å¼è¡¥ä¸: {exc}")
        return

    def _safe_finish(self, *args, **kwargs):  # pragma: no cover - è¿è¡æ¶æä¼è§¦å
        try:
            return original_finish(self, *args, **kwargs)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            try:
                environ = getattr(self, 'environ', {}) or {}
                method = environ.get('REQUEST_METHOD', '')
                path = environ.get('PATH_INFO', '')
                logger.warning(f"å®¢æ·ç«¯å·²ä¸»å¨æ­å¼ï¼å¿½ç¥å¼å¸¸: {method} {path} ({exc})")
            except Exception:
                logger.warning(f"å®¢æ·ç«¯å·²ä¸»å¨æ­å¼ï¼å¿½ç¥å¼å¸¸: {exc}")
            return

    eventlet.wsgi.HttpProtocol.finish = _safe_finish  # type: ignore[attr-defined]
    logger.info("å·²å¯¹ eventlet è¿æ¥ä¸­æ­è¿è¡å®å¨é²æ¤")

_patch_eventlet_disconnect_logging()

# æ³¨åReportEngine Blueprint
if REPORT_ENGINE_AVAILABLE:
    app.register_blueprint(report_bp, url_prefix='/api/report')
    logger.info("ReportEngineæ¥å£å·²æ³¨å")
else:
    logger.info("ReportEngineä¸å¯ç¨ï¼è·³è¿æ¥å£æ³¨åå¹¶æ·»å éçº§è·¯ç±")
    @app.route('/api/report/status', methods=['GET'])
    def fallback_report_status():
        return jsonify({'success': False, 'initialized': False, 'error': 'ReportEngineä¸å¯ç¨'})

# æ³¨åOpenAIå¼å®¹API Blueprint
if OPENAI_COMPAT_AVAILABLE:
    app.register_blueprint(openai_bp, url_prefix='/v1')
    logger.info("OpenAIå¼å®¹APIå·²æ³¨å (POST /v1/chat/completions, GET /v1/models)")
else:
    logger.info("OpenAIå¼å®¹APIä¸å¯ç¨")


# åå»ºæ¥å¿ç®å½
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)


@app.route('/')
def landing_page():
    """Open WebUI æ¯å¯ä¸åç«¯ï¼æ­¤å¤ä»å API å¥åº·æ£æ¥å¥å£."""
    return jsonify({
        'name': 'New Radar API',
        'version': '2.0.0',
        'frontend': 'Open WebUI (port 3000)',
        'endpoints': {
            'chat': 'POST /v1/chat/completions',
            'models': 'GET /v1/models',
            'health': 'GET /v1/health',
            'sentiment': 'POST /v1/sentiment',
            'report_status': 'GET /api/report/status',
            'report_generate': 'POST /api/report/generate',
            'report_stream': 'GET /api/report/stream/<task_id>',
            'report_history': 'GET /api/report/history',
        }
    })


CONFIG_MODULE_NAME = 'config'
CONFIG_FILE_PATH = Path(__file__).resolve().parent / 'config.py'
CONFIG_KEYS = [
    'HOST',
    'PORT',
    'DB_DIALECT',
    'DB_HOST',
    'DB_PORT',
    'DB_USER',
    'DB_PASSWORD',
    'DB_NAME',
    'DB_CHARSET',
    'INSIGHT_ENGINE_API_KEY',
    'INSIGHT_ENGINE_BASE_URL',
    'INSIGHT_ENGINE_MODEL_NAME',
    'MEDIA_ENGINE_API_KEY',
    'MEDIA_ENGINE_BASE_URL',
    'MEDIA_ENGINE_MODEL_NAME',
    'QUERY_ENGINE_API_KEY',
    'QUERY_ENGINE_BASE_URL',
    'QUERY_ENGINE_MODEL_NAME',
    'REPORT_ENGINE_API_KEY',
    'REPORT_ENGINE_BASE_URL',
    'REPORT_ENGINE_MODEL_NAME',
    'FORUM_HOST_API_KEY',
    'FORUM_HOST_BASE_URL',
    'FORUM_HOST_MODEL_NAME',
    'KEYWORD_OPTIMIZER_API_KEY',
    'KEYWORD_OPTIMIZER_BASE_URL',
    'KEYWORD_OPTIMIZER_MODEL_NAME',
    'ANSPIRE_API_KEY',
    'ENABLE_ANSPIRE',
    'TAVILY_API_KEY',
    'ENABLE_TAVILY',
    'BOCHA_WEB_API_KEY',
    'ENABLE_BOCHA',
    'FIRECRAWL_API_KEY',
    'ENABLE_FIRECRAWL',
    'ENABLE_MEDIACRAWLER',
    'ENABLE_WEB_ACCESS',
    'OPENAI_API_KEY',
    'OPENAI_MODEL_NAME',
    'ENABLE_SENTIMENT_TOOL',
]


def _load_config_module():
    """Load or reload the config module to ensure latest values are available."""
    importlib.invalidate_caches()
    module = sys.modules.get(CONFIG_MODULE_NAME)
    try:
        if module is None:
            module = importlib.import_module(CONFIG_MODULE_NAME)
        else:
            module = importlib.reload(module)
    except ModuleNotFoundError:
        return None
    return module


def read_config_values():
    """Return the current configuration values that are exposed to the frontend."""
    try:
        # éæ°å è½½éç½®ä»¥è·åææ°ç Settings å®ä¾
        from backend.config import reload_settings, settings
        reload_settings()
        
        values = {}
        for key in CONFIG_KEYS:
            # ä» Pydantic Settings å®ä¾è¯»åå¼
            value = getattr(settings, key, None)
            # Convert to string for uniform handling on the frontend.
            if value is None:
                values[key] = ''
            else:
                values[key] = str(value)
        return values
    except Exception as exc:
        logger.exception(f"è¯»åéç½®å¤±è´¥: {exc}")
        return {}


def _serialize_config_value(value):
    """Serialize Python values back to a config.py assignment-friendly string."""
    if isinstance(value, bool):
        return 'True' if value else 'False'
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return 'None'

    value_str = str(value)
    escaped = value_str.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def write_config_values(updates):
    """Persist configuration updates to .env file (Pydantic Settings source)."""
    from pathlib import Path
    
    # ç¡®å® .env æä»¶è·¯å¾ï¼ä¸ config.py ä¸­çé»è¾ä¸è´ï¼
    project_root = Path(__file__).resolve().parent
    cwd_env = Path.cwd() / ".env"
    env_file_path = cwd_env if cwd_env.exists() else (project_root / ".env")
    
    # è¯»åç°æç .env æä»¶åå®¹
    env_lines = []
    env_key_indices = {}  # è®°å½æ¯ä¸ªé®å¨æä»¶ä¸­çç´¢å¼ä½ç½®
    if env_file_path.exists():
        env_lines = env_file_path.read_text(encoding='utf-8').splitlines()
        # æåå·²å­å¨çé®åå¶ç´¢å¼
        for i, line in enumerate(env_lines):
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('#'):
                if '=' in line_stripped:
                    key = line_stripped.split('=')[0].strip()
                    env_key_indices[key] = i
    
    # æ´æ°ææ·»å éç½®é¡¹
    for key, raw_value in updates.items():
        # æ ¼å¼åå¼ç¨äº .env æä»¶ï¼ä¸éè¦å¼å·ï¼é¤éæ¯å­ç¬¦ä¸²ä¸åå«ç©ºæ ¼ï¼
        if raw_value is None or raw_value == '':
            env_value = ''
        elif isinstance(raw_value, (int, float)):
            env_value = str(raw_value)
        elif isinstance(raw_value, bool):
            env_value = 'True' if raw_value else 'False'
        else:
            value_str = str(raw_value)
            # å¦æåå«ç©ºæ ¼æç¹æ®å­ç¬¦ï¼éè¦å¼å·
            if ' ' in value_str or '\n' in value_str or '#' in value_str:
                escaped = value_str.replace('\\', '\\\\').replace('"', '\\"')
                env_value = f'"{escaped}"'
            else:
                env_value = value_str
        
        # æ´æ°ææ·»å éç½®é¡¹
        if key in env_key_indices:
            # æ´æ°ç°æè¡
            env_lines[env_key_indices[key]] = f'{key}={env_value}'
        else:
            # æ·»å æ°è¡å°æä»¶æ«å°¾
            env_lines.append(f'{key}={env_value}')
    
    # åå¥ .env æä»¶
    env_file_path.parent.mkdir(parents=True, exist_ok=True)
    env_file_path.write_text('\n'.join(env_lines) + '\n', encoding='utf-8')
    
    # éæ°å è½½éç½®æ¨¡åï¼è¿ä¼éæ°è¯»å .env æä»¶å¹¶åå»ºæ°ç Settings å®ä¾ï¼
    _load_config_module()


system_state_lock = threading.Lock()
system_state = {
    'started': False,
    'starting': False,
    'shutdown_in_progress': False
}


def _set_system_state(*, started=None, starting=None):
    """Safely update the cached system state flags."""
    with system_state_lock:
        if started is not None:
            system_state['started'] = started
        if starting is not None:
            system_state['starting'] = starting


def _get_system_state():
    """Return a shallow copy of the system state flags."""
    with system_state_lock:
        return system_state.copy()


def _prepare_system_start():
    """Mark the system as starting if it is not already running or starting."""
    with system_state_lock:
        if system_state['started']:
            return False, 'ç³»ç»å·²å¯å¨'
        if system_state['starting']:
            return False, 'ç³»ç»æ­£å¨å¯å¨'
        system_state['starting'] = True
        return True, None

def _mark_shutdown_requested():
    """æ è®°å³æºå·²è¯·æ±ï¼è¥å·²æå³æºæµç¨åè¿å False""
    with system_state_lock:
        if system_state.get('shutdown_in_progress'):
            return False
        system_state['shutdown_in_progress'] = True
        return True


def initialize_system_components():
    """å¯å¨ææä¾èµç»ä»¶ï¼Streamlit å­åºç¨orumEngineeportEngineï¼""
    logs = []
    errors = []
    
    spider = MindSpider()
    if spider.initialize_database():
        logger.info("æ°æ®åºåå§åæå")
    else:
        logger.error("æ°æ®åºåå§åå¤±è´¥")

    try:
        stop_forum_engine()
        logs.append("å·²åæ­¢ ForumEngine çæ§å¨ä»¥é¿åæä»¶å²çª")
    except Exception as exc:  # pragma: no cover - å®å¨æè·
        message = f"åæ­¢ ForumEngine æ¶åçå¼å¸¸: {exc}"
        logs.append(message)
        logger.exception(message)

    processes['forum']['status'] = 'stopped'

    forum_started = False
    try:
        start_forum_engine()
        processes['forum']['status'] = 'running'
        logs.append("ForumEngine å¯å¨å®æ")
        forum_started = True
    except Exception as exc:  # pragma: no cover - ä¿åºæè·
        error_msg = f"ForumEngine å¯å¨å¤±è´¥: {exc}"
        logs.append(error_msg)
        errors.append(error_msg)

    if REPORT_ENGINE_AVAILABLE:
        try:
            if initialize_report_engine():
                logs.append("ReportEngine åå§åæå")
            else:
                msg = "ReportEngine åå§åå¤±è´¥"
                logs.append(msg)
                errors.append(msg)
        except Exception as exc:  # pragma: no cover
            msg = f"ReportEngine åå§åå¼å¸¸: {exc}"
            logs.append(msg)
            errors.append(msg)

    if errors:
        cleanup_processes()
        processes['forum']['status'] = 'stopped'
        if forum_started:
            try:
                stop_forum_engine()
            except Exception:  # pragma: no cover
                logger.exception("åæ­¢ForumEngineå¤±è´¥")
        return False, logs, errors

    return True, logs, []

# åå§åForumEngineçforum.logæä»¶
def init_forum_log():
    """åå§åforum.logæä»¶"""
    try:
        forum_log_file = LOG_DIR / "forum.log"
        # æ£æ¥æä»¶ä¸å­å¨ååå»ºå¹¶ä¸åä¸ä¸ªå¼å§ï¼å­å¨å°±æ¸ç©ºåä¸ä¸ªå¼å§
        if not forum_log_file.exists():
            with open(forum_log_file, 'w', encoding='utf-8') as f:
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"=== ForumEngine ç³»ç»åå§å - {start_time} ===\n")
            logger.info(f"ForumEngine: forum.log å·²åå§å")
        else:
            with open(forum_log_file, 'w', encoding='utf-8') as f:
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"=== ForumEngine ç³»ç»åå§å - {start_time} ===\n")
            logger.info(f"ForumEngine: forum.log å·²åå§å")
    except Exception as e:
        logger.exception(f"ForumEngine: åå§åforum.logå¤±è´¥: {e}")

# åå§åforum.log
init_forum_log()

# å¯å¨ForumEngineæºè½çæ§
def start_forum_engine():
    """å¯å¨ForumEngineè®ºå"""
    try:
        from backend.engines.forum.monitor import start_forum_monitoring
        logger.info("ForumEngine: å¯å¨è®ºå...")
        success = start_forum_monitoring()
        if not success:
            logger.info("ForumEngine: è®ºåå¯å¨å¤±è´¥")
    except Exception as e:
        logger.exception(f"ForumEngine: å¯å¨è®ºåå¤±è´¥: {e}")

# åæ­¢ForumEngineæºè½çæ§
def stop_forum_engine():
    """åæ­¢ForumEngineè®ºå"""
    try:
        from backend.engines.forum.monitor import stop_forum_monitoring
        logger.info("ForumEngine: åæ­¢è®ºå...")
        stop_forum_monitoring()
        logger.info("ForumEngine: è®ºåå·²åæ­¢")
    except Exception as e:
        logger.exception(f"ForumEngine: åæ­¢è®ºåå¤±è´¥: {e}")

def parse_forum_log_line(line):
    """è§£æforum.logè¡åå®¹ï¼æåå¯¹è¯ä¿¡æ¯"""
    import re
    
    # å¹éæ ¼å¼: [æ¶é´] [æ¥æº] åå®¹ï¼æ¥æºåè®¸å¤§å°ååç©ºæ ¼ï¼
    pattern = r'\[(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]\s*(.*)'
    match = re.match(pattern, line)
    
    if not match:
        return None

    timestamp, raw_source, content = match.groups()
    source = raw_source.strip().upper()

    # è¿æ»¤æç³»ç»æ¶æ¯åç©ºåå®¹
    if source == 'SYSTEM' or not content.strip():
        return None
    
    # æ¯æä¸ä¸ªAgentåä¸»æäºº
    if source not in ['QUERY', 'INSIGHT', 'MEDIA', 'HOST']:
        return None
    
    # è§£ç æ¥å¿ä¸­çè½¬ä¹æ¢è¡ï¼ä¿çå¤è¡æ ¼å¼
    cleaned_content = content.replace('\\n', '\n').replace('\\r', '').strip()
    
    # æ ¹æ®æ¥æºç¡®å®æ¶æ¯ç±»åååéè
    if source == 'HOST':
        message_type = 'host'
        sender = 'Forum Host'
    else:
        message_type = 'agent'
        sender = f'{source.title()} Engine'
    
    return {
        'type': message_type,
        'sender': sender,
        'content': cleaned_content,
        'timestamp': timestamp,
        'source': source
    }

# Forumæ¥å¿çå¬å¨
# å­å¨æ¯ä¸ªå®¢æ·ç«¯çåå²æ¥å¿åéä½ç½®
forum_log_positions = {}

def monitor_forum_log():
    """çå¬forum.logæä»¶ååå¹¶æ¨éå°åç«¯"""
    import time
    from pathlib import Path

    forum_log_file = LOG_DIR / "forum.log"
    last_position = 0
    processed_lines = set()  # ç¨äºè·è¸ªå·²å¤ççè¡ï¼é¿åéå¤

    # å¦ææä»¶å­å¨ï¼è·ååå§ä½ç½®ä½ä¸è·³è¿åå®¹
    if forum_log_file.exists():
        with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            # è®°å½æä»¶å¤§å°ï¼ä½ä¸æ·»å å°processed_lines
            # è¿æ ·ç¨æ·æå¼forumæ ç­¾æ¶å¯ä»¥è·ååå²
            f.seek(0, 2)  # ç§»å°æä»¶æ«å°¾
            last_position = f.tell()

    while True:
        try:
            if forum_log_file.exists():
                with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    f.seek(last_position)
                    new_lines = f.readlines()

                    if new_lines:
                        for line in new_lines:
                            line = line.rstrip('\n\r')
                            if line.strip():
                                line_hash = hash(line.strip())

                                # é¿åéå¤å¤çåä¸è¡
                                if line_hash in processed_lines:
                                    continue

                                processed_lines.add(line_hash)

                                # è§£ææ¥å¿è¡å¹¶åéforumæ¶æ¯
                                parsed_message = parse_forum_log_line(line)
                                if parsed_message:
                                    socketio.emit('forum_message', parsed_message)

                                # åªæå¨æ§å¶å°æ¾ç¤ºforumæ¶æåéæ§å¶å°æ¶æ¯
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                formatted_line = f"[{timestamp}] {line}"
                                socketio.emit('console_output', {
                                    'app': 'forum',
                                    'line': formatted_line
                                })

                        last_position = f.tell()

                        # æ¸çprocessed_lineséåï¼é¿ååå­æ³æ¼ï¼ä¿çæè¿1000è¡çåå¸ï¼
                        if len(processed_lines) > 1000:
                            # ä¿çæè¿500è¡çåå¸
                            recent_hashes = list(processed_lines)[-500:]
                            processed_lines = set(recent_hashes)

            time.sleep(1)  # æ¯ç§æ£æ¥ä¸æ¬¡
        except Exception as e:
            logger.error(f"Forumæ¥å¿çå¬éè¯¯: {e}")
            time.sleep(5)

# å¯å¨Forumæ¥å¿çå¬çº¿ç¨
forum_monitor_thread = threading.Thread(target=monitor_forum_log, daemon=True)
forum_monitor_thread.start()

# å¨å±åéå­å¨è¿ç¨ä¿¡æ¯
processes = {
    'crawler': {'process': None, 'port': None, 'status': 'running', 'output': [], 'log_file': None}, # ç¬è«å¼æå§ç»ä¿æå¯ç¨ç¶æ
    'forum': {'process': None, 'port': None, 'status': 'stopped', 'output': [], 'log_file': None}  # å¯å¨åæ è®°ä¸º running
}

def _log_shutdown_step(message: str):
    """ç»ä¸è®°å½å³æºæ­¥éª¤ï¼ä¾¿äºææ¥""
    logger.info(f"[Shutdown] {message}")


def _describe_running_children():
    """ååºå½åå­æ´»çå­è¿ç¨""
    running = []
    for name, info in processes.items():
        proc = info.get('process')
        if proc is not None and proc.poll() is None:
            port_desc = f", port={info.get('port')}" if info.get('port') else ""
            running.append(f"{name}(pid={proc.pid}{port_desc})")
    return running

# è¾åºéå
output_queues = {
    'insight': Queue(),
    'media': Queue(),
    'query': Queue(),
    'forum': Queue()
}

def write_log_to_file(app_name, line):
    """å°æ¥å¿åå¥æä»¶"""
    try:
        log_file_path = LOG_DIR / f"{app_name}.log"
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
            f.flush()
    except Exception as e:
        logger.error(f"Error writing log for {app_name}: {e}")

def read_log_from_file(app_name, tail_lines=None):
    """ä»æä»¶è¯»åæ¥å¿"""
    try:
        log_file_path = LOG_DIR / f"{app_name}.log"
        if not log_file_path.exists():
            return []
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # å¨è¿åç»åç«¯æ¶æªæ­åºå¤§ç JSON è¾åºï¼é²æ­¢å¡é¡¿
            processed_lines = []
            for line in lines:
                line = line.rstrip('\n\r')
                if not line.strip():
                    continue
                if "æ¸çåçè¾åº: {" in line and len(line) > 300:
                    line = line[:150] + " ... [JSONåå®¹è¿é¿ï¼åç«¯å·²æå æ¾ç¤º]"
                processed_lines.append(line)
            
            if tail_lines:
                return processed_lines[-tail_lines:]
            return processed_lines
    except Exception as e:
        logger.exception(f"Error reading log for {app_name}: {e}")
        return []

def read_process_output(process, app_name):
    """è¯»åè¿ç¨è¾åºå¹¶åå¥æä»¶"""
    import select
    import sys
    import os
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, PROJECT_ROOT)

    def process_and_emit_line(line):
        line = line.strip()
        if not line:
            return
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_line = f"[{timestamp}] {line}"
        
        # åå¥æ¥å¿æä»¶ (ä¿çå®æ´åå®¹ä¾ ForumEngine è¯»å)
        write_log_to_file(app_name, formatted_line)
        
        # åéå°åç«¯æ¶æªæ­åºå¤§ç JSON è¾åº
        emit_line = formatted_line
        if "æ¸çåçè¾åº: {" in formatted_line and len(formatted_line) > 300:
            emit_line = formatted_line[:150] + " ... [JSONåå®¹è¿é¿ï¼åç«¯å·²æå æ¾ç¤º]"
            
        socketio.emit('console_output', {
            'app': app_name,
            'line': emit_line
        })
    
    while True:
        try:
            if process.poll() is not None:
                # è¿ç¨ç»æï¼è¯»åå©ä½è¾åº
                remaining_output = process.stdout.read()
                if remaining_output:
                    lines = remaining_output.decode('utf-8', errors='replace').split('\n')
                    for line in lines:
                        process_and_emit_line(line)
                break
            
            # ä½¿ç¨éé»å¡è¯»å
            if sys.platform == 'win32':
                # Windowsä¸ä½¿ç¨ä¸åçæ¹æ³
                output = process.stdout.readline()
                if output:
                    line = output.decode('utf-8', errors='replace')
                    process_and_emit_line(line)
                else:
                    # æ²¡æè¾åºæ¶ç­æä¼ç 
                    time.sleep(0.1)
            else:
                # Unixç³»ç»ä½¿ç¨select
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if ready:
                    output = process.stdout.readline()
                    if output:
                        line = output.decode('utf-8', errors='replace')
                        process_and_emit_line(line)
                            
        except Exception as e:
            error_msg = f"Error reading output for {app_name}: {e}"
            logger.exception(error_msg)
            write_log_to_file(app_name, f"[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
            break

def check_app_status():
    """æ£æ¥åºç¨ç¶æ"""
    for app_name, info in processes.items():
        if info['process'] is not None:
            if info['process'].poll() is None:
                info['status'] = 'running'
            else:
                # è¿ç¨å·²ç»æ
                info['process'] = None
                info['status'] = 'stopped'

def wait_for_app_startup(app_name, max_wait_time=90):
    """ç­å¾åºç¨å¯å¨å®æ"""
    import time
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        info = processes[app_name]
        if info['process'] is None:
            return False, "è¿ç¨å·²åæ­¢"
        
        if info['process'].poll() is not None:
            return False, "è¿ç¨å¯å¨å¤±è´¥"
        
        try:
            response = requests.get(
                _build_healthcheck_url(info['port']),
                timeout=2,
                proxies=HEALTHCHECK_PROXIES
            )
            if response.status_code == 200:
                info['status'] = 'running'
                return True, "å¯å¨æå"
        except Exception as exc:
            _log_healthcheck_failure(app_name, exc)

        time.sleep(1)

    return False, "å¯å¨è¶æ¶"

def cleanup_processes():
    """æ¸çææè¿ç¨"""
    _log_shutdown_step("å¼å§ä¸²è¡æ¸çå­è¿ç¨")

    processes['forum']['status'] = 'stopped'
    try:
        stop_forum_engine()
    except Exception:  # pragma: no cover
        logger.exception("åæ­¢ForumEngineå¤±è´¥")
    _log_shutdown_step("å­è¿ç¨æ¸çå®æ")
    _set_system_state(started=False, starting=False)

def cleanup_processes_concurrent(timeout: float = 6.0):
    """å¹¶åæ¸çææå­è¿ç¨ï¼è¶æ¶åå¼ºå¶æææ®çè¿ç¨""
    _log_shutdown_step(f"å¼å§å¹¶åæ¸çå­è¿ç¨ï¼è¶æ¶ {timeout}sï¼")
    _log_shutdown_step("ä»ç»æ­¢å½åæ§å¶å°å¯å¨å¹¶è®°å½çå­è¿ç¨ï¼ä¸åç«¯å£æ«æ")
    running_before = _describe_running_children()
    if running_before:
        _log_shutdown_step("å½åå­æ´»å­è¿ç¨: " + ", ".join(running_before))
    else:
        _log_shutdown_step("æªæ£æµå°å­æ´»å­è¿ç¨ï¼ä»å°åéå³é­æä»¤")

    threads = []

    # å¹¶åå³é­ ForumEngine
    forum_thread = threading.Thread(target=stop_forum_engine, daemon=True)
    threads.append(forum_thread)
    forum_thread.start()

    # ç­å¾ææçº¿ç¨å®æï¼æå¤ timeout ç§
    end_time = time.time() + timeout
    for t in threads:
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        t.join(timeout=remaining)

    processes['forum']['status'] = 'stopped'
    _log_shutdown_step("å¹¶åæ¸çç»æï¼æ è®°ç³»ç»æªå¯å¨")
    _set_system_state(started=False, starting=False)

def _schedule_server_shutdown(delay_seconds: float = 0.1):
    """å¨æ¸çå®æåå°½å¿«éåºï¼é¿åé»å¡å½åè¯·æ±""
    def _shutdown():
        time.sleep(delay_seconds)
        try:
            socketio.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"SocketIO åæ­¢æ¶å¼å¸¸ï¼ç»§ç»­éåº: {exc}")
        _log_shutdown_step("SocketIO åæ­¢æä»¤å·²åéï¼å³å°éåºä¸»è¿ç¨")
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()

def _start_async_shutdown(cleanup_timeout: float = 3.0):
    """å¼æ­¥è§¦åæ¸çå¹¶å¼ºå¶éåºï¼é¿åHTTPè¯·æ±é»å¡""
    _log_shutdown_step(f"æ¶å°å³æºæä»¤ï¼å¯å¨å¼æ­¥æ¸çï¼è¶æ¶ {cleanup_timeout}sï¼")

    def _force_exit():
        _log_shutdown_step("å³æºè¶æ¶ï¼è§¦åå¼ºå¶éåº")
        os._exit(0)

    # ç¡¬è¶æ¶ä¿æ¤ï¼å³ä¾¿æ¸ççº¿ç¨å¼å¸¸ä¹è½éåº
    hard_timeout = cleanup_timeout + 2.0
    force_timer = threading.Timer(hard_timeout, _force_exit)
    force_timer.daemon = True
    force_timer.start()

    def _cleanup_and_exit():
        try:
            cleanup_processes_concurrent(timeout=cleanup_timeout)
        except Exception as exc:  # pragma: no cover
            logger.exception(f"å³æºæ¸çå¼å¸¸: {exc}")
        finally:
            _log_shutdown_step("æ¸ççº¿ç¨ç»æï¼è°åº¦ä¸»è¿ç¨éåº")
            _schedule_server_shutdown(0.05)

    threading.Thread(target=_cleanup_and_exit, daemon=True).start()

# æ³¨åæ¸çå½æ°
atexit.register(cleanup_processes)

# API è·¯ç±
@app.route('/api/status')
def get_status():
    """è·åææåºç¨ç¶æ"""
    check_app_status()
    return jsonify({
        app_name: {
            'status': info['status'],
            'port': info['port'],
            'output_lines': len(info['output'])
        }
        for app_name, info in processes.items()
    })

@app.route('/api/start/<app_name>')
def start_app(app_name):
    """å¯å¨æå®åºç¨"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': 'æªç¥åºç¨'})

    if app_name == 'forum':
        try:
            start_forum_engine()
            processes['forum']['status'] = 'running'
            return jsonify({'success': True, 'message': 'ForumEngineå·²å¯å¨'})
        except Exception as exc:  # pragma: no cover
            logger.exception("æå¨å¯å¨ForumEngineå¤±è´¥")
            return jsonify({'success': False, 'message': f'ForumEngineå¯å¨å¤±è´¥: {exc}'})

    return jsonify({'success': False, 'message': 'è¯¥åºç¨ä¸æ¯æå¯å¨æä½'})

@app.route('/api/stop/<app_name>')
def stop_app(app_name):
    """åæ­¢æå®åºç¨"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': 'æªç¥åºç¨'})

    if app_name == 'forum':
        try:
            stop_forum_engine()
            processes['forum']['status'] = 'stopped'
            return jsonify({'success': True, 'message': 'ForumEngineå·²åæ­¢'})
        except Exception as exc:  # pragma: no cover
            logger.exception("æå¨åæ­¢ForumEngineå¤±è´¥")
            return jsonify({'success': False, 'message': f'ForumEngineåæ­¢å¤±è´¥: {exc}'})

    return jsonify({'success': False, 'message': 'è¯¥åºç¨ä¸æ¯æåæ­¢æä½'})

@app.route('/api/output/<app_name>')
def get_output(app_name):
    """è·ååºç¨è¾åº"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': 'æªç¥åºç¨'})
    
    # ç¹æ®å¤çForum Engine
    if app_name == 'forum':
        try:
            forum_log_content = read_log_from_file('forum')
            return jsonify({
                'success': True,
                'output': forum_log_content,
                'total_lines': len(forum_log_content)
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'è¯»åforumæ¥å¿å¤±è´¥: {str(e)}'})
    
    # ä»æä»¶è¯»åå®æ´æ¥å¿
    output_lines = read_log_from_file(app_name)
    
    return jsonify({
        'success': True,
        'output': output_lines
    })

@app.route('/api/test_log/<app_name>')
def test_log(app_name):
    """æµè¯æ¥å¿åå¥åè½"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': 'æªç¥åºç¨'})
    
    # åå¥æµè¯æ¶æ¯
    test_msg = f"[{datetime.now().strftime('%H:%M:%S')}] æµè¯æ¥å¿æ¶æ¯ - {datetime.now()}"
    write_log_to_file(app_name, test_msg)
    
    # éè¿Socket.IOåé
    socketio.emit('console_output', {
        'app': app_name,
        'line': test_msg
    })
    
    return jsonify({
        'success': True,
        'message': f'æµè¯æ¶æ¯å·²åå¥ {app_name} æ¥å¿'
    })

@app.route('/api/forum/start')
def start_forum_monitoring_api():
    """æå¨å¯å¨ForumEngineè®ºå"""
    try:
        from backend.engines.forum.monitor import start_forum_monitoring
        success = start_forum_monitoring()
        if success:
            return jsonify({'success': True, 'message': 'ForumEngineè®ºåå·²å¯å¨'})
        else:
            return jsonify({'success': False, 'message': 'ForumEngineè®ºåå¯å¨å¤±è´¥'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'å¯å¨è®ºåå¤±è´¥: {str(e)}'})

@app.route('/api/forum/stop')
def stop_forum_monitoring_api():
    """æå¨åæ­¢ForumEngineè®ºå"""
    try:
        from backend.engines.forum.monitor import stop_forum_monitoring
        stop_forum_monitoring()
        return jsonify({'success': True, 'message': 'ForumEngineè®ºåå·²åæ­¢'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'åæ­¢è®ºåå¤±è´¥: {str(e)}'})

@app.route('/api/forum/log')
def get_forum_log():
    """è·åForumEngineçforum.logåå®¹"""
    try:
        forum_log_file = LOG_DIR / "forum.log"
        if not forum_log_file.exists():
            return jsonify({
                'success': True,
                'log_lines': [],
                'parsed_messages': [],
                'total_lines': 0
            })
        
        with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            lines = [line.rstrip('\n\r') for line in lines if line.strip()]
        
        # è§£ææ¯ä¸è¡æ¥å¿å¹¶æåå¯¹è¯ä¿¡æ¯
        parsed_messages = []
        for line in lines:
            parsed_message = parse_forum_log_line(line)
            if parsed_message:
                parsed_messages.append(parsed_message)
        
        return jsonify({
            'success': True,
            'log_lines': lines,
            'parsed_messages': parsed_messages,
            'total_lines': len(lines)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'è¯»åforum.logå¤±è´¥: {str(e)}'})

@app.route('/api/forum/log/history', methods=['POST'])
def get_forum_log_history():
    """è·åForumåå²æ¥å¿ï¼æ¯æä»æå®ä½ç½®å¼å§ï¼"""
    try:
        data = request.get_json()
        start_position = data.get('position', 0)  # å®¢æ·ç«¯ä¸æ¬¡æ¥æ¶çä½ç½®
        max_lines = data.get('max_lines', 1000)   # æå¤è¿åçè¡æ°

        forum_log_file = LOG_DIR / "forum.log"
        if not forum_log_file.exists():
            return jsonify({
                'success': True,
                'log_lines': [],
                'position': 0,
                'has_more': False
            })

        with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            # ä»æå®ä½ç½®å¼å§è¯»å
            f.seek(start_position)
            lines = []
            line_count = 0

            for line in f:
                if line_count >= max_lines:
                    break
                line = line.rstrip('\n\r')
                if line.strip():
                    # æ·»å æ¶é´æ³
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    formatted_line = f"[{timestamp}] {line}"
                    lines.append(formatted_line)
                    line_count += 1

            # è®°å½å½åä½ç½®
            current_position = f.tell()

            # æ£æ¥æ¯å¦è¿ææ´å¤åå®¹
            f.seek(0, 2)  # ç§»å°æä»¶æ«å°¾
            end_position = f.tell()
            has_more = current_position < end_position

        return jsonify({
            'success': True,
            'log_lines': lines,
            'position': current_position,
            'has_more': has_more
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'è¯»åforumåå²å¤±è´¥: {str(e)}'})

@app.route('/api/search', methods=['POST'])
def search():
    """ç»ä¸æç´¢æ¥å£"""
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'message': 'æç´¢æ¥è¯¢ä¸è½ä¸ºç©º'})
    
    # ãæ°å¢æºå¶ï¼å®æ¶è§¦åå¢éæå    # å¨åéæç´¢ä»»å¡ç»åºå± Agent ä¹åï¼åå©ç¨ Anspire æåå¨ç½ææ° 20 æ¡ç­ç¹å¹¶å¥åºï¼ä¿è¯æ¶ææ§
    try:
        from backend.engines.insight.utils.data_ingestion import ingest_all_sources_data
        # å¼æ­¥å¯å¨æåï¼ä¸é»å¡ä¸»æµç¨ï¼å¹¶è®°å½å° crawler.log ä¸­
        import threading
        def run_jit_crawler():
            log_file = LOG_DIR / "crawler.log"
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] ð·ï¸ [å¤§ä»»å¡èå¨] æ¶å°ç³»ç»ç»ä¸æç´¢ä»»å¡ï¼å¼å§èªå¨èåæå '{query}' ç¸å³æ°æ®...\n")
            try:
                # æè· ingest å½æ°çè¿åå¼ï¼ä»¥ä¾¿æ´è¯¦ç»å°è®°å½
                inserted_count, details = ingest_all_sources_data(query)
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] â [å¤§ä»»å¡èå¨] ç¦»çº¿å¤æºç¬è«æåå®æï¼å±æåå¥åº {inserted_count} æ¡æ°æ®n")
                    if details:
                        f.write(f"[{ts}] [SYSTEM] ð æ°æ®åå¸: {details}\n")
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [ERROR] â [å¤§ä»»å¡èå¨] ç¦»çº¿ç¬è«æåå¤±è´¥: {str(e)}\n")
        
        threading.Thread(target=run_jit_crawler, daemon=True).start()
    except Exception as e:
        logger.error(f"å¯å¨å¤æºå¢éæ°æ®æåçº¿ç¨å¤±è´¥: {e}")

    # æ£æ¥åªäºåºç¨æ­£å¨è¿è¡
    check_app_status()
    running_apps = [name for name, info in processes.items() if info['status'] == 'running']
    
    if not running_apps:
        return jsonify({'success': False, 'message': 'æ²¡æè¿è¡ä¸­çåºç¨'})
    
    # åè¿è¡ä¸­çåºç¨åéæç´¢è¯·æ±
    results = {}
    api_ports = {'insight': 8501, 'media': 8502, 'query': 8503}
    
    for app_name in running_apps:
        try:
            api_port = api_ports[app_name]
            # è°ç¨Streamlitåºç¨çAPIç«¯ç¹
            response = requests.post(
                f"http://localhost:{api_port}/api/search",
                json={'query': query},
                timeout=10
            )
            if response.status_code == 200:
                results[app_name] = response.json()
            else:
                results[app_name] = {'success': False, 'message': 'APIè°ç¨å¤±è´¥'}
        except Exception as e:
            results[app_name] = {'success': False, 'message': str(e)}
    
    # æç´¢å®æåå¯ä»¥éæ©åæ­¢çæ§ï¼æèè®©å®ç»§ç»­è¿è¡ä»¥æè·åç»­çå¤çæ¥å¿
    # è¿éæä»¬è®©çæ§ç»§ç»­è¿è¡ï¼ç¨æ·å¯ä»¥éè¿å¶ä»æ¥å£æå¨åæ­¢
    
    return jsonify({
        'success': True,
        'query': query,
        'results': results
    })


@app.route('/api/ingest', methods=['POST'])
def manual_ingest():
    """æå¨è§¦ååçç¦»çº¿ç¬è«ï¼åå¥æ¬å°æ°æ®åºï¼ï¼å¹¶å°æ¥å¿æå¥ crawler.log"""
    data = request.get_json()
    query = data.get('query', '').strip()
    wait = data.get('wait', False)
    if not query:
        return jsonify({'success': False, 'error': 'æç´¢è¯ä¸è½ä¸ºç©º'})
        
    try:
        if wait:
            # åæ­¥é»å¡æ§è¡
            log_file = LOG_DIR / "crawler.log"
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] ð·ï¸ [å¤§ä»»å¡èå¨] æ¶å°ç³»ç»ç»ä¸æç´¢ä»»å¡ï¼å¼å§èªå¨èåæå '{query}' ç¸å³æ°æ®...\n")
            try:
                from backend.engines.insight.utils.data_ingestion import ingest_all_sources_data
                inserted_count, details = ingest_all_sources_data(query)
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] â [å¤§ä»»å¡èå¨] ç¦»çº¿å¤æºç¬è«æåå®æï¼å±æåå¥åº {inserted_count} æ¡æ°æ®n")
                    if details:
                        f.write(f"[{ts}] [SYSTEM] ð æ°æ®åå¸: {details}\n")
                return jsonify({'success': True, 'message': 'å·²å®æç¦»çº¿ç¬è«æå'})
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [ERROR] â [å¤§ä»»å¡èå¨] ç¦»çº¿ç¬è«æåå¤±è´¥: {str(e)}\n")
                return jsonify({'success': False, 'error': str(e)})
        else:
            # å¼æ­¥éé»å¡æ§è¡
            import threading
            def run_ingest():
                log_file = LOG_DIR / "crawler.log"
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] ð·ï¸ æ¶å°ç¦»çº¿ç¬è«ä»»å¡ï¼å¼å§æå '{query}' ç¸å³æ°æ®å¹¶åå¥æ¬å°æ°æ®åº...\n")
                
                try:
                    from backend.engines.insight.utils.data_ingestion import ingest_all_sources_data
                    inserted_count, details = ingest_all_sources_data(query)
                    with open(log_file, "a", encoding="utf-8") as f:
                        ts = datetime.now().strftime('%H:%M:%S')
                        f.write(f"[{ts}] [SYSTEM] â ç¦»çº¿å¤æºç¬è«æåå®æï¼å±æåå¥åº {inserted_count} æ¡æ°æ®n")
                        if details:
                            f.write(f"[{ts}] [SYSTEM] ð æ°æ®åå¸: {details}\n")
                except Exception as e:
                    with open(log_file, "a", encoding="utf-8") as f:
                        ts = datetime.now().strftime('%H:%M:%S')
                        f.write(f"[{ts}] [ERROR] â ç¦»çº¿ç¬è«æåå¤±è´¥: {str(e)}\n")
                        
            threading.Thread(target=run_ingest, daemon=True).start()
            return jsonify({'success': True, 'message': 'å·²å¯å¨ç¦»çº¿ç¬è«'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ================= æ°ä¸ä»£ç°ä»£åç«¯ API (Stage 1) =================
from flask import Response

@app.route('/api/v1/logs/stream')
def stream_crawler_logs():
    """
    æä¾ SSE (Server-Sent Events) ç«¯ç¹ï¼ç¨äºåç°ä»£åç«¯å®æ¶æµå¼æ¨éç¬è«æ¥å¿    åç«¯å¯ä»¥ç¨ EventSource çå¬æ­¤æ¥å£    """
    def generate_logs():
        log_file_path = LOG_DIR / "crawler.log"
        # å¦ææä»¶ä¸å­å¨ï¼ååå»ºä¸ä¸ªç©ºç
        if not log_file_path.exists():
            log_file_path.touch()

        with open(log_file_path, "r", encoding="utf-8") as f:
            # ç§»å¨å°æä»¶æ«å°¾ï¼åªçå¬æ°å¢æ¥å¿ï¼é¿åæ¯æ¬¡å è½½å åè¡åå²ï¼
            f.seek(0, os.SEEK_END)
            last_size = f.tell()
            while True:
                # æ£æ¥æä»¶æ¯å¦è¢«æ¸ç©ºï¼éç½®ï¼
                current_size = log_file_path.stat().st_size if log_file_path.exists() else 0
                if current_size < last_size:
                    # æä»¶è¢«æ¸ç©ºï¼éç½®ä½ç½®
                    f.seek(0, os.SEEK_END)
                    last_size = current_size

                line = f.readline()
                if not line:
                    time.sleep(0.5)  # ç­å¾æ°æ¥å¿åå¥
                    continue
                last_size = f.tell()
                # SSE æ ¼å¼: "data: <content>\n\n"
                yield f"data: {line.strip()}\n\n"

    return Response(generate_logs(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@app.route('/api/v1/crawler/status')
def crawler_status():
    """
    è·åç¬è«ç³»ç»ç¶æï¼åæ¬ï¼
    - æ°æ®åºè¿æ¥ç¶æ
    - æè¿å¥åºæ°æ®ç»è®¡
    - æ´»è·ç¬è«ä»»å¡
    """
    try:
        # æ£æ¥æ°æ®åºè¿æ¥
        db_status = "unknown"
        recent_count = 0
        try:
            import asyncpg
            import asyncio

            async def check_db():
                try:
                    pool = await asyncpg.connect(
                        host=os.getenv("DB_HOST", "127.0.0.1"),
                        port=int(os.getenv("DB_PORT", "5444")),
                        user=os.getenv("DB_USER", "radar"),
                        password=os.getenv("DB_PASSWORD", "radar"),
                        database=os.getenv("DB_NAME", "radar"),
                        timeout=3,
                    )
                    # è·åæè¿å¥åºæ°éï¼ä»å¤©çæ°æ®ï¼
                    result = await pool.fetchval("""
                        SELECT COUNT(*) FROM crawled_data
                        WHERE DATE(create_time) = CURRENT_DATE
                    """)
                    await pool.close()
                    return "connected", result or 0
                except Exception:
                    return "disconnected", 0

            db_status, recent_count = asyncio.run(check_db())
        except Exception as e:
            db_status = f"error: {str(e)}"

        # æ£æ¥æ¯å¦ææ´»è·ä»»å¡
        active_task_count = len(active_tasks)

        # è·åç¬è«æ¥å¿ææ°è¡æ°
        crawler_log_lines = 0
        try:
            crawler_log = LOG_DIR / "crawler.log"
            if crawler_log.exists():
                with open(crawler_log, 'r', encoding='utf-8') as f:
                    crawler_log_lines = sum(1 for _ in f)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'database': {
                'status': db_status,
                'today_records': recent_count
            },
            'crawler': {
                'active_tasks': active_task_count,
                'log_lines': crawler_log_lines
            }
        })
    except Exception as e:
        logger.exception("è·åç¬è«ç¶æå¤±è´¥")
        return jsonify({'success': False, 'error': str(e)}), 500

active_tasks = {}

@app.route('/api/v1/report/stream/<task_id>')
def stream_reports(task_id):
    """
    æä¾ SSE (Server-Sent Events) ç«¯ç¹ï¼ç¨äºåç°ä»£åç«¯å®æ¶æµå¼æ¨éä¸å¤§å¼æåææ¥ååè®ºååå®¹    """
    if task_id not in active_tasks:
        return jsonify({'success': False, 'error': 'Task not found'}), 404
        
    q = active_tasks[task_id]['queue']
    
    def generate_reports():
        active_engines = 3
        while active_engines > 0:
            try:
                msg = q.get(timeout=30)
                
                if msg["type"] == "log":
                    yield f"data: {json.dumps({'status': 'thinking', 'engine': msg['engine'], 'log': msg['content']})}\n\n"
                elif msg["type"] == "forum":
                    yield f"data: {json.dumps({'status': 'forum', 'content': msg['content']})}\n\n"
                elif msg["type"] == "qrcode":
                    yield f"data: {json.dumps({'status': 'qrcode', 'image': msg['content']})}\n\n"
                elif msg["type"] == "done":
                    # When an engine finishes, stream its content
                    content = msg["content"]
                    def chunker(engine, text):
                        # æ¨¡ææå­æºææ
                        for i in range(0, len(text), 10):
                            q.put({"engine": engine, "type": "chunk", "content": text[i:i+10]})
                            time.sleep(0.02)
                        q.put({"engine": engine, "type": "complete"})
                    threading.Thread(target=chunker, args=(msg["engine"], content)).start()
                elif msg["type"] == "chunk":
                    yield f"data: {json.dumps({'status': 'streaming', 'engine': msg['engine'], 'content': msg['content']})}\n\n"
                elif msg["type"] == "complete":
                    yield f"data: {json.dumps({'status': 'complete', 'engine': msg['engine']})}\n\n"
                    active_engines -= 1
                elif msg["type"] == "error":
                    yield f"data: {json.dumps({'status': 'error', 'engine': msg['engine'], 'message': msg['content']})}\n\n"
                    active_engines -= 1
            except Exception as e:
                pass
                
        yield f"data: {json.dumps({'status': 'complete'})}\n\n"
        # ä»»å¡ç»æï¼æ¸ç
        if task_id in active_tasks:
            del active_tasks[task_id]

    return Response(generate_reports(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })

@app.route('/api/v1/task/start', methods=['POST'])
def v1_start_task():
    """
    å¼æ­¥è§¦åå¤æºç¬è«åå¼æåæ    è¿å Task IDï¼ä¾åç«¯è¿æ¥ SSE ç¶æ    """
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'error': 'Query cannot be empty'}), 400
        
    task_id = f"task_{int(time.time())}"
    q = Queue()
    active_tasks[task_id] = {
        "query": query,
        "queue": q
    }
    
    def run_full_pipeline():
        log_file = LOG_DIR / "crawler.log"
        with open(log_file, "a", encoding="utf-8") as f:
            ts = datetime.now().strftime('%H:%M:%S')
            f.write(f"[{ts}] [SYSTEM] ð [Task {task_id}] å¯å¨ç°ä»£åç«¯æ¶æééåææµç¨: '{query}'\n")
            
        try:
            from backend.engines.insight.utils.data_ingestion import ingest_all_sources_data
            inserted_count, details = ingest_all_sources_data(query)
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] â [Task {task_id}] ééé¶æ®µå®æï¼å±å¥åº {inserted_count} æ¡æ°æ®n")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [ERROR] â [Task {task_id}] ä»»å¡å´©æº: {str(e)}\n")
            # éç¥åç«¯ç¬è«å¤±è´¥ï¼åæ­¢ææå¼æ
            for eng in ["insight", "media", "query"]:
                q.put({"type": "error", "engine": eng, "content": str(e)})
            return

        # ================== å¯å¨ ForumEngine å 3 ä¸ª Agent ==================
        try:
            start_forum_engine()
            processes['forum']['status'] = 'running'
        except Exception as e:
            logger.error(f"ForumEngineå¯å¨å¤±è´¥: {e}")

        def log_handler(message):
            path = str(message.record["file"].path)
            msg = message.record["message"]
            if "backend.engines.insight" in path:
                q.put({"type": "log", "engine": "insight", "content": msg})
            elif "backend.engines.media" in path:
                q.put({"type": "log", "engine": "media", "content": msg})
            elif "backend.engines.query" in path:
                q.put({"type": "log", "engine": "query", "content": msg})
            elif "backend/engines/forum" in path or "monitor.py" in path or "llm_host.py" in path:
                # è¿æ»¤æä¸äºè¿é¿çæä¸å¿è¦çæ¥å¿
                if "Forum Update" not in msg:
                    q.put({"type": "forum", "content": msg})
                
        handler_id = logger.add(log_handler, level="INFO")
        
        final_reports = {}
        
        def run_agent(engine_name, module_name):
            try:
                import importlib
                agent_module = importlib.import_module(f"{module_name}.agent")
                agent = agent_module.create_agent()
                final_report = agent.research(query)
                final_reports[engine_name] = final_report
                q.put({"type": "done", "engine": engine_name, "content": final_report})
            except Exception as e:
                q.put({"type": "error", "engine": engine_name, "content": str(e)})

        t1 = threading.Thread(target=run_agent, args=("insight", "backend.engines.insight"))
        t2 = threading.Thread(target=run_agent, args=("media", "backend.engines.media"))
        t3 = threading.Thread(target=run_agent, args=("query", "backend.engines.query"))
        
        t1.start()
        t2.start()
        t3.start()
        
        t1.join()
        t2.join()
        t3.join()
        
        logger.remove(handler_id)
        
        try:
            stop_forum_engine()
            processes['forum']['status'] = 'stopped'
        except Exception:
            pass

        # å½ä¸ä¸ªå¼æé½å®æåï¼è°ç¨ ReportEngine çææç» HTML
        try:
            from backend.engines.report.agent import create_agent as create_report_agent
            report_agent = create_report_agent()
            
            # è¯»åè®ºåæ¥å¿
            forum_log_path = LOG_DIR / "forum.log"
            forum_logs = forum_log_path.read_text(encoding="utf-8") if forum_log_path.exists() else ""
            
            reports_list = [final_reports.get(e) for e in ["insight", "media", "query"] if final_reports.get(e)]
            
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] ð å¼å§çæç»¼å HTML æ¥å...\n")
                
            report_agent.generate_report(
                query=query,
                reports=reports_list,
                forum_logs=forum_logs
            )
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] â ç»¼åæ¥åçæå®æï¼è¯·å¨åå²è®°å½ä¸­æ¥çn")
        except Exception as e:
            logger.error(f"ReportEngine å¤±è´¥: {e}")
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [ERROR] â ReportEngine çææ¥åå¤±è´¥: {e}\n")

    threading.Thread(target=run_full_pipeline, daemon=True).start()
    
    return jsonify({
        'success': True, 
        'message': 'Task triggered asynchronously', 
        'task_id': task_id
    })

# ç¨äºå­å¨ MediaCrawler ä¼ éè¿æ¥çäºç»´ç  Base64 å­ç¬¦ä¸²
current_qr_code = {"image": None}

@app.route('/api/v1/internal/qrcode', methods=['POST'])
def receive_qrcode():
    """
    ä¾ MediaCrawler åé¨è°ç¨ï¼æ¥æ¶æ«ç ç»å½çäºç»´ç å¹¶å­å¨    """
    data = request.get_json() or {}
    image_b64 = data.get('image')
    if image_b64:
        current_qr_code['image'] = image_b64
        # å¯ä»¥å°äºç»´ç ä½ä¸ºä¸ç§ç¹æ®ç Log ç±»åéè¿ SSE æ¨éç»åç«¯ï¼åæææ´»è·ä»»å¡å¹¿æ­ï¼
        for tid, tinfo in active_tasks.items():
            if 'queue' in tinfo:
                tinfo['queue'].put({"type": "qrcode", "content": image_b64})
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/api/v1/reports', methods=['GET'])
def get_reports_list():
    """è·åææå·²çæçåå²æ¥ååè¡¨"""
    reports_dir = Path('final_reports')
    if not reports_dir.exists():
        return jsonify({'success': True, 'reports': []})
    
    reports = []
    for file in reports_dir.glob('*.html'):
        stat = file.stat()
        reports.append({
            'name': file.name,
            'title': file.stem.replace('final_report_', ''),
            'size': stat.st_size,
            'created_at': stat.st_mtime,
            'html_url': f'/api/v1/reports/download/html/{file.name}',
            'pdf_url': f'/api/v1/reports/download/pdf/{file.name}',
            'md_url': f'/api/v1/reports/download/md/{file.name}'
        })
    
    # æåå»ºæ¶é´ååº
    reports.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'success': True, 'reports': reports})

@app.route('/api/v1/reports/download/<format>/<filename>')
def download_report_format(format, filename):
    """
    ä¸è½½æé¢è§æ¥å    æ¯æ html, pdf, mdãå¦æ pdf/md ä¸å­å¨ï¼åå°è¯ä» IR json å¨æçæ    """
    reports_dir = Path('final_reports')
    
    if format == 'html':
        return send_from_directory(reports_dir, filename)
    
    # è·åå¯¹åºç IR æä»¶
    # html æä»¶åæ ¼å¼: final_report_xxx.html
    # IR æä»¶åæ ¼å¼: ir/report_ir_xxx.json
    base_name = filename.replace('final_report_', '').replace('.html', '')
    ir_filename = f"report_ir_{base_name}.json"
    ir_path = reports_dir / 'ir' / ir_filename
    
    if not ir_path.exists():
        return jsonify({'success': False, 'error': 'æªæ¾å°å¯¹åºçä¸­é´è¡¨ç¤º(IR)æä»¶ï¼æ æ³å¯¼åºè¯¥æ ¼å¼'}), 404
        
    try:
        import json
        with open(ir_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)
            
        if format == 'md':
            from backend.engines.report.renderers.markdown_renderer import MarkdownRenderer
            renderer = MarkdownRenderer()
            md_content = renderer.render(document_ir)
            return Response(
                md_content,
                mimetype='text/markdown',
                headers={'Content-Disposition': f'attachment; filename="{base_name}.md"'}
            )
            
        elif format == 'pdf':
            from backend.engines.report.renderers.pdf_renderer import PDFRenderer
            renderer = PDFRenderer()
            # å¨æçæ PDFï¼å¯è½ä¼æç¹æ¢
            pdf_bytes = renderer.render(document_ir)
            return Response(
                pdf_bytes,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{base_name}.pdf"'}
            )
            
        else:
            return jsonify({'success': False, 'error': 'ä¸æ¯æçæ ¼å¼'}), 400
            
    except Exception as e:
        logger.exception(f"å¯¼åº {format} å¤±è´¥")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Expose selected configuration values to the frontend."""
    try:
        config_values = read_config_values()
        return jsonify({'success': True, 'config': config_values})
    except Exception as exc:
        logger.exception("è¯»åéç½®å¤±è´¥")
        return jsonify({'success': False, 'message': f'è¯»åéç½®å¤±è´¥: {exc}'}), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration values and persist them to config.py."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return jsonify({'success': False, 'message': 'è¯·æ±ä½ä¸è½ä¸ºç©º'}), 400

    updates = {}
    for key, value in payload.items():
        if key in CONFIG_KEYS:
            updates[key] = value if value is not None else ''

    if not updates:
        return jsonify({'success': False, 'message': 'æ²¡æå¯æ´æ°çéç½®é¡¹'}), 400

    try:
        write_config_values(updates)
        
        # ä¸ºäºä¿è¯éè½½çæï¼æä»¬éè¦åæ¸é¤æä½ç³»ç»çç¯å¢åéç¼å­
        import os
        for key in updates.keys():
            if key in os.environ:
                del os.environ[key]
                
        updated_config = read_config_values()
        return jsonify({'success': True, 'config': updated_config})
    except Exception as exc:
        logger.exception("æ´æ°éç½®å¤±è´¥")
        return jsonify({'success': False, 'message': f'æ´æ°éç½®å¤±è´¥: {exc}'}), 500


@app.route('/api/system/status')
def get_system_status():
    """è¿åç³»ç»å¯å¨ç¶æ""
    state = _get_system_state()
    return jsonify({
        'success': True,
        'started': state['started'],
        'starting': state['starting']
    })


@app.route('/api/system/start', methods=['POST'])
def start_system():
    """å¨æ¥æ¶å°è¯·æ±åå¯å¨å®æ´ç³»ç»""
    allowed, message = _prepare_system_start()
    if not allowed:
        return jsonify({'success': False, 'message': message}), 400

    try:
        success, logs, errors = initialize_system_components()
        if success:
            _set_system_state(started=True)
            return jsonify({'success': True, 'message': 'ç³»ç»å¯å¨æå', 'logs': logs})

        _set_system_state(started=False)
        return jsonify({
            'success': False,
            'message': 'ç³»ç»å¯å¨å¤±è´¥',
            'logs': logs,
            'errors': errors
        }), 500
    except Exception as exc:  # pragma: no cover - ä¿åºæè·
        logger.exception("ç³»ç»å¯å¨è¿ç¨ä¸­åºç°å¼å¸¸")
        _set_system_state(started=False)
        return jsonify({'success': False, 'message': f'ç³»ç»å¯å¨å¼å¸¸: {exc}'}), 500
    finally:
        _set_system_state(starting=False)

@app.route('/api/system/shutdown', methods=['POST'])
def shutdown_system():
    """ä¼éåæ­¢ææç»ä»¶å¹¶å³é­å½åæå¡è¿ç¨""
    state = _get_system_state()
    if state['starting']:
        return jsonify({'success': False, 'message': 'ç³»ç»æ­£å¨å¯å¨/éå¯ï¼è¯·ç¨å'}), 400

    target_ports = [
        f"{name}:{info['port']}"
        for name, info in processes.items()
        if info.get('port')
    ]

    # å·²æå³æºè¯·æ±æ§è¡ä¸­æ¶ï¼è¿åå½åå­æ´»çå­è¿ç¨ï¼ä¾¿äºåç«¯å¤æ­è¿åº¦
    if not _mark_shutdown_requested():
        running = _describe_running_children()
        detail = 'å³æºæä»¤å·²ä¸åï¼è¯·ç¨ç­...'
        if running:
            detail = f"å³æºæä»¤å·²ä¸åï¼ç­å¾è¿ç¨éåº: {', '.join(running)}"
        if target_ports:
            detail = f"{detail}ï¼ç«¯å£: {', '.join(target_ports)}ï¼"
        return jsonify({'success': True, 'message': detail, 'ports': target_ports})

    running = _describe_running_children()
    if running:
        _log_shutdown_step("å¼å§å³é­ç³»ç»ï¼æ­£å¨ç­å¾å­è¿ç¨éåº: " + ", ".join(running))
    else:
        _log_shutdown_step("å¼å§å³é­ç³»ç»ï¼æªæ£æµå°å­æ´»å­è¿ç¨")

    try:
        _set_system_state(started=False, starting=False)
        _start_async_shutdown(cleanup_timeout=6.0)
        message = 'å³é­ç³»ç»æä»¤å·²ä¸åï¼æ­£å¨åæ­¢è¿ç¨'
        if running:
            message = f"{message}: {', '.join(running)}"
        if target_ports:
            message = f"{message}ï¼ç«¯å£: {', '.join(target_ports)}ï¼"
        return jsonify({'success': True, 'message': message, 'ports': target_ports})
    except Exception as exc:  # pragma: no cover - ååºæè·
        logger.exception("ç³»ç»å³é­è¿ç¨ä¸­åºç°å¼å¸¸")
        return jsonify({'success': False, 'message': f'ç³»ç»å³é­å¼å¸¸: {exc}'}), 500

@socketio.on('connect')
def handle_connect():
    """å®¢æ·ç«¯è¿æ¥"""
    emit('status', 'Connected to Flask server')

@socketio.on('request_status')
def handle_status_request():
    """è¯·æ±ç¶ææ´æ°"""
    check_app_status()
    emit('status_update', {
        app_name: {
            'status': info['status'],
            'port': info['port']
        }
        for app_name, info in processes.items()
    })

if __name__ == '__main__':
    # ä»éç½®æä»¶è¯»å HOST å PORT
    from backend.config import settings
    HOST = settings.HOST
    PORT = settings.PORT
    
    logger.info("ç­å¾éç½®ç¡®è®¤ï¼ç³»ç»å°å¨åç«¯æä»¤åå¯å¨ç»ä»¶...")
    logger.info(f"Flaskæå¡å¨å·²å¯å¨ï¼è®¿é®å°å: http://{HOST}:{PORT}")
    
    try:
        socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("\næ­£å¨å³é­åºç¨...")
        cleanup_processes()
        
    
