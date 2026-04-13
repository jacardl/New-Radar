"""
Flask主应用 - 统一管理三个Streamlit应用
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 【修复】时区同步问题
# 1. 在 Windows 本地运行时，移除可能被错误注入的 UTC 时区
if os.name == 'nt' and 'TZ' in os.environ:
    del os.environ['TZ']
# 2. 在 Docker 容器 (Linux) 中运行时，如果没有映射宿主机时区，默认将其设置为东八区（北京时间）
elif os.name == 'posix':
    if 'TZ' not in os.environ or os.environ['TZ'] == 'UTC':
        os.environ['TZ'] = 'Asia/Shanghai'
        import time
        if hasattr(time, 'tzset'):
            time.tzset()

# 【修复】尽早设置环境变量，确保所有模块都使用无缓冲模式
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'  # 禁用Python输出缓冲，确保日志实时输出

# 【修复】设置 HF_ENDPOINT，保证国内下载 HuggingFace 模型不卡死
if os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT")
elif "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 【修复】屏蔽 transformers 库恼人的内部 alias 警告
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
import warnings
warnings.filterwarnings("ignore", module="transformers")

import subprocess
import time
import threading
from datetime import datetime
from queue import Queue
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import atexit
import requests
from loguru import logger
import importlib
from pathlib import Path
from MindSpider.main import MindSpider

# 导入ReportEngine
try:
    from ReportEngine.flask_interface import report_bp, initialize_report_engine
    REPORT_ENGINE_AVAILABLE = True
except ImportError as e:
    logger.error(f"ReportEngine导入失败: {e}")
    REPORT_ENGINE_AVAILABLE = False

# 设置静态文件目录
dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web', 'dist')
app = Flask(__name__, static_folder=dist_dir, static_url_path='')
app.config['SECRET_KEY'] = 'Dedicated-to-creating-a-concise-and-versatile-public-opinion-analysis-platform'
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# eventlet 在客户端主动断开时偶尔会抛出 ConnectionAbortedError，这里做一次防御性包裹，
# 避免无意义的堆栈污染日志（仅在 eventlet 可用时启用）。
def _patch_eventlet_disconnect_logging():
    if sys.version_info >= (3, 12):
        return
    try:
        import eventlet.wsgi  # type: ignore
    except Exception as exc:  # pragma: no cover - 仅在生产环境有效
        logger.debug(f"eventlet 不可用，跳过断开补丁: {exc}")
        return

    try:
        original_finish = eventlet.wsgi.HttpProtocol.finish  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover
        logger.debug(f"eventlet 缺少 HttpProtocol.finish，跳过断开补丁: {exc}")
        return

    def _safe_finish(self, *args, **kwargs):  # pragma: no cover - 运行时才会触发
        try:
            return original_finish(self, *args, **kwargs)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as exc:
            try:
                environ = getattr(self, 'environ', {}) or {}
                method = environ.get('REQUEST_METHOD', '')
                path = environ.get('PATH_INFO', '')
                logger.warning(f"客户端已主动断开，忽略异常: {method} {path} ({exc})")
            except Exception:
                logger.warning(f"客户端已主动断开，忽略异常: {exc}")
            return

    eventlet.wsgi.HttpProtocol.finish = _safe_finish  # type: ignore[attr-defined]
    logger.info("已对 eventlet 连接中断进行安全防护")

_patch_eventlet_disconnect_logging()

# 注册ReportEngine Blueprint
if REPORT_ENGINE_AVAILABLE:
    app.register_blueprint(report_bp, url_prefix='/api/report')
    logger.info("ReportEngine接口已注册")
else:
    logger.info("ReportEngine不可用，跳过接口注册并添加降级路由")
    @app.route('/api/report/status', methods=['GET'])
    def fallback_report_status():
        return jsonify({'success': False, 'initialized': False, 'error': 'ReportEngine不可用'})


# 创建日志目录
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# 托管前端静态文件
@app.route('/')
@app.route('/<path:path>')
def serve_frontend(path=''):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

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
    'ENABLE_WEB_ACCESS'
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
        # 重新加载配置以获取最新的 Settings 实例
        from config import reload_settings, settings
        reload_settings()
        
        values = {}
        for key in CONFIG_KEYS:
            # 从 Pydantic Settings 实例读取值
            value = getattr(settings, key, None)
            # Convert to string for uniform handling on the frontend.
            if value is None:
                values[key] = ''
            else:
                values[key] = str(value)
        return values
    except Exception as exc:
        logger.exception(f"读取配置失败: {exc}")
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
    
    # 确定 .env 文件路径（与 config.py 中的逻辑一致）
    project_root = Path(__file__).resolve().parent
    cwd_env = Path.cwd() / ".env"
    env_file_path = cwd_env if cwd_env.exists() else (project_root / ".env")
    
    # 读取现有的 .env 文件内容
    env_lines = []
    env_key_indices = {}  # 记录每个键在文件中的索引位置
    if env_file_path.exists():
        env_lines = env_file_path.read_text(encoding='utf-8').splitlines()
        # 提取已存在的键及其索引
        for i, line in enumerate(env_lines):
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('#'):
                if '=' in line_stripped:
                    key = line_stripped.split('=')[0].strip()
                    env_key_indices[key] = i
    
    # 更新或添加配置项
    for key, raw_value in updates.items():
        # 格式化值用于 .env 文件（不需要引号，除非是字符串且包含空格）
        if raw_value is None or raw_value == '':
            env_value = ''
        elif isinstance(raw_value, (int, float)):
            env_value = str(raw_value)
        elif isinstance(raw_value, bool):
            env_value = 'True' if raw_value else 'False'
        else:
            value_str = str(raw_value)
            # 如果包含空格或特殊字符，需要引号
            if ' ' in value_str or '\n' in value_str or '#' in value_str:
                escaped = value_str.replace('\\', '\\\\').replace('"', '\\"')
                env_value = f'"{escaped}"'
            else:
                env_value = value_str
        
        # 更新或添加配置项
        if key in env_key_indices:
            # 更新现有行
            env_lines[env_key_indices[key]] = f'{key}={env_value}'
        else:
            # 添加新行到文件末尾
            env_lines.append(f'{key}={env_value}')
    
    # 写入 .env 文件
    env_file_path.parent.mkdir(parents=True, exist_ok=True)
    env_file_path.write_text('\n'.join(env_lines) + '\n', encoding='utf-8')
    
    # 重新加载配置模块（这会重新读取 .env 文件并创建新的 Settings 实例）
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
            return False, '系统已启动'
        if system_state['starting']:
            return False, '系统正在启动'
        system_state['starting'] = True
        return True, None

def _mark_shutdown_requested():
    """标记关机已请求；若已有关机流程则返回 False。"""
    with system_state_lock:
        if system_state.get('shutdown_in_progress'):
            return False
        system_state['shutdown_in_progress'] = True
        return True


def initialize_system_components():
    """启动所有依赖组件（Streamlit 子应用、ForumEngine、ReportEngine）。"""
    logs = []
    errors = []
    
    spider = MindSpider()
    if spider.initialize_database():
        logger.info("数据库初始化成功")
    else:
        logger.error("数据库初始化失败")

    try:
        stop_forum_engine()
        logs.append("已停止 ForumEngine 监控器以避免文件冲突")
    except Exception as exc:  # pragma: no cover - 安全捕获
        message = f"停止 ForumEngine 时发生异常: {exc}"
        logs.append(message)
        logger.exception(message)

    processes['forum']['status'] = 'stopped'

    forum_started = False
    try:
        start_forum_engine()
        processes['forum']['status'] = 'running'
        logs.append("ForumEngine 启动完成")
        forum_started = True
    except Exception as exc:  # pragma: no cover - 保底捕获
        error_msg = f"ForumEngine 启动失败: {exc}"
        logs.append(error_msg)
        errors.append(error_msg)

    if REPORT_ENGINE_AVAILABLE:
        try:
            if initialize_report_engine():
                logs.append("ReportEngine 初始化成功")
            else:
                msg = "ReportEngine 初始化失败"
                logs.append(msg)
                errors.append(msg)
        except Exception as exc:  # pragma: no cover
            msg = f"ReportEngine 初始化异常: {exc}"
            logs.append(msg)
            errors.append(msg)

    if errors:
        cleanup_processes()
        processes['forum']['status'] = 'stopped'
        if forum_started:
            try:
                stop_forum_engine()
            except Exception:  # pragma: no cover
                logger.exception("停止ForumEngine失败")
        return False, logs, errors

    return True, logs, []

# 初始化ForumEngine的forum.log文件
def init_forum_log():
    """初始化forum.log文件"""
    try:
        forum_log_file = LOG_DIR / "forum.log"
        # 检查文件不存在则创建并且写一个开始，存在就清空写一个开始
        if not forum_log_file.exists():
            with open(forum_log_file, 'w', encoding='utf-8') as f:
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"=== ForumEngine 系统初始化 - {start_time} ===\n")
            logger.info(f"ForumEngine: forum.log 已初始化")
        else:
            with open(forum_log_file, 'w', encoding='utf-8') as f:
                start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"=== ForumEngine 系统初始化 - {start_time} ===\n")
            logger.info(f"ForumEngine: forum.log 已初始化")
    except Exception as e:
        logger.exception(f"ForumEngine: 初始化forum.log失败: {e}")

# 初始化forum.log
init_forum_log()

# 启动ForumEngine智能监控
def start_forum_engine():
    """启动ForumEngine论坛"""
    try:
        from ForumEngine.monitor import start_forum_monitoring
        logger.info("ForumEngine: 启动论坛...")
        success = start_forum_monitoring()
        if not success:
            logger.info("ForumEngine: 论坛启动失败")
    except Exception as e:
        logger.exception(f"ForumEngine: 启动论坛失败: {e}")

# 停止ForumEngine智能监控
def stop_forum_engine():
    """停止ForumEngine论坛"""
    try:
        from ForumEngine.monitor import stop_forum_monitoring
        logger.info("ForumEngine: 停止论坛...")
        stop_forum_monitoring()
        logger.info("ForumEngine: 论坛已停止")
    except Exception as e:
        logger.exception(f"ForumEngine: 停止论坛失败: {e}")

def parse_forum_log_line(line):
    """解析forum.log行内容，提取对话信息"""
    import re
    
    # 匹配格式: [时间] [来源] 内容（来源允许大小写及空格）
    pattern = r'\[(\d{2}:\d{2}:\d{2})\]\s*\[([^\]]+)\]\s*(.*)'
    match = re.match(pattern, line)
    
    if not match:
        return None

    timestamp, raw_source, content = match.groups()
    source = raw_source.strip().upper()

    # 过滤掉系统消息和空内容
    if source == 'SYSTEM' or not content.strip():
        return None
    
    # 支持三个Agent和主持人
    if source not in ['QUERY', 'INSIGHT', 'MEDIA', 'HOST']:
        return None
    
    # 解码日志中的转义换行，保留多行格式
    cleaned_content = content.replace('\\n', '\n').replace('\\r', '').strip()
    
    # 根据来源确定消息类型和发送者
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

# Forum日志监听器
# 存储每个客户端的历史日志发送位置
forum_log_positions = {}

def monitor_forum_log():
    """监听forum.log文件变化并推送到前端"""
    import time
    from pathlib import Path

    forum_log_file = LOG_DIR / "forum.log"
    last_position = 0
    processed_lines = set()  # 用于跟踪已处理的行，避免重复

    # 如果文件存在，获取初始位置但不跳过内容
    if forum_log_file.exists():
        with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            # 记录文件大小，但不添加到processed_lines
            # 这样用户打开forum标签时可以获取历史
            f.seek(0, 2)  # 移到文件末尾
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

                                # 避免重复处理同一行
                                if line_hash in processed_lines:
                                    continue

                                processed_lines.add(line_hash)

                                # 解析日志行并发送forum消息
                                parsed_message = parse_forum_log_line(line)
                                if parsed_message:
                                    socketio.emit('forum_message', parsed_message)

                                # 只有在控制台显示forum时才发送控制台消息
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                formatted_line = f"[{timestamp}] {line}"
                                socketio.emit('console_output', {
                                    'app': 'forum',
                                    'line': formatted_line
                                })

                        last_position = f.tell()

                        # 清理processed_lines集合，避免内存泄漏（保留最近1000行的哈希）
                        if len(processed_lines) > 1000:
                            # 保留最近500行的哈希
                            recent_hashes = list(processed_lines)[-500:]
                            processed_lines = set(recent_hashes)

            time.sleep(1)  # 每秒检查一次
        except Exception as e:
            logger.error(f"Forum日志监听错误: {e}")
            time.sleep(5)

# 启动Forum日志监听线程
forum_monitor_thread = threading.Thread(target=monitor_forum_log, daemon=True)
forum_monitor_thread.start()

# 全局变量存储进程信息
processes = {
    'crawler': {'process': None, 'port': None, 'status': 'running', 'output': [], 'log_file': None}, # 爬虫引擎始终保持可用状态
    'forum': {'process': None, 'port': None, 'status': 'stopped', 'output': [], 'log_file': None}  # 启动后标记为 running
}

def _log_shutdown_step(message: str):
    """统一记录关机步骤，便于排查。"""
    logger.info(f"[Shutdown] {message}")


def _describe_running_children():
    """列出当前存活的子进程。"""
    running = []
    for name, info in processes.items():
        proc = info.get('process')
        if proc is not None and proc.poll() is None:
            port_desc = f", port={info.get('port')}" if info.get('port') else ""
            running.append(f"{name}(pid={proc.pid}{port_desc})")
    return running

# 输出队列
output_queues = {
    'insight': Queue(),
    'media': Queue(),
    'query': Queue(),
    'forum': Queue()
}

def write_log_to_file(app_name, line):
    """将日志写入文件"""
    try:
        log_file_path = LOG_DIR / f"{app_name}.log"
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
            f.flush()
    except Exception as e:
        logger.error(f"Error writing log for {app_name}: {e}")

def read_log_from_file(app_name, tail_lines=None):
    """从文件读取日志"""
    try:
        log_file_path = LOG_DIR / f"{app_name}.log"
        if not log_file_path.exists():
            return []
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # 在返回给前端时截断庞大的 JSON 输出，防止卡顿
            processed_lines = []
            for line in lines:
                line = line.rstrip('\n\r')
                if not line.strip():
                    continue
                if "清理后的输出: {" in line and len(line) > 300:
                    line = line[:150] + " ... [JSON内容过长，前端已折叠显示]"
                processed_lines.append(line)
            
            if tail_lines:
                return processed_lines[-tail_lines:]
            return processed_lines
    except Exception as e:
        logger.exception(f"Error reading log for {app_name}: {e}")
        return []

def read_process_output(process, app_name):
    """读取进程输出并写入文件"""
    import select
    import sys
    
    def process_and_emit_line(line):
        line = line.strip()
        if not line:
            return
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_line = f"[{timestamp}] {line}"
        
        # 写入日志文件 (保留完整内容供 ForumEngine 读取)
        write_log_to_file(app_name, formatted_line)
        
        # 发送到前端时截断庞大的 JSON 输出
        emit_line = formatted_line
        if "清理后的输出: {" in formatted_line and len(formatted_line) > 300:
            emit_line = formatted_line[:150] + " ... [JSON内容过长，前端已折叠显示]"
            
        socketio.emit('console_output', {
            'app': app_name,
            'line': emit_line
        })
    
    while True:
        try:
            if process.poll() is not None:
                # 进程结束，读取剩余输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    lines = remaining_output.decode('utf-8', errors='replace').split('\n')
                    for line in lines:
                        process_and_emit_line(line)
                break
            
            # 使用非阻塞读取
            if sys.platform == 'win32':
                # Windows下使用不同的方法
                output = process.stdout.readline()
                if output:
                    line = output.decode('utf-8', errors='replace')
                    process_and_emit_line(line)
                else:
                    # 没有输出时短暂休眠
                    time.sleep(0.1)
            else:
                # Unix系统使用select
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
    """检查应用状态"""
    for app_name, info in processes.items():
        if info['process'] is not None:
            if info['process'].poll() is None:
                info['status'] = 'running'
            else:
                # 进程已结束
                info['process'] = None
                info['status'] = 'stopped'

def wait_for_app_startup(app_name, max_wait_time=90):
    """等待应用启动完成"""
    import time
    start_time = time.time()
    while time.time() - start_time < max_wait_time:
        info = processes[app_name]
        if info['process'] is None:
            return False, "进程已停止"
        
        if info['process'].poll() is not None:
            return False, "进程启动失败"
        
        try:
            response = requests.get(
                _build_healthcheck_url(info['port']),
                timeout=2,
                proxies=HEALTHCHECK_PROXIES
            )
            if response.status_code == 200:
                info['status'] = 'running'
                return True, "启动成功"
        except Exception as exc:
            _log_healthcheck_failure(app_name, exc)

        time.sleep(1)

    return False, "启动超时"

def cleanup_processes():
    """清理所有进程"""
    _log_shutdown_step("开始串行清理子进程")

    processes['forum']['status'] = 'stopped'
    try:
        stop_forum_engine()
    except Exception:  # pragma: no cover
        logger.exception("停止ForumEngine失败")
    _log_shutdown_step("子进程清理完成")
    _set_system_state(started=False, starting=False)

def cleanup_processes_concurrent(timeout: float = 6.0):
    """并发清理所有子进程，超时后强制杀掉残留进程。"""
    _log_shutdown_step(f"开始并发清理子进程（超时 {timeout}s）")
    _log_shutdown_step("仅终止当前控制台启动并记录的子进程，不做端口扫描")
    running_before = _describe_running_children()
    if running_before:
        _log_shutdown_step("当前存活子进程: " + ", ".join(running_before))
    else:
        _log_shutdown_step("未检测到存活子进程，仍将发送关闭指令")

    threads = []

    # 并发关闭 ForumEngine
    forum_thread = threading.Thread(target=stop_forum_engine, daemon=True)
    threads.append(forum_thread)
    forum_thread.start()

    # 等待所有线程完成，最多 timeout 秒
    end_time = time.time() + timeout
    for t in threads:
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        t.join(timeout=remaining)

    processes['forum']['status'] = 'stopped'
    _log_shutdown_step("并发清理结束，标记系统未启动")
    _set_system_state(started=False, starting=False)

def _schedule_server_shutdown(delay_seconds: float = 0.1):
    """在清理完成后尽快退出，避免阻塞当前请求。"""
    def _shutdown():
        time.sleep(delay_seconds)
        try:
            socketio.stop()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"SocketIO 停止时异常，继续退出: {exc}")
        _log_shutdown_step("SocketIO 停止指令已发送，即将退出主进程")
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()

def _start_async_shutdown(cleanup_timeout: float = 3.0):
    """异步触发清理并强制退出，避免HTTP请求阻塞。"""
    _log_shutdown_step(f"收到关机指令，启动异步清理（超时 {cleanup_timeout}s）")

    def _force_exit():
        _log_shutdown_step("关机超时，触发强制退出")
        os._exit(0)

    # 硬超时保护，即便清理线程异常也能退出
    hard_timeout = cleanup_timeout + 2.0
    force_timer = threading.Timer(hard_timeout, _force_exit)
    force_timer.daemon = True
    force_timer.start()

    def _cleanup_and_exit():
        try:
            cleanup_processes_concurrent(timeout=cleanup_timeout)
        except Exception as exc:  # pragma: no cover
            logger.exception(f"关机清理异常: {exc}")
        finally:
            _log_shutdown_step("清理线程结束，调度主进程退出")
            _schedule_server_shutdown(0.05)

    threading.Thread(target=_cleanup_and_exit, daemon=True).start()

# 注册清理函数
atexit.register(cleanup_processes)

# API 路由
@app.route('/api/status')
def get_status():
    """获取所有应用状态"""
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
    """启动指定应用"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': '未知应用'})

    if app_name == 'forum':
        try:
            start_forum_engine()
            processes['forum']['status'] = 'running'
            return jsonify({'success': True, 'message': 'ForumEngine已启动'})
        except Exception as exc:  # pragma: no cover
            logger.exception("手动启动ForumEngine失败")
            return jsonify({'success': False, 'message': f'ForumEngine启动失败: {exc}'})

    return jsonify({'success': False, 'message': '该应用不支持启动操作'})

