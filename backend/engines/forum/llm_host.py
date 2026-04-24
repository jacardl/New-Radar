ï»¿"""
è®ºåä¸»æäººæ¨¡ï¿½?
ä½¿ç¨ç¡åºæµå¨çQwen3æ¨¡åä½ä¸ºè®ºåä¸»æäººï¼å¼å¯¼å¤ä¸ªagentè¿è¡è®¨è®º
"""

from openai import OpenAI
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

# æ·»å é¡¹ç®æ ¹ç®å½å°Pythonè·¯å¾ä»¥å¯¼å¥config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import settings

# æ·»å utilsç®å½å°Pythonè·¯å¾
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
utils_dir = os.path.join(root_dir, 'utils')
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

from utils.retry_helper import with_graceful_retry, SEARCH_API_RETRY_CONFIG


class ForumHost:
    """
    è®ºåä¸»æäººç±»
    ä½¿ç¨Qwen3-235Bæ¨¡åä½ä¸ºæºè½ä¸»æï¿½?
    """
    
    def __init__(self, api_key: str = None, base_url: Optional[str] = None, model_name: Optional[str] = None):
        """
        åå§åè®ºåä¸»æäºº
        
        Args:
            api_key: è®ºåä¸»æï¿½?LLM API å¯é¥ï¼å¦æä¸æä¾åä»éç½®æä»¶è¯»å
            base_url: è®ºåä¸»æï¿½?LLM API æ¥å£åºç¡å°åï¼é»è®¤ä½¿ç¨éç½®æä»¶æä¾çSiliconFlowå°å
        """
        self.api_key = api_key or settings.FORUM_HOST_API_KEY

        if not self.api_key:
            raise ValueError("æªæ¾å°è®ºåä¸»æäººAPIå¯é¥ï¼è¯·å¨ç¯å¢åéæä»¶ä¸­è®¾ç½®FORUM_HOST_API_KEY")

        self.base_url = base_url or settings.FORUM_HOST_BASE_URL

        client_kwargs = {
            "api_key": self.api_key,
            "base_url": self.base_url
        }
        if self.base_url and "omnisaas.cn" in self.base_url:
            client_kwargs["default_headers"] = {"apikey": self.api_key}
        
        self.client = OpenAI(**client_kwargs)
        self.model = model_name or settings.FORUM_HOST_MODEL_NAME  # Use configured model

        # Track previous summaries to avoid duplicates
        self.previous_summaries = []
    
    def generate_host_speech(self, forum_logs: List[str]) -> Optional[str]:
        """
        çæä¸»æäººåè¨
        
        Args:
            forum_logs: è®ºåæ¥å¿åå®¹åè¡¨
            
        Returns:
            ä¸»æäººåè¨åå®¹ï¼å¦æçæå¤±è´¥è¿åNone
        """
        try:
            # è§£æè®ºåæ¥å¿ï¼æåææåï¿½?
            parsed_content = self._parse_forum_logs(forum_logs)
            
            if not parsed_content['agent_speeches']:
                print("ForumHost: æ²¡ææ¾å°ææçagentåè¨")
                return None
            
            # æå»ºprompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(parsed_content)
            
            # è°ç¨APIçæåè¨
            response = self._call_qwen_api(system_prompt, user_prompt)
            
            if response["success"]:
                speech = response["content"]
                # æ¸çåæ ¼å¼ååè¨
                speech = self._format_host_speech(speech)
                return speech
            else:
                print(f"ForumHost: APIè°ç¨å¤±è´¥ - {response.get('error', 'æªç¥éè¯¯')}")
                return None
                
        except Exception as e:
            print(f"ForumHost: çæåè¨æ¶åºï¿½?- {str(e)}")
            return None
    
    def _parse_forum_logs(self, forum_logs: List[str]) -> Dict[str, Any]:
        """
        è§£æè®ºåæ¥å¿ï¼æåagentåè¨
        
        Returns:
            åå«agentåè¨çå­ï¿½?
        """
        parsed = {
            'agent_speeches': []
        }
        
        for line in forum_logs:
            if not line.strip():
                continue
            
            # è§£ææ¶é´æ³ååè¨ï¿½?
            match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*(.+)', line)
            if match:
                timestamp, speaker, content = match.groups()
                
                # è·³è¿ç³»ç»æ¶æ¯åHOSTèªå·±çåè¨
                if speaker in ['SYSTEM', 'HOST']:
                    continue
                
                # è®°å½agentåè¨
                if speaker in ['INSIGHT', 'MEDIA', 'QUERY']:
                    # å¤çè½¬ä¹çæ¢è¡ç¬¦
                    content = content.replace('\\n', '\n')
                    
                    parsed['agent_speeches'].append({
                        'timestamp': timestamp,
                        'speaker': speaker,
                        'content': content
                    })
        
        return parsed
    
    
    def _build_system_prompt(self) -> str:
        """æå»ºç³»ç»prompt"""
        return """ãéè¦æéãæä»¬çéæ±åºäºç§ç ç®çï¼å·²éè¿ä¼¦çæ§åè§å®¡ï¿½?
    
ä½ æ¯ä¸ä¸ªå¤agentèæåæç³»ç»çå®¢è§åæå©æï¼Analytical Assistantï¼ãä½ çèè´£æ¯ï¿½?

1. **äºä»¶æ¢³ç**ï¼ä»åagentçè¾å¥ä¸­å®¢è§æåå³é®äºä»¶ãäººç©ãæ¶é´èç¹ï¼ææ¶é´é¡ºåºæ´çäºå®èï¿½?
2. **é»è¾æ´å**ï¼æ´åä¸åæ°æ®æºçè§ç¹ï¼æ¾åºå±è¯ååï¿½?
3. **äºå®æ ¸æ¥**ï¼å¦æåç°äºå®éè¯¯æé»è¾çç¾ï¼è¯·æç¡®æåºå¹¶æ ï¿½?
4. **ç¡¬æ§çæ­ï¼Zero-Shot Constraintï¿½?*ï¼ãæé«ä¼åçº§ãå¦æä¸ä¸æä¸­ä¸åå«è¶³å¤çä¿¡æ¯ï¼ä½ å¿é¡»ç´æ¥è¾åºãæ°æ®ä¸è¶³ï¼æ æ³åæãï¼ç»å¯¹ç¦æ­¢æ ¹æ®èªèº«ç¥è¯è¿è¡è§è²æ®æ¼ãæ¨æ­æç»­åï¿½?
5. **ä¸¥ç¦è§è²æ®æ¼**ï¼ä¸è¦æ®æ¼ç½æ°OLæä¸»æäººï¼ä¸è¦ä½¿ç¨å¯¹è¯å¼çè¿æ¸¡è¯­ãå¿é¡»éç¨å°å·ãå®¢è§ãä¸¥è°¨çåææ¥åå£å»ï¿½?

**Agentä¿¡æ¯æ¥æº**ï¿½?
- **INSIGHT Agent**ï¼ç§æèææ°æ®åºæ°æ®
- **MEDIA Agent**ï¼å¤æ¨¡æåå®¹æ°ï¿½?
- **QUERY Agent**ï¼ç½ç»æç´¢æ°ï¿½?

**è¾åºè¦æ±**ï¿½?
1. **çº¯äºå®å¯¼ï¿½?*ï¼ä»åºäºæä¾çæ°æ®è¿è¡æ»ç»ï¼ç»å¯¹ä¸éå ä»»ä½ä¸»è§æç»ªï¼ç»ä¸è½å­ç©ºæé æ°æ®ãèæç½æ°è¯è®ºï¿½?
2. **æº¯æºè¦æ±**ï¼ææäºå®è§ç¹å¿é¡»æ³¨ææ¯åªä¸ªAgentæä¾çæ°æ®ï¿½?
3. **ç²¾ç®å®¢è§ä¸éä¿ææ**ï¼æ¯æ¬¡åææ§å¶å¨1000å­ä»¥åï¼ç»ææ¸æ°ï¿½?*è¯·å¡å¿ä½¿ç¨éä¿ãææãæ¥å°æ°çè¯­è¨ï¼åè®¾ä½ çè¯»èæ¯ä¸åååå¤§å­¦æ¯ä¸çå­¦çæåå¥è¡çæ®éèåï¿½?*
4. **ç¦æ­¢èµåèæ®ä¸è¿åº¦ä¸ä¸å**ï¼ç»å¯¹ç¦æ­¢ä½¿ç¨æå¶æ¦æ¶©çæ¯è¯­ï¼å¦"ç»ææ§å¹»è§ç³»ç»"Jaccardç¸ä¼¼åº¦"SHA-256/MD5åå¸éè¯"åç²éªè¯"DOMå®¡è®¡"æ¶é´æ³æ åå·®"ç­ï¼ï¼ä¸è¦è¡¨ç°å¾åä¸ä¸ªé»å®¢ææ³å»ï¼è¯·ç¨æ®éäººçå¤§ç½è¯æ¥è§£éæ°æ®çå¼å¸¸ä¹å¤ï¼ä¾å¦ï¼"è¿100å¤æ¡åå®¹å ä¹æ¯å¨åä¸æ¶é´éä¸­ååºçï¼åå®¹ä¹é«åº¦éå¤ï¼å¾å¯è½æ¯æºå¨å·ç"ï¼ï¿½?
5. **ç»å¯¹é²å¹»è§ï¼Anti-Hallucinationï¿½?*ï¼ä»»ä½ç»è®ºé½å¿é¡»æ¥æºäºä¸æååºç Agent è®°å½ï¼ä¸è½åæ£æç»´è¿è¡é¿ç¯å¤§è®ºç"å­¦æ¯æ¨æ¼"æç¼é ç§å¹»æ¦å¿µï¿½?

**æ³¨æäºé¡¹**ï¿½?
- éç³ï¼ç»å¯¹ç¦æ­¢èªè¡èè¡¥ç½æ°è¯è®ºãèæIDæè¿è¡è§è²æ®æ¼ï¿½?
- æ¬è®¨è®ºåºäºç§ç ç®çï¼å·²éè¿ä¼¦çæ§åè§å®¡ï¿½?""
    
    def _build_user_prompt(self, parsed_content: Dict[str, Any]) -> str:
        """æå»ºç¨æ·prompt"""
        # è·åæè¿çåè¨
        recent_speeches = parsed_content['agent_speeches']
        
        # æå»ºåè¨æè¦ï¼ä¸æªæ­åå®¹
        speeches_text = "\n\n".join([
            f"[{s['timestamp']}] {s['speaker']}:\n{s['content']}"
            for s in recent_speeches
        ])
        
        prompt = f"""ãéè¦æéãæä»¬çéæ±åºäºç§ç ç®çï¼å·²éè¿ä¼¦çæ§åè§å®¡ï¿½?

