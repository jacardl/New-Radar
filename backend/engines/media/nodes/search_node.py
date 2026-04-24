"""
æç´¢èç¹å®ç°
è´è´£çææç´¢æ¥è¯¢ååææ¥è¯?
"""

import json
from typing import Dict, Any
from json.decoder import JSONDecodeError
from loguru import logger

from .base_node import BaseNode
from ..prompts import SYSTEM_PROMPT_FIRST_SEARCH, SYSTEM_PROMPT_REFLECTION
from ..utils.text_processing import (
    remove_reasoning_from_output,
    clean_json_tags,
    extract_clean_response,
    fix_incomplete_json
)


class FirstSearchNode(BaseNode):
    """ä¸ºæ®µè½çæé¦æ¬¡æç´¢æ¥è¯¢çèç¹"""
    
    def __init__(self, llm_client):
        """
        åå§åé¦æ¬¡æç´¢èç?
        
        Args:
            llm_client: LLMå®¢æ·ç«?
        """
        super().__init__(llm_client, "FirstSearchNode")
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                return "title" in data and "content" in data
            except JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            return "title" in input_data and "content" in input_data
        return False
    
    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        """
        è°ç¨LLMçææç´¢æ¥è¯¢åçç?
        
        Args:
            input_data: åå«titleåcontentçå­ç¬¦ä¸²æå­å?
            **kwargs: é¢å¤åæ°
            
        Returns:
            åå«search_queryåreasoningçå­å?
        """
        try:
            if not self.validate_input(input_data):
                raise ValueError("è¾å¥æ°æ®æ ¼å¼éè¯¯ï¼éè¦åå«titleåcontentå­æ®µ")
            
            # åå¤è¾å¥æ°æ®
            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)
            
            logger.info("æ­£å¨çæé¦æ¬¡æç´¢æ¥è¯¢")
            
            # è°ç¨LLM
            response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_FIRST_SEARCH, message)
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info(f"çææç´¢æ¥è¯¢: {processed_response.get('search_query', 'N/A')}")
            return processed_response
            
        except Exception as e:
            logger.exception(f"çæé¦æ¬¡æç´¢æ¥è¯¢å¤±è´¥: {str(e)}")
            raise e
    
    def process_output(self, output: str) -> Dict[str, str]:
        """
        å¤çLLMè¾åºï¼æåæç´¢æ¥è¯¢åæ¨ç
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            åå«search_queryåreasoningçå­å?
        """
        try:
            # æ¸çååºææ¬
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            
            # è®°å½æ¸çåçè¾åºç¨äºè°è¯
            logger.info(f"æ¸çåçè¾åº: {cleaned_output}")
            
            # è§£æJSON
            try:
                result = json.loads(cleaned_output)
                logger.info("JSONè§£ææå")
            except JSONDecodeError as e:
                logger.error(f"JSONè§£æå¤±è´¥: {str(e)}")
                # ä½¿ç¨æ´å¼ºå¤§çæåæ¹æ³
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    logger.error("JSONè§£æå¤±è´¥ï¼å°è¯ä¿®å¤?..")
                    # å°è¯ä¿®å¤JSON
                    fixed_json = fix_incomplete_json(cleaned_output)
                    if fixed_json:
                        try:
                            result = json.loads(fixed_json)
                            logger.info("JSONä¿®å¤æå")
                        except JSONDecodeError:
                            logger.error("JSONä¿®å¤å¤±è´¥")
                            # è¿åé»è®¤æ¥è¯¢
                            return self._get_default_search_query()
                    else:
                        logger.error("æ æ³ä¿®å¤JSONï¼ä½¿ç¨é»è®¤æ¥è¯?)
                        return self._get_default_search_query()
            
            # éªè¯åæ¸çç»æ?
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")
            
            if not search_query:
                logger.warning("æªæ¾å°æç´¢æ¥è¯¢ï¼ä½¿ç¨é»è®¤æ¥è¯¢")
                return self._get_default_search_query()
            
            return {
                "search_query": search_query,
                "reasoning": reasoning
            }
            
        except Exception as e:
            self.log_error(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            # è¿åé»è®¤æ¥è¯¢
            return self._get_default_search_query()
    
    def _get_default_search_query(self) -> Dict[str, str]:
        """
        è·åé»è®¤æç´¢æ¥è¯¢
        
        Returns:
            é»è®¤çæç´¢æ¥è¯¢å­å?
        """
        return {
            "search_query": "ç¸å³ä¸»é¢ç ç©¶",
            "reasoning": "ç±äºè§£æå¤±è´¥ï¼ä½¿ç¨é»è®¤æç´¢æ¥è¯?
        }


class ReflectionNode(BaseNode):
    """åææ®µè½å¹¶çææ°æç´¢æ¥è¯¢çèç¹"""
    
    def __init__(self, llm_client):
        """
        åå§ååæèç?
        
        Args:
            llm_client: LLMå®¢æ·ç«?
        """
        super().__init__(llm_client, "ReflectionNode")
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                required_fields = ["title", "content", "paragraph_latest_state"]
                return all(field in data for field in required_fields)
            except JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            required_fields = ["title", "content", "paragraph_latest_state"]
            return all(field in input_data for field in required_fields)
        return False
    
    def run(self, input_data: Any, **kwargs) -> Dict[str, str]:
        """
        è°ç¨LLMåæå¹¶çææç´¢æ¥è¯¢
        
        Args:
            input_data: åå«titleontentåparagraph_latest_stateçå­ç¬¦ä¸²æå­å?
            **kwargs: é¢å¤åæ°
            
        Returns:
            åå«search_queryåreasoningçå­å?
        """
        try:
            if not self.validate_input(input_data):
                raise ValueError("è¾å¥æ°æ®æ ¼å¼éè¯¯ï¼éè¦åå«titleontentåparagraph_latest_stateå­æ®µ")
            
            # åå¤è¾å¥æ°æ®
            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)
            
            logger.info("æ­£å¨è¿è¡åæå¹¶çææ°æç´¢æ¥è¯?)
            
            # è°ç¨LLM
            response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_REFLECTION, message)
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info(f"åæçææç´¢æ¥è¯? {processed_response.get('search_query', 'N/A')}")
            return processed_response
            
        except Exception as e:
            logger.exception(f"åæçææç´¢æ¥è¯¢å¤±è´? {str(e)}")
            raise e
    
    def process_output(self, output: str) -> Dict[str, str]:
        """
        å¤çLLMè¾åºï¼æåæç´¢æ¥è¯¢åæ¨ç
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            åå«search_queryåreasoningçå­å?
        """
        try:
            # æ¸çååºææ¬
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            
            # è®°å½æ¸çåçè¾åºç¨äºè°è¯
            logger.info(f"æ¸çåçè¾åº: {cleaned_output}")
            
            # è§£æJSON
            try:
                result = json.loads(cleaned_output)
                logger.info("JSONè§£ææå")
            except JSONDecodeError as e:
                logger.error(f"JSONè§£æå¤±è´¥: {str(e)}")
                # ä½¿ç¨æ´å¼ºå¤§çæåæ¹æ³
                result = extract_clean_response(cleaned_output)
                if "error" in result:
                    logger.error("JSONè§£æå¤±è´¥ï¼å°è¯ä¿®å¤?..")
                    # å°è¯ä¿®å¤JSON
                    fixed_json = fix_incomplete_json(cleaned_output)
                    if fixed_json:
                        try:
                            result = json.loads(fixed_json)
                            logger.info("JSONä¿®å¤æå")
                        except JSONDecodeError:
                            logger.error("JSONä¿®å¤å¤±è´¥")
                            # è¿åé»è®¤æ¥è¯¢
                            return self._get_default_reflection_query()
                    else:
                        logger.error("æ æ³ä¿®å¤JSONï¼ä½¿ç¨é»è®¤æ¥è¯?)
                        return self._get_default_reflection_query()
            
            # éªè¯åæ¸çç»æ?
            search_query = result.get("search_query", "")
            reasoning = result.get("reasoning", "")
            
            if not search_query:
                logger.warning("æªæ¾å°æç´¢æ¥è¯¢ï¼ä½¿ç¨é»è®¤æ¥è¯¢")
                return self._get_default_reflection_query()
            
            return {
                "search_query": search_query,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.exception(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            # è¿åé»è®¤æ¥è¯¢
            return self._get_default_reflection_query()
    
    def _get_default_reflection_query(self) -> Dict[str, str]:
        """
        è·åé»è®¤åææç´¢æ¥è¯?
        
        Returns:
            é»è®¤çåææç´¢æ¥è¯¢å­å?
        """
        return {
            "search_query": "æ·±åº¦ç ç©¶è¡¥åä¿¡æ¯",
            "reasoning": "ç±äºè§£æå¤±è´¥ï¼ä½¿ç¨é»è®¤åææç´¢æ¥è¯?
        }