@app.route('/api/stop/<app_name>')
def stop_app(app_name):
    """停止指定应用"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': '未知应用'})

    if app_name == 'forum':
        try:
            stop_forum_engine()
            processes['forum']['status'] = 'stopped'
            return jsonify({'success': True, 'message': 'ForumEngine已停止'})
        except Exception as exc:  # pragma: no cover
            logger.exception("手动停止ForumEngine失败")
            return jsonify({'success': False, 'message': f'ForumEngine停止失败: {exc}'})

    return jsonify({'success': False, 'message': '该应用不支持停止操作'})

@app.route('/api/output/<app_name>')
def get_output(app_name):
    """获取应用输出"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': '未知应用'})
    
    # 特殊处理Forum Engine
    if app_name == 'forum':
        try:
            forum_log_content = read_log_from_file('forum')
            return jsonify({
                'success': True,
                'output': forum_log_content,
                'total_lines': len(forum_log_content)
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'读取forum日志失败: {str(e)}'})
    
    # 从文件读取完整日志
    output_lines = read_log_from_file(app_name)
    
    return jsonify({
        'success': True,
        'output': output_lines
    })

@app.route('/api/test_log/<app_name>')
def test_log(app_name):
    """测试日志写入功能"""
    if app_name not in processes:
        return jsonify({'success': False, 'message': '未知应用'})
    
    # 写入测试消息
    test_msg = f"[{datetime.now().strftime('%H:%M:%S')}] 测试日志消息 - {datetime.now()}"
    write_log_to_file(app_name, test_msg)
    
    # 通过Socket.IO发送
    socketio.emit('console_output', {
        'app': app_name,
        'line': test_msg
    })
    
    return jsonify({
        'success': True,
        'message': f'测试消息已写入 {app_name} 日志'
    })

