ï»¿from __future__ import annotations

import json
from typing import Any, Dict, List

from loguru import logger

from backend.engines.report.utils.chart_review_service import get_chart_review_service


class MarkdownRenderer:
    """
    ï¿½?Document IR è½¬ä¸º Markdownï¿½?

    - å¾è¡¨ä¸è¯äºç»ä¸éçº§ä¸ºæ°æ®è¡¨æ ¼ï¼é¿åä¸¢å¤±å³é®ä¿¡æ¯ï¿½?
    - å°½éä¿çéç¨ç¹æ§ï¼æ é¢ãåè¡¨ãä»£ç ãè¡¨æ ¼ãå¼ç¨ç­ï¼ï¼
    - å¯¹ä¸å¸¸è§ç¹æ§ï¼callout/kpiGrid/engineQuoteç­ï¼ä½¿ç¨è¿ä¼¼æ¿æ¢ï¿½?
    """

    def __init__(self) -> None:
        self.document: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}

    def render(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: str | None = None
    ) -> str:
        """
        å¥å£ï¼å°IRè½¬æ¢ä¸ºMarkdownå­ç¬¦ä¸²ï¿½?

        åæ°:
            document_ir: Document IR æ°æ®
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­

        è¿å:
            str: Markdown å­ç¬¦ï¿½?
        """
        self.document = document_ir or {}

        # ä½¿ç¨ç»ä¸ï¿½?ChartReviewService è¿è¡å¾è¡¨å®¡æ¥ä¸ä¿®ï¿½?
        # è½ç¶ Markdown æ¸²ææ¶å¾è¡¨ä¼éçº§ä¸ºè¡¨æ ¼ï¼ä½ä»éç¡®ä¿æ°æ®ææ
        # review_document è¿åæ¬æ¬¡ä¼è¯çç»è®¡ä¿¡æ¯ï¼çº¿ç¨å®å¨ï¼æ­¤å¤ä¸ä½¿ç¨ï¿½?
        chart_service = get_chart_review_service()
        _ = chart_service.review_document(
            self.document,
            ir_file_path=ir_file_path,
            reset_stats=True,
            save_on_repair=bool(ir_file_path)
        )

        self.metadata = self.document.get("metadata", {}) or {}

        parts: List[str] = []
        title = self.metadata.get("title") or self.metadata.get("query") or "æ¥å"
        if title:
            parts.append(f"# {self._escape_text(title)}")
            parts.append("")

        for chapter in self.document.get("chapters", []) or []:
            chapter_md = self._render_chapter(chapter)
            if chapter_md:
                parts.append(chapter_md)

        return "\n".join(part for part in parts if part is not None).strip()

    # ===== ç« èä¸åçº§æ¸²ï¿½?=====

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        lines: List[str] = []
        title = chapter.get("title") or chapter.get("chapterId")
        blocks = chapter.get("blocks", []) if isinstance(chapter.get("blocks"), list) else []

        # ç« èæ é¢ä½¿ç¨ä¸çº§æ é¢æ ¼å¼ï¼å¹¶é¿åä¸é¦ä¸ªheadingéå¤
        if title:
            lines.append(f"# {self._escape_text(title)}")
            lines.append("")

        if blocks and self._is_heading_duplicate(blocks[0], title):
            blocks = blocks[1:]

        body = self._render_blocks(blocks)
        if body:
            lines.append(body)
        return "\n".join(lines).strip()

    def _render_blocks(self, blocks: List[Dict[str, Any]] | None, join_with_blank: bool = True) -> str:
        rendered: List[str] = []
        for block in blocks or []:
            md = self._render_block(block)
            if md is None:
                continue
            md = md.strip()
            if md:
                rendered.append(md)
        if not rendered:
            return ""
        separator = "\n\n" if join_with_blank else "\n"
        return separator.join(rendered)

    def _render_block(self, block: Any) -> str:
        if block is None:
            return ""
        if isinstance(block, str):
            return self._escape_text(block)
        if not isinstance(block, dict):
            return ""

        block_type = block.get("type") or ("paragraph" if block.get("inlines") else None)
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "list": self._render_list,
            "table": self._render_table,
            "swotTable": self._render_swot_table,
            "pestTable": self._render_pest_table,
            "blockquote": self._render_blockquote,
            "engineQuote": self._render_engine_quote,
            "hr": lambda b: "---",
            "code": self._render_code,
            "math": self._render_math,
            "figure": self._render_figure,
            "callout": self._render_callout,
            "kpiGrid": self._render_kpi_grid,
            "widget": self._render_widget,
            "toc": lambda b: "",
            "citationList": self._render_citation_list,
        }
        if block_type in handlers:
            return handlers[block_type](block)

        if isinstance(block.get("blocks"), list):
            return self._render_blocks(block["blocks"])

        return self._fallback_unknown(block)

    def _render_heading(self, block: Dict[str, Any]) -> str:
        level = block.get("level", 2)
        level = max(1, min(6, level))
        hashes = "#" * level
        text = block.get("text") or ""
        subtitle = block.get("subtitle")
        subtitle_text = f" _{self._escape_text(subtitle)}_" if subtitle else ""
        heading_line = f"{hashes} {self._escape_text(text)}{subtitle_text}"
        # ç« èåçä¸çº§æ é¢åé¢å¤æå¥ä¸ä¸ªç©ºè¡ï¼ä¸å½±åææ¡£é¢ç®ï¼
        if level == 1:
            return f"\n\n\n\n\n{heading_line}"
        return heading_line

    def _render_paragraph(self, block: Dict[str, Any]) -> str:
        inlines = block.get("inlines", [])
        # æ£æµå¹¶è·³è¿åå«ææ¡£åæ°ï¿½?JSON çæ®µï¿½?
        if self._is_metadata_paragraph(inlines):
            return ""
        return self._render_inlines(inlines)

    def _is_metadata_paragraph(self, inlines: List[Any]) -> bool:
        """
        æ£æµæ®µè½æ¯å¦åªåå«ææ¡£åæ°ï¿½?JSONï¿½?
        
        æäº LLM çæçåå®¹ä¼å°åæ°æ®ï¼å¦ xrefsidgetsootnotesetadataï¿½?
        éè¯¯å°ä½ä¸ºæ®µè½åå®¹è¾åºï¼æ¬æ¹æ³è¯å«å¹¶æ è®°è¿ç§æåµä»¥ä¾¿è·³è¿æ¸²æï¿½?
        """
        if not inlines or len(inlines) != 1:
            return False
        first = inlines[0]
        if not isinstance(first, dict):
            return False
        text = first.get("text", "")
        if not isinstance(text, str):
            return False
        text = text.strip()
        if not text.startswith("{") or not text.endswith("}"):
            return False
        # æ£æµå¸åçåæ°æ®é®
        metadata_indicators = ['"xrefs"', '"widgets"', '"footnotes"', '"metadata"', '"sectionBudgets"']
        return any(indicator in text for indicator in metadata_indicators)

    def _render_list(self, block: Dict[str, Any]) -> str:
        list_type = block.get("listType", "bullet")
        items = block.get("items") or []
        lines: List[str] = []
        for idx, item_blocks in enumerate(items):
            prefix = "-"
            if list_type == "ordered":
                prefix = f"{idx + 1}."
            elif list_type == "task":
                prefix = "- [ ]"
            content = self._render_blocks(item_blocks, join_with_blank=False)
            if not content:
                continue
            content_lines = content.splitlines() or [""]
            first = content_lines[0]
            lines.append(f"{prefix} {first}")
            for cont in content_lines[1:]:
                lines.append(f"  {cont}")
        return "\n".join(lines)

    def _flatten_nested_cells(self, cells: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        å±å¹³éè¯¯åµå¥çååæ ¼ç»æï¿½?

        æäº LLM çæçè¡¨æ ¼æ°æ®ä¸­ï¼ååæ ¼è¢«éè¯¯å°éå½åµå¥ï¿½?
        cells[0] æ­£å¸¸, cells[1].cells[0] æ­£å¸¸, cells[1].cells[1].cells[0] æ­£å¸¸...
        æ¬æ¹æ³å°è¿ç§åµå¥ç»æå±å¹³ä¸ºæ åçå¹³è¡ååæ ¼æ°ç»ï¿½?

        åæ°:
            cells: å¯è½åå«åµå¥ç»æçååæ ¼æ°ç»ï¿½?

        è¿å:
            List[Dict]: å±å¹³åçååæ ¼æ°ç»ï¿½?
        """
        if not cells:
            return []

        flattened: List[Dict[str, Any]] = []

        def _extract_cells(cell_or_list: Any) -> None:
            """éå½æåææååæ ¼"""
            if not isinstance(cell_or_list, dict):
                return

            # å¦æå½åå¯¹è±¡ï¿½?blocksï¼è¯´æå®æ¯ä¸ä¸ªææçååï¿½?
            if "blocks" in cell_or_list:
                # åå»ºååæ ¼å¯æ¬ï¼ç§»é¤åµå¥ï¿½?cells
                clean_cell = {
                    k: v for k, v in cell_or_list.items()
                    if k != "cells"
                }
                flattened.append(clean_cell)

            # å¦æå½åå¯¹è±¡æåµå¥ç cellsï¼éå½å¤ç
            nested_cells = cell_or_list.get("cells")
            if isinstance(nested_cells, list):
                for nested_cell in nested_cells:
                    _extract_cells(nested_cell)

        for cell in cells:
            _extract_cells(cell)

        return flattened

    def _fix_nested_table_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        ä¿®å¤åµå¥éè¯¯çè¡¨æ ¼è¡ç»æï¿½?

        æäº LLM çæçè¡¨æ ¼æ°æ®ä¸­ï¼ææè¡çååæ ¼é½è¢«åµå¥å¨ç¬¬ä¸è¡ä¸­ï¿½?
        å¯¼è´è¡¨æ ¼åªæ1è¡ä½åå«æææ°æ®ãæ¬æ¹æ³æ£æµå¹¶ä¿®å¤è¿ç§æåµï¿½?

        åæ°:
            rows: åå§çè¡¨æ ¼è¡æ°ç»ï¿½?

        è¿å:
            List[Dict]: ä¿®å¤åçè¡¨æ ¼è¡æ°ç»ï¿½?
        """
        if not rows or len(rows) != 1:
            # åªå¤çåªï¿½?è¡çå¼å¸¸æåµ
            return rows

        first_row = rows[0]
        original_cells = first_row.get("cells", [])

        # æ£æ¥æ¯å¦å­å¨åµå¥ç»ï¿½?
        has_nested = any(
            isinstance(cell.get("cells"), list)
            for cell in original_cells
            if isinstance(cell, dict)
        )

        if not has_nested:
            return rows

        # å±å¹³ææååæ ¼
        all_cells = self._flatten_nested_cells(original_cells)

        if len(all_cells) <= 2:
            # ååæ ¼å¤ªå°ï¼ä¸éè¦éï¿½?
            return rows

        # è¾å©å½æ°ï¼è·åååæ ¼ææ¬
        def _get_cell_text(cell: Dict[str, Any]) -> str:
            """è·åååæ ¼çææ¬åå®¹"""
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
            """å¤æ­ååæ ¼æ¯å¦æ¯å ä½ç¬¦ï¼ï¿½?'--', '-', 'ï¿½? ç­ï¼"""
            text = _get_cell_text(cell)
            return text in ("--", "-", "ï¿½?, "-ï¿½?, "", "N/A", "n/a")

        # åè¿æ»¤æå ä½ç¬¦ååæ ¼
        all_cells = [c for c in all_cells if not _is_placeholder_cell(c)]

        if len(all_cells) <= 2:
            return rows

        # æ£æµè¡¨å¤´åæ°ï¼æ¥æ¾å¸¦æ bold æ è®°æå¸åè¡¨å¤´è¯çååæ ¼
        def _is_header_cell(cell: Dict[str, Any]) -> bool:
            """å¤æ­ååæ ¼æ¯å¦åè¡¨å¤´ï¼æå ç²æ è®°ææ¯å¸åè¡¨å¤´è¯ï¼"""
            blocks = cell.get("blocks", [])
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "paragraph":
                    inlines = block.get("inlines", [])
                    for inline in inlines:
                        if isinstance(inline, dict):
                            marks = inline.get("marks", [])
                            if any(isinstance(m, dict) and m.get("type") == "bold" for m in marks):
                                return True
            # ä¹æ£æ¥å¸åçè¡¨å¤´ï¿½?
            text = _get_cell_text(cell)
            header_keywords = {
                "æ¶é´", "æ¥æ", "åç§°", "ç±»å", "ç¶ï¿½?, "æ°é", "éé¢", "æ¯ä¾", "ææ ",
                "å¹³å°", "æ¸ é", "æ¥æº", "æè¿°", "è¯´æ", "å¤æ³¨", "åºå·", "ç¼å·",
                "äºä»¶", "å³é®", "æ°æ®", "æ¯æ", "ååº", "å¸åº", "ææ", "èç¹",
                "ç»´åº¦", "è¦ç¹", "è¯¦æ", "æ ç­¾", "å½±å", "è¶å¿", "æé", "ç±»å«",
                "ä¿¡æ¯", "åå®¹", "é£æ ¼", "åå¥½", "ä¸»è¦", "ç¨æ·", "æ ¸å¿", "ç¹å¾",
                "åç±»", "èå´", "å¯¹è±¡", "é¡¹ç®", "é¶æ®µ", "å¨æ", "é¢ç", "ç­çº§",
            }
            return any(kw in text for kw in header_keywords) and len(text) <= 20

        # è®¡ç®è¡¨å¤´åæ°ï¼ç»è®¡è¿ç»­çè¡¨å¤´ååæ ¼æ°ï¿½?
        header_count = 0
        for cell in all_cells:
            if _is_header_cell(cell):
                header_count += 1
            else:
                # éå°ç¬¬ä¸ä¸ªéè¡¨å¤´ååæ ¼ï¼è¯´ææ°æ®åºå¼ï¿½?
                break

        # å¦ææ²¡ææ£æµå°è¡¨å¤´ï¼å°è¯ä½¿ç¨å¯åå¼æ¹æ³
        if header_count == 0:
            # åè®¾åæ°ï¿½?4 ï¿½?5ï¼å¸¸è§çè¡¨æ ¼åæ°ï¿½?
            total = len(all_cells)
            for possible_cols in [4, 5, 3, 6, 2]:
                if total % possible_cols == 0:
                    header_count = possible_cols
                    break
            else:
                # å°è¯æ¾å°ææ¥è¿çè½æ´é¤çåï¿½?
                for possible_cols in [4, 5, 3, 6, 2]:
                    remainder = total % possible_cols
                    # åè®¸æï¿½?ä¸ªå¤ä½çååæ ¼ï¼å¯è½æ¯å°¾é¨çæ»ç»ææ³¨éï¼
                    if remainder <= 3:
                        header_count = possible_cols
                        break
                else:
                    # æ æ³ç¡®å®åæ°ï¼è¿ååå§æ°ï¿½?
                    return rows

        # è®¡ç®ææçååæ ¼æ°éï¼å¯è½éè¦æªæ­å°¾é¨å¤ä½çååæ ¼ï¼
        total = len(all_cells)
        remainder = total % header_count
        if remainder > 0 and remainder <= 3:
            # æªæ­å°¾é¨å¤ä½çååæ ¼ï¼å¯è½æ¯æ»ç»ææ³¨éï¼
            all_cells = all_cells[:total - remainder]
        elif remainder > 3:
            # ä½æ°å¤ªå¤§ï¼å¯è½åæ°æ£æµéè¯¯ï¼è¿ååå§æ°æ®
            return rows

        # éæ°ç»ç»æå¤ï¿½?
        fixed_rows: List[Dict[str, Any]] = []
        for i in range(0, len(all_cells), header_count):
            row_cells = all_cells[i:i + header_count]
            # æ è®°ç¬¬ä¸è¡ä¸ºè¡¨å¤´
            if i == 0:
                for cell in row_cells:
                    cell["header"] = True
            fixed_rows.append({"cells": row_cells})

        return fixed_rows

    def _render_table(self, block: Dict[str, Any]) -> str:
        raw_rows = block.get("rows") or []
        if not raw_rows:
            return ""

        # åä¿®å¤å¯è½å­å¨çåµå¥è¡ç»æé®ï¿½?
        rows = self._fix_nested_table_rows(raw_rows)

        header_cells: List[str] = []
        body_rows: List[List[str]] = []

        # å±å¹³å¯è½å­å¨çåµå¥ååæ ¼ç»æï¼ä½ä¸ºé¢å¤ä¿æ¤ï¼
        first_row_cells_raw = rows[0].get("cells") if isinstance(rows[0], dict) else None
        first_row_cells = self._flatten_nested_cells(first_row_cells_raw) if first_row_cells_raw else None

        # æ£æµé¦è¡æ¯å¦å£°æä¸ºè¡¨å¤´
        has_header = bool(first_row_cells and any(cell.get("header") or cell.get("isHeader") for cell in first_row_cells))

        # è®¡ç®æå¤§åæ°ï¼å¿½ç¥rowspan
        col_count = 0
        for row in rows:
            cells_raw = row.get("cells") if isinstance(row, dict) else None
            cells = self._flatten_nested_cells(cells_raw) if cells_raw else []
            span = 0
            for cell in cells:
                span += int(cell.get("colspan") or 1)
            col_count = max(col_count, span)

        if has_header and first_row_cells:
            header_cells = [self._render_cell_content(cell) for cell in first_row_cells]
            rows = rows[1:]
        else:
            header_cells = [f"å{idx + 1}" for idx in range(col_count or (len(first_row_cells or []) or 1))]

        for row in rows:
            if not isinstance(row, dict):
                continue
            cells_raw = row.get("cells") or []
            # å±å¹³å¯è½å­å¨çåµå¥ååæ ¼ç»æ
            cells = self._flatten_nested_cells(cells_raw)
            row_cells: List[str] = []
            for cell in cells:
                text = self._render_cell_content(cell)
                span = int(cell.get("colspan") or 1)
                row_cells.append(text)
                if span > 1:
                    row_cells.extend([""] * (span - 1))
            while len(row_cells) < len(header_cells):
                row_cells.append("")
            body_rows.append(row_cells[: len(header_cells)])

        lines = [
            self._markdown_row(header_cells),
            self._markdown_separator(len(header_cells)),
        ]
        for row in body_rows:
            lines.append(self._markdown_row(row))
        return "\n".join(lines)

    def _render_swot_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "SWOT åæ"
        summary = block.get("summary")
        quadrants = [
            ("strengths", "S ä¼å¿"),
            ("weaknesses", "W å£å¿"),
            ("opportunities", "O æºä¼"),
            ("threats", "T å¨è"),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in quadrants:
            items = self._normalize_swot_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> ææ æ°æ®")
                continue
            table_lines = [
                self._markdown_row(["åºå·", "è¦ç¹", "è¯¦æ", "æ ç­¾"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or item.get("evidence") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "æªå½åè¦ï¿½?, for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_pest_table(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or "PEST åæ"
        summary = block.get("summary")
        dimensions = [
            ("political", "P æ¿æ²»"),
            ("economic", "E ç»æµ"),
            ("social", "S ç¤¾ä¼"),
            ("technological", "T æï¿½?),
        ]

        lines = [f"### {self._escape_text(title)}"]
        if summary:
            lines.append(self._escape_text(summary))

        for key, label in dimensions:
            items = self._normalize_pest_items(block.get(key))
            lines.append(f"#### {label}")
            if not items:
                lines.append("> ææ æ°æ®")
                continue
            table_lines = [
                self._markdown_row(["åºå·", "è¦ç¹", "è¯¦æ", "æ ç­¾"]),
                self._markdown_separator(4),
            ]
            for idx, item in enumerate(items, start=1):
                tags = [val for val in (item.get("impact"), item.get("weight"), item.get("priority")) if val]
                tag_text = " / ".join(self._escape_text(t) for t in tags) or ""
                detail = item.get("detail") or item.get("description") or ""
                table_lines.append(
                    self._markdown_row([
                        str(idx),
                        self._escape_text(item.get("title") or "æªå½åè¦ï¿½?, for_table=True),
                        self._escape_text(detail, for_table=True),
                        self._escape_text(tag_text, for_table=True),
                    ])
                )
            lines.append("\n".join(table_lines))
        return "\n\n".join(lines)

    def _render_blockquote(self, block: Dict[str, Any]) -> str:
        inner = self._render_blocks(block.get("blocks", []))
        return self._quote_lines(inner)

    def _render_engine_quote(self, block: Dict[str, Any]) -> str:
        title = block.get("title") or block.get("engine") or "å¼ç¨"
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}**"
        return self._quote_lines(f"{header}\n{inner}" if inner else header)

    def _render_code(self, block: Dict[str, Any]) -> str:
        lang = block.get("lang") or ""
        content = block.get("content") or ""
        return f"```{lang}\n{content}\n```"

    def _render_math(self, block: Dict[str, Any]) -> str:
        latex = self._normalize_math(block.get("latex", ""))
        if not latex:
            return ""
        return f"$$\n{latex}\n$$"

    def _render_figure(self, block: Dict[str, Any]) -> str:
        caption = block.get("caption") or "å¾ååå®¹å ä½"
        return f"> ![å¾ç¤ºå ä½]({''}) {self._escape_text(caption)}"

    def _render_callout(self, block: Dict[str, Any]) -> str:
        tone = block.get("tone") or "info"
        title = block.get("title")
        inner = self._render_blocks(block.get("blocks", []))
        header = f"**{self._escape_text(title)}** [{tone}]" if title else f"[{tone}]"
        content = header if not inner else f"{header}\n{inner}"
        return self._quote_lines(content)

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        items = block.get("items") or []
        if not items:
            return ""
        header = ["ææ ", "æ°ï¿½?, "åå"]
        lines = [self._markdown_row(header), self._markdown_separator(len(header))]
        for item in items:
            label = item.get("label") or ""
            value = f"{item.get('value', '')}{item.get('unit') or ''}"
            delta = self._format_delta(item.get("delta"), item.get("deltaTone"))
            lines.append(self._markdown_row([
                self._escape_text(label, for_table=True),
                self._escape_text(value, for_table=True),
                self._escape_text(delta, for_table=True),
            ]))
        return "\n".join(lines)

    def _render_widget(self, block: Dict[str, Any]) -> str:
        widget_type = (block.get("widgetType") or "").lower()
        title = block.get("title") or (block.get("props", {}) or {}).get("title")
        title_prefix = f"**{self._escape_text(title)}**\n\n" if title else ""

        if widget_type.startswith("chart.js"):
            chart_table = self._render_chart_as_table(block)
            return f"{title_prefix}{chart_table}".strip()
        if "wordcloud" in widget_type:
            cloud_table = self._render_wordcloud_as_table(block)
            return f"{title_prefix}{cloud_table}".strip()

        data_preview = ""
        try:
            data_preview = json.dumps(block.get("data") or {}, ensure_ascii=False)[:200]
        except Exception:
            data_preview = ""
        note = "> æ°æ®ç»ä»¶æä¸æ¯æMarkdownæ¸²æ"
        return f"{title_prefix}{note}" + (f"\n\n```\n{data_preview}\n```" if data_preview else "")

    def _render_citation_list(self, block: Dict[str, Any]) -> str:
        """æ¸²æææ«å¼ç¨ä¿¡æ¯æºåè¡¨ä¸ºMarkdown"""
        items = block.get("items", [])
        if not items:
            return ""

        # å»éé»è¾ï¼åºï¿½?URL ï¿½?title è¿è¡å»é
        unique_items = []
        seen_urls = set()
        seen_titles = set()
        for item in items:
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            
            if url and url in seen_urls:
                continue
            if not url and title and title in seen_titles:
                continue
                
            if url:
                seen_urls.add(url)
            if title:
                seen_titles.add(title)
                
            item["index"] = len(unique_items) + 1
            unique_items.append(item)

        lines = [
            "---",
            "### åèèµï¿½?/ å¼ç¨æ¥æº",
            ""
        ]

        for item in unique_items:
            index = item.get("index", "")
            title = self._escape_text(item.get("title", ""))
            url = item.get("url", "")
            source = self._escape_text(item.get("source", ""))
            pub_date = self._escape_text(item.get("publishedAt", ""))

            source_text = f" - {source}" if source else ""
            date_text = f" ({pub_date})" if pub_date else ""

            if url:
                if url.startswith("seed://"):
                    seed_id = url.split("seed://")[1].split("/")[0] if "seed://" in url else ""
                    lines.append(f"{index}. [{title}](/api/report/seed/{seed_id}){source_text}{date_text} `[å¨çº¿é¢è§éä»¶]`")
                elif url.startswith("file:///"):
                    lines.append(f"{index}. ~{title}~{source_text}{date_text} `[æ¬å°éä»¶æ æ³ç´æ¥é¢è§]`")
                else:
                    lines.append(f"{index}. [{title}]({url}){source_text}{date_text}")
            else:
                lines.append(f"{index}. {title}{source_text}{date_text}")

        return "\n".join(lines)

    # ===== å·¥å·æ¹æ³ =====

    def _render_chart_as_table(self, block: Dict[str, Any]) -> str:
        data = self._coerce_chart_data(block.get("data") or {})
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return "> å¾è¡¨æ°æ®ç¼ºå¤±ï¼æ æ³è½¬ä¸ºè¡¨ï¿½?

        headers = ["ç±»å«"] + [
            ds.get("label") or f"ç³»å{idx + 1}"
            for idx, ds in enumerate(datasets)
        ]
        lines = [self._markdown_row(headers), self._markdown_separator(len(headers))]
        for idx, label in enumerate(labels):
            row_cells = [self._escape_text(self._stringify_value(label), for_table=True)]
            for ds in datasets:
                series = ds.get("data") or []
                value = series[idx] if idx < len(series) else ""
                row_cells.append(self._escape_text(self._stringify_value(value), for_table=True))
            lines.append(self._markdown_row(row_cells))
        return "\n".join(lines)

    def _render_wordcloud_as_table(self, block: Dict[str, Any]) -> str:
        items = self._collect_wordcloud_items(block)
        if not items:
            return "> è¯äºæ°æ®ç¼ºå¤±ï¼æ æ³è½¬ä¸ºè¡¨ï¿½?

        lines = [
            self._markdown_row(["å³é®ï¿½?, "æé", "ç±»å«"]),
            self._markdown_separator(3),
        ]
        for item in items:
            lines.append(
                self._markdown_row([
                    self._escape_text(item.get("word", ""), for_table=True),
                    self._escape_text(self._stringify_value(item.get("weight")), for_table=True),
                    self._escape_text(item.get("category", "") or "-", for_table=True),
                ])
            )
        return "\n".join(lines)

    def _render_cell_content(self, cell: Dict[str, Any]) -> str:
        blocks = cell.get("blocks") if isinstance(cell, dict) else None
        return self._render_blocks_as_text(blocks)

    def _render_blocks_as_text(self, blocks: List[Dict[str, Any]] | None) -> str:
        texts: List[str] = []
        for block in blocks or []:
            texts.append(self._render_block_as_text(block))
        return " ".join(filter(None, texts))

    def _render_block_as_text(self, block: Any) -> str:
        if isinstance(block, str):
            return self._escape_text(block, for_table=True)
        if not isinstance(block, dict):
            return ""
        block_type = block.get("type")
        if block_type == "paragraph":
            return self._render_inlines(block.get("inlines", []), for_table=True)
        if block_type == "heading":
            return self._escape_text(block.get("text") or "", for_table=True)
        if block_type == "list":
            items = []
            for sub in block.get("items") or []:
                items.append(self._render_blocks_as_text(sub))
            return "; ".join(filter(None, items))
        if block_type == "math":
            return f"${self._normalize_math(block.get('latex', ''))}$"
        if block_type == "code":
            return block.get("content", "") or ""
        if block_type == "widget":
            return self._escape_text(block.get("title") or "å¾è¡¨", for_table=True)
        if isinstance(block.get("blocks"), list):
            return self._render_blocks_as_text(block.get("blocks"))
        return self._escape_text(str(block), for_table=True)

    def _markdown_row(self, cells: List[str]) -> str:
        return "| " + " | ".join(cells) + " |"

    def _markdown_separator(self, count: int) -> str:
        return "| " + " | ".join(["---"] * max(1, count)) + " |"

    def _render_inlines(self, inlines: List[Any], for_table: bool = False) -> str:
        parts: List[str] = []
        for run in inlines or []:
            parts.append(self._render_inline_run(run, for_table=for_table))
        return "".join(parts)

    def _render_inline_run(self, run: Any, for_table: bool = False) -> str:
        if isinstance(run, dict):
            # å¤ç inlineRun ç±»åï¼åµå¥ç inlines æ°ç»
            if run.get("type") == "inlineRun":
                inner_inlines = run.get("inlines") or []
                outer_marks = run.get("marks") or []
                # éå½æ¸²æåé¨ï¿½?inlines
                inner_text = self._render_inlines(inner_inlines, for_table=for_table)
                # åºç¨å¤å±ï¿½?marks
                result = inner_text
                for mark in outer_marks:
                    result = self._apply_mark(result, mark)
                return result
            text = run.get("text", "")
            marks = run.get("marks") or []
        else:
            text = run if isinstance(run, str) else ""
            marks = []
        
        # å°è¯æ£æµå¹¶è§£æè¢«éè¯¯åºååä¸ºå­ç¬¦ä¸²ï¿½?inlineRun JSON
        if isinstance(text, str) and text.startswith('{"type": "inlineRun"'):
            parsed = self._try_parse_inline_run_string(text)
            if parsed:
                return self._render_inline_run(parsed, for_table=for_table)
        
        result = self._escape_text(text, for_table=for_table)
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            mtype = mark.get("type")
            if mtype == "bold":
                result = f"**{result}**"
            elif mtype == "italic":
                result = f"*{result}*"
            elif mtype == "underline":
                result = f"__{result}__"
            elif mtype == "strike":
                result = f"~~{result}~~"
            elif mtype == "code":
                result = f"`{result}`"
            elif mtype == "link":
                href = mark.get("href") or mark.get("value")
                href = str(href) if href else ""
                result = f"[{result}]({href})" if href else result
            elif mtype == "highlight":
                result = f"=={result}=="
            elif mtype == "subscript":
                result = f"~{result}~"
            elif mtype == "superscript":
                result = f"^{result}^"
            elif mtype == "math":
                latex = self._normalize_math(mark.get("value") or text)
                result = f"${latex}$" if latex else result
            # é¢è²/å­ä½ç­ééç¨æ è®°ç´æ¥éçº§ä¸ºçº¯ææ¬
        return result

    def _apply_mark(self, text: str, mark: Any) -> str:
        """
        å¯¹ææ¬åºç¨åï¿½?mark æ ¼å¼ï¿½?
        
        ç¨äºå¤ç inlineRun ç±»åçå¤ï¿½?marksï¿½?
        """
        if not isinstance(mark, dict):
            return text
        mtype = mark.get("type")
        if mtype == "bold":
            return f"**{text}**"
        elif mtype == "italic":
            return f"*{text}*"
        elif mtype == "underline":
            return f"__{text}__"
        elif mtype == "strike":
            return f"~~{text}~~"
        elif mtype == "code":
            return f"`{text}`"
        elif mtype == "link":
            href = mark.get("href") or mark.get("value")
            href = str(href) if href else ""
            return f"[{text}]({href})" if href else text
        elif mtype == "highlight":
            return f"=={text}=="
        elif mtype == "subscript":
            return f"~{text}~"
        elif mtype == "superscript":
            return f"^{text}^"
        elif mtype == "math":
            latex = self._normalize_math(mark.get("value") or text)
            return f"${latex}$" if latex else text
        return text

    def _try_parse_inline_run_string(self, text: str) -> dict | None:
        """
        å°è¯è§£æè¢«éè¯¯åºååä¸ºå­ç¬¦ä¸²ï¿½?inlineRun JSONï¿½?
        
        æäº LLM çæçåå®¹ä¼ï¿½?inlineRun ç»ææå¤å°ä½ä¸ºå­ç¬¦ä¸²
        å­å¥ text å­æ®µï¼æ¬æ¹æ³å°è¯è¯å«å¹¶è§£æè¿ç§æåµï¿½?
        
        åæ°:
            text: å¯è½åå« JSON çå­ç¬¦ä¸²
            
        è¿å:
            dict | None: è§£ææåè¿å inlineRun å­å¸ï¼å¦åè¿ï¿½?None
        """
        if not text or not isinstance(text, str):
            return None
        text = text.strip()
        if not text.startswith('{"type": "inlineRun"'):
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("type") == "inlineRun":
                return parsed
        except json.JSONDecodeError:
            pass
        return None

    def _is_heading_duplicate(self, block: Dict[str, Any], chapter_title: str | None) -> bool:
        """å¤æ­é¦ä¸ªheadingæ¯å¦ä¸ç« èæ é¢éï¿½?""
        if not isinstance(block, dict) or block.get("type") != "heading":
            return False
        if not chapter_title:
            return False
        heading_text = block.get("text") or ""
        return self._normalize_heading_text(heading_text) == self._normalize_heading_text(chapter_title)

    def _normalize_heading_text(self, text: Any) -> str:
        """å»é¤åºå·åç¼å¹¶ç»ä¸ç©ºç½"""
        if not isinstance(text, str):
            return ""
        stripped = text.strip()
        # å»æç±»ä¼¼ï¿½?."ãï¿½?.1"ä¸ãï¿½?
        for sep in (" ", "ï¿½?):
            if sep in stripped:
                maybe_prefix, rest = stripped.split(sep, 1)
                if self._looks_like_prefix(maybe_prefix):
                    stripped = rest.strip()
                    break
        else:
            parts = stripped.split(".", 1)
            if len(parts) == 2 and self._looks_like_prefix(parts[0]):
                stripped = parts[1].strip()
        return stripped

    @staticmethod
    def _looks_like_prefix(token: str) -> bool:
        """å¤æ­tokenæ¯å¦ååºå·åç¼"""
        if not token:
            return False
        if token.isdigit():
            return True
        chinese_numerals = set("ä¸äºä¸åäºå­ä¸å«ä¹åé¶ãå£¹è´°åèä¼éææçï¿½?)
        return all(ch in chinese_numerals or ch == "." for ch in token)

    def _quote_lines(self, text: str) -> str:
        if not text:
            return ""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            prefix = "> " if line else ">"
            lines.append(f"{prefix}{line}")
        return "\n".join(lines)

    def _normalize_swot_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                impact = entry.get("impact")
                priority = entry.get("priority")
                evidence = entry.get("evidence")
                items.append({
                    "title": title or "æªå½åè¦ï¿½?,
                    "detail": detail,
                    "impact": impact,
                    "priority": priority,
                    "evidence": evidence,
                })
        return items

    def _normalize_pest_items(self, raw: Any) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not raw:
            return items
        for entry in raw:
            if isinstance(entry, str):
                items.append({"title": entry})
            elif isinstance(entry, dict):
                title = entry.get("title") or entry.get("label") or entry.get("text")
                detail = entry.get("detail") or entry.get("description")
                items.append({
                    "title": title or "æªå½åè¦ï¿½?,
                    "detail": detail,
                    "impact": entry.get("impact"),
                    "priority": entry.get("priority"),
                    "weight": entry.get("weight"),
                })
        return items

    def _coerce_chart_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if "labels" in data or "datasets" in data:
            return data
        for key in ("data", "chartData", "payload"):
            nested = data.get(key)
            if isinstance(nested, dict) and ("labels" in nested or "datasets" in nested):
                return nested
        return data

    def _collect_wordcloud_items(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        props = block.get("props") or {}
        candidates: List[Any] = []
        for key in ("data", "words", "items"):
            value = props.get(key)
            if isinstance(value, list):
                candidates.append(value)
        data_field = block.get("data")
        if isinstance(data_field, list):
            candidates.append(data_field)
        elif isinstance(data_field, dict):
            if isinstance(data_field.get("items"), list):
                candidates.append(data_field.get("items"))
            if isinstance(data_field.get("words"), list):
                candidates.append(data_field.get("words"))

        items: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def push(word: str, weight: Any, category: str) -> None:
            key = f"{word}::{category}"
            if key in seen:
                return
            seen.add(key)
            items.append({"word": word, "weight": weight, "category": category})

        for candidate in candidates:
            for entry in candidate or []:
                if isinstance(entry, dict):
                    word = entry.get("word") or entry.get("text") or entry.get("label")
                    if not word:
                        continue
                    weight = entry.get("weight") or entry.get("value")
                    category = entry.get("category") or ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, (list, tuple)) and entry:
                    word = entry[0]
                    weight = entry[1] if len(entry) > 1 else ""
                    category = entry[2] if len(entry) > 2 else ""
                    push(str(word), weight, str(category))
                elif isinstance(entry, str):
                    push(entry, "", "")
        return items

    def _escape_text(self, text: Any, for_table: bool = False) -> str:
        if text is None:
            return ""
        value = str(text)
        if for_table:
            value = value.replace("|", r"\|").replace("\n", " ").replace("\r", " ")
        return value.strip()

    def _stringify_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, dict):
            # ä¼ååå¸¸è§æ°å¼å­ï¿½?
            for key in ("y", "value"):
                if key in value:
                    return str(value[key])
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        if isinstance(value, list):
            return ", ".join(self._stringify_value(v) for v in value)
        return str(value)

    def _normalize_math(self, raw: Any) -> str:
        if not isinstance(raw, str):
            return ""
        text = raw.strip()
        patterns = [
            ("$$", "$$"),
            ("\\[", "\\]"),
            ("\\(", "\\)"),
        ]
        for start, end in patterns:
            if text.startswith(start) and text.endswith(end):
                return text[len(start) : -len(end)].strip()
        return text

    def _format_delta(self, delta: Any, tone: Any) -> str:
        if delta is None:
            return ""
        prefix = ""
        tone_val = (tone or "").lower()
        if tone_val in ("up", "increase", "positive"):
            prefix = "ï¿½?"
        elif tone_val in ("down", "decrease", "negative"):
            prefix = "ï¿½?"
        return f"{prefix}{delta}"

    def _fallback_unknown(self, block: Dict[str, Any]) -> str:
        try:
            payload = json.dumps(block, ensure_ascii=False, indent=2)
        except Exception:
            payload = str(block)
        logger.debug(f"æªè¯å«çåºåç±»åï¼ä½¿ç¨JSONååº: {block}")
        return f"```json\n{payload}\n```"


__all__ = ["MarkdownRenderer"]
