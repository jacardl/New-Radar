ï»¿"""
PDFæ¸²æï¿½?- ä½¿ç¨WeasyPrintä»HTMLçæPDF
æ¯æå®æ´çCSSæ ·å¼åä¸­æå­ï¿½?
"""

from __future__ import annotations

import base64
import copy
import os
import sys
import io
import re
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from loguru import logger
from backend.engines.report.utils.dependency_check import (
    prepare_pango_environment,
    check_pango_available,
)

# å¨å¯¼å¥WeasyPrintä¹åï¼å°è¯è¡¥åå¸¸è§çmacOS Homebrewå¨æåºè·¯å¾ï¿½?
# é¿åå æªè®¾ç½®DYLD_LIBRARY_PATHèæ¾ä¸å°pango/cairoç­ä¾èµï¿½?
if sys.platform == 'darwin':
    mac_libs = [Path('/opt/homebrew/lib'), Path('/usr/local/lib')]
    current = os.environ.get('DYLD_LIBRARY_PATH', '')
    inserts = []
    for lib in mac_libs:
        if lib.exists() and str(lib) not in current.split(':'):
            inserts.append(str(lib))
    if inserts:
        os.environ['DYLD_LIBRARY_PATH'] = ":".join(inserts + ([current] if current else []))

# Windows: èªå¨è¡¥åå¸¸è§ GTK/Pango è¿è¡æ¶è·¯å¾ï¼é¿å DLL å è½½å¤±è´¥
if sys.platform.startswith('win'):
    added = prepare_pango_environment()
    if added:
        logger.debug(f"å·²èªå¨æ·»ï¿½?GTK è¿è¡æ¶è·¯ï¿½? {added}")

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
    PDF_DEP_STATUS = "OK"
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    # å¤æ­éè¯¯ç±»åä»¥æä¾æ´åå¥½çæç¤ºï¼å¹¶å°è¯è¾åºç¼ºå¤±ä¾èµçè¯¦ç»ä¿¡æ¯
    try:
        _, dep_message = check_pango_available()
    except Exception:
        dep_message = None

    if isinstance(e, OSError):
        msg = dep_message or (
            "PDF å¯¼åºä¾èµç¼ºå¤±ï¼ç³»ç»åºæªå®è£æç¯å¢åéæªè®¾ç½®ï¼ï¿½?
            "PDF å¯¼åºåè½å°ä¸å¯ç¨ãå¶ä»åè½ä¸åå½±åï¿½?
        )
        logger.warning(msg)
        PDF_DEP_STATUS = msg
    else:
        msg = dep_message or "WeasyPrintæªå®è£ï¼PDFå¯¼åºåè½å°ä¸å¯ç¨"
        logger.warning(msg)
        PDF_DEP_STATUS = msg
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    PDF_DEP_STATUS = f"WeasyPrint å è½½å¤±è´¥: {e}ï¼PDFå¯¼åºåè½å°ä¸å¯ç¨"
    logger.warning(PDF_DEP_STATUS)

from .html_renderer import HTMLRenderer
from .pdf_layout_optimizer import PDFLayoutOptimizer, PDFLayoutConfig
from .chart_to_svg import create_chart_converter
from .math_to_svg import MathToSVG
from backend.engines.report.utils.chart_review_service import get_chart_review_service
try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False
    logger = logger  # ensure logger exists even before declaration