@app.route('/api/forum/start')
def start_forum_monitoring_api():
    """手动启动ForumEngine论坛"""
    try:
        from ForumEngine.monitor import start_forum_monitoring
        success = start_forum_monitoring()
        if success:
            return jsonify({'success': True, 'message': 'ForumEngine论坛已启动'})
        else:
            return jsonify({'success': False, 'message': 'ForumEngine论坛启动失败'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'启动论坛失败: {str(e)}'})

@app.route('/api/forum/stop')
def stop_forum_monitoring_api():
    """手动停止ForumEngine论坛"""
    try:
        from ForumEngine.monitor import stop_forum_monitoring
        stop_forum_monitoring()
        return jsonify({'success': True, 'message': 'ForumEngine论坛已停止'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'停止论坛失败: {str(e)}'})

@app.route('/api/forum/log')
def get_forum_log():
    """获取ForumEngine的forum.log内容"""
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
        
        # 解析每一行日志并提取对话信息
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
        return jsonify({'success': False, 'message': f'读取forum.log失败: {str(e)}'})

@app.route('/api/forum/log/history', methods=['POST'])
def get_forum_log_history():
    """获取Forum历史日志（支持从指定位置开始）"""
    try:
        data = request.get_json()
        start_position = data.get('position', 0)  # 客户端上次接收的位置
        max_lines = data.get('max_lines', 1000)   # 最多返回的行数

        forum_log_file = LOG_DIR / "forum.log"
        if not forum_log_file.exists():
            return jsonify({
                'success': True,
                'log_lines': [],
                'position': 0,
                'has_more': False
            })

        with open(forum_log_file, 'r', encoding='utf-8', errors='ignore') as f:
            # 从指定位置开始读取
            f.seek(start_position)
            lines = []
            line_count = 0

            for line in f:
                if line_count >= max_lines:
                    break
                line = line.rstrip('\n\r')
                if line.strip():
                    # 添加时间戳
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    formatted_line = f"[{timestamp}] {line}"
                    lines.append(formatted_line)
                    line_count += 1

            # 记录当前位置
            current_position = f.tell()

            # 检查是否还有更多内容
            f.seek(0, 2)  # 移到文件末尾
            end_position = f.tell()
            has_more = current_position < end_position

        return jsonify({
            'success': True,
            'log_lines': lines,
            'position': current_position,
            'has_more': has_more
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取forum历史失败: {str(e)}'})

@app.route('/api/search', methods=['POST'])
def search():
    """统一搜索接口"""
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'success': False, 'message': '搜索查询不能为空'})
    
    # 【新增机制：实时触发增量抓取】
    # 在分配搜索任务给底层 Agent 之前，先利用 Anspire 抓取全网最新 20 条热点并入库，保证时效性
    try:
        from InsightEngine.utils.data_ingestion import ingest_all_sources_data
        # 异步启动抓取，不阻塞主流程，并记录到 crawler.log 中
        import threading
        def run_jit_crawler():
            log_file = LOG_DIR / "crawler.log"
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] 🕷️ [大任务联动] 收到系统统一搜索任务，开始自动联合抓取 '{query}' 相关数据...\n")
            try:
                # 捕获 ingest 函数的返回值，以便更详细地记录
                inserted_count, details = ingest_all_sources_data(query)
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] ✅ [大任务联动] 离线多源爬虫抓取完成！共成功入库 {inserted_count} 条数据。\n")
                    if details:
                        f.write(f"[{ts}] [SYSTEM] 📊 数据分布: {details}\n")
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [ERROR] ❌ [大任务联动] 离线爬虫抓取失败: {str(e)}\n")
        
        threading.Thread(target=run_jit_crawler, daemon=True).start()
    except Exception as e:
        logger.error(f"启动多源增量数据抓取线程失败: {e}")

    # 检查哪些应用正在运行
    check_app_status()
    running_apps = [name for name, info in processes.items() if info['status'] == 'running']
    
    if not running_apps:
        return jsonify({'success': False, 'message': '没有运行中的应用'})
    
    # 向运行中的应用发送搜索请求
    results = {}
    api_ports = {'insight': 8501, 'media': 8502, 'query': 8503}
    
    for app_name in running_apps:
        try:
            api_port = api_ports[app_name]
            # 调用Streamlit应用的API端点
            response = requests.post(
                f"http://localhost:{api_port}/api/search",
                json={'query': query},
                timeout=10
            )
            if response.status_code == 200:
                results[app_name] = response.json()
            else:
                results[app_name] = {'success': False, 'message': 'API调用失败'}
        except Exception as e:
            results[app_name] = {'success': False, 'message': str(e)}
    
    # 搜索完成后可以选择停止监控，或者让它继续运行以捕获后续的处理日志
    # 这里我们让监控继续运行，用户可以通过其他接口手动停止
    
    return jsonify({
        'success': True,
        'query': query,
        'results': results
    })


