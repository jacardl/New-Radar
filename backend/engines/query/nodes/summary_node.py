"""
æ»ç»èç¹å®ç°
è´è´£æ ¹æ®æç´¢ç»æçæåæ´æ°æ®µè½åå®?
"""

import json
from typing import Dict, Any, List
from json.decoder import JSONDecodeError
from loguru import logger

from .base_node import StateMutationNode
from ..state.state import State
from ..prompts import SYSTEM_PROMPT_FIRST_SUMMARY, SYSTEM_PROMPT_REFLECTION_SUMMARY
from ..utils.text_processing import (
    remove_reasoning_from_output,
    clean_json_tags,
    extract_clean_response,
    fix_incomplete_json,
    format_search_results_for_prompt
)

# å¯¼å¥è®ºåè¯»åå·¥å·
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from utils.forum_reader import get_latest_host_speech, format_host_speech_for_prompt
    FORUM_READER_AVAILABLE = True
except ImportError:
    FORUM_READER_AVAILABLE = False
    logger.warning("è­¦å: æ æ³å¯¼å¥forum_readeræ¨¡åï¼å°è·³è¿HOSTåè¨è¯»ååè½")


class FirstSummaryNode(StateMutationNode):
    """æ ¹æ®æç´¢ç»æçææ®µè½é¦æ¬¡æ»ç»çèç?""
    
    def __init__(self, llm_client):
        """
        åå§åé¦æ¬¡æ»ç»èç¹
        
        Args:
            llm_client: LLMå®¢æ·ç«?
        """
        super().__init__(llm_client, "FirstSummaryNode")
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                required_fields = ["title", "content", "search_query", "search_results"]
                return all(field in data for field in required_fields)
            except JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            required_fields = ["title", "content", "search_query", "search_results"]
            return all(field in input_data for field in required_fields)
        return False
    
    def run(self, input_data: Any, **kwargs) -> str:
        """
        è°ç¨LLMçææ®µè½æ»ç»
        
        Args:
            input_data: åå«titleontentearch_queryåsearch_resultsçæ°æ?
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ®µè½æ»ç»åå®¹
        """
        try:
            if not self.validate_input(input_data):
                raise ValueError("è¾å¥æ°æ®æ ¼å¼éè¯¯")
            
            # åå¤è¾å¥æ°æ®
            if isinstance(input_data, str):
                data = json.loads(input_data)
            else:
                data = input_data.copy() if isinstance(input_data, dict) else input_data
            
            # è¯»åææ°çHOSTåè¨ï¼å¦æå¯ç¨ï¼
            if FORUM_READER_AVAILABLE:
                try:
                    host_speech = get_latest_host_speech()
                    if host_speech:
                        # å°HOSTåè¨æ·»å å°è¾å¥æ°æ®ä¸­
                        data['host_speech'] = host_speech
                        logger.info(f"å·²è¯»åHOSTåè¨ï¼é¿åº? {len(host_speech)}å­ç¬¦")
                except Exception as e:
                    logger.exception(f"è¯»åHOSTåè¨å¤±è´¥: {str(e)}")
            
            # è½¬æ¢ä¸ºJSONå­ç¬¦ä¸?
            message = json.dumps(data, ensure_ascii=False)
            
            # å¦ææHOSTåè¨ï¼æ·»å å°æ¶æ¯åé¢ä½ä¸ºåè?
            if FORUM_READER_AVAILABLE and 'host_speech' in data and data['host_speech']:
                formatted_host = format_host_speech_for_prompt(data['host_speech'])
                message = formatted_host + "\n" + message
            
            logger.info("æ­£å¨çæé¦æ¬¡æ®µè½æ»ç»")
            
            # è°ç¨LLMçææ»ç»ï¼æµå¼ï¼å®å¨æ¼æ¥UTF-8ï¼?
            response = self.llm_client.stream_invoke_to_string(
                SYSTEM_PROMPT_FIRST_SUMMARY,
                message,
            )
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info("æåçæé¦æ¬¡æ®µè½æ»ç»")
            return processed_response
            
        except Exception as e:
            logger.exception(f"çæé¦æ¬¡æ»ç»å¤±è´¥: {str(e)}")
            raise e
    
    def process_output(self, output: str) -> str:
        """
        å¤çLLMè¾åºï¼æåæ®µè½åå®?
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            æ®µè½åå®¹
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
                # å°è¯ä¿®å¤JSON
                fixed_json = fix_incomplete_json(cleaned_output)
                if fixed_json:
                    try:
                        result = json.loads(fixed_json)
                        logger.info("JSONä¿®å¤æå")
                    except JSONDecodeError:
                        logger.error("JSONä¿®å¤å¤±è´¥ï¼ç´æ¥ä½¿ç¨æ¸çåçææ?)
                        # å¦æä¸æ¯JSONæ ¼å¼ï¼ç´æ¥è¿åæ¸çåçææ?
                        return cleaned_output
                else:
                    logger.error("æ æ³ä¿®å¤JSONï¼ç´æ¥ä½¿ç¨æ¸çåçææ?)
                    # å¦æä¸æ¯JSONæ ¼å¼ï¼ç´æ¥è¿åæ¸çåçææ?
                    return cleaned_output
            
            # æåæ®µè½åå®¹
            if isinstance(result, dict):
                paragraph_content = result.get("paragraph_latest_state", "")
                if paragraph_content:
                    return paragraph_content
            
            # å¦ææåå¤±è´¥ï¼è¿ååå§æ¸çåçææ?
            return cleaned_output
            
        except Exception as e:
            logger.exception(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            return "æ®µè½æ»ç»çæå¤±è´¥"
    
    def mutate_state(self, input_data: Any, state: State, paragraph_index: int, **kwargs) -> State:
        """
        æ´æ°æ®µè½çææ°æ»ç»å°ç¶æ?
        
        Args:
            input_data: è¾å¥æ°æ®
            state: å½åç¶æ?
            paragraph_index: æ®µè½ç´¢å¼
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ´æ°åçç¶æ?
        """
        try:
            # çææ»ç»
            summary = self.run(input_data, **kwargs)
            
            # æ´æ°ç¶æ?
            if 0 <= paragraph_index < len(state.paragraphs):
                state.paragraphs[paragraph_index].research.latest_summary = summary
                logger.info(f"å·²æ´æ°æ®µè?{paragraph_index} çé¦æ¬¡æ»ç»")
            else:
                raise ValueError(f"æ®µè½ç´¢å¼ {paragraph_index} è¶åºèå´")
            
            state.update_timestamp()
            return state
            
        except Exception as e:
            logger.exception(f"ç¶ææ´æ°å¤±è´? {str(e)}")
            raise e


class ReflectionSummaryNode(StateMutationNode):
    """æ ¹æ®åææç´¢ç»ææ´æ°æ®µè½æ»ç»çèç?""
    
    def __init__(self, llm_client):
        """
        åå§ååææ»ç»èç¹
        
        Args:
            llm_client: LLMå®¢æ·ç«?
        """
        super().__init__(llm_client, "ReflectionSummaryNode")
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                required_fields = ["title", "content", "search_query", "search_results", "paragraph_latest_state"]
                return all(field in data for field in required_fields)
            except JSONDecodeError:
                return False
        elif isinstance(input_data, dict):
            required_fields = ["title", "content", "search_query", "search_results", "paragraph_latest_state"]
            return all(field in input_data for field in required_fields)
        return False
    
    def run(self, input_data: Any, **kwargs) -> str:
        """
        è°ç¨LLMæ´æ°æ®µè½åå®¹
        
        Args:
            input_data: åå«å®æ´åæä¿¡æ¯çæ°æ®
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ´æ°åçæ®µè½åå®¹
        """
        try:
            if not self.validate_input(input_data):
                raise ValueError("è¾å¥æ°æ®æ ¼å¼éè¯¯")
            
            # åå¤è¾å¥æ°æ®
            if isinstance(input_data, str):
                data = json.loads(input_data)
            else:
                data = input_data.copy() if isinstance(input_data, dict) else input_data
            
            # è¯»åææ°çHOSTåè¨ï¼å¦æå¯ç¨ï¼
            if FORUM_READER_AVAILABLE:
                try:
                    host_speech = get_latest_host_speech()
                    if host_speech:
                        # å°HOSTåè¨æ·»å å°è¾å¥æ°æ®ä¸­
                        data['host_speech'] = host_speech
                        logger.info(f"å·²è¯»åHOSTåè¨ï¼é¿åº? {len(host_speech)}å­ç¬¦")
                except Exception as e:
                    logger.exception(f"è¯»åHOSTåè¨å¤±è´¥: {str(e)}")
            
            # è½¬æ¢ä¸ºJSONå­ç¬¦ä¸?
            message = json.dumps(data, ensure_ascii=False)
            
            # å¦ææHOSTåè¨ï¼æ·»å å°æ¶æ¯åé¢ä½ä¸ºåè?
            if FORUM_READER_AVAILABLE and 'host_speech' in data and data['host_speech']:
                formatted_host = format_host_speech_for_prompt(data['host_speech'])
                message = formatted_host + "\n" + message
            
            logger.info("æ­£å¨çæåææ»ç»")
            
            # è°ç¨LLMçææ»ç»ï¼æµå¼ï¼å®å¨æ¼æ¥UTF-8ï¼?
            response = self.llm_client.stream_invoke_to_string(
                SYSTEM_PROMPT_REFLECTION_SUMMARY,
                message,
            )
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info("æåçæåææ»ç»")
            return processed_response
            
        except Exception as e:
            logger.exception(f"çæåææ»ç»å¤±è´¥: {str(e)}")
            raise e
    
    def process_output(self, output: str) -> str:
        """
        å¤çLLMè¾åºï¼æåæ´æ°åçæ®µè½åå®?
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            æ´æ°åçæ®µè½åå®¹
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
                # å°è¯ä¿®å¤JSON
                fixed_json = fix_incomplete_json(cleaned_output)
                if fixed_json:
                    try:
                        result = json.loads(fixed_json)
                        logger.info("JSONä¿®å¤æå")
                    except JSONDecodeError:
                        logger.error("JSONä¿®å¤å¤±è´¥ï¼ç´æ¥ä½¿ç¨æ¸çåçææ?)
                        # å¦æä¸æ¯JSONæ ¼å¼ï¼ç´æ¥è¿åæ¸çåçææ?
                        return cleaned_output
                else:
                    logger.error("æ æ³ä¿®å¤JSONï¼ç´æ¥ä½¿ç¨æ¸çåçææ?)
                    # å¦æä¸æ¯JSONæ ¼å¼ï¼ç´æ¥è¿åæ¸çåçææ?
                    return cleaned_output
            
            # æåæ´æ°åçæ®µè½åå®¹
            if isinstance(result, dict):
                updated_content = result.get("updated_paragraph_latest_state", "")
                if updated_content:
                    return updated_content
            
            # å¦ææåå¤±è´¥ï¼è¿ååå§æ¸çåçææ?
            return cleaned_output
            
        except Exception as e:
            logger.exception(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            return "åææ»ç»çæå¤±è´¥"
    
    def mutate_state(self, input_data: Any, state: State, paragraph_index: int, **kwargs) -> State:
        """
        å°æ´æ°åçæ»ç»åå¥ç¶æ?
        
        Args:
            input_data: è¾å¥æ°æ®
            state: å½åç¶æ?
            paragraph_index: æ®µè½ç´¢å¼
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ´æ°åçç¶æ?
        """
        try:
            # çææ´æ°åçæ»ç»
            updated_summary = self.run(input_data, **kwargs)
            
            # æ´æ°ç¶æ?
            if 0 <= paragraph_index < len(state.paragraphs):
                state.paragraphs[paragraph_index].research.latest_summary = updated_summary
                state.paragraphs[paragraph_index].research.increment_reflection()
                logger.info(f"å·²æ´æ°æ®µè?{paragraph_index} çåææ»ç»")
            else:
                raise ValueError(f"æ®µè½ç´¢å¼ {paragraph_index} è¶åºèå´")
            
            state.update_timestamp()
            return state
            
        except Exception as e:
            logger.exception(f"ç¶ææ´æ°å¤±è´? {str(e)}")
            raise e
