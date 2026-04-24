"""
æ¥å¿çæ§å?- å®æ¶çæ§ä¸ä¸ªlogæä»¶ä¸­çSummaryNodeè¾åº
"""

import os
import time
import threading
from pathlib import Path
from datetime import datetime
import re
import json
from typing import Dict, Optional, List
from threading import Lock
from loguru import logger

# å¯¼å¥è®ºåä¸»æäººæ¨¡å?
try:
    from .llm_host import generate_host_speech
    HOST_AVAILABLE = True
except ImportError:
    logger.exception("ForumEngine: è®ºåä¸»æäººæ¨¡åæªæ¾å°ï¼å°ä»¥çº¯çæ§æ¨¡å¼è¿è¡")
    HOST_AVAILABLE = False

class LogMonitor:
    """åºäºæä»¶ååçæºè½æ¥å¿çæ§å¨"""
   
    def __init__(self, log_dir: str = "logs"):
        """åå§åæ¥å¿çæ§å¨"""
        self.log_dir = Path(log_dir)
        self.forum_log_file = self.log_dir / "forum.log"
       
        # è¦çæ§çæ¥å¿æä»¶
        self.monitored_logs = {
            'insight': self.log_dir / 'insight.log',
            'media': self.log_dir / 'media.log',
            'query': self.log_dir / 'query.log'
        }
       
        # çæ§ç¶æ?
        self.is_monitoring = False
        self.monitor_thread = None
        self.file_positions = {}  # è®°å½æ¯ä¸ªæä»¶çè¯»åä½ç½?
        self.file_line_counts = {}  # è®°å½æ¯ä¸ªæä»¶çè¡æ?
        self.is_searching = False  # æ¯å¦æ­£å¨æç´¢
        self.search_inactive_count = 0  # æç´¢éæ´»è·è®¡æ°å¨
        self.write_lock = Lock()  # åå¥éï¼é²æ­¢å¹¶ååå¥å²çª
        
        # ä¸»æäººç¸å³ç¶æ?
        self.agent_speeches_buffer = []  # agentåè¨ç¼å²å?
        self.host_speech_threshold = 5  # æ¯?æ¡agentåè¨è§¦åä¸æ¬¡ä¸»æäººåè¨
        self.is_host_generating = False  # ä¸»æäººæ¯å¦æ­£å¨çæåè¨
       
        # ç®æ èç¹è¯å«æ¨¡å¼
        # 1. ç±»åï¼æ§æ ¼å¼å¯è½åå«ï¼?
        # 2. å®æ´æ¨¡åè·¯å¾ï¼å®éæ¥å¿æ ¼å¼ï¼åå«å¼æåç¼ï¼?
        # 3. é¨åæ¨¡åè·¯å¾ï¼å¼å®¹æ§ï¼
        # 4. å³é®æ è¯ææ¬
        self.target_node_patterns = [
            'FirstSummaryNode',  # ç±»å
            'ReflectionSummaryNode',  # ç±»å
            'InsightEngine.nodes.summary_node',  # InsightEngineå®æ´è·¯å¾
            'MediaEngine.nodes.summary_node',  # MediaEngineå®æ´è·¯å¾
            'QueryEngine.nodes.summary_node',  # QueryEngineå®æ´è·¯å¾
            'nodes.summary_node',  # æ¨¡åè·¯å¾ï¼å¼å®¹æ§ï¼ç¨äºé¨åå¹éï¼?
            'æ­£å¨çæé¦æ¬¡æ®µè½æ»ç»',  # FirstSummaryNodeçæ è¯?
            'æ­£å¨çæåææ»ç»',  # ReflectionSummaryNodeçæ è¯?
        ]
        
        # å¤è¡åå®¹æè·ç¶æ?
        self.capturing_json = {}  # æ¯ä¸ªappçJSONæè·ç¶æ?
        self.json_buffer = {}     # æ¯ä¸ªappçJSONç¼å²å?
        self.json_start_line = {} # æ¯ä¸ªappçJSONå¼å§è¡
        self.in_error_block = {}  # æ¯ä¸ªappæ¯å¦å¨ERRORåä¸­
       
        # ç¡®ä¿logsç®å½å­å¨
        self.log_dir.mkdir(exist_ok=True)
   
    def clear_forum_log(self):
        """æ¸ç©ºforum.logæä»¶"""
        try:
            if self.forum_log_file.exists():
                self.forum_log_file.unlink()
           
            # åå»ºæ°çforum.logæä»¶å¹¶åå¥å¼å§æ è®?
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # ä½¿ç¨write_to_forum_logå½æ°æ¥åå¥å¼å§æ è®°ï¼ç¡®ä¿æ ¼å¼ä¸è?
            with open(self.forum_log_file, 'w', encoding='utf-8') as f:
                pass  # ååå»ºç©ºæä»¶
            self.write_to_forum_log(f"=== ForumEngine çæ§å¼å§?- {start_time} ===", "SYSTEM")
               
            logger.info(f"ForumEngine: forum.log å·²æ¸ç©ºå¹¶åå§å?)
            
            # éç½®JSONæè·ç¶æ?
            self.capturing_json = {}
            self.json_buffer = {}
            self.json_start_line = {}
            self.in_error_block = {}
            
            # éç½®ä¸»æäººç¸å³ç¶æ?
            self.agent_speeches_buffer = []
            self.is_host_generating = False
           
        except Exception as e:
            logger.exception(f"ForumEngine: æ¸ç©ºforum.logå¤±è´¥: {e}")
   
    def write_to_forum_log(self, content: str, source: str = None):
        """åå¥åå®¹å°forum.logï¼çº¿ç¨å®å¨ï¼"""
        try:
            with self.write_lock:  # ä½¿ç¨éç¡®ä¿çº¿ç¨å®å?
                with open(self.forum_log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime('%H:%M:%S')
                    # å°åå®¹ä¸­çå®éæ¢è¡ç¬¦è½¬æ¢ä¸º\nå­ç¬¦ä¸²ï¼ç¡®ä¿æ´ä¸ªè®°å½å¨ä¸è¡?
                    content_one_line = content.replace('\n', '\\n').replace('\r', '\\r')
                    # å¦ææä¾äºæ¥æºæ ç­¾ï¼åå¨æ¶é´æ³åæ·»å 
                    if source:
                        f.write(f"[{timestamp}] [{source}] {content_one_line}\n")
                    else:
                        f.write(f"[{timestamp}] {content_one_line}\n")
                    f.flush()
        except Exception as e:
            logger.exception(f"ForumEngine: åå¥forum.logå¤±è´¥: {e}")
    
    def get_log_level(self, line: str) -> Optional[str]:
        """æ£æµæ¥å¿è¡ççº§å«ï¼INFO/ERROR/WARNING/DEBUGç­ï¼
        
        æ¯æloguruæ ¼å¼ï¼YYYY-MM-DD HH:mm:ss.SSS | LEVEL | ...
        
        Returns:
            'INFO', 'ERROR', 'WARNING', 'DEBUG' æ?Noneï¼æ æ³è¯å«ï¼
        """
        # æ£æ¥loguruæ ¼å¼ï¼YYYY-MM-DD HH:mm:ss.SSS | LEVEL | ...
        # å¹éæ¨¡å¼ï¼| LEVEL | æ?| LEVEL     |
        match = re.search(r'\|\s*(INFO|ERROR|WARNING|DEBUG|TRACE|CRITICAL)\s*\|', line)
        if match:
            return match.group(1)
        return None
    
    def is_target_log_line(self, line: str) -> bool:
        """æ£æ¥æ¯å¦æ¯ç®æ æ¥å¿è¡ï¼SummaryNodeï¼?
        
        æ¯æå¤ç§è¯å«æ¹å¼ï¼?
        1. ç±»åï¼FirstSummaryNode, ReflectionSummaryNode
        2. å®æ´æ¨¡åè·¯å¾ï¼InsightEngine.nodes.summary_nodeediaEngine.nodes.summary_nodeueryEngine.nodes.summary_node
        3. é¨åæ¨¡åè·¯å¾ï¼nodes.summary_nodeï¼å¼å®¹æ§ï¼
        4. å³é®æ è¯ææ¬ï¼æ­£å¨çæé¦æ¬¡æ®µè½æ»ç»ãæ­£å¨çæåææ»ç»
        
        æé¤æ¡ä»¶ï¼?
        - ERROR çº§å«çæ¥å¿ï¼éè¯¯æ¥å¿ä¸åºè¢«è¯å«ä¸ºç®æ èç¹ï¼?
        - åå«éè¯¯å³é®è¯çæ¥å¿ï¼JSONè§£æå¤±è´¥SONä¿®å¤å¤±è´¥ç­ï¼
        """
        # æé¤ ERROR çº§å«çæ¥å¿?
        log_level = self.get_log_level(line)
        if log_level == 'ERROR':
            return False
        
        # å¼å®¹æ§æ£æ¥æ¹å¼?
        if "| ERROR" in line or "| ERROR    |" in line:
            return False
        
        # æé¤åå«éè¯¯å³é®è¯çæ¥å¿
        error_keywords = ["JSONè§£æå¤±è´¥", "JSONä¿®å¤å¤±è´¥", "Traceback", "File \""]
        for keyword in error_keywords:
            if keyword in line:
                return False
        
        # æ£æ¥æ¯å¦åå«ç®æ èç¹æ¨¡å¼?
        for pattern in self.target_node_patterns:
            if pattern in line:
                return True
        return False
    
    def is_valuable_content(self, line: str) -> bool:
        """å¤æ­æ¯å¦æ¯æä»·å¼çåå®¹ï¼æé¤ç­å°çæç¤ºä¿¡æ¯åéè¯¯ä¿¡æ¯ï¼"""
        # å¦æåå«"æ¸çåçè¾åº"ï¼åè®¤ä¸ºæ¯æä»·å¼ç
        if "æ¸çåçè¾åº" in line:
            return True
        
        # æé¤å¸¸è§çç­å°æç¤ºä¿¡æ¯åéè¯¯ä¿¡æ¯
        exclude_patterns = [
            "JSONè§£æå¤±è´¥",
            "JSONä¿®å¤å¤±è´¥",
            "ç´æ¥ä½¿ç¨æ¸çåçææ¬",
            "JSONè§£ææå",
            "æåçæ",
            "å·²æ´æ°æ®µè?,
            "æ­£å¨çæ",
            "å¼å§å¤ç?,
            "å¤çå®æ",
            "å·²è¯»åHOSTåè¨",
            "è¯»åHOSTåè¨å¤±è´¥",
            "æªæ¾å°HOSTåè¨",
            "è°è¯è¾åº",
            "ä¿¡æ¯è®°å½"
        ]
        
        for pattern in exclude_patterns:
            if pattern in line:
                return False
        
        # å¦æè¡é¿åº¦è¿ç­ï¼ä¹è®¤ä¸ºä¸æ¯æä»·å¼çåå®¹
        # ç§»é¤æ¶é´æ³ï¼æ¯ææ§æ ¼å¼åæ°æ ¼å¼?
        clean_line = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', line)
        clean_line = re.sub(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', clean_line)
        clean_line = clean_line.strip()
        if len(clean_line) < 30:  # éå¼å¯ä»¥è°æ?
            return False
            
        return True
    
    def is_json_start_line(self, line: str) -> bool:
        """å¤æ­æ¯å¦æ¯JSONå¼å§è¡"""
        return "æ¸çåçè¾åº: {" in line
    
    def is_json_end_line(self, line: str) -> bool:
        """å¤æ­æ¯å¦æ¯JSONç»æè¡?
        
        åªå¤æ­çº¯ç²¹çç»ææ è®°è¡ï¼ä¸åå«ä»»ä½æ¥å¿æ ¼å¼ä¿¡æ¯ï¼æ¶é´æ³ç­ï¼
        å¦æè¡åå«æ¶é´æ³ï¼åºè¯¥åæ¸çåå¤æ­ï¼ä½è¿éè¿åFalseè¡¨ç¤ºéè¦è¿ä¸æ­¥å¤ç
        """
        stripped = line.strip()
        
        # å¦æè¡åå«æ¶é´æ³ï¼æ§æ ¼å¼ææ°æ ¼å¼ï¼ï¼è¯´æä¸æ¯çº¯ç²¹çç»æè¡
        # æ§æ ¼å¼ï¼[HH:MM:SS]
        if re.match(r'^\[\d{2}:\d{2}:\d{2}\]', stripped):
            return False
        # æ°æ ¼å¼ï¼YYYY-MM-DD HH:mm:ss.SSS
        if re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}', stripped):
            return False
        
        # ä¸åå«æ¶é´æ³çè¡ï¼æ£æ¥æ¯å¦æ¯çº¯ç»ææ è®?
        if stripped == "}" or stripped == "] }":
            return True
        return False
    
    def extract_json_content(self, json_lines: List[str]) -> Optional[str]:
        """ä»å¤è¡ä¸­æåå¹¶è§£æJSONåå®¹"""
        try:
            # æ¾å°JSONå¼å§çä½ç½®
            json_start_idx = -1
            for i, line in enumerate(json_lines):
                if "æ¸çåçè¾åº: {" in line:
                    json_start_idx = i
                    break
            
            if json_start_idx == -1:
                return None
            
            # æåJSONé¨å
            first_line = json_lines[json_start_idx]
            json_start_pos = first_line.find("æ¸çåçè¾åº: {")
            if json_start_pos == -1:
                return None
            
            json_part = first_line[json_start_pos + len("æ¸çåçè¾åº: "):]
            
            # å¦æç¬¬ä¸è¡å°±åå«å®æ´JSONï¼ç´æ¥å¤ç?
            if json_part.strip().endswith("}") and json_part.count("{") == json_part.count("}"):
                try:
                    json_obj = json.loads(json_part.strip())
                    return self.format_json_content(json_obj)
                except json.JSONDecodeError:
                    # åè¡JSONè§£æå¤±è´¥ï¼å°è¯ä¿®å¤?
                    fixed_json = self.fix_json_string(json_part.strip())
                    if fixed_json:
                        try:
                            json_obj = json.loads(fixed_json)
                            return self.format_json_content(json_obj)
                        except json.JSONDecodeError:
                            pass
                    return None
            
            # å¤çå¤è¡JSON
            json_text = json_part
            for line in json_lines[json_start_idx + 1:]:
                # ç§»é¤æ¶é´æ³ï¼æ¯ææ§æ ¼å¼?[HH:MM:SS] åæ°æ ¼å¼ loguru (YYYY-MM-DD HH:mm:ss.SSS | LEVEL | ...)
                # æ§æ ¼å¼ï¼[HH:MM:SS]
                clean_line = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]\s*', '', line)
                # æ°æ ¼å¼ï¼ç§»é¤ loguru æ ¼å¼çæ¶é´æ³åçº§å«ä¿¡æ?
                # æ ¼å¼: YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
                clean_line = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', clean_line)
                json_text += clean_line
            
            # å°è¯è§£æJSON
            try:
                json_obj = json.loads(json_text.strip())
                return self.format_json_content(json_obj)
            except json.JSONDecodeError:
                # å¤è¡JSONè§£æå¤±è´¥ï¼å°è¯ä¿®å¤?
                fixed_json = self.fix_json_string(json_text.strip())
                if fixed_json:
                    try:
                        json_obj = json.loads(fixed_json)
                        return self.format_json_content(json_obj)
                    except json.JSONDecodeError:
                        pass
                return None
            
        except Exception as e:
            # å¶ä»å¼å¸¸ä¹ä¸æå°éè¯¯ä¿¡æ¯ï¼ç´æ¥è¿åNone
            return None
    
    def format_json_content(self, json_obj: dict) -> str:
        """æ ¼å¼åJSONåå®¹ä¸ºå¯è¯»å½¢å¼?""
        try:
            # æåä¸»è¦åå®¹ï¼ä¼åéæ©åææ»ç»ï¼å¶æ¬¡æ¯é¦æ¬¡æ»ç»
            content = None
            
            if "updated_paragraph_latest_state" in json_obj:
                content = json_obj["updated_paragraph_latest_state"]
            elif "paragraph_latest_state" in json_obj:
                content = json_obj["paragraph_latest_state"]
            
            # å¦ææ¾å°äºåå®¹ï¼ç´æ¥è¿åï¼ä¿ææ¢è¡ç¬¦ä¸º\nï¼?
            if content:
                return content
            
            # å¦ææ²¡ææ¾å°é¢æçå­æ®µï¼è¿åæ´ä¸ªJSONçå­ç¬¦ä¸²è¡¨ç¤º
            return f"æ¸çåçè¾åº: {json.dumps(json_obj, ensure_ascii=False, indent=2)}"
            
        except Exception as e:
            logger.exception(f"ForumEngine: æ ¼å¼åJSONæ¶åºé? {e}")
            return f"æ¸çåçè¾åº: {json.dumps(json_obj, ensure_ascii=False, indent=2)}"

    def extract_node_content(self, line: str) -> Optional[str]:
        """æåèç¹åå®¹ï¼å»é¤æ¶é´æ³ãèç¹åç§°ç­åç¼"""
        content = line
        
        # ç§»é¤æ¶é´æ³é¨åï¼æ¯ææ§æ ¼å¼åæ°æ ¼å¼?
        # æ§æ ¼å¼? [HH:MM:SS]
        match_old = re.search(r'\[\d{2}:\d{2}:\d{2}\]\s*(.+)', content)
        if match_old:
            content = match_old.group(1).strip()
        else:
            # æ°æ ¼å¼? YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
            match_new = re.search(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*(.+)', content)
            if match_new:
                content = match_new.group(1).strip()
        
        if not content:
            return line.strip()
        
        # ç§»é¤ææçæ¹æ¬å·æ ç­¾ï¼åæ¬èç¹åç§°ååºç¨åç§°ï¼
        content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # ç»§ç»­ç§»é¤å¯è½çå¤ä¸ªè¿ç»­æ ç­?
        while re.match(r'^\[.*?\]\s*', content):
            content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # ç§»é¤å¸¸è§åç¼ï¼å¦"é¦æ¬¡æ»ç»: "åææ»ç»: "ç­ï¼
        prefixes_to_remove = [
            "é¦æ¬¡æ»ç»: ",
            "åææ»ç»: ",
            "æ¸çåçè¾åº: "
        ]
        
        for prefix in prefixes_to_remove:
            if content.startswith(prefix):
                content = content[len(prefix):]
                break
        
        # ç§»é¤å¯è½å­å¨çåºç¨åæ ç­¾ï¼ä¸å¨æ¹æ¬å·åçï¼?
        app_names = ['INSIGHT', 'MEDIA', 'QUERY']
        for app_name in app_names:
            # ç§»é¤åç¬çAPP_NAMEï¼å¨è¡é¦ï¼?
            content = re.sub(rf'^{app_name}\s+', '', content, flags=re.IGNORECASE)
        
        # æ¸çå¤ä½çç©ºæ ?
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
   
    def get_file_size(self, file_path: Path) -> int:
        """è·åæä»¶å¤§å°"""
        try:
            return file_path.stat().st_size if file_path.exists() else 0
        except:
            return 0
   
    def get_file_line_count(self, file_path: Path) -> int:
        """è·åæä»¶è¡æ°"""
        try:
            if not file_path.exists():
                return 0
            with open(file_path, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except:
            return 0
   
    def read_new_lines(self, file_path: Path, app_name: str) -> List[str]:
        """è¯»åæä»¶ä¸­çæ°è¡"""
        new_lines = []
       
        try:
            if not file_path.exists():
                return new_lines
           
            current_size = self.get_file_size(file_path)
            last_position = self.file_positions.get(app_name, 0)
           
            # å¦ææä»¶åå°äºï¼è¯´æè¢«æ¸ç©ºäºï¼éæ°ä»å¤´å¼å§?
            if current_size < last_position:
                last_position = 0
                # éç½®JSONæè·ç¶æ?
                self.capturing_json[app_name] = False
                self.json_buffer[app_name] = []
                self.in_error_block[app_name] = False
           
            if current_size > last_position:
                with open(file_path, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    new_lines = new_content.split('\n')
                   
                    # æ´æ°ä½ç½®
                    self.file_positions[app_name] = f.tell()
                   
                    # è¿æ»¤ç©ºè¡
                    new_lines = [line.strip() for line in new_lines if line.strip()]
                   
        except Exception as e:
            logger.exception(f"ForumEngine: è¯»å{app_name}æ¥å¿å¤±è´¥: {e}")
       
        return new_lines
   
    def process_lines_for_json(self, lines: List[str], app_name: str) -> List[str]:
        """å¤çè¡ä»¥æè·å¤è¡JSONåå®¹
        
        å®ç°ERRORåè¿æ»¤ï¼å¦æéå°ERRORçº§å«çæ¥å¿ï¼æç»å¤çç´å°éå°ä¸ä¸ä¸ªINFOçº§å«çæ¥å¿?
        """
        captured_contents = []
        
        # åå§åç¶æ?
        if app_name not in self.capturing_json:
            self.capturing_json[app_name] = False
            self.json_buffer[app_name] = []
        if app_name not in self.in_error_block:
            self.in_error_block[app_name] = False
        
        for line in lines:
            if not line.strip():
                continue
            
            # é¦åæ£æ¥æ¥å¿çº§å«ï¼æ´æ°ERRORåç¶æ?
            log_level = self.get_log_level(line)
            if log_level == 'ERROR':
                # éå°ERRORï¼è¿å¥ERRORåç¶æ?
                self.in_error_block[app_name] = True
                # å¦ææ­£å¨æè·JSONï¼ç«å³åæ­¢å¹¶æ¸ç©ºç¼å²å?
                if self.capturing_json[app_name]:
                    self.capturing_json[app_name] = False
                    self.json_buffer[app_name] = []
                # è·³è¿å½åè¡ï¼ä¸å¤ç?
                continue
            elif log_level == 'INFO':
                # éå°INFOï¼éåºERRORåç¶æ?
                self.in_error_block[app_name] = False
            # å¶ä»çº§å«ï¼WARNINGEBUGç­ï¼ä¿æå½åç¶æ?
            
            # å¦æå¨ERRORåä¸­ï¼æç»å¤çææåå®?
            if self.in_error_block[app_name]:
                # å¦ææ­£å¨æè·JSONï¼ç«å³åæ­¢å¹¶æ¸ç©ºç¼å²å?
                if self.capturing_json[app_name]:
                    self.capturing_json[app_name] = False
                    self.json_buffer[app_name] = []
                # è·³è¿å½åè¡ï¼ä¸å¤ç?
                continue
                
            # æ£æ¥æ¯å¦æ¯ç®æ èç¹è¡åJSONå¼å§æ è®?
            is_target = self.is_target_log_line(line)
            is_json_start = self.is_json_start_line(line)
            
            # åªæç®æ èç¹ï¼SummaryNodeï¼çJSONè¾åºæåºè¯¥è¢«æè·
            # è¿æ»¤æSearchNodeç­å¶ä»èç¹çè¾åºï¼å®ä»¬ä¸æ¯ç®æ èç¹ï¼å³ä½¿æJSONä¹ä¸ä¼è¢«æè·ï¼?
            if is_target and is_json_start:
                # å¼å§æè·JSONï¼å¿é¡»æ¯ç®æ èç¹ä¸åå?æ¸çåçè¾åº: {"ï¼?
                self.capturing_json[app_name] = True
                self.json_buffer[app_name] = [line]
                self.json_start_line[app_name] = line
                
                # æ£æ¥æ¯å¦æ¯åè¡JSON
                if line.strip().endswith("}"):
                    # åè¡JSONï¼ç«å³å¤ç?
                    content = self.extract_json_content([line])
                    if content:  # åªææåè§£æçåå®¹æä¼è¢«è®°å½
                        # å»é¤éå¤çæ ç­¾åæ ¼å¼å?
                        clean_content = self._clean_content_tags(content, app_name)
                        captured_contents.append(f"{clean_content}")
                    self.capturing_json[app_name] = False
                    self.json_buffer[app_name] = []
                    
            elif is_target and self.is_valuable_content(line):
                # å¶ä»æä»·å¼çSummaryNodeåå®¹ï¼å¿é¡»æ¯ç®æ èç¹ä¸æä»·å¼ï¼
                clean_content = self._clean_content_tags(self.extract_node_content(line), app_name)
                captured_contents.append(f"{clean_content}")
                    
            elif self.capturing_json[app_name]:
                # æ­£å¨æè·JSONçåç»­è¡
                self.json_buffer[app_name].append(line)
                
                # æ£æ¥æ¯å¦æ¯JSONç»æ
                # åæ¸çæ¶é´æ³ï¼ç¶åå¤æ­æ¸çåçè¡æ¯å¦æ¯ç»ææ è®?
                cleaned_line = line.strip()
                # æ¸çæ§æ ¼å¼æ¶é´æ³ï¼[HH:MM:SS]
                cleaned_line = re.sub(r'^\[\d{2}:\d{2}:\d{2}\]\s*', '', cleaned_line)
                # æ¸çæ°æ ¼å¼æ¶é´æ³ï¼YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:function:line -
                cleaned_line = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\|\s*[A-Z]+\s*\|\s*[^|]+?\s*-\s*', '', cleaned_line)
                cleaned_line = cleaned_line.strip()
                
                # æ¸çåå¤æ­æ¯å¦æ¯ç»ææ è®°
                if cleaned_line == "}" or cleaned_line == "] }":
                    # JSONç»æï¼å¤çå®æ´çJSON
                    content = self.extract_json_content(self.json_buffer[app_name])
                    if content:  # åªææåè§£æçåå®¹æä¼è¢«è®°å½
                        # å»é¤éå¤çæ ç­¾åæ ¼å¼å?
                        clean_content = self._clean_content_tags(content, app_name)
                        captured_contents.append(f"{clean_content}")
                    
                    # éç½®ç¶æ?
                    self.capturing_json[app_name] = False
                    self.json_buffer[app_name] = []
        
        return captured_contents
    
    def _trigger_host_speech(self):
        """è§¦åä¸»æäººåè¨ï¼åæ­¥æ§è¡ï¼"""
        if not HOST_AVAILABLE or self.is_host_generating:
            return
        
        try:
            # è®¾ç½®çææ å¿
            self.is_host_generating = True
            
            # è·åç¼å²åºç5æ¡åè¨
            recent_speeches = self.agent_speeches_buffer[:5]
            if len(recent_speeches) < 5:
                self.is_host_generating = False
                return
            
            logger.info("ForumEngine: æ­£å¨çæä¸»æäººåè¨...")
            
            # è°ç¨ä¸»æäººçæåè¨ï¼ä¼ å¥æè¿?æ¡ï¼
            host_speech = generate_host_speech(recent_speeches)
            
            if host_speech:
                # åå¥ä¸»æäººåè¨å°forum.log
                self.write_to_forum_log(host_speech, "HOST")
                logger.info(f"ForumEngine: ä¸»æäººåè¨å·²è®°å½?)
                
                # æ¸ç©ºå·²å¤çç5æ¡åè¨
                self.agent_speeches_buffer = self.agent_speeches_buffer[5:]
            else:
                logger.error("ForumEngine: ä¸»æäººåè¨çæå¤±è´¥")
            
            # éç½®çææ å¿
            self.is_host_generating = False
                
        except Exception as e:
            logger.exception(f"ForumEngine: è§¦åä¸»æäººåè¨æ¶åºé? {e}")
            self.is_host_generating = False
    
    def _clean_content_tags(self, content: str, app_name: str) -> str:
        """æ¸çåå®¹ä¸­çéå¤æ ç­¾åå¤ä½åç¼"""
        if not content:
            return content
            
        # åå»é¤ææå¯è½çæ ç­¾æ ¼å¼ï¼åæ?[INSIGHT]MEDIA]QUERY] ç­ï¼
        # ä½¿ç¨æ´å¼ºåçæ¸çæ¹å¼
        all_app_names = ['INSIGHT', 'MEDIA', 'QUERY']
        
        for name in all_app_names:
            # å»é¤ [APP_NAME] æ ¼å¼ï¼å¤§å°åä¸ææï¼
            content = re.sub(rf'\[{name}\]\s*', '', content, flags=re.IGNORECASE)
            # å»é¤åç¬ç?APP_NAME æ ¼å¼
            content = re.sub(rf'^{name}\s+', '', content, flags=re.IGNORECASE)
        
        # å»é¤ä»»ä½å¶ä»çæ¹æ¬å·æ ç­¾
        content = re.sub(r'^\[.*?\]\s*', '', content)
        
        # å»é¤å¯è½çéå¤ç©ºæ ?
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
   
    def monitor_logs(self):
        """æºè½çæ§æ¥å¿æä»¶"""
        logger.info("ForumEngine: è®ºååå»ºä¸?..")
       
        # åå§åæä»¶è¡æ°åä½ç½® - è®°å½å½åç¶æä½ä¸ºåºçº?
        for app_name, log_file in self.monitored_logs.items():
            self.file_line_counts[app_name] = self.get_file_line_count(log_file)
            self.file_positions[app_name] = self.get_file_size(log_file)
            self.capturing_json[app_name] = False
            self.json_buffer[app_name] = []
            self.in_error_block[app_name] = False
            # logger.info(f"ForumEngine: {app_name} åºçº¿è¡æ°: {self.file_line_counts[app_name]}")
       
        while self.is_monitoring:
            try:
                # åæ¶æ£æµä¸ä¸ªlogæä»¶çåå?
                any_growth = False
                any_shrink = False
                captured_any = False
               
                # ä¸ºæ¯ä¸ªlogæä»¶ç¬ç«å¤ç
                for app_name, log_file in self.monitored_logs.items():
                    current_lines = self.get_file_line_count(log_file)
                    previous_lines = self.file_line_counts.get(app_name, 0)
                   
                    if current_lines > previous_lines:
                        any_growth = True
                        # ç«å³è¯»åæ°å¢åå®¹
                        new_lines = self.read_new_lines(log_file, app_name)
                       
                        # åæ£æ¥æ¯å¦éè¦è§¦åæç´¢ï¼åªè§¦åä¸æ¬¡ï¼
                        if not self.is_searching:
                            for line in new_lines:
                                # æ£æ¥æ¯å¦åå«ç®æ èç¹æ¨¡å¼ï¼æ¯æå¤ç§æ ¼å¼ï¼?
                                if line.strip() and self.is_target_log_line(line):
                                    # è¿ä¸æ­¥ç¡®è®¤æ¯é¦æ¬¡æ»ç»èç¹ï¼FirstSummaryNodeæåå?æ­£å¨çæé¦æ¬¡æ®µè½æ»ç»"ï¼?
                                    if 'FirstSummaryNode' in line or 'æ­£å¨çæé¦æ¬¡æ®µè½æ»ç»' in line:
                                        logger.info(f"ForumEngine: å¨{app_name}ä¸­æ£æµå°ç¬¬ä¸æ¬¡è®ºååè¡¨åå®?)
                                        self.is_searching = True
                                        self.search_inactive_count = 0
                                        # æ¸ç©ºforum.logå¼å§æ°ä¼è¯
                                        self.clear_forum_log()
                                        break  # æ¾å°ä¸ä¸ªå°±å¤äºï¼è·³åºå¾ªç?
                       
                        # å¤çæææ°å¢åå®¹ï¼å¦ææ­£å¨æç´¢ç¶æï¼
                        if self.is_searching:
                            # ä½¿ç¨æ°çå¤çé»è¾
                            captured_contents = self.process_lines_for_json(new_lines, app_name)
                            
                            for content in captured_contents:
                                # å°app_nameè½¬æ¢ä¸ºå¤§åä½ä¸ºæ ç­¾ï¼å¦?insight -> INSIGHTï¼?
                                source_tag = app_name.upper()
                                self.write_to_forum_log(content, source_tag)
                                # logger.info(f"ForumEngine: æè· - {content}")
                                captured_any = True
                                
                                # å°åè¨æ·»å å°ç¼å²åºï¼æ ¼å¼åä¸ºå®æ´çæ¥å¿è¡ï¼
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                log_line = f"[{timestamp}] [{source_tag}] {content}"
                                self.agent_speeches_buffer.append(log_line)
                                
                                # æ£æ¥æ¯å¦éè¦è§¦åä¸»æäººåè¨
                                if len(self.agent_speeches_buffer) >= self.host_speech_threshold and not self.is_host_generating:
                                    # åæ­¥è§¦åä¸»æäººåè¨
                                    self._trigger_host_speech()
                   
                    elif current_lines < previous_lines:
                        any_shrink = True
                        # logger.info(f"ForumEngine: æ£æµå° {app_name} æ¥å¿ç¼©ç­ï¼å°éç½®åºçº¿")
                        # éç½®æä»¶ä½ç½®å°æ°çæä»¶æ«å°?
                        self.file_positions[app_name] = self.get_file_size(log_file)
                        # éç½®JSONæè·ç¶æ?
                        self.capturing_json[app_name] = False
                        self.json_buffer[app_name] = []
                        self.in_error_block[app_name] = False
                   
                    # æ´æ°è¡æ°è®°å½
                    self.file_line_counts[app_name] = current_lines
               
                # æ£æ¥æ¯å¦åºè¯¥ç»æå½åæç´¢ä¼è¯?
                if self.is_searching:
                    if any_shrink:
                        # logåç­ï¼ç»æå½åæç´¢ä¼è¯ï¼éç½®ä¸ºç­å¾ç¶æ?
                        # logger.info("ForumEngine: æ¥å¿ç¼©ç­ï¼ç»æå½åæç´¢ä¼è¯ï¼åå°ç­å¾ç¶æ?)
                        self.is_searching = False
                        self.search_inactive_count = 0
                        # éç½®ä¸»æäººç¸å³ç¶æ?
                        self.agent_speeches_buffer = []
                        self.is_host_generating = False
                        # åå¥ç»ææ è®°
                        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.write_to_forum_log(f"=== ForumEngine è®ºåç»æ - {end_time} ===", "SYSTEM")
                        # logger.info("ForumEngine: å·²éç½®åºçº¿ï¼ç­å¾ä¸æ¬¡FirstSummaryNodeè§¦å")
                    elif not any_growth and not captured_any:
                        # æ²¡æå¢é¿ä¹æ²¡ææè·åå®¹ï¼å¢å éæ´»è·è®¡æ?
                        self.search_inactive_count += 1
                        if self.search_inactive_count >= 7200:  # è¶æ¶æ æ´»å¨èªå¨ç»æ?
                            logger.info("ForumEngine: é¿æ¶é´æ æ´»å¨ï¼ç»æè®ºå?)
                            self.is_searching = False
                            self.search_inactive_count = 0
                            # éç½®ä¸»æäººç¸å³ç¶æ?
                            self.agent_speeches_buffer = []
                            self.is_host_generating = False
                            # åå¥ç»ææ è®°
                            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            self.write_to_forum_log(f"=== ForumEngine è®ºåç»æ - {end_time} ===", "SYSTEM")
                    else:
                        self.search_inactive_count = 0  # éç½®è®¡æ°å?
               
                # ç­æä¼ç 
                time.sleep(1)
               
            except Exception as e:
                logger.exception(f"ForumEngine: è®ºåè®°å½ä¸­åºé? {e}")
                import traceback
                traceback.print_exc()
                time.sleep(2)
       
        logger.info("ForumEngine: åæ­¢è®ºåæ¥å¿æä»¶")
   
    def start_monitoring(self):
        """å¼å§æºè½çæ?""
        if self.is_monitoring:
            logger.info("ForumEngine: è®ºåå·²ç»å¨è¿è¡ä¸­")
            return False
       
        try:
            # å¯å¨çæ§
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_logs, daemon=True)
            self.monitor_thread.start()
           
            logger.info("ForumEngine: è®ºåå·²å¯å?)
            return True
           
        except Exception as e:
            logger.exception(f"ForumEngine: å¯å¨è®ºåå¤±è´¥: {e}")
            self.is_monitoring = False
            return False
   
    def stop_monitoring(self):
        """åæ­¢çæ§"""
        if not self.is_monitoring:
            logger.info("ForumEngine: è®ºåæªè¿è¡?)
            return
       
        try:
            self.is_monitoring = False
           
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2)
           
            # åå¥ç»ææ è®°
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.write_to_forum_log(f"=== ForumEngine è®ºåç»æ - {end_time} ===", "SYSTEM")
           
            logger.info("ForumEngine: è®ºåå·²åæ­?)
           
        except Exception as e:
            logger.exception(f"ForumEngine: åæ­¢è®ºåå¤±è´¥: {e}")
   
    def get_forum_log_content(self) -> List[str]:
        """è·åforum.logçåå®?""
        try:
            if not self.forum_log_file.exists():
                return []
           
            with open(self.forum_log_file, 'r', encoding='utf-8') as f:
                return [line.rstrip('\n\r') for line in f.readlines()]
               
        except Exception as e:
            logger.exception(f"ForumEngine: è¯»åforum.logå¤±è´¥: {e}")
            return []

    def fix_json_string(self, json_text: str) -> str:
        """ä¿®å¤JSONå­ç¬¦ä¸²ä¸­çå¸¸è§é®é¢ï¼ç¹å«æ¯æªè½¬ä¹çåå¼å·"""
        try:
            # å°è¯ç´æ¥è§£æï¼å¦ææååè¿ååææ?
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError:
            pass
        
        # ä¿®å¤æªè½¬ä¹çåå¼å·é®é¢?
        # è¿æ¯ä¸ä¸ªæ´æºè½çä¿®å¤æ¹æ³ï¼ä¸é¨å¤çå­ç¬¦ä¸²å¼ä¸­çåå¼å·
        
        try:
            # ä½¿ç¨ç¶ææºæ¹æ³ä¿®å¤JSON
            # éåå­ç¬¦ï¼è·è¸ªæ¯å¦å¨å­ç¬¦ä¸²å¼åé?
            
            fixed_text = ""
            i = 0
            in_string = False
            escape_next = False
            
            while i < len(json_text):
                char = json_text[i]
                
                if escape_next:
                    # å¤çè½¬ä¹å­ç¬¦
                    fixed_text += char
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    # è½¬ä¹å­ç¬¦
                    fixed_text += char
                    escape_next = True
                    i += 1
                    continue
                
                if char == '"' and not escape_next:
                    # éå°åå¼å?
                    if in_string:
                        # å¨å­ç¬¦ä¸²åé¨ï¼æ£æ¥ä¸ä¸ä¸ªå­ç¬?
                        # å¦æä¸ä¸ä¸ªå­ç¬¦æ¯åå·æèéå·æèå¤§æ¬å·ï¼è¯´æè¿æ¯å­ç¬¦ä¸²ç»æ
                        next_char_pos = i + 1
                        while next_char_pos < len(json_text) and json_text[next_char_pos].isspace():
                            next_char_pos += 1
                        
                        if next_char_pos < len(json_text):
                            next_char = json_text[next_char_pos]
                            if next_char in [':', ',', '}']:
                                # è¿æ¯å­ç¬¦ä¸²ç»æï¼éåºå­ç¬¦ä¸²ç¶æ?
                                in_string = False
                                fixed_text += char
                            else:
                                # è¿æ¯å­ç¬¦ä¸²åé¨çå¼å·ï¼éè¦è½¬ä¹?
                                fixed_text += '\\"'
                        else:
                            # æä»¶ç»æï¼éåºå­ç¬¦ä¸²ç¶æ?
                            in_string = False
                            fixed_text += char
                    else:
                        # å­ç¬¦ä¸²å¼å§?
                        in_string = True
                        fixed_text += char
                else:
                    # å¶ä»å­ç¬¦
                    fixed_text += char
                
                i += 1
            
            # å°è¯è§£æä¿®å¤åçJSON
            try:
                json.loads(fixed_text)
                return fixed_text
            except json.JSONDecodeError:
                # ä¿®å¤å¤±è´¥ï¼è¿åNone
                return None
                
        except Exception:
            return None

# å¨å±çæ§å¨å®ä¾?
_monitor_instance = None

def get_monitor() -> LogMonitor:
    """è·åå¨å±çæ§å¨å®ä¾?""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = LogMonitor()
    return _monitor_instance

def start_forum_monitoring():
    """å¯å¨ForumEngineæºè½çæ§"""
    return get_monitor().start_monitoring()

def stop_forum_monitoring():
    """åæ­¢ForumEngineçæ§"""
    get_monitor().stop_monitoring()

def get_forum_log():
    """è·åforum.logåå®¹"""
    return get_monitor().get_forum_log_content()
