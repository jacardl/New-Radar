"""
æ¥åæ ¼å¼åèç?
è´è´£å°æç»ç ç©¶ç»ææ ¼å¼åä¸ºç¾è§çMarkdownæ¥å
"""

import json
from typing import List, Dict, Any
from loguru import logger

from .base_node import BaseNode
from ..prompts import SYSTEM_PROMPT_REPORT_FORMATTING
from ..utils.text_processing import (
    remove_reasoning_from_output,
    clean_markdown_tags
)




class ReportFormattingNode(BaseNode):
    """æ ¼å¼åæç»æ¥åçèç¹"""
    
    def __init__(self, llm_client):
        """
        åå§åæ¥åæ ¼å¼åèç¹
        
        Args:
            llm_client: LLMå®¢æ·ç«?
        """
        super().__init__(llm_client, "ReportFormattingNode")
    
    def validate_input(self, input_data: Any) -> bool:
        """éªè¯è¾å¥æ°æ®"""
        if isinstance(input_data, str):
            try:
                data = json.loads(input_data)
                return isinstance(data, list) and all(
                    isinstance(item, dict) and "title" in item and "paragraph_latest_state" in item
                    for item in data
                )
            except:
                return False
        elif isinstance(input_data, list):
            return all(
                isinstance(item, dict) and "title" in item and "paragraph_latest_state" in item
                for item in input_data
            )
        return False
    
    def run(self, input_data: Any, **kwargs) -> str:
        """
        è°ç¨LLMçæMarkdownæ ¼å¼æ¥å
        
        Args:
            input_data: åå«æææ®µè½ä¿¡æ¯çåè¡¨
            **kwargs: é¢å¤åæ°
            
        Returns:
            æ ¼å¼åçMarkdownæ¥å
        """
        try:
            if not self.validate_input(input_data):
                raise ValueError("è¾å¥æ°æ®æ ¼å¼éè¯¯ï¼éè¦åå«titleåparagraph_latest_stateçåè¡?)
            
            # åå¤è¾å¥æ°æ®
            if isinstance(input_data, str):
                message = input_data
            else:
                message = json.dumps(input_data, ensure_ascii=False)
            
            logger.info("æ­£å¨æ ¼å¼åæç»æ¥å?)
            
            # è°ç¨LLMï¼æµå¼ï¼å®å¨æ¼æ¥UTF-8ï¼?
            response = self.llm_client.stream_invoke_to_string(
                SYSTEM_PROMPT_REPORT_FORMATTING,
                message,
            )
            
            # å¤çååº
            processed_response = self.process_output(response)
            
            logger.info("æåçææ ¼å¼åæ¥å?)
            return processed_response
            
        except Exception as e:
            logger.exception(f"æ¥åæ ¼å¼åå¤±è´? {str(e)}")
            raise e
    
    def process_output(self, output: str) -> str:
        """
        å¤çLLMè¾åºï¼æ¸çMarkdownæ ¼å¼
        
        Args:
            output: LLMåå§è¾åº
            
        Returns:
            æ¸çåçMarkdownæ¥å
        """
        try:
            # æ¸çååºææ¬
            cleaned_output = remove_reasoning_from_output(output)
            cleaned_output = clean_markdown_tags(cleaned_output)
            
            # ç¡®ä¿æ¥åæåºæ¬ç»æ?
            if not cleaned_output.strip():
                return "# æ¥åçæå¤±è´¥\n\næ æ³çæææçæ¥ååå®¹
            
            # å¦ææ²¡ææ é¢ï¼æ·»å ä¸ä¸ªé»è®¤æ é¢?
            if not cleaned_output.strip().startswith('#'):
                cleaned_output = "# æ·±åº¦ç ç©¶æ¥å\n\n" + cleaned_output
            
            return cleaned_output.strip()
            
        except Exception as e:
            logger.exception(f"å¤çè¾åºå¤±è´¥: {str(e)}")
            return "# æ¥åå¤çå¤±è´¥\n\næ¥åæ ¼å¼åè¿ç¨ä¸­åçéè¯¯
    
    def format_report_manually(self, paragraphs_data: List[Dict[str, str]], 
                             report_title: str = "æ·±åº¦ç ç©¶æ¥å") -> str:
        """
        æå¨æ ¼å¼åæ¥åï¼å¤ç¨æ¹æ³ï¼?
        
        Args:
            paragraphs_data: æ®µè½æ°æ®åè¡¨
            report_title: æ¥åæ é¢
            
        Returns:
            æ ¼å¼åçMarkdownæ¥å
        """
        try:
            logger.info("ä½¿ç¨æå¨æ ¼å¼åæ¹æ³?)
            
            # æå»ºæ¥å
            report_lines = [
                f"# {report_title}",
                "",
                "---",
                ""
            ]
            
            # æ·»å åä¸ªæ®µè½
            for i, paragraph in enumerate(paragraphs_data, 1):
                title = paragraph.get("title", f"æ®µè½ {i}")
                content = paragraph.get("paragraph_latest_state", "")
                
                if content:
                    report_lines.extend([
                        f"## {title}",
                        "",
                        content,
                        "",
                        "---",
                        ""
                    ])
            
            # æ·»å ç»è®º
            if len(paragraphs_data) > 1:
                report_lines.extend([
                    "## ç»è®º",
                    "",
                    "æ¬æ¥åéè¿æ·±åº¦æç´¢åç ç©¶ï¼å¯¹ç¸å³ä¸»é¢è¿è¡äºå¨é¢åæ
                    "ä»¥ä¸åä¸ªæ¹é¢çåå®¹ä¸ºçè§£è¯¥ä¸»é¢æä¾äºéè¦åè,
                    ""
                ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.exception(f"æå¨æ ¼å¼åå¤±è´? {str(e)}")
            return "# æ¥åçæå¤±è´¥\n\næ æ³å®ææ¥åæ ¼å¼å
