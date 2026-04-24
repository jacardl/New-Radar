"""
Report Engineç¶æç®¡ç?
å®ä¹æ¥åçæè¿ç¨ä¸­çç®åç¶ææ°æ®ç»æ?
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
from datetime import datetime


@dataclass
class ReportMetadata:
    """ç®åçæ¥ååæ°æ?""
    query: str = ""                      # åå§æ¥è¯¢
    template_used: str = ""              # ä½¿ç¨çæ¨¡æ¿åç§?
    generation_time: float = 0.0         # çæèæ¶ï¼ç§ï¼?
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼?""
        return {
            "query": self.query,
            "template_used": self.template_used,
            "generation_time": self.generation_time,
            "timestamp": self.timestamp
        }


@dataclass 
class ReportState:
    """
    ç®åçæ¥åç¶æç®¡ç

    å­å¨ä»»å¡åºæ¬ä¿¡æ¯ãè¾å¥ãè¾åºä¸åæ°æ®ï¼ä¾Agentä¸Flaskå±å±äº«
    """
    # åºæ¬ä¿¡æ¯
    task_id: str = ""                    # ä»»å¡ID
    query: str = ""                      # åå§æ¥è¯¢
    status: str = "pending"              # ç¶æ? pending, processing, completed, failed
    
    # è¾å¥æ°æ®
    query_engine_report: str = ""        # QueryEngineæ¥å
    media_engine_report: str = ""        # MediaEngineæ¥å  
    insight_engine_report: str = ""      # InsightEngineæ¥å
    forum_logs: str = ""                 # è®ºåæ¥å¿
    
    # å¤çç»æ
    selected_template: str = ""          # éæ©çæ¨¡æ?
    html_content: str = ""               # æç»HTMLåå®¹
    
    # åæ°æ?
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    
    def __post_init__(self):
        """åå§ååå¤ç"""
        if not self.task_id:
            self.task_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metadata.query = self.query
    
    def mark_processing(self):
        """æ è®°ä¸ºå¤çä¸­ï¼åå°çº¿ç¨å¼å§è°åº¦çææµç¨""
        self.status = "processing"
    
    def mark_completed(self):
        """æ è®°ä¸ºå®æï¼åæ¶æå³ç `html_content` å·²å¯ç¨""
        self.status = "completed"
    
    def mark_failed(self, error_message: str = ""):
        """æ è®°ä¸ºå¤±è´¥ï¼å¹¶è®°å½æåä¸æ¬¡éè¯¯æ¶æ¯""
        self.status = "failed"
        self.error_message = error_message
    
    def is_completed(self) -> bool:
        """æ£æ¥æ¯å¦å®æï¼åæ¬ç¶æä¸ºcompletedä¸å­å¨HTMLåå®¹""
        return self.status == "completed" and bool(self.html_content)
    
    def get_progress(self) -> float:
        """è·åè¿åº¦ç¾åæ¯ï¼æç§æ¨¡æ¿/åå®¹ä¸¤ä¸ªé¶æ®µç²ç¥ä¼°ç®""
        if self.status == "completed":
            return 100.0
        elif self.status == "processing":
            # ç®åçè¿åº¦è®¡ç®
            progress = 0.0
            if self.selected_template:
                progress += 30.0
            if self.html_content:
                progress += 70.0
            return progress
        else:
            return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼ï¼æ¹ä¾¿åºååç»åç«¯""
        return {
            "task_id": self.task_id,
            "query": self.query,
            "status": self.status,
            "progress": self.get_progress(),
            "selected_template": self.selected_template,
            "has_html_content": bool(self.html_content),
            "html_content_length": len(self.html_content) if self.html_content else 0,
            "metadata": self.metadata.to_dict(),
            "query_engine_report": self.query_engine_report,
            "media_engine_report": self.media_engine_report,
            "insight_engine_report": self.insight_engine_report,
            "forum_logs": self.forum_logs
        }
    
    def save_to_file(self, file_path: str):
        """ä¿å­ç¶æå°æä»¶ï¼æé¤HTMLæ­£æä»¥æ§å¶ä½ç§¯""
        try:
            state_data = self.to_dict()
            # ä¸ä¿å­å®æ´çHTMLåå®¹å°ç¶ææä»¶ï¼å¤ªå¤§ï¼?
            state_data.pop("html_content", None)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"ä¿å­ç¶ææä»¶å¤±è´? {str(e)}")
    
    @classmethod
    def load_from_file(cls, file_path: str) -> Optional["ReportState"]:
        """ä»æä»¶å è½½ç¶æï¼ä»æ¢å¤å³é®å­æ®µä¾¿äºè°è¯""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # åå»ºReportStateå¯¹è±¡
            state = cls(
                task_id=data.get("task_id", ""),
                query=data.get("query", ""),
                status=data.get("status", "pending"),
                selected_template=data.get("selected_template", "")
            )
            
            # è®¾ç½®åæ°æ?
            metadata_data = data.get("metadata", {})
            state.metadata.template_used = metadata_data.get("template_used", "")
            state.metadata.generation_time = metadata_data.get("generation_time", 0.0)
            
            return state
            
        except Exception as e:
            print(f"å è½½ç¶ææä»¶å¤±è´? {str(e)}")
            return None
