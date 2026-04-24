import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FactCheckerNode:
    """
    äº¤åéªè¯ä¸ç½®ä¿¡åº¦è¯åèç¹ï¼Cross-Validation Node & Confidence Scoringï¼    å¨IRè£éå®æ¯ãæ¸²æHTMLä¹åæ§è¡    åè½ï¼?    1. éåæ¥åçææç« èï¼æ£æ¥æ¯å¦æå¤é¨æ¥æºå¼ç¨æ è®°    2. è®¡ç®å°èçå¼ç¨å¯åº¦ï¼èµäº ç½®ä¿¡åº?(High/Medium/Low Confidence) æ ç­¾    3. å¦æææ®µè½æ²¡æä»»ä½å¼ç¨ä¸è¾å¥æ°æ®è¾å°ï¼å¼ºå¶å ä¸"ç¼ºä¹äºå®æ¯æ"çé¢è²ææ è®°    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def run(self, document_ir: Dict[str, Any], raw_reports: Dict[str, Any]) -> Dict[str, Any]:
        """
        å¯¹å·²çæçDocument IRæ§è¡ç½®ä¿¡åº¦æ³¨å¥åç®åçäºå®éªè¯        æ­¤çæ¬éè¿è®¡ç®ç« èå¼ç¨è§æ æ°éï¼ç´æ¥æ³¨å¥ç½®ä¿¡åº¦Calloutï¼?        å¹¶å¨æ²¡æå¼ç¨çæ®µè½ä¸è¿½å é«äº®ææé        """
        try:
            logger.info("å¼å§æ§è¡?FactCheckerNode äº¤åéªè¯ä¸ç½®ä¿¡åº¦è¯å...")
            chapters = document_ir.get("chapters", [])
            for chapter in chapters:
                self._check_and_score_chapter(chapter)
            logger.info("FactCheckerNode å¤çå®æ")
            return document_ir
        except Exception as e:
            logger.exception(f"FactCheckerNode å¤±è´¥: {e}")
            return document_ir

    def _check_and_score_chapter(self, chapter: Dict[str, Any]):
        blocks = chapter.get("blocks", [])
        
        # ä¸ºäºç»æ¯ä¸?Heading è®¡ç®ç½®ä¿¡åº¦ï¼æä»¬éè¦æ Blocks æ?Heading åå
        current_heading_index = -1
        heading_citation_counts = {}
        
        # 1. ç¬¬ä¸éæ«æï¼ç»è®¡æ¯ä¸ª heading ä¸çå¼ç¨æ°é
        for i, block in enumerate(blocks):
            if block.get("type") == "heading":
                # ä»å¯¹äºçº§åä»¥ä¸çæ é¢è¿è¡äºå®æ ¸æ¥è¯åï¼ä¸çº§æ é¢éå¸¸ä¸ºå¤§ç« èå®¹å¨ï¼æ éè¯å
                level = block.get("level", 2)
                if level > 1:
                    current_heading_index = i
                    heading_citation_counts[current_heading_index] = 0
                else:
                    current_heading_index = -1
            elif current_heading_index != -1:
                # æ£æ¥æ®µè½ä¸­ç?superscript link æ°é
                if block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        marks = inline.get("marks", [])
                        if any(isinstance(m, dict) and m.get("type") == "superscript" for m in marks):
                            heading_citation_counts[current_heading_index] += 1
                elif block.get("type") in ["table", "list", "widget", "pestTable", "swotTable"]:
                    # ç²ç¥ä¼°è®¡ï¼å¦ææå¤æåï¼éå¸¸ä¹åå«æ°æ®æç»æ
                    heading_citation_counts[current_heading_index] += 1
                    
        # 2. ç¬¬äºéæ«æï¼æå¥ç½®ä¿¡åº?Callout å¹¶é»æ­ä½ç½®ä¿¡åº¦ç« è?        new_blocks = []

        for i, block in enumerate(blocks):
            if block.get("type") == "heading":
                # å¦æè¿ä¸ª heading ä¸å¨ heading_citation_counts ä¸­ï¼è¯´æå®æ¯ä¸çº§æ é¢?                if i in heading_citation_counts:
                    citations = heading_citation_counts[i]
                    if citations == 0:
                        new_blocks.append(block)
                        
                        callout_block = {
                            "type": "callout",
                            "tone": "danger",
                            "title": "äºå®æ ¸æ¥è¯åï¼ä½ç½®ä¿¡åº?,
                            "blocks": [
                                {
                                    "type": "paragraph",
                                    "inlines": [
                                        {
                                            "text": "â ï¸ æ¬èåå®¹æªè½éè¿å¤æ¹ä¿¡æ¯æºçäº¤åéªè¯ï¼ç¼ºä¹è¶³å¤çä¸åæ°æ®æºæ¯æï¼æåæ¹è¡¨è¿°ä¸ä¸è´ï¼ãè¿äºåå®¹ä»æä¸å®æ¦çæ¯çå®çï¼è¯·ç»åææ«çåèèµæ?URL èªè¡æ ¸å¯¹ä¸å¤æ­
                                        }
                                    ]
                                }
                            ]
                        }
                        new_blocks.append(callout_block)
                    else:
                        new_blocks.append(block)
                        if citations <= 3:
                            confidence = "ä¸­ç­ç½®ä¿¡åº?
                            tone = "warning"
                            text = "æ¬èåå®¹æå°éä¿¡æ¯æºæ¯æï¼å»ºè®®ç»åå¼ç¨æ¸åäº¤åéªè¯
                        else:
                            confidence = "é«ç½®ä¿¡åº¦"
                            tone = "success"
                            text = "æ¬èåå®¹æåè¶³çå¤é¨ä¿¡æ¯æºï¼å¤å¤å¼ç¨ï¼æ¯æ
                        
                        # å?heading ä¸æ¹æå¥ä¸ä¸?callout block
                        callout_block = {
                            "type": "callout",
                            "tone": tone,
                            "title": f"äºå®æ ¸æ¥è¯åï¼{confidence}",
                            "blocks": [
                                {
                                    "type": "paragraph",
                                    "inlines": [
                                        {
                                            "text": text
                                        }
                                    ]
                                }
                            ]
                        }
                        new_blocks.append(callout_block)
                else:
                    new_blocks.append(block)
            else:
                new_blocks.append(block)
                
        chapter["blocks"] = new_blocks
