"""
Report Engine é»è®¤çOpenAIå¼å®¹LLMå®¢æ·ç«¯å°è£

æä¾ç»ä¸çéæµå¼/æµå¼è°ç¨ãå¯ééè¯ãå­èå®å¨æ¼æ¥ä¸æ¨¡ååä¿¡æ¯æ¥è¯¢
"""

import os
import sys
from typing import Any, Dict, Optional, Generator
from loguru import logger

from openai import OpenAI

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
utils_dir = os.path.join(project_root, "utils")
if utils_dir not in sys.path:
    sys.path.append(utils_dir)

try:
    from retry_helper import with_retry, LLM_RETRY_CONFIG
except ImportError:
    def with_retry(config=None):
        """ç®åçwith_retryå ä½ï¼å®ç°ä¸çå®è£é¥°å¨ä¸è´çè°ç¨ç­¾å"""
        def decorator(func):
            """ç´æ¥è¿ååå½æ°ï¼ç¡®ä¿æ retryä¾èµæ¶ä»£ç ä»å¯è¿è¡?""
            return func
        return decorator

    LLM_RETRY_CONFIG = None


class LLMClient:
    """éå¯¹OpenAI Chat Completion APIçè½»éå°è£ï¼ç»ä¸Report Engineè°ç¨å¥å£""

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        """
        åå§åLLMå®¢æ·ç«¯å¹¶ä¿å­åºç¡è¿æ¥ä¿¡æ¯

        Args:
            api_key: ç¨äºé´æçAPI Token
            model_name: å·ä½æ¨¡åIDï¼ç¨äºå®ä½ä¾åºåè½å
            base_url: èªå®ä¹å¼å®¹æ¥å£å°åï¼é»è®¤ä¸ºOpenAIå®æ¹
        """
        if not api_key:
            raise ValueError("Report Engine LLM API key is required.")
        if not model_name:
            raise ValueError("Report Engine model name is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("REPORT_ENGINE_REQUEST_TIMEOUT") or "3000"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 3000.0

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "max_retries": 0,
        }
        
        if base_url:
            client_kwargs["base_url"] = base_url
            
        import httpx
        # åå»ºèªå®ä¹ç httpx Client ä»¥ç»è¿åºå±ç Header è§èåæºå?
        # HTTP/1.1 åè®¸ä¿ç Header çåå§å¤§å°å
        headers = {}
        if base_url and "omnisaas.cn" in base_url:
            headers["apikey"] = api_key
            
        custom_http_client = httpx.Client(
            headers=headers,
            timeout=self.timeout
        )
        client_kwargs["http_client"] = custom_http_client

        self.client = OpenAI(**client_kwargs)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        ä»¥éæµå¼æ¹å¼è°ç¨LLMï¼å¹¶è¿åä¸æ¬¡æ§å®æçå®æ´ååº

        Args:
            system_prompt: ç³»ç»è§è²æç¤º
            user_prompt: ç¨æ·é«ä¼åçº§æä»¤
            **kwargs: åè®¸éä¼ temperature/top_pç­éæ ·åæ?

        Returns:
            å»é¤é¦å°¾ç©ºç½åçLLMååºææ¬
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "stream"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}

        timeout = kwargs.pop("timeout", self.timeout)

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            timeout=timeout,
            **extra_params,
        )

        if response.choices and response.choices[0].message:
            return self.validate_response(response.choices[0].message.content)
        return ""

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        æµå¼è°ç¨LLMï¼éæ­¥è¿åååºåå®¹
        å¸¦æé²å¾¡æ§çèªå¨æªæ­é»è¾ï¼ä»¥é²å¤§æ¨¡åæåº "request was too large" ä¸å¯¼è´æ ééè¯
        
        åæ°:
            system_prompt: ç³»ç»æç¤ºè¯
            user_prompt: ç¨æ·æç¤ºè¯
            **kwargs: éæ ·åæ°ï¼temperatureop_pç­ï¼
            
        äº§åº:
            str: æ¯æ¬¡yieldä¸æ®µdeltaææ¬ï¼æ¹ä¾¿ä¸å±å®æ¶æ¸²æ
        """
        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "max_tokens"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}
        if "max_tokens" not in extra_params:
            extra_params["max_tokens"] = 8192
        # å¼ºå¶ä½¿ç¨æµå¼
        extra_params["stream"] = True

        # =======================
        # æ°å¢é²å¾¡æºå¶ï¼å¨ææªæ­ä»¥é²å¾¡ "request was too large"
        # =======================
        MAX_CHARS = 100000  # åå§è¾¹çï¼çº¦3ä¸Token
        if len(user_prompt) > MAX_CHARS:
            logger.warning(f"ç¨æ·æç¤ºè¯è¿é?({len(user_prompt)} å­ç¬¦)ï¼è§¦ååå§æªæ­ä»¥é²æ­¢ 'request was too large')
            half = MAX_CHARS // 2
            user_prompt = user_prompt[:half] + "\n\n...[ç±äºé¿åº¦éå¶ï¼ä¸­é´é¨åå·²è¢«ç³»ç»èªå¨æªæ­]...\n\n" + user_prompt[-half:]

        while True:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            timeout = kwargs.get("timeout", self.timeout)

            try:
                stream = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    timeout=timeout,
                    **extra_params,
                )
                
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content
                break  # æååéåºå¾ªç?
                
            except Exception as e:
                error_msg = str(e)
                
                # å¤çè¶å¤§è¯·æ±æ¥éï¼å¨æéåæªæ­ï¼?
                if "request was too large" in error_msg.lower() or "context length exceeded" in error_msg.lower():
                    # è®¡ç®æ°çæ´å°çé¿åº¦éå?
                    current_len = len(user_prompt)
                    new_len = int(current_len * 0.7)  # æ¯æ¬¡ç¼©å 30%
                    
                    if new_len < 1000:
                        # ç¼©åå°æéä»å¤±è´¥ï¼è¯´ææ¯å¶ä»é®é¢ï¼æåºå¼å¸?
                        logger.error(f"ç¨æ·æç¤ºè¯å·²ç¼©åè³æé?({current_len} å­ç¬¦)ï¼ä»ç¶æç¤ºè¯·æ±è¿å¤§ãåæ­¢éè¯)
                        raise e
                        
                    logger.warning(f"å¤§æ¨¡åè¿å?'request was too large'ãå½åå­ç¬¦æ°: {current_len}ãç³»ç»æ­£å¨èªå¨ç¼©å?30% è?{new_len} å­ç¬¦å¹¶ç«å³éè¯?..")
                    half = new_len // 2
                    user_prompt = user_prompt[:half] + "\n\n...[å æ¨¡åä¸ä¸ææº¢åºï¼ä¸­é´é¨åè¢«ç³»ç»èªå¨æªæ­]...\n\n" + user_prompt[-half:]
                    continue  # ç»§ç»­å¾ªç¯è¿è¡ä¸ä¸æ¬¡å°è¯?

                logger.error(f"æµå¼è¯·æ±å¤±è´¥: {error_msg}")
                # å¦ææ?502/504 ç­ç½å³éè¯¯å¯¼è´ç HTML ååºï¼åè£ææ´æç¡®çå¼å¸¸ï¼ä»¥ä¾¿ä¸å±éè¯æºå¶è½å¤æè?
                if "<html>" in error_msg.lower() or "502 bad gateway" in error_msg.lower() or "504 gateway time-out" in error_msg.lower():
                    raise Exception(f"API ç½å³è¶æ¶æè¿åäºæ æç?HTML ååº: {error_msg[:200]}...") from e
                raise e
    
    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        æµå¼è°ç¨LLMå¹¶å®å¨å°æ¼æ¥ä¸ºå®æ´å­ç¬¦ä¸²ï¼é¿åUTF-8å¤å­èå­ç¬¦æªæ­ï¼
        
        åæ°:
            system_prompt: ç³»ç»æç¤ºè¯
            user_prompt: ç¨æ·æç¤ºè¯
            **kwargs: éæ ·æè¶æ¶éç½®
            
        è¿å:
            str: å°æædeltaæ¼æ¥åçå®æ´ååº
        """
        # ä»¥å­èå½¢å¼æ¶éææå
        byte_chunks = []
        for chunk in self.stream_invoke(system_prompt, user_prompt, **kwargs):
            byte_chunks.append(chunk.encode('utf-8'))
        
        # æ¼æ¥ææå­èï¼ç¶åä¸æ¬¡æ§è§£ç ?
        if byte_chunks:
            return b''.join(byte_chunks).decode('utf-8', errors='replace')
        return ""

    @staticmethod
    def validate_response(response: Optional[str]) -> str:
        """ååºå¤çNone/ç©ºç½å­ç¬¦ä¸²ï¼é²æ­¢ä¸å±é»è¾å´©æº"""
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        """ä»¥å­å¸å½¢å¼è¿åå½åå®¢æ·ç«¯çæ¨¡å?æä¾æ?åºç¡URLä¿¡æ¯"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
        }
