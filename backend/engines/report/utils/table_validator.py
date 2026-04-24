"""
è¡¨æ ¼éªè¯åä¿®å¤å·¥å·

æä¾å¯?IR è¡¨æ ¼æ°æ®çéªè¯åä¿®å¤è½åï¼?
1. éªè¯è¡¨æ ¼æ°æ®æ ¼å¼æ¯å¦ç¬¦å IR schema è¦æ±
2. æ£æµåµå¥?cells ç»æé®é¢
3. éªè¯ rows/cells åºæ¬æ ¼å¼
4. æ£æ¥æ°æ®å®æ´æ?
5. æ¬å°è§åä¿®å¤å¸¸è§é®é¢
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class TableValidationResult:
    """è¡¨æ ¼éªè¯ç»æ"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    nested_cells_detected: bool = False
    empty_cells_count: int = 0
    total_cells_count: int = 0

    def has_critical_errors(self) -> bool:
        """æ¯å¦æä¸¥ééè¯¯ï¼ä¼å¯¼è´æ¸²æå¤±è´¥ï¼"""
        return not self.is_valid and len(self.errors) > 0


@dataclass
class TableRepairResult:
    """è¡¨æ ¼ä¿®å¤ç»æ"""
    success: bool
    repaired_block: Optional[Dict[str, Any]]
    changes: List[str]

    def has_changes(self) -> bool:
        """æ¯å¦æä¿®æ?""
        return len(self.changes) > 0


class TableValidator:
    """
    è¡¨æ ¼éªè¯å?- éªè¯ IR è¡¨æ ¼æ°æ®æ ¼å¼æ¯å¦æ­£ç¡®

    éªè¯è§åï¼?
    1. åºæ¬ç»æéªè¯ï¼type, rows å­æ®µ
    2. è¡ç»æéªè¯ï¼æ¯è¡å¿é¡»æ?cells æ°ç»
    3. ååæ ¼ç»æéªè¯ï¼æ¯ä¸ª cell å¿é¡»æ?blocks æ°ç»
    4. åµå¥ cells æ£æµï¼æ£æµéè¯¯çåµå¥ cells ç»æ
    5. æ°æ®å®æ´æ§éªè¯ï¼æ£æ¥ç©ºååæ ¼åç¼ºå¤±æ°æ®
    """

    def __init__(self):
        """åå§åéªè¯å¨"""
        pass

    def validate(self, table_block: Dict[str, Any]) -> TableValidationResult:
        """
        éªè¯è¡¨æ ¼æ ¼å¼

        Args:
            table_block: table ç±»åç?blockï¼åå?type, rows ç­å­æ®?

        Returns:
            TableValidationResult: éªè¯ç»æ
        """
        errors: List[str] = []
        warnings: List[str] = []
        nested_cells_detected = False
        empty_cells_count = 0
        total_cells_count = 0

        # 1. åºæ¬ç»æéªè¯
        if not isinstance(table_block, dict):
            errors.append("table_block å¿é¡»æ¯å­å¸ç±»å?)
            return TableValidationResult(
                False, errors, warnings, nested_cells_detected,
                empty_cells_count, total_cells_count
            )

        # 2. æ£æ?type
        block_type = table_block.get('type')
        if block_type != 'table':
            errors.append(f"block type åºä¸º 'table'ï¼å®éä¸º '{block_type}'")

        # 3. éªè¯ rows å­æ®µ
        rows = table_block.get('rows')
        if rows is None:
            errors.append("ç¼ºå° rows å­æ®µ")
            return TableValidationResult(
                False, errors, warnings, nested_cells_detected,
                empty_cells_count, total_cells_count
            )

        if not isinstance(rows, list):
            errors.append("rows å¿é¡»æ¯æ°ç»ç±»å?)
            return TableValidationResult(
                False, errors, warnings, nested_cells_detected,
                empty_cells_count, total_cells_count
            )

        if len(rows) == 0:
            warnings.append("rows æ°ç»ä¸ºç©ºï¼è¡¨æ ¼å¯è½æ æ³æ­£å¸¸æ¾ç¤?)

        # 4. éªè¯æ¯ä¸è¡?
        for row_idx, row in enumerate(rows):
            row_result = self._validate_row(row, row_idx)
            errors.extend(row_result['errors'])
            warnings.extend(row_result['warnings'])
            if row_result['nested_cells_detected']:
                nested_cells_detected = True
            empty_cells_count += row_result['empty_cells_count']
            total_cells_count += row_result['total_cells_count']

        # 5. æ£æ¥åæ°ä¸è´æ?
        column_counts = []
        for row in rows:
            if isinstance(row, dict):
                cells = row.get('cells', [])
                if isinstance(cells, list):
                    col_count = 0
                    for cell in cells:
                        if isinstance(cell, dict):
                            col_count += int(cell.get('colspan', 1))
                        else:
                            col_count += 1
                    column_counts.append(col_count)

        if column_counts and len(set(column_counts)) > 1:
            warnings.append(
                f"åè¡åæ°ä¸ä¸è? {column_counts}ï¼å¯è½å¯¼è´æ¸²æé®é¢?
            )

        # 6. ç©ºååæ ¼è­¦å
        if total_cells_count > 0 and empty_cells_count > total_cells_count * 0.5:
            warnings.append(
                f"è¶è¿50%çååæ ¼ä¸ºç©º ({empty_cells_count}/{total_cells_count})ï¼?
                "è¡¨æ ¼å¯è½ç¼ºå°æ°æ®"
            )

        is_valid = len(errors) == 0
        return TableValidationResult(
            is_valid, errors, warnings, nested_cells_detected,
            empty_cells_count, total_cells_count
        )

    def _validate_row(self, row: Any, row_idx: int) -> Dict[str, Any]:
        """éªè¯åè¡"""
        result = {
            'errors': [],
            'warnings': [],
            'nested_cells_detected': False,
            'empty_cells_count': 0,
            'total_cells_count': 0,
        }

        if not isinstance(row, dict):
            result['errors'].append(f"rows[{row_idx}] å¿é¡»æ¯å¯¹è±¡ç±»å?)
            return result

        cells = row.get('cells')
        if cells is None:
            result['errors'].append(f"rows[{row_idx}] ç¼ºå° cells å­æ®µ")
            return result

        if not isinstance(cells, list):
            result['errors'].append(f"rows[{row_idx}].cells å¿é¡»æ¯æ°ç»ç±»å?)
            return result

        if len(cells) == 0:
            result['warnings'].append(f"rows[{row_idx}].cells æ°ç»ä¸ºç©º")

        # éªè¯æ¯ä¸ªååæ ?
        for cell_idx, cell in enumerate(cells):
            cell_result = self._validate_cell(cell, row_idx, cell_idx)
            result['errors'].extend(cell_result['errors'])
            result['warnings'].extend(cell_result['warnings'])
            if cell_result['nested_cells_detected']:
                result['nested_cells_detected'] = True
            if cell_result['is_empty']:
                result['empty_cells_count'] += 1
            result['total_cells_count'] += 1

        return result

    def _validate_cell(self, cell: Any, row_idx: int, cell_idx: int) -> Dict[str, Any]:
        """éªè¯åä¸ªååæ ?""
        result = {
            'errors': [],
            'warnings': [],
            'nested_cells_detected': False,
            'is_empty': False,
        }

        if not isinstance(cell, dict):
            result['errors'].append(
                f"rows[{row_idx}].cells[{cell_idx}] å¿é¡»æ¯å¯¹è±¡ç±»å?
            )
            return result

        # æ£æµåµå¥?cells ç»æï¼è¿æ¯å¸¸è§ç LLM éè¯¯ï¼?
        if 'cells' in cell and 'blocks' not in cell:
            result['nested_cells_detected'] = True
            result['errors'].append(
                f"rows[{row_idx}].cells[{cell_idx}] æ£æµå°éè¯¯çåµå¥?cells ç»æï¼?
                "åºè¯¥æ?blocks èä¸æ?cells"
            )
            return result

        # éªè¯ blocks å­æ®µ
        blocks = cell.get('blocks')
        if blocks is None:
            result['errors'].append(
                f"rows[{row_idx}].cells[{cell_idx}] ç¼ºå° blocks å­æ®µ"
            )
            return result

        if not isinstance(blocks, list):
            result['errors'].append(
                f"rows[{row_idx}].cells[{cell_idx}].blocks å¿é¡»æ¯æ°ç»ç±»å?
            )
            return result

        # æ£æ¥æ¯å¦ä¸ºç©?
        if len(blocks) == 0:
            result['is_empty'] = True
        else:
            # æ£æ?blocks åå®¹æ¯å¦ææ
            has_content = False
            for block in blocks:
                if isinstance(block, dict):
                    # æ£æ?paragraph ç?inlines
                    if block.get('type') == 'paragraph':
                        inlines = block.get('inlines', [])
                        for inline in inlines:
                            if isinstance(inline, dict):
                                text = inline.get('text', '')
                                if text and text.strip():
                                    has_content = True
                                    break
                    # æ£æ¥å¶ä»ç±»åç text/content
                    elif block.get('text') or block.get('content'):
                        has_content = True
                        break
                if has_content:
                    break

            if not has_content:
                result['is_empty'] = True

        # éªè¯ colspan/rowspan
        colspan = cell.get('colspan')
        if colspan is not None:
            if not isinstance(colspan, int) or colspan < 1:
                result['warnings'].append(
                    f"rows[{row_idx}].cells[{cell_idx}].colspan å¼æ æ? {colspan}"
                )

        rowspan = cell.get('rowspan')
        if rowspan is not None:
            if not isinstance(rowspan, int) or rowspan < 1:
                result['warnings'].append(
                    f"rows[{row_idx}].cells[{cell_idx}].rowspan å¼æ æ? {rowspan}"
                )

        return result

    def can_render(self, table_block: Dict[str, Any]) -> bool:
        """
        å¤æ­è¡¨æ ¼æ¯å¦è½æ­£å¸¸æ¸²æï¼å¿«éæ£æ¥ï¼

        Args:
            table_block: table ç±»åç?block

        Returns:
            bool: æ¯å¦è½æ­£å¸¸æ¸²æ?
        """
        result = self.validate(table_block)
        return result.is_valid

    def has_nested_cells(self, table_block: Dict[str, Any]) -> bool:
        """
        æ£æµè¡¨æ ¼æ¯å¦åå«åµå¥?cells ç»æ

        Args:
            table_block: table ç±»åç?block

        Returns:
            bool: æ¯å¦åå«åµå¥ cells
        """
        result = self.validate(table_block)
        return result.nested_cells_detected


