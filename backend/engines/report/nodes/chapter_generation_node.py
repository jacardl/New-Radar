"""
ç« èçº§JSONçæèç¹

æ¯ä¸ªç« èä¾æ®Markdownæ¨¡æ¿åçç¬ç«è°ç¨LLMï¼æµå¼åå¥Rawæä»¶ï¼?
å®æåæ ¡éªå¹¶è½çæ ååJSONãè¯¥èç¹åªè´è´£"æ¿å°åè§ç« è"
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple, Callable, Optional, Set

from loguru import logger

from ..core import TemplateSection, ChapterStorage
from ..ir import (
    ALLOWED_BLOCK_TYPES,
    ALLOWED_INLINE_MARKS,
    ENGINE_AGENT_TITLES,
    IRValidator,
)
from ..prompts import (
    SYSTEM_PROMPT_CHAPTER_JSON,
    SYSTEM_PROMPT_CHAPTER_JSON_REPAIR,
    SYSTEM_PROMPT_CHAPTER_JSON_RECOVERY,
    build_chapter_repair_prompt,
    build_chapter_recovery_payload,
    build_chapter_user_prompt,
)
from ..utils.json_parser import RobustJSONParser, JSONParseError
from .base_node import BaseNode

try:
    from json_repair import repair_json as _json_repair_fn
except ImportError:  # pragma: no cover - å¯éä¾èµ?
    _json_repair_fn = None


class ChapterJsonParseError(ValueError):
    """ç« èLLMè¾åºæ æ³è§£æä¸ºåæ³JSONæ¶æåºçå¼å¸¸ï¼éå¸¦åå§ææ¬æ¹ä¾¿ææ¥""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        """
        æé å¼å¸¸å¹¶éå åå§è¾åºï¼ä¾¿äºæ¥å¿ä¸­å®ä½

        Args:
            message: äººç±»å¯è¯»çéè¯¯æè¿°
            raw_text: è§¦åå¼å¸¸çå®æ´LLMè¾åº
        """
        super().__init__(message)
        self.raw_text = raw_text