@app.route('/api/ingest', methods=['POST'])
def manual_ingest():
    """手动触发原生离线爬虫（写入本地数据库），并将日志打入 crawler.log"""
    data = request.get_json()
    query = data.get('query', '').strip()
    wait = data.get('wait', False)
    if not query:
        return jsonify({'success': False, 'error': '搜索词不能为空'})
        
    try:
        if wait:
            # 同步阻塞执行
            log_file = LOG_DIR / "crawler.log"
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] 🕷️ [大任务联动] 收到系统统一搜索任务，开始自动联合抓取 '{query}' 相关数据...\n")
            try:
                from InsightEngine.utils.data_ingestion import ingest_all_sources_data
                inserted_count, details = ingest_all_sources_data(query)
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] ✅ [大任务联动] 离线多源爬虫抓取完成！共成功入库 {inserted_count} 条数据。\n")
                    if details:
                        f.write(f"[{ts}] [SYSTEM] 📊 数据分布: {details}\n")
                return jsonify({'success': True, 'message': '已完成离线爬虫抓取'})
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [ERROR] ❌ [大任务联动] 离线爬虫抓取失败: {str(e)}\n")
                return jsonify({'success': False, 'error': str(e)})
        else:
            # 异步非阻塞执行
            import threading
            def run_ingest():
                log_file = LOG_DIR / "crawler.log"
                with open(log_file, "a", encoding="utf-8") as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    f.write(f"[{ts}] [SYSTEM] 🕷️ 收到离线爬虫任务，开始抓取 '{query}' 相关数据并写入本地数据库...\n")
                
                try:
                    from InsightEngine.utils.data_ingestion import ingest_all_sources_data
                    inserted_count, details = ingest_all_sources_data(query)
                    with open(log_file, "a", encoding="utf-8") as f:
                        ts = datetime.now().strftime('%H:%M:%S')
                        f.write(f"[{ts}] [SYSTEM] ✅ 离线多源爬虫抓取完成！共成功入库 {inserted_count} 条数据。\n")
                        if details:
                            f.write(f"[{ts}] [SYSTEM] 📊 数据分布: {details}\n")
                except Exception as e:
                    with open(log_file, "a", encoding="utf-8") as f:
                        ts = datetime.now().strftime('%H:%M:%S')
                        f.write(f"[{ts}] [ERROR] ❌ 离线爬虫抓取失败: {str(e)}\n")
                        
            threading.Thread(target=run_ingest, daemon=True).start()
            return jsonify({'success': True, 'message': '已启动离线爬虫'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ================= 新一代现代前端 API (Stage 1) =================
from flask import Response

@app.route('/api/v1/logs/stream')
def stream_crawler_logs():
    """
    提供 SSE (Server-Sent Events) 端点，用于向现代前端实时流式推送爬虫日志。
    前端可以用 EventSource 监听此接口。
    """
    def generate_logs():
        log_file_path = LOG_DIR / "crawler.log"
        # 如果文件不存在，先创建一个空的
        if not log_file_path.exists():
            log_file_path.touch()
            
        with open(log_file_path, "r", encoding="utf-8") as f:
            # 先移动到文件末尾（只监听新增日志，避免每次加载几千行历史）
            # 或者如果是要加载历史，可以先 readlines()，这里为了演示纯增量
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)  # 等待新日志写入
                    continue
                # SSE 格式: "data: xxx\n\n"
                yield f"data: {line.strip()}\n\n"

    return Response(generate_logs(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })

active_tasks = {}

@app.route('/api/v1/report/stream/<task_id>')
def stream_reports(task_id):
    """
    提供 SSE (Server-Sent Events) 端点，用于向现代前端实时流式推送三大引擎分析报告及论坛内容。
    """
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
                        # 模拟打字机效果
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
        # 任务结束，清理
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
    异步触发多源爬虫和引擎分析。
    返回 Task ID，供前端连接 SSE 状态。
    """
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
            f.write(f"[{ts}] [SYSTEM] 🚀 [Task {task_id}] 启动现代前端架构采集分析流程: '{query}'\n")
            
        try:
            from InsightEngine.utils.data_ingestion import ingest_all_sources_data
            inserted_count, details = ingest_all_sources_data(query)
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] ✅ [Task {task_id}] 采集阶段完成！共入库 {inserted_count} 条数据。\n")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [ERROR] ❌ [Task {task_id}] 任务崩溃: {str(e)}\n")
            # 通知前端爬虫失败，停止所有引擎
            for eng in ["insight", "media", "query"]:
                q.put({"type": "error", "engine": eng, "content": str(e)})
            return

        # ================== 启动 ForumEngine 和 3 个 Agent ==================
        try:
            start_forum_engine()
            processes['forum']['status'] = 'running'
        except Exception as e:
            logger.error(f"ForumEngine启动失败: {e}")

        def log_handler(message):
            path = str(message.record["file"].path)
            msg = message.record["message"]
            if "InsightEngine" in path:
                q.put({"type": "log", "engine": "insight", "content": msg})
            elif "MediaEngine" in path:
                q.put({"type": "log", "engine": "media", "content": msg})
            elif "QueryEngine" in path:
                q.put({"type": "log", "engine": "query", "content": msg})
            elif "ForumEngine" in path or "monitor.py" in path or "llm_host.py" in path:
                # 过滤掉一些过长的或不必要的日志
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

        t1 = threading.Thread(target=run_agent, args=("insight", "InsightEngine"))
        t2 = threading.Thread(target=run_agent, args=("media", "MediaEngine"))
        t3 = threading.Thread(target=run_agent, args=("query", "QueryEngine"))
        
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

        # 当三个引擎都完成后，调用 ReportEngine 生成最终 HTML
        try:
            from ReportEngine.agent import create_agent as create_report_agent
            report_agent = create_report_agent()
            
            # 读取论坛日志
            forum_log_path = LOG_DIR / "forum.log"
            forum_logs = forum_log_path.read_text(encoding="utf-8") if forum_log_path.exists() else ""
            
            reports_list = [final_reports.get(e) for e in ["insight", "media", "query"] if final_reports.get(e)]
            
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] 📝 开始生成综合 HTML 报告...\n")
                
            report_agent.generate_report(
                query=query,
                reports=reports_list,
                forum_logs=forum_logs
            )
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [SYSTEM] ✅ 综合报告生成完成！请在历史记录中查看。\n")
        except Exception as e:
            logger.error(f"ReportEngine 失败: {e}")
            with open(log_file, "a", encoding="utf-8") as f:
                ts = datetime.now().strftime('%H:%M:%S')
                f.write(f"[{ts}] [ERROR] ❌ ReportEngine 生成报告失败: {e}\n")

    threading.Thread(target=run_full_pipeline, daemon=True).start()
    
    return jsonify({
        'success': True, 
        'message': 'Task triggered asynchronously', 
        'task_id': task_id
    })

# 用于存储 MediaCrawler 传递过来的二维码 Base64 字符串
current_qr_code = {"image": None}

@app.route('/api/v1/internal/qrcode', methods=['POST'])
def receive_qrcode():
    """
    供 MediaCrawler 内部调用，接收扫码登录的二维码并存储。
    """
    data = request.get_json() or {}
    image_b64 = data.get('image')
    if image_b64:
        current_qr_code['image'] = image_b64
        # 可以将二维码作为一种特殊的 Log 类型通过 SSE 推送给前端（向所有活跃任务广播）
        for tid, tinfo in active_tasks.items():
            if 'queue' in tinfo:
                tinfo['queue'].put({"type": "qrcode", "content": image_b64})
        return jsonify({'success': True})
    return jsonify({'success': False}), 400

@app.route('/api/v1/reports', methods=['GET'])
def get_reports_list():
    """获取所有已生成的历史报告列表"""
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
    
    # 按创建时间倒序
    reports.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'success': True, 'reports': reports})

@app.route('/api/v1/reports/download/<format>/<filename>')
def download_report_format(format, filename):
    """
    下载或预览报告。
    支持 html, pdf, md。如果 pdf/md 不存在，则尝试从 IR json 动态生成。
    """
    reports_dir = Path('final_reports')
    
    if format == 'html':
        return send_from_directory(reports_dir, filename)
    
    # 获取对应的 IR 文件
    # html 文件名格式: final_report_xxx.html
    # IR 文件名格式: ir/report_ir_xxx.json
    base_name = filename.replace('final_report_', '').replace('.html', '')
    ir_filename = f"report_ir_{base_name}.json"
    ir_path = reports_dir / 'ir' / ir_filename
    
    if not ir_path.exists():
        return jsonify({'success': False, 'error': '未找到对应的中间表示(IR)文件，无法导出该格式'}), 404
        
    try:
        import json
        with open(ir_path, 'r', encoding='utf-8') as f:
            document_ir = json.load(f)
            
        if format == 'md':
            from ReportEngine.renderers.markdown_renderer import MarkdownRenderer
            renderer = MarkdownRenderer()
            md_content = renderer.render(document_ir)
            return Response(
                md_content,
                mimetype='text/markdown',
                headers={'Content-Disposition': f'attachment; filename="{base_name}.md"'}
            )
            
        elif format == 'pdf':
            from ReportEngine.renderers.pdf_renderer import PDFRenderer
            renderer = PDFRenderer()
            # 动态生成 PDF，可能会有点慢
            pdf_bytes = renderer.render(document_ir)
            return Response(
                pdf_bytes,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{base_name}.pdf"'}
            )
            
        else:
            return jsonify({'success': False, 'error': '不支持的格式'}), 400
            
    except Exception as e:
        logger.exception(f"导出 {format} 失败")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================

@app.route('/api/config', methods=['GET'])
def get_config():
    """Expose selected configuration values to the frontend."""
    try:
        config_values = read_config_values()
        return jsonify({'success': True, 'config': config_values})
    except Exception as exc:
        logger.exception("读取配置失败")
        return jsonify({'success': False, 'message': f'读取配置失败: {exc}'}), 500


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration values and persist them to config.py."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return jsonify({'success': False, 'message': '请求体不能为空'}), 400

    updates = {}
    for key, value in payload.items():
        if key in CONFIG_KEYS:
            updates[key] = value if value is not None else ''

    if not updates:
        return jsonify({'success': False, 'message': '没有可更新的配置项'}), 400

    try:
        write_config_values(updates)
        
        # 为了保证重载生效，我们需要先清除操作系统的环境变量缓存
        import os
        for key in updates.keys():
            if key in os.environ:
                del os.environ[key]
                
        updated_config = read_config_values()
        return jsonify({'success': True, 'config': updated_config})
    except Exception as exc:
        logger.exception("更新配置失败")
        return jsonify({'success': False, 'message': f'更新配置失败: {exc}'}), 500


@app.route('/api/system/status')
def get_system_status():
    """返回系统启动状态。"""
    state = _get_system_state()
    return jsonify({
        'success': True,
        'started': state['started'],
        'starting': state['starting']
    })


@app.route('/api/system/start', methods=['POST'])
def start_system():
    """在接收到请求后启动完整系统。"""
    allowed, message = _prepare_system_start()
    if not allowed:
        return jsonify({'success': False, 'message': message}), 400

    try:
        success, logs, errors = initialize_system_components()
        if success:
            _set_system_state(started=True)
            return jsonify({'success': True, 'message': '系统启动成功', 'logs': logs})

        _set_system_state(started=False)
        return jsonify({
            'success': False,
            'message': '系统启动失败',
            'logs': logs,
            'errors': errors
        }), 500
    except Exception as exc:  # pragma: no cover - 保底捕获
        logger.exception("系统启动过程中出现异常")
        _set_system_state(started=False)
        return jsonify({'success': False, 'message': f'系统启动异常: {exc}'}), 500
    finally:
        _set_system_state(starting=False)

@app.route('/api/system/shutdown', methods=['POST'])
def shutdown_system():
    """优雅停止所有组件并关闭当前服务进程。"""
    state = _get_system_state()
    if state['starting']:
        return jsonify({'success': False, 'message': '系统正在启动/重启，请稍候'}), 400

    target_ports = [
        f"{name}:{info['port']}"
        for name, info in processes.items()
        if info.get('port')
    ]

    # 已有关机请求执行中时，返回当前存活的子进程，便于前端判断进度
    if not _mark_shutdown_requested():
        running = _describe_running_children()
        detail = '关机指令已下发，请稍等...'
        if running:
            detail = f"关机指令已下发，等待进程退出: {', '.join(running)}"
        if target_ports:
            detail = f"{detail}（端口: {', '.join(target_ports)}）"
        return jsonify({'success': True, 'message': detail, 'ports': target_ports})

    running = _describe_running_children()
    if running:
        _log_shutdown_step("开始关闭系统，正在等待子进程退出: " + ", ".join(running))
    else:
        _log_shutdown_step("开始关闭系统，未检测到存活子进程")

    try:
        _set_system_state(started=False, starting=False)
        _start_async_shutdown(cleanup_timeout=6.0)
        message = '关闭系统指令已下发，正在停止进程'
        if running:
            message = f"{message}: {', '.join(running)}"
        if target_ports:
            message = f"{message}（端口: {', '.join(target_ports)}）"
        return jsonify({'success': True, 'message': message, 'ports': target_ports})
    except Exception as exc:  # pragma: no cover - 兜底捕获
        logger.exception("系统关闭过程中出现异常")
        return jsonify({'success': False, 'message': f'系统关闭异常: {exc}'}), 500

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    emit('status', 'Connected to Flask server')

@socketio.on('request_status')
def handle_status_request():
    """请求状态更新"""
    check_app_status()
    emit('status_update', {
        app_name: {
            'status': info['status'],
            'port': info['port']
        }
        for app_name, info in processes.items()
    })

if __name__ == '__main__':
    # 从配置文件读取 HOST 和 PORT
    from config import settings
    HOST = settings.HOST
    PORT = settings.PORT
    
    logger.info("等待配置确认，系统将在前端指令后启动组件...")
    logger.info(f"Flask服务器已启动，访问地址: http://{HOST}:{PORT}")
    
    try:
        socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("\n正在关闭应用...")
        cleanup_processes()
        
    