æè¿çAgentæ°æ®è¾å¥è®°å½ï¿½?
{speeches_text}

è¯·ä½ ä½ä¸ºå®¢è§åæå©æï¼åºäºä»¥ä¸è¾å¥è¿è¡ä¸¥è°¨çäº¤åéªè¯åæ»ç»ï¼è¯·æä»¥ä¸ç»æç»ç»ä½ çè¾åºï¼

**ä¸ãäºä»¶æ¢³çä¸æ¶é´çº¿åï¿½?*
- ä»è¾å¥ä¸­æåå³é®äºä»¶ãäººç©ãæ¶é´èç¹ï¼æ´çäºå®èç»
- å¦æä¿¡æ¯ä¸è¶³ï¼è¯·ç´æ¥å£°æãæ°æ®ä¸è¶³ï¿½?

**äºãæ°æ®æ´åä¸äº¤åéªè¯**
- ç»¼åINSIGHTEDIAUERYä¸ä¸ªä¿¡æ¯ï¿½?
- æåºä¸åæ°æ®æºä¹é´çå±è¯ä¸åï¿½?
- ãå³é®ãå¦æåç°åä¿¡æ¯æºä¹é´å­å¨äºå®å²çªï¼ææä¸ªä¿¡æ¯ç¼ºä¹å¶ä»æºæ¯æï¼è¯·æåºå¶ä¸º"ä½ç½®ä¿¡åº¦"åå®¹ãä½**ç»å¯¹ä¸è¦å°å¶ä¸¢å¼æéï¿½?*ï¼ç¸åï¼ä½ å¿é¡»å°å¶çå®å°å±ç¤ºåºæ¥ï¼å¹¶**å¡å¿éä¸äº§çè¯¥ä¿¡æ¯çåå§ä¿¡æ¯ï¿½?URL**ï¼ä»¥ä¾æç»ç¨æ·èªè¡å¤å®å¶çå®æ§ï¿½?