class ChapterContentError(ValueError):
    """
    ç« èåå®¹ç¨çå¼å¸¸

    å½LLMä»è¾åºæ é¢ææ­£æä¸è¶³ä»¥æ¯æä¸ç« æ¶è§¦åï¼é©±å¨éè¯ä»¥ä¿è¯æ¥åè´¨é
    """

    def __init__(
        self,
        message: str,
        chapter: Optional[Dict[str, Any]] = None,
        body_characters: int = 0,
        narrative_characters: int = 0,
        non_heading_blocks: int = 0,
    ):
        """ä¿å­æ¬æ¬¡å¼å¸¸çæ­£æç¹å¾ï¼ä¾éè¯ä¸ååºç­ç¥åè""
        super().__init__(message)
        self.chapter_payload: Optional[Dict[str, Any]] = chapter
        self.body_characters: int = int(body_characters or 0)
        self.narrative_characters: int = int(narrative_characters or 0)
        self.non_heading_blocks: int = int(non_heading_blocks or 0)


class ChapterValidationError(ValueError):
    """
    ç« èç»æå¨æ¬å°åLLMä¿®å¤åä»æ æ³éè¿æ ¡éªæ¶æåº

    è¯¥å¼å¸¸ç¨äºå¨Agentå±è§¦åéå¯¹åç« çéè¯ï¼èæ ééå¯æ´æ¬æ¥å
    """

    def __init__(self, message: str, errors: Optional[List[str]] | None = None):
        super().__init__(message)
        self.errors: List[str] = list(errors or [])


class ChapterGenerationNode(BaseNode):
    """
    è´è´£æç« èè°ç¨LLMå¹¶æ ¡éªJSONç»æ

    æ ¸å¿è½åï¼?
        - æé ç« èçº§ payload ä¸æç¤ºè¯ï¼?
        - ä»¥æµå¼å½¢å¼åå?raw æä»¶å¹¶éä¼  deltaï¼?
        - å°è¯ä¿®å¤/è§£æLLMè¾åºï¼å¹¶ä½¿ç¨ IRValidator æ ¡éªï¼?
        - å¯¹blockç»æåå®¹éä¿®å¤ï¼ç¡®ä¿æç»JSONå¯æ¸²æ
    """

    _COLON_EQUALS_PATTERN = re.compile(r'(":\s*)=')
    _LINE_BREAK_SENTINEL = "__LINE_BREAK__"
    _INLINE_MARK_ALIASES = {
        "strong": "bold",
        "b": "bold",
        "em": "italic",
        "emphasis": "italic",
        "i": "italic",
        "u": "underline",
        "strike-through": "strike",
        "strikethrough": "strike",
        "s": "strike",
        "codeblock": "code",
        "monospace": "code",
        "hyperlink": "link",
        "url": "link",
        "colour": "color",
        "textcolor": "color",
        "bgcolor": "highlight",
        "background": "highlight",
        "highlightcolor": "highlight",
        "sub": "subscript",
        "sup": "superscript",
    }
    # ç« èè¥ä»åå«æ é¢æå­ç¬¦è¿å°åè§ä¸ºå¤±è´¥ï¼å¼ºå¶LLMéæ°çæ
    _MIN_NON_HEADING_BLOCKS = 2
    _MIN_BODY_CHARACTERS = 600
    _MIN_NARRATIVE_CHARACTERS = 300
    _PARAGRAPH_FRAGMENT_MAX_CHARS = 80
    _PARAGRAPH_FRAGMENT_NO_TERMINATOR_MAX_CHARS = 240
    _TERMINATION_PUNCTUATION = set("ãï¼ï¼??ï¼?...â?)

    def __init__(
        self,
        llm_client,
        validator: IRValidator,
        storage: ChapterStorage,
        fallback_llm_clients: Optional[List[Tuple[str, Any]]] = None,
        error_log_dir: Optional[str | Path] = None,
    ):
        """
        è®°å½LLMå®¢æ·ç«?æ ¡éªå?ç« èå­å¨å¨ï¼ä¾¿äºrunæ¹æ³è°åº¦

        Args:
            llm_client: å®éè°ç¨å¤§æ¨¡åçå®¢æ·ç«?
            validator: IRç»ææ ¡éªå?
            storage: è´è´£ç« èæµå¼è½ççå­å¨å¨
        """
        super().__init__(llm_client, "ChapterGenerationNode")
        self.validator = validator
        self.storage = storage
        self.fallback_llm_clients: List[Tuple[str, Any]] = fallback_llm_clients or [
            ("report_engine", llm_client)
        ]
        error_dir = Path(error_log_dir or "logs/json_repair_failures")
        error_dir.mkdir(parents=True, exist_ok=True)
        self.error_log_dir = error_dir
        self._failed_block_counter = 0
        self._active_run_id: Optional[str] = None
        self._rescue_attempted_labels: Dict[str, Set[str]] = {}
        self._skipped_placeholder_chapters: Set[str] = set()
        self._archived_failed_json: Dict[str, str] = {}
        # ååºä½¿ç¨æ´é²æ£çJSONè§£æå¨ï¼å°½å¯è½æåºåæ³å
        self._robust_parser = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,
        )

    def run(
        self,
        section: TemplateSection,
        context: Dict[str, Any],
        run_dir: Path,
        stream_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        éå¯¹åä¸ªç« èè°ç¨LLMï¼æ ¡éª?è½çç« èJSONå¹¶è¿åç»æåç»æ

        åæ°:
            section: æ¨¡æ¿åççæçç« èå¯¹è±¡ï¼åå«æ é¢/é¡ºåº/slug
            context: Agentæé çå±äº«ä¸ä¸æï¼ä¸»é¢ãç¯å¹ãå¸å±ç­ï¼
            run_dir: ç« èå­çç®å½ï¼ç± `ChapterStorage.start_session` è¿å
            stream_callback: å¯éæµå¼åè°ï¼å°LLM delta æ¨éç»åç«¯
            **kwargs: éä¼ æ¸©åº¦op_pç­éæ ·åæ°

        è¿å:
            dict: éè¿IRæ ¡éªçç« èJSON

        å¼å¸¸:
            ChapterJsonParseError: å¤æ¬¡å°è¯åä»æ æ³è§£æåæ³JSON
            ChapterContentError: æ­£æå¯åº¦ä¸è¶³æåªææ é¢ï¼éè¦è§¦åéè¯
        """
        chapter_meta = {
            "chapterId": section.chapter_id,
            "slug": section.slug,
            "title": section.title,
            "order": section.order,
        }
        chapter_dir = self.storage.begin_chapter(run_dir, chapter_meta)
        run_id = run_dir.name
        self._ensure_run_state(run_id)
        llm_payload = self._build_payload(section, context)
        user_message = build_chapter_user_prompt(llm_payload)

        raw_text = self._stream_llm(
            user_message,
            chapter_dir,
            stream_callback=stream_callback,
            section_meta=chapter_meta,
            **kwargs,
        )
        parse_context: List[str] = []
        placeholder_created = False
        try:
            chapter_json = self._parse_chapter(raw_text)
        except ChapterJsonParseError as parse_error:
            logger.warning(f"{section.title} ç« èJSONè§£æå¤±è´¥ï¼å°è¯è·¨å¼æä¿®å¤: {parse_error}")
            parse_context.append(str(parse_error))
            self._archive_failed_output(section, raw_text)
            recovered = self._attempt_cross_engine_json_rescue(
                section,
                llm_payload,
                raw_text,
                run_id,
            )
            if recovered:
                chapter_json = recovered
                logger.info(f"{section.title} ç« èJSONå·²éè¿è·¨å¼æä¿®å¤?)
            else:
                placeholder = self._build_placeholder_chapter(section, raw_text, parse_error)
                if not placeholder:
                    raise
                chapter_json, placeholder_notes = placeholder
                parse_context.extend(placeholder_notes)
                placeholder_created = True

        # èªå¨è¡¥å¨å³é®å­æ®µååæ ¡éª
        chapter_json.setdefault("chapterId", section.chapter_id)
        chapter_json.setdefault("anchor", section.slug)
        chapter_json.setdefault("title", section.title)
        chapter_json.setdefault("order", section.order)
        self._sanitize_chapter_blocks(chapter_json, section_outline=[{"title": o} if isinstance(o, str) else o for o in section.outline] if hasattr(section, "outline") and section.outline else None)

        valid, errors = self.validator.validate_chapter(chapter_json)
        if not valid and errors:
            repaired = self._attempt_llm_structural_repair(
                chapter_json,
                errors,
                raw_text=raw_text,
            )
            if repaired:
                chapter_json = repaired
                chapter_json.setdefault("chapterId", section.chapter_id)
                chapter_json.setdefault("anchor", section.slug)
                chapter_json.setdefault("title", section.title)
                chapter_json.setdefault("order", section.order)
                self._sanitize_chapter_blocks(chapter_json, section_outline=[{"title": o} if isinstance(o, str) else o for o in section.outline] if hasattr(section, "outline") and section.outline else None)
                valid, errors = self.validator.validate_chapter(chapter_json)
        content_error: ChapterContentError | None = None
        if valid and not placeholder_created:
            try:
                self._ensure_content_density(chapter_json)
            except ChapterContentError as exc:
                content_error = exc

        error_messages: List[str] = parse_context.copy()
        if not valid and errors:
            error_messages.extend(errors)
        if content_error:
            error_messages.append(str(content_error))

        self.storage.persist_chapter(
            run_dir,
            chapter_meta,
            chapter_json,
            errors=None if not error_messages else error_messages,
        )

        if not valid:
            raise ChapterValidationError(
                f"{section.title} ç« èJSONæ ¡éªå¤±è´¥: {'; '.join(errors[:5])}",
                errors=errors,
            )
        if content_error:
            raise content_error

        return chapter_json

    # ====== åé¨æ¹æ³ ======

    def _chunk_and_filter_markdown(self, markdown_text: str, target_title: str, target_outline: str, max_chars: int = 15000) -> str:
        """
        è½»éçº?Markdown ææ¬ååä¸æéæ£ç´?(Working Memory æºå¶å®ç°)
        æ ¹æ®å½åç« èç?title å?outlineï¼å¯¹é¿ç¯ markdown è¿è¡åºäºæ®µè½/æ é¢çåçï¼
        è®¡ç®å³é®è¯éååº¦ï¼åªä¿çæç¸å³ç?chunks
        """
        if not markdown_text or len(markdown_text) <= max_chars:
            return markdown_text
            
        import re
        import jieba
        
        # 1. ç®åç Markdown ååï¼æäºçº§/ä¸çº§æ é¢æåæ¢è¡æåï¼?
        chunks = re.split(r'\n(?=## |\n\n)', markdown_text)
        
        # 2. æåå½åç« èçç®æ å³é®è¯
        target_text = f"{target_title} {target_outline}"
        # ç®åè¿æ»¤å¸¸è§åç¨è¯ï¼æåå®è¯?
        target_words = set(w for w in jieba.cut(target_text) if len(w) > 1)
        
        if not target_words:
            # æåå¤±è´¥åç´æ¥æªæ?
            return markdown_text[:max_chars]
            
        # 3. å¯¹æ¯ä¸?chunk è¿è¡æå
        chunk_scores = []
        for chunk in chunks:
            if not chunk.strip():
                continue
            # è®¡ç®è¯?chunk ä¸­åå«ç®æ å³é®è¯çæ°é?
            chunk_words = set(jieba.cut(chunk))
            score = len(target_words.intersection(chunk_words))
            # å ä¸é¿åº¦æ©ç½ï¼å¾åäºä¿çä¿¡æ¯ééä¸­çæ®µè½ï¼é¿åæç­æ®µè½
            score += min(len(chunk) / 500.0, 2.0)
            chunk_scores.append((score, chunk))
            
        # 4. æåæ°ååºæåº
        chunk_scores.sort(key=lambda x: x[0], reverse=True)
        
        # 5. ç»è£æé«åç?chunks ç´å°è¾¾å° max_chars éå¶
        selected_chunks = []
        current_len = 0
        for score, chunk in chunk_scores:
            if current_len + len(chunk) > max_chars:
                # å°½éåæ»¡
                if current_len < max_chars * 0.5:
                    selected_chunks.append(chunk[:max_chars - current_len] + "\n...(æªæ­)")
                break
            selected_chunks.append(chunk)
            current_len += len(chunk)
            
        # æå¨åæä¸­çååé¡ºåºéæ°æåºï¼ä¸ºäºå¯è¯»æ§ï¼è¿éç®åå¤çï¼ç´æ¥è¿åï¼?
        # è¿éä¸ºäºå¿«éå®ç°ï¼ç´æ¥ç¨ç¸å³åº¦æé«çæ¾å¨åé¢
        return "\n\n".join(selected_chunks)

    def _build_payload(self, section: TemplateSection, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        æé LLMè¾å¥payload

        åæ°:
            section: å½åè¦çæçç« èï¼æä¾æ é¢?ç¼å·/æçº²
            context: å¨å±ä¸ä¸æå­å¸ï¼åå«ä¸»é¢ãä¸å¼ææ¥åãç¯å¹è§åç­

        è¿å:
            dict: å¯ä»¥ç´æ¥åºååè¿æç¤ºè¯çpayloadï¼å¼é¡¾ç« èä¿¡æ¯ä¸å¨å±çº¦æ
        """
        reports = context.get("reports", {})
        # ç« èç¯å¹è§åï¼æ¥èªWordBudgetNodeï¼ï¼ç¨äºæå¯¼å­æ°ä¸å¼ºè°ç¹
        chapter_plan_map = context.get("chapter_directives", {})
        chapter_plan = chapter_plan_map.get(section.chapter_id) if chapter_plan_map else {}

        # ä»?layout ç?tocPlan ä¸­æ¥æ¾è¯¥ç« èæ¯å¦åè®¸ä½¿ç¨SWOTååPESTå?
        allow_swot = self._get_chapter_swot_permission(section.chapter_id, context)
        allow_pest = self._get_chapter_pest_permission(section.chapter_id, context)

        payload = {
            "section": {
                "chapterId": section.chapter_id,
                "title": section.title,
                "slug": section.slug,
                "order": section.order,
                "number": section.number,
                "outline": section.outline,
            },
            "globalContext": {
                "query": context.get("query"),
                "templateName": context.get("template_name"),
                "themeTokens": context.get("theme_tokens", {}),
                "styleDirectives": context.get("style_directives", {}),
                # layoutéåå«æ é¢?ç®å½/heroç­ä¿¡æ¯ï¼æ¹ä¾¿ç« èä¿æç»ä¸è§è§è°æ?
                "layout": context.get("layout"),
                "templateOverview": context.get("template_overview", {}),
            },
            "reports": {
                "query_engine": self._chunk_and_filter_markdown(reports.get("query_engine", ""), section.title, section.outline, 15000),
                "media_engine": self._chunk_and_filter_markdown(reports.get("media_engine", ""), section.title, section.outline, 15000),
                "insight_engine": self._chunk_and_filter_markdown(reports.get("insight_engine", ""), section.title, section.outline, 15000),
            },
            # =======================
            # æ°å¢: ä¼ éåæè®°å¿?
            # =======================
            "previousChapterMemories": context.get("chapter_memories", []),
            "forumLogs": self._chunk_and_filter_markdown(context.get("forum_logs", ""), section.title, section.outline, 15000),
            "dataBundles": str(context.get("data_bundles", []))[:10000] if context.get("data_bundles") else [],
            "constraints": {
                "language": "zh-CN",
                "maxTokens": context.get("max_tokens", 4096),
                "allowedBlocks": ALLOWED_BLOCK_TYPES,
                "allowSwot": allow_swot,
                "allowPest": allow_pest,
                "styleHints": {
                    "expectWidgets": True,
                    "forceHeadingAnchors": True,
                    "allowInlineMix": True,
                },
            },
            "chapterPlan": chapter_plan,
            "wordPlan": context.get("word_plan"),
        }
        if chapter_plan:
            constraints = payload["constraints"]
            if chapter_plan.get("targetWords"):
                constraints["wordTarget"] = chapter_plan["targetWords"]
            if chapter_plan.get("minWords"):
                constraints["minWords"] = chapter_plan["minWords"]
            if chapter_plan.get("maxWords"):
                constraints["maxWords"] = chapter_plan["maxWords"]
            if chapter_plan.get("emphasis"):
                constraints["emphasis"] = chapter_plan["emphasis"]
            if chapter_plan.get("sections"):
                constraints["sectionBudgets"] = chapter_plan["sections"]
                payload["globalContext"]["sectionBudgets"] = chapter_plan["sections"]
        return payload

    def _get_chapter_swot_permission(self, chapter_id: str, context: Dict[str, Any]) -> bool:
        """
        ä»?layout ç?tocPlan ä¸­æ¥æ¾æå®ç« èæ¯å¦åè®¸ä½¿ç?SWOT å

        å¨ææå¤åªæä¸ä¸ªç« èåè®¸ä½¿ç?SWOT åï¼ç±ææ¡£è®¾è®¡é¶æ®µå¨ tocPlan ä¸?
        éè¿ allowSwot å­æ®µæ è®°

        åæ°:
            chapter_id: å½åç« èID
            context: å¨å±ä¸ä¸æå­å¸

        è¿å:
            bool: å¦æè¯¥ç« èåè®¸ä½¿ç?SWOT ååè¿å Trueï¼å¦åè¿å?False
        """
        layout = context.get("layout")
        if not isinstance(layout, dict):
            return False

        toc_plan = layout.get("tocPlan")
        if not isinstance(toc_plan, list):
            return False

        for entry in toc_plan:
            if not isinstance(entry, dict):
                continue
            if entry.get("chapterId") == chapter_id:
                return bool(entry.get("allowSwot", False))

        return False

    def _get_chapter_pest_permission(self, chapter_id: str, context: Dict[str, Any]) -> bool:
        """
        ä»?layout ç?tocPlan ä¸­æ¥æ¾æå®ç« èæ¯å¦åè®¸ä½¿ç?PEST å

        å¨ææå¤åªæä¸ä¸ªç« èåè®¸ä½¿ç?PEST åï¼ç±ææ¡£è®¾è®¡é¶æ®µå¨ tocPlan ä¸?
        éè¿ allowPest å­æ®µæ è®°

        PESTåç¨äºå®è§ç¯å¢åæï¼
        - Politicalï¼æ¿æ²»å ç´ ï¼
        - Economicï¼ç»æµå ç´ ï¼
        - Socialï¼ç¤¾ä¼å ç´ ï¼
        - Technologicalï¼ææ¯å ç´ ï¼

        åæ°:
            chapter_id: å½åç« èID
            context: å¨å±ä¸ä¸æå­å¸

        è¿å:
            bool: å¦æè¯¥ç« èåè®¸ä½¿ç?PEST ååè¿å Trueï¼å¦åè¿å?False
        """
        layout = context.get("layout")
        if not isinstance(layout, dict):
            return False

        toc_plan = layout.get("tocPlan")
        if not isinstance(toc_plan, list):
            return False

        for entry in toc_plan:
            if not isinstance(entry, dict):
                continue
            if entry.get("chapterId") == chapter_id:
                return bool(entry.get("allowPest", False))

        return False

    def _stream_llm(
        self,
        user_message: str,
        chapter_dir: Path,
        stream_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        section_meta: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        æµå¼è°ç¨LLMå¹¶å®æ¶åå¥rawæä»¶ï¼åæ¶éè¿åè°å°deltaæåº

        åæ°:
            user_message: æ¼è£å¥½çç¨æ·æç¤ºè¯
            chapter_dir: ç« èçæ¬å°ç¼å­ç®å½ï¼ç¨äºå­æ¾ stream.raw
            stream_callback: SSEæµå¼æ¨éçåè°å½æ°
            section_meta: éå¸¦çç« èID/æ é¢ï¼ç¨äºåè°payload
            **kwargs: éä¼ æ¸©åº¦op_pç­åæ°

        è¿å:
            str: å°æædeltaæ¼æ¥åçåå§ææ¬
        """
        chunks: List[str] = []
        with self.storage.capture_stream(chapter_dir) as stream_fp:
            stream = self.llm_client.stream_invoke(
                SYSTEM_PROMPT_CHAPTER_JSON,
                user_message,
                temperature=kwargs.get("temperature", 0.2),
                top_p=kwargs.get("top_p", 0.95),
            )
            for delta in stream:
                stream_fp.write(delta)
                chunks.append(delta)
                if stream_callback:
                    meta = section_meta or {}
                    try:
                        stream_callback(delta, meta)
                    except Exception as callback_error:  # pragma: no cover - ä»è®°å½ï¼ä¸é»æ­ä¸»æµç¨
                        logger.warning(f"ç« èæµå¼åè°å¤±è´¥: {callback_error}")
        return "".join(chunks)

    def _attempt_cross_engine_json_rescue(
        self,
        section: TemplateSection,
        generation_payload: Dict[str, Any],
        raw_text: str,
        run_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        ä¾æ¬¡è°ç¨Report/Forum/Insight/Mediaåå¥APIå°è¯ä¿®å¤æ æ³è§£æçJSON

        Returns:
            dict | None: æåä¿®å¤æ¶è¿åç« èJSONï¼å¦åä¸ºNone
        """
        if not self.fallback_llm_clients:
            return None
        if self._chapter_already_skipped(section):
            logger.info(f"[{run_id}] {section.title} å·²æ è®°ä¸ºå ä½ï¼ä¸åè§¦åè·¨å¼æä¿®å¤")
            return None
        section_payload = {
            "chapterId": section.chapter_id,
            "title": section.title,
            "slug": section.slug,
            "order": section.order,
            "number": section.number,
            "outline": section.outline,
        }
        repair_prompt = build_chapter_recovery_payload(
            section_payload,
            generation_payload,
            raw_text,
        )
        attempted_labels = self._rescue_attempted_labels.setdefault(section.chapter_id, set())
        for label, client in self.fallback_llm_clients:
            if label in attempted_labels:
                continue
            attempt_index = len(attempted_labels) + 1
            attempted_labels.add(label)
            logger.info(
                f"[{run_id}] ç« è {section.title} è§¦å {label} API JSONæ¢ä¿®ï¼ç¬¬{attempt_index}æ¬¡å°è¯ï¼"
            )
            try:
                response = client.invoke(
                    SYSTEM_PROMPT_CHAPTER_JSON_RECOVERY,
                    repair_prompt,
                    temperature=0.0,
                    top_p=0.05,
                )
            except Exception as exc:
                logger.warning(f"{label} JSONä¿®å¤è°ç¨å¤±è´¥: {exc}")
                continue
            if not response:
                continue
            try:
                repaired = self._parse_chapter(response)
            except Exception as exc:
                logger.warning(f"{label} JSONä¿®å¤è¾åºä»æ æ³è§£æ? {exc}")
                continue
            logger.warning(f"[{run_id}] {label} APIå·²ä¿®å¤ç« èJSON")
            self._archived_failed_json.pop(section.chapter_id, None)
            return repaired
        return None

    def _ensure_run_state(self, run_id: str):
        """ç¡®ä¿æ¯æ¬¡æ¥åè¿è¡æ¶çä¿®å¤ç¶æéç¦»ï¼é²æ­¢ä¸ä¸ä»½ä»»å¡çè®°å½å½±åæ°ä»»å¡""
        if self._active_run_id == run_id:
            return
        self._active_run_id = run_id
        self._rescue_attempted_labels = {}
        self._skipped_placeholder_chapters = set()
        self._archived_failed_json = {}

    def _archive_failed_output(self, section: TemplateSection, raw_text: str):
        """ç¼å­å½åç« èçåå§éè¯¯JSONï¼ä»¥ä¾¿åç»­å ä½æäººå·¥ä½¿ç¨""
        if not raw_text:
            return
        self._archived_failed_json[section.chapter_id] = raw_text

    def _get_archived_failed_output(self, section: TemplateSection) -> Optional[str]:
        """è·åç« èæè¿ä¸æ¬¡å¤±è´¥çåå§è¾åº""
        return self._archived_failed_json.get(section.chapter_id)

    def _mark_chapter_skipped(self, section: TemplateSection):
        """è®°å½è¯¥ç« èå·²ç»éçº§ä¸ºå ä½ï¼é¿åéå¤è§¦åè·¨å¼æä¿®å¤""
        self._skipped_placeholder_chapters.add(section.chapter_id)

    def _chapter_already_skipped(self, section: TemplateSection) -> bool:
        """å¤æ­ç« èæ¯å¦å·²ç»è¢«æ è®°ä¸ºå ä½""
        return section.chapter_id in self._skipped_placeholder_chapters

    def _build_placeholder_chapter(
        self,
        section: TemplateSection,
        raw_text: str,
        parse_error: Exception,
    ) -> Optional[Tuple[Dict[str, Any], List[str]]]:
        """
        å¨ææä¿®å¤å¤±è´¥æ¶æé å¯æ¸²æçå ä½ç« èï¼å¹¶è®°å½æ¥å¿æä»¶ä¾åç»­ææ¥
        """
        snapshot = self._get_archived_failed_output(section) or raw_text
        log_ref = self._persist_error_payload(section, snapshot, parse_error)
        if not log_ref:
            logger.error(f"{section.title} ç« èJSONå®å¨æåä¸æ æ³åå¥æ¥å¿?)
            return None
        importance = "critical" if self._is_section_critical(section) else "standard"
        message = (
            f"LLMè¿ååè§£æéè¯¯ï¼è¯¦æè¯·è§ {log_ref['relativeFile']} ç?{log_ref['entryId']} è®°å½
        )
        heading_block = {
            "type": "heading",
            "level": 2 if importance == "critical" else 3,
            "text": section.title,
            "anchor": section.slug,
        }
        callout_block = {
            "type": "callout",
            "tone": "danger" if importance == "critical" else "warning",
            "title": "LLMè¿ååè§£æéè¯?,
            "blocks": [
                {
                    "type": "paragraph",
                    "inlines": [
                        {
                            "text": message,
                        }
                    ],
                }
            ],
            "meta": {
                "errorLogRef": log_ref,
                "rawJsonPreview": (snapshot or "")[:2000],
                "errorMessage": message,
                "importance": importance,
            },
        }
        placeholder = {
            "chapterId": section.chapter_id,
            "title": section.title,
            "anchor": section.slug,
            "order": section.order,
            "blocks": [heading_block, callout_block],
            "errorPlaceholder": True,
        }
        errors = [
            f"{section.title} ç« èJSONè§£æå¤±è´¥ï¼å·²éçº§ä¸ºå ä½ãåè?{log_ref['relativeFile']}#{log_ref['entryId']}"
        ]
        self._mark_chapter_skipped(section)
        return placeholder, errors

    def _parse_chapter(self, raw_text: str) -> Dict[str, Any]:
        """
        æ¸æ´LLMè¾åºå¹¶è§£æJSON

        åæ°:
            raw_text: LLMåå§è¾åºï¼å¯è½åå«```åè£¹æé¢å¤è¯´æï¼

        è¿å:
            dict: ç« èJSONå¯¹è±¡ï¼è³å°åå?chapterId/title/blocks

        å¼å¸¸:
            ChapterJsonParseError: å¤ç§ä¿®å¤ç­ç¥ä»æ æ³è§£æåæ³JSON
        """
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            raise ChapterJsonParseError("LLMè¿åç©ºåå®?, raw_text=raw_text)

        candidate_payloads = [cleaned]
        repaired = self._repair_llm_json(cleaned)
        if repaired != cleaned:
            candidate_payloads.append(repaired)

        data: Dict[str, Any] | None = None
        try:
            data = self._parse_with_candidates(candidate_payloads)
        except json.JSONDecodeError as exc:
            repaired_payload = self._attempt_json_repair(cleaned)
            if repaired_payload:
                candidate_payloads.append(repaired_payload)
                try:
                    data = self._parse_with_candidates(candidate_payloads[-1:])
                except json.JSONDecodeError:
                    data = None
            if data is None:
                try:
                    data = self._robust_parser.parse(
                        cleaned,
                        context_name="ChapterJSON",
                        expected_keys=["chapter", "blocks", "chapterId", "title"],
                    )
                except JSONParseError as robust_exc:
                    raise ChapterJsonParseError(
                        f"ç« èJSONè§£æå¤±è´¥: {robust_exc}", raw_text=cleaned
                    ) from robust_exc

        if "chapter" in data and isinstance(data["chapter"], dict):
            return data["chapter"]
        if isinstance(data, dict) and all(
            key in data for key in ("chapterId", "title", "blocks")
        ):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "chapter" in item and isinstance(item["chapter"], dict):
                        return item["chapter"]
                    if all(key in item for key in ("chapterId", "title", "blocks")):
                        return item
        raise ChapterJsonParseError("ç« èJSONç¼ºå°chapterå­æ®µæç»æä¸å®æ´", raw_text=cleaned)

    def _persist_error_payload(
        self,
        section: TemplateSection,
        raw_text: str,
        parse_error: Exception,
    ) -> Optional[Dict[str, str]]:
        """å°æ æ³è§£æçJSONææ¬è½çï¼ä¾¿äºå¨HTMLä¸­æåå·ä½æä»¶""
        try:
            self._failed_block_counter += 1
            entry_id = f"E{self._failed_block_counter:04d}"
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            slug = section.slug or "section"
            filename = f"{timestamp}-{slug}-{entry_id}.json"
            file_path = self.error_log_dir / filename
            payload = {
                "chapterId": section.chapter_id,
                "title": section.title,
                "slug": section.slug,
                "order": section.order,
                "rawOutput": raw_text,
                "error": str(parse_error),
                "loggedAt": timestamp,
            }
            file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            try:
                relative_path = str(file_path.relative_to(Path.cwd()))
            except ValueError:
                relative_path = str(file_path)
            return {
                "file": str(file_path),
                "relativeFile": relative_path,
                "entryId": entry_id,
                "timestamp": timestamp,
            }
        except Exception as exc:
            logger.error(f"è®°å½ç« èJSONéè¯¯æ¥å¿å¤±è´¥: {exc}")
            return None

    def _is_section_critical(self, section: TemplateSection) -> bool:
        """åºäºç« èæ·±åº¦/ç¼å·å¤æ­æ¯å¦ä¼å½±åç®å½ï¼ä»èå³å®æç¤ºå¼ºåº¦""
        if not section:
            return False
        if section.depth <= 2:
            return True
        number = section.number or ""
        if number and number.count(".") <= 1:
            return True
        return False

    def _repair_llm_json(self, text: str) -> str:
        """
        å¤çå¸¸è§çLLMéè¯¯ï¼å¦":=å¯¼è´çéæ³JSONï¼

        åæ°:
            text: åå§ç« èJSONææ¬

        è¿å:
            str: ä¿®å¤åçææ¬ï¼è¥æªåæ¹å¨åè¿åååå®¹
        """
        repaired = text
        mutated = False

        new_text = self._COLON_EQUALS_PATTERN.sub(r"\1", repaired)
        if new_text != repaired:
            logger.warning("æ£æµå°ç« èJSONä¸­ç\":=\"å­ç¬¦ï¼å·²èªå¨ç§»é¤å¤ä½ç?='å?)
            repaired = new_text
            mutated = True

        repaired, escaped = self._escape_in_string_controls(repaired)
        if escaped:
            logger.warning("æ£æµå°ç« èJSONå­ç¬¦ä¸²ä¸­å­å¨æªè½¬ä¹çæ§å¶å­ç¬¦ï¼å·²èªå¨è½¬æ¢ä¸ºè½¬ä¹åºå?)
            mutated = True

        repaired, balanced = self._balance_brackets(repaired)
        if balanced:
            logger.warning("æ£æµå°ç« èJSONæ¬å·ä¸å¹³è¡¡ï¼å·²èªå¨è¡¥é½?åé¤å¼å¸¸æ¬å·")
            mutated = True

        repaired, commas_fixed = self._fix_missing_commas(repaired)
        if commas_fixed:
            logger.warning("æ£æµå°ç« èJSONå¯¹è±¡/æ°ç»ä¹é´ç¼ºå°éå·ï¼å·²èªå¨è¡¥é½")
            mutated = True

        return repaired if mutated else text

    def _escape_in_string_controls(self, text: str) -> Tuple[str, bool]:
        """
        å°å­ç¬¦ä¸²å­é¢éä¸­çè£¸æ¢è¡/å¶è¡¨ç¬?æ§å¶å­ç¬¦æ¿æ¢ä¸ºJSONåæ³çè½¬ä¹åºå
        """
        if not text:
            return text, False

        result: List[str] = []
        in_string = False
        escaped = False
        mutated = False
        control_map = {"\n": "\\n", "\r": "\\n", "\t": "\\t"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string and ch in control_map:
                result.append(control_map[ch])
                mutated = True
                continue

            if in_string and ord(ch) < 0x20:
                result.append(f"\\u{ord(ch):04x}")
                mutated = True
                continue

            result.append(ch)

        return "".join(result), mutated

    def _fix_missing_commas(self, text: str) -> Tuple[str, bool]:
        """å¨å¯¹è±?æ°ç»è¿ç»­åºç°æ¶èªå¨è¡¥éå·"""
        if not text:
            return text, False

        chars: List[str] = []
        mutated = False
        in_string = False
        escaped = False
        length = len(text)
        i = 0
        while i < length:
            ch = text[i]
            chars.append(ch)
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == '"':
                in_string = not in_string
                i += 1
                continue
            if not in_string and ch in "}]":
                j = i + 1
                while j < length and text[j] in " \t\r\n":
                    j += 1
                if j < length:
                    next_ch = text[j]
                    if next_ch in "{[":
                        chars.append(",")
                        mutated = True
            i += 1
        return "".join(chars), mutated

    def _balance_brackets(self, text: str) -> Tuple[str, bool]:
        """å°è¯ä¿®å¤å LLMå¤å/å°åæ¬å·å¯¼è´çä¸å¹³è¡¡ç»æ"""
        if not text:
            return text, False

        result: List[str] = []
        stack: List[str] = []
        mutated = False
        in_string = False
        escaped = False

        opener_map = {"{": "}", "[": "]"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string:
                result.append(ch)
                continue

            if ch in "{[":
                stack.append(ch)
                result.append(ch)
                continue

            if ch in "}]":
                if stack and ((ch == "}" and stack[-1] == "{") or (ch == "]" and stack[-1] == "[")):
                    stack.pop()
                    result.append(ch)
                else:
                    mutated = True
                continue

            result.append(ch)

        while stack:
            opener = stack.pop()
            result.append(opener_map[opener])
            mutated = True

        return "".join(result), mutated

    def _attempt_json_repair(self, text: str) -> str | None:
        """ä½¿ç¨å¯éçjson_repairåºè¿ä¸æ­¥ä¿®å¤å¤æè¯­æ³éè¯?""
        if not _json_repair_fn:
            return None
        try:
            fixed = _json_repair_fn(text)
        except Exception as exc:  # pragma: no cover - åºçº§æé
            logger.warning(f"json_repair ä¿®å¤ç« èJSONå¤±è´¥: {exc}")
            return None
        if fixed == text:
            return None
        logger.warning("å·²ä½¿ç¨json_repairèªå¨ä¿®å¤ç« èJSONè¯­æ³")
        return fixed

    def _attempt_llm_structural_repair(
        self,
        chapter: Dict[str, Any],
        validation_errors: List[str],
        raw_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """å°ç»ææ§éè¯¯çç« èäº¤ç»LLMååºä¿®å¤ï¼ä¿æReport Engineç¸åçAPIè®¾ç½®""
        if not validation_errors:
            return None
        payload = build_chapter_repair_prompt(chapter, validation_errors, raw_text)
        try:
            response = self.llm_client.invoke(
                SYSTEM_PROMPT_CHAPTER_JSON_REPAIR,
                payload,
                temperature=0.0,
                top_p=0.05,
            )
        except Exception as exc:  # pragma: no cover - ç½ç»æAPIå¼å¸¸ä»è®°å½?
            logger.error(f"ç« èJSON LLMä¿®å¤è°ç¨å¤±è´¥: {exc}")
            return None
        if not response:
            return None
        try:
            repaired = self._parse_chapter(response)
        except Exception as exc:
            logger.error(f"LLMä¿®å¤åçç« èJSONè§£æå¤±è´¥: {exc}")
            return None
        logger.warning("ç« èJSONç»å¤æ¬¡æ¬å°ä¿®å¤ä»ä¸åè§ï¼å·²æåå¯ç¨LLMååºä¿®å¤")
        return repaired

    def _sanitize_chapter_blocks(self, chapter: Dict[str, Any], section_outline: Optional[List[Dict[str, Any]]] = None):
        """
        ä¿®æ­£å¸¸è§çç»ææ§éè¯¯ï¼ä¾å¦list.itemsåµå¥è¿æ·±ï¼ï¼å¹¶åé¤è¶ææ é¢

        åæ°:
            chapter: ç« èJSONå¯¹è±¡ï¼ä¼å¨åå°è¢«æ¸çåè§æ´
            section_outline: è¯¥ç« èçåæ³æçº²åè¡¨ï¼ç¨äºåé¤è¶æç heading å
        """

        # æ¶éææåæ³çæ é¢åç¼ï¼ä¾å¦?"4.1"ï¼?
        valid_prefixes = []
        if section_outline:
            import re
            for item in section_outline:
                title = item.get("title", "")
                m = re.match(r"^([\d\.]+)", title.strip())
                if m:
                    valid_prefixes.append(m.group(1))

        def walk(blocks: List[Dict[str, Any]] | None):
            """éå½æ£æ¥å¹¶ä¿®å¤åµå¥ç»æï¼ä¿è¯æ¯ä¸ªblockåæ³"""
            if not isinstance(blocks, list):
                return
            # åè¿æ»¤æéå­å¸ç±»åçå¼å¸¸ block
            valid_indices = []
            for idx, block in enumerate(blocks):
                if not isinstance(block, dict):
                    # å°è¯å°å­ç¬¦ä¸²è½¬æ¢ä¸?paragraph
                    if isinstance(block, str) and block.strip():
                        blocks[idx] = self._as_paragraph_block(block)
                        valid_indices.append(idx)
                        logger.warning(f"walk: å°å­ç¬¦ä¸² block è½¬æ¢ä¸?paragraph")
                    elif isinstance(block, list):
                        # å°è¯æååè¡¨ä¸­çææå­å¸
                        for item in block:
                            if isinstance(item, dict):
                                self._ensure_block_type(item)
                                blocks[idx] = item
                                valid_indices.append(idx)
                                logger.warning(f"walk: ä»åè¡¨ä¸­æåå­å¸ block")
                                break
                        else:
                            logger.warning(f"walk: è·³è¿æ æçåè¡?block: {block}")
                    else:
                        logger.warning(f"walk: è·³è¿æ æç?blockï¼ç±»å? {type(block).__name__}ï¼?)
                else:
                    # å¦ææ?headingï¼æ ¡éªå¶æ¯å¦å¨åæ³å¤§çº²åç¼å?
                    if valid_prefixes and block.get("type") == "heading":
                        heading_text = block.get("text", "")
                        import re
                        m = re.match(r"^([\d\.]+)", heading_text.strip())
                        if m:
                            prefix = m.group(1)
                            if prefix not in valid_prefixes:
                                logger.warning(f"åé¤è¶æçæçæ é¢?block: {heading_text} (å°å¶éçº§ä¸ºå ç²æ®µè?")
                                # å°è¶æ?heading éçº§ä¸ºå ç²æ®µè?
                                blocks[idx] = {
                                    "type": "paragraph",
                                    "inlines": [
                                        {"text": heading_text, "marks": [{"type": "bold"}]}
                                    ]
                                }
                    valid_indices.append(idx)

            for idx in valid_indices:
                block = blocks[idx]
                if not isinstance(block, dict):
                    continue
                self._ensure_block_type(block)
                self._sanitize_block_content(block)
                block_type = block.get("type")
                if block_type == "list":
                    # èªå¨ä¿®å¤ listTypeï¼ç¡®ä¿æ¯åæ³å?
                    self._normalize_list_type(block)
                    items = block.get("items")
                    normalized = self._normalize_list_items(items)
                    if normalized:
                        block["items"] = normalized
                    for entry in block.get("items", []):
                        walk(entry)
                elif block_type in {"callout", "blockquote", "engineQuote"}:
                    walk(block.get("blocks"))
                elif block_type == "table":
                    for row in block.get("rows", []):
                        if not isinstance(row, dict):
                            continue
                        cells = row.get("cells") or []
                        for cell in cells:
                            if not isinstance(cell, dict):
                                continue
                            walk(cell.get("blocks"))
                elif block_type == "widget":
                    self._normalize_widget_block(block)
                else:
                    nested = block.get("blocks")
                    if isinstance(nested, list):
                        walk(nested)

        walk(chapter.get("blocks"))

        blocks = chapter.get("blocks")
        if isinstance(blocks, list):
            # å¨åå¹¶ååè¿æ»¤æææéå­å¸ç±»åç?block
            filtered_blocks = [b for b in blocks if isinstance(b, dict)]
            chapter["blocks"] = self._merge_fragment_sequences(filtered_blocks)

    def _ensure_content_density(self, chapter: Dict[str, Any]):
        """
        æ ¡éªç« èæ­£æå¯åº¦

        è¥blocksç¼ºå¤±ãé¤æ é¢å¤æ ææåºåï¼ææ­£æå­ç¬¦æ°ä½äºéå¼ï¼
        åè§ä¸ºç« èåå®¹å¼å¸¸ï¼è§¦åChapterContentErrorä»¥ä¾¿ä¸æ¸¸éè¯

        åæ°:
            chapter: å½åç« èJSON

        å¼å¸¸:
            ChapterContentError: å½æ­£æåºåæ°éæå­ç¬¦æ°è¾¾ä¸å°ä¸éæ¶æåº
        """
        blocks = chapter.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise ChapterContentError(
                "ç« èç¼ºå°æ­£æåºåï¼æ æ³è¾åºåå®?,
                chapter=chapter,
                body_characters=0,
                narrative_characters=0,
                non_heading_blocks=0,
            )

        non_heading_blocks = [
            block
            for block in blocks
            if isinstance(block, dict)
            and block.get("type") not in {"heading", "divider", "toc"}
        ]
        valid_block_count = len(non_heading_blocks)
        body_characters = self._count_body_characters(blocks)
        narrative_characters = self._count_narrative_characters(blocks)

        if (
            valid_block_count < self._MIN_NON_HEADING_BLOCKS
            or body_characters < self._MIN_BODY_CHARACTERS
            or narrative_characters < self._MIN_NARRATIVE_CHARACTERS
        ):
            raise ChapterContentError(
                f"{chapter.get('title') or 'è¯¥ç« è?} æ­£æä¸è¶³ï¼ææåºå?{valid_block_count} ä¸ªï¼ä¼°ç®å­ç¬¦æ?{body_characters}ï¼åè¿°æ§å­ç¬¦æ° {narrative_characters}",
                chapter=chapter,
                body_characters=body_characters,
                narrative_characters=narrative_characters,
                non_heading_blocks=valid_block_count,
            )

    def _count_body_characters(self, blocks: Any) -> int:
        """
        éå½ç»è®¡æ­£æå­ç¬¦æ°

        - å¿½ç¥heading/divider/widgetç­éæ­£æç±»åï¼?
        - å¯¹paragraph/list/table/calloutç­ç»ææ½ååµå¥ææ¬ï¼
        - ä»ç¨äºç²ç²åº¦å¤æ­ç¯å¹æ¯å¦åç

        åæ°:
            blocks: ç« èç?blocks åè¡¨æå­æ 

        è¿å:
            int: ä¼°ç®çæ­£æå­ç¬¦æ°é
        """

        def walk(node: Any) -> int:
            """éå½ä¸é»blockæ å¹¶è¿åå­ç¬¦ä¼°ç®ï¼è·³è¿éæ­£æç±»å"""
            if node is None:
                return 0
            if isinstance(node, list):
                return sum(walk(item) for item in node)
            if isinstance(node, str):
                return len(node.strip())
            if not isinstance(node, dict):
                return 0

            block_type = node.get("type")
            if block_type in {"heading", "divider", "toc", "widget"}:
                return 0

            if block_type == "paragraph":
                return self._estimate_paragraph_characters(node)

            if block_type == "list":
                total = 0
                for item in node.get("items", []):
                    total += walk(item)
                return total

            if block_type in {"blockquote", "callout", "engineQuote"}:
                return walk(node.get("blocks"))

            if block_type == "table":
                total = 0
                for row in node.get("rows", []):
                    cells = row.get("cells") or []
                    for cell in cells:
                        total += walk(cell.get("blocks"))
                return total

            nested = node.get("blocks")
            if isinstance(nested, list):
                return walk(nested)

            return len(self._extract_block_text(node).strip())

        return walk(blocks)

    def _count_narrative_characters(self, blocks: Any) -> int:
        """
        ç»è®¡paragraph/callout/list/blockquote/engineQuoteç­åè¿°æ§ç»æçå­ç¬¦æ°ï¼é¿åè¢«è¡¨æ ?å¾è¡¨"å·é¿"
        """

        def walk(node: Any) -> int:
            """éå½éååè¿°æ§èç¹ï¼å¿½ç¥å¾è¡¨/ç®å½ç­éæ­£æç»æ"""
            if node is None:
                return 0
            if isinstance(node, list):
                return sum(walk(item) for item in node)
            if isinstance(node, str):
                return len(node.strip())
            if not isinstance(node, dict):
                return 0

            block_type = node.get("type")
            if block_type == "paragraph":
                return self._estimate_paragraph_characters(node)
            if block_type == "list":
                total = 0
                for item in node.get("items", []):
                    total += walk(item)
                return total
            if block_type in {"callout", "blockquote", "engineQuote"}:
                return walk(node.get("blocks"))

            # listé¡¹å¯è½æ¯å¿ådictï¼å¼å®¹æ§éå?
            if block_type is None:
                nested = node.get("blocks")
                if isinstance(nested, list):
                    return walk(nested)
            return 0

        return walk(blocks)

    def _estimate_paragraph_characters(self, block: Dict[str, Any]) -> int:
        """æåparagraphææ¬é¿åº¦ï¼å¤ç¨å¨å¤ç§ç»è®¡ä¸­""
        inlines = block.get("inlines")
        if isinstance(inlines, list):
            total = 0
            for run in inlines:
                if isinstance(run, dict):
                    text = run.get("text")
                    if isinstance(text, str):
                        total += len(text.strip())
            return total
        text_value = block.get("text")
        if isinstance(text_value, str):
            return len(text_value.strip())
        return len(self._extract_block_text(block).strip())

    def _sanitize_block_content(self, block: Dict[str, Any]):
        """æ ¹æ®ç±»ååç²¾ç»åä¿®å¤ï¼ä¾å¦æ¸çparagraphåçéæ³inline mark"""
        block_type = block.get("type")
        if block_type == "paragraph":
            self._normalize_paragraph_block(block)
        elif block_type == "table":
            self._sanitize_table_block(block)
        elif block_type == "engineQuote":
            self._sanitize_engine_quote_block(block)

    def _sanitize_table_block(self, block: Dict[str, Any]):
        """ä¿è¯è¡¨æ ¼çrows/cellsç»æåæ³ä¸æ¯ä¸ªååæ ¼åå«è³å°ä¸ä¸ªblock"""
        raw_rows = block.get("rows")
        # åæ£æµæ¯å¦å­å¨åµå¥è¡ç»æé®é¢ï¼åªæ?è¡ä½cellsä¸­æåµå¥ï¼?
        if isinstance(raw_rows, list) and len(raw_rows) == 1:
            first_row = raw_rows[0]
            if isinstance(first_row, dict):
                cells = first_row.get("cells", [])
                # æ£æµæ¯å¦å­å¨åµå¥ç»æ?
                has_nested = any(
                    isinstance(cell, dict) and "cells" in cell and "blocks" not in cell
                    for cell in cells
                    if isinstance(cell, dict)
                )
                if has_nested:
                    # ä¿®å¤åµå¥è¡ç»æ?
                    fixed_rows = self._fix_nested_rows_structure(raw_rows)
                    block["rows"] = fixed_rows
                    return
        # æ­£å¸¸æåµä¸ï¼ä½¿ç¨æ åè§èå?
        rows = self._normalize_table_rows(raw_rows)
        block["rows"] = rows

    def _fix_nested_rows_structure(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        ä¿®å¤åµå¥éè¯¯çè¡¨æ ¼è¡ç»æ

        å½LLMçæçè¡¨æ ¼åªæ?è¡ä½æææ°æ®è¢«åµå¥å¨cellsä¸­æ¶ï¼?
        æ¬æ¹æ³ä¼å±å¹³ææååæ ¼å¹¶éæ°ç»ç»ææ­£ç¡®çå¤è¡ç»æ

        åæ°:
            rows: åå§çè¡¨æ ¼è¡æ°ç»ï¼åºè¯¥åªæ?è¡ï¼

        è¿å:
            List[Dict]: ä¿®å¤åçå¤è¡è¡¨æ ¼ç»æ
        """
        if not rows or len(rows) != 1:
            return self._normalize_table_rows(rows)

        first_row = rows[0]
        original_cells = first_row.get("cells", [])

        # éå½å±å¹³ææåµå¥çååæ ?
        all_cells = self._flatten_all_cells_recursive(original_cells)

        if len(all_cells) <= 1:
            return self._normalize_table_rows(rows)

        # è¾å©å½æ°ï¼è·åååæ ¼ææ¬
        def _get_cell_text(cell: Dict[str, Any]) -> str:
            blocks = cell.get("blocks", [])
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        if isinstance(inline, dict):
                            text = inline.get("text", "")
                            if text:
                                return str(text).strip()
            return ""

        def _is_placeholder_cell(cell: Dict[str, Any]) -> bool:
            """å¤æ­ååæ ¼æ¯å¦æ¯å ä½ç¬?""
            text = _get_cell_text(cell)
            return text in ("--", "-", "â?, "-â?, "", "N/A", "n/a")

        def _is_header_cell(cell: Dict[str, Any]) -> bool:
            """å¤æ­ååæ ¼æ¯å¦åè¡¨å¤´ï¼éå¸¸æå ç²æ è®°ææ¯å¸åè¡¨å¤´è¯ï¼?""
            blocks = cell.get("blocks", [])
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        if isinstance(inline, dict):
                            marks = inline.get("marks", [])
                            if any(isinstance(m, dict) and m.get("type") == "bold" for m in marks):
                                return True
            # ä¹æ£æ¥å¸åçè¡¨å¤´è¯?
            text = _get_cell_text(cell)
            header_keywords = {
                "æ¶é´", "æ¥æ", "åç§°", "ç±»å", "ç¶æ?, "æ°é", "éé¢", "æ¯ä¾", "ææ ",
                "å¹³å°", "æ¸ é", "æ¥æº", "æè¿°", "è¯´æ", "å¤æ³¨", "åºå·", "ç¼å·",
                "äºä»¶", "å³é®", "æ°æ®", "æ¯æ", "ååº", "å¸åº", "ææ", "èç¹",
                "ç»´åº¦", "è¦ç¹", "è¯¦æ", "æ ç­¾", "å½±å", "è¶å¿", "æé", "ç±»å«",
                "ä¿¡æ¯", "åå®¹", "é£æ ¼", "åå¥½", "ä¸»è¦", "ç¨æ·", "æ ¸å¿", "ç¹å¾",
                "åç±»", "èå´", "å¯¹è±¡", "é¡¹ç®", "é¶æ®µ", "å¨æ", "é¢ç", "ç­çº§",
            }
            return any(kw in text for kw in header_keywords) and len(text) <= 20

        # è¿æ»¤æå ä½ç¬¦ååæ ?
        valid_cells = [c for c in all_cells if not _is_placeholder_cell(c)]

        if len(valid_cells) <= 1:
            return self._normalize_table_rows(rows)

        # æ£æµè¡¨å¤´åæ°ï¼ç»è®¡è¿ç»­çè¡¨å¤´ååæ ¼æ°é
        header_count = 0
        for cell in valid_cells:
            if _is_header_cell(cell):
                header_count += 1
            else:
                break

        # å¦ææ²¡ææ£æµå°è¡¨å¤´ï¼ä½¿ç¨å¯åå¼æ¹æ³
        if header_count == 0:
            total = len(valid_cells)
            for possible_cols in [4, 5, 3, 6, 2]:
                if total % possible_cols == 0:
                    header_count = possible_cols
                    break
            else:
                # å°è¯æ¾å°ææ¥è¿çè½æ´é¤çåæ?
                for possible_cols in [4, 5, 3, 6, 2]:
                    remainder = total % possible_cols
                    if remainder <= 3:
                        header_count = possible_cols
                        break
                else:
                    # æ æ³ç¡®å®åæ°ï¼ä½¿ç¨åå§æ°æ?
                    return self._normalize_table_rows(rows)

        # è®¡ç®ææçååæ ¼æ°é
        total = len(valid_cells)
        remainder = total % header_count
        if remainder > 0 and remainder <= 3:
            # æªæ­å°¾é¨å¤ä½çååæ ¼
            valid_cells = valid_cells[:total - remainder]
        elif remainder > 3:
            # ä½æ°å¤ªå¤§ï¼å¯è½åæ°æ£æµéè¯?
            return self._normalize_table_rows(rows)

        # éæ°ç»ç»æå¤è¡?
        fixed_rows: List[Dict[str, Any]] = []
        for i in range(0, len(valid_cells), header_count):
            row_cells = valid_cells[i:i + header_count]
            # æ è®°ç¬¬ä¸è¡ä¸ºè¡¨å¤´
            if i == 0:
                for cell in row_cells:
                    cell["header"] = True
            fixed_rows.append({"cells": row_cells})

        return fixed_rows if fixed_rows else self._normalize_table_rows(rows)

    def _flatten_all_cells_recursive(self, cells: List[Any]) -> List[Dict[str, Any]]:
        """
        éå½å±å¹³ææåµå¥çååæ ¼ç»æ

        åæ°:
            cells: å¯è½åå«åµå¥ç»æçååæ ¼æ°ç»

        è¿å:
            List[Dict]: å±å¹³åçååæ ¼æ°ç»ï¼æ¯ä¸ªååæ ¼é½æblocks
        """
        if not cells:
            return []

        flattened: List[Dict[str, Any]] = []

        def _extract_cells(cell_or_list: Any) -> None:
            if not isinstance(cell_or_list, dict):
                if isinstance(cell_or_list, (str, int, float)):
                    flattened.append({"blocks": [self._as_paragraph_block(str(cell_or_list))]})
                return

            # å¦æå½åå¯¹è±¡æ?blocksï¼è¯´æå®æ¯ä¸ä¸ªææçååæ ?
            if "blocks" in cell_or_list:
                # åå»ºååæ ¼å¯æ¬ï¼ç§»é¤åµå¥ç?cells
                clean_cell = {
                    k: v for k, v in cell_or_list.items()
                    if k != "cells"
                }
                # ç¡®ä¿blocksææ
                blocks = clean_cell.get("blocks")
                if not isinstance(blocks, list) or not blocks:
                    clean_cell["blocks"] = [self._as_paragraph_block("")]
                flattened.append(clean_cell)

            # å¦æå½åå¯¹è±¡æåµå¥ç cellsï¼éå½å¤ç
            nested_cells = cell_or_list.get("cells")
            if isinstance(nested_cells, list):
                for nested_cell in nested_cells:
                    _extract_cells(nested_cell)

        for cell in cells:
            _extract_cells(cell)

        return flattened

    def _sanitize_engine_quote_block(self, block: Dict[str, Any]):
        """engineQuoteä»ç¨äºåAgentåè¨ï¼åé¨ä»åè®¸paragraphä¸titleééå®Agentåç§°"""
        engine_raw = block.get("engine")
        engine = engine_raw.lower() if isinstance(engine_raw, str) else None
        if engine not in ENGINE_AGENT_TITLES:
            engine = "insight"
        block["engine"] = engine
        block["title"] = ENGINE_AGENT_TITLES[engine]
        allowed_marks = {"bold", "italic"}
        raw_blocks = block.get("blocks")
        candidates = raw_blocks if isinstance(raw_blocks, list) else ([raw_blocks] if raw_blocks else [])
        sanitized_blocks: List[Dict[str, Any]] = []

        for item in candidates:
            if isinstance(item, dict) and item.get("type") == "paragraph":
                para = dict(item)
            else:
                text = self._extract_block_text(item) if isinstance(item, dict) else (item or "")
                para = self._as_paragraph_block(str(text))

            inlines = para.get("inlines")
            if not isinstance(inlines, list) or not inlines:
                inlines = [self._as_inline_run(self._extract_block_text(para))]

            cleaned_inlines: List[Dict[str, Any]] = []
            for run in inlines:
                if isinstance(run, dict):
                    text_val = run.get("text")
                    text_str = text_val if isinstance(text_val, str) else ("" if text_val is None else str(text_val))
                    marks_raw = run.get("marks") if isinstance(run.get("marks"), list) else []
                    marks_filtered: List[Dict[str, Any]] = []
                    for mark in marks_raw:
                        if not isinstance(mark, dict):
                            continue
                        mark_type = mark.get("type")
                        if mark_type in allowed_marks:
                            marks_filtered.append({"type": mark_type})
                    cleaned_inlines.append({"text": text_str, "marks": marks_filtered})
                else:
                    cleaned_inlines.append(self._as_inline_run(str(run)))

            if not cleaned_inlines:
                cleaned_inlines.append(self._as_inline_run(""))
            para["inlines"] = cleaned_inlines
            para["type"] = "paragraph"
            para.pop("blocks", None)
            sanitized_blocks.append(para)

        if not sanitized_blocks:
            sanitized_blocks.append(self._as_paragraph_block(""))
        block["blocks"] = sanitized_blocks

    def _normalize_table_rows(self, rows: Any) -> List[Dict[str, Any]]:
        """ç¡®ä¿rowså§ç»æ¯ç±rowå¯¹è±¡ç»æçåè¡?""
        if rows is None:
            rows_iterable: List[Any] = []
        elif isinstance(rows, list):
            rows_iterable = rows
        else:
            rows_iterable = [rows]

        normalized_rows: List[Dict[str, Any]] = []
        for row in rows_iterable:
            sanitized_row = self._normalize_table_row(row)
            if sanitized_row:
                normalized_rows.append(sanitized_row)

        if not normalized_rows:
            normalized_rows.append({"cells": [self._build_default_table_cell()]})
        return normalized_rows

    def _normalize_table_row(self, row: Any) -> Dict[str, Any] | None:
        """å°åç§è¡è¡¨è¾¾ç»ä¸æ{'cells': [...]}ç»æ"""
        if row is None:
            return None
        if isinstance(row, dict):
            result = dict(row)
            cells_value = result.get("cells")
        else:
            result = {}
            cells_value = row

        cells = self._normalize_table_cells(cells_value)
        if not cells:
            cells = [self._build_default_table_cell()]
        result["cells"] = cells
        return result

    def _normalize_table_cells(self, cells: Any) -> List[Dict[str, Any]]:
        """æ¸æ´ååæ ¼ï¼ä¿è¯æ¯ä¸ªcellä¸é½æéç©ºblocks"""
        if cells is None:
            cell_entries: List[Any] = []
        elif isinstance(cells, list):
            cell_entries = cells
        else:
            cell_entries = [cells]

        normalized_cells: List[Dict[str, Any]] = []
        for cell in cell_entries:
            # æ£æµéè¯¯åµå¥ç cells ç»æï¼æ cells ä½æ²¡æ?blocks
            # éè¦å±å¹³æå¤ä¸ªç¬ç«ç?cells
            if isinstance(cell, dict) and "cells" in cell and "blocks" not in cell:
                flattened = self._flatten_all_nested_cells(cell)
                normalized_cells.extend(flattened)
            else:
                sanitized = self._normalize_table_cell(cell)
                if sanitized:
                    normalized_cells.append(sanitized)

        return normalized_cells

    def _flatten_all_nested_cells(self, cell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        å±å¹³éè¯¯åµå¥ç?cells ç»æï¼è¿åææå±å¹³åç?cells

        LLM ææ¶ä¼çæç±»ä¼¼è¿æ ·çéè¯¯ç»æï¼?
        { "cells": [
            { "blocks": [...] },
            { "cells": [
                { "blocks": [...] },
                { "cells": [...] }
              ]
            }
          ]
        }

        åºè¯¥å±å¹³ä¸ºç¬ç«ç cells åè¡¨
        """
        nested_cells = cell.get("cells")
        if not isinstance(nested_cells, list) or not nested_cells:
            return [{"blocks": [self._as_paragraph_block("")]}]

        result: List[Dict[str, Any]] = []
        for nested in nested_cells:
            if isinstance(nested, dict):
                if "blocks" in nested and "cells" not in nested:
                    # æ­£å¸¸ç?cellï¼ç´æ¥è§èåæ·»å 
                    sanitized = self._normalize_table_cell(nested)
                    if sanitized:
                        result.append(sanitized)
                elif "cells" in nested and "blocks" not in nested:
                    # ç»§ç»­éå½å±å¹³åµå¥ç?cells
                    result.extend(self._flatten_all_nested_cells(nested))
                else:
                    # å¶ä»æåµï¼å°è¯è§èå
                    sanitized = self._normalize_table_cell(nested)
                    if sanitized:
                        result.append(sanitized)
            elif isinstance(nested, (str, int, float)):
                result.append({"blocks": [self._as_paragraph_block(str(nested))]})

        return result if result else [{"blocks": [self._as_paragraph_block("")]}]

    def _normalize_table_cell(self, cell: Any) -> Dict[str, Any] | None:
        """æåç§ååæ ¼åæ³è§æ´ä¸ºschemaè®¤å¯çå½¢å¼?""
        if cell is None:
            return {"blocks": [self._as_paragraph_block("")]}

        if isinstance(cell, dict):
            # æ£æµéè¯¯åµå¥ç cells ç»æï¼æ cells ä½æ²¡æ?blocks
            # è¿æ¯ LLM å¸¸è§çéè¯¯ï¼æåçº?cell åµå¥è¿äº cells æ°ç»
            if "cells" in cell and "blocks" not in cell:
                # å±å¹³åµå¥ç?cells å¹¶è¿åç¬¬ä¸ä¸ªææ?cell
                # æ³¨æï¼å¶ä½åµå¥ç cells ä¼å¨ _normalize_table_cells ä¸­è¢«å¤ç
                return self._flatten_nested_cell(cell)

            normalized = dict(cell)
            blocks = self._coerce_cell_blocks(normalized.get("blocks"), normalized)
        elif isinstance(cell, list):
            normalized = {}
            blocks = self._coerce_cell_blocks(cell, None)
        elif isinstance(cell, (str, int, float)):
            normalized = {}
            blocks = [self._as_paragraph_block(str(cell))]
        else:
            normalized = {}
            blocks = [self._as_paragraph_block(str(cell))]

        normalized["blocks"] = blocks or [self._as_paragraph_block("")]
        return normalized

    def _flatten_nested_cell(self, cell: Dict[str, Any]) -> Dict[str, Any]:
        """
        å±å¹³éè¯¯åµå¥ç?cell ç»æ

        LLM ææ¶ä¼çæç±»ä¼¼è¿æ ·çéè¯¯ç»æï¼?
        { "cells": [ { "blocks": [...] }, { "cells": [...] } ] }

        åºè¯¥è¿åç¬¬ä¸ä¸ªææç cell åå®¹
        """
        nested_cells = cell.get("cells")
        if not isinstance(nested_cells, list) or not nested_cells:
            # æ²¡æææçåµå¥åå®¹ï¼è¿åç©?cell
            return {"blocks": [self._as_paragraph_block("")]}

        # éå½æ¥æ¾ç¬¬ä¸ä¸ªåå?blocks çææ?cell
        for nested in nested_cells:
            if isinstance(nested, dict):
                if "blocks" in nested:
                    # æ¾å°ææ cellï¼éå½è§èå?
                    return self._normalize_table_cell(nested)
                elif "cells" in nested:
                    # ç»§ç»­éå½å±å¹³
                    result = self._flatten_nested_cell(nested)
                    if result:
                        return result

        # æ²¡ææ¾å°ææåå®¹ï¼å°è¯ä»ç¬¬ä¸ä¸ªåµå¥åç´ æåææ?
        first_nested = nested_cells[0]
        if isinstance(first_nested, dict):
            text = self._extract_block_text(first_nested)
            return {"blocks": [self._as_paragraph_block(text or "")]}

        return {"blocks": [self._as_paragraph_block("")]}

    def _coerce_cell_blocks(
        self, blocks: Any, source: Dict[str, Any] | None
    ) -> List[Dict[str, Any]]:
        """å°cell.blockså­æ®µå¼ºå¶è½¬æ¢ä¸ºåæ³çblockæ°ç»"""
        if isinstance(blocks, list):
            entries = blocks
        elif blocks is None:
            entries = []
        else:
            entries = [blocks]

        normalized_blocks: List[Dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, dict):
                normalized_blocks.append(entry)
            elif isinstance(entry, list):
                normalized_blocks.extend(self._coerce_cell_blocks(entry, None))
            elif isinstance(entry, (str, int, float)):
                normalized_blocks.append(self._as_paragraph_block(str(entry)))
            elif entry is None:
                continue
            else:
                normalized_blocks.append(self._as_paragraph_block(str(entry)))

        if normalized_blocks:
            return normalized_blocks

        text_hint = ""
        if isinstance(source, dict):
            text_hint = self._extract_block_text(source).strip()
        return [self._as_paragraph_block(text_hint or "--")]

    def _build_default_table_cell(self) -> Dict[str, Any]:
        """çæä¸ä¸ªæå°å¯æ¸²æçç©ºç½ååæ ¼"""
        return {"blocks": [self._as_paragraph_block("--")]}

    def _normalize_paragraph_block(self, block: Dict[str, Any]):
        """å°paragraphçinlinesç»ä¸è§æ´ï¼åé¤éæ³marks"""
        inlines = block.get("inlines")
        normalized_runs: List[Dict[str, Any]] = []
        if isinstance(inlines, list) and inlines:
            for run in inlines:
                normalized_runs.extend(self._coerce_inline_run(run))
        else:
            normalized_runs = [self._as_inline_run(self._extract_block_text(block))]
        if not normalized_runs:
            normalized_runs = [self._as_inline_run("")]
        block["inlines"] = self._strip_inline_artifacts(normalized_runs)

    def _strip_inline_artifacts(self, inlines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ç§»é¤è¢«LLMè¯¯åå¥çJSONå¨åµææ¬ï¼é²æ­¢æ¸²æåº`{\"type\": \"\"}`ç­åå¾å­ç¬?""
        cleaned: List[Dict[str, Any]] = []
        for run in inlines or []:
            if not isinstance(run, dict):
                continue
            text = run.get("text")
            if isinstance(text, str):
                stripped = text.strip()
                if stripped.startswith("{") and stripped.endswith("}"):
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError:
                        payload = None
                    if isinstance(payload, dict) and set(payload.keys()).issubset({"type", "value"}):
                        continue
            cleaned.append(run)
        return cleaned or [self._as_inline_run("")]

    def _merge_fragment_sequences(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """åå¹¶è¢«LLMææå¤æ®µçå¥å­çæ®µï¼é¿åHTMLåºç°å¤§éå­¤ç«<p>"""
        if not isinstance(blocks, list):
            return blocks

        merged: List[Dict[str, Any]] = []
        fragment_buffer: List[Dict[str, Any]] = []

        def flush_buffer():
            """å°å½åçæ®µç¼å²åå¥mergedåè¡¨ï¼å¿è¦æ¶åå¹¶ä¸ºåæ®µparagraph"""
            nonlocal fragment_buffer
            if not fragment_buffer:
                return
            if len(fragment_buffer) == 1:
                merged.append(fragment_buffer[0])
            else:
                merged.append(self._combine_paragraph_fragments(fragment_buffer))
            fragment_buffer = []

        for block in blocks:
            # ç±»åæ£æ¥ï¼è·³è¿éå­å¸ç±»åçå¼å¸¸ blockï¼é¿å?AttributeError
            if not isinstance(block, dict):
                # å°è¯å°éå­å¸ç±»åè½¬æ¢ä¸?paragraph
                if isinstance(block, str) and block.strip():
                    converted = self._as_paragraph_block(block)
                    logger.warning(f"æ£æµå°éå­å¸ç±»åç blockï¼å­ç¬¦ä¸²ï¼ï¼å·²è½¬æ¢ä¸º paragraph: {block[:50]}...")
                    merged.append(converted)
                elif isinstance(block, list):
                    # åè¡¨ç±»åç?block å¯è½æ?LLM è¾åºéè¯¯ï¼å°è¯æåææåå®?
                    logger.warning(f"æ£æµå°åè¡¨ç±»åç?blockï¼å°è¯æåææåå®? {block}")
                    for item in block:
                        if isinstance(item, dict):
                            self._ensure_block_type(item)
                            merged.append(self._merge_nested_fragments(item))
                        elif isinstance(item, str) and item.strip():
                            merged.append(self._as_paragraph_block(item))
                else:
                    logger.warning(f"è·³è¿æ æç?blockï¼ç±»å? {type(block).__name__}ï¼? {block}")
                continue
            if self._is_paragraph_fragment(block):
                fragment_buffer.append(block)
                continue
            flush_buffer()
            merged.append(self._merge_nested_fragments(block))

        flush_buffer()
        return merged

    def _merge_nested_fragments(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """å¯¹åµå¥ç»æï¼callout/blockquote/engineQuote/list/tableï¼éå½å¤ççæ®µåå¹¶"""
        # ç±»åæ£æ¥ï¼ç¡®ä¿ block æ¯å­å¸ç±»å?
        if not isinstance(block, dict):
            # å°è¯å°éå­å¸ç±»åè½¬æ¢ä¸?paragraph
            if isinstance(block, str) and block.strip():
                logger.warning(f"_merge_nested_fragments æ¶å°å­ç¬¦ä¸²ç±»åï¼å·²è½¬æ¢ä¸º paragraph")
                return self._as_paragraph_block(block)
            elif isinstance(block, list):
                # å°è¯æååè¡¨ä¸­çç¬¬ä¸ä¸ªææå­å?
                for item in block:
                    if isinstance(item, dict):
                        self._ensure_block_type(item)
                        return self._merge_nested_fragments(item)
                logger.warning(f"_merge_nested_fragments æ¶å°æ æåè¡¨ï¼è¿åç©º paragraph")
                return self._as_paragraph_block("")
            else:
                logger.warning(f"_merge_nested_fragments æ¶å°æ æç±»åï¼{type(block).__name__}ï¼ï¼è¿åç©?paragraph")
                return self._as_paragraph_block("")

        block_type = block.get("type")
        if block_type in {"callout", "blockquote", "engineQuote"}:
            nested = block.get("blocks")
            if isinstance(nested, list):
                block["blocks"] = self._merge_fragment_sequences(nested)
        elif block_type == "list":
            items = block.get("items")
            if isinstance(items, list):
                for entry in items:
                    if isinstance(entry, list):
                        merged_entry = self._merge_fragment_sequences(entry)
                        entry[:] = merged_entry
        elif block_type == "table":
            for row in block.get("rows", []):
                if not isinstance(row, dict):
                    continue
                cells = row.get("cells") or []
                for cell in cells:
                    if not isinstance(cell, dict):
                        continue
                    nested_blocks = cell.get("blocks")
                    if isinstance(nested_blocks, list):
                        cell["blocks"] = self._merge_fragment_sequences(nested_blocks)
        return block

    def _combine_paragraph_fragments(self, fragments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """å°å¤ä¸ªå¥å­çæ®µåå¹¶ä¸ºåä¸ªparagraph block"""
        template = dict(fragments[0])
        combined_inlines: List[Dict[str, Any]] = []
        for fragment in fragments:
            runs = fragment.get("inlines")
            if isinstance(runs, list) and runs:
                combined_inlines.extend(runs)
            else:
                fallback_text = self._extract_block_text(fragment)
                combined_inlines.append(self._as_inline_run(fallback_text))
        if not combined_inlines:
            combined_inlines.append(self._as_inline_run(""))
        template["inlines"] = combined_inlines
        return template

    def _is_paragraph_fragment(self, block: Dict[str, Any]) -> bool:
        """å¤æ­paragraphæ¯å¦ä¸ºè¢«éè¯¯æåçç­çæ®µ"""
        if not isinstance(block, dict) or block.get("type") != "paragraph":
            return False
        inlines = block.get("inlines")
        text = ""
        has_marks = False
        if isinstance(inlines, list) and inlines:
            parts: List[str] = []
            for run in inlines:
                if not isinstance(run, dict):
                    continue
                parts.append(str(run.get("text") or ""))
                marks = run.get("marks")
                if isinstance(marks, list) and any(marks):
                    has_marks = True
            text = "".join(parts)
        else:
            text = self._extract_block_text(block)
        stripped = (text or "").strip()
        if not stripped:
            return True
        if has_marks:
            return False
        if "\n" in stripped:
            return False

        short_limit = self._PARAGRAPH_FRAGMENT_MAX_CHARS
        long_limit = getattr(
            self,
            "_PARAGRAPH_FRAGMENT_NO_TERMINATOR_MAX_CHARS",
            short_limit * 3,
        )

        if stripped[-1] in self._TERMINATION_PUNCTUATION:
            return len(stripped) <= short_limit

        if len(stripped) > long_limit:
            return False
        return True

    def _coerce_inline_run(self, run: Any) -> List[Dict[str, Any]]:
        """å°ä»»æinlineåæ³è§æ´ä¸ºåæ³run"""
        if isinstance(run, dict):
            normalized_run = dict(run)
            text = normalized_run.get("text")
            if not isinstance(text, str):
                text = "" if text is None else str(text)
            marks = normalized_run.get("marks")
            sanitized_marks, extra_text = self._sanitize_inline_marks(marks)
            normalized_run["marks"] = sanitized_marks
            normalized_run["text"] = (text or "") + extra_text
            return [normalized_run]
        if isinstance(run, str):
            return [self._as_inline_run(run)]
        if isinstance(run, (int, float)):
            return [self._as_inline_run(str(run))]
        if isinstance(run, list):
            normalized: List[Dict[str, Any]] = []
            for item in run:
                normalized.extend(self._coerce_inline_run(item))
            return normalized
        return [self._as_inline_run("" if run is None else str(run))]

    def _sanitize_inline_marks(self, marks: Any) -> Tuple[List[Dict[str, Any]], str]:
        """è¿æ»¤éæ³markså¹¶å°breakç±»æ§å¶ç¬¦è½¬æææ¬"""
        text_suffix = ""
        if marks is None:
            return [], text_suffix
        mark_list = marks if isinstance(marks, list) else [marks]
        sanitized: List[Dict[str, Any]] = []
        for mark in mark_list:
            normalized_mark, extra_text = self._normalize_inline_mark(mark)
            if normalized_mark:
                sanitized.append(normalized_mark)
            if extra_text:
                text_suffix += extra_text
        return sanitized, text_suffix

    def _normalize_inline_mark(self, mark: Any) -> Tuple[Dict[str, Any] | None, str]:
        """å¯¹åä¸ªmarkåå¼å®¹æ å°ï¼æèå¨å¿è¦æ¶è½¬æ¢ä¸ºææ¬"""
        if not isinstance(mark, dict):
            return None, ""
        canonical_type = self._canonical_inline_mark_type(mark.get("type"))
        if canonical_type == self._LINE_BREAK_SENTINEL:
            return None, "\n"
        if canonical_type in ALLOWED_INLINE_MARKS:
            normalized = dict(mark)
            normalized["type"] = canonical_type
            return normalized, ""
        return None, ""

    def _canonical_inline_mark_type(self, mark_type: Any) -> str | None:
        """å°mark typeæ å°ä¸ºSchemaææ¯æçåå?""
        if not isinstance(mark_type, str):
            return None
        normalized = mark_type.strip()
        if not normalized:
            return None
        lowered = normalized.lower()
        if lowered in {"break", "linebreak", "br"}:
            return self._LINE_BREAK_SENTINEL
        return self._INLINE_MARK_ALIASES.get(lowered, lowered)

    def _extract_block_text(self, block: Dict[str, Any]) -> str:
        """ä¼åä»text/contentç­å­æ®µæåfallbackææ¬"""
        for key in ("text", "content", "value", "title"):
            value = block.get(key)
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
        return ""

    # åæ³ç?listType å?
    _ALLOWED_LIST_TYPES = {"ordered", "bullet", "task"}
    # listType çå«åæ å°?
    _LIST_TYPE_ALIASES = {
        "unordered": "bullet",
        "ul": "bullet",
        "ol": "ordered",
        "numbered": "ordered",
        "checkbox": "task",
        "check": "task",
        "todo": "task",
    }

    def _normalize_list_type(self, block: Dict[str, Any]):
        """
        ç¡®ä¿ list block ç?listType æ¯åæ³å¼

        å¦æ listType ç¼ºå¤±æéæ³ï¼èªå¨ä¿®å¤ä¸?bullet
        """
        list_type = block.get("listType")
        if list_type in self._ALLOWED_LIST_TYPES:
            return
        # å°è¯å«åæ å°
        if isinstance(list_type, str):
            lowered = list_type.strip().lower()
            if lowered in self._LIST_TYPE_ALIASES:
                block["listType"] = self._LIST_TYPE_ALIASES[lowered]
                logger.warning(f"å·²å° listType '{list_type}' æ å°ä¸?'{block['listType']}'")
                return
            if lowered in self._ALLOWED_LIST_TYPES:
                block["listType"] = lowered
                return
        # æ æ³è¯å«ï¼é»è®¤ä½¿ç?bullet
        logger.warning(f"æ£æµå°éæ³ listType: {list_type}ï¼å·²ä¿®å¤ä¸?bullet")
        block["listType"] = "bullet"

    def _normalize_list_items(self, items: Any) -> List[List[Dict[str, Any]]]:
        """ç¡®ä¿list blockçitemsä¸º[[block, block], ...]ç»æ"""
        if not isinstance(items, list):
            return []
        normalized: List[List[Dict[str, Any]]] = []
        for item in items:
            normalized.extend(self._coerce_list_item(item))
        return [entry for entry in normalized if entry]

    def _coerce_list_item(self, item: Any) -> List[List[Dict[str, Any]]]:
        """å°åç§åµå¥åæ³ç»ä¸æç®ä¸ºåºåæ°ç»?""
        result: List[List[Dict[str, Any]]] = []
        if isinstance(item, dict):
            self._ensure_block_type(item)
            result.append([item])
            return result
        if isinstance(item, list):
            dicts = [elem for elem in item if isinstance(elem, dict)]
            if dicts:
                for elem in dicts:
                    self._ensure_block_type(elem)
                result.append(dicts)
            for elem in item:
                if isinstance(elem, list):
                    result.extend(self._coerce_list_item(elem))
                elif isinstance(elem, dict):
                    continue
                elif isinstance(elem, str):
                    result.append([self._as_paragraph_block(elem)])
                elif isinstance(elem, (int, float)):
                    result.append([self._as_paragraph_block(str(elem))])
        elif isinstance(item, str):
            result.append([self._as_paragraph_block(item)])
        elif isinstance(item, (int, float)):
            result.append([self._as_paragraph_block(str(item))])
        return result

    def _normalize_widget_block(self, block: Dict[str, Any]):
        """ç¡®ä¿widgetå·å¤é¡¶å±dataædataRef"""
        has_data = block.get("data") is not None or block.get("dataRef") is not None
        if has_data:
            return
        props = block.get("props")
        if isinstance(props, dict) and "data" in props:
            block["data"] = props.pop("data")
            return
        block["data"] = {"labels": [], "datasets": []}

    def _ensure_block_type(self, block: Dict[str, Any]):
        """è¥blockç¼ºå°åæ³typeï¼åéçº§ä¸ºparagraph"""
        block_type = block.get("type")
        if isinstance(block_type, str) and block_type in ALLOWED_BLOCK_TYPES:
            return
        text = ""
        for key in ("text", "content", "title"):
            value = block.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
        if not text:
            try:
                text = json.dumps(block, ensure_ascii=False)
            except Exception:
                text = str(block)
        block.clear()
        block["type"] = "paragraph"
        block["inlines"] = [self._as_inline_run(text)]

    @staticmethod
    def _as_paragraph_block(text: str) -> Dict[str, Any]:
        """å°å­ç¬¦ä¸²å¿«éåè£æparagraph blockï¼æ¹ä¾¿ç»ä¸å¤ç"""
        return {
            "type": "paragraph",
            "inlines": [ChapterGenerationNode._as_inline_run(text)],
        }

    @staticmethod
    def _as_inline_run(text: str) -> Dict[str, Any]:
        """æé åºç¡inline runï¼ä¿è¯markså­æ®µå­å¨"""
        return {"text": text or "", "marks": []}

    @staticmethod
    def _parse_with_candidates(payloads: List[str]) -> Dict[str, Any]:
        """æé¡ºåºå°è¯å¤ä¸ªpayloadï¼ç´å°è§£ææå?""
        last_exc: json.JSONDecodeError | None = None
        for payload in payloads:
            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:
                last_exc = exc
        assert last_exc is not None
        raise last_exc


__all__ = [
    "ChapterGenerationNode",
    "ChapterJsonParseError",
    "ChapterContentError",
    "ChapterValidationError",
]
