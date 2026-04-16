# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/store/zhihu/_store_impl.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。


# -*- coding: utf-8 -*-
# @Author  : persist1@126.com
# @Time    : 2025/9/5 19:34
# @Desc    : Zhihu storage implementation class
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.db_session import get_session
from database.models import ZhihuContent, ZhihuComment, ZhihuCreator
from tools import utils


class ZhihuDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            content_item: content item dict
        """
        content_id = content_item.get("content_id")
        async with get_session() as session:
            stmt = select(ZhihuContent).where(ZhihuContent.content_id == content_id)
            result = await session.execute(stmt)
            existing_content = result.scalars().first()
            if existing_content:
                for key, value in content_item.items():
                    if hasattr(existing_content, key):
                        setattr(existing_content, key, value)
            else:
                new_content = ZhihuContent(**content_item)
                session.add(new_content)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            comment_item: comment item dict
        """
        comment_id = comment_item.get("comment_id")
        async with get_session() as session:
            stmt = select(ZhihuComment).where(ZhihuComment.comment_id == comment_id)
            result = await session.execute(stmt)
            existing_comment = result.scalars().first()
            if existing_comment:
                for key, value in comment_item.items():
                    if hasattr(existing_comment, key):
                        setattr(existing_comment, key, value)
            else:
                new_comment = ZhihuComment(**comment_item)
                session.add(new_comment)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        Zhihu content DB storage implementation
        Args:
            creator: creator dict
        """
        user_id = creator.get("user_id")
        async with get_session() as session:
            stmt = select(ZhihuCreator).where(ZhihuCreator.user_id == user_id)
            result = await session.execute(stmt)
            existing_creator = result.scalars().first()
            if existing_creator:
                for key, value in creator.items():
                    if hasattr(existing_creator, key):
                        setattr(existing_creator, key, value)
            else:
                new_creator = ZhihuCreator(**creator)
                session.add(new_creator)
            await session.commit()

