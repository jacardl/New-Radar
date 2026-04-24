"""
Report Engineèç¹åºç±»

ææé«é¶æ¨çèç¹é½ç»§æ¿äºæ­¤ï¼ç»ä¸æ¥å¿ãè¾å¥æ ¡éªä¸ç¶æåæ´æ¥å£
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..llms.base import LLMClient
from ..state.state import ReportState
from loguru import logger

class BaseNode(ABC):
    """
    èç¹åºç±»

    ç»ä¸å®ç°æ¥å¿å·¥å·ãè¾å?è¾åºé©å­ä»¥åLLMå®¢æ·ç«¯ä¾èµæ³¨å¥ï¼
    ä¾¿äºææèç¹åªä¸æ³¨ä¸å¡é»è¾
    """
    
    def __init__(self, llm_client: LLMClient, node_name: str = ""):
        """
        åå§åèç?
        
        Args:
            llm_client: LLMå®¢æ·ç«?
            node_name: èç¹åç§°

        BaseNode ä¼ä¿å­èç¹åä»¥ä¾¿ç»ä¸è¾åºæ¥å¿åç¼
        """
        self.llm_client = llm_client
        self.node_name = node_name or self.__class__.__name__
    
    @abstractmethod
    def run(self, input_data: Any, **kwargs) -> Any:
        """
        æ§è¡èç¹å¤çé»è¾
        
        Args:
            input_data: è¾å¥æ°æ®
            **kwargs: é¢å¤åæ°
            
        Returns:
            å¤çç»æ
        """
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """
        éªè¯è¾å¥æ°æ®
        é»è®¤ç´æ¥éè¿ï¼å­ç±»å¯æéè¦åå®ç°å­æ®µæ£æ¥
        
        Args:
            input_data: è¾å¥æ°æ®
            
        Returns:
            éªè¯æ¯å¦éè¿
        """
        return True
    
    def process_output(self, output: Any) -> Any:
        """
        å¤çè¾åºæ°æ®
        å­ç±»å¯è¦åè¿è¡ç»æåææ ¡éª
        
        Args:
            output: åå§è¾åº
            
        Returns:
            å¤çåçè¾åº
        """
        return output
    
    def log_info(self, message: str):
        """è®°å½ä¿¡æ¯æ¥å¿ï¼å¹¶èªå¨å¸¦ä¸èç¹åä½ä¸ºåç¼""
        formatted_message = f"[{self.node_name}] {message}"
        logger.info(formatted_message)
    
    def log_error(self, message: str):
        """è®°å½éè¯¯æ¥å¿ï¼ä¾¿äºæé""
        formatted_message = f"[{self.node_name}] {message}"
        logger.error(formatted_message)


class StateMutationNode(BaseNode):
    """
    å¸¦ç¶æä¿®æ¹åè½çèç¹åºç±»

    éç¨äºèç¹éè¦ç´æ¥åå?ReportState çåºæ¯
    """
    
    @abstractmethod
    def mutate_state(self, input_data: Any, state: ReportState, **kwargs) -> ReportState:
        """
        ä¿®æ¹ç¶æ

        å­ç±»éè¿åæ°çç¶æå¯¹è±¡æå¨åå°ä¿®æ¹ååä¼ ï¼ä¾æµæ°´çº¿è®°å½
        
        Args:
            input_data: è¾å¥æ°æ®
            state: å½åç¶æ?
            **kwargs: é¢å¤åæ°
            
        Returns:
            ä¿®æ¹åçç¶æ?
        """
        pass
