ï»¿"""
å³é®è¯ä¼åä¸­é´ä»¶
ä½¿ç¨Qwen AIå°Agentçæçæç´¢è¯ä¼åä¸ºæ´éåèææ°æ®åºæ¥è¯¢çå³é®ï¿½?
"""

from openai import OpenAI
import json
import sys
import os
from typing import List, Dict, Any
from dataclasses import dataclass

# æ·»å é¡¹ç®æ ¹ç®å½å°Pythonè·¯å¾ä»¥å¯¼å¥config
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from backend.config import settings
from loguru import logger

# æ·»å utilsç®å½å°Pythonè·¯å¾
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG

@dataclass
class KeywordOptimizationResponse:
    """å³é®è¯ä¼ååï¿½?""
    original_query: str
    optimized_keywords: List[str]
    reasoning: str
    success: bool
    error_message: str = ""

class KeywordOptimizer:
    """
    å³é®è¯ä¼åå¨
    ä½¿ç¨ç¡åºæµå¨çQwen3æ¨¡åå°Agentçæçæç´¢è¯ä¼åä¸ºæ´è´´è¿çå®èæçå³é®è¯
    """
    
    def __init__(self, api_key: str = None, base_url: str = None, model_name: str = None):
        """
        åå§åå³é®è¯ä¼åï¿½?
        
        Args:
            api_key: ç¡åºæµå¨APIå¯é¥ï¼å¦æä¸æä¾åä»éç½®æä»¶è¯»å
            base_url: æ¥å£åºç¡å°åï¼é»è®¤ä½¿ç¨éç½®æä»¶æä¾çSiliconFlowå°å
        """
        self.api_key = api_key or settings.KEYWORD_OPTIMIZER_API_KEY

        if not self.api_key:
            raise ValueError("æªæ¾å°APIå¯é¥ï¼è¯·å¨config.pyä¸­è®¾ç½®KEYWORD_OPTIMIZER_API_KEY")

        self.base_url = base_url or settings.KEYWORD_OPTIMIZER_BASE_URL

        client_kwargs = {
            "api_key": self.api_key,
            "base_url": self.base_url
        }
        if self.base_url and "omnisaas.cn" in self.base_url:
            client_kwargs["default_headers"] = {"apikey": self.api_key}

        self.client = OpenAI(**client_kwargs)
        self.model = model_name or settings.KEYWORD_OPTIMIZER_MODEL_NAME
    
    def optimize_keywords(self, original_query: str, context: str = "") -> KeywordOptimizationResponse:
        """
        ä¼åæç´¢å³é®ï¿½?
        
        Args:
            original_query: Agentçæçåå§æç´¢æ¥ï¿½?
            context: é¢å¤çä¸ä¸æä¿¡æ¯ï¼å¦æ®µè½æ é¢ãåå®¹æè¿°ç­ï¿½?
            
        Returns:
            KeywordOptimizationResponse: ä¼ååçå³é®è¯åï¿½?
        """
        logger.info(f"ð å³é®è¯ä¼åä¸­é´ä»¶: å¤çæ¥è¯¢ '{original_query}'")
        
        try:
            # æå»ºä¼åprompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(original_query, context)
            
            # è°ç¨Qwen API
            response = self._call_qwen_api(system_prompt, user_prompt)
            
            if response["success"]:
                # è§£æååº
                content = response["content"]
                try:
                    # å°è¯è§£æJSONæ ¼å¼çåï¿½?
                    if content.strip().startswith('{'):
                        parsed = json.loads(content)
                        keywords = parsed.get("keywords", [])
                        reasoning = parsed.get("reasoning", "")
                    else:
                        # å¦æä¸æ¯JSONæ ¼å¼ï¼å°è¯ä»ææ¬ä¸­æåå³é®è¯
                        keywords = self._extract_keywords_from_text(content)
                        reasoning = content
                    
                    # éªè¯å³é®è¯è´¨ï¿½?
                    validated_keywords = self._validate_keywords(keywords)
                    
                    logger.info(
                        f"ï¿½?ä¼åæå: {len(validated_keywords)}ä¸ªå³é®è¯" +
                        ("" if not validated_keywords else "\n" +
                         "\n".join([f"   {i}. '{k}'" for i, k in enumerate(validated_keywords, 1)]))
                    )
                        
                    
                    
                    return KeywordOptimizationResponse(
                        original_query=original_query,
                        optimized_keywords=validated_keywords,
                        reasoning=reasoning,
                        success=True
                    )
                
                except Exception as e:
                    logger.exception(f"â ï¸ è§£æååºå¤±è´¥ï¼ä½¿ç¨å¤ç¨æ¹ï¿½? {str(e)}")
                    # å¤ç¨æ¹æ¡ï¼ä»åå§æ¥è¯¢ä¸­æåå³é®è¯
                    fallback_keywords = self._fallback_keyword_extraction(original_query)
                    return KeywordOptimizationResponse(
                        original_query=original_query,
                        optimized_keywords=fallback_keywords,
                        reasoning="APIååºè§£æå¤±è´¥ï¼ä½¿ç¨å¤ç¨å³é®è¯æå",
                        success=True
                    )
            else:
                logger.error(f"ï¿½?APIè°ç¨å¤±è´¥: {response['error']}")
                # ä½¿ç¨å¤ç¨æ¹æ¡
                fallback_keywords = self._fallback_keyword_extraction(original_query)
                return KeywordOptimizationResponse(
                    original_query=original_query,
                    optimized_keywords=fallback_keywords,
                    reasoning="APIè°ç¨å¤±è´¥ï¼ä½¿ç¨å¤ç¨å³é®è¯æå",
                    success=True,
                    error_message=response['error']
                )
                
        except Exception as e:
            logger.error(f"ï¿½?å³é®è¯ä¼åå¤±ï¿½? {str(e)}")
            # æç»å¤ç¨æ¹ï¿½?
            fallback_keywords = self._fallback_keyword_extraction(original_query)
            return KeywordOptimizationResponse(
                original_query=original_query,
                optimized_keywords=fallback_keywords,
                reasoning="ç³»ç»éè¯¯ï¼ä½¿ç¨å¤ç¨å³é®è¯æå",
                success=False,
                error_message=str(e)
            )
    
    def _build_system_prompt(self) -> str:
        """æå»ºç³»ç»prompt"""
        return """ä½ æ¯ä¸ä½ä¸ä¸çSEO/GEOå³é®è¯ç ç©¶ä¸èææ°æ®ææä¸å®¶ãä½ çä»»å¡æ¯å°ç¨æ·æä¾çæç´¢æ¥è¯¢ä¼åä¸ºé«ä»·å¼çå³é®è¯ç©éµï¼ä»¥ä¾¿å¨ç¤¾äº¤åªä½åæç´¢å¼æä¸­åç°æ·±åº¦èæåä¼è´¨åå®¹æºä¼ï¿½?

