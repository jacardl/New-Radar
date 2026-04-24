"""
æ ¹æ®æ¨¡æ¿ç®å½ä¸å¤æºæ¥åï¼çææ´æ¬æ¥åçæ é¢?ç®å½/ä¸»é¢è®¾è®¡
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from ..core import TemplateSection
from ..prompts import (
    SYSTEM_PROMPT_DOCUMENT_LAYOUT,
    build_document_layout_prompt,
)
from ..utils.json_parser import RobustJSONParser, JSONParseError
from .base_node import BaseNode


class DocumentLayoutNode(BaseNode):
    """
    è´è´£çæå¨å±æ é¢ãç®å½ä¸Heroè®¾è®¡

    ç»åæ¨¡æ¿åçãæ¥åæè¦ä¸è®ºåè®¨è®ºï¼æå¯¼æ´æ¬ä¹¦çè§è§ä¸ç»æåºè°
    """

    def __init__(self, llm_client):
        """è®°å½LLMå®¢æ·ç«¯å¹¶è®¾ç½®èç¹åå­ï¼ä¾BaseNodeæ¥å¿ä½¿ç¨"""
        super().__init__(llm_client, "DocumentLayoutNode")
        # åå§åé²æ£JSONè§£æå¨ï¼å¯ç¨ææä¿®å¤ç­ç?
        self.json_parser = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,  # å¯ä»¥æ ¹æ®éè¦å¯ç¨LLMä¿®å¤
            max_repair_attempts=3,
        )

    def run(
        self,
        sections: List[TemplateSection],
        template_markdown: str,
        reports: Dict[str, str],
        forum_logs: str,
        query: str,
        template_overview: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        ç»¼åæ¨¡æ¿+å¤æºåå®¹ï¼çæå¨ä¹¦çæ é¢ãç®å½ç»æä¸ä¸»é¢è²æ¿

        åæ°:
            sections: æ¨¡æ¿åçåçç« èåè¡¨
            template_markdown: æ¨¡æ¿åæï¼ç¨äºLLMçè§£ä¸ä¸æ
            reports: ä¸ä¸ªå¼æçåå®¹æ å°
            forum_logs: è®ºåè®¨è®ºæè¦
            query: ç¨æ·æ¥è¯¢è¯
            template_overview: é¢çæçæ¨¡æ¿æ¦è§ï¼å¯å¤ç¨ä»¥åå°æç¤ºè¯é¿åº¦

        è¿å:
            dict: åå« title/subtitle/toc/hero/themeTokens ç­è®¾è®¡ä¿¡æ¯çå­å¸
        """
        # è®¡ç®è¾å¥æ°æ®éï¼å¤æ­æ¯å¦ä¿¡æ¯ç¨ç?
        total_report_length = sum(len(str(content)) for content in reports.values())
        is_sparse = total_report_length < 2000
        
        # æªæ­è¿é¿ç?reports å?forum_logs é¿åæº¢åº
        truncated_reports = {}
        for k, v in reports.items():
            content = str(v)
            truncated_reports[k] = content[:15000] if len(content) > 15000 else content
            
        truncated_forum_logs = str(forum_logs)[:15000] if forum_logs else ""
        
        # å°æ¨¡æ¿åæãåçç»æä¸å¤æºæ¥åä¸å¹¶åç»LLMï¼ä¾¿äºå¶çè§£å±çº§ä¸ç´ æ?
        payload = {
            "query": query,
            "template": {
                "raw": template_markdown[:5000],  # æ¨¡æ¿ä¹ç¨å¾®æªæ?
                "sections": [section.to_dict() for section in sections],
            },
            "templateOverview": template_overview
            or {
                "title": sections[0].title if sections else "",
                "chapters": [section.to_dict() for section in sections],
            },
            "reports": truncated_reports,
            "forumLogs": truncated_forum_logs,
            "is_sparse_data": is_sparse,
            "pruning_instruction": (
                "ãå¼ºå¶å¨æå¤§çº²ä¿®åªãå½åè¾å¥æ°æ®éæå°ï¼äºå®å¯åº¦è¿ä½ãä½ å¿é¡»ä¸»å¨ç æ PESTWOTãå®éå¾è¡¨ç­æ·±æ°´åºç« èï¼å°æ¥åéçº§ä¸ºä¸ä»½ç®æ¥ãè¯·å?tocPlan ä¸­ç§»é¤è¿äºç« èï¼ç»å¯¹ä¸è¦å¼ºé?LLM å»å¡«æ¨¡æ¿ç¼é åå®¹ 
                if is_sparse else "å½åæ°æ®éæ­£å¸¸ï¼å¯æéä¿ç PESTWOT ç­æ·±åº¦åæç« è
            )
        }

        user_message = build_document_layout_prompt(payload)
        response = self.llm_client.stream_invoke_to_string(
            SYSTEM_PROMPT_DOCUMENT_LAYOUT,
            user_message,
            temperature=0.3,
            top_p=0.9,
        )
        design = self._parse_response(response)
        logger.info("ææ¡£æ é¢/ç®å½è®¾è®¡å·²çæ?)
        return design

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        è§£æLLMè¿åçJSONææ¬ï¼è¥å¤±è´¥åæåºåå¥½éè¯¯

        ä½¿ç¨é²æ£JSONè§£æå¨è¿è¡å¤éä¿®å¤å°è¯ï¼
        1. æ¸çmarkdownæ è®°åæèåå®?
        2. æ¬å°è¯­æ³ä¿®å¤ï¼æ¬å·å¹³è¡¡ãéå·è¡¥å¨ãæ§å¶å­ç¬¦è½¬ä¹ç­ï¼?
        3. ä½¿ç¨json_repairåºè¿è¡é«çº§ä¿®å¤?
        4. å¯éçLLMè¾å©ä¿®å¤

        åæ°:
            raw: LLMåå§è¿åå­ç¬¦ä¸²ï¼åè®¸å¸¦```åè£¹ãæèåå®¹ç­

        è¿å:
            dict: ç»æåçè®¾è®¡ç¨¿

        å¼å¸¸:
            ValueError: å½ååºä¸ºç©ºæJSONè§£æå¤±è´¥æ¶æåº
        """
        try:
            result = self.json_parser.parse(
                raw,
                context_name="ææ¡£è®¾è®¡",
                # ç®å½å­æ®µå·²æ´åä¸º tocPlanï¼è¿éè·éææ°Schemaæ ¡éª
                expected_keys=["title", "tocPlan", "hero"],
            )
            # éªè¯å³é®å­æ®µçç±»å?
            if not isinstance(result.get("title"), str):
                logger.warning("ææ¡£è®¾è®¡ç¼ºå°titleå­æ®µæç±»åéè¯¯ï¼ä½¿ç¨é»è®¤å?)
                result.setdefault("title", "æªå½åæ¥å?)

            # å¤çtocPlanå­æ®µ
            toc_plan = result.get("tocPlan", [])
            if not isinstance(toc_plan, list):
                logger.warning("ææ¡£è®¾è®¡ç¼ºå°tocPlanå­æ®µæç±»åéè¯¯ï¼ä½¿ç¨ç©ºåè¡?)
                result["tocPlan"] = []
            else:
                # æ¸çtocPlanä¸­çdescriptionå­æ®µ
                result["tocPlan"] = self._clean_toc_plan_descriptions(toc_plan)

            if not isinstance(result.get("hero"), dict):
                logger.warning("ææ¡£è®¾è®¡ç¼ºå°heroå­æ®µæç±»åéè¯¯ï¼ä½¿ç¨ç©ºå¯¹è±?)
                result.setdefault("hero", {})

            return result
        except JSONParseError as exc:
            # è½¬æ¢ä¸ºåæçå¼å¸¸ç±»åä»¥ä¿æååå¼å®?
            raise ValueError(f"ææ¡£è®¾è®¡JSONè§£æå¤±è´¥: {exc}") from exc

    def _clean_toc_plan_descriptions(self, toc_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        æ¸çtocPlanä¸­æ¯ä¸ªæ¡ç®çdescriptionå­æ®µï¼ç§»é¤å¯è½çJSONçæ®µ

        åæ°:
            toc_plan: åå§çç®å½è®¡ååè¡?

        è¿å:
            List[Dict[str, Any]]: æ¸çåçç®å½è®¡ååè¡¨
        """
        import re

        def clean_text(text: Any) -> str:
            """æ¸çææ¬ä¸­çJSONçæ®µ"""
            if not text or not isinstance(text, str):
                return ""

            cleaned = text

            # ç§»é¤ä»¥éå·+ç©ºç½+{å¼å¤´çä¸å®æ´JSONå¯¹è±¡
            cleaned = re.sub(r',\s*\{[^}]*$', '', cleaned)

            # ç§»é¤ä»¥éå·+ç©ºç½+[å¼å¤´çä¸å®æ´JSONæ°ç»
            cleaned = re.sub(r',\s*\[[^\]]*$', '', cleaned)

            # ç§»é¤å­¤ç«ç?{ å ä¸åç»­åå®¹ï¼å¦ææ²¡æå¹éç }ï¼?
            open_brace_pos = cleaned.rfind('{')
            if open_brace_pos != -1:
                close_brace_pos = cleaned.rfind('}')
                if close_brace_pos < open_brace_pos:
                    cleaned = cleaned[:open_brace_pos].rstrip(',ï¼\t\n')

            # ç§»é¤å­¤ç«ç?[ å ä¸åç»­åå®¹ï¼å¦ææ²¡æå¹éç ]ï¼?
            open_bracket_pos = cleaned.rfind('[')
            if open_bracket_pos != -1:
                close_bracket_pos = cleaned.rfind(']')
                if close_bracket_pos < open_bracket_pos:
                    cleaned = cleaned[:open_bracket_pos].rstrip(',ï¼\t\n')

            # ç§»é¤çèµ·æ¥åJSONé®å¼å¯¹ççæ®?
            cleaned = re.sub(r',?\s*"[^"]+"\s*:\s*"[^"]*$', '', cleaned)
            cleaned = re.sub(r',?\s*"[^"]+"\s*:\s*[^,}\]]*$', '', cleaned)

            # æ¸çæ«å°¾çéå·åç©ºç?
            cleaned = cleaned.rstrip(',ï¼\t\n')

            return cleaned.strip()

        cleaned_plan = []
        for entry in toc_plan:
            if not isinstance(entry, dict):
                continue

            # æ¸çdescriptionå­æ®µ
            if "description" in entry:
                original_desc = entry["description"]
                cleaned_desc = clean_text(original_desc)

                if cleaned_desc != original_desc:
                    logger.warning(
                        f"æ¸çç®å½é¡?'{entry.get('display', 'unknown')}' çdescriptionå­æ®µä¸­çJSONçæ®µ:\n"
                        f"  åæ: {original_desc[:100]}...\n"
                        f"  æ¸çå? {cleaned_desc[:100]}..."
                    )
                    entry["description"] = cleaned_desc

            cleaned_plan.append(entry)

        return cleaned_plan


__all__ = ["DocumentLayoutNode"]
