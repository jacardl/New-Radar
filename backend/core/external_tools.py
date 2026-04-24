import os
import json
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ExternalSearchTools:
    """
    å°è£åå¤§å¤é¨æç´¢ API ä¸ºä¾ Hermes Agent è°ç¨çå½æ°    åå«ï¼Anspire, Bocha, Tavily, Firecrawl
    """
    
    @staticmethod
    def anspire_search(query: str, limit: int = 5) -> str:
        """
        ä½¿ç¨ Anspire API è¿è¡æ·±åº¦ç½ç»æç´¢        éå Insight Engine è¿è¡ç§åç¥è¯æ©å±        """
        api_key = os.getenv("ANSPIRE_API_KEY")
        base_url = os.getenv("ANSPIRE_PRO_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/prosearch")
        if not api_key:
            return "Anspire API å¯é¥æªéç½®

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"query": query, "limit": limit}
                response = client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                # åè®¾è¿åç»æä¸­æ data å­æ®µ
                return json.dumps(data.get("data", []), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Anspire Search Failed: {e}")
            return f"Anspire æç´¢å¤±è´¥: {str(e)}"

    @staticmethod
    def bocha_search(query: str, limit: int = 5) -> str:
        """
        ä½¿ç¨ Bocha API è¿è¡ç½ç»æç´¢        éå Media Engine å¤çå¤æ¨¡ææç»æåæ°æ®çæ£ç´¢        """
        api_key = os.getenv("BOCHA_WEB_API_KEY")
        base_url = os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn/v1/web-search")
        if not api_key:
            return "Bocha API å¯é¥æªéç½®

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"query": query, "count": limit}
                response = client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return json.dumps(data.get("data", {}).get("webPages", {}).get("value", []), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Bocha Search Failed: {e}")
            return f"Bocha æç´¢å¤±è´¥: {str(e)}"

    @staticmethod
    def tavily_search(query: str, search_depth: str = "basic") -> str:
        """
        ä½¿ç¨ Tavily API è¿è¡å®æ¶ä¿¡æ¯åæ°é»æç´¢        éå Query Engine äºè§£ææ°å¬ä¼è¶å¿        """
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Tavily API å¯é¥æªéç½®

        try:
            # è¿éå¯ä»¥ç´æ¥è°ç¨ tavily-python åºï¼æèä½¿ç?httpx åé?POST è¯·æ±
            with httpx.Client(timeout=30.0) as client:
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": search_depth,
                    "include_answer": True
                }
                response = client.post("https://api.tavily.com/search", json=payload)
                response.raise_for_status()
                return json.dumps(response.json(), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Tavily Search Failed: {e}")
            return f"Tavily æç´¢å¤±è´¥: {str(e)}"

    @staticmethod
    def firecrawl_scrape(url: str) -> str:
        """
        ä½¿ç¨ Firecrawl API å¯¹ç¹å®?URL è¿è¡æ·±åº¦é¡µé¢æåå¹¶è½¬æ¢ä¸º Markdown        """
        api_key = os.getenv("FIRECRAWL_API_KEY")
        base_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1")
        if not api_key:
            return "Firecrawl API å¯é¥æªéç½®

        try:
            with httpx.Client(timeout=60.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"url": url, "formats": ["markdown"]}
                response = client.post(f"{base_url}/scrape", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("markdown", "æååå®¹ä¸ºç©º)
        except Exception as e:
            logger.error(f"Firecrawl Scrape Failed: {e}")
            return f"Firecrawl æåå¤±è´¥: {str(e)}"
