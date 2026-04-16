# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/store/tieba/_store_impl.py
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
# @Desc    : Tieba storage implementation class
from typing import Dict

from sqlalchemy import select

from base.base_crawler import AbstractStore
from database.models import TiebaNote, TiebaComment, TiebaCreator
from tools import utils
from database.db_session import get_session


class TieBaDbStoreImplement(AbstractStore):
    async def store_content(self, content_item: Dict):
        """
        tieba content DB storage implementation
        Args:
            content_item: content item dict
        """
        note_id = content_item.get("note_id")
        async with get_session() as session:
            stmt = select(TiebaNote).where(TiebaNote.note_id == note_id)
            res = await session.execute(stmt)
            db_note = res.scalar_one_or_none()
            if db_note:
                for key, value in content_item.items():
                    setattr(db_note, key, value)
            else:
                db_note = TiebaNote(**content_item)
                session.add(db_note)
            await session.commit()

    async def store_comment(self, comment_item: Dict):
        """
        tieba content DB storage implementation
        Args:
            comment_item: comment item dict
        """
        comment_id = comment_item.get("comment_id")
        async with get_session() as session:
            stmt = select(TiebaComment).where(TiebaComment.comment_id == comment_id)
            res = await session.execute(stmt)
            db_comment = res.scalar_one_or_none()
            if db_comment:
                for key, value in comment_item.items():
                    setattr(db_comment, key, value)
            else:
                db_comment = TiebaComment(**comment_item)
                session.add(db_comment)
            await session.commit()

    async def store_creator(self, creator: Dict):
        """
        tieba content DB storage implementation
        Args:
            creator: creator dict
        """
        user_id = creator.get("user_id")
        async with get_session() as session:
            stmt = select(TiebaCreator).where(TiebaCreator.user_id == user_id)
            res = await session.execute(stmt)
            db_creator = res.scalar_one_or_none()
            if db_creator:
                for key, value in creator.items():
                    setattr(db_creator, key, value)
            else:
                db_creator = TiebaCreator(**creator)
                session.add(db_creator)
            await session.commit()