class TableRepairer:
    """
    è¡¨æ ¼ä¿®å¤å?- å°è¯ä¿®å¤è¡¨æ ¼æ°æ®

    ä¿®å¤ç­ç¥ï¼?
    1. å±å¹³åµå¥ cells ç»æ
    2. è¡¥åç¼ºå¤±ç?blocks å­æ®µ
    3. è§èåååæ ¼ç»æ
    4. éªè¯ä¿®å¤ç»æ
    """

    def __init__(self, validator: Optional[TableValidator] = None):
        """
        åå§åä¿®å¤å¨

        Args:
            validator: è¡¨æ ¼éªè¯å¨å®ä¾?
        """
        self.validator = validator or TableValidator()

    def repair(
        self,
        table_block: Dict[str, Any],
        validation_result: Optional[TableValidationResult] = None
    ) -> TableRepairResult:
        """
        å°è¯ä¿®å¤è¡¨æ ¼æ°æ®

        Args:
            table_block: table ç±»åç?block
            validation_result: éªè¯ç»æï¼å¯éï¼å¦ææ²¡æä¼åè¿è¡éªè¯ï¼?

        Returns:
            TableRepairResult: ä¿®å¤ç»æ
        """
        # 1. å¦ææ²¡æéªè¯ç»æï¼åéªè¯
        if validation_result is None:
            validation_result = self.validator.validate(table_block)

        # 2. å¦æå·²ç»ææï¼è¿ååæ°æ®
        if validation_result.is_valid and not validation_result.nested_cells_detected:
            return TableRepairResult(True, table_block, [])

        # 3. å°è¯ä¿®å¤
        repaired = copy.deepcopy(table_block)
        changes: List[str] = []

        # ç¡®ä¿åºæ¬ç»æ
        if 'type' not in repaired:
            repaired['type'] = 'table'
            changes.append("æ·»å ç¼ºå¤±ç?type å­æ®µ")

        if 'rows' not in repaired or not isinstance(repaired.get('rows'), list):
            repaired['rows'] = []
            changes.append("æ·»å ç¼ºå¤±ç?rows å­æ®µ")

        # ä¿®å¤æ¯ä¸è¡?
        repaired_rows: List[Dict[str, Any]] = []
        for row_idx, row in enumerate(repaired.get('rows', [])):
            repaired_row, row_changes = self._repair_row(row, row_idx)
            repaired_rows.append(repaired_row)
            changes.extend(row_changes)

        repaired['rows'] = repaired_rows

        # 4. éªè¯ä¿®å¤ç»æ
        repaired_validation = self.validator.validate(repaired)
        success = repaired_validation.is_valid

        if not success:
            logger.warning(
                f"è¡¨æ ¼ä¿®å¤åä»æé®é¢? {repaired_validation.errors}"
            )

        return TableRepairResult(success, repaired, changes)

    def _repair_row(
        self, row: Any, row_idx: int
    ) -> Tuple[Dict[str, Any], List[str]]:
        """ä¿®å¤åè¡"""
        changes: List[str] = []

        if not isinstance(row, dict):
            return {'cells': [self._default_cell()]}, [
                f"rows[{row_idx}] ç±»åéè¯¯ï¼å·²éå»º"
            ]

        repaired_row = dict(row)

        # ç¡®ä¿æ?cells å­æ®µ
        if 'cells' not in repaired_row or not isinstance(repaired_row.get('cells'), list):
            repaired_row['cells'] = [self._default_cell()]
            changes.append(f"rows[{row_idx}] æ·»å ç¼ºå¤±ç?cells å­æ®µ")
            return repaired_row, changes

        # ä¿®å¤æ¯ä¸ªååæ ?
        repaired_cells: List[Dict[str, Any]] = []
        for cell_idx, cell in enumerate(repaired_row.get('cells', [])):
            if isinstance(cell, dict) and 'cells' in cell and 'blocks' not in cell:
                # å±å¹³åµå¥ cells
                flattened = self._flatten_nested_cells(cell)
                repaired_cells.extend(flattened)
                changes.append(
                    f"rows[{row_idx}].cells[{cell_idx}] å±å¹³åµå¥ cells ç»æ"
                )
            else:
                repaired_cell, cell_changes = self._repair_cell(cell, row_idx, cell_idx)
                repaired_cells.append(repaired_cell)
                changes.extend(cell_changes)

        repaired_row['cells'] = repaired_cells
        return repaired_row, changes

    def _repair_cell(
        self, cell: Any, row_idx: int, cell_idx: int
    ) -> Tuple[Dict[str, Any], List[str]]:
        """ä¿®å¤åä¸ªååæ ?""
        changes: List[str] = []

        if not isinstance(cell, dict):
            if isinstance(cell, (str, int, float)):
                return {
                    'blocks': [self._text_to_paragraph(str(cell))]
                }, [f"rows[{row_idx}].cells[{cell_idx}] è½¬æ¢ä¸ºæ åæ ¼å¼?]
            return self._default_cell(), [
                f"rows[{row_idx}].cells[{cell_idx}] ç±»åéè¯¯ï¼å·²éå»º"
            ]

        repaired_cell = dict(cell)

        # ç¡®ä¿æ?blocks å­æ®µ
        if 'blocks' not in repaired_cell:
            # å°è¯ä»å¶ä»å­æ®µæååå®?
            text = ''
            for key in ('text', 'content', 'value'):
                if key in repaired_cell and repaired_cell[key]:
                    text = str(repaired_cell[key])
                    break

            repaired_cell['blocks'] = [self._text_to_paragraph(text or '')]
            changes.append(
                f"rows[{row_idx}].cells[{cell_idx}] æ·»å ç¼ºå¤±ç?blocks å­æ®µ"
            )
        elif not isinstance(repaired_cell['blocks'], list):
            repaired_cell['blocks'] = [self._text_to_paragraph('')]
            changes.append(
                f"rows[{row_idx}].cells[{cell_idx}].blocks ç±»åéè¯¯ï¼å·²éå»º"
            )
        elif len(repaired_cell['blocks']) == 0:
            repaired_cell['blocks'] = [self._text_to_paragraph('')]
            changes.append(
                f"rows[{row_idx}].cells[{cell_idx}].blocks ä¸ºç©ºï¼æ·»å é»è®¤åå®?
            )

        return repaired_cell, changes

    def _flatten_nested_cells(self, cell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """å±å¹³åµå¥ç?cells ç»æ"""
        nested_cells = cell.get('cells', [])
        if not isinstance(nested_cells, list):
            return [self._default_cell()]

        result: List[Dict[str, Any]] = []
        for nested in nested_cells:
            if isinstance(nested, dict):
                if 'blocks' in nested and 'cells' not in nested:
                    # æ­£å¸¸ç?cell
                    result.append(nested)
                elif 'cells' in nested and 'blocks' not in nested:
                    # ç»§ç»­éå½å±å¹³
                    result.extend(self._flatten_nested_cells(nested))
                else:
                    # å°è¯ä¿®å¤
                    repaired, _ = self._repair_cell(nested, 0, 0)
                    result.append(repaired)
            elif isinstance(nested, (str, int, float)):
                result.append({
                    'blocks': [self._text_to_paragraph(str(nested))]
                })

        return result if result else [self._default_cell()]

    def _default_cell(self) -> Dict[str, Any]:
        """åå»ºé»è®¤ååæ ?""
        return {
            'blocks': [self._text_to_paragraph('')]
        }

    def _text_to_paragraph(self, text: str) -> Dict[str, Any]:
        """å°ææ¬è½¬æ¢ä¸º paragraph block"""
        return {
            'type': 'paragraph',
            'inlines': [{'text': text, 'marks': []}]
        }


def create_table_validator() -> TableValidator:
    """åå»ºè¡¨æ ¼éªè¯å¨å®ä¾?""
    return TableValidator()


def create_table_repairer(
    validator: Optional[TableValidator] = None
) -> TableRepairer:
    """åå»ºè¡¨æ ¼ä¿®å¤å¨å®ä¾?""
    return TableRepairer(validator)


__all__ = [
    'TableValidator',
    'TableRepairer',
    'TableValidationResult',
    'TableRepairResult',
    'create_table_validator',
    'create_table_repairer',
]
