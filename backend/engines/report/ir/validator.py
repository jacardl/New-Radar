"""
ç« èçº§JSONç»ææ ¡éªå¨

LLMæç« èçæIRåï¼éè¦å¨è½çä¸è£è®¢åç»è¿ä¸¥æ ¼æ ¡éªï¼ä»¥é¿å
æ¸²ææçç»ææ§å´©æºãæ¬æ¨¡åå®ç°è½»éçº§çPythonæ ¡éªé»è¾ï¼?
æ éä¾èµjsonschemaåºå³å¯å¿«éå®ä½éè¯¯
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .schema import (
    ALLOWED_BLOCK_TYPES,
    ALLOWED_INLINE_MARKS,
    ENGINE_AGENT_TITLES,
    IR_VERSION,
)


class IRValidator:
    """
    ç« èIRç»ææ ¡éªå¨

    è¯´æï¼?
        - validate_chapterè¿å(æ¯å¦éè¿, éè¯¯åè¡¨)
        - éè¯¯å®ä½éç¨pathè¯­æ³ï¼ä¾¿äºå¿«éè¿½è¸?
        - åç½®å¯¹heading/paragraph/list/tableç­ææåºåçç»ç²åº¦æ ¡éª?
    """

    def __init__(self, schema_version: str = IR_VERSION):
        """è®°å½å½åSchemaçæ¬ï¼ä¾¿äºæªæ¥å¤çæ¬å¹¶å­"""
        self.schema_version = schema_version

    # ======== å¯¹å¤æ¥å£ ========

    def validate_chapter(self, chapter: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """æ ¡éªåä¸ªç« èå¯¹è±¡çå¿å¡«å­æ®µä¸blockç»æ"""
        errors: List[str] = []
        if not isinstance(chapter, dict):
            return False, ["chapterå¿é¡»æ¯å¯¹è±?]

        for field in ("chapterId", "title", "anchor", "order", "blocks"):
            if field not in chapter:
                errors.append(f"missing chapter.{field}")

        if not isinstance(chapter.get("blocks"), list) or not chapter.get("blocks"):
            errors.append("chapter.blockså¿é¡»æ¯éç©ºæ°ç»?)
            return False, errors

        blocks = chapter.get("blocks", [])
        for idx, block in enumerate(blocks):
            self._validate_block(block, f"blocks[{idx}]", errors)

        return len(errors) == 0, errors

    # ======== åé¨å·¥å· ========

    def _validate_block(self, block: Any, path: str, errors: List[str]):
        """æ ¹æ®blockç±»åè°ç¨ä¸åçæ ¡éªå¨"""
        if not isinstance(block, dict):
            errors.append(f"{path} å¿é¡»æ¯å¯¹è±?)
            return

        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            errors.append(f"{path}.type ä¸è¢«æ¯æ: {block_type}")
            return

        validator = getattr(self, f"_validate_{block_type}_block", None)
        if validator:
            validator(block, path, errors)

    def _validate_heading_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """headingå¿é¡»ælevel/text/anchor"""
        if "level" not in block or not isinstance(block["level"], int):
            errors.append(f"{path}.level å¿é¡»æ¯æ´æ?)
        if "text" not in block:
            errors.append(f"{path}.text ç¼ºå¤±")
        if "anchor" not in block:
            errors.append(f"{path}.anchor ç¼ºå¤±")

    def _validate_paragraph_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """paragraphéè¦éç©ºinlinesï¼å¹¶éæ¡æ ¡éª"""
        inlines = block.get("inlines")
        if not isinstance(inlines, list) or not inlines:
            errors.append(f"{path}.inlines å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for idx, run in enumerate(inlines):
            self._validate_inline_run(run, f"{path}.inlines[{idx}]", errors)

    def _validate_list_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """åè¡¨éè¦å£°ælistTypeä¸æ¯ä¸ªitemé½æ¯blockæ°ç»"""
        if block.get("listType") not in {"ordered", "bullet", "task"}:
            errors.append(f"{path}.listType åå¼éæ³?)
        items = block.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.items å¿é¡»æ¯éç©ºåè¡?)
            return
        for i, item in enumerate(items):
            if not isinstance(item, list):
                errors.append(f"{path}.items[{i}] å¿é¡»æ¯åºåæ°ç»?)
                continue
            for j, sub_block in enumerate(item):
                self._validate_block(sub_block, f"{path}.items[{i}][{j}]", errors)

    def _validate_table_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """è¡¨æ ¼éæä¾rows/cells/blocksï¼éå½æ ¡éªååæ ¼åå®?""
        rows = block.get("rows")
        if not isinstance(rows, list) or not rows:
            errors.append(f"{path}.rows å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for r_idx, row in enumerate(rows):
            cells = row.get("cells") if isinstance(row, dict) else None
            if not isinstance(cells, list) or not cells:
                errors.append(f"{path}.rows[{r_idx}].cells å¿é¡»æ¯éç©ºæ°ç»?)
                continue
            for c_idx, cell in enumerate(cells):
                if not isinstance(cell, dict):
                    errors.append(f"{path}.rows[{r_idx}].cells[{c_idx}] å¿é¡»æ¯å¯¹è±?)
                    continue
                blocks = cell.get("blocks")
                if not isinstance(blocks, list) or not blocks:
                    errors.append(
                        f"{path}.rows[{r_idx}].cells[{c_idx}].blocks å¿é¡»æ¯éç©ºæ°ç»?
                    )
                    continue
                for b_idx, sub_block in enumerate(blocks):
                    self._validate_block(
                        sub_block,
                        f"{path}.rows[{r_idx}].cells[{c_idx}].blocks[{b_idx}]",
                        errors,
                    )

    def _validate_swotTable_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """SWOTè¡¨è³å°æä¾åè±¡éä¹ä¸ï¼æ¯è±¡éä¸ºæ¡ç®æ°ç»?""
        quadrants = ("strengths", "weaknesses", "opportunities", "threats")
        if not any(block.get(name) is not None for name in quadrants):
            errors.append(f"{path} éè¦è³å°åå?strengths/weaknesses/opportunities/threats ä¹ä¸")
        for name in quadrants:
            entries = block.get(name)
            if entries is None:
                continue
            if not isinstance(entries, list):
                errors.append(f"{path}.{name} å¿é¡»æ¯æ°ç»?)
                continue
            for idx, entry in enumerate(entries):
                self._validate_swot_item(entry, f"{path}.{name}[{idx}]", errors)

    # SWOT impact å­æ®µåè®¸çè¯çº§å?
    ALLOWED_IMPACT_VALUES = {"ä½?, "ä¸­ä½", "ä¸?, "ä¸­é«", "é«?, "æé«"}

    def _validate_swot_item(self, item: Any, path: str, errors: List[str]):
        """åä¸ªSWOTæ¡ç®æ¯æå­ç¬¦ä¸²æå¸¦å­æ®µçå¯¹è±¡"""
        if isinstance(item, str):
            if not item.strip():
                errors.append(f"{path} ä¸è½ä¸ºç©ºå­ç¬¦ä¸?)
            return
        if not isinstance(item, dict):
            errors.append(f"{path} å¿é¡»æ¯å­ç¬¦ä¸²æå¯¹è±?)
            return
        title = None
        for key in ("title", "label", "text", "detail", "description"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                title = value
                break
        if title is None:
            errors.append(f"{path} ç¼ºå° title/label/text/description ç­æå­å­æ®?)

        # æ ¡éª impact å­æ®µï¼åªåè®¸è¯çº§å?
        impact = item.get("impact")
        if impact is not None:
            if not isinstance(impact, str) or impact not in self.ALLOWED_IMPACT_VALUES:
                errors.append(
                    f"{path}.impact åªåè®¸å¡«åå½±åè¯çº§ï¼ä½?ä¸­ä½/ä¸?ä¸­é«/é«?æé«ï¼ï¼"
                    f"å½åå? {impact}ï¼å¦éè¯¦ç»è¯´æè¯·åå?detail å­æ®µ"
                )

        # # æ ¡éª score å­æ®µï¼åªåè®¸ 0-10 çæ°å­ï¼å·²ç¦ç¨ï¼
        # score = item.get("score")
        # if score is not None:
        #     valid_score = False
        #     if isinstance(score, (int, float)):
        #         valid_score = 0 <= score <= 10
        #     elif isinstance(score, str):
        #         # å¼å®¹å­ç¬¦ä¸²å½¢å¼çæ°å­
        #         try:
        #             numeric_score = float(score)
        #             valid_score = 0 <= numeric_score <= 10
        #         except ValueError:
        #             valid_score = False
        #     if not valid_score:
        #         errors.append(
        #             f"{path}.score åªåè®¸å¡«å?0-10 çæ°å­ï¼å½åå? {score}"
        #         )

    def _validate_blockquote_block(
        self, block: Dict[str, Any], path: str, errors: List[str]
    ):
        """å¼ç¨ååé¨éè¦è³å°ä¸ä¸ªå­block"""
        inner = block.get("blocks")
        if not isinstance(inner, list) or not inner:
            errors.append(f"{path}.blocks å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for idx, sub_block in enumerate(inner):
            self._validate_block(sub_block, f"{path}.blocks[{idx}]", errors)

    def _validate_engineQuote_block(
        self, block: Dict[str, Any], path: str, errors: List[str]
    ):
        """åå¼æåè¨åéæ æ³¨engineå¹¶åå«å­blocks"""
        engine_raw = block.get("engine")
        engine = engine_raw.lower() if isinstance(engine_raw, str) else None
        if engine not in {"insight", "media", "query"}:
            errors.append(f"{path}.engine åå¼éæ³? {engine_raw}")
        title = block.get("title")
        expected_title = ENGINE_AGENT_TITLES.get(engine) if engine else None
        if title is None:
            errors.append(f"{path}.title ç¼ºå¤±")
        elif not isinstance(title, str):
            errors.append(f"{path}.title å¿é¡»æ¯å­ç¬¦ä¸²")
        elif expected_title and title != expected_title:
            errors.append(
                f"{path}.title å¿é¡»ä¸engineä¸è´ï¼ä½¿ç¨å¯¹åºAgentåç§°: {expected_title}"
            )
        inner = block.get("blocks")
        if not isinstance(inner, list) or not inner:
            errors.append(f"{path}.blocks å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for idx, sub_block in enumerate(inner):
            sub_path = f"{path}.blocks[{idx}]"
            if not isinstance(sub_block, dict):
                errors.append(f"{sub_path} å¿é¡»æ¯å¯¹è±?)
                continue
            if sub_block.get("type") != "paragraph":
                errors.append(f"{sub_path}.type ä»åè®?paragraph")
                continue
            # å¤ç¨ paragraph ç»ææ ¡éªï¼ä½éå¶ marks
            inlines = sub_block.get("inlines")
            if not isinstance(inlines, list) or not inlines:
                errors.append(f"{sub_path}.inlines å¿é¡»æ¯éç©ºæ°ç»?)
                continue
            for ridx, run in enumerate(inlines):
                self._validate_inline_run(run, f"{sub_path}.inlines[{ridx}]", errors)
                if not isinstance(run, dict):
                    continue
                marks = run.get("marks") or []
                if not isinstance(marks, list):
                    errors.append(f"{sub_path}.inlines[{ridx}].marks å¿é¡»æ¯æ°ç»?)
                    continue
                for midx, mark in enumerate(marks):
                    mark_type = mark.get("type") if isinstance(mark, dict) else None
                    if mark_type not in {"bold", "italic"}:
                        errors.append(
                            f"{sub_path}.inlines[{ridx}].marks[{midx}].type ä»åè®?bold/italic"
                        )

    def _validate_callout_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """calloutéå£°ætoneï¼å¹¶è³å°æä¸ä¸ªå­block"""
        tone = block.get("tone")
        if tone not in {"info", "warning", "success", "danger"}:
            errors.append(f"{path}.tone åå¼éæ³? {tone}")
        blocks = block.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{path}.blocks å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for idx, sub_block in enumerate(blocks):
            self._validate_block(sub_block, f"{path}.blocks[{idx}]", errors)

    def _validate_kpiGrid_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """KPIå¡éè¦éç©ºitemsï¼æ¯é¡¹åå«label/value"""
        items = block.get("items")
        if not isinstance(items, list) or not items:
            errors.append(f"{path}.items å¿é¡»æ¯éç©ºæ°ç»?)
            return
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{path}.items[{idx}] å¿é¡»æ¯å¯¹è±?)
                continue
            if "label" not in item or "value" not in item:
                errors.append(f"{path}.items[{idx}] éè¦labelä¸value")

    def _validate_widget_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """widgetå¿é¡»å£°æwidgetId/typeï¼å¹¶æä¾æ°æ®ææ°æ®å¼ç?""
        if "widgetId" not in block:
            errors.append(f"{path}.widgetId ç¼ºå¤±")
        if "widgetType" not in block:
            errors.append(f"{path}.widgetType ç¼ºå¤±")
        if "data" not in block and "dataRef" not in block:
            errors.append(f"{path} éè¦?data æ?dataRef å¶ä¸")

    def _validate_code_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """code blockè³å°è¦æcontent"""
        if "content" not in block:
            errors.append(f"{path}.content ç¼ºå¤±")

    def _validate_math_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """æ°å­¦åè¦æ±latexå­æ®µ"""
        if "latex" not in block:
            errors.append(f"{path}.latex ç¼ºå¤±")

    def _validate_figure_block(
        self, block: Dict[str, Any], path: str, errors: List[str]
    ):
        """figureéè¦imgå¯¹è±¡ä¸è³å°å¸¦src"""
        img = block.get("img")
        if not isinstance(img, dict):
            errors.append(f"{path}.img å¿é¡»æ¯å¯¹è±?)
            return
        if "src" not in img:
            errors.append(f"{path}.img.src ç¼ºå¤±")

    def _validate_inline_run(
        self, run: Any, path: str, errors: List[str]
    ):
        """æ ¡éªparagraphä¸­çinline runä¸marksåæ³æ?""
        if not isinstance(run, dict):
            errors.append(f"{path} å¿é¡»æ¯å¯¹è±?)
            return
        if "text" not in run:
            errors.append(f"{path}.text ç¼ºå¤±")
        marks = run.get("marks", [])
        if marks is None:
            return
        if not isinstance(marks, list):
            errors.append(f"{path}.marks å¿é¡»æ¯æ°ç»?)
            return
        for m_idx, mark in enumerate(marks):
            if not isinstance(mark, dict):
                errors.append(f"{path}.marks[{m_idx}] å¿é¡»æ¯å¯¹è±?)
                continue
            m_type = mark.get("type")
            if m_type not in ALLOWED_INLINE_MARKS:
                errors.append(f"{path}.marks[{m_idx}].type ä¸è¢«æ¯æ: {m_type}")

    def _validate_toc_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """TOCåºåæ·±åº¦éå?-4ä¹é´"""
        depth = block.get("depth")
        if depth is not None and not (isinstance(depth, int) and 1 <= depth <= 4):
            errors.append(f"{path}.depth å¿é¡»æ?å?ä¹é´çæ´æ?)

    def _validate_citationList_block(self, block: Dict[str, Any], path: str, errors: List[str]):
        """å¼ç¨æ¸åæ ¡éª"""
        items = block.get("items")
        if not isinstance(items, list):
            errors.append(f"{path}.items å¿é¡»æ¯æ°ç»?)
            return
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"{path}.items[{i}] å¿é¡»æ¯å¯¹è±?)
                continue
            if "index" not in item or "title" not in item or "url" not in item:
                errors.append(f"{path}.items[{i}] å¿é¡»åå« index, title, url")


__all__ = ["IRValidator"]
