"""
å¾è¡¨éªè¯åä¿®å¤å·¥å·

æä¾å¯¹Chart.jså¾è¡¨æ°æ®çéªè¯åä¿®å¤è½åï¼?
1. éªè¯å¾è¡¨æ°æ®æ ¼å¼æ¯å¦ç¬¦åChart.jsè¦æ±
2. æ¬å°è§åä¿®å¤å¸¸è§é®é¢
3. LLM APIè¾å©ä¿®å¤å¤æé®é¢
4. éµå¾ª"å®æ¿ä¸æ¹ï¼ä¹ä¸è¦æ¹é"çåå?

æ¯æçå¾è¡¨ç±»åï¼
- line (æçº¿å?
- bar (æ±ç¶å?
- pie (é¥¼å¾)
- doughnut (åç¯å?
- radar (é·è¾¾å?
- polararea (æå°åºåå?
- scatter (æ£ç¹å?
- bubble (æ°æ³¡å?
- horizontalbar (æ¨ªåæ±ç¶å?
"""

from __future__ import annotations

import copy
import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from loguru import logger


@dataclass
class ValidationResult:
    """éªè¯ç»æ"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]

    def has_critical_errors(self) -> bool:
        """æ¯å¦æä¸¥ééè¯¯ï¼ä¼å¯¼è´æ¸²æå¤±è´¥ï¼"""
        return not self.is_valid and len(self.errors) > 0


@dataclass
class RepairResult:
    """ä¿®å¤ç»æ"""
    success: bool
    repaired_block: Optional[Dict[str, Any]]
    method: str  # 'none', 'local', 'api'
    changes: List[str]

    def has_changes(self) -> bool:
        """æ¯å¦æä¿®æ?""
        return len(self.changes) > 0