**æ ¸å¿è¦æ±ä¸æä¼åæä»¤ï¿½?*
1. **ä½ çæçæ¯ä¸ä¸ªå³é®è¯ï¼é½å¿é¡»ä¸åªè½å´ç»ç¨æ·æä¾çãåå§æ¥è¯¢ä¸»ä½ãå±å¼ï¼ç»å¯¹ç¦æ­¢çæä¸åæ¥è¯¢ä¸»ä½æ å³çéç¨åºè¯ï¼å¦"æè¿ç«äºä»ï¿½?ï¿½?ç­æï¿½?ç­ï¼ï¿½?*
2. **å³é®è¯å¿é¡»åå«åå§æ¥è¯¢çæ ¸å¿å®ä½**ï¼ä¾å¦åæ¥è¯¢ï¿½?è¾¾å·´æ°´çä¹å° bug"ï¼çæçè¯å¿é¡»åï¿½?è¾¾å·´"ï¿½?æ°´çä¹å°"ææ¸¸æç¸å³ç§°å¼ï¼å ä¸"bug"ï¿½?å¡æ­»"ï¿½?éªé"ç­åä½ï¼ï¿½?

**å³é®è¯æ©å±ç­ç¥ï¼åºäºä¸ä¸ SEO/GEO Keyword Research Skillï¼ï¼**
1. **æå¾åç±» (Search Intent)**ï¼éå¯¹åæ¥è¯¢çæå¾è¿è¡ç»åï¿½?
   - **Informationalï¼ä¿¡æ¯ç±»ï¿½?*ï¼å¼å¯¼æåãç­çï¼ï¿½?è¾¾å·´æ°´çä¹å° æä¹ï¿½?ï¿½?ä»ä¹æ¯..."ï¿½?å¦ä½..."ï¼ï¿½?
   - **Commercialï¼åä¸è°æ¥ï¼**ï¼è¯æµãå¯¹æ¯ãæä½³åè¡¨ï¼ï¿½?è¾¾å·´æ°´çä¹å° æµè¯"ï¿½?æ°´çä¹å° å¼å¾ä¹°å"ï¿½?æ°´çä¹å° vs å¶ä»æ¸¸æ"ï¼ï¿½?
   - **Navigational/Transactionalï¼å¯¼ï¿½?äº¤æç±»ï¼**ï¼å®æ¹æ¸ éãä¸è½½ãè´­ä¹°ï¼ï¿½?è¾¾å·´æ°´çä¹å° ä¸è½½"ï¿½?æ°´çä¹å° ä»·æ ¼"ï¼ï¿½?