class PDFRenderer:
    """
    åºäºWeasyPrintçPDFæ¸²æï¿½?

    - ç´æ¥ä»HTMLçæPDFï¼ä¿çææCSSæ ·å¼
    - å®ç¾æ¯æä¸­æå­ä½
    - èªå¨å¤çåé¡µåå¸å±
    """

    def __init__(
        self,
        config: Dict[str, Any] | None = None,
        layout_optimizer: PDFLayoutOptimizer | None = None
    ):
        """
        åå§åPDFæ¸²æï¿½?

        åæ°:
            config: æ¸²æå¨éï¿½?
            layout_optimizer: PDFå¸å±ä¼åå¨ï¼å¯éï¼
        """
        self.config = config or {}
        self.html_renderer = HTMLRenderer(config)
        self.layout_optimizer = layout_optimizer or PDFLayoutOptimizer()

        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError(
                PDF_DEP_STATUS
                if 'PDF_DEP_STATUS' in globals() else
                "WeasyPrintæªå®è£ï¼è¯·è¿ï¿½? pip install weasyprint"
            )

        # åå§åå¾è¡¨è½¬æ¢å¨
        try:
            font_path = self._get_font_path()
            self.chart_converter = create_chart_converter(font_path=str(font_path))
            logger.info("å¾è¡¨SVGè½¬æ¢å¨åå§åæå")
        except Exception as e:
            logger.warning(f"å¾è¡¨SVGè½¬æ¢å¨åå§åå¤±è´¥: {e}ï¼å°ä½¿ç¨è¡¨æ ¼éçº§")

        # åå§åæ°å­¦å¬å¼è½¬æ¢å¨
        try:
            self.math_converter = MathToSVG(font_size=16, color='black')
            logger.info("æ°å­¦å¬å¼SVGè½¬æ¢å¨åå§åæå")
        except Exception as e:
            logger.warning(f"æ°å­¦å¬å¼SVGè½¬æ¢å¨åå§åå¤±è´¥: {e}ï¼å¬å¼å°æ¾ç¤ºä¸ºæï¿½?)
            self.math_converter = None

    @staticmethod
    def _get_font_path() -> Path:
        """è·åå­ä½æä»¶è·¯å¾"""
        # ä¼åä½¿ç¨å®æ´å­ä½ä»¥ç¡®ä¿å­ç¬¦è¦ï¿½?
        fonts_dir = Path(__file__).parent / "assets" / "fonts"

        # æ£æ¥å®æ´å­ï¿½?
        full_font = fonts_dir / "SourceHanSerifSC-Medium.otf"
        if full_font.exists():
            logger.info(f"ä½¿ç¨å®æ´å­ä½: {full_font}")
            return full_font

        # æ£æ¥TTFå­éå­ä½
        subset_ttf = fonts_dir / "SourceHanSerifSC-Medium-Subset.ttf"
        if subset_ttf.exists():
            logger.info(f"ä½¿ç¨TTFå­éå­ä½: {subset_ttf}")
            return subset_ttf

        # æ£æ¥OTFå­éå­ä½
        subset_otf = fonts_dir / "SourceHanSerifSC-Medium-Subset.otf"
        if subset_otf.exists():
            logger.info(f"ä½¿ç¨OTFå­éå­ä½: {subset_otf}")
            return subset_otf

        raise FileNotFoundError(f"æªæ¾å°å­ä½æä»¶ï¼è¯·æ£ï¿½?{fonts_dir} ç®å½")

    def _preprocess_charts(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: str | None = None
    ) -> Dict[str, Any]:
        """
        é¢å¤çå¾è¡¨ï¼ä½¿ç¨ ChartReviewService éªè¯å¹¶ä¿®å¤ææå¾è¡¨æ°æ®ï¿½?

        ä½¿ç¨ç»ä¸ï¿½?ChartReviewService è¿è¡å¾è¡¨å®¡æ¥ï¼ä¿®å¤ç»æç´æ¥ååä¼ å¥ç IRï¿½?
        å¦ææä¾ ir_file_pathï¼ä¿®å¤åä¼èªå¨ä¿å­å°æä»¶ï¿½?

        åæ°:
            document_ir: Document IRæ°æ®
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­

        è¿å:
            Dict[str, Any]: ä¿®å¤åçDocument IRï¼æ·±æ·è´ï¿½?
        """
        # ä½¿ç¨ç»ä¸ï¿½?ChartReviewService
        # review_document è¿åæ¬æ¬¡ä¼è¯çç»è®¡ä¿¡æ¯ï¼çº¿ç¨å®å¨ï¿½?
        chart_service = get_chart_review_service()
        review_stats = chart_service.review_document(
            document_ir,
            ir_file_path=ir_file_path,
            reset_stats=True,
            save_on_repair=bool(ir_file_path)
        )

        # ä½¿ç¨è¿åï¿½?ReviewStats å¯¹è±¡ï¼èéå±äº«ï¿½?chart_service.stats
        if review_stats.total > 0:
            logger.info(
                f"PDFå¾è¡¨é¢å¤çå®ï¿½? "
                f"æ»è®¡ {review_stats.total} ä¸ªå¾ï¿½? "
                f"ä¿®å¤ {review_stats.repaired_total} ï¿½? "
                f"å¤±è´¥ {review_stats.failed} ï¿½?
            )

        # è¿åæ·±æ·è´ï¼é¿ååç»­ SVG è½¬æ¢è¿ç¨å½±ååååçåå§ IR
        return copy.deepcopy(document_ir)

    def _convert_charts_to_svg(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        å°document_irä¸­çææå¾è¡¨è½¬æ¢ä¸ºSVG

        åæ°:
            document_ir: Document IRæ°æ®

        è¿å:
            Dict[str, str]: widgetIdå°SVGå­ç¬¦ä¸²çæ å°
        """
        svg_map = {}

        if not hasattr(self, 'chart_converter') or not self.chart_converter:
            logger.warning("å¾è¡¨è½¬æ¢å¨æªåå§åï¼è·³è¿å¾è¡¨è½¬æ¢")
            return svg_map

        # éåææç« ï¿½?
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_and_convert_widgets(blocks, svg_map)

        logger.info(f"æåè½¬æ¢ {len(svg_map)} ä¸ªå¾è¡¨ä¸ºSVG")
        return svg_map

    def _convert_wordclouds_to_images(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        å°document_irä¸­çè¯äºwidgetè½¬æ¢ä¸ºPNGå¹¶è¿ådata URIæ å°
        """
        img_map: Dict[str, str] = {}

        if not WORDCLOUD_AVAILABLE:
            logger.debug("wordcloudåºæªå®è£ï¼è¯äºå°ä½¿ç¨è¡¨æ ¼ååº")
            return img_map

        # éåææç« ï¿½?
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_wordcloud_widgets(blocks, img_map)

        if img_map:
            logger.info(f"æåè½¬æ¢ {len(img_map)} ä¸ªè¯äºä¸ºå¾ç")
        return img_map

    def _extract_and_convert_widgets(
        self,
        blocks: list,
        svg_map: Dict[str, str]
    ) -> None:
        """
        éå½éåblocksï¼æ¾å°ææwidgetå¹¶è½¬æ¢ä¸ºSVG

        åæ°:
            blocks: blockåè¡¨
            svg_map: ç¨äºå­å¨è½¬æ¢ç»æçå­ï¿½?
        """
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')

            # å¤çwidgetç±»å
            if block_type == 'widget':
                widget_id = block.get('widgetId')
                widget_type = block.get('widgetType', '')

                # åªå¤çchart.jsç±»åçwidget
                if widget_id and widget_type.startswith('chart.js'):
                    widget_type_lower = widget_type.lower()
                    props = block.get('props')
                    props_type = str(props.get('type') or '').lower() if isinstance(props, dict) else ''
                    if 'wordcloud' in widget_type_lower or 'wordcloud' in props_type:
                        logger.debug(f"æ£æµå°è¯äº {widget_id}ï¼è·³è¿SVGè½¬æ¢å¹¶ä½¿ç¨å¾çæ³¨å¥æµï¿½?)
                        continue

                    failed, fail_reason = self.html_renderer._has_chart_failure(block)
                    if block.get("_chart_renderable") is False or failed:
                        logger.debug(
                            f"è·³è¿è½¬æ¢å¤±è´¥çå¾ï¿½?{widget_id}"
                            f"{f'ï¼åï¿½? {fail_reason}' if fail_reason else ''}"
                        )
                        continue
                    try:
                        svg_content = self.chart_converter.convert_widget_to_svg(
                            block,
                            width=800,
                            height=500,
                            dpi=100
                        )
                        if svg_content:
                            svg_map[widget_id] = svg_content
                            logger.debug(f"å¾è¡¨ {widget_id} è½¬æ¢ä¸ºSVGæå")
                        else:
                            logger.warning(f"å¾è¡¨ {widget_id} è½¬æ¢ä¸ºSVGå¤±è´¥")
                    except Exception as e:
                        logger.error(f"è½¬æ¢å¾è¡¨ {widget_id} æ¶åºï¿½? {e}")

            # éå½å¤çåµå¥çblocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_and_convert_widgets(nested_blocks, svg_map)

            # å¤çåè¡¨ï¿½?
            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_and_convert_widgets(item, svg_map)

            # å¤çè¡¨æ ¼ååï¿½?
            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_and_convert_widgets(cell_blocks, svg_map)

    def _extract_wordcloud_widgets(
        self,
        blocks: list,
        img_map: Dict[str, str]
    ) -> None:
        """
        éå½éåblocksï¼æ¾å°è¯äºwidgetå¹¶çæå¾ï¿½?
        """
        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')
            if block_type == 'widget':
                widget_id = block.get('widgetId')
                widget_type = block.get('widgetType', '')

                props = block.get('props')
                props_type = str(props.get('type') or '') if isinstance(props, dict) else ''
                is_wordcloud = (
                    isinstance(widget_type, str) and 'wordcloud' in widget_type.lower()
                ) or ('wordcloud' in props_type.lower())

                if widget_id and is_wordcloud:
                    try:
                        data_uri = self._generate_wordcloud_image(block)
                        if data_uri:
                            img_map[widget_id] = data_uri
                            logger.debug(f"è¯äº {widget_id} è½¬æ¢ä¸ºå¾çæï¿½?)
                    except Exception as exc:
                        logger.warning(f"çæè¯äºå¾çå¤±è´¥ {widget_id}: {exc}")

            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_wordcloud_widgets(nested_blocks, img_map)

            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_wordcloud_widgets(item, img_map)

            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_wordcloud_widgets(cell_blocks, img_map)

    def _normalize_wordcloud_items(self, block: Dict[str, Any]) -> list:
        """
        ä»widget blockä¸­æåè¯äºæ°ï¿½?
        """
        props = block.get('props') or {}
        raw_items = props.get('data')
        if not isinstance(raw_items, list):
            return []
        normalized = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            word = item.get('word') or item.get('text') or item.get('label')
            if not word:
                continue
            weight = item.get('weight')
            try:
                weight_val = float(weight)
                if weight_val <= 0:
                    weight_val = 1.0
            except (TypeError, ValueError):
                weight_val = 1.0
            category = (item.get('category') or '').lower()
            normalized.append({'word': str(word), 'weight': weight_val, 'category': category})
        return normalized

    def _generate_wordcloud_image(self, block: Dict[str, Any]) -> str | None:
        """
        çæè¯äºPNGå¹¶è¿ådata URI
        """
        items = self._normalize_wordcloud_items(block)
        if not items:
            return None

        # ä½¿ç¨é¢æ¬¡å½¢å¼é¦å¥wordcloudï¿½?
        frequencies = {}
        for item in items:
            weight = item['weight']
            # å¼å®¹æéï¿½?-1çå°æ°ï¼æ¾å¤§ä»¥ä½ç°å·®ï¿½?
            freq = weight * 100 if 0 < weight <= 1.5 else weight
            frequencies[item['word']] = max(1, freq)

        font_path = str(self._get_font_path())
        wc = WordCloud(
            width=1000,
            height=360,
            background_color="white",
            font_path=font_path,
            prefer_horizontal=0.98,
            random_state=42,
            max_words=180,
            collocations=False,
        )
        wc.generate_from_frequencies(frequencies)

        buffer = io.BytesIO()
        wc.to_image().save(buffer, format='PNG')
        encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    def _convert_math_to_svg(self, document_ir: Dict[str, Any]) -> Dict[str, str]:
        """
        å°document_irä¸­çæææ°å­¦å¬å¼è½¬æ¢ä¸ºSVG

        åæ°:
            document_ir: Document IRæ°æ®

        è¿å:
            Dict[str, str]: å¬å¼åIDå°SVGå­ç¬¦ä¸²çæ å°
        """
        svg_map = {}

        if not hasattr(self, 'math_converter') or not self.math_converter:
            logger.warning("æ°å­¦å¬å¼è½¬æ¢å¨æªåå§åï¼è·³è¿å¬å¼è½¬æ¢")
            return svg_map

        # éåææç« èï¼ä¿æå¨å±è®¡æ°å¨é¿åIDéå¤
        block_counter = [0]
        chapters = document_ir.get('chapters', [])
        for chapter in chapters:
            blocks = chapter.get('blocks', [])
            self._extract_and_convert_math_blocks(blocks, svg_map, block_counter)

        logger.info(f"æåè½¬æ¢ {len(svg_map)} ä¸ªæ°å­¦å¬å¼ä¸ºSVG")
        return svg_map

    def _extract_and_convert_math_blocks(
        self,
        blocks: list,
        svg_map: Dict[str, str],
        block_counter: list = None
    ) -> None:
        """
        éå½éåblocksï¼æ¾å°ææmathåå¹¶è½¬æ¢ä¸ºSVG

        åæ°:
            blocks: blockåè¡¨
            svg_map: ç¨äºå­å¨è½¬æ¢ç»æçå­ï¿½?
            block_counter: ç¨äºçæå¯ä¸IDçè®¡æ°å¨
        """
        if block_counter is None:
            block_counter = [0]

        def _extract_inline_math_from_inlines(inlines: list):
            """ä»æ®µè½åèèç¹ä¸­æåæ°å­¦å¬å¼"""
            if not isinstance(inlines, list):
                return
            for run in inlines:
                if not isinstance(run, dict):
                    continue
                marks = run.get('marks') or []
                math_mark = next((m for m in marks if m.get('type') == 'math'), None)

                if math_mark:
                    # ä»åä¸ªmath mark
                    raw = math_mark.get('value') or run.get('text') or ''
                    latex = self._normalize_latex(raw)
                    # è¡åmarkç»ä¸æinlineå¤çï¼é¿åè¯¯å°è¡åå¬å¼å½ædisplay
                    is_display = False
                    if not latex:
                        continue
                    block_counter[0] += 1
                    math_id = run.get('mathId') or f"math-inline-{block_counter[0]}"
                    run['mathId'] = math_id
                    try:
                        svg_content = (
                            self.math_converter.convert_display_to_svg(latex)
                            if is_display else
                            self.math_converter.convert_inline_to_svg(latex)
                        )
                        if svg_content:
                            svg_map[math_id] = svg_content
                            logger.debug(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGæå")
                        else:
                            logger.warning(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGå¤±è´¥: {latex[:50]}...")
                    except Exception as exc:
                        logger.error(f"è½¬æ¢åèå¬å¼ {latex[:50]}... æ¶åºï¿½? {exc}")
                    continue

                # æ math markï¼å°è¯è§£æææ¬ä¸­çå¤ä¸ªå¬ï¿½?
                text_val = run.get('text')
                if not isinstance(text_val, str):
                    continue
                segments = self._find_all_math_in_text(text_val)
                if not segments:
                    continue
                ids_for_html: list[str] = []
                for idx, (latex, is_display) in enumerate(segments, start=1):
                    if not latex:
                        continue
                    block_counter[0] += 1
                    math_id = f"auto-math-{block_counter[0]}"
                    ids_for_html.append(math_id)
                    try:
                        svg_content = (
                            self.math_converter.convert_display_to_svg(latex)
                            if is_display else
                            self.math_converter.convert_inline_to_svg(latex)
                        )
                        if svg_content:
                            svg_map[math_id] = svg_content
                            logger.debug(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGæå")
                        else:
                            logger.warning(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGå¤±è´¥: {latex[:50]}...")
                    except Exception as exc:
                        logger.error(f"è½¬æ¢åèå¬å¼ {latex[:50]}... æ¶åºï¿½? {exc}")
                if ids_for_html:
                    # å°IDåè¡¨åårunï¼ä¾¿äºHTMLæ¸²ææ¶ä½¿ç¨ç¸åIDï¼é¡ºåºå¯¹åºsegmentsï¿½?
                    run['mathIds'] = ids_for_html

        for block in blocks:
            if not isinstance(block, dict):
                continue

            block_type = block.get('type')

            # å¤çmathç±»å
            if block_type == 'math':
                latex = self._normalize_latex(block.get('latex', ''))
                if latex:
                    block_counter[0] += 1
                    math_id = f"math-block-{block_counter[0]}"
                    try:
                        svg_content = self.math_converter.convert_display_to_svg(latex)
                        if svg_content:
                            svg_map[math_id] = svg_content
                            # å°IDæ·»å å°blockä¸­ï¼ä»¥ä¾¿åç»­æ³¨å¥æ¶è¯ï¿½?
                            block['mathId'] = math_id
                            logger.debug(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGæå")
                        else:
                            logger.warning(f"å¬å¼ {math_id} è½¬æ¢ä¸ºSVGå¤±è´¥: {latex[:50]}...")
                    except Exception as e:
                        logger.error(f"è½¬æ¢å¬å¼ {latex[:50]}... æ¶åºï¿½? {e}")
            else:
                # æåæ®µè½ãè¡¨æ ¼ç­åé¨çåèå¬ï¿½?
                inlines = block.get('inlines')
                if inlines:
                    _extract_inline_math_from_inlines(inlines)

            # éå½å¤çåµå¥çblocks
            nested_blocks = block.get('blocks')
            if isinstance(nested_blocks, list):
                self._extract_and_convert_math_blocks(nested_blocks, svg_map, block_counter)

            # å¤çåè¡¨ï¿½?
            if block_type == 'list':
                items = block.get('items', [])
                for item in items:
                    if isinstance(item, list):
                        self._extract_and_convert_math_blocks(item, svg_map, block_counter)

            # å¤çè¡¨æ ¼ååï¿½?
            if block_type == 'table':
                rows = block.get('rows', [])
                for row in rows:
                    cells = row.get('cells', [])
                    for cell in cells:
                        cell_blocks = cell.get('blocks', [])
                        if isinstance(cell_blocks, list):
                            self._extract_and_convert_math_blocks(cell_blocks, svg_map, block_counter)

            # å¤çcalloutåé¨çblocks
            if block_type == 'callout':
                callout_blocks = block.get('blocks', [])
                if isinstance(callout_blocks, list):
                    self._extract_and_convert_math_blocks(callout_blocks, svg_map, block_counter)

    def _inject_svg_into_html(self, html: str, svg_map: Dict[str, str]) -> str:
        """
        å°SVGåå®¹ç´æ¥æ³¨å¥å°HTMLä¸­ï¼ä¸ä½¿ç¨JavaScriptï¿½?

        åæ°:
            html: åå§HTMLåå®¹
            svg_map: widgetIdå°SVGåå®¹çæ ï¿½?

        è¿å:
            str: æ³¨å¥SVGåçHTML
        """
        if not svg_map:
            return html

        import re

        # ä¸ºæ¯ä¸ªwidgetIdæ¥æ¾å¯¹åºçcanvaså¹¶æ¿æ¢ä¸ºSVG
        for widget_id, svg_content in svg_map.items():
            # æ¸çSVGåå®¹ï¼ç§»é¤XMLå£°æï¼å ä¸ºSVGå°åµå¥HTMLï¿½?
            svg_content = re.sub(r'<\?xml[^>]+\?>', '', svg_content)
            svg_content = re.sub(r'<!DOCTYPE[^>]+>', '', svg_content)
            svg_content = svg_content.strip()

            # åå»ºSVGå®¹å¨HTML
            svg_html = f'<div class="chart-svg-container">{svg_content}</div>'

            # æ¥æ¾åå«æ­¤widgetIdçéç½®èæ¬ï¼éå¶å¨åä¸ï¿½?/script>åï¼é¿åè·¨æ ç­¾è¯¯éï¼
            config_pattern = rf'<script[^>]+id="([^"]+)"[^>]*>(?:(?!</script>).)*?"widgetId"\s*:\s*"{re.escape(widget_id)}"(?:(?!</script>).)*?</script>'
            match = re.search(config_pattern, html, re.DOTALL)

            if match:
                config_id = match.group(1)

                # æ¥æ¾å¯¹åºçcanvasåç´ 
                # æ ¼å¼: <canvas id="chart-N" data-config-id="chart-config-N"></canvas>
                canvas_pattern = rf'<canvas[^>]+data-config-id="{re.escape(config_id)}"[^>]*></canvas>'

                # ãä¿®å¤ãæ¿æ¢canvasä¸ºSVGï¼ä½¿ç¨lambdaé¿ååææ è½¬ä¹é®ï¿½?
                html, replaced = re.subn(canvas_pattern, lambda m: svg_html, html, count=1)
                if replaced:
                    logger.debug(f"å·²æ¿æ¢å¾ï¿½?{widget_id} çcanvasä¸ºSVG")
                else:
                    logger.warning(f"æªæ¾å°å¾ï¿½?{widget_id} çcanvasè¿è¡æ¿æ¢")

                # å°å¯¹åºfallbackæ è®°ä¸ºéèï¼é¿åPDFä¸­åºç°éå¤è¡¨ï¿½?
                fallback_pattern = rf'<div class="chart-fallback"([^>]*data-widget-id="{re.escape(widget_id)}"[^>]*)>'

                def _hide_fallback(m: re.Match) -> str:
                    """ä¸ºå¹éå°çå¾è¡¨fallbackæ·»å éèç±»ï¼é²æ­¢PDFä¸­éå¤æ¸²ï¿½?""
                    tag = m.group(0)
                    if 'svg-hidden' in tag:
                        return tag
                    return tag.replace('chart-fallback"', 'chart-fallback svg-hidden"', 1)

                html = re.sub(fallback_pattern, _hide_fallback, html, count=1)
            else:
                logger.warning(f"æªæ¾å°å¾ï¿½?{widget_id} å¯¹åºçéç½®èï¿½?)

        return html

    @staticmethod
    def _normalize_latex(raw: Any) -> str:
        """å»é¤å¤å±æ°å­¦å®çç¬¦ï¼å¼å®¹ $...$ï¿½?$...$$\(\\)\[\\] ç­æ ¼ï¿½?""
        if not isinstance(raw, str):
            return ""
        latex = raw.strip()
        patterns = [
            r'^\$\$(.*)\$\$$',
            r'^\$(.*)\$$',
            r'^\\\[(.*)\\\]$',
            r'^\\\((.*)\\\)$',
        ]
        for pat in patterns:
            m = re.match(pat, latex, re.DOTALL)
            if m:
                latex = m.group(1).strip()
                break
        # æ¸çæ§å¶å­ç¬¦ãé²æ­¢mathtextè§£æå¤±è´¥
        latex = re.sub(r'[\x00-\x1f\x7f]', '', latex)
        # å¸¸è§å¼å®¹ï¼\tfrac/\dfrac -> \frac
        latex = latex.replace(r'\tfrac', r'\frac').replace(r'\dfrac', r'\frac')
        return latex

    @staticmethod
    def _find_first_math_in_text(text: Any) -> tuple[str, bool] | None:
        """ä»çº¯ææ¬ä¸­æåé¦ä¸ªæ°å­¦çæ®µï¼è¿å(åå®¹, æ¯å¦display)"""
        if not isinstance(text, str):
            return None
        pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]', re.S)
        matches = list(pattern.finditer(text))
        if not matches:
            return None
        m = matches[0]
        raw = next(g for g in m.groups() if g is not None)
        latex = raw.strip()
        is_display_raw = bool(m.group(1) or m.group(4))  # $$ or \[ \]
        is_standalone = (
            len(matches) == 1 and
            not text[:m.start()].strip() and
            not text[m.end():].strip()
        )
        return latex, bool(is_display_raw and is_standalone)

    @staticmethod
    def _find_all_math_in_text(text: Any) -> list[tuple[str, bool]]:
        """ä»çº¯ææ¬ä¸­æåæææ°å­¦çæ®µï¼è¿å[(åå®¹, æ¯å¦display)]"""
        if not isinstance(text, str):
            return []
        pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\]', re.S)
        results = []
        matches = list(pattern.finditer(text))
        if not matches:
            return results
        total = len(matches)

        for m in matches:
            raw = next(g for g in m.groups() if g is not None)
            latex = raw.strip()
            is_display_raw = bool(m.group(1) or m.group(4))
            is_standalone = (
                total == 1 and
                not text[:m.start()].strip() and
                not text[m.end():].strip()
            )
            is_display = is_display_raw and is_standalone
            results.append((latex, is_display))
        return results

    def _inject_wordcloud_images(self, html: str, img_map: Dict[str, str]) -> str:
        """
        å°è¯äºPNG data URIæ³¨å¥HTMLï¼æ¿æ¢å¯¹åºcanvas
        """
        if not img_map:
            return html

        import re

        for widget_id, data_uri in img_map.items():
            img_html = (
                f'<div class="chart-svg-container wordcloud-img">'
                f'<img src="{data_uri}" alt="è¯äº" />'
                f'</div>'
            )

            config_pattern = rf'<script[^>]+id="([^"]+)"[^>]*>(?:(?!</script>).)*?"widgetId"\s*:\s*"{re.escape(widget_id)}"(?:(?!</script>).)*?</script>'
            match = re.search(config_pattern, html, re.DOTALL)
            if not match:
                logger.debug(f"æªæ¾å°è¯ï¿½?{widget_id} çéç½®èæ¬ï¼è·³è¿æ³¨å¥")
                continue

            config_id = match.group(1)
            canvas_pattern = rf'<canvas[^>]+data-config-id="{re.escape(config_id)}"[^>]*></canvas>'

            html, replaced = re.subn(canvas_pattern, lambda m: img_html, html, count=1)
            if replaced:
                logger.debug(f"å·²æ¿æ¢è¯ï¿½?{widget_id} çcanvasä¸ºPNGå¾ç")
            else:
                logger.warning(f"æªæ¾å°è¯ï¿½?{widget_id} çcanvasè¿è¡æ¿æ¢")

            fallback_pattern = rf'<div class="chart-fallback"([^>]*data-widget-id="{re.escape(widget_id)}"[^>]*)>'

            def _hide_fallback(m: re.Match) -> str:
                """å¹éè¯äºè¡¨æ ¼ååºå¹¶æä¸éèæ è®°ï¼é¿åSVG/å¾çéå¤æ¾ç¤º"""
                tag = m.group(0)
                if 'svg-hidden' in tag:
                    return tag
                return tag.replace('chart-fallback"', 'chart-fallback svg-hidden"', 1)

            html = re.sub(fallback_pattern, _hide_fallback, html, count=1)

        return html

    def _inject_math_svg_into_html(self, html: str, svg_map: Dict[str, str]) -> str:
        """
        å°æ°å­¦å¬å¼SVGåå®¹æ³¨å¥å°HTMLï¿½?

        åæ°:
            html: åå§HTMLåå®¹
            svg_map: å¬å¼IDå°SVGåå®¹çæ ï¿½?

        è¿å:
            str: æ³¨å¥SVGåçHTML
        """
        if not svg_map:
            return html

        import re

        # ä¼åæ¿æ¢åèå¬å¼ï¼åæ¿æ¢åçº§å¬å¼ï¼ä¿æé¡ºåºä¸ï¿½?
        for math_id, svg_content in svg_map.items():
            # æ¸çSVGåå®¹ï¼ç§»é¤XMLå£°æï¼å ä¸ºSVGå°åµå¥HTMLï¿½?
            svg_content = re.sub(r'<\?xml[^>]+\?>', '', svg_content)
            svg_content = re.sub(r'<!DOCTYPE[^>]+>', '', svg_content)
            svg_content = svg_content.strip()

            svg_block_html = f'<div class="math-svg-container">{svg_content}</div>'
            svg_inline_html = f'<span class="math-svg-inline">{svg_content}</span>'

            replaced = False
            # ä¼åï¿½?data-math-id ç²¾ç¡®æ¿æ¢
            inline_pattern = rf'<span class="math-inline"[^>]*data-math-id="{re.escape(math_id)}"[^>]*>.*?</span>'
            if re.search(inline_pattern, html, re.DOTALL):
                html = re.sub(inline_pattern, lambda m: svg_inline_html, html, count=1)
                replaced = True
            else:
                block_pattern = rf'<div class="math-block"[^>]*data-math-id="{re.escape(math_id)}"[^>]*>.*?</div>'
                if re.search(block_pattern, html, re.DOTALL):
                    html = re.sub(block_pattern, lambda m: svg_block_html, html, count=1)
                    replaced = True

            # å¦ææ²¡ææ¾å°ç¹å®IDï¼æåºç°é¡ºåºååºæ¿æ¢
            if not replaced:
                html, sub_inline = re.subn(r'<span class="math-inline">[^<]*</span>', lambda m: svg_inline_html, html, count=1)
                if sub_inline:
                    replaced = True
                else:
                    html, sub_block = re.subn(r'<div class="math-block">\$\$[^$]*\$\$</div>', lambda m: svg_block_html, html, count=1)
                    if sub_block:
                        replaced = True

            if replaced:
                logger.debug(f"å·²æ¿æ¢å¬ï¿½?{math_id} ä¸ºSVG")

        return html

    def _get_pdf_html(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True,
        ir_file_path: str | None = None
    ) -> str:
        """
        çæéç¨äºPDFçHTMLåå®¹

        - ç§»é¤äº¤äºå¼åç´ ï¼æé®ãå¯¼èªç­ï¿½?
        - æ·»å PDFä¸ç¨æ ·å¼
        - åµå¥å­ä½æä»¶
        - åºç¨å¸å±ä¼å
        - å°å¾è¡¨è½¬æ¢ä¸ºSVGç¢éå¾å½¢

        åæ°:
            document_ir: Document IRæ°æ®
            optimize_layout: æ¯å¦å¯ç¨å¸å±ä¼å
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­

        è¿å:
            str: ä¼ååçHTMLåå®¹
        """
        # å¦æå¯ç¨å¸å±ä¼åï¼ååæææ¡£å¹¶çæä¼åéï¿½?
        if optimize_layout:
            logger.info("å¯ç¨PDFå¸å±ä¼å...")
            layout_config = self.layout_optimizer.optimize_for_document(document_ir)

            # ä¿å­ä¼åæ¥å¿
            log_dir = Path('logs/pdf_layouts')
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"layout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            # ä¿å­éç½®åä¼åæ¥ï¿½?
            optimization_log = self.layout_optimizer._log_optimization(
                self.layout_optimizer._analyze_document(document_ir),
                layout_config
            )
            self.layout_optimizer.config = layout_config
            self.layout_optimizer.save_config(log_file, optimization_log)
        else:
            layout_config = self.layout_optimizer.config

        # å³é®ä¿®å¤ï¼åé¢å¤çå¾è¡¨ï¼ç¡®ä¿æ°æ®ææ
        logger.info("é¢å¤çå¾è¡¨æ°ï¿½?..")
        preprocessed_ir = self._preprocess_charts(document_ir, ir_file_path)

        # è½¬æ¢å¾è¡¨ä¸ºSVGï¼ä½¿ç¨é¢å¤çåçIRï¿½?
        logger.info("å¼å§è½¬æ¢å¾è¡¨ä¸ºSVGç¢éå¾å½¢...")
        svg_map = self._convert_charts_to_svg(preprocessed_ir)

        # è½¬æ¢è¯äºä¸ºPNG
        logger.info("å¼å§è½¬æ¢è¯äºä¸ºå¾ç...")
        wordcloud_map = self._convert_wordclouds_to_images(preprocessed_ir)

        # è½¬æ¢æ°å­¦å¬å¼ä¸ºSVG
        logger.info("å¼å§è½¬æ¢æ°å­¦å¬å¼ä¸ºSVGç¢éå¾å½¢...")
        math_svg_map = self._convert_math_to_svg(preprocessed_ir)

        # ä½¿ç¨HTMLæ¸²æå¨çæåºç¡HTMLï¼ä½¿ç¨é¢å¤çåçIRï¼ä»¥ä¾¿å¤ç¨mathIdç­æ è®°ï¼
        html = self.html_renderer.render(preprocessed_ir, ir_file_path=ir_file_path)

        # æ³¨å¥å¾è¡¨SVG
        if svg_map:
            html = self._inject_svg_into_html(html, svg_map)
            logger.info(f"å·²æ³¨ï¿½?{len(svg_map)} ä¸ªSVGå¾è¡¨")

        if wordcloud_map:
            html = self._inject_wordcloud_images(html, wordcloud_map)
            logger.info(f"å·²æ³¨ï¿½?{len(wordcloud_map)} ä¸ªè¯äºå¾ï¿½?)

        # æ³¨å¥æ°å­¦å¬å¼SVG
        if math_svg_map:
            html = self._inject_math_svg_into_html(html, math_svg_map)
            logger.info(f"å·²æ³¨ï¿½?{len(math_svg_map)} ä¸ªSVGå¬å¼")

        # è·åå­ä½è·¯å¾å¹¶è½¬æ¢ä¸ºbase64ï¼ç¨äºåµå¥ï¼
        font_path = self._get_font_path()
        font_data = font_path.read_bytes()
        font_base64 = base64.b64encode(font_data).decode('ascii')

        # å¤æ­å­ä½æ ¼å¼
        font_format = 'opentype' if font_path.suffix == '.otf' else 'truetype'

        # çæä¼ååçCSS
        optimized_css = self.layout_optimizer.generate_pdf_css()

        # æ·»å PDFä¸ç¨CSS
        pdf_css = f"""
<style>
/* PDFä¸ç¨å­ä½åµå¥ */
@font-face {{
    font-family: 'SourceHanSerif';
    src: url(data:font/{font_format};base64,{font_base64}) format('{font_format}');
    font-weight: normal;
    font-style: normal;
}}

/* å¼ºå¶ææææ¬ä½¿ç¨ææºå®ä½ */
body, h1, h2, h3, h4, h5, h6, p, li, td, th, div, span {{
    font-family: 'SourceHanSerif', serif !important;
}}

/* PDFä¸ç¨æ ·å¼è°æ´ */
.report-header {{
    display: none !important;
}}

.no-print {{
    display: none !important;
}}

body {{
    background: white !important;
}}

/* ========== ä¿®å¤ WeasyPrint CSS åéæ¸åå¼å®¹æ§é®ï¿½?========== */
/* WeasyPrint ä¸æ¯æå¨ linear-gradient ä¸­ä½¿ï¿½?var()ï¼éè¦ç¨éæå¼è¦ï¿½?*/

/* è¦çæé®æ¸å */
.action-btn {{
    background: linear-gradient(135deg, #4a90e2 0%, #17a2b8 100%) !important;
}}

/* è¦çè¿åº¦æ¡æ¸ï¿½?*/
.export-progress::after {{
    background: linear-gradient(90deg, #4a90e2, #17a2b8) !important;
}}

/* è¦ç PEST å¡çæ é¢æ¸å */
.pest-card__title {{
    background: linear-gradient(135deg, #8e44ad, #2980b9) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
}}

/* è¦ç PEST æ¡å¸¦æç¤ºå¨æ¸ï¿½?*/
.pest-strip__indicator.political {{
    background: linear-gradient(180deg, #8e44ad, rgba(142,68,173,0.8)) !important;
}}
.pest-strip__indicator.economic {{
    background: linear-gradient(180deg, #16a085, rgba(22,160,133,0.8)) !important;
}}
.pest-strip__indicator.social {{
    background: linear-gradient(180deg, #e84393, rgba(232,67,147,0.8)) !important;
}}
.pest-strip__indicator.technological {{
    background: linear-gradient(180deg, #2980b9, rgba(41,128,185,0.8)) !important;
}}

/* è¦ç PEST æ¡å¸¦èæ¯ï¼åæ¥ä½¿ï¿½?var(--pest-strip-*-bg)ï¼åå«æ¸åååéï¿½?*/
.pest-strip {{
    background: #ffffff !important;
}}
.pest-strip.political {{
    background: linear-gradient(90deg, rgba(142,68,173,0.08), rgba(255,255,255,0.85)), #ffffff !important;
    border-color: rgba(142,68,173,0.4) !important;
}}
.pest-strip.economic {{
    background: linear-gradient(90deg, rgba(22,160,133,0.08), rgba(255,255,255,0.85)), #ffffff !important;
    border-color: rgba(22,160,133,0.4) !important;
}}
.pest-strip.social {{
    background: linear-gradient(90deg, rgba(232,67,147,0.08), rgba(255,255,255,0.85)), #ffffff !important;
    border-color: rgba(232,67,147,0.4) !important;
}}
.pest-strip.technological {{
    background: linear-gradient(90deg, rgba(41,128,185,0.08), rgba(255,255,255,0.85)), #ffffff !important;
    border-color: rgba(41,128,185,0.4) !important;
}}

/* è¦ç SWOT å¡çèæ¯ï¼åæ¥ä½¿ï¿½?var(--swot-card-bg)ï¼åå«æ¸åååéï¿½?*/
.swot-card {{
    background: linear-gradient(135deg, rgba(76,132,255,0.04), rgba(28,127,110,0.06)), #ffffff !important;
}}

/* è¦ç SWOT ååæ ¼èæ¯ï¼åæ¥ä½¿ç¨ var(--swot-cell-*-bg)ï¼åå«æ¸åååéï¿½?*/
.swot-cell {{
    background: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,255,255,0.5)) !important;
}}
.swot-cell.strength {{
    background: linear-gradient(135deg, rgba(28,127,110,0.07), rgba(255,255,255,0.78)), #ffffff !important;
    border-color: rgba(28,127,110,0.35) !important;
}}
.swot-cell.weakness {{
    background: linear-gradient(135deg, rgba(192,57,43,0.07), rgba(255,255,255,0.78)), #ffffff !important;
    border-color: rgba(192,57,43,0.35) !important;
}}
.swot-cell.opportunity {{
    background: linear-gradient(135deg, rgba(31,90,179,0.07), rgba(255,255,255,0.78)), #ffffff !important;
    border-color: rgba(31,90,179,0.35) !important;
}}
.swot-cell.threat {{
    background: linear-gradient(135deg, rgba(179,107,22,0.07), rgba(255,255,255,0.78)), #ffffff !important;
    border-color: rgba(179,107,22,0.35) !important;
}}

/* è¦ç SWOT å¾ä¾é¡¹åè¯ä¸¸ï¼ä½¿ç¨éæé¢è²ï¼ */
.swot-legend__item.strength, .swot-pill.strength {{
    background: #1c7f6e !important;
}}
.swot-legend__item.weakness, .swot-pill.weakness {{
    background: #c0392b !important;
}}
.swot-legend__item.opportunity, .swot-pill.opportunity {{
    background: #1f5ab3 !important;
}}
.swot-legend__item.threat, .swot-pill.threat {{
    background: #b36b16 !important;
}}

/* è¦çå¶ä»ä½¿ç¨ var() çåï¿½?*/
.swot-item {{
    background: rgba(255,255,255,0.92) !important;
}}
.swot-tag {{
    background: rgba(0,0,0,0.04) !important;
}}
.swot-empty {{
    border-color: #e0e0e0 !important;
}}

/* è¦ç PEST å¡çèæ¯ */
.pest-card {{
    background: linear-gradient(145deg, rgba(142,68,173,0.03), rgba(22,160,133,0.04)), #ffffff !important;
}}

/* è¦çå¾è¡¨å¡çéè¯¯ç¶ææ¸ï¿½?*/
.chart-card.chart-card--error {{
    background: linear-gradient(135deg, rgba(0,0,0,0.015), rgba(0,0,0,0.04)) !important;
}}

/* è¦çè¯äºå¾½ç« æ¸å */
.wordcloud-badge {{
    background: linear-gradient(135deg, rgba(74, 144, 226, 0.14) 0%, rgba(74, 144, 226, 0.24) 100%) !important;
}}

/* è¦çè±éåºåæ¸å */
.hero-section {{
    background: linear-gradient(135deg, rgba(0,123,255,0.1), rgba(23,162,184,0.1)) !important;
}}

/* ========== è¦ç hero-actions æé®æ ·å¼ï¼æ è¾¹æ¡æ ·å¼ï¿½?========== */
.hero-actions {{
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    margin-top: 14px !important;
    padding: 0 !important;
}}

.hero-actions button,
.hero-actions .ghost-btn,
button.ghost-btn {{
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
    font-size: 12px !important;
    color: #222 !important;
    white-space: normal !important;
    line-height: 1.5 !important;
    text-align: left !important;
    box-shadow: none !important;
    -webkit-appearance: none !important;
    -moz-appearance: none !important;
    appearance: none !important;
    outline: none !important;
    outline-width: 0 !important;
    word-break: break-word !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    margin: 0 !important;
    font-family: inherit !important;
}}

/* SVGå¾è¡¨å®¹å¨æ ·å¼ */
.chart-svg-container {{
    width: 100%;
    height: auto;
    display: flex;
    justify-content: center;
    align-items: center;
}}

.chart-svg-container svg {{
    max-width: 100%;
    height: auto;
}}
.chart-svg-container img {{
    max-width: 100%;
    height: auto;
}}

/* æ°å­¦å¬å¼SVGå®¹å¨æ ·å¼ */
.math-svg-container {{
    width: 100%;
    height: auto;
    display: flex;
    justify-content: center;
    align-items: center;
    margin: 20px 0;
}}

.math-svg-container svg {{
    max-width: 100%;
    height: auto;
}}

/* éèåå§çmath-blockï¼å ä¸ºå·²è¢«SVGæ¿æ¢ï¿½?*/
.math-block {{
    display: none !important;
}}

/* å½å¯¹åºSVGæåæ³¨å¥æ¶éèfallbackè¡¨æ ¼ï¼å¤±è´¥æ¶ç»§ç»­æ¾ç¤ºååºæ°æ® */
.chart-fallback.svg-hidden {{
    display: none !important;
}}

/* ç¡®ä¿chart-containeræ¾ç¤ºï¼ç¨äºæ¾ç½®SVGï¿½?*/
.chart-container {{
    display: block !important;
    min-height: 400px;
}}

/* ========== SWOT PDFè¡¨æ ¼å¸å± ========== */
/* æ ¸å¿ç­ç¥ï¼PDFä¸­ä½¿ç¨è¡¨æ ¼å½¢å¼èéå¡çå½¢å¼ï¼æ´éååé¡µ */

/* éèHTMLå¡çå¸å±ï¼æ¾ç¤ºPDFè¡¨æ ¼å¸å± */
.swot-card--html {{
    display: none !important;
}}

.swot-pdf-wrapper {{
    display: block !important;
    margin: 24px 0;
}}

/* PDFè¡¨æ ¼æ´ä½æ ·å¼ */
.swot-pdf-table {{
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 11px !important;
    table-layout: fixed !important;
    background: white;
}}

/* è¡¨æ ¼æ é¢ */
.swot-pdf-caption {{
    caption-side: top !important;
    text-align: left !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 12px 0 !important;
    color: #1a1a1a !important;
    border-bottom: 2px solid #333 !important;
    margin-bottom: 8px !important;
}}

/* è¡¨å¤´æ ·å¼ */
.swot-pdf-thead {{
    break-after: avoid !important;
    page-break-after: avoid !important;
}}

.swot-pdf-thead th {{
    background: #f0f0f0 !important;
    padding: 10px 8px !important;
    text-align: left !important;
    font-weight: 600 !important;
    border: 1px solid #ccc !important;
    color: #333 !important;
    font-size: 11px !important;
}}

.swot-pdf-th-quadrant {{ width: 70px !important; }}
.swot-pdf-th-num {{ width: 40px !important; text-align: center !important; }}
.swot-pdf-th-title {{ width: 20% !important; }}
.swot-pdf-th-detail {{ width: auto !important; }}
.swot-pdf-th-tags {{ width: 80px !important; text-align: center !important; }}

/* æè¦ï¿½?*/
.swot-pdf-summary {{
    padding: 10px 12px !important;
    background: #f8f8f8 !important;
    color: #555 !important;
    font-style: italic !important;
    border: 1px solid #ccc !important;
    font-size: 11px !important;
}}

/* æ¯ä¸ªè±¡éåºå - æ ¸å¿åé¡µæ§å¶ */
.swot-pdf-quadrant {{
    break-inside: avoid !important;
    page-break-inside: avoid !important;
}}

/* åè®¸å¨ä¸åè±¡éä¹é´åï¿½?*/
.swot-pdf-quadrant + .swot-pdf-quadrant {{
    break-before: auto;
    page-break-before: auto;
}}

/* è±¡éæ ç­¾ååï¿½?*/
.swot-pdf-quadrant-label {{
    text-align: center !important;
    vertical-align: middle !important;
    padding: 12px 6px !important;
    font-weight: 700 !important;
    border: 1px solid #ccc !important;
    width: 70px !important;
}}

/* åä¸ªè±¡éçé¢è²ä¸»ï¿½?*/
.swot-pdf-quadrant-label.swot-pdf-strength {{
    background: #e8f5f2 !important;
    color: #1c7f6e !important;
    border-left: 4px solid #1c7f6e !important;
}}
.swot-pdf-quadrant-label.swot-pdf-weakness {{
    background: #fdeaea !important;
    color: #c0392b !important;
    border-left: 4px solid #c0392b !important;
}}
.swot-pdf-quadrant-label.swot-pdf-opportunity {{
    background: #e8f0fa !important;
    color: #1f5ab3 !important;
    border-left: 4px solid #1f5ab3 !important;
}}
.swot-pdf-quadrant-label.swot-pdf-threat {{
    background: #fdf3e6 !important;
    color: #b36b16 !important;
    border-left: 4px solid #b36b16 !important;
}}

/* è±¡éä»£ç å­æ¯ */
.swot-pdf-code {{
    display: block !important;
    font-size: 20px !important;
    font-weight: 800 !important;
    margin-bottom: 2px !important;
}}

/* è±¡éæ ç­¾æå­ */
.swot-pdf-label-text {{
    display: block !important;
    font-size: 9px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
}}

/* æ°æ®ï¿½?*/
.swot-pdf-item-row td {{
    padding: 8px 6px !important;
    border: 1px solid #ddd !important;
    vertical-align: top !important;
    font-size: 11px !important;
    line-height: 1.4 !important;
}}

/* è¡èæ¯è² */
.swot-pdf-item-row.swot-pdf-strength td {{ background: #f7fbfa !important; }}
.swot-pdf-item-row.swot-pdf-weakness td {{ background: #fef9f9 !important; }}
.swot-pdf-item-row.swot-pdf-opportunity td {{ background: #f7f9fc !important; }}
.swot-pdf-item-row.swot-pdf-threat td {{ background: #fdfbf7 !important; }}

/* åºå·ååï¿½?*/
.swot-pdf-item-num {{
    text-align: center !important;
    font-weight: 600 !important;
    color: #888 !important;
    width: 40px !important;
}}

/* è¦ç¹æ é¢ */
.swot-pdf-item-title {{
    font-weight: 600 !important;
    color: #222 !important;
}}

/* è¯¦æè¯´æ */
.swot-pdf-item-detail {{
    color: #444 !important;
    line-height: 1.5 !important;
}}

/* æ ç­¾ååï¿½?*/
.swot-pdf-item-tags {{
    text-align: center !important;
}}

/* æ ç­¾æ ·å¼ */
.swot-pdf-tag {{
    display: inline-block !important;
    padding: 2px 6px !important;
    border-radius: 3px !important;
    font-size: 9px !important;
    background: #e9ecef !important;
    color: #495057 !important;
    margin: 1px !important;
}}

.swot-pdf-tag--score {{
    background: #fff3cd !important;
    color: #856404 !important;
}}

/* ç©ºæ°æ®æï¿½?*/
.swot-pdf-empty {{
    text-align: center !important;
    color: #999 !important;
    font-style: italic !important;
}}

/* ========== PEST PDFè¡¨æ ¼å¸å± ========== */
/* æ ¸å¿ç­ç¥ï¼PDFä¸­ä½¿ç¨è¡¨æ ¼å½¢å¼èéå¡çå½¢å¼ï¼æ´éååé¡µ */

/* éèHTMLå¡çå¸å±ï¼æ¾ç¤ºPDFè¡¨æ ¼å¸å± */
.pest-card--html {{
    display: none !important;
}}

.pest-pdf-wrapper {{
    display: block !important;
    margin: 24px 0;
}}

/* PDFè¡¨æ ¼æ´ä½æ ·å¼ */
.pest-pdf-table {{
    width: 100% !important;
    border-collapse: collapse !important;
    font-size: 11px !important;
    table-layout: fixed !important;
    background: white;
}}

/* è¡¨æ ¼æ é¢ */
.pest-pdf-caption {{
    caption-side: top !important;
    text-align: left !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    padding: 12px 0 !important;
    color: #333 !important;
    border-bottom: 2px solid #333 !important;
    margin-bottom: 8px !important;
}}

/* è¡¨å¤´æ ·å¼ */
.pest-pdf-thead {{
    break-after: avoid !important;
    page-break-after: avoid !important;
}}

.pest-pdf-thead th {{
    background: #f5f3f7 !important;
    padding: 10px 8px !important;
    text-align: left !important;
    font-weight: 600 !important;
    border: 1px solid #ccc !important;
    color: #4a4458 !important;
    font-size: 11px !important;
}}

.pest-pdf-th-dimension {{ width: 70px !important; }}
.pest-pdf-th-num {{ width: 40px !important; text-align: center !important; }}
.pest-pdf-th-title {{ width: 20% !important; }}
.pest-pdf-th-detail {{ width: auto !important; }}
.pest-pdf-th-tags {{ width: 80px !important; text-align: center !important; }}

/* æè¦ï¿½?*/
.pest-pdf-summary {{
    padding: 10px 12px !important;
    background: #f8f6fa !important;
    color: #555 !important;
    font-style: italic !important;
    border: 1px solid #ccc !important;
    font-size: 11px !important;
}}

/* æ¯ä¸ªç»´åº¦åºå - æ ¸å¿åé¡µæ§å¶ */
.pest-pdf-dimension {{
    break-inside: avoid !important;
    page-break-inside: avoid !important;
}}

/* åè®¸å¨ä¸åç»´åº¦ä¹é´åï¿½?*/
.pest-pdf-dimension + .pest-pdf-dimension {{
    break-before: auto;
    page-break-before: auto;
}}

/* ç»´åº¦æ ç­¾ååï¿½?*/
.pest-pdf-dimension-label {{
    text-align: center !important;
    vertical-align: middle !important;
    padding: 12px 6px !important;
    font-weight: 700 !important;
    border: 1px solid #ccc !important;
    width: 70px !important;
}}

/* åä¸ªç»´åº¦çé¢è²ä¸»ï¿½?*/
.pest-pdf-dimension-label.pest-pdf-political {{
    background: #f5eef8 !important;
    color: #8e44ad !important;
    border-left: 4px solid #8e44ad !important;
}}
.pest-pdf-dimension-label.pest-pdf-economic {{
    background: #e8f6f3 !important;
    color: #16a085 !important;
    border-left: 4px solid #16a085 !important;
}}
.pest-pdf-dimension-label.pest-pdf-social {{
    background: #fdecf4 !important;
    color: #e84393 !important;
    border-left: 4px solid #e84393 !important;
}}
.pest-pdf-dimension-label.pest-pdf-technological {{
    background: #ebf3f9 !important;
    color: #2980b9 !important;
    border-left: 4px solid #2980b9 !important;
}}

/* ç»´åº¦ä»£ç å­æ¯ */
.pest-pdf-code {{
    display: block !important;
    font-size: 20px !important;
    font-weight: 800 !important;
    margin-bottom: 2px !important;
}}

/* ç»´åº¦æ ç­¾æå­ */
.pest-pdf-label-text {{
    display: block !important;
    font-size: 9px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
}}

/* æ°æ®ï¿½?*/
.pest-pdf-item-row td {{
    padding: 8px 6px !important;
    border: 1px solid #ddd !important;
    vertical-align: top !important;
    font-size: 11px !important;
    line-height: 1.4 !important;
}}

/* è¡èæ¯è² */
.pest-pdf-item-row.pest-pdf-political td {{ background: #faf7fc !important; }}
.pest-pdf-item-row.pest-pdf-economic td {{ background: #f5fbfa !important; }}
.pest-pdf-item-row.pest-pdf-social td {{ background: #fef8fb !important; }}
.pest-pdf-item-row.pest-pdf-technological td {{ background: #f7fafd !important; }}

/* åºå·ååï¿½?*/
.pest-pdf-item-num {{
    text-align: center !important;
    font-weight: 600 !important;
    color: #888 !important;
    width: 40px !important;
}}

/* è¦ç¹æ é¢ */
.pest-pdf-item-title {{
    font-weight: 600 !important;
    color: #222 !important;
}}

/* è¯¦æè¯´æ */
.pest-pdf-item-detail {{
    color: #444 !important;
    line-height: 1.5 !important;
}}

/* æ ç­¾ååï¿½?*/
.pest-pdf-item-tags {{
    text-align: center !important;
}}

/* æ ç­¾æ ·å¼ */
.pest-pdf-tag {{
    display: inline-block !important;
    padding: 2px 6px !important;
    border-radius: 3px !important;
    font-size: 9px !important;
    background: #ece9f1 !important;
    color: #5a4f6a !important;
    margin: 1px !important;
}}

/* ç©ºæ°æ®æï¿½?*/
.pest-pdf-empty {{
    text-align: center !important;
    color: #999 !important;
    font-style: italic !important;
}}

{optimized_css}
</style>
"""

        # ï¿½?/head>åæå¥PDFä¸ç¨CSS
        html = html.replace('</head>', f'{pdf_css}\n</head>')

        return html

    def render_to_pdf(
        self,
        document_ir: Dict[str, Any],
        output_path: str | Path,
        optimize_layout: bool = True,
        ir_file_path: str | None = None
    ) -> Path:
        """
        å°Document IRæ¸²æä¸ºPDFæä»¶

        åæ°:
            document_ir: Document IRæ°æ®
            output_path: PDFè¾åºè·¯å¾
            optimize_layout: æ¯å¦å¯ç¨å¸å±ä¼åï¼é»è®¤Trueï¿½?
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­

        è¿å:
            Path: çæçPDFæä»¶è·¯å¾
        """
        output_path = Path(output_path)

        logger.info(f"å¼å§çæPDF: {output_path}")

        # çæHTMLåå®¹
        html_content = self._get_pdf_html(document_ir, optimize_layout, ir_file_path)

        # éç½®å­ä½
        font_config = FontConfiguration()

        # ä»HTMLå­ç¬¦ä¸²åå»ºWeasyPrint HTMLå¯¹è±¡
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        # çæPDF
        try:
            html_doc.write_pdf(
                output_path,
                font_config=font_config,
                presentational_hints=True  # ä¿çHTMLçåç°æï¿½?
            )
            logger.info(f"ï¿½?PDFçææå: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"PDFçæå¤±è´¥: {e}")
            raise

    def render_to_bytes(
        self,
        document_ir: Dict[str, Any],
        optimize_layout: bool = True,
        ir_file_path: str | None = None
    ) -> bytes:
        """
        å°Document IRæ¸²æä¸ºPDFå­èï¿½?

        åæ°:
            document_ir: Document IRæ°æ®
            optimize_layout: æ¯å¦å¯ç¨å¸å±ä¼åï¼é»è®¤Trueï¿½?
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­

        è¿å:
            bytes: PDFæä»¶çå­èåï¿½?
        """
        html_content = self._get_pdf_html(document_ir, optimize_layout, ir_file_path)
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content, base_url=str(Path.cwd()))

        return html_doc.write_pdf(
            font_config=font_config,
            presentational_hints=True
        )


__all__ = ["PDFRenderer"]