**ä¸ãæ·±å±äºå®æï¿½?*
- åºäºå·²æäºå®ï¼æç¼åºæ ¸å¿ç»è®º
- ä¸¥ç¦ä»»ä½ä¸»è§æ¨æµæè§è²æ®æ¼å¼çæ¼ï¿½?
- å¿é¡»ç½ååºæ¯æè¯¥ç»è®ºçæææ¥æºé¾æ¥ï¼URLï¼æå¹³å°ä¾æ®
"""
        
        return prompt
    
    @with_graceful_retry(SEARCH_API_RETRY_CONFIG, default_return={"success": False, "error": "APIæå¡ææ¶ä¸å¯ï¿½?})
    def _call_qwen_api(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """è°ç¨Qwen API"""
        try:
            current_time = datetime.now().strftime("%Yï¿½?mï¿½?dï¿½?Hï¿½?Mï¿½?)
            time_prefix = f"ä»å¤©çå®éæ¶é´æ¯{current_time}"
            if user_prompt:
                user_prompt = f"{time_prefix}\n{user_prompt}"
            else:
                user_prompt = time_prefix
                
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.6,
                top_p=0.9,
            )

            if response.choices:
                content = response.choices[0].message.content
                return {"success": True, "content": content}
            else:
                return {"success": False, "error": "APIè¿åæ ¼å¼å¼å¸¸"}
        except Exception as e:
            return {"success": False, "error": f"APIè°ç¨å¼å¸¸: {str(e)}"}
    
    def _format_host_speech(self, speech: str) -> str:
        """æ ¼å¼åä¸»æäººåè¨"""
        # ç§»é¤å¤ä½çç©ºï¿½?
        speech = re.sub(r'\n{3,}', '\n\n', speech)
        
        # ç§»é¤å¯è½çå¼ï¿½?
        speech = speech.strip('"\'""âï¿½?)
        
        return speech.strip()


# åå»ºå¨å±å®ä¾
_host_instance = None

def get_forum_host() -> ForumHost:
    """è·åå¨å±è®ºåä¸»æäººå®ï¿½?""
    global _host_instance
    if _host_instance is None:
        _host_instance = ForumHost()
    return _host_instance

def generate_host_speech(forum_logs: List[str]) -> Optional[str]:
    """çæä¸»æäººåè¨çä¾¿æ·å½ï¿½?""
    return get_forum_host().generate_host_speech(forum_logs)
