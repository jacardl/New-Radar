"""
Forumæ¥å¿è¯»åå·¥å·
ç¨äºè¯»åforum.logä¸­çææ°HOSTåè¨
"""

import re
from pathlib import Path
from typing import Optional, List, Dict
from loguru import logger

def get_latest_host_speech(log_dir: str = "logs") -> Optional[str]:
    """
    è·åforum.logä¸­ææ°çHOSTåè¨
    
    Args:
        log_dir: æ¥å¿ç®å½è·¯å¾
        
    Returns:
        ææ°çHOSTåè¨åå®¹ï¼å¦ææ²¡æåè¿åNone
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"
        
        if not forum_log_path.exists():
            logger.debug("forum.logæä»¶ä¸å­å¨")
            return None
            
        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # ä»åå¾åæ¥æ¾ææ°çHOSTåè¨
        host_speech = None
        for line in reversed(lines):
            # å¹éæ ¼å¼: [æ¶é´] [HOST] åå®¹
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[HOST\]\s*(.+)', line)
            if match:
                _, content = match.groups()
                # å¤çè½¬ä¹çæ¢è¡ç¬¦ï¼è¿åä¸ºå®éæ¢è¡
                host_speech = content.replace('\\n', '\n').strip()
                break
        
        if host_speech:
            logger.info(f"æ¾å°ææ°çHOSTåè¨ï¼é¿åº¦: {len(host_speech)}å­ç¬¦")
        else:
            logger.debug("æªæ¾å°HOSTåè¨")
            
        return host_speech
        
    except Exception as e:
        logger.error(f"è¯»åforum.logå¤±è´¥: {str(e)}")
        return None


def get_all_host_speeches(log_dir: str = "logs") -> List[Dict[str, str]]:
    """
    è·åforum.logä¸­ææçHOSTåè¨
    
    Args:
        log_dir: æ¥å¿ç®å½è·¯å¾
        
    Returns:
        åå«ææHOSTåè¨çåè¡¨ï¼æ¯ä¸ªåç´ æ¯åå«timestampåcontentçå­å¸
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"
        
        if not forum_log_path.exists():
            logger.debug("forum.logæä»¶ä¸å­å¨")
            return []
            
        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        host_speeches = []
        for line in lines:
            # å¹éæ ¼å¼: [æ¶é´] [HOST] åå®¹
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[HOST\]\s*(.+)', line)
            if match:
                timestamp, content = match.groups()
                # å¤çè½¬ä¹çæ¢è¡ç¬¦
                content = content.replace('\\n', '\n').strip()
                host_speeches.append({
                    'timestamp': timestamp,
                    'content': content
                })
        
        logger.info(f"æ¾å°{len(host_speeches)}æ¡HOSTåè¨")
        return host_speeches
        
    except Exception as e:
        logger.error(f"è¯»åforum.logå¤±è´¥: {str(e)}")
        return []


def get_recent_agent_speeches(log_dir: str = "logs", limit: int = 5) -> List[Dict[str, str]]:
    """
    è·åforum.logä¸­æè¿çAgentåè¨ï¼ä¸åæ¬HOSTï¼
    
    Args:
        log_dir: æ¥å¿ç®å½è·¯å¾
        limit: è¿åçæå¤§åè¨æ°é
        
    Returns:
        åå«æè¿Agentåè¨çåè¡¨
    """
    try:
        forum_log_path = Path(log_dir) / "forum.log"
        
        if not forum_log_path.exists():
            return []
            
        with open(forum_log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        agent_speeches = []
        for line in reversed(lines):  # ä»åå¾åè¯»å
            # å¹éæ ¼å¼: [æ¶é´] [AGENT_NAME] åå®¹
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[(INSIGHT|MEDIA|QUERY)\]\s*(.+)', line)
            if match:
                timestamp, agent, content = match.groups()
                # å¤çè½¬ä¹çæ¢è¡ç¬¦
                content = content.replace('\\n', '\n').strip()
                agent_speeches.append({
                    'timestamp': timestamp,
                    'agent': agent,
                    'content': content
                })
                if len(agent_speeches) >= limit:
                    break
        
        agent_speeches.reverse()  # æ¢å¤æ¶é´é¡ºåº
        return agent_speeches
        
    except Exception as e:
        logger.error(f"è¯»åforum.logå¤±è´¥: {str(e)}")
        return []


def format_host_speech_for_prompt(host_speech: str) -> str:
    """
    æ ¼å¼åHOSTåè¨ï¼ç¨äºæ·»å å°promptä¸­
    
    Args:
        host_speech: HOSTåè¨åå®¹
        
    Returns:
        æ ¼å¼ååçåå®¹
    """
    if not host_speech:
        return ""
    
    return f"""
### è®ºåä¸»æäººææ°æ»ç»
ä»¥ä¸æ¯è®ºåä¸»æäººå¯¹åAgentè®¨è®ºçææ°æ»ç»åå¼å¯¼ï¼è¯·åèå¶ä¸­çè§ç¹åå»ºè®®ï¼

{host_speech}

---
"""
