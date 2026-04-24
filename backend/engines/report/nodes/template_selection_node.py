"""
æ¨¡æ¿éæ©èç¹

ç»¼åç¨æ·æ¥è¯¢ãä¸å¼ææ¥åãè®ºåæ¥å¿ä¸æ¬å°æ¨¡æ¿åºï¼
è°ç¨LLMæéæåéçæ¥åéª¨æ¶
"""

import os
import json
from typing import Dict, Any, List, Optional
from loguru import logger

from .base_node import BaseNode
from ..prompts import SYSTEM_PROMPT_TEMPLATE_SELECTION
from ..utils.json_parser import RobustJSONParser, JSONParseError


class TemplateSelectionNode(BaseNode):
    """
    æ¨¡æ¿éæ©å¤çèç¹

    è´è´£åå¤æ¨¡æ¿åéåè¡¨ãæå»ºæç¤ºè¯ãè§£æLLMè¿åç»æï¼?
    å¹¶å¨å¤±è´¥æ¶åéå°åç½®æ¨¡æ¿
    """
    
    def __init__(self, llm_client, template_dir: str = "ReportEngine/report_template"):
        """
        åå§åæ¨¡æ¿éæ©èç¹

        Args:
            llm_client: LLMå®¢æ·ç«?
            template_dir: æ¨¡æ¿ç®å½è·¯å¾
        """
        super().__init__(llm_client, "TemplateSelectionNode")
        self.template_dir = template_dir
        # åå§åé²æ£JSONè§£æå¨ï¼å¯ç¨ææä¿®å¤ç­ç?
        self.json_parser = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,
            max_repair_attempts=3,
        )
        
    def run(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        æ§è¡æ¨¡æ¿éæ©
        
        Args:
            input_data: åå«æ¥è¯¢åæ¥ååå®¹çå­å¸
                - query: åå§æ¥è¯¢
                - reports: ä¸ä¸ªå­agentçæ¥ååè¡?
                - forum_logs: è®ºåæ¥å¿åå®¹
                
        Returns:
            éæ©çæ¨¡æ¿ä¿¡æ¯ï¼åå«åç§°ãåå®¹ä¸éæ©çç±
        """
        logger.info("å¼å§æ¨¡æ¿éæ©...")
        
        query = input_data.get('query', '')
        reports = input_data.get('reports', [])
        forum_logs = input_data.get('forum_logs', '')
        
        # è·åå¯ç¨æ¨¡æ¿
        available_templates = self._get_available_templates()
        
        if not available_templates:
            logger.info("æªæ¾å°é¢è®¾æ¨¡æ¿ï¼ä½¿ç¨åç½®é»è®¤æ¨¡æ¿")
            return self._get_fallback_template()
        
        # ä½¿ç¨LLMè¿è¡æ¨¡æ¿éæ©
        try:
            llm_result = self._llm_template_selection(query, reports, forum_logs, available_templates)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.exception(f"LLMæ¨¡æ¿éæ©å¤±è´¥: {str(e)}")
        
        # å¦æLLMéæ©å¤±è´¥ï¼ä½¿ç¨å¤éæ¹æ¡?
        return self._get_fallback_template()
    

    
    def _llm_template_selection(self, query: str, reports: List[Any], forum_logs: str, 
                              available_templates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        ä½¿ç¨LLMè¿è¡æ¨¡æ¿éæ©

        æé æ¨¡æ¿åè¡¨ä¸æ¥åæè¦ â?è°ç¨LLM â?è§£æJSON â?
        éªè¯æ¨¡æ¿æ¯å¦å­å¨å¹¶è¿åæ åç»æ

        åæ°:
            query: ç¨æ·è¾å¥çä¸»é¢è¯
            reports: å¤ä¸ªåæå¼æçæ¥ååå®¹
            forum_logs: è®ºåæ¥å¿ï¼å¯è½ä¸ºç©º
            available_templates: æ¬å°å¯ç¨æ¨¡æ¿æ¸å

        è¿å:
            dict | None: è¥LLMæåè¿ååæ³ç»æååå«æ¨¡æ¿ä¿¡æ¯ï¼å¦åä¸ºNone
        """
        logger.info("å°è¯ä½¿ç¨LLMè¿è¡æ¨¡æ¿éæ©...")
        
        # æå»ºæ¨¡æ¿åè¡¨
        template_list = "\n".join([f"- {t['name']}: {t['description']}" for t in available_templates])
        
        # æå»ºæ¥ååå®¹æè¦
        reports_summary = ""
        if reports:
            reports_summary = "\n\n=== åæå¼ææ¥ååå®¹ ===\n"
            for i, report in enumerate(reports, 1):
                # è·åæ¥ååå®¹ï¼æ¯æä¸åçæ°æ®æ ¼å¼
                if isinstance(report, dict):
                    content = report.get('content', str(report))
                elif hasattr(report, 'content'):
                    content = report.content
                else:
                    content = str(report)
                
                # æªæ­è¿é¿çåå®¹ï¼ä¿çå?000ä¸ªå­ç¬?
                if len(content) > 1000:
                    content = content[:1000] + "...(åå®¹å·²æªæ?"
                
                reports_summary += f"\næ¥å{i}åå®¹:\n{content}\n"
        
        # æå»ºè®ºåæ¥å¿æè¦
        forum_summary = ""
        if forum_logs and forum_logs.strip():
            forum_summary = "\n\n=== ä¸ä¸ªå¼æçè®¨è®ºåå®?===\n"
            # æªæ­è¿é¿çæ¥å¿åå®¹ï¼ä¿çå?00ä¸ªå­ç¬?
            if len(forum_logs) > 800:
                forum_content = forum_logs[:800] + "...(è®¨è®ºåå®¹å·²æªæ?"
            else:
                forum_content = forum_logs
            forum_summary += forum_content
        
        user_message = f"""æ¥è¯¢åå®¹: {query}

æ¥åæ°é: {len(reports)} ä¸ªåæå¼ææ¥å?
è®ºåæ¥å¿: {'æ? if forum_logs else 'æ?}
{reports_summary}{forum_summary}

å¯ç¨æ¨¡æ¿:
{template_list}

è¯·æ ¹æ®æ¥è¯¢åå®¹ãæ¥ååå®¹åè®ºåæ¥å¿çå·ä½æåµï¼éæ©æåéçæ¨¡æ¿""
        
        # è°ç¨LLM
        response = self.llm_client.stream_invoke_to_string(SYSTEM_PROMPT_TEMPLATE_SELECTION, user_message)

        # æ£æ¥ååºæ¯å¦ä¸ºç©?
        if not response or not response.strip():
            logger.error("LLMè¿åç©ºååº?)
            return None

        logger.info(f"LLMåå§ååº: {response}")

        # å°è¯è§£æJSONååºï¼ä½¿ç¨é²æ£è§£æå¨
        try:
            result = self.json_parser.parse(
                response,
                context_name="æ¨¡æ¿éæ©",
                expected_keys=["template_name", "selection_reason"],
            )

            # éªè¯éæ©çæ¨¡æ¿æ¯å¦å­å?
            selected_template_name = result.get('template_name', '')
            for template in available_templates:
                if template['name'] == selected_template_name or selected_template_name in template['name']:
                    logger.info(f"LLMéæ©æ¨¡æ¿: {selected_template_name}")
                    return {
                        'template_name': template['name'],
                        'template_content': template['content'],
                        'selection_reason': result.get('selection_reason', 'LLMæºè½éæ©')
                    }

            logger.error(f"LLMéæ©çæ¨¡æ¿ä¸å­å¨: {selected_template_name}")
            return None

        except JSONParseError as e:
            logger.error(f"JSONè§£æå¤±è´¥: {str(e)}")
            # å°è¯ä»ææ¬ååºä¸­æåæ¨¡æ¿ä¿¡æ¯
            return self._extract_template_from_text(response, available_templates)
    

    def _extract_template_from_text(self, response: str, available_templates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        ä»ææ¬ååºä¸­æåæ¨¡æ¿ä¿¡æ¯

        å½LLMæªè¾åºåæ³JSONæ¶ï¼å°è¯å¹éæ¨¡æ¿åç§°å³é®å­åéçº§

        åæ°:
            response: éç»æåçLLMææ¬
            available_templates: å¯éæ¨¡æ¿åè¡¨

        è¿å:
            dict | None: å¹éæåæ¶è¿åæ¨¡æ¿è¯¦æï¼å¦åä¸ºNone
        """
        logger.info("å°è¯ä»ææ¬ååºä¸­æåæ¨¡æ¿ä¿¡æ¯")
        
        # æ¥æ¾ååºä¸­æ¯å¦åå«æ¨¡æ¿åç§?
        for template in available_templates:
            template_name_variants = [
                template['name'],
                template['name'].replace('.md', ''),
                template['name'].replace('æ¨¡æ¿', ''),
            ]
            
            for variant in template_name_variants:
                if variant in response:
                    logger.info(f"å¨ååºä¸­æ¾å°æ¨¡æ¿: {template['name']}")
                    return {
                        'template_name': template['name'],
                        'template_content': template['content'],
                        'selection_reason': 'ä»ææ¬ååºä¸­æå'
                    }
        
        return None
    
    def _get_available_templates(self) -> List[Dict[str, Any]]:
        """
        è·åå¯ç¨çæ¨¡æ¿åè¡¨

        æä¸¾æ¨¡æ¿ç®å½ä¸ç `.md` æä»¶å¹¶è¯»ååå®¹ä¸æè¿°å­æ®µ

        è¿å:
            list[dict]: æ¯é¡¹åå« name/path/content/description
        """
        templates = []
        
        if not os.path.exists(self.template_dir):
            logger.error(f"æ¨¡æ¿ç®å½ä¸å­å? {self.template_dir}")
            return templates
        
        # æ¥æ¾ææmarkdownæ¨¡æ¿æä»¶
        for filename in os.listdir(self.template_dir):
            if filename.endswith('.md'):
                template_path = os.path.join(self.template_dir, filename)
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    template_name = filename.replace('.md', '')
                    description = self._extract_template_description(template_name)
                    
                    templates.append({
                        'name': template_name,
                        'path': template_path,
                        'content': content,
                        'description': description
                    })
                except Exception as e:
                    logger.exception(f"è¯»åæ¨¡æ¿æä»¶å¤±è´¥ {filename}: {str(e)}")
        
        return templates
    
    def _extract_template_description(self, template_name: str) -> str:
        """æ ¹æ®æ¨¡æ¿åç§°çææè¿°ï¼æ¹ä¾¿LLMçè§£æ¨¡æ¿å®ä½""
        if 'æ¸¸æ' in template_name:
            return "éç¨äºåæ¬¾æ¸¸æäº§åçå¸åºè¡¨ç°ãç©å®¶åé¦ä¸èè®ºæå¿æ·±åº¦åæ"
        elif 'ä¼ä¸åç' in template_name:
            return "éç¨äºä¼ä¸åçå£°èªåå½¢è±¡åæ"
        elif 'å¸åºç«äº' in template_name:
            return "éç¨äºå¸åºç«äºæ ¼å±åå¯¹æåæ?
        elif 'æ¥å¸¸' in template_name or 'å®æ' in template_name:
            return "éç¨äºæ¥å¸¸çæµåå®ææ±æ¥"
        elif 'æ¿ç­' in template_name or 'è¡ä¸' in template_name:
            return "éç¨äºæ¿ç­å½±ååè¡ä¸å¨æåæ?
        elif 'ç­ç¹' in template_name or 'ç¤¾ä¼' in template_name:
            return "éç¨äºç¤¾ä¼ç­ç¹åå¬å±äºä»¶åæ"
        elif 'çªå' in template_name or 'å±æº' in template_name:
            return "éç¨äºçªåäºä»¶åå±æºå¬å³"
        
        return "éç¨æ¥åæ¨¡æ¿"
    

    
    def _get_fallback_template(self) -> Dict[str, Any]:
        """
        è·åå¤ç¨é»è®¤æ¨¡æ¿ï¼ç©ºæ¨¡æ¿ï¼è®©LLMèªè¡åæ¥ï¼

        è¿å:
            dict: ç»æä½å­æ®µä¸LLMè¿åä¸è´ï¼æ¹ä¾¿ç´æ¥æ¿æ¢
        """
        logger.info("æªæ¾å°åéæ¨¡æ¿ï¼ä½¿ç¨ç©ºæ¨¡æ¿è®©LLMèªè¡åæ¥")
        
        return {
            'template_name': 'èªç±åæ¥æ¨¡æ¿',
            'template_content': '',
            'selection_reason': 'æªæ¾å°åéçé¢è®¾æ¨¡æ¿ï¼è®©LLMæ ¹æ®åå®¹èªè¡è®¾è®¡æ¥åç»æ'
        }
