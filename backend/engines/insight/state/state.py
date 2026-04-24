"""
Deep Search Agentç¶æç®¡ç?
å®ä¹ææç¶ææ°æ®ç»æåæä½æ¹æ³
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
from datetime import datetime


@dataclass
class Search:
    """åä¸ªæç´¢ç»æçç¶æ?""
    query: str = ""                    # æç´¢æ¥è¯¢
    url: str = ""                      # æç´¢ç»æçé¾æ?
    title: str = ""                    # æç´¢ç»ææ é¢
    content: str = ""                  # æç´¢è¿åçåå®?
    score: Optional[float] = None      # ç¸å³åº¦è¯å?
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼?""
        return {
            "query": self.query,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "score": self.score,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Search":
        """ä»å­å¸åå»ºSearchå¯¹è±¡"""
        return cls(
            query=data.get("query", ""),
            url=data.get("url", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            score=data.get("score"),
            timestamp=data.get("timestamp", datetime.now().isoformat())
        )


@dataclass
class Research:
    """æ®µè½ç ç©¶è¿ç¨çç¶æ?""
    search_history: List[Search] = field(default_factory=list)     # æç´¢è®°å½åè¡¨
    latest_summary: str = ""                                       # å½åæ®µè½çææ°æ»ç»
    reflection_iteration: int = 0                                  # åæè¿­ä»£æ¬¡æ?
    is_completed: bool = False                                     # æ¯å¦å®æç ç©¶
    
    def add_search(self, search: Search):
        """æ·»å æç´¢è®°å½"""
        self.search_history.append(search)
    
    def add_search_results(self, query: str, results: List[Dict[str, Any]]):
        """æ¹éæ·»å æç´¢ç»æ"""
        for result in results:
            search = Search(
                query=query,
                url=result.get("url", ""),
                title=result.get("title", ""),
                content=result.get("content", ""),
                score=result.get("score")
            )
            self.add_search(search)
    
    def get_search_count(self) -> int:
        """è·åæç´¢æ¬¡æ°"""
        return len(self.search_history)
    
    def increment_reflection(self):
        """å¢å åææ¬¡æ?""
        self.reflection_iteration += 1
    
    def mark_completed(self):
        """æ è®°ä¸ºå®æ?""
        self.is_completed = True
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼?""
        return {
            "search_history": [search.to_dict() for search in self.search_history],
            "latest_summary": self.latest_summary,
            "reflection_iteration": self.reflection_iteration,
            "is_completed": self.is_completed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Research":
        """ä»å­å¸åå»ºResearchå¯¹è±¡"""
        search_history = [Search.from_dict(search_data) for search_data in data.get("search_history", [])]
        return cls(
            search_history=search_history,
            latest_summary=data.get("latest_summary", ""),
            reflection_iteration=data.get("reflection_iteration", 0),
            is_completed=data.get("is_completed", False)
        )


@dataclass
class Paragraph:
    """æ¥åä¸­åä¸ªæ®µè½çç¶æ?""
    title: str = ""                                                # æ®µè½æ é¢
    content: str = ""                                              # æ®µè½çé¢æåå®¹ï¼åå§è§åï¼?
    research: Research = field(default_factory=Research)          # ç ç©¶è¿åº¦
    order: int = 0                                                 # æ®µè½é¡ºåº
    
    def is_completed(self) -> bool:
        """æ£æ¥æ®µè½æ¯å¦å®æ?""
        return self.research.is_completed and bool(self.research.latest_summary)
    
    def get_final_content(self) -> str:
        """è·åæç»åå®?""
        return self.research.latest_summary or self.content
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼?""
        return {
            "title": self.title,
            "content": self.content,
            "research": self.research.to_dict(),
            "order": self.order
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Paragraph":
        """ä»å­å¸åå»ºParagraphå¯¹è±¡"""
        research_data = data.get("research", {})
        research = Research.from_dict(research_data) if research_data else Research()
        
        return cls(
            title=data.get("title", ""),
            content=data.get("content", ""),
            research=research,
            order=data.get("order", 0)
        )


@dataclass
class State:
    """æ´ä¸ªæ¥åçç¶æ?""
    query: str = ""                                                # åå§æ¥è¯¢
    task_id: str = ""
    seed_id: str = ""
    report_title: str = ""                                         # æ¥åæ é¢
    paragraphs: List[Paragraph] = field(default_factory=list)     # æ®µè½åè¡¨
    final_report: str = ""                                         # æç»æ¥ååå®?
    is_completed: bool = False                                     # æ¯å¦å®æ
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_paragraph(self, title: str, content: str) -> int:
        """
        æ·»å æ®µè½
        
        Args:
            title: æ®µè½æ é¢
            content: æ®µè½åå®¹
            
        Returns:
            æ®µè½ç´¢å¼
        """
        order = len(self.paragraphs)
        paragraph = Paragraph(title=title, content=content, order=order)
        self.paragraphs.append(paragraph)
        self.update_timestamp()
        return order
    
    def get_paragraph(self, index: int) -> Optional[Paragraph]:
        """è·åæå®ç´¢å¼çæ®µè?""
        if 0 <= index < len(self.paragraphs):
            return self.paragraphs[index]
        return None
    
    def get_completed_paragraphs_count(self) -> int:
        """è·åå·²å®ææ®µè½æ°é?""
        return sum(1 for p in self.paragraphs if p.is_completed())
    
    def get_total_paragraphs_count(self) -> int:
        """è·åæ»æ®µè½æ°é?""
        return len(self.paragraphs)
    
    def is_all_paragraphs_completed(self) -> bool:
        """æ£æ¥æ¯å¦æææ®µè½é½å®æ"""
        return all(p.is_completed() for p in self.paragraphs) if self.paragraphs else False
    
    def mark_completed(self):
        """æ è®°æ´ä¸ªæ¥åä¸ºå®æ?""
        self.is_completed = True
        self.update_timestamp()
    
    def update_timestamp(self):
        """æ´æ°æ¶é´æ?""
        self.updated_at = datetime.now().isoformat()
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """è·åè¿åº¦æè¦"""
        completed = self.get_completed_paragraphs_count()
        total = self.get_total_paragraphs_count()
        
        return {
            "total_paragraphs": total,
            "completed_paragraphs": completed,
            "progress_percentage": (completed / total * 100) if total > 0 else 0,
            "is_completed": self.is_completed,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å¸æ ¼å¼?""
        return {
            "query": self.query,
            "report_title": self.report_title,
            "paragraphs": [p.to_dict() for p in self.paragraphs],
            "final_report": self.final_report,
            "is_completed": self.is_completed,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_json(self, indent: int = 2) -> str:
        """è½¬æ¢ä¸ºJSONå­ç¬¦ä¸?""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "State":
        """ä»å­å¸åå»ºStateå¯¹è±¡"""
        paragraphs = [Paragraph.from_dict(p_data) for p_data in data.get("paragraphs", [])]
        
        return cls(
            query=data.get("query", ""),
            report_title=data.get("report_title", ""),
            paragraphs=paragraphs,
            final_report=data.get("final_report", ""),
            is_completed=data.get("is_completed", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat())
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "State":
        """ä»JSONå­ç¬¦ä¸²åå»ºStateå¯¹è±¡"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def save_to_file(self, filepath: str):
        """ä¿å­ç¶æå°æä»¶"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_json())
    
    @classmethod
    def load_from_file(cls, filepath: str) -> "State":
        """ä»æä»¶å è½½ç¶æ?""
        with open(filepath, 'r', encoding='utf-8') as f:
            json_str = f.read()
        return cls.from_json(json_str)
