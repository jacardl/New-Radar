"""
PDFå¸å±ä¼åå?

èªå¨åæåä¼åPDFå¸å±ï¼ç¡®ä¿åå®¹ä¸æº¢åºãæçç¾è§
æ¯æï¼?
- èªå¨è°æ´å­å·
- ä¼åè¡é´è·?
- è°æ´è²åå¤§å°
- æºè½æåä¿¡æ¯å?
- ä¿å­åå è½½ä¼åæ¹æ¡?
- ææ¬å®½åº¦æ£æµåæº¢åºé¢é²
- è²åè¾¹çæ£æµåèªå¨è°æ´
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger


@dataclass
class KPICardLayout:
    """KPIå¡çå¸å±éç½®"""
    font_size_value: int = 32  # æ°å¼å­å?
    font_size_label: int = 14  # æ ç­¾å­å·
    font_size_change: int = 13  # ååå¼å­å?
    padding: int = 20  # åè¾¹è·?
    min_height: int = 120  # æå°é«åº?
    value_max_length: int = 10  # æ°å¼æå¤§å­ç¬¦æ°ï¼è¶è¿åç¼©å°å­å·ï¼?


@dataclass
class CalloutLayout:
    """æç¤ºæ¡å¸å±éç½®"""
    font_size_title: int = 16  # æ é¢å­å·
    font_size_content: int = 14  # åå®¹å­å·
    padding: int = 20  # åè¾¹è·?
    line_height: float = 1.6  # è¡é«åæ°
    max_width: str = "100%"  # æå¤§å®½åº?


@dataclass
class TableLayout:
    """è¡¨æ ¼å¸å±éç½®"""
    font_size_header: int = 13  # è¡¨å¤´å­å·
    font_size_body: int = 12  # è¡¨ä½å­å·
    cell_padding: int = 12  # ååæ ¼åè¾¹è·
    max_cell_width: int = 200  # æå¤§ååæ ¼å®½åº¦ï¼åç´ ï¼
    overflow_strategy: str = "wrap"  # æº¢åºç­ç¥ï¼wrap(æ¢è¡) / ellipsis(çç¥å?


@dataclass
class ChartLayout:
    """å¾è¡¨å¸å±éç½®"""
    font_size_title: int = 16  # å¾è¡¨æ é¢å­å·
    font_size_label: int = 12  # æ ç­¾å­å·
    min_height: int = 300  # æå°é«åº?
    max_height: int = 600  # æå¤§é«åº?
    padding: int = 20  # åè¾¹è·?


@dataclass
class GridLayout:
    """ç½æ ¼å¸å±éç½®"""
    columns: int = 3  # æ¯è¡åæ°ï¼æ­£æé»è®¤ä¸åï¼
    gap: int = 20  # é´è·
    responsive_breakpoint: int = 768  # ååºå¼æ­ç¹ï¼å®½åº¦ï¼?


@dataclass
class DataBlockLayout:
    """æ°æ®åï¼è²åPIãè¡¨æ ¼ç­ï¼çç¼©æ¾éç½®"""
    overview_text_scale: float = 0.93  # æç« æ»è§æ°æ®åæå­ç¼©æ¾ï¼è½»å¾®ç¼©å°ï¼?
    overview_kpi_scale: float = 0.88  # æ»è§KPIç¼©æ¾
    body_text_scale: float = 0.8      # æ­£ææ°æ®åæå­ç¼©æ¾ï¼å¤§å¹ç¼©å°ï¼?
    body_kpi_scale: float = 0.76      # æ­£æKPIç¼©æ¾
    min_overview_font: int = 12       # æ»è§æå°å­å?
    min_body_font: int = 11           # æ­£ææå°å­å?


@dataclass
class PageLayout:
    """é¡µé¢æ´ä½å¸å±éç½®"""
    font_size_base: int = 14  # åºç¡å­å·
    font_size_h1: int = 28  # ä¸çº§æ é¢?
    font_size_h2: int = 24  # äºçº§æ é¢
    font_size_h3: int = 20  # ä¸çº§æ é¢
    font_size_h4: int = 16  # åçº§æ é¢
    line_height: float = 1.6  # è¡é«åæ°
    paragraph_spacing: int = 16  # æ®µè½é´è·
    section_spacing: int = 32  # ç« èé´è·
    page_padding: int = 40  # é¡µé¢è¾¹è·
    max_content_width: int = 800  # æå¤§åå®¹å®½åº?


@dataclass
class PDFLayoutConfig:
    """å®æ´çPDFå¸å±éç½®"""
    page: PageLayout
    kpi_card: KPICardLayout
    callout: CalloutLayout
    table: TableLayout
    chart: ChartLayout
    grid: GridLayout
    data_block: DataBlockLayout

    # ä¼åç­ç¥éç½®
    auto_adjust_font_size: bool = True  # èªå¨è°æ´å­å·
    auto_adjust_grid_columns: bool = True  # èªå¨è°æ´ç½æ ¼åæ°
    prevent_orphan_headers: bool = True  # é²æ­¢æ é¢å­¤è¡
    optimize_for_print: bool = True  # æå°ä¼å

    def to_dict(self) -> Dict[str, Any]:
        """è½¬æ¢ä¸ºå­å?""
        return {
            'page': asdict(self.page),
            'kpi_card': asdict(self.kpi_card),
            'callout': asdict(self.callout),
            'table': asdict(self.table),
            'chart': asdict(self.chart),
            'grid': asdict(self.grid),
            'data_block': asdict(self.data_block),
            'auto_adjust_font_size': self.auto_adjust_font_size,
            'auto_adjust_grid_columns': self.auto_adjust_grid_columns,
            'prevent_orphan_headers': self.prevent_orphan_headers,
            'optimize_for_print': self.optimize_for_print,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PDFLayoutConfig:
        """ä»å­å¸åå»ºéç½?""
        return cls(
            page=PageLayout(**data['page']),
            kpi_card=KPICardLayout(**data['kpi_card']),
            callout=CalloutLayout(**data['callout']),
            table=TableLayout(**data['table']),
            chart=ChartLayout(**data['chart']),
            grid=GridLayout(**data['grid']),
            data_block=DataBlockLayout(**data.get('data_block', {})),
            auto_adjust_font_size=data.get('auto_adjust_font_size', True),
            auto_adjust_grid_columns=data.get('auto_adjust_grid_columns', True),
            prevent_orphan_headers=data.get('prevent_orphan_headers', True),
            optimize_for_print=data.get('optimize_for_print', True),
        )


class PDFLayoutOptimizer:
    """
    PDFå¸å±ä¼åå?

    æ ¹æ®åå®¹ç¹å¾èªå¨ä¼åPDFå¸å±ï¼é²æ­¢æº¢åºåæçé®é¢
    """

    # å­ç¬¦å®½åº¦ä¼°ç®ç³»æ°ï¼åºäºå¸¸è§ä¸­æå­ä½ï¼
    # ä¸­æå­ç¬¦éå¸¸æ¯ç­å®½çï¼çº¦ç­äºå­å·çåç´ å?
    # è±æåæ°å­çº¦ä¸ºå­å·ç0.5-0.6å?
    # æ´æ°ï¼ä½¿ç¨æ´ç²¾ç¡®çç³»æ°ä»¥æ´å¥½å°é¢æµæº¢å?
    CHAR_WIDTH_FACTOR = {
        'chinese': 1.05,     # ä¸­æå­ç¬¦ï¼ç¥å¾®å¢å ä»¥ç¡®ä¿å®å¨è¾¹çï¼?
        'english': 0.58,     # è±æå­æ¯
        'number': 0.65,      # æ°å­ï¼æ°å­éå¸¸æ¯å­æ¯ç¨å®½ï¼
        'symbol': 0.45,      # ç¬¦å·
        'percent': 0.7,      # ç¾åå·ç­ç¹æ®ç¬¦å·
    }

    def __init__(self, config: Optional[PDFLayoutConfig] = None):
        """
        åå§åä¼åå¨

        åæ°:
            config: å¸å±éç½®ï¼å¦æä¸ºNoneåä½¿ç¨é»è®¤éç½?
        """
        self.config = config or self._create_default_config()
        self.optimization_log = []

    @staticmethod
    def _create_default_config() -> PDFLayoutConfig:
        """åå»ºé»è®¤éç½®"""
        return PDFLayoutConfig(
            page=PageLayout(),
            kpi_card=KPICardLayout(),
            callout=CalloutLayout(),
            table=TableLayout(),
            chart=ChartLayout(),
            grid=GridLayout(),
            data_block=DataBlockLayout(),
        )

    def optimize_for_document(self, document_ir: Dict[str, Any]) -> PDFLayoutConfig:
        """
        æ ¹æ®ææ¡£IRåå®¹ä¼åå¸å±éç½®

        åæ°:
            document_ir: Document IRæ°æ®

        è¿å:
            PDFLayoutConfig: ä¼ååçå¸å±éç½®
        """
        logger.info("å¼å§åæææ¡£å¹¶ä¼åå¸å±...")

        # åæææ¡£ç»æ
        stats = self._analyze_document(document_ir)

        # æ ¹æ®åæç»æè°æ´éç½®
        optimized_config = self._adjust_config_based_on_stats(stats)

        # è®°å½ä¼åæ¥å¿
        self._log_optimization(stats, optimized_config)

        return optimized_config

    def _analyze_document(self, document_ir: Dict[str, Any]) -> Dict[str, Any]:
        """
        åæææ¡£åå®¹ç¹å¾

        è¿åç»è®¡ä¿¡æ¯ï¼?
        - kpi_count: KPIå¡çæ°é
        - table_count: è¡¨æ ¼æ°é
        - chart_count: å¾è¡¨æ°é
        - max_kpi_value_length: æé¿KPIæ°å¼é¿åº?
        - max_table_columns: æå¤è¡¨æ ¼åæ?
        - total_content_length: æ»åå®¹é¿åº?
        - hero_kpi_count: HeroåºåçKPIæ°é
        - max_hero_kpi_value_length: Heroåºåæé¿KPIæ°å¼é¿åº?
        """
        stats = {
            'kpi_count': 0,
            'table_count': 0,
            'chart_count': 0,
            'callout_count': 0,
            'max_kpi_value_length': 0,
            'max_table_columns': 0,
            'max_table_rows': 0,
            'total_content_length': 0,
            'has_long_text': False,
            'hero_kpi_count': 0,
            'max_hero_kpi_value_length': 0,
        }

        # åæheroåºåçKPI
        metadata = document_ir.get('metadata', {})
        hero = metadata.get('hero', {})
        if hero:
            hero_kpis = hero.get('kpis', [])
            stats['hero_kpi_count'] = len(hero_kpis)
            for kpi in hero_kpis:
                value = str(kpi.get('value', ''))
                stats['max_hero_kpi_value_length'] = max(
                    stats['max_hero_kpi_value_length'],
                    len(value)
                )

        # ä¼åä½¿ç¨chaptersï¼fallbackå°sections
        chapters = document_ir.get('chapters', [])
        if not chapters:
            chapters = document_ir.get('sections', [])

        # éåç« è
        for chapter in chapters:
            self._analyze_chapter(chapter, stats)

        logger.info(f"ææ¡£åæå®æ: {stats}")
        return stats

    def _analyze_chapter(self, chapter: Dict[str, Any], stats: Dict[str, Any]):
        """åæåä¸ªç« è"""
        # åæç« èä¸­çblocks
        blocks = chapter.get('blocks', [])
        for block in blocks:
            self._analyze_block(block, stats)

        # éå½å¤çå­ç« èï¼å¦ææï¼
        children = chapter.get('children', [])
        for child in children:
            if isinstance(child, dict):
                self._analyze_chapter(child, stats)

    def _analyze_block(self, block: Dict[str, Any], stats: Dict[str, Any]):
        """åæåä¸ªblockèç¹"""
        if not isinstance(block, dict):
            return

        node_type = block.get('type')

        if node_type == 'kpiGrid':
            kpis = block.get('items', [])
            stats['kpi_count'] += len(kpis)

            # æ£æ¥KPIæ°å¼é¿åº?
            for kpi in kpis:
                value = str(kpi.get('value', ''))
                stats['max_kpi_value_length'] = max(
                    stats['max_kpi_value_length'],
                    len(value)
                )

        elif node_type == 'table':
            stats['table_count'] += 1

            # åæè¡¨æ ¼ç»æ
            headers = block.get('headers', [])
            rows = block.get('rows', [])
            if rows and isinstance(rows[0], dict):
                # ä»ç¬¬ä¸è¡çcellsè®¡ç®åæ°
                cells = rows[0].get('cells', [])
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(cells)
                )
            else:
                stats['max_table_columns'] = max(
                    stats['max_table_columns'],
                    len(headers)
                )
            stats['max_table_rows'] = max(
                stats['max_table_rows'],
                len(rows)
            )

        elif node_type == 'chart' or node_type == 'widget':
            stats['chart_count'] += 1

        elif node_type == 'callout':
            stats['callout_count'] += 1
            # æ£æ¥calloutä¸­çblocks
            callout_blocks = block.get('blocks', [])
            for cb in callout_blocks:
                if isinstance(cb, dict) and cb.get('type') == 'paragraph':
                    text = self._extract_text_from_paragraph(cb)
                    if len(text) > 200:
                        stats['has_long_text'] = True

        elif node_type == 'paragraph':
            text = self._extract_text_from_paragraph(block)
            stats['total_content_length'] += len(text)
            if len(text) > 500:
                stats['has_long_text'] = True

        # éå½å¤çåµå¥çblocks
        nested_blocks = block.get('blocks', [])
        if nested_blocks:
            for nested in nested_blocks:
                self._analyze_block(nested, stats)

    def _extract_text_from_paragraph(self, paragraph: Dict[str, Any]) -> str:
        """ä»paragraph blockä¸­æåçº¯ææ¬"""
        text_parts = []
        inlines = paragraph.get('inlines', [])
        for inline in inlines:
            if isinstance(inline, dict):
                text = inline.get('text', '')
                if text:
                    text_parts.append(str(text))
            elif isinstance(inline, str):
                text_parts.append(inline)
        return ''.join(text_parts)

    def _analyze_section(self, section: Dict[str, Any], stats: Dict[str, Any]):
        """éå½åæç« èï¼ä¿çç¨äºååå¼å®¹ï¼"""
        # è¿ä¸ªæ¹æ³ä¿çç¨äºååå¼å®¹ï¼å®éä¸è°ç¨_analyze_chapter
        self._analyze_chapter(section, stats)

    def _estimate_text_width(self, text: str, font_size: int) -> float:
        """
        ä¼°ç®ææ¬çåç´ å®½åº?

        åæ°:
            text: è¦æµéçææ¬
            font_size: å­å·ï¼åç´ ï¼

        è¿å:
            float: ä¼°ç®çå®½åº¦ï¼åç´ ï¼?
        """
        if not text:
            return 0.0

        width = 0.0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # ä¸­æå­ç¬¦èå´
                width += font_size * self.CHAR_WIDTH_FACTOR['chinese']
            elif char.isalpha():
                width += font_size * self.CHAR_WIDTH_FACTOR['english']
            elif char.isdigit():
                width += font_size * self.CHAR_WIDTH_FACTOR['number']
            elif char in '%ï¼?:  # ç¾åå?
                width += font_size * self.CHAR_WIDTH_FACTOR['percent']
            else:
                width += font_size * self.CHAR_WIDTH_FACTOR['symbol']

        return width

    def _check_text_overflow(self, text: str, font_size: int, max_width: int) -> bool:
        """
        æ£æ¥ææ¬æ¯å¦ä¼æº¢åº

        åæ°:
            text: è¦æ£æ¥çææ¬
            font_size: å­å·ï¼åç´ ï¼
            max_width: æå¤§å®½åº¦ï¼åç´ ï¼?

        è¿å:
            bool: Trueè¡¨ç¤ºä¼æº¢å?
        """
        estimated_width = self._estimate_text_width(text, font_size)
        return estimated_width > max_width

    def _calculate_safe_font_size(
        self,
        text: str,
        max_width: int,
        min_font_size: int = 10,
        max_font_size: int = 32
    ) -> Tuple[int, bool]:
        """
        è®¡ç®å®å¨çå­å·ä»¥é¿åæº¢åº

        åæ°:
            text: è¦æ¾ç¤ºçææ¬
            max_width: æå¤§å®½åº¦ï¼åç´ ï¼?
            min_font_size: æå°å­å?
            max_font_size: æå¤§å­å?

        è¿å:
            Tuple[int, bool]: (å»ºè®®å­å·, æ¯å¦éè¦è°æ?
        """
        if not text:
            return max_font_size, False

        # ä»æå¤§å­å·å¼å§å°è¯?
        for font_size in range(max_font_size, min_font_size - 1, -1):
            if not self._check_text_overflow(text, font_size, max_width):
                # å¦æéè¦ç¼©å°å­å?
                needs_adjustment = font_size < max_font_size
                return font_size, needs_adjustment

        # å¦æè¿æå°å­å·é½æº¢åºï¼è¿åæå°å­å·å¹¶æ è®°éè¦è°æ?
        return min_font_size, True

    def _detect_kpi_overflow_issues(self, stats: Dict[str, Any]) -> List[str]:
        """
        æ£æµKPIå¡çå¯è½çæº¢åºé®é¢?

        åæ°:
            stats: ææ¡£ç»è®¡ä¿¡æ¯

        è¿å:
            List[str]: æ£æµå°çé®é¢åè¡?
        """
        issues = []

        # KPIå¡ççå¸åå®½åº¦ï¼åç´ ï¼?
        # åºäº2åå¸å±ï¼å®¹å¨å®½åº?00pxï¼é´è·?0px
        kpi_card_width = (800 - 20) // 2 - 40  # åå»padding

        # æ£æ¥æé¿KPIæ°å?
        max_kpi_length = stats.get('max_kpi_value_length', 0)
        if max_kpi_length > 0:
            # åè®¾ä¸ä¸ªå¾é¿çæ°å?
            sample_text = '1' * max_kpi_length + 'äº¿å'
            current_font_size = self.config.kpi_card.font_size_value

            if self._check_text_overflow(sample_text, current_font_size, kpi_card_width):
                issues.append(
                    f"KPIæ°å¼è¿é?{max_kpi_length}å­ç¬¦)ï¼?
                    f"å­å·{current_font_size}pxå¯è½å¯¼è´æº¢åº"
                )

        return issues

    def _adjust_config_based_on_stats(
        self,
        stats: Dict[str, Any]
    ) -> PDFLayoutConfig:
        """æ ¹æ®ç»è®¡ä¿¡æ¯è°æ´éç½®"""
        config = PDFLayoutConfig(
            page=PageLayout(**asdict(self.config.page)),
            kpi_card=KPICardLayout(**asdict(self.config.kpi_card)),
            callout=CalloutLayout(**asdict(self.config.callout)),
            table=TableLayout(**asdict(self.config.table)),
            chart=ChartLayout(**asdict(self.config.chart)),
            grid=GridLayout(**asdict(self.config.grid)),
            data_block=DataBlockLayout(**asdict(self.config.data_block)),
            auto_adjust_font_size=self.config.auto_adjust_font_size,
            auto_adjust_grid_columns=self.config.auto_adjust_grid_columns,
            prevent_orphan_headers=self.config.prevent_orphan_headers,
            optimize_for_print=self.config.optimize_for_print,
        )

        # æ£æµKPIæº¢åºé®é¢
        overflow_issues = self._detect_kpi_overflow_issues(stats)
        if overflow_issues:
            for issue in overflow_issues:
                logger.warning(f"æ£æµå°å¸å±é®é¢: {issue}")

        # KPIå¡çå®½åº¦ï¼åç´ ï¼- æ´ä¿å®çè®¡ç®ï¼çåºæ´å¤å®å¨è¾¹ç?
        kpi_card_width = (800 - 20) // 2 - 60  # 2åå¸å±ï¼å¢å è¾¹è·ä»¥é²æº¢å?

        # ä¼åå¤çHeroåºåçKPIï¼å¦ææçè¯ï¼?
        if stats['hero_kpi_count'] > 0 and stats['max_hero_kpi_value_length'] > 0:
            # HeroåºåçKPIå¡çå®½åº¦éå¸¸æ´çª
            hero_kpi_width = 250  # Heroä¾§è¾¹æ çå¸åå®½åº¦
            sample_text = '9' * stats['max_hero_kpi_value_length'] + 'å?
            safe_font_size, needs_adjustment = self._calculate_safe_font_size(
                sample_text,
                hero_kpi_width,
                min_font_size=14,
                max_font_size=24  # Hero KPIå­å·éå¸¸è¾å°
            )

            if needs_adjustment or stats['max_hero_kpi_value_length'] > 6:
                # Hero KPIéè¦æ´ä¿å®çå­å?
                config.kpi_card.font_size_value = max(14, safe_font_size - 2)
                self.optimization_log.append(
                    f"Hero KPIæ°å¼è¾é?{stats['max_hero_kpi_value_length']}å­ç¬¦)ï¼?
                    f"å­å·è°æ´ä¸º{config.kpi_card.font_size_value}px"
                )

        # æ ¹æ®KPIæ°å¼é¿åº¦æºè½è°æ´å­å?
        if stats['max_kpi_value_length'] > 0:
            # åå»ºç¤ºä¾ææ¬è¿è¡æµè¯ - ä½¿ç¨å®éå¯è½çå­ç¬¦ç»å?
            sample_text = '9' * stats['max_kpi_value_length'] + 'äº?  # å ä¸å¯è½çåä½?
            safe_font_size, needs_adjustment = self._calculate_safe_font_size(
                sample_text,
                kpi_card_width,
                min_font_size=16,  # éä½æå°å­å·ä»¥ç¡®ä¿ä¸æº¢å?
                max_font_size=28   # éä½æå¤§å­å·ä»¥æ´ä¿å®?
            )

            if needs_adjustment:
                config.kpi_card.font_size_value = safe_font_size
                # è¿ä¸æ­¥éä½ä»¥çåºå®å¨è¾¹ç
                config.kpi_card.font_size_value = max(16, safe_font_size - 2)
                self.optimization_log.append(
                    f"KPIæ°å¼è¿é?{stats['max_kpi_value_length']}å­ç¬¦)ï¼?
                    f"å­å·èªå¨è°æ´ä¸º{config.kpi_card.font_size_value}pxä»¥é²æ­¢æº¢å?
                )
            elif stats['max_kpi_value_length'] > 8:
                # å¯¹äºè¾é¿ææ¬ï¼æ´ä¿å®å°è°æ?
                config.kpi_card.font_size_value = min(24, safe_font_size)
                self.optimization_log.append(
                    f"KPIæ°å¼è¾é?{stats['max_kpi_value_length']}å­ç¬¦)ï¼?
                    f"é¢é²æ§è°æ´å­å·ä¸º{config.kpi_card.font_size_value}px"
                )

        # æ¶ç´§KPIå­å·ä¸éï¼ä¸ºæ­£ææ°æ®åç¼©æ¾çåºç©ºé?
        base = config.page.font_size_base
        kpi_value_cap = max(base + 6, 20)
        kpi_label_cap = max(base - 1, 12)
        kpi_change_cap = max(base, 12)

        original_value = config.kpi_card.font_size_value
        original_label = config.kpi_card.font_size_label
        original_change = config.kpi_card.font_size_change

        config.kpi_card.font_size_value = min(original_value, kpi_value_cap)
        config.kpi_card.font_size_value = max(config.kpi_card.font_size_value, base + 1)
        config.kpi_card.font_size_label = min(original_label, kpi_label_cap)
        config.kpi_card.font_size_label = max(config.kpi_card.font_size_label, 12)
        config.kpi_card.font_size_change = min(original_change, kpi_change_cap)
        config.kpi_card.font_size_change = max(config.kpi_card.font_size_change, 12)
        self.optimization_log.append(
            f"KPIå­å·ä¸éæ¶ç´§ï¼æ°å¼{original_value}px->{config.kpi_card.font_size_value}pxï¼?
            f"æ ç­¾{original_label}px->{config.kpi_card.font_size_label}pxï¼?
            f"åå¨{original_change}px->{config.kpi_card.font_size_change}px"
        )

        total_blocks = (stats['kpi_count'] + stats['table_count'] +
                        stats['chart_count'] + stats['callout_count'])

        # åå¼æ¶ç´§æç« æ»è§ä¸æ­£ææ°æ®åçæå­?
        if stats['hero_kpi_count'] >= 3 or stats['max_hero_kpi_value_length'] > 6:
            prev = config.data_block.overview_kpi_scale
            config.data_block.overview_kpi_scale = min(prev, 0.86)
            if config.data_block.overview_kpi_scale != prev:
                self.optimization_log.append(
                    f"æç« æ»è§KPIè¾å¯éï¼ç¼©æ¾ç³»æ° {prev:.2f}->{config.data_block.overview_kpi_scale:.2f}"
                )

        if stats['has_long_text'] or stats['max_table_columns'] > 6:
            prev_text = config.data_block.body_text_scale
            prev_kpi = config.data_block.body_kpi_scale
            config.data_block.body_text_scale = min(prev_text, 0.78)
            config.data_block.body_kpi_scale = min(prev_kpi, 0.74)
            self.optimization_log.append(
                f"æ­£ææ°æ®åç´§ç¼©ï¼é¿ææ?å®½è¡¨è§¦åï¼æå­ç¼©æ¾è³{config.data_block.body_text_scale*100:.0f}%ï¼?
                f"KPIç¼©æ¾è³{config.data_block.body_kpi_scale*100:.0f}%"
            )
        elif total_blocks > 16:
            prev_text = config.data_block.body_text_scale
            prev_kpi = config.data_block.body_kpi_scale
            config.data_block.body_text_scale = min(prev_text, 0.80)
            config.data_block.body_kpi_scale = min(prev_kpi, 0.75)
            self.optimization_log.append(
                f"æ­£ææ°æ®åç¼©æ¾ï¼åå®¹åè¾å¤?{total_blocks}ä¸?ï¼æå­ç¼©æ¾è³{config.data_block.body_text_scale*100:.0f}%ï¼?
                f"KPIç¼©æ¾è³{config.data_block.body_kpi_scale*100:.0f}%"
            )
        elif total_blocks > 10:
            prev_text = config.data_block.body_text_scale
            config.data_block.body_text_scale = min(prev_text, 0.82)
            if config.data_block.body_text_scale != prev_text:
                self.optimization_log.append(
                    f"æ­£ææ°æ®åè½»éç¼©æ?{total_blocks}ä¸ªå)ï¼æå­ç¼©æ¾ç³»æ?{prev_text:.2f}->{config.data_block.body_text_scale:.2f}"
                )

        # æ ¹æ®KPIæ°éè°æ´é´è·ä½ä¿ææ­£æé»è®¤ä¸åè£è®?
        config.grid.columns = 3
        if stats['kpi_count'] > 6:
            config.kpi_card.min_height = 100
            config.kpi_card.padding = 14  # ç¼©å°paddingä»¥èçç©ºé?
            config.grid.gap = 16  # åå°é´è·
            self.optimization_log.append(
                f"KPIå¡çè¾å¤({stats['kpi_count']}ä¸?ï¼?
                f"ä¿æä¸åå¸å±å¹¶ç¼©å°åè¾¹è·åé´è·?
            )
        elif stats['kpi_count'] > 4:
            config.kpi_card.padding = 16
            config.grid.gap = 18
            self.optimization_log.append(
                f"KPIå¡çéä¸­({stats['kpi_count']}ä¸?ï¼ä¿æä¸åå¸å±å¹¶éåº¦è°æ´é´è·"
            )
        elif stats['kpi_count'] <= 2:
            config.kpi_card.padding = 22  # è¾å°å¡çæ¶å¢å padding
            config.grid.gap = 20
            self.optimization_log.append(
                f"KPIå¡çè¾å°({stats['kpi_count']}ä¸?ï¼?
                f"ä¿æä¸åå¸å±å¹¶å¢å åè¾¹è·"
            )

        # æ ¹æ®è¡¨æ ¼åæ°è°æ´å­å·åé´è·?
        if stats['max_table_columns'] > 8:
            config.table.font_size_header = 10
            config.table.font_size_body = 9
            config.table.cell_padding = 6
            self.optimization_log.append(
                f"è¡¨æ ¼åæ°å¾å¤({stats['max_table_columns']}å?ï¼?
                f"å¤§å¹ç¼©å°å­å·ååè¾¹è·"
            )
        elif stats['max_table_columns'] > 6:
            config.table.font_size_header = 11
            config.table.font_size_body = 10
            config.table.cell_padding = 8
            self.optimization_log.append(
                f"è¡¨æ ¼åæ°è¾å¤({stats['max_table_columns']}å?ï¼?
                f"ç¼©å°å­å·ååè¾¹è·"
            )
        elif stats['max_table_columns'] > 4:
            config.table.font_size_header = 12
            config.table.font_size_body = 11
            config.table.cell_padding = 10
            self.optimization_log.append(
                f"è¡¨æ ¼åæ°éä¸­({stats['max_table_columns']}å?ï¼?
                f"éåº¦è°æ´å­å·"
            )

        # å¦ææé¿ææ¬ï¼å¢å è¡é«åæ®µè½é´è·
        if stats['has_long_text']:
            config.page.line_height = 1.75  # ç¨å¾®éä½ä»¥èçç©ºé?
            config.callout.line_height = 1.75
            config.page.paragraph_spacing = 16  # éåº¦é´è·
            self.optimization_log.append(
                "æ£æµå°é¿ææ¬ï¼å¢å è¡é«è?.75åæ®µè½é´è·ä»¥æé«å¯è¯»æ?
            )
        else:
            # æ²¡æé¿ææ¬æ¶ä½¿ç¨æ´ç´§åçé´è·
            config.page.line_height = 1.5
            config.callout.line_height = 1.6
            config.page.paragraph_spacing = 14
            self.optimization_log.append(
                "ææ¬é¿åº¦éä¸­ï¼ä½¿ç¨æ åè¡é«åæ®µè½é´è·"
            )

        # å¦æåå®¹è¾å¤ï¼åå°æ´ä½å­å?
        if total_blocks > 20:
            config.page.font_size_base = 13
            config.page.font_size_h2 = 22
            config.page.font_size_h3 = 18
            self.optimization_log.append(
                f"åå®¹åè¾å¤?{total_blocks}ä¸?ï¼?
                f"éåº¦ç¼©å°æ´ä½å­å·ä»¥ä¼åæç?
            )

        return config

    def _log_optimization(
        self,
        stats: Dict[str, Any],
        config: PDFLayoutConfig
    ):
        """è®°å½ä¼åè¿ç¨"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'document_stats': stats,
            'optimizations': self.optimization_log.copy(),
            'final_config': config.to_dict(),
        }

        logger.info(f"å¸å±ä¼åå®æï¼åºç¨äº{len(self.optimization_log)}é¡¹ä¼å?)
        for opt in self.optimization_log:
            logger.info(f"  - {opt}")

        # æ¸ç©ºæ¥å¿ä¾ä¸æ¬¡ä½¿ç?
        self.optimization_log.clear()

        return log_entry

    def save_config(self, path: str | Path, log_entry: Optional[Dict] = None):
        """
        ä¿å­éç½®å°æä»?

        åæ°:
            path: ä¿å­è·¯å¾
            log_entry: ä¼åæ¥å¿æ¡ç®ï¼å¯éï¼
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'config': self.config.to_dict(),
        }

        if log_entry:
            data['optimization_log'] = log_entry

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"å¸å±éç½®å·²ä¿å­? {path}")

    @classmethod
    def load_config(cls, path: str | Path) -> PDFLayoutOptimizer:
        """
        ä»æä»¶å è½½éç½?

        åæ°:
            path: éç½®æä»¶è·¯å¾

        è¿å:
            PDFLayoutOptimizer: å è½½äºéç½®çä¼åå¨å®ä¾?
        """
        path = Path(path)

        if not path.exists():
            logger.warning(f"éç½®æä»¶ä¸å­å? {path}ï¼ä½¿ç¨é»è®¤éç½?)
            return cls()

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        config = PDFLayoutConfig.from_dict(data['config'])
        optimizer = cls(config)

        logger.info(f"å¸å±éç½®å·²å è½? {path}")
        return optimizer

    def generate_pdf_css(self) -> str:
        """
        æ ¹æ®å½åéç½®çæPDFä¸ç¨CSS

        è¿å:
            str: CSSæ ·å¼å­ç¬¦ä¸?
        """
        cfg = self.config
        db = cfg.data_block

        def _scaled(value: float, scale: float, minimum: int) -> int:
            """ææ¯ä¾ç¼©æ¾å¹¶ä¸éä¿æ¤ï¼é¿åæ°æ®åæå­è¿å¤§æè¿å°?""
            try:
                return max(int(round(value * scale)), minimum)
            except Exception:
                return minimum

        # æç« æ»è§æ°æ®åå­ä½?
        overview_summary_font = _scaled(cfg.page.font_size_base, db.overview_text_scale, db.min_overview_font)
        overview_badge_font = _scaled(max(cfg.page.font_size_base - 2, db.min_overview_font), db.overview_text_scale, db.min_overview_font)
        overview_kpi_value = _scaled(cfg.kpi_card.font_size_value, db.overview_kpi_scale, db.min_overview_font + 1)
        overview_kpi_label = _scaled(cfg.kpi_card.font_size_label, db.overview_kpi_scale, db.min_overview_font)
        overview_kpi_delta = _scaled(cfg.kpi_card.font_size_change, db.overview_kpi_scale, db.min_overview_font)

        # æ­£ææ°æ®åå­ä½?
        body_kpi_value = _scaled(cfg.kpi_card.font_size_value, db.body_kpi_scale, db.min_body_font + 1)
        body_kpi_label = _scaled(cfg.kpi_card.font_size_label, db.body_kpi_scale, db.min_body_font)
        body_kpi_delta = _scaled(cfg.kpi_card.font_size_change, db.body_kpi_scale, db.min_body_font)
        body_callout_title = _scaled(cfg.callout.font_size_title, db.body_text_scale, db.min_body_font + 1)
        body_callout_content = _scaled(cfg.callout.font_size_content, db.body_text_scale, db.min_body_font)
        body_table_header = _scaled(cfg.table.font_size_header, db.body_text_scale, db.min_body_font)
        body_table_body = _scaled(cfg.table.font_size_body, db.body_text_scale, db.min_body_font)
        body_chart_title = _scaled(cfg.chart.font_size_title, db.body_text_scale, db.min_body_font + 1)
        body_badge_font = _scaled(max(cfg.page.font_size_base - 2, db.min_body_font), db.body_text_scale, db.min_body_font)

        css = f"""
/* PDFå¸å±ä¼åæ ·å¼ - ç±PDFLayoutOptimizerèªå¨çæ */

/* éèç¬ç«çå°é¢sectionï¼å·²åå¹¶å°hero */
.cover {{
    display: none !important;
}}

/* PDFä¸­æ¾ç¤ºhero actionsï¼å»ºè®?è¡å¨æ¡ç®ï¼?*/
.hero-actions {{
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    margin-top: 14px !important;
    padding: 0 !important;
}}

.hero-actions .ghost-btn {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    background: none !important;
    background-color: #f3f4f6 !important;
    background-image: none !important;
    border: none !important;
    border-width: 0 !important;
    border-style: none !important;
    border-radius: 999px !important;
    padding: 5px 10px !important;
    font-size: {max(cfg.page.font_size_base - 2, 11)}px !important;
    color: #222 !important;
    width: auto !important;
    height: auto !important;
    white-space: normal !important;
    line-height: 1.5 !important;
    text-align: left !important;
    box-shadow: none !important;
    cursor: default !important;
    -webkit-appearance: none !important;
    appearance: none !important;
    outline: none !important;
    word-break: break-word !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
}}

/* é¡µé¢åºç¡æ ·å¼ */
body {{
    font-size: {cfg.page.font_size_base}px;
    line-height: {cfg.page.line_height};
}}

main {{
    padding: {cfg.page.page_padding}px !important;
    max-width: {cfg.page.max_content_width}px;
    margin: 0 auto;
}}

/* æ é¢æ ·å¼ */
h1 {{ font-size: {cfg.page.font_size_h1}px !important; }}
h2 {{ font-size: {cfg.page.font_size_h2}px !important; }}
h3 {{ font-size: {cfg.page.font_size_h3}px !important; }}
h4 {{ font-size: {cfg.page.font_size_h4}px !important; }}

/* æ®µè½é´è· */
p {{
    margin-bottom: {cfg.page.paragraph_spacing}px;
}}

.chapter {{
    margin-bottom: {cfg.page.section_spacing}px;
}}

/* KPIå¡çä¼å - é²æ­¢æº¢åº */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    grid-auto-rows: minmax(auto, 1fr);
    grid-auto-flow: row dense;
    gap: {cfg.grid.gap}px;
    margin: 20px 0;
    align-items: stretch;
}}

.kpi-grid .kpi-card {{
    grid-column: span 2;
}}

/* åæ¡/åæ¡/ä¸æ¡çç¹æ®åæ?*/
.chapter .kpi-grid[data-kpi-count="1"] {{
    grid-template-columns: repeat(1, minmax(0, 1fr));
    grid-auto-flow: row;
}}
.chapter .kpi-grid[data-kpi-count="1"] .kpi-card {{
    grid-column: span 1;
}}
.chapter .kpi-grid[data-kpi-count="2"] {{
    grid-template-columns: repeat(4, minmax(0, 1fr));
}}
.chapter .kpi-grid[data-kpi-count="2"] .kpi-card {{
    grid-column: span 2;
}}
.chapter .kpi-grid[data-kpi-count="3"] {{
    grid-template-columns: repeat(6, minmax(0, 1fr));
}}

/* åæ¡æ¶éç?x2æå¸ */
.chapter .kpi-grid[data-kpi-count="4"] {{
    grid-template-columns: repeat(4, minmax(0, 1fr));
}}
.chapter .kpi-grid[data-kpi-count="4"] .kpi-card {{
    grid-column: span 2;
}}

/* äºæ¡åä»¥ä¸é»è®¤ä¸åï¼6æ æ ¼ï¼æ¯å¡å 2ï¼?*/
.chapter .kpi-grid[data-kpi-count="5"],
.chapter .kpi-grid[data-kpi-count="6"],
.chapter .kpi-grid[data-kpi-count="7"],
.chapter .kpi-grid[data-kpi-count="8"],
.chapter .kpi-grid[data-kpi-count="9"],
.chapter .kpi-grid[data-kpi-count="10"],
.chapter .kpi-grid[data-kpi-count="11"],
.chapter .kpi-grid[data-kpi-count="12"],
.chapter .kpi-grid[data-kpi-count="13"],
.chapter .kpi-grid[data-kpi-count="14"],
.chapter .kpi-grid[data-kpi-count="15"],
.chapter .kpi-grid[data-kpi-count="16"] {{
    grid-template-columns: repeat(6, minmax(0, 1fr));
}}

/* ä½æ°ä¸?æ¶ï¼æåä¸¤å¼ å¹³åå¨å®?*/
.chapter .kpi-grid[data-kpi-count="5"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="8"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="11"] .kpi-card:nth-last-child(-n+2),
.chapter .kpi-grid[data-kpi-count="14"] .kpi-card:nth-last-child(-n+2) {{
    grid-column: span 3;
}}

/* ä½æ°ä¸?æ¶ï¼æåä¸å¼ å æ»¡å¨å®?*/
.chapter .kpi-grid[data-kpi-count="7"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="10"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="13"] .kpi-card:last-child,
.chapter .kpi-grid[data-kpi-count="16"] .kpi-card:last-child {{
    grid-column: 1 / -1;
}}

.kpi-card {{
    padding: {cfg.kpi_card.padding}px !important;
    min-height: {cfg.kpi_card.min_height}px;
    break-inside: avoid;
    page-break-inside: avoid;
    box-sizing: border-box;
    max-width: 100%;
    height: auto;
    display: flex;
    flex-direction: column;
    align-items: stretch !important;
    gap: 8px;
}}

.kpi-card .kpi-value {{
    font-size: {body_kpi_value}px !important;
    line-height: 1.25;
    white-space: nowrap;
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    display: flex;
    flex-wrap: nowrap;
    align-items: baseline;
    gap: 4px 6px;
}}
.kpi-card .kpi-value small {{
    font-size: 0.65em;
    white-space: nowrap;
    align-self: baseline;
}}
.kpi-card .kpi-label {{
    font-size: {body_kpi_label}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
    line-height: 1.35;
}}

.kpi-card .change,
.kpi-card .delta {{
    font-size: {body_kpi_delta}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: 1.3;
}}

/* æç¤ºæ¡ä¼å?- é²æ­¢æº¢åº */
.callout {{
    padding: {cfg.callout.padding}px !important;
    margin: 20px 0;
    line-height: {cfg.callout.line_height};
    font-size: {body_callout_content}px !important;
    break-inside: avoid;
    page-break-inside: avoid;
    /* é²æ­¢æº¢åº */
    overflow: hidden;
    box-sizing: border-box;
    max-width: 100%;
}}

.callout-title {{
    font-size: {body_callout_title}px !important;
    margin-bottom: 10px;
    word-break: break-word;
    line-height: 1.4;
}}

.callout-content {{
    font-size: {body_callout_content}px !important;
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: {cfg.callout.line_height};
}}

.callout strong {{
    font-size: {body_callout_title}px !important;
}}

.callout p,
.callout li,
.callout table,
.callout td,
.callout th {{
    font-size: {body_callout_content}px !important;
}}

/* ç¡®ä¿ callout åé¨æåä¸ä¸ªåç´ ä¸ä¼æº¢åºåºé?*/
.callout > *:last-child,
.callout > *:last-child > *:last-child {{
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}}

/* è¡¨æ ¼ä¼å - ä¸¥æ ¼é²æ­¢æº¢åº */
table {{
    width: 100%;
    break-inside: avoid;
    page-break-inside: avoid;
    /* è¡¨æ ¼å¸å±åºå® */
    table-layout: fixed;
    max-width: 100%;
    overflow: hidden;
}}

th {{
    font-size: {body_table_header}px !important;
    padding: {cfg.table.cell_padding}px !important;
    /* è¡¨å¤´æå­æ§å¶ */
    word-break: break-word;
    overflow-wrap: break-word;
    hyphens: auto;
    max-width: 100%;
}}

td {{
    font-size: {body_table_body}px !important;
    padding: {cfg.table.cell_padding}px !important;
    max-width: {cfg.table.max_cell_width}px;
    /* å¼ºå¶æ¢è¡ï¼é²æ­¢æº¢å?*/
    word-wrap: break-word;
    overflow-wrap: break-word;
    word-break: break-word;
    hyphens: auto;
    white-space: normal;
}}

/* å¾è¡¨ä¼å */
.chart-card {{
    min-height: {cfg.chart.min_height}px;
    max-height: {cfg.chart.max_height}px;
    padding: {cfg.chart.padding}px;
    break-inside: avoid;
    page-break-inside: avoid;
    /* é²æ­¢å¾è¡¨æº¢åº */
    overflow: hidden;
    max-width: 100%;
    box-sizing: border-box;
}}

.chart-title {{
    font-size: {body_chart_title}px !important;
    word-break: break-word;
}}

/* Heroåºååå¹¶çæ¬ - å»æå¤§è²åï¼é¦å±ä»¥å¡çåæå¸åç°æç« æ»è§ */
.hero-section-combined {{
    padding: 38px 44px !important;
    margin: 0 auto 34px auto !important;
    min-height: 420px;
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box;
    overflow: visible;
    border-radius: 26px !important;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 18px 44px rgba(15, 23, 42, 0.06);
    page-break-after: always !important;
    page-break-inside: avoid;
}}

/* Heroæ é¢åºå */
.hero-header {{
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    row-gap: 6px;
    margin-bottom: 22px;
    padding-bottom: 16px;
    border-bottom: 1px solid #eef1f5;
    text-align: left;
}}

.hero-hint {{
    font-size: {max(cfg.page.font_size_base - 2, 11)}px !important;
    color: #556070;
    margin: 0;
    font-weight: 600;
    letter-spacing: 0.04em;
}}

.hero-title {{
    font-size: {max(cfg.page.font_size_base + 5, 19)}px !important;
    font-weight: 700;
    margin: 0;
    color: #0f172a;
    line-height: 1.25;
    letter-spacing: -0.01em;
}}

.hero-subtitle {{
    font-size: {max(cfg.page.font_size_base - 1, 12)}px !important;
    color: #475467;
    margin: 2px 0 0 0;
    font-weight: 500;
}}

/* Heroä¸»ä½åºå - ç½æ ¼åæ  */
.hero-body {{
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
    gap: 22px 28px;
    align-items: flex-start;
    align-content: start;
}}

/* å·¦ä¾§æè¦/äº®ç¹ */
.hero-content {{
    display: grid;
    gap: 14px;
    min-width: 0;
    align-content: start;
}}

/* å³ä¾§KPIåºå */
.hero-side {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: {max(cfg.grid.gap - 2, 10)}px;
    overflow: hidden;
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 0;
    align-content: flex-start;
}}

/* HeroåºåçKPIå¡ç */
.hero-kpi {{
    background: #fdfdfd;
    border-radius: 14px !important;
    border: 1px solid #e5e7eb;
    box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08);
    padding: 14px 16px !important;
    overflow: hidden;
    box-sizing: border-box;
    min-height: 110px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}}

.hero-kpi .label {{
    font-size: {overview_kpi_label}px !important;
    word-break: break-word;
    max-width: 100%;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #556070;
}}

.hero-kpi .value {{
    font-size: {overview_kpi_value}px !important;
    white-space: nowrap;
    width: 100%;
    max-width: 100%;
    line-height: 1.1;
    display: block;
    hyphens: auto;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 2px;
    color: #0f172a;
}}

.hero-kpi .delta {{
    font-size: {overview_kpi_delta}px !important;
    word-break: break-word;
    margin-top: 2px;
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.2;
}}

/* Hero summaryææ¬ */
.hero-summary {{
    font-size: {overview_summary_font}px !important;
    line-height: 1.65;
    margin: 0 0 12px 0;
    padding: 0;
    word-break: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    width: 100%;
    box-sizing: border-box;
    align-self: start;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
}}

/* Hero highlightsåè¡¨ - ç½æ ¼æå¸ */
.hero-highlights {{
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px 12px;
}}

.hero-highlights li {{
    margin: 0;
    max-width: 100%;
    flex-shrink: 0;
    flex-grow: 0;
}}

/* hero highlightsä¸­çbadge - å¡çåçå°æ¡ç?*/
.hero-highlights .badge {{
    font-size: {overview_badge_font}px !important;
    padding: 10px 12px !important;
    max-width: 100%;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    word-wrap: break-word;
    white-space: normal;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
    line-height: 1.5;
    min-height: 40px;
    background: #f3f4f6 !important;
    border-radius: 12px !important;
    border: 1px solid #e5e7eb;
    color: #111827;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
    align-items: flex-start;
    justify-content: flex-start;
}}

/* Hero actionsæé® - PDFä¸­æ¾ç¤ºä¸ºçº¿æ¡æ ç­¾æ ·å¼ */
.hero-actions {{
    margin-top: 14px;
    display: flex !important;
    flex-wrap: wrap;
    gap: 8px;
    max-width: 100%;
    overflow: visible;
    padding: 0;
}}

.hero-actions button,
.hero-actions .ghost-btn {{
    font-size: {max(cfg.page.font_size_base - 2, 11)}px !important;
    padding: 5px 10px !important;
    max-width: 100%;
    word-break: break-word;
    white-space: normal;
    overflow: visible;
    box-sizing: border-box;
    background: none !important;
    background-color: #f3f4f6 !important;
    background-image: none !important;
    border: none !important;
    border-width: 0 !important;
    border-style: none !important;
    border-radius: 999px !important;
    color: #222 !important;
    line-height: 1.5;
    display: inline-flex !important;
    align-items: center;
    justify-content: flex-start;
    outline: none !important;
    -webkit-appearance: none !important;
    appearance: none !important;
    box-shadow: none !important;
}}

/* é²æ­¢æ é¢å­¤è¡ */
h1, h2, h3, h4, h5, h6 {{
    break-after: avoid;
    page-break-after: avoid;
    word-break: break-word;
    overflow-wrap: break-word;
}}

/* ===== å¼ºå¶é¡µé¢åç¦»è§å ===== */

/* ç®å½sectionå¼ºå¶å¼å§æ°é¡µå¹¶å¨ä¹åå¼ºå¶åé¡?*/
.toc-section {{
    page-break-before: always !important;
    page-break-after: always !important;
}}

/* ç¬¬ä¸ä¸ªç« èå¼ºå¶å¼å§æ°é¡µï¼æ­£æä»ç¬¬ä¸é¡µå¼å§ï¼ */
main > .chapter:first-of-type {{
    page-break-before: always !important;
}}

/* ç¡®ä¿åå®¹åä¸è¢«åé¡µä¸ä¸æº¢å?*/
.content-block {{
    break-inside: avoid;
    page-break-inside: avoid;
    overflow: hidden;
    max-width: 100%;
}}

/* å¨å±æº¢åºé²æ¤ */
* {{
    box-sizing: border-box;
    max-width: 100%;
}}

/* ç¹å«æ§å¶æ°å­åé¿åè¯ */
.kpi-value, .value, .delta {{
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.02em;  /* ç¨å¾®ç´§ç¼©é´è·ä»¥èçç©ºé?*/
}}

/* è²åï¼badgeï¼æ ·å¼æ§å?- é²æ­¢è¿å¤§ */
.badge {{
    display: inline-block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: normal;
    /* éå¶badgeçæå¤§å°ºå¯?*/
    padding: 4px 12px !important;
    font-size: {body_badge_font}px !important;
    line-height: 1.4 !important;
    /* é²æ­¢badgeå¼å¸¸è¿å¤§ */
    word-break: break-word;
    hyphens: auto;
}}

/* ç¡®ä¿calloutä¸ä¼è¿å¤§ */
.callout {{
    max-width: 100% !important;
    margin: 16px 0 !important;
    padding: {cfg.callout.padding}px !important;
    box-sizing: border-box;
    overflow: hidden;
}}

/* ååºå¼è°æ?*/
@media print {{
    /* æå°æ¶æ´ä¸¥æ ¼çæ§å?*/
    * {{
        overflow: visible !important;
        max-width: 100% !important;
    }}

    .kpi-card, .callout, .chart-card {{
        overflow: hidden !important;
    }}
}}
"""

        return css


__all__ = [
    'PDFLayoutOptimizer',
    'PDFLayoutConfig',
    'PageLayout',
    'KPICardLayout',
    'CalloutLayout',
    'TableLayout',
    'ChartLayout',
    'GridLayout',
    'DataBlockLayout',
]