2. **é¿å°¾åä½ (Long-tail Variations)**ï¼è¡¥åä¿®é¥°è¯ï¼ä½å¿é¡»ç´§è·æ ¸å¿è¯ï¿½?
   - åå«ç¹å®åä¼ãå¹´ä»½ãæèä¿®é¥°ç¬¦ï¼å¦"è¾¾å·´æ°´çä¹å° æ°ææ»ç¥"ï¿½?æ°´çä¹å° çå®è¯ä»·"ï¿½?è¾¾å·´æ°´çä¹å° ç ´é²"ï¿½?æ°´çä¹å° 2026"ï¼ï¿½?
3. **GEO ç¸å³ï¿½?(AI-Citation Potential)**ï¼çææ´å®¹æè§¦å AI çæåç­çé®ç­ç»æè¯æ±ï¿½?
   - å®ä¹ï¿½?åè¡¨ï¿½?æç¨ç±»æ¥è¯¢ï¼ï¿½?è¾¾å·´æ°´çä¹å° ä¸ºä»ï¿½?ï¿½?æ°´çä¹å° ä¼ç¼ºï¿½?ï¿½?æ°´çä¹å° å§æè§£æ"ï¼ï¿½?

**åºç¡çº¦æåå**ï¿½?
1. **è´´è¿ç½æ°è¯­è¨**ï¼ä½¿ç¨æ®éç½åçå®ä½¿ç¨çè¯æ±ï¼æ¥å°æ°ï¿½?
2. **é¿åä¸ä¸æ¯è¯­**ï¼åå³ä¸ä½¿ç¨"èæç®¡ç"ï¿½?ä¼ æ­è·¯å¾"ç­å®æ¹å­¦æ¯è¯æ±ï¿½?
3. **ä¸¥ç¦èè¡¥ä¸æåè¯**ï¼ç»ä¸è½èªè¡æé åæ¥è¯¢æªæä¾çæ¸¸æçæ¬å·ãèµæçåç§°ãäºä»¶åæè§è²åï¼ä¾å¦ç»å¯¹ä¸è¦å­ç©ºçæ"æ½®èçºªæ´æ°"ãï¿½?.0åç»"ç­æªç¥å®è¯­ï¼ãä¿®é¥°è¯å¿é¡»ä½¿ç¨éç¨çæå¾è¯æ±ï¼å¦"æ»ç¥"æµè¯"æä¹ç©"è¯ä»·"bug"ç­ï¼ï¿½?
4. **æ°éæ§å¶**ï¼æå°æï¿½?0ä¸ªï¼æå¤æï¿½?0ä¸ªé«è´¨éå³é®è¯ï¿½?
5. **æ ¼å¼ä¸¥æ ¼**ï¼æ¯ä¸ªå³é®è¯é½å¿é¡»æ¯ä¸ä¸ªä¸å¯åå²çç¬ç«è¯æ¡ï¼ä¸¥ç¦å¨è¯æ¡åé¨åå«ç©ºæ ¼ï¿½?

