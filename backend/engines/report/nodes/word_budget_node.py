"""
ç« èç¯å¹è§åèç¹
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ..core import TemplateSection
from ..prompts import (
    SYSTEM_PROMPT_WORD_BUDGET,
    build_word_budget_prompt,
)
from ..utils.json_parser import RobustJSONParser, JSONParseError
from .base_node import BaseNode


class WordBudgetNode(BaseNode):
    """
    è§ååç« èå­æ°ä¸éç¹

    è¾åºæ»å­æ°ãå¨å±åä½ååä»¥åæ¯ç« /å°èç?target/min/max å­æ°çº¦æ
    """

    def __init__(self, llm_client):
        """ä»è®°å½LLMå®¢æ·ç«¯å¼ç¨ï¼æ¹ä¾¿runé¶æ®µåèµ·è¯·æ±"""
        super().__init__(llm_client, "WordBudgetNode")
        # åå§åé²æ£JSONè§£æå¨ï¼å¯ç¨ææä¿®å¤ç­ç?
        self.json_parser = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,  # å¯ä»¥æ ¹æ®éè¦å¯ç¨LLMä¿®å¤
            max_repair_attempts=3,
        )

    def run(
        self,
        sections: List[TemplateSection],
        design: Dict[str, Any],
        reports: Dict[str, str],
        forum_logs: str,
        query: str,
        template_overview: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        æ ¹æ®è®¾è®¡ç¨¿åææç´ æè§åç« èå­æ°ï¼è®©LLMåä½æ¶ææç¡®ç¯å¹ç®æ 

        åæ°:
            sections: æ¨¡æ¿ç« èåè¡¨
            design: å¸å±èç¹è¿åçè®¾è®¡ç¨¿ï¼title/toc/heroç­ï¼
            reports: ä¸å¼ææ¥åæ å°
            forum_logs: è®ºåæ¥å¿åæ
            query: ç¨æ·æ¥è¯¢è¯
            template_overview: å¯éçæ¨¡æ¿æ¦è§ï¼å«ç« èåä¿¡æ¯

        è¿å:
            dict: ç« èç¯å¹è§åç»æï¼åå?`totalWords`globalGuidelines` ä¸éç«  `chapters`
        """
        # æªæ­è¿é¿çåå®¹é¿åæº¢å?
        truncated_reports = {}
        for k, v in reports.items():
            content = str(v)
            truncated_reports[k] = content[:15000] if len(content) > 15000 else content
            
        truncated_forum_logs = str(forum_logs)[:15000] if forum_logs else ""

        # è¾å¥ä¸­é¤äºç« èéª¨æ¶å¤ï¼è¿åå«å¸å±èç¹è¾åºï¼æ¹ä¾¿çº¦æç¯å¹æ¶åèè§è§ä¸»æ¬?
        payload = {
            "query": query,
            "design": design,
            "sections": [section.to_dict() for section in sections],
            "templateOverview": template_overview
            or {
                "title": sections[0].title if sections else "",
                "chapters": [section.to_dict() for section in sections],
            },
            "reports": truncated_reports,
            "forumLogs": truncated_forum_logs,
        }
        user = build_word_budget_prompt(payload)
        response = self.llm_client.stream_invoke_to_string(
            SYSTEM_PROMPT_WORD_BUDGET,
            user,
            temperature=0.25,
            top_p=0.85,
        )
        plan = self._parse_response(response)
        
        # å¼ºå¶åå¤çï¼ç§»é¤ä»»ä½å¨åå§?template_overview ä¸­ä¸å­å¨çéæ³æ°å¢å°èï¼é²å¹»è§æ©å±ï¼
        if plan.get("chapters") and isinstance(plan["chapters"], list):
            valid_chapters = []
            for ch in plan["chapters"]:
                ch_title = ch.get("title", "")
                ch_id = ch.get("chapterId", "")
                
                # å¯»æ¾å¹éçåå§æ¨¡æ¿ç« è?
                matched_tpl_sec = None
                for sec in sections:
                    if sec.slug == ch_id or sec.title == ch_title:
                        matched_tpl_sec = sec
                        break
                        
                if matched_tpl_sec and "sections" in ch and isinstance(ch["sections"], list):
                    import re
                    valid_sections = []
                    # åå§å¤§çº²çææå­æ é¢åç¼åè¡¨ï¼ä¾å¦?["4.1"]
                    valid_prefixes = []
                    for out_item in matched_tpl_sec.outline:
                        if isinstance(out_item, dict):
                            out_title = out_item.get("title", "")
                        else:
                            out_title = str(out_item)
                        m = re.match(r"^([\d\.]+)", out_title.strip())
                        if m:
                            valid_prefixes.append(m.group(1))
                            
                    for sub_sec in ch["sections"]:
                        if isinstance(sub_sec, dict):
                            sub_title = sub_sec.get("title", "")
                        else:
                            sub_title = str(sub_sec)
                            sub_sec = {"title": sub_title}
                        # å¦æå­èæ é¢çåç¼ä¸å¨ valid_prefixes ä¸­ï¼è¯´ææ?LLM èªå·±åæçï¼å¦?4.2ï¼?
                        m = re.match(r"^([\d\.]+)", sub_title.strip())
                        if m and valid_prefixes:
                            prefix = m.group(1)
                            # å¦æåç¼ä¸æ¯ä»»ä½ææåç¼çç²¾ç¡®å¹éï¼ä¸åç¼ä¸­ææ°å­ï¼å¦ 4.2 ä¸å¨ [4.1] éï¼
                            if prefix not in valid_prefixes:
                                logger.warning(f"åé¤è¶æçæçå­ç« è: {sub_title}")
                                # æéæ³ç« èçå­æ°ç®æ åéç¹åå¹¶å°åæ³çæåä¸ä¸ªç« èé
                                if valid_sections:
                                    valid_sections[-1]["targetWords"] = valid_sections[-1].get("targetWords", 0) + sub_sec.get("targetWords", 0)
                                continue
                        valid_sections.append(sub_sec)
                    ch["sections"] = valid_sections
                    
            logger.info("ç« èå­æ°è§åå·²çæå¹¶å®æè¶æåé¤")
            
        return plan

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        å°LLMè¾åºçJSONææ¬è½¬ä¸ºå­å¸ï¼å¤±è´¥æ¶æç¤ºè§åå¼å¸¸

        ä½¿ç¨é²æ£JSONè§£æå¨è¿è¡å¤éä¿®å¤å°è¯ï¼
        1. æ¸çmarkdownæ è®°åæèåå®?
        2. æ¬å°è¯­æ³ä¿®å¤ï¼æ¬å·å¹³è¡¡ãéå·è¡¥å¨ãæ§å¶å­ç¬¦è½¬ä¹ç­ï¼?
        3. ä½¿ç¨json_repairåºè¿è¡é«çº§ä¿®å¤?
        4. å¯éçLLMè¾å©ä¿®å¤

        åæ°:
            raw: LLMè¿åå¼ï¼å¯è½åå«```åè£¹ãæèåå®¹ç­

        è¿å:
            dict: åæ³çç¯å¹è§åJSON

        å¼å¸¸:
            ValueError: å½ååºä¸ºç©ºæJSONè§£æå¤±è´¥æ¶æåº
        """
        try:
            result = self.json_parser.parse(
                raw,
                context_name="ç¯å¹è§å",
                expected_keys=["totalWords", "globalGuidelines", "chapters"],
            )
            # éªè¯å³é®å­æ®µçç±»å?
            if not isinstance(result.get("totalWords"), (int, float)):
                logger.warning("ç¯å¹è§åç¼ºå°totalWordså­æ®µæç±»åéè¯¯ï¼ä½¿ç¨é»è®¤å?)
                result.setdefault("totalWords", 10000)
            if not isinstance(result.get("globalGuidelines"), list):
                logger.warning("ç¯å¹è§åç¼ºå°globalGuidelineså­æ®µæç±»åéè¯¯ï¼ä½¿ç¨ç©ºåè¡?)
                result.setdefault("globalGuidelines", [])
            if not isinstance(result.get("chapters"), (list, dict)):
                logger.warning("ç¯å¹è§åç¼ºå°chapterså­æ®µæç±»åéè¯¯ï¼ä½¿ç¨ç©ºåè¡?)
                result.setdefault("chapters", [])
            return result
        except JSONParseError as exc:
            # è½¬æ¢ä¸ºåæçå¼å¸¸ç±»åä»¥ä¿æååå¼å®?
            raise ValueError(f"ç¯å¹è§åJSONè§£æå¤±è´¥: {exc}") from exc


__all__ = ["WordBudgetNode"]
