# -*- coding: utf-8 -*-
"""
web-access 兜底爬虫桥接模块
当 MediaCrawler 遇到反爬/登录态限制时，通过 CDP Proxy 兜底抓取
"""

import asyncio
import httpx
import json
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# CDP Proxy 默认地址
CDP_PROXY_BASE = "http://localhost:3456"


class WebAccessBridge:
    """
    web-access CDP Proxy 桥接器
    用于处理 MediaCrawler 无法直接爬取的页面（需要登录态/反爬绕过）
    """

    def __init__(self, base_url: str = CDP_PROXY_BASE):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def is_available(self) -> bool:
        """检查 CDP Proxy 是否可用"""
        if self._available is not None:
            return self._available

        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/health")
            data = resp.json()
            self._available = data.get("connected", False)
            logger.info(f"CDP Proxy 状态: {'已连接' if self._available else '未连接 Chrome'}")
            return self._available
        except Exception as e:
            logger.warning(f"CDP Proxy 不可用: {e}")
            self._available = False
            return False

    async def new_tab(self, url: str) -> Optional[str]:
        """
        创建新标签页并打开 URL

        Args:
            url: 目标页面 URL

        Returns:
            targetId，失败返回 None
        """
        if not await self.is_available():
            return None

        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/new", params={"url": url})
            data = resp.json()
            target_id = data.get("targetId")
            logger.info(f"CDP 打开页面: {url} -> targetId={target_id}")
            return target_id
        except Exception as e:
            logger.error(f"CDP new_tab 失败: {e}")
            return None

    async def navigate(self, target_id: str, url: str) -> bool:
        """导航到指定 URL"""
        if not await self.is_available():
            return False

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/navigate",
                params={"target": target_id, "url": url}
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"CDP navigate 失败: {e}")
            return False

    async def eval_js(self, target_id: str, expr: str) -> Optional[Any]:
        """
        执行 JavaScript 并返回结果

        Args:
            target_id: 标签页 ID
            expr: JavaScript 表达式

        Returns:
            执行结果，失败返回 None
        """
        if not await self.is_available():
            return None

        try:
            client = await self._get_client()
            resp = await client.post(
                f"{self.base_url}/eval",
                params={"target": target_id},
                content=expr
            )
            data = resp.json()
            return data.get("value")
        except Exception as e:
            logger.error(f"CDP eval_js 失败: {e}")
            return None

    async def get_page_content(self, target_id: str) -> Optional[str]:
        """获取页面 HTML 内容"""
        return await self.eval_js(target_id, "document.body.innerHTML")

    async def get_page_text(self, target_id: str) -> Optional[str]:
        """获取页面纯文本"""
        return await self.eval_js(
            target_id,
            "document.body.innerText || document.body.textContent"
        )

    async def get_title(self, target_id: str) -> Optional[str]:
        """获取页面标题"""
        return await self.eval_js(target_id, "document.title")

    async def screenshot(self, target_id: str, filepath: str) -> bool:
        """
        页面截图

        Args:
            target_id: 标签页 ID
            filepath: 保存路径

        Returns:
            是否成功
        """
        if not await self.is_available():
            return False

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/screenshot",
                params={"target": target_id, "file": filepath}
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"CDP screenshot 失败: {e}")
            return False

    async def scroll(self, target_id: str, direction: str = "down", y: int = 3000) -> bool:
        """
        滚动页面

        Args:
            target_id: 标签页 ID
            direction: 'up', 'down', 'top', 'bottom'
            y: 滚动像素（direction 为 up/down 时）

        Returns:
            是否成功
        """
        if not await self.is_available():
            return False

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/scroll",
                params={"target": target_id, "direction": direction, "y": str(y)}
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"CDP scroll 失败: {e}")
            return False

    async def close_tab(self, target_id: str) -> bool:
        """关闭标签页"""
        if not await self.is_available():
            return False

        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.base_url}/close",
                params={"target": target_id}
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"CDP close_tab 失败: {e}")
            return False

    async def scrape_xhs_note(self, url: str) -> Optional[Dict]:
        """
        通过 CDP 抓取小红书笔记
        适用于需要登录态的小红书页面

        Args:
            url: 小红书笔记 URL

        Returns:
            笔记数据字典，失败返回 None
        """
        target_id = await self.new_tab(url)
        if not target_id:
            return None

        try:
            # 等待页面加载
            await asyncio.sleep(3)

            # 获取标题和正文
            title = await self.get_title(target_id)
            content = await self.eval_js(
                target_id,
                """
                (() => {
                    const noteContent = document.querySelector('#detail-desc') ||
                                        document.querySelector('.note-content') ||
                                        document.querySelector('meta[name="description"]');
                    return noteContent ? noteContent.innerText || noteContent.content : '';
                })()
                """
            )

            # 获取作者
            author = await self.eval_js(
                target_id,
                """
                (() => {
                    const author = document.querySelector('.author-wrapper') ||
                                   document.querySelector('.user-nickname') ||
                                   document.querySelector('meta[property="og:author"]');
                    return author ? author.innerText || author.content : '';
                })()
                """
            )

            # 获取互动数据
            liked_count = await self.eval_js(
                target_id,
                """
                (() => {
                    const like = document.querySelector('.like-wrapper .count') ||
                                 document.querySelector('[class*="like"] .count');
                    return like ? like.innerText : '0';
                })()
                """
            )

            result = {
                "note_url": url,
                "title": title or "",
                "content": content or "",
                "nickname": author or "",
                "liked_count": liked_count or "0",
                "ip_location": await self.eval_js(target_id, """
                    (() => {
                        const ip = document.querySelector('.ip-location') ||
                                   document.querySelector('[class*="ip"]');
                        return ip ? ip.innerText : '';
                    })()
                """) or "",
            }

            return result

        finally:
            await self.close_tab(target_id)

    async def scrape_wechat_article(self, url: str) -> Optional[Dict]:
        """
        通过 CDP 抓取微信公众号文章

        Args:
            url: 文章 URL

        Returns:
            文章数据字典，失败返回 None
        """
        target_id = await self.new_tab(url)
        if not target_id:
            return None

        try:
            await asyncio.sleep(3)

            title = await self.get_title(target_id)
            content = await self.eval_js(
                target_id,
                """
                (() => {
                    const article = document.getElementById('js_content') ||
                                    document.querySelector('.article-content') ||
                                    document.querySelector('#js_content');
                    return article ? article.innerText : '';
                })()
                """
            )
            author = await self.eval_js(
                target_id,
                """
                (() => {
                    const author = document.getElementById('js_name') ||
                                   document.querySelector('.account_name') ||
                                   document.querySelector('meta[property="og:author"]');
                    return author ? author.innerText || author.content : '';
                })()
                """
            )

            result = {
                "content_url": url,
                "title": title or "",
                "content": content or "",
                "author": author or "",
            }

            return result

        finally:
            await self.close_tab(target_id)


# 全局实例
_bridge: Optional[WebAccessBridge] = None


def get_web_access_bridge() -> WebAccessBridge:
    """获取 WebAccessBridge 单例"""
    global _bridge
    if _bridge is None:
        _bridge = WebAccessBridge()
    return _bridge


async def close_web_access_bridge():
    """关闭桥接器"""
    global _bridge
    if _bridge:
        await _bridge.close()
        _bridge = None
