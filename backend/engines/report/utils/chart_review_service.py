ï»¿"""
å¾è¡¨å®¡æ¥æå¡ - ç»ä¸ç®¡çå¾è¡¨éªè¯åä¿®å¤ï¿½?

æä¾åä¾æå¡ï¼ç¡®ä¿æææ¸²æå¨å±äº«ä¿®å¤ç¶æï¼é¿åéå¤ä¿®å¤ï¿½?
ä¿®å¤æååå¯èªå¨æä¹åå° IR æä»¶ï¿½?

çº¿ç¨å®å¨è¯´æï¿½?
- éªè¯å¨åä¿®å¤å¨å®ä¾æ¯æ ç¶æçï¼å¯å®å¨å±äº«
- æ¯æ¬¡ review_document è°ç¨ä¼åå»ºç¬ç«ç ReviewSession
- ç»è®¡ä¿¡æ¯éè¿ ReviewSession è¿åï¼é¿åå¹¶åç«ï¿½?
"""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.engines.report.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    ValidationResult,
    create_chart_validator,
    create_chart_repairer
)
from backend.engines.report.utils.chart_repair_api import create_llm_repair_functions


@dataclass
class ReviewStats:
    """
    å¾è¡¨å®¡æ¥ç»è®¡ä¿¡æ¯ - æ¯æ¬¡å®¡æ¥ä¼è¯ç¬ç«çç»è®¡æ°æ®ï¿½?

    éè¿ä¸ºæ¯ï¿½?review_document è°ç¨åå»ºç¬ç«ï¿½?ReviewStats å®ä¾ï¿½?
    é¿åå¤çº¿ç¨å¹¶åæ¶çç»è®¡æ°æ®ç«äºé®é¢ï¿½?
    """
    total: int = 0
    valid: int = 0
    repaired_locally: int = 0
    repaired_api: int = 0
    failed: int = 0

    def to_dict(self) -> Dict[str, int]:
        """è½¬æ¢ä¸ºå­å¸æ ¼ï¿½?""
        return {
            'total': self.total,
            'valid': self.valid,
            'repaired_locally': self.repaired_locally,
            'repaired_api': self.repaired_api,
            'failed': self.failed
        }

    @property
    def repaired_total(self) -> int:
        """ä¿®å¤æ»æ°"""
        return self.repaired_locally + self.repaired_api


class ChartReviewService:
    """
    å¾è¡¨å®¡æ¥æå¡ - åä¾æ¨¡å¼ï¿½?

    èè´£ï¿½?
    1. ç»ä¸ç®¡çå¾è¡¨éªè¯åä¿®ï¿½?
    2. ç»´æ¤ä¿®å¤ç¼å­ï¼é¿åéå¤ä¿®ï¿½?
    3. æ¯æä¿®å¤åèªå¨æä¹åï¿½?IR æä»¶
    4. æä¾ç»è®¡ä¿¡æ¯ï¼éè¿ ReviewStats è¿åï¼çº¿ç¨å®å¨ï¼

    çº¿ç¨å®å¨è¯´æï¿½?
    - validator ï¿½?repairer æ¯æ ç¶æçï¼å¯å®å¨å±äº«
    - æ¯æ¬¡ review_document è°ç¨åå»ºç¬ç«ï¿½?ReviewStats
    - ä¸åä½¿ç¨å¨å± _statsï¼é¿åå¹¶åç«ï¿½?
    """

    _instance: Optional["ChartReviewService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ChartReviewService":
        """åä¾æ¨¡å¼"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """åå§åæå¡ï¼ä»é¦æ¬¡è°ç¨æ¶æ§è¡ï¿½?""
        if self._initialized:
            return

        self._initialized = True

        # åå§åéªè¯å¨åä¿®å¤å¨ï¼æ ç¶æï¼å¯å®å¨å±äº«ï¼
        self.validator = create_chart_validator()
        self.llm_repair_fns = create_llm_repair_functions()
        self.repairer = create_chart_repairer(
            validator=self.validator,
            llm_repair_fns=self.llm_repair_fns
        )

        # æå° LLM ä¿®å¤å½æ°ç¶ï¿½?
        if not self.llm_repair_fns:
            logger.warning("ChartReviewService: æªéç½®ä»»ï¿½?LLM APIï¼å¾ï¿½?API ä¿®å¤åè½ä¸å¯ï¿½?)
        else:
            logger.info(f"ChartReviewService: å·²éï¿½?{len(self.llm_repair_fns)} ï¿½?LLM ä¿®å¤å½æ°")

        # æåä¸æ¬¡å®¡æ¥çç»è®¡ä¿¡æ¯ï¼ä»ç¨äºååå¼å®¹ï¼ä¸æ¨èå¨å¹¶ååºæ¯ä½¿ç¨ï¼
        # æ°ä»£ç åºä½¿ç¨ review_document è¿åï¿½?ReviewStats
        self._last_stats: Optional[ReviewStats] = None
        self._last_stats_lock = threading.Lock()

        logger.info("ChartReviewService åå§åå®ï¿½?)

    def reset_stats(self) -> None:
        """
        éç½®ç»è®¡ä¿¡æ¯ï¼ååå¼å®¹ï¼ä¸æ¨èä½¿ç¨ï¼ï¿½?

        æ³¨æï¼æ­¤æ¹æ³ä»ç¨äºååå¼å®¹ãå¨å¹¶ååºæ¯ä¸ï¼
        åºä½¿ï¿½?review_document è¿åï¿½?ReviewStats å¯¹è±¡ï¿½?
        """
        with self._last_stats_lock:
            self._last_stats = None

    @property
    def stats(self) -> Dict[str, int]:
        """
        è·åæåä¸æ¬¡å®¡æ¥çç»è®¡ä¿¡æ¯å¯æ¬ï¼ååå¼å®¹ï¼ï¿½?

        è­¦åï¼å¨å¹¶ååºæ¯ä¸ï¼æ­¤å±æ§å¯è½è¿åå¶ä»çº¿ç¨çç»è®¡ç»æï¿½?
        æ¨èä½¿ç¨ review_document è¿åï¿½?ReviewStats å¯¹è±¡ï¿½?

        è¿å:
            Dict[str, int]: ç»è®¡ä¿¡æ¯å­å¸å¯æ¬
        """
        with self._last_stats_lock:
            if self._last_stats is None:
                return {
                    'total': 0,
                    'valid': 0,
                    'repaired_locally': 0,
                    'repaired_api': 0,
                    'failed': 0
                }
            return self._last_stats.to_dict()

    def review_document(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: Optional[str | Path] = None,
        *,
        reset_stats: bool = True,
        save_on_repair: bool = True
    ) -> ReviewStats:
        """
        å®¡æ¥å¹¶ä¿®å¤ææ¡£ä¸­çææå¾è¡¨ï¿½?

        éåææç« èç blocksï¼æ£æµå¾è¡¨ç±»åç widgetï¿½?
        å¯¹æªå®¡æ¥è¿çå¾è¡¨è¿è¡éªè¯åä¿®å¤ï¿½?

        çº¿ç¨å®å¨ï¼æ¯æ¬¡è°ç¨åå»ºç¬ç«ç ReviewStatsï¼é¿åå¹¶åç«äºï¿½?

        åæ°:
            document_ir: Document IR æ°æ®
            ir_file_path: IR æä»¶è·¯å¾ï¼å¦ææä¾ä¸æä¿®å¤ï¼ä¼èªå¨ä¿ï¿½?
            reset_stats: ä¿çåæ°ä»¥ä¿æååå¼å®¹ï¼ä¸åæå®éä½ï¿½?
            save_on_repair: ä¿®å¤åæ¯å¦èªå¨ä¿å­å°æä»¶

        è¿å:
            ReviewStats: æ¬æ¬¡å®¡æ¥çç»è®¡ä¿¡æ¯ï¼çº¿ç¨å®å¨ï¿½?
        """
        # æ¯æ¬¡è°ç¨åå»ºç¬ç«çç»è®¡å¯¹è±¡ï¼é¿åå¹¶åç«äº
        session_stats = ReviewStats()

        if not document_ir:
            logger.warning("ChartReviewService: document_ir ä¸ºç©ºï¼è·³è¿å®¡ï¿½?)
            # æ´æ° _last_stats ä»¥ä¿æååå¼ï¿½?
            with self._last_stats_lock:
                self._last_stats = session_stats
            return session_stats

        has_repairs = False

        # éåææç« ï¿½?
        for chapter in document_ir.get("chapters", []) or []:
            if not isinstance(chapter, dict):
                continue
            blocks = chapter.get("blocks", [])
            if isinstance(blocks, list):
                chapter_repairs = self._walk_and_review_blocks(blocks, chapter, session_stats)
                if chapter_repairs:
                    has_repairs = True

        # è¾åºç»è®¡ä¿¡æ¯
        self._log_stats(session_stats)

        # æ´æ° _last_stats ä»¥ä¿æååå¼ï¿½?
        with self._last_stats_lock:
            self._last_stats = session_stats

        # å¦ææä¿®å¤ä¸æä¾äºæä»¶è·¯å¾ï¼ä¿å­å°æï¿½?
        if has_repairs and ir_file_path and save_on_repair:
            self._save_ir_to_file(document_ir, ir_file_path)

        return session_stats

    def _walk_and_review_blocks(
        self,
        blocks: List[Any],
        chapter_context: Dict[str, Any] | None,
        session_stats: ReviewStats
    ) -> bool:
        """
        éå½éå blocks å¹¶å®¡æ¥å¾è¡¨ï¿½?

        åæ°:
            blocks: è¦éåç block åè¡¨
            chapter_context: ç« èä¸ä¸ï¿½?
            session_stats: æ¬æ¬¡å®¡æ¥ä¼è¯çç»è®¡å¯¹ï¿½?

        è¿å:
            bool: æ¯å¦æä¿®å¤åï¿½?
        """
        has_repairs = False

        for block in blocks or []:
            if not isinstance(block, dict):
                continue

            # æ£æ¥æ¯å¦æ¯å¾è¡¨ widget
            if block.get("type") == "widget":
                repaired = self._review_chart_block(block, chapter_context, session_stats)
                if repaired:
                    has_repairs = True

            # éå½å¤çåµå¥ï¿½?blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                if self._walk_and_review_blocks(nested_blocks, chapter_context, session_stats):
                    has_repairs = True

            # å¤ç list ç±»åï¿½?items
            if block.get("type") == "list":
                for item in block.get("items", []):
                    if isinstance(item, list):
                        if self._walk_and_review_blocks(item, chapter_context, session_stats):
                            has_repairs = True

            # å¤ç table ç±»åï¿½?cells
            if block.get("type") == "table":
                for row in block.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    for cell in row.get("cells", []):
                        if isinstance(cell, dict):
                            cell_blocks = cell.get("blocks", [])
                            if isinstance(cell_blocks, list):
                                if self._walk_and_review_blocks(cell_blocks, chapter_context, session_stats):
                                    has_repairs = True

        return has_repairs

    def _review_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None,
        session_stats: ReviewStats
    ) -> bool:
        """
        å®¡æ¥åä¸ªå¾è¡¨ blockï¿½?

        åæ°:
            block: è¦å®¡æ¥ç block
            chapter_context: ç« èä¸ä¸ï¿½?
            session_stats: æ¬æ¬¡å®¡æ¥ä¼è¯çç»è®¡å¯¹ï¿½?

        è¿å:
            bool: æ¯å¦è¿è¡äºä¿®ï¿½?
        """
        widget_type = block.get("widgetType", "")
        if not isinstance(widget_type, str):
            return False

        # åªå¤ï¿½?chart.js ç±»åï¼è¯äºåç¬å¤çï¼ä¸éè¦ä¿®å¤ï¼
        is_chart = widget_type.startswith("chart.js")
        is_wordcloud = "wordcloud" in widget_type.lower()

        if not is_chart:
            return False

        widget_id = block.get("widgetId", "unknown")

        # æ£æ¥æ¯å¦å·²å®¡æ¥ï¿½?
        if block.get("_chart_reviewed"):
            logger.debug(f"å¾è¡¨ {widget_id} å·²å®¡æ¥è¿ï¼è·³ï¿½?)
            return False

        session_stats.total += 1

        # è¯äºç´æ¥æ è®°ä¸ºæï¿½?
        if is_wordcloud:
            session_stats.valid += 1
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "valid"
            block["_chart_review_method"] = "none"
            return False

        # åè¿è¡æ°æ®è§èåï¼ä»ç« èä¸ä¸æè¡¥åæ°æ®ï¼
        self._normalize_chart_block(block, chapter_context)

        # éªè¯å¾è¡¨
        validation_result = self.validator.validate(block)

        if validation_result.is_valid:
            # éªè¯éè¿
            session_stats.valid += 1
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "valid"
            block["_chart_review_method"] = "none"
            if validation_result.warnings:
                logger.debug(f"å¾è¡¨ {widget_id} éªè¯éè¿ï¼ä½æè­¦ï¿½? {validation_result.warnings}")
            return False

        # éªè¯å¤±è´¥ï¼å°è¯ä¿®ï¿½?
        logger.warning(f"å¾è¡¨ {widget_id} éªè¯å¤±è´¥: {validation_result.errors}")

        repair_result = self.repairer.repair(block, validation_result)

        if repair_result.success and repair_result.repaired_block:
            # ä¿®å¤æåï¼è¦çåï¿½?block æ°æ®
            repaired_block = repair_result.repaired_block
            # ä¿çåå§çä¸äºåä¿¡æ¯
            original_widget_id = block.get("widgetId")
            block.clear()
            block.update(repaired_block)
            # ç¡®ä¿ widgetId ä¸ä¸¢ï¿½?
            if original_widget_id and not block.get("widgetId"):
                block["widgetId"] = original_widget_id

            method = repair_result.method or "local"
            if method == "local":
                session_stats.repaired_locally += 1
            elif method == "api":
                session_stats.repaired_api += 1

            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "repaired"
            block["_chart_review_method"] = method

            logger.info(f"å¾è¡¨ {widget_id} ä¿®å¤æå (æ¹æ³: {method}): {repair_result.changes}")
            return True

        # ä¿®å¤å¤±è´¥
        session_stats.failed += 1
        block["_chart_reviewed"] = True
        block["_chart_renderable"] = False
        block["_chart_review_status"] = "failed"
        block["_chart_review_method"] = "none"
        block["_chart_error_reason"] = self._format_error_reason(validation_result)

        logger.warning(f"å¾è¡¨ {widget_id} ä¿®å¤å¤±è´¥ï¼å·²æ è®°ä¸ºä¸å¯æ¸²ï¿½?)
        return False

    def _normalize_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None = None
    ) -> None:
        """
        è§èåå¾è¡¨æ°æ®ï¼è¡¥å¨ç¼ºå¤±å­æ®µï¼å¦propscalesatasetsï¼ï¼æåå®¹éæ§ï¿½?

        ï¿½?HTMLRenderer._normalize_chart_block() ä¿æä¸è´ï¼
        - ç¡®ä¿ props å­å¨
        - å°é¡¶ï¿½?scales åå¹¶ï¿½?props.options
        - ç¡®ä¿ data å­å¨
        - å°è¯ä½¿ç¨ç« èï¿½?data ä½ä¸ºååº
        - èªå¨çæ labels
        """
        if not isinstance(block, dict):
            return

        if block.get("type") != "widget":
            return

        widget_type = block.get("widgetType", "")
        if not (isinstance(widget_type, str) and widget_type.startswith("chart.js")):
            return

        # ç¡®ä¿ props å­å¨
        props = block.get("props")
        if not isinstance(props, dict):
            block["props"] = {}
            props = block["props"]

        # å°é¡¶ï¿½?scales åå¹¶ï¿½?optionsï¼é¿åéç½®ä¸¢ï¿½?
        scales = block.get("scales")
        if isinstance(scales, dict):
            options = props.get("options") if isinstance(props.get("options"), dict) else {}
            props["options"] = self._merge_dicts(options, {"scales": scales})

        # ç¡®ä¿ data å­å¨
        data = block.get("data")
        if not isinstance(data, dict):
            data = {}
            block["data"] = data

        # å¦æ datasets ä¸ºç©ºï¼å°è¯ä½¿ç¨ç« èçº§ data å¡«å
        if chapter_context and self._is_chart_data_empty(data):
            chapter_data = chapter_context.get("data") if isinstance(chapter_context, dict) else None
            if isinstance(chapter_data, dict):
                fallback_ds = chapter_data.get("datasets")
                if isinstance(fallback_ds, list) and len(fallback_ds) > 0:
                    merged_data = copy.deepcopy(data)
                    merged_data["datasets"] = copy.deepcopy(fallback_ds)

                    if not merged_data.get("labels") and isinstance(chapter_data.get("labels"), list):
                        merged_data["labels"] = copy.deepcopy(chapter_data["labels"])

                    block["data"] = merged_data

        # è¥ä»ç¼ºå° labels ä¸æ°æ®ç¹åå« x å¼ï¼èªå¨çæä¾¿äº fallback ååæ å»ï¿½?
        data_ref = block.get("data")
        if isinstance(data_ref, dict) and not data_ref.get("labels"):
            datasets_ref = data_ref.get("datasets")
            if isinstance(datasets_ref, list) and datasets_ref:
                first_ds = datasets_ref[0]
                ds_data = first_ds.get("data") if isinstance(first_ds, dict) else None
                if isinstance(ds_data, list):
                    labels_from_data = []
                    for idx, point in enumerate(ds_data):
                        if isinstance(point, dict):
                            label_text = point.get("x") or point.get("label") or f"ç¹{idx + 1}"
                        else:
                            label_text = f"ç¹{idx + 1}"
                        labels_from_data.append(str(label_text))

                    if labels_from_data:
                        data_ref["labels"] = labels_from_data

    @staticmethod
    def _is_chart_data_empty(data: Dict[str, Any] | None) -> bool:
        """æ£æ¥å¾è¡¨æ°æ®æ¯å¦ä¸ºç©ºæç¼ºå°ææ datasets"""
        if not isinstance(data, dict):
            return True

        datasets = data.get("datasets")
        if not isinstance(datasets, list) or len(datasets) == 0:
            return True

        for ds in datasets:
            if not isinstance(ds, dict):
                continue
            series = ds.get("data")
            if isinstance(series, list) and len(series) > 0:
                return False

        return True

    @staticmethod
    def _merge_dicts(
        base: Dict[str, Any] | None, override: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        éå½åå¹¶ä¸¤ä¸ªå­å¸ï¼override è¦ç baseï¼åä¸ºæ°å¯æ¬ï¼é¿åå¯ä½ç¨ï¿½?
        """
        result = copy.deepcopy(base) if isinstance(base, dict) else {}
        if not isinstance(override, dict):
            return result
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ChartReviewService._merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _format_error_reason(self, validation_result: ValidationResult | None) -> str:
        """æ ¼å¼åéè¯¯åï¿½?""
        if not validation_result:
            return "æªç¥éè¯¯"
        errors = validation_result.errors or []
        if not errors:
            return "éªè¯å¤±è´¥ä½æ å·ä½éè¯¯ä¿¡æ¯"
        return "; ".join(errors[:3])

    def _log_stats(self, stats: ReviewStats) -> None:
        """è¾åºç»è®¡ä¿¡æ¯"""
        if stats.total == 0:
            logger.debug("ChartReviewService: æ²¡æå¾è¡¨éè¦å®¡ï¿½?)
            return

        logger.info(
            f"ChartReviewService å¾è¡¨å®¡æ¥å®æ: "
            f"æ»è®¡ {stats.total} ï¿½? "
            f"ææ {stats.valid} ï¿½? "
            f"ä¿®å¤ {stats.repaired_total} ï¿½?(æ¬å° {stats.repaired_locally}, API {stats.repaired_api}), "
            f"å¤±è´¥ {stats.failed} ï¿½?
        )

    # åé¨åæ°æ®é®ï¼ä¸åºä¿å­å° IR æä»¶
    _INTERNAL_METADATA_KEYS = frozenset([
        "_chart_reviewed",
        "_chart_renderable",
        "_chart_review_status",
        "_chart_review_method",
        "_chart_error_reason",
    ])

    def _strip_internal_metadata(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        ç§»é¤ææ¡£ä¸­ææåé¨åæ°æ®é®ï¼è¿åå¹²åçå¯æ¬ç¨äºæä¹åï¿½?

        è¿äºåé¨æ è®°ä»ç¨äºæ¸²æè¿ç¨çç¶æè·è¸ªï¼ä¸åºä¿å­ï¿½?IR æä»¶ä¸­ï¼
        ä»¥é¿åæ±¡æææ¡£ç»æåå¯¼è´éå¤ä½¿ç¨æ¶çä¸ä¸è´è¡ä¸ºï¿½?
        """
        cleaned = copy.deepcopy(document_ir)

        def strip_from_block(block: Dict[str, Any]) -> None:
            """éå½ç§»é¤ block åå¶åµå¥ç»æä¸­çåé¨åæ°ï¿½?""
            if not isinstance(block, dict):
                return

            # ç§»é¤å½å block çåé¨é®
            for key in self._INTERNAL_METADATA_KEYS:
                block.pop(key, None)

            # éå½å¤çåµå¥ï¿½?blocks
            nested_blocks = block.get("blocks")
            if isinstance(nested_blocks, list):
                for nested in nested_blocks:
                    strip_from_block(nested)

            # å¤ç list ç±»åï¿½?items
            if block.get("type") == "list":
                for item in block.get("items", []):
                    if isinstance(item, list):
                        for sub_block in item:
                            strip_from_block(sub_block)

            # å¤ç table ç±»åï¿½?cells
            if block.get("type") == "table":
                for row in block.get("rows", []):
                    if not isinstance(row, dict):
                        continue
                    for cell in row.get("cells", []):
                        if isinstance(cell, dict):
                            cell_blocks = cell.get("blocks", [])
                            if isinstance(cell_blocks, list):
                                for cell_block in cell_blocks:
                                    strip_from_block(cell_block)

        # å¤çææç« ï¿½?
        for chapter in cleaned.get("chapters", []) or []:
            if not isinstance(chapter, dict):
                continue
            blocks = chapter.get("blocks", [])
            if isinstance(blocks, list):
                for block in blocks:
                    strip_from_block(block)

        return cleaned

    def _save_ir_to_file(self, document_ir: Dict[str, Any], file_path: str | Path) -> None:
        """ä¿å­ IR å°æä»¶ï¼ç§»é¤åé¨åæ°æ®åï¿½?""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            # ç§»é¤åé¨åæ°æ®é®ï¼ä¿ï¿½?IR æä»¶å¹²å
            cleaned_ir = self._strip_internal_metadata(document_ir)

            path.write_text(
                json.dumps(cleaned_ir, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            logger.info(f"ChartReviewService: ä¿®å¤åç IR å·²ä¿å­å° {path}")
        except Exception as e:
            logger.exception(f"ChartReviewService: ä¿å­ IR æä»¶å¤±è´¥: {e}")


# å¨å±åä¾å®ä¾
_chart_review_service: Optional[ChartReviewService] = None


def get_chart_review_service() -> ChartReviewService:
    """è·å ChartReviewService åä¾å®ä¾"""
    global _chart_review_service
    if _chart_review_service is None:
        _chart_review_service = ChartReviewService()
    return _chart_review_service


def review_document_charts(
    document_ir: Dict[str, Any],
    ir_file_path: Optional[str | Path] = None,
    *,
    reset_stats: bool = True,
    save_on_repair: bool = True
) -> ReviewStats:
    """
    ä¾¿æ·å½æ°ï¼å®¡æ¥å¹¶ä¿®å¤ææ¡£ä¸­çææå¾è¡¨ï¿½?

    åæ°:
        document_ir: Document IR æ°æ®
        ir_file_path: IR æä»¶è·¯å¾ï¼å¦ææä¾ä¸æä¿®å¤ï¼ä¼èªå¨ä¿ï¿½?
        reset_stats: ä¿çåæ°ä»¥ä¿æååå¼å®¹ï¼ä¸åæå®éä½ï¿½?
        save_on_repair: ä¿®å¤åæ¯å¦èªå¨ä¿å­å°æä»¶

    è¿å:
        ReviewStats: æ¬æ¬¡å®¡æ¥çç»è®¡ä¿¡ï¿½?
    """
    service = get_chart_review_service()
    return service.review_document(
        document_ir,
        ir_file_path,
        reset_stats=reset_stats,
        save_on_repair=save_on_repair
    )


__all__ = [
    "ChartReviewService",
    "ReviewStats",
    "get_chart_review_service",
    "review_document_charts",
]