class ChartValidator:
    """
    å¾è¡¨éªè¯å?- éªè¯Chart.jså¾è¡¨æ°æ®æ ¼å¼æ¯å¦æ­£ç¡®

    éªè¯è§åï¼?
    1. åºæ¬ç»æéªè¯ï¼widgetType, props, dataå­æ®µ
    2. å¾è¡¨ç±»åéªè¯ï¼æ¯æçå¾è¡¨ç±»å
    3. æ°æ®æ ¼å¼éªè¯ï¼labelsådatasetsç»æ
    4. æ°æ®ä¸è´æ§éªè¯ï¼labelsådatasetsé¿åº¦å¹é
    5. æ°å¼ç±»åéªè¯ï¼æ°æ®å¼ç±»åæ­£ç¡?
    """

    # æ¯æçå¾è¡¨ç±»å?
    SUPPORTED_CHART_TYPES = {
        'line', 'bar', 'pie', 'doughnut', 'radar', 'polararea', 'scatter',
        'bubble', 'horizontalbar'
    }

    # éè¦labelsçå¾è¡¨ç±»å?
    LABEL_REQUIRED_TYPES = {
        'line', 'bar', 'radar', 'polararea', 'pie', 'doughnut'
    }

    # éè¦æ°å¼æ°æ®çå¾è¡¨ç±»å
    NUMERIC_DATA_TYPES = {
        'line', 'bar', 'radar', 'polararea', 'pie', 'doughnut'
    }

    # éè¦ç¹æ®æ°æ®æ ¼å¼çå¾è¡¨ç±»å
    SPECIAL_DATA_TYPES = {
        'scatter': {'x', 'y'},
        'bubble': {'x', 'y', 'r'}
    }

    def __init__(self):
        """åå§åéªè¯å¨å¹¶é¢çç¼å­ç»æï¼ä¾¿äºåç»­å¤ç¨éªè¯/ä¿®å¤ç»æ"""

    def validate(self, widget_block: Dict[str, Any]) -> ValidationResult:
        """
        éªè¯å¾è¡¨æ ¼å¼

        Args:
            widget_block: widgetç±»åçblockï¼åå«widgetId/widgetType/props/data

        Returns:
            ValidationResult: éªè¯ç»æ
        """
        errors = []
        warnings = []

        # 1. åºæ¬ç»æéªè¯
        if not isinstance(widget_block, dict):
            errors.append("widget_blockå¿é¡»æ¯å­å¸ç±»å?)
            return ValidationResult(False, errors, warnings)

        # 2. æ£æ¥widgetType
        widget_type = widget_block.get('widgetType', '')
        if not widget_type or not isinstance(widget_type, str):
            errors.append("ç¼ºå°widgetTypeå­æ®µæç±»åä¸æ­£ç¡®")
            return ValidationResult(False, errors, warnings)

        # æ£æ¥æ¯å¦æ¯chart.jsç±»å
        if not widget_type.startswith('chart.js'):
            # ä¸æ¯å¾è¡¨ç±»åï¼è·³è¿éªè¯?
            return ValidationResult(True, errors, warnings)

        # 3. æåå¾è¡¨ç±»å
        chart_type = self._extract_chart_type(widget_block)
        if not chart_type:
            errors.append("æ æ³ç¡®å®å¾è¡¨ç±»å")
            return ValidationResult(False, errors, warnings)

        # 4. æ£æ¥æ¯å¦æ¯æè¯¥å¾è¡¨ç±»å
        if chart_type not in self.SUPPORTED_CHART_TYPES:
            warnings.append(f"å¾è¡¨ç±»å '{chart_type}' å¯è½ä¸è¢«æ¯æï¼å°å°è¯éçº§æ¸²æ")

        # 5. éªè¯æ°æ®ç»æ
        data = widget_block.get('data')
        if not isinstance(data, dict):
            errors.append("dataå­æ®µå¿é¡»æ¯å­å¸ç±»å?)
            return ValidationResult(False, errors, warnings)

        # æ£æµæ¯å¦ä½¿ç¨äº{x, y}å½¢å¼çæ°æ®ç¹ï¼éå¸¸ç¨äºæ¶é´è½?æ£ç¹ï¼?
        def contains_object_points(ds_list: List[Any] | None) -> bool:
            """æ£æ¥æ°æ®éä¸­æ¯å¦åå«ä»¥x/yé®è¡¨ç¤ºçå¯¹è±¡ç¹ï¼ç¨äºåæ¢éªè¯åæ¯"""
            if not isinstance(ds_list, list):
                return False
            for point in ds_list:
                if isinstance(point, dict) and any(key in point for key in ('x', 'y', 't')):
                    return True
            return False

        datasets_for_detection = data.get('datasets') or []
        uses_object_points = any(
            isinstance(ds, dict) and contains_object_points(ds.get('data'))
            for ds in datasets_for_detection
        )

        # 6. æ ¹æ®å¾è¡¨ç±»åéªè¯æ°æ®
        if chart_type in self.SPECIAL_DATA_TYPES:
            # ç¹æ®æ°æ®æ ¼å¼ï¼scatter, bubbleï¼?
            self._validate_special_data(data, chart_type, errors, warnings)
        else:
            # æ åæ°æ®æ ¼å¼ï¼labels + datasetsï¼?
            self._validate_standard_data(data, chart_type, errors, warnings, uses_object_points)

        # 7. éªè¯props
        props = widget_block.get('props')
        if props is not None and not isinstance(props, dict):
            warnings.append("propså­æ®µåºè¯¥æ¯å­å¸ç±»å?)

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings)

    def _extract_chart_type(self, widget_block: Dict[str, Any]) -> Optional[str]:
        """
        æåå¾è¡¨ç±»å

        ä¼åçº§ï¼
        1. props.type
        2. widgetTypeä¸­çç±»åï¼chart.js/bar -> barï¼?
        3. data.type
        """
        # 1. ä»propsä¸­è·å?
        props = widget_block.get('props') or {}
        if isinstance(props, dict):
            chart_type = props.get('type')
            if chart_type and isinstance(chart_type, str):
                return chart_type.lower()

        # 2. ä»widgetTypeä¸­æå?
        widget_type = widget_block.get('widgetType', '')
        if '/' in widget_type:
            chart_type = widget_type.split('/')[-1]
            if chart_type:
                return chart_type.lower()

        # 3. ä»dataä¸­è·å?
        data = widget_block.get('data') or {}
        if isinstance(data, dict):
            chart_type = data.get('type')
            if chart_type and isinstance(chart_type, str):
                return chart_type.lower()

        return None

    def _validate_standard_data(
        self,
        data: Dict[str, Any],
        chart_type: str,
        errors: List[str],
        warnings: List[str],
        uses_object_points: bool = False
    ):
        """éªè¯æ åæ°æ®æ ¼å¼ï¼labels + datasetsï¼?""
        labels = data.get('labels')
        datasets = data.get('datasets')

        # éªè¯labels
        if chart_type in self.LABEL_REQUIRED_TYPES:
            if not labels:
                if uses_object_points:
                    warnings.append(
                        f"{chart_type}ç±»åå¾è¡¨ç¼ºå°labelsï¼å·²æ ¹æ®æ°æ®ç¹æ¸²æï¼ä½¿ç¨xå¼ï¼"
                    )
                else:
                    errors.append(f"{chart_type}ç±»åå¾è¡¨å¿é¡»åå«labelså­æ®µ")
            elif not isinstance(labels, list):
                errors.append("labelså¿é¡»æ¯æ°ç»ç±»å?)
            elif len(labels) == 0:
                warnings.append("labelsæ°ç»ä¸ºç©ºï¼å¾è¡¨å¯è½æ æ³æ­£å¸¸æ¾ç¤?)

        # éªè¯datasets
        if datasets is None:
            errors.append("ç¼ºå°datasetså­æ®µ")
            return

        if not isinstance(datasets, list):
            errors.append("datasetså¿é¡»æ¯æ°ç»ç±»å?)
            return

        if len(datasets) == 0:
            errors.append("datasetsæ°ç»ä¸ºç©º")
            return

        # éªè¯æ¯ä¸ªdataset
        for idx, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                errors.append(f"datasets[{idx}]å¿é¡»æ¯å¯¹è±¡ç±»å?)
                continue

            # éªè¯dataå­æ®µ
            ds_data = dataset.get('data')
            if ds_data is None:
                errors.append(f"datasets[{idx}]ç¼ºå°dataå­æ®µ")
                continue

            if not isinstance(ds_data, list):
                errors.append(f"datasets[{idx}].dataå¿é¡»æ¯æ°ç»ç±»å?)
                continue

            if len(ds_data) == 0:
                warnings.append(f"datasets[{idx}].dataæ°ç»ä¸ºç©º")
                continue

            # å¦ææ¯{x, y}å¯¹è±¡å½¢å¼çæ°æ®ç¹ï¼é»è®¤åè®¸è·³è¿labelsé¿åº¦åæ°å¼æ ¡éª?
            object_points = any(
                isinstance(value, dict) and any(key in value for key in ('x', 'y', 't'))
                for value in ds_data
            )

            # éªè¯æ°æ®é¿åº¦ä¸è´æ?
            if labels and isinstance(labels, list) and not object_points:
                if len(ds_data) != len(labels):
                    warnings.append(
                        f"datasets[{idx}].dataé¿åº¦({len(ds_data)})ä¸labelsé¿åº¦({len(labels)})ä¸å¹é?
                    )

            # éªè¯æ°å¼ç±»å?
            if chart_type in self.NUMERIC_DATA_TYPES and not object_points:
                for data_idx, value in enumerate(ds_data):
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append(
                            f"datasets[{idx}].data[{data_idx}]çå?{value}'ä¸æ¯ææçæ°å¼ç±»å?
                        )
                        break  # åªæ¥åç¬¬ä¸ä¸ªéè¯?

    def _validate_special_data(
        self,
        data: Dict[str, Any],
        chart_type: str,
        errors: List[str],
        warnings: List[str]
    ):
        """éªè¯ç¹æ®æ°æ®æ ¼å¼ï¼scatter, bubbleï¼?""
        datasets = data.get('datasets')

        if not datasets:
            errors.append("ç¼ºå°datasetså­æ®µ")
            return

        if not isinstance(datasets, list):
            errors.append("datasetså¿é¡»æ¯æ°ç»ç±»å?)
            return

        if len(datasets) == 0:
            errors.append("datasetsæ°ç»ä¸ºç©º")
            return

        required_keys = self.SPECIAL_DATA_TYPES.get(chart_type, set())

        # éªè¯æ¯ä¸ªdataset
        for idx, dataset in enumerate(datasets):
            if not isinstance(dataset, dict):
                errors.append(f"datasets[{idx}]å¿é¡»æ¯å¯¹è±¡ç±»å?)
                continue

            ds_data = dataset.get('data')
            if ds_data is None:
                errors.append(f"datasets[{idx}]ç¼ºå°dataå­æ®µ")
                continue

            if not isinstance(ds_data, list):
                errors.append(f"datasets[{idx}].dataå¿é¡»æ¯æ°ç»ç±»å?)
                continue

            if len(ds_data) == 0:
                warnings.append(f"datasets[{idx}].dataæ°ç»ä¸ºç©º")
                continue

            # éªè¯æ°æ®ç¹æ ¼å¼?
            for data_idx, point in enumerate(ds_data):
                if not isinstance(point, dict):
                    errors.append(
                        f"datasets[{idx}].data[{data_idx}]å¿é¡»æ¯å¯¹è±¡ç±»åï¼åå«{required_keys}å­æ®µï¼?
                    )
                    break

                # æ£æ¥å¿éçé®
                missing_keys = required_keys - set(point.keys())
                if missing_keys:
                    errors.append(
                        f"datasets[{idx}].data[{data_idx}]ç¼ºå°å¿éå­æ®µ: {missing_keys}"
                    )
                    break

                # éªè¯æ°å¼ç±»å?
                for key in required_keys:
                    value = point.get(key)
                    if value is not None and not isinstance(value, (int, float)):
                        errors.append(
                            f"datasets[{idx}].data[{data_idx}].{key}çå?{value}'ä¸æ¯ææçæ°å¼ç±»å?
                        )
                        break

    def can_render(self, widget_block: Dict[str, Any]) -> bool:
        """
        å¤æ­å¾è¡¨æ¯å¦è½æ­£å¸¸æ¸²æï¼å¿«éæ£æ¥ï¼

        Args:
            widget_block: widgetç±»åçblock

        Returns:
            bool: æ¯å¦è½æ­£å¸¸æ¸²æ?
        """
        result = self.validate(widget_block)
        return result.is_valid


class ChartRepairer:
    """
    å¾è¡¨ä¿®å¤å?- å°è¯ä¿®å¤å¾è¡¨æ°æ®

    ä¿®å¤ç­ç¥ï¼?
    1. æ¬å°è§åä¿®å¤ï¼ä¿®å¤å¸¸è§é®é¢?
    2. APIä¿®å¤ï¼ä½¿ç¨LLMä¿®å¤å¤æé®é¢
    3. éªè¯ä¿®å¤ç»æï¼ç¡®ä¿ä¿®å¤åè½æ­£å¸¸æ¸²æ?
    """

    def __init__(
        self,
        validator: ChartValidator,
        llm_repair_fns: Optional[List[Callable]] = None
    ):
        """
        åå§åä¿®å¤å¨

        Args:
            validator: å¾è¡¨éªè¯å¨å®ä¾?
            llm_repair_fns: LLMä¿®å¤å½æ°åè¡¨ï¼å¯¹åº?ä¸ªEngineï¼?
        """
        self.validator = validator
        self.llm_repair_fns = llm_repair_fns or []
        # ç¼å­ä¿®å¤ç»æï¼é¿ååä¸ä¸ªå¾è¡¨å¨å¤å¤è¢«éå¤è°ç¨LLM
        self._result_cache: Dict[str, RepairResult] = {}

    def build_cache_key(self, widget_block: Dict[str, Any]) -> str:
        """
        ä¸ºå¾è¡¨çæç¨³å®çç¼å­keyï¼ä¿è¯åæ ·çæ°æ®ä¸ä¼éå¤è§¦åä¿®å¤

        - ä¼åä½¿ç¨widgetIdï¼?
        - ç»åæ°æ®åå®¹çåå¸ï¼é¿ååIDä½åå®¹ååæ¶è¯¯ç¨æ§ç»æ
        """
        widget_id = ""
        if isinstance(widget_block, dict):
            widget_id = widget_block.get('widgetId') or widget_block.get('id') or ""
        try:
            serialized = json.dumps(
                widget_block,
                ensure_ascii=False,
                sort_keys=True,
                default=str
            )
        except Exception:
            serialized = repr(widget_block)
        digest = hashlib.md5(serialized.encode('utf-8', errors='ignore')).hexdigest()
        return f"{widget_id}:{digest}"

    def repair(
        self,
        widget_block: Dict[str, Any],
        validation_result: Optional[ValidationResult] = None
    ) -> RepairResult:
        """
        å°è¯ä¿®å¤å¾è¡¨æ°æ®

        Args:
            widget_block: widgetç±»åçblock
            validation_result: éªè¯ç»æï¼å¯éï¼å¦ææ²¡æä¼åè¿è¡éªè¯ï¼?

        Returns:
            RepairResult: ä¿®å¤ç»æ
        """
        cache_key = self.build_cache_key(widget_block)

        cached = self._result_cache.get(cache_key)
        if cached:
            # è¿åç¼å­çæ·±æ·è´ï¼é¿åå¤é¨ä¿®æ¹å½±åç¼å­?
            return copy.deepcopy(cached)

        def _cache_and_return(res: RepairResult) -> RepairResult:
            """åå¥ä¿®å¤ç»æç¼å­å¹¶è¿åï¼é¿åéå¤è°ç¨ä¸æ¸¸ä¿®å¤é»è¾"""
            try:
                self._result_cache[cache_key] = copy.deepcopy(res)
            except Exception:
                self._result_cache[cache_key] = res
            return res

        # 1. å¦ææ²¡æéªè¯ç»æï¼åéªè¯
        if validation_result is None:
            validation_result = self.validator.validate(widget_block)

        # è·è¸ªå½åææ°çéªè¯ç»æåæ°æ?
        current_validation = validation_result
        current_block = widget_block

        # 2. å°è¯æ¬å°ä¿®å¤ï¼å³ä½¿éªè¯éè¿ä¹å°è¯ï¼å ä¸ºå¯è½æè­¦åï¼
        logger.info(f"å°è¯æ¬å°ä¿®å¤å¾è¡¨")
        local_result = self.repair_locally(widget_block, validation_result)

        # 3. éªè¯æ¬å°ä¿®å¤ç»æ
        if local_result.has_changes():
            repaired_validation = self.validator.validate(local_result.repaired_block)
            if repaired_validation.is_valid:
                logger.info(f"æ¬å°ä¿®å¤æå: {local_result.changes}")
                return _cache_and_return(
                    RepairResult(True, local_result.repaired_block, 'local', local_result.changes)
                )
            else:
                logger.warning(f"æ¬å°ä¿®å¤åä»ç¶æ æ? {repaired_validation.errors}")
                # æ´æ°å½åç¶æä¸ºæ¬å°ä¿®å¤åçç»æï¼ä¾APIä¿®å¤ä½¿ç¨
                current_validation = repaired_validation
                current_block = local_result.repaired_block

        # 4. å¦æå½åä»æä¸¥ééè¯¯ï¼å°è¯APIä¿®å¤
        # æ³¨æï¼ä½¿ç?current_validation èéåå§ validation_result
        if current_validation.has_critical_errors() and len(self.llm_repair_fns) > 0:
            logger.info("æ¬å°ä¿®å¤å¤±è´¥æä¸è¶³ï¼å°è¯APIä¿®å¤")
            # ä¼ å¥æ¬å°å·²ä¿®å¤çæ°æ®ï¼å¦ææï¼ï¼é¿åæµªè´¹æ¬å°ä¿®å¤çå·¥ä½?
            api_result = self.repair_with_api(current_block, current_validation)

            if api_result.success:
                # éªè¯ä¿®å¤ç»æ
                api_repaired_validation = self.validator.validate(api_result.repaired_block)
                if api_repaired_validation.is_valid:
                    logger.info(f"APIä¿®å¤æå: {api_result.changes}")
                    return _cache_and_return(api_result)
                else:
                    logger.warning(f"APIä¿®å¤åä»ç¶æ æ? {api_repaired_validation.errors}")

        # 5. å¦æåå§éªè¯éè¿ï¼è¿ååå§æä¿®å¤åçæ°æ®
        if validation_result.is_valid:
            if local_result.has_changes():
                return _cache_and_return(
                    RepairResult(True, local_result.repaired_block, 'local', local_result.changes)
                )
            else:
                return _cache_and_return(RepairResult(True, widget_block, 'none', []))

        # 6. ææä¿®å¤é½å¤±è´¥ï¼è¿ååå§æ°æ®ï¼ææ¬å°é¨åä¿®å¤çæ°æ®ï¼?
        logger.warning("ææä¿®å¤å°è¯å¤±è´¥ï¼ä¿æåå§æ°æ®")
        # å¦ææ¬å°æé¨åä¿®å¤ï¼è¿åæ¬å°ä¿®å¤åçæ°æ®ï¼è½ç¶éªè¯ä»å¤±è´¥ï¼ä½å¯è½æ¯åå§æ°æ®å¥½ï¼?
        final_block = local_result.repaired_block if local_result.has_changes() else widget_block
        return _cache_and_return(RepairResult(False, final_block, 'none', []))

    def repair_locally(
        self,
        widget_block: Dict[str, Any],
        validation_result: ValidationResult
    ) -> RepairResult:
        """
        ä½¿ç¨æ¬å°è§åä¿®å¤

        ä¿®å¤è§åï¼?
        1. è¡¥å¨ç¼ºå¤±çåºæ¬å­æ®?
        2. ä¿®å¤æ°æ®ç±»åéè¯¯
        3. ä¿®å¤æ°æ®é¿åº¦ä¸å¹é?
        4. æ¸çæ ææ°æ®
        5. æ·»å é»è®¤å?
        """
        repaired = copy.deepcopy(widget_block)
        changes = []

        # 1. ç¡®ä¿åºæ¬ç»æå­å¨
        if 'props' not in repaired or not isinstance(repaired.get('props'), dict):
            repaired['props'] = {}
            changes.append("æ·»å ç¼ºå¤±çpropså­æ®µ")

        if 'data' not in repaired or not isinstance(repaired.get('data'), dict):
            repaired['data'] = {}
            changes.append("æ·»å ç¼ºå¤±çdataå­æ®µ")

        # 2. ç¡®ä¿å¾è¡¨ç±»åå­å¨
        chart_type = self.validator._extract_chart_type(repaired)
        props = repaired['props']

        if not chart_type:
            # å°è¯ä»widgetTypeæ¨æ­
            widget_type = repaired.get('widgetType', '')
            if '/' in widget_type:
                chart_type = widget_type.split('/')[-1].lower()
                props['type'] = chart_type
                changes.append(f"ä»widgetTypeæ¨æ­å¾è¡¨ç±»å: {chart_type}")
            else:
                # é»è®¤ä½¿ç¨barç±»å
                chart_type = 'bar'
                props['type'] = chart_type
                changes.append("è®¾ç½®é»è®¤å¾è¡¨ç±»å: bar")
        elif 'type' not in props or not props['type']:
            # chart_typeå­å¨ä½propsä¸­æ²¡ætypeå­æ®µï¼éè¦æ·»å?
            props['type'] = chart_type
            changes.append(f"å°æ¨æ­çå¾è¡¨ç±»åæ·»å å°props: {chart_type}")

        # 3. ä¿®å¤æ°æ®ç»æ
        data = repaired['data']

        # ç¡®ä¿datasetså­å¨
        if 'datasets' not in data or not isinstance(data.get('datasets'), list):
            data['datasets'] = []
            changes.append("æ·»å ç¼ºå¤±çdatasetså­æ®µ")

        # å¦ædatasetsä¸ºç©ºä½dataä¸­æå¶ä»æ°æ®ï¼å°è¯æé datasets
        if len(data['datasets']) == 0:
            constructed = self._try_construct_datasets(data, chart_type)
            if constructed:
                data['datasets'] = constructed
                changes.append("ä»dataä¸­æé datasets")
            elif 'labels' in data and isinstance(data.get('labels'), list) and len(data['labels']) > 0:
                # å¦æælabelsä½æ²¡ææ°æ®ï¼åå»ºä¸ä¸ªç©ºdataset
                data['datasets'] = [{
                    'label': 'æ°æ®',
                    'data': [0] * len(data['labels'])
                }]
                changes.append("æ ¹æ®labelsåå»ºé»è®¤datasetï¼ä½¿ç¨é¶å¼ï¼")

        # ç¡®ä¿labelså­å¨ï¼å¦æéè¦ï¼
        if chart_type in ChartValidator.LABEL_REQUIRED_TYPES:
            if 'labels' not in data or not isinstance(data.get('labels'), list):
                # å°è¯æ ¹æ®datasetsé¿åº¦çælabels
                if data['datasets'] and len(data['datasets']) > 0:
                    first_ds = data['datasets'][0]
                    if isinstance(first_ds, dict) and isinstance(first_ds.get('data'), list):
                        data_len = len(first_ds['data'])
                        data['labels'] = [f"é¡¹ç® {i+1}" for i in range(data_len)]
                        changes.append(f"çæ{data_len}ä¸ªé»è®¤labels")

        # 4. ä¿®å¤datasetsä¸­çæ°æ®
        for idx, dataset in enumerate(data.get('datasets', [])):
            if not isinstance(dataset, dict):
                continue

            # ç¡®ä¿ædataå­æ®µ
            if 'data' not in dataset or not isinstance(dataset.get('data'), list):
                dataset['data'] = []
                changes.append(f"ä¸ºdatasets[{idx}]æ·»å ç©ºdataæ°ç»")

            # ç¡®ä¿ælabel
            if 'label' not in dataset:
                dataset['label'] = f"ç³»å {idx + 1}"
                changes.append(f"ä¸ºdatasets[{idx}]æ·»å é»è®¤label")

            # ä¿®å¤æ°æ®é¿åº¦ä¸å¹é?
            labels = data.get('labels', [])
            ds_data = dataset.get('data', [])
            if isinstance(labels, list) and isinstance(ds_data, list):
                if len(ds_data) < len(labels):
                    # æ°æ®ä¸å¤ï¼è¡¥null
                    dataset['data'] = ds_data + [None] * (len(labels) - len(ds_data))
                    changes.append(f"datasets[{idx}]æ°æ®é¿åº¦ä¸è¶³ï¼è¡¥ånull")
                elif len(ds_data) > len(labels):
                    # æ°æ®è¿å¤ï¼æªæ?
                    dataset['data'] = ds_data[:len(labels)]
                    changes.append(f"datasets[{idx}]æ°æ®é¿åº¦è¿é¿ï¼æªæ?)

            # è½¬æ¢éæ°å¼æ°æ®ä¸ºæ°å¼ï¼å¦æå¯è½ï¼?
            if chart_type in ChartValidator.NUMERIC_DATA_TYPES:
                ds_data = dataset.get('data', [])
                converted = False
                for i, value in enumerate(ds_data):
                    if value is None:
                        continue
                    if not isinstance(value, (int, float)):
                        # å°è¯è½¬æ¢
                        try:
                            if isinstance(value, str):
                                # å°è¯è½¬æ¢å­ç¬¦ä¸?
                                ds_data[i] = float(value)
                                converted = True
                        except (ValueError, TypeError):
                            # è½¬æ¢å¤±è´¥ï¼è®¾ä¸ºnull
                            ds_data[i] = None
                            converted = True
                if converted:
                    changes.append(f"datasets[{idx}]åå«éæ°å¼æ°æ®ï¼å·²å°è¯è½¬æ?)

        # 5. éªè¯ä¿®å¤ç»æ
        success = len(changes) > 0

        return RepairResult(success, repaired, 'local', changes)

    def _try_construct_datasets(
        self,
        data: Dict[str, Any],
        chart_type: str
    ) -> Optional[List[Dict[str, Any]]]:
        """å°è¯ä»dataä¸­æé datasets"""
        # å¦ædataç´æ¥åå«æ°æ®æ°ç»ï¼å°è¯æé?
        if 'values' in data and isinstance(data['values'], list):
            return [{
                'label': 'æ°æ®',
                'data': data['values']
            }]

        # å¦ædataåå«serieså­æ®µ
        if 'series' in data and isinstance(data['series'], list):
            datasets = []
            for idx, series in enumerate(data['series']):
                if isinstance(series, dict):
                    datasets.append({
                        'label': series.get('name', f'ç³»å {idx + 1}'),
                        'data': series.get('data', [])
                    })
                elif isinstance(series, list):
                    datasets.append({
                        'label': f'ç³»å {idx + 1}',
                        'data': series
                    })
            if datasets:
                return datasets

        return None

    def repair_with_api(
        self,
        widget_block: Dict[str, Any],
        validation_result: ValidationResult
    ) -> RepairResult:
        """
        ä½¿ç¨APIä¿®å¤ï¼è°ç?ä¸ªEngineçLLMï¼

        ç­ç¥ï¼æé¡ºåºå°è¯ä¸åçEngineï¼ç´å°ä¿®å¤æå?
        """
        if not self.llm_repair_fns:
            logger.debug("æ²¡æå¯ç¨çLLMä¿®å¤å½æ°ï¼è·³è¿APIä¿®å¤")
            return RepairResult(False, None, 'api', [])

        widget_id = widget_block.get('widgetId', 'unknown')
        logger.info(f"å¾è¡¨ {widget_id} å¼å§APIä¿®å¤ï¼å± {len(self.llm_repair_fns)} ä¸ªEngineå¯ç¨")

        for idx, repair_fn in enumerate(self.llm_repair_fns):
            try:
                logger.info(f"å°è¯ä½¿ç¨Engine {idx + 1}/{len(self.llm_repair_fns)} ä¿®å¤å¾è¡¨ {widget_id}")
                repaired = repair_fn(widget_block, validation_result.errors)

                if repaired and isinstance(repaired, dict):
                    # éªè¯ä¿®å¤ç»æ
                    repaired_validation = self.validator.validate(repaired)
                    if repaired_validation.is_valid:
                        logger.info(f"å¾è¡¨ {widget_id} ä½¿ç¨Engine {idx + 1} ä¿®å¤æå")
                        return RepairResult(
                            True,
                            repaired,
                            'api',
                            [f"ä½¿ç¨Engine {idx + 1}ä¿®å¤æå"]
                        )
                    else:
                        logger.warning(
                            f"å¾è¡¨ {widget_id} Engine {idx + 1} è¿åçæ°æ®éªè¯å¤±è´? "
                            f"{repaired_validation.errors}"
                        )
                else:
                    logger.warning(f"å¾è¡¨ {widget_id} Engine {idx + 1} è¿åç©ºææ æååº")
            except Exception as e:
                # ä½¿ç¨ exception è®°å½å®æ´å æ 
                logger.exception(f"å¾è¡¨ {widget_id} Engine {idx + 1} ä¿®å¤è¿ç¨ä¸­åçå¼å¸? {e}")
                continue

        logger.warning(f"å¾è¡¨ {widget_id} ææ?{len(self.llm_repair_fns)} ä¸ªEngineåä¿®å¤å¤±è´?)
        return RepairResult(False, None, 'api', [])


def create_chart_validator() -> ChartValidator:
    """åå»ºå¾è¡¨éªè¯å¨å®ä¾?""
    return ChartValidator()


def create_chart_repairer(
    validator: Optional[ChartValidator] = None,
    llm_repair_fns: Optional[List[Callable]] = None
) -> ChartRepairer:
    """åå»ºå¾è¡¨ä¿®å¤å¨å®ä¾?""
    if validator is None:
        validator = create_chart_validator()
    return ChartRepairer(validator, llm_repair_fns)