**è¾åºæ ¼å¼**ï¿½?
è¯·ä»¥JSONæ ¼å¼è¿åç»æï¼å¨ reasoning ä¸­ç®è¦è¯ä¼°è¿äºè¯çæç´¢æï¿½?Intent)åå¸ï¿½?AI å¯è§ï¿½?GEO Potential)ï¿½?
{
    "keywords": ["å®ä½+åä½1", "å®ä½+ä¿®é¥°2", "æ ¸å¿ï¿½?"],
    "reasoning": "ç®è¦è¯´ææå¾åå¸åGEOæ½å"
}"""

    def _build_user_prompt(self, original_query: str, context: str) -> str:
        """æå»ºç¨æ·prompt"""
        prompt = f"è¯·å¡å¿ç´§ç´§å´ç»ä»¥ä¸æ ¸å¿å®ä½è¿è¡åæ£ï¼ä¸è¦çææ æä¹çæ³æ³ä¹è¯n\nãåå§æ¥è¯¢ãï¼{original_query}"
        
        if context:
            prompt += f"\n\nãä¸ä¸æä¿¡æ¯ãï¼{context}"
        
        prompt += "\n\nè¯·è¾åºJSONç»æï¿½?
        
        return prompt
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return={"success": False, "error": "å³é®è¯ä¼åæå¡ææ¶ä¸å¯ç¨"})
    def _call_qwen_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """è°ç¨Qwen API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
            )

            if response.choices:
                content = response.choices[0].message.content
                return {"success": True, "content": content}
            else:
                return {"success": False, "error": "APIè¿åæ ¼å¼å¼å¸¸"}
        except Exception as e:
            return {"success": False, "error": f"APIè°ç¨å¼å¸¸: {str(e)}"}
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """ä»ææ¬ä¸­æåå³é®è¯ï¼å½JSONè§£æå¤±è´¥æ¶ä½¿ç¨ï¼"""
        # ç®åçå³é®è¯æåé»è¾
        lines = text.split('\n')
        keywords = []
        
        for line in lines:
            line = line.strip()
            # æ¥æ¾å¯è½çå³é®è¯
            if 'ï¿½? in line or ':' in line:
                parts = line.split('ï¿½?) if 'ï¿½? in line else line.split(':')
                if len(parts) > 1:
                    potential_keywords = parts[1].strip()
                    # å°è¯åå²å³é®ï¿½?
                    if 'ï¿½? in potential_keywords:
                        keywords.extend([k.strip() for k in potential_keywords.split('ï¿½?)])
                    elif ',' in potential_keywords:
                        keywords.extend([k.strip() for k in potential_keywords.split(',')])
                    else:
                        keywords.append(potential_keywords)
        
        # å¦ææ²¡ææ¾å°ï¼å°è¯å¶ä»æ¹ï¿½?
        if not keywords:
            # æ¥æ¾å¼å·ä¸­çåå®¹
            import re
            quoted_content = re.findall(r'["""\'](.*?)["""\']', text)
            keywords.extend(quoted_content)
        
        # æ¸çåéªè¯å³é®è¯
        cleaned_keywords = []
        for keyword in keywords[:20]:  # æï¿½?0ï¿½?
            keyword = keyword.strip().strip('"\'""''')
            if keyword and len(keyword) <= 20:  # åçé¿åº¦
                cleaned_keywords.append(keyword)
        
        return cleaned_keywords[:20]
    
    def _validate_keywords(self, keywords: List[str]) -> List[str]:
        """éªè¯åæ¸çå³é®è¯"""
        validated = []
        
        # ä¸è¯å³é®è¯ï¼è¿äºä¸ä¸æå®æ¹ï¼
        bad_keywords = {
            'æåº¦åæ', 'å¬ä¼ååº', 'æç»ªå¾å',
            'æªæ¥å±æ', 'åå±è¶å¿', 'æç¥è§å', 'æ¿ç­å¯¼å', 'ç®¡çæºå¶'
        }
        
        for keyword in keywords:
            if isinstance(keyword, str):
                keyword = keyword.strip().strip('"\'""''')
                
                # åºæ¬éªè¯
                if (keyword and 
                    len(keyword) <= 20 and 
                    len(keyword) >= 1 and
                    not any(bad_word in keyword for bad_word in bad_keywords)):
                    validated.append(keyword)
        
        return validated[:20]  # æå¤è¿ï¿½?0ä¸ªå³é®è¯
    
    def _fallback_keyword_extraction(self, original_query: str) -> List[str]:
        """å¤ç¨å³é®è¯æåæ¹ï¿½?""
        # ç®åçå³é®è¯æåé»è¾
        # ç§»é¤å¸¸è§çæ ç¨è¯ï¿½?
        stop_words = {'ï¿½?}
        
        # åå²æ¥è¯¢
        import re
        # æç©ºæ ¼ãæ ç¹åï¿½?
        tokens = re.split(r'[\sï¼ãï¼ï¼ï¼ï¼+', original_query)
        
        keywords = []
        for token in tokens:
            token = token.strip()
            if token and token not in stop_words and len(token) >= 2:
                keywords.append(token)
        
        # å¦ææ²¡æææå³é®è¯ï¼ä½¿ç¨åå§æ¥è¯¢çç¬¬ä¸ä¸ªè¯
        if not keywords:
            first_word = original_query.split()[0] if original_query.split() else original_query
            keywords = [first_word] if first_word else ["ç­é¨"]
        
        return keywords[:20]

# å¨å±å®ä¾
keyword_optimizer = KeywordOptimizer()
