"""
Unified OpenAI-compatible LLM client for the Insight Engine, with retry support.
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Iterator, Generator, List
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
        def decorator(func):
            return func
        return decorator

    LLM_RETRY_CONFIG = None


class LLMClient:
    """Minimal wrapper around the OpenAI-compatible chat completion API."""

    def __init__(self, api_key: str, model_name: str, base_url: Optional[str] = None):
        if not api_key:
            raise ValueError("Insight Engine INSIGHT_ENGINE_API_KEY is required.")
        if not model_name:
            raise ValueError("Insight Engine INSIGHT_ENGINE_MODEL_NAME is required.")

        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.provider = model_name
        timeout_fallback = os.getenv("LLM_REQUEST_TIMEOUT") or os.getenv("INSIGHT_ENGINE_REQUEST_TIMEOUT") or "1800"
        try:
            self.timeout = float(timeout_fallback)
        except ValueError:
            self.timeout = 1800.0

        candidates_env = os.getenv("INSIGHT_ENGINE_MODEL_CANDIDATES", "")
        candidates: List[str] = []
        if candidates_env:
            candidates = [m.strip() for m in candidates_env.split(",") if m.strip()]
        self.model_candidates: List[str] = []
        seen = set()
        for m in [self.model_name] + candidates:
            if m and m not in seen:
                self.model_candidates.append(m)
                seen.add(m)

        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "max_retries": 0,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
            if "omnisaas.cn" in base_url:
                client_kwargs["default_headers"] = {"apikey": api_key}
        self.client = OpenAI(**client_kwargs)

    def _should_fallback(self, e: Exception) -> bool:
        s = str(e).lower()
        keys = ["rate limit", "429", "quota", "insufficient", "model_not_found", "model not found", "unsupported", "402", "payment"]
        return any(k in s for k in keys)

    @with_retry(LLM_RETRY_CONFIG)
    def invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        current_time = datetime.now().strftime("%Yå¹?mæ?dæ?Hæ?Må?)
        time_prefix = f"ä»å¤©çå®éæ¶é´æ¯{current_time}"
        if user_prompt:
            user_prompt = f"{time_prefix}\n{user_prompt}"
        else:
            user_prompt = time_prefix
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "stream"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}

        timeout = kwargs.pop("timeout", self.timeout)

        last_error = None
        for m in self.model_candidates:
            try:
                response = self.client.chat.completions.create(
                    model=m,
                    messages=messages,
                    timeout=timeout,
                    **extra_params,
                )
                self.model_name = m
                self.provider = m
                if response.choices and response.choices[0].message:
                    return self.validate_response(response.choices[0].message.content)
                return ""
            except Exception as e:
                last_error = e
                if not self._should_fallback(e):
                    raise
                continue
        if last_error:
            raise last_error
        return ""

    def stream_invoke(self, system_prompt: str, user_prompt: str, **kwargs) -> Generator[str, None, None]:
        """
        æµå¼è°ç¨LLMï¼éæ­¥è¿åååºåå®¹
        
        Args:
            system_prompt: ç³»ç»æç¤ºè¯?
            user_prompt: ç¨æ·æç¤ºè¯?
            **kwargs: é¢å¤åæ°ï¼temperature, top_pç­ï¼
            
        Yields:
            ååºææ¬åï¼strï¼?
        """
        current_time = datetime.now().strftime("%Yå¹?mæ?dæ?Hæ?Må?)
        time_prefix = f"ä»å¤©çå®éæ¶é´æ¯{current_time}"
        if user_prompt:
            user_prompt = f"{time_prefix}\n{user_prompt}"
        else:
            user_prompt = time_prefix
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        allowed_keys = {"temperature", "top_p", "presence_penalty", "frequency_penalty", "max_tokens"}
        extra_params = {key: value for key, value in kwargs.items() if key in allowed_keys and value is not None}
        if "max_tokens" not in extra_params:
            extra_params["max_tokens"] = 4096
        # å¼ºå¶ä½¿ç¨æµå¼
        extra_params["stream"] = True

        timeout = kwargs.pop("timeout", self.timeout)

        last_error = None
        for m in self.model_candidates:
            try:
                stream = self.client.chat.completions.create(
                    model=m,
                    messages=messages,
                    timeout=timeout,
                    **extra_params,
                )
                self.model_name = m
                self.provider = m
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and delta.content:
                            yield delta.content
                return
            except Exception as e:
                last_error = e
                if not self._should_fallback(e):
                    logger.error(f"æµå¼è¯·æ±å¤±è´¥: {str(e)}")
                    raise
                continue
        if last_error:
            logger.error(f"æµå¼è¯·æ±å¤±è´¥: {str(last_error)}")
            raise last_error
    
    @with_retry(LLM_RETRY_CONFIG)
    def stream_invoke_to_string(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """
        æµå¼è°ç¨LLMå¹¶å®å¨å°æ¼æ¥ä¸ºå®æ´å­ç¬¦ä¸²ï¼é¿åUTF-8å¤å­èå­ç¬¦æªæ­ï¼
        
        Args:
            system_prompt: ç³»ç»æç¤ºè¯?
            user_prompt: ç¨æ·æç¤ºè¯?
            **kwargs: é¢å¤åæ°ï¼temperature, top_pç­ï¼
            
        Returns:
            å®æ´çååºå­ç¬¦ä¸²
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
        if response is None:
            return ""
        return response.strip()

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "api_base": self.base_url or "default",
        }
