import os
import json
import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ExternalSearchTools:
    """
    封装各大外部搜索 API 为供 Hermes Agent 调用的函数�?    包含：Anspire, Bocha, Tavily, Firecrawl
    """
    
    @staticmethod
    def anspire_search(query: str, limit: int = 5) -> str:
        """
        使用 Anspire API 进行深度网络搜索�?        适合 Insight Engine 进行私域知识扩展�?        """
        api_key = os.getenv("ANSPIRE_API_KEY")
        base_url = os.getenv("ANSPIRE_PRO_BASE_URL", "https://plugin.anspire.cn/api/ntsearch/prosearch")
        if not api_key:
            return "Anspire API 密钥未配置�?

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"query": query, "limit": limit}
                response = client.post(base_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                # 假设返回结果中有 data 字段
                return json.dumps(data.get("data", []), ensure_ascii=False)
        except Exception as e:
            logger.error(f"Anspire Search Failed: {e}")
            return f"Anspire 搜索失败: {str(e)}"

    @staticmethod
    def bocha_search(query: str, limit: int = 5) -> str:
        """
        使用 Bocha API 进行网络搜索�?        适合 Media Engine 处理多模态或结构化数据的检索�?        """
        api_key = os.getenv("BOCHA_WEB_API_KEY")
        base_url = os.getenv("BOCHA_BASE_URL", "https://api.bocha.cn/v1/web-search")
        if not api_key:
            return "Bocha API 密钥未配置�?

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
            return f"Bocha 搜索失败: {str(e)}"

    @staticmethod
    def tavily_search(query: str, search_depth: str = "basic") -> str:
        """
        使用 Tavily API 进行实时信息和新闻搜索�?        适合 Query Engine 了解最新公众趋势�?        """
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return "Tavily API 密钥未配置�?

        try:
            # 这里可以直接调用 tavily-python 库，或者使�?httpx 发�?POST 请求
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
            return f"Tavily 搜索失败: {str(e)}"

    @staticmethod
    def firecrawl_scrape(url: str) -> str:
        """
        使用 Firecrawl API 对特�?URL 进行深度页面抓取并转换为 Markdown�?        """
        api_key = os.getenv("FIRECRAWL_API_KEY")
        base_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v1")
        if not api_key:
            return "Firecrawl API 密钥未配置�?

        try:
            with httpx.Client(timeout=60.0) as client:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"url": url, "formats": ["markdown"]}
                response = client.post(f"{base_url}/scrape", headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("data", {}).get("markdown", "抓取内容为空�?)
        except Exception as e:
            logger.error(f"Firecrawl Scrape Failed: {e}")
            return f"Firecrawl 抓取失败: {str(e)}"
