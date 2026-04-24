"""
æ¥åç»æçæèç¹
è´è´£æ ¹æ®æ¥è¯¢çææ¥åçæ´ä½ç»æ?
"""

import json
from typing import Dict, Any, List
from json.decoder import JSONDecodeError
from loguru import logger

from .base_node import StateMutationNode
from ..state.state import State
from ..prompts import SYSTEM_PROMPT_REPORT_STRUCTURE
from ..utils.text_processing import (
    remove_reasoning_from_output,
    clean_json_tags,
    extract_clean_response,
    fix_incomplete_json
)


class ReportStructureNode(StateMutationNode):
    """çææ¥åç»æçèç?""
    
    def __init__(self, llm_client, query: str):
        """
        åå§åæ¥åç»æèç?
        
        Args:
            llm_client: LLMå®¢æ·ç«?
            query: ç¨æ·æ¥è¯¢
        """
        super().__init__(llm_client, "ReportStructureNode")
        self.query = query
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        return isinstance(self.query, str) and len(self.query.strip()) > 0
    
    def run(self, input_data: Any = None, **kwargs) -> List[Dict[str, str]]:
        """
        è°ç¨LLMçææ¥åç»æ
        
        Args:
            input_data: è¾å¥æ°æ®ï¼è¿éä¸ä½¿ç¨ï¼ä½¿ç¨åå§åæ¶çqueryï¼?
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ¥åç»æåè¡¨
        """
        try:
            logger.info(f"æ­£å¨ä¸ºæ¥è¯¢çææ¥åç»æ? {self.query}")
            
            # è°ç¨LLMï¼æµå¼ï¼å®å¨æ¼æ¥UTF-8ï¼?
            response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_REPORT_STRUCTURE, self.query)
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info(f"æåçæ {len(processed_response)} ä¸ªæ®µè½ç»æ?)
            return processed_response
            
        except Exception as e:
            logger.exception(f"çææ¥åç»æå¤±è´¥: {str(e)}")
            raise e
    
    def process_output(self, output: str) -> List[Dict[str, str]]:
        """
        å¤çLLMè¾åºï¼æåæ¥åç»æ?
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            å¤çåçæ¥åç»æåè¡¨
        """
        try:
            # æ¸çååºææ¬
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_json_tags(cleaned_output)
            
            # è®°å½æ¸çåçè¾åºç¨äºè°è¯
            logger.info(f"æ¸çåçè¾åº: {cleaned_output}")
            
            # è§£æJSON
            try:
                report_structure = json.loads(cleaned_output)
                logger.info("JSONè§£ææå")
            except JSONDecodeError as e:
                logger.error(f"JSONè§£æå¤±è´¥: {str(e)}")
                # ä½¿ç¨æ´å¼ºå¤§çæåæ¹æ³
                report_structure = extract_clean_response(cleaned_output)
                if "error" in report_structure:
                    logger.error("JSONè§£æå¤±è´¥ï¼å°è¯ä¿®å¤?..")
                    # å°è¯ä¿®å¤JSON
                    fixed_json = fix_incomplete_json(cleaned_output)
                    if fixed_json:
                        try:
                            report_structure = json.loads(fixed_json)
                            logger.info("JSONä¿®å¤æå")
                        except JSONDecodeError:
                            logger.error("JSONä¿®å¤å¤±è´¥")
                            # è¿åé»è®¤ç»æ
                            return self._generate_default_structure()
                    else:
                        logger.error("æ æ³ä¿®å¤JSONï¼ä½¿ç¨é»è®¤ç»æ?)
                        return self._generate_default_structure()
            
            # éªè¯ç»æ
            if not isinstance(report_structure, list):
                logger.info("æ¥åç»æä¸æ¯åè¡¨ï¼å°è¯è½¬æ?..")
                if isinstance(report_structure, dict):
                    # å¦ææ¯åä¸ªå¯¹è±¡ï¼åè£æåè¡?
                    report_structure = [report_structure]
                else:
                    logger.exception("æ¥åç»ææ ¼å¼æ æï¼ä½¿ç¨é»è®¤ç»æ?)
                    return self._generate_default_structure()
            
            # éªè¯æ¯ä¸ªæ®µè½
            validated_structure = []
            for i, paragraph in enumerate(report_structure):
                if not isinstance(paragraph, dict):
                    logger.warning(f"æ®µè½ {i+1} ä¸æ¯å­å¸æ ¼å¼ï¼è·³è¿?)
                    continue
                
                title = paragraph.get("title", f"æ®µè½ {i+1}")
                content = paragraph.get("content", "")
                
                if not title or not content:
                    logger.warning(f"æ®µè½ {i+1} ç¼ºå°æ é¢æåå®¹ï¼è·³è¿")
                    continue
                
                validated_structure.append({
                    "title": title,
                    "content": content
                })
            
            if not validated_structure:
                logger.warning("æ²¡æææçæ®µè½ç»æï¼ä½¿ç¨é»è®¤ç»æ")
                return self._generate_default_structure()
            
            logger.info(f"æåéªè¯ {len(validated_structure)} ä¸ªæ®µè½ç»æ?)
            return validated_structure
            
        except Exception as e:
            logger.exception(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            return self._generate_default_structure()
    
    def _generate_default_structure(self) -> List[Dict[str, str]]:
        """
        çæé»è®¤çæ¥åç»æ?
        
        Returns:
            é»è®¤çæ¥åç»æåè¡?
        """
        logger.info("çæé»è®¤æ¥åç»æ")
        return [
            {
                "title": "ç ç©¶æ¦è¿°",
                "content": "å¯¹æ¥è¯¢ä¸»é¢è¿è¡æ»ä½æ¦è¿°ååæ?
            },
            {
                "title": "æ·±åº¦åæ",
                "content": "æ·±å¥åææ¥è¯¢ä¸»é¢çåä¸ªæ¹é?
            }
        ]
    
    def mutate_state(self, input_data: Any = None, state: State = None, **kwargs) -> State:
        """
        å°æ¥åç»æåå¥ç¶æ?
        
        Args:
            input_data: è¾å¥æ°æ®
            state: å½åç¶æï¼å¦æä¸ºNoneååå»ºæ°ç¶æ?
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ´æ°åçç¶æ?
        """
        if state is None:
            state = State()
        
        try:
            # çææ¥åç»æ
            report_structure = self.run(input_data, **kwargs)
            
            # è®¾ç½®æ¥è¯¢åæ¥åæ é¢?
            state.query = self.query
            if not state.report_title:
                state.report_title = f"å³äº'{self.query}'çæ·±åº¦ç ç©¶æ¥å?
            
            # æ·»å æ®µè½å°ç¶æ?
            for paragraph_data in report_structure:
                state.add_paragraph(
                    title=paragraph_data["title"],
                    content=paragraph_data["content"]
                )
            
            logger.info(f"å·²å° {len(report_structure)} ä¸ªæ®µè½æ·»å å°ç¶æä¸­")
            return state
            
        except Exception as e:
            logger.exception(f"ç¶ææ´æ°å¤±è´? {str(e)}")
            raise e
