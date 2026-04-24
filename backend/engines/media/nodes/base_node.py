"""
èç¹åºç±»
å®ä¹ææå¤çèç¹çåºç¡æ¥å£
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from ..llms.base import LLMClient
from ..state.state import State
from loguru import logger


class BaseNode(ABC):
    """èç¹åºç±»"""

    def __init__(self, llm_client: LLMClient, node_name: str = ""):
        """
        åå§åèç?

        Args:
            llm_client: LLMå®¢æ·ç«?
            node_name: èç¹åç§°
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

        Args:
            input_data: è¾å¥æ°æ®

        Returns:
            éªè¯æ¯å¦éè¿
        """
        return True

    def process_output(self, output: Any) -> Any:
        """
        å¤çè¾åºæ°æ®

        Args:
            output: åå§è¾åº

        Returns:
            å¤çåçè¾åº
        """
        return output

    def log_info(self, message: str):
        """è®°å½ä¿¡æ¯æ¥å¿"""
        logger.info(f"[{self.node_name}] {message}")
    
    def log_warning(self, message: str):
        """è®°å½è­¦åæ¥å¿"""
        logger.warning(f"[{self.node_name}] è­¦å: {message}")

    def log_error(self, message: str):
        """è®°å½éè¯¯æ¥å¿"""
        logger.error(f"[{self.node_name}] éè¯¯: {message}")


class StateMutationNode(BaseNode):
    """å¸¦ç¶æä¿®æ¹åè½çèç¹åºç±»"""
    
    @abstractmethod
    def mutate_state(self, input_data: Any, state: State, **kwargs) -> State:
        """
        ä¿®æ¹ç¶æ?
        
        Args:
            input_data: è¾å¥æ°æ®
            state: å½åç¶æ?
            **kwargs: é¢å¤åæ°
            
        Returns:
            ä¿®æ¹åçç¶æ?
        """
        pass
