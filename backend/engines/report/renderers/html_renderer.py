ï»¿"""
åºäºç« èIRçHTML/PDFæ¸²æå¨ï¼å®ç°ä¸ç¤ºä¾æ¥åä¸è´çäº¤äºä¸è§è§ï¿½?

æ°å¢è¦ç¹ï¿½?
1. åç½®Chart.jsæ°æ®éªè¯/ä¿®å¤ï¼ChartValidator+LLMååºï¼ï¼æç»éæ³éç½®å¯¼è´çæ³¨å¥æå´©æºï¿½?
2. å°MathJax/Chart.js/html2canvas/jspdfç­ä¾èµåèå¹¶å¸¦CDN fallbackï¼ééç¦»çº¿æè¢«å¢ç¯å¢ï¼
3. é¢ç½®ææºå®ä½å­éçBase64å­ä½ï¼ç¨äºPDF/HTMLä¸ä½åå¯¼åºï¼é¿åç¼ºå­æé¢å¤ç³»ç»ä¾èµï¿½?
"""

from __future__ import annotations

import ast
import copy
import html
import json
import os
import re
import base64
from pathlib import Path
from typing import Any, Dict, List
from loguru import logger

from backend.engines.report.ir.schema import ENGINE_AGENT_TITLES
from backend.engines.report.utils.chart_validator import (
    ChartValidator,
    ChartRepairer,
    ValidationResult,
    create_chart_validator,
    create_chart_repairer
)
from backend.engines.report.utils.chart_repair_api import create_llm_repair_functions
from backend.engines.report.utils.chart_review_service import get_chart_review_service


class HTMLRenderer:
    """
    Document IR ï¿½?HTML æ¸²æå¨ï¿½?

    - è¯»å IR metadata/chaptersï¼å°ç»ææ å°ä¸ºååºå¼HTMLï¿½?
    - å¨ææé ç®å½ãéç¹hart.jsèæ¬åäºå¨é»è¾ï¿½?
    - æä¾ä¸»é¢åéãç¼å·æ å°ç­è¾å©åè½ï¿½?
    """

    # ===== æ¸²ææµç¨å¿«éå¯¼è§ï¼ä¾¿äºå®ä½æ³¨éï¿½?=====
    # render(document_ir): åä¸å¬å¼å¥å£ï¼è´è´£éç½®ç¶æå¹¶ä¸²è _render_head / _render_bodyï¿½?
    # _render_head: æ ¹æ® themeTokens æï¿½?<head>ï¼æ³¨ï¿½?CSS åéãåèåºï¿½?CDN fallbackï¿½?
    # _render_body: ç»è£é¡µé¢éª¨æ¶ï¼é¡µï¿½?headerãç®ï¿½?tocãç« ï¿½?blocksãèæ¬æ³¨æ°´ï¼ï¿½?
    # _render_header: çæé¡¶é¨æé®åºåï¼æï¿½?ID åäºä»¶å¨ _hydration_script åç»å®ï¿½?
    # _render_widget: å¤ç Chart.js/è¯äºç»ä»¶ï¼åæ ¡éªä¸ä¿®å¤æ°æ®ï¼ååï¿½?<script type="application/json"> éç½®ï¿½?
    # _hydration_script: è¾åºæ«å°¾ JSï¼è´è´£æé®äº¤äºï¼ä¸»é¢åæ¢/æå°/å¯¼åºï¼ä¸å¾è¡¨å®ä¾åï¿½?

    CALLOUT_ALLOWED_TYPES = {
        "paragraph",
        "list",
        "table",
        "blockquote",
        "code",
        "math",
        "figure",
        "kpiGrid",
        "swotTable",
        "pestTable",
        "engineQuote",
    }
    INLINE_ARTIFACT_KEYS = {
        "props",
        "widgetId",
        "widgetType",
        "data",
        "dataRef",
        "datasets",
        "labels",
        "config",
        "options",
    }
    TABLE_COMPLEX_CHARS = set(
        "@ï¿½?ï¼ï¼()ï¿½?ãï¼;ï¿½?ãï¼?ï¿½?�·ï¿½?-_+<>[]{}|\\/\"'`~$^&*#"
    )

    def __init__(self, config: Dict[str, Any] | None = None):
        """
        åå§åæ¸²æå¨ç¼å­å¹¶åè®¸æ³¨å¥é¢å¤éç½®ï¿½?

        åæ°å±çº§è¯´æï¿½?
        - config: dict | Noneï¼ä¾è°ç¨æ¹ä¸´æ¶è¦çä¸»ï¿½?è°è¯å¼å³ç­ï¼ä¼åçº§æé«ï¼
          å¸åé®å¼ï¼
            - themeOverride: è¦çåæ°æ®éï¿½?themeTokensï¿½?
            - enableDebug: boolï¼æ¯å¦è¾åºé¢å¤æ¥å¿ï¿½?
        åé¨ç¶æï¼
        - self.document/metadata/chaptersï¼ä¿å­ä¸æ¬¡æ¸²æå¨æç IRï¿½?
        - self.widget_scriptsï¼æ¶éå¾è¡¨éï¿½?JSONï¼åç»­å¨ _render_body å°¾é¨æ³¨æ°´ï¿½?
        - self._lib_cache/_pdf_font_base64ï¼ç¼å­æ¬å°åºä¸å­ä½ï¼é¿åéå¤IOï¿½?
        - self.chart_validator/chart_repairerï¼Chart.js éç½®çæ¬å°ä¸ LLM ååºä¿®å¤å¨ï¼
        - self.chart_validation_statsï¼è®°å½æ»é/ä¿®å¤æ¥æº/å¤±è´¥æ°éï¼ä¾¿äºæ¥å¿å®¡è®¡ï¿½?
        """
        self.config = config or {}
        self.document: Dict[str, Any] = {}
        self.widget_scripts: List[str] = []
        self.chart_counter = 0
        self.toc_entries: List[Dict[str, Any]] = []
        self.heading_counter = 0
        self.metadata: Dict[str, Any] = {}
        self.chapters: List[Dict[str, Any]] = []
        self.chapter_anchor_map: Dict[str, str] = {}
        self.heading_label_map: Dict[str, Dict[str, Any]] = {}
        self.primary_heading_index = 0
        self.secondary_heading_index = 0
        self.toc_rendered = False
        self.hero_kpi_signature: tuple | None = None
        self._current_chapter: Dict[str, Any] | None = None
        self._lib_cache: Dict[str, str] = {}
        self._pdf_font_base64: str | None = None

        # åå§åå¾è¡¨éªè¯åä¿®å¤ï¿½?
        self.chart_validator = create_chart_validator()
        llm_repair_fns = create_llm_repair_functions()
        self.chart_repairer = create_chart_repairer(
            validator=self.chart_validator,
            llm_repair_fns=llm_repair_fns
        )
        # æå°LLMä¿®å¤å½æ°ç¶ï¿½?
        self._llm_repair_count = len(llm_repair_fns)
        if not llm_repair_fns:
            logger.warning("HTMLRenderer: æªéç½®ä»»ä½LLM APIï¼å¾è¡¨APIä¿®å¤åè½ä¸å¯ï¿½?)
        else:
            logger.info(f"HTMLRenderer: å·²éï¿½?{len(llm_repair_fns)} ä¸ªLLMä¿®å¤å½æ°")
        # è®°å½ä¿®å¤å¤±è´¥çå¾è¡¨ï¼é¿åå¤æ¬¡è§¦åLLMå¾ªç¯ä¿®å¤
        self._chart_failure_notes: Dict[str, str] = {}
        self._chart_failure_recorded: set[str] = set()

        # ç»è®¡ä¿¡æ¯
        self.chart_validation_stats = {
            'total': 0,
            'valid': 0,
            'repaired_locally': 0,
            'repaired_api': 0,
            'failed': 0
        }

    @staticmethod
    def _get_lib_path() -> Path:
        """è·åç¬¬ä¸æ¹åºæä»¶çç®å½è·¯ï¿½?""
        return Path(__file__).parent / "libs"

    @staticmethod
    def _get_font_path() -> Path:
        """è¿åPDFå¯¼åºæéå­ä½çè·¯å¾ï¼ä½¿ç¨ä¼ååçå­éå­ä½ï¿½?""
        return Path(__file__).parent / "assets" / "fonts" / "SourceHanSerifSC-Medium-Subset.ttf"

    def _load_lib(self, filename: str) -> str:
        """
        å è½½æå®çç¬¬ä¸æ¹åºæä»¶åï¿½?

        åæ°:
            filename: åºæä»¶å

        è¿å:
            str: åºæä»¶çJavaScriptä»£ç åå®¹
        """
        if filename in self._lib_cache:
            return self._lib_cache[filename]

        lib_path = self._get_lib_path() / filename
        try:
            with open(lib_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._lib_cache[filename] = content
                return content
        except FileNotFoundError:
            print(f"è­¦å: åºæï¿½?{filename} æªæ¾å°ï¼å°ä½¿ç¨CDNå¤ç¨é¾æ¥")
            return ""
        except Exception as e:
            print(f"è­¦å: è¯»ååºæï¿½?{filename} æ¶åºï¿½? {e}")
            return ""

    def _load_pdf_font_data(self) -> str:
        """å è½½PDFå­ä½çBase64æ°æ®ï¼é¿åéå¤è¯»åå¤§åæï¿½?""
        if self._pdf_font_base64 is not None:
            return self._pdf_font_base64
        font_path = self._get_font_path()
        try:
            data = font_path.read_bytes()
            self._pdf_font_base64 = base64.b64encode(data).decode("ascii")
            return self._pdf_font_base64
        except FileNotFoundError:
            logger.warning("PDFå­ä½æä»¶ç¼ºå¤±ï¿½?s", font_path)
        except Exception as exc:
            logger.warning("è¯»åPDFå­ä½æä»¶å¤±è´¥ï¿½?s (%s)", font_path, exc)
        self._pdf_font_base64 = ""
        return self._pdf_font_base64

    def _reset_chart_validation_stats(self) -> None:
        """éç½®å¾è¡¨æ ¡éªç»è®¡å¹¶æ¸é¤å¤±è´¥è®¡æ°æ ï¿½?""
        self.chart_validation_stats = {
            'total': 0,
            'valid': 0,
            'repaired_locally': 0,
            'repaired_api': 0,
            'failed': 0
        }
        # ä¿çå¤±è´¥åå ç¼å­ï¼ä½éç½®æ¬æ¬¡æ¸²æçè®¡ï¿½?
        self._chart_failure_recorded = set()

    def _build_script_with_fallback(
        self,
        inline_code: str,
        cdn_url: str,
        check_expression: str,
        lib_name: str,
        is_defer: bool = False
    ) -> str:
        """
        æå»ºå¸¦æCDN fallbackæºå¶çscriptæ ç­¾

        ç­ç¥ï¿½?
        1. ä¼ååµå¥æ¬å°åºä»£ï¿½?
        2. æ·»å æ£æµèæ¬ï¼éªè¯åºæ¯å¦æåå ï¿½?
        3. å¦ææ£æµå¤±è´¥ï¼å¨æå è½½CDNçæ¬ä½ä¸ºå¤ç¨

        åæ°:
            inline_code: æ¬å°åºçJavaScriptä»£ç åå®¹
            cdn_url: CDNå¤ç¨é¾æ¥
            check_expression: JavaScriptè¡¨è¾¾å¼ï¼ç¨äºæ£æµåºæ¯å¦å è½½æå
            lib_name: åºåç§°ï¼ç¨äºæ¥å¿è¾åºï¿½?
            is_defer: æ¯å¦ä½¿ç¨deferå±ï¿½?

        è¿å:
            str: å®æ´çscriptæ ç­¾HTML
        """
        defer_attr = ' defer' if is_defer else ''

        if inline_code:
            # åµå¥æ¬å°åºä»£ç ï¼å¹¶æ·»å fallbackæ£ï¿½?
            return f"""
  <script{defer_attr}>
    // {lib_name} - åµå¥å¼çï¿½?
    try {{
      {inline_code}
    }} catch (e) {{
      console.error('{lib_name}åµå¥å¼å è½½å¤±ï¿½?', e);
    }}
  </script>
  <script{defer_attr}>
    // {lib_name} - CDN Fallbackæ£ï¿½?
    (function() {{
      var checkLib = function() {{
        if (!({check_expression})) {{
          console.warn('{lib_name}æ¬å°çæ¬å è½½å¤±è´¥ï¼æ­£å¨ä»CDNå è½½å¤ç¨çæ¬...');
          var script = document.createElement('script');
          script.src = '{cdn_url}';
          script.onerror = function() {{
            console.error('{lib_name} CDNå¤ç¨å è½½ä¹å¤±è´¥äº');
          }};
          script.onload = function() {{
            console.log('{lib_name} CDNå¤ç¨çæ¬å è½½æå');
          }};
          document.head.appendChild(script);
        }}
      }};

      // å»¶è¿æ£æµï¼ç¡®ä¿åµå¥ä»£ç ææ¶é´æ§ï¿½?
      if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', function() {{
          setTimeout(checkLib, 100);
        }});
      }} else {{
        setTimeout(checkLib, 100);
      }}
    }})();
  </script>""".strip()
        else:
            # æ¬å°æä»¶è¯»åå¤±è´¥ï¼ç´æ¥ä½¿ç¨CDN
            logger.warning(f"{lib_name}æ¬å°æä»¶æªæ¾å°æè¯»åå¤±è´¥ï¼å°ç´æ¥ä½¿ç¨CDN")
            return f'  <script{defer_attr} src="{cdn_url}"></script>'

    # ====== å¬å±å¥å£ ======

    def render(
        self,
        document_ir: Dict[str, Any],
        ir_file_path: str | None = None
    ) -> str:
        """
        æ¥æ¶Document IRï¼éç½®åé¨ç¶æå¹¶è¾åºå®æ´HTMLï¿½?

        åæ°:
            document_ir: ï¿½?DocumentComposer çæçæ´æ¬æ¥åæ°æ®ï¿½?
            ir_file_path: å¯éï¼IR æä»¶è·¯å¾ï¼æä¾æ¶ä¿®å¤åä¼èªå¨ä¿å­ï¿½?

        è¿å:
            str: å¯ç´æ¥åå¥ç£ççå®æ´HTMLææ¡£ï¿½?
        """
        self.document = document_ir or {}

        # ä½¿ç¨ç»ä¸ï¿½?ChartReviewService è¿è¡å¾è¡¨å®¡æ¥ä¸ä¿®ï¿½?
        # ä¿®å¤ç»æä¼ç´æ¥ååå° document_irï¼é¿åå¤æ¬¡æ¸²æéå¤ä¿®ï¿½?
        # review_document è¿åæ¬æ¬¡ä¼è¯çç»è®¡ä¿¡æ¯ï¼çº¿ç¨å®å¨ï¿½?
        chart_service = get_chart_review_service()
        review_stats = chart_service.review_document(
            self.document,
            ir_file_path=ir_file_path,
            reset_stats=True,
            save_on_repair=bool(ir_file_path)
        )
        # åæ­¥ç»è®¡ä¿¡æ¯å°æ¬å°ï¼ç¨äºå¼å®¹æ§ç _log_chart_validation_statsï¿½?
        # ä½¿ç¨è¿åï¿½?ReviewStats å¯¹è±¡ï¼èéå±äº«ï¿½?chart_service.stats
        self.chart_validation_stats.update(review_stats.to_dict())

        self.widget_scripts = []
        self.chart_counter = 0
        self.heading_counter = 0
        self.metadata = self.document.get("metadata", {}) or {}
        raw_chapters = self.document.get("chapters", []) or []
        self.toc_rendered = False
        self.chapters = self._prepare_chapters(raw_chapters)
        self.chapter_anchor_map = {
            chapter.get("chapterId"): chapter.get("anchor")
            for chapter in self.chapters
            if chapter.get("chapterId") and chapter.get("anchor")
        }
        self.heading_label_map = self._compute_heading_labels(self.chapters)
        self.toc_entries = self._collect_toc_entries(self.chapters)

        metadata = self.metadata
        theme_tokens = metadata.get("themeTokens") or self.document.get("themeTokens", {})
        title = metadata.get("title") or metadata.get("query") or "æºè½èææ¥å"
        hero_kpis = (metadata.get("hero") or {}).get("kpis")
        self.hero_kpi_signature = self._kpi_signature_from_items(hero_kpis)

        head = self._render_head(title, theme_tokens)
        body = self._render_body()

        # è¾åºå¾è¡¨éªè¯ç»è®¡
        self._log_chart_validation_stats()

        return f"<!DOCTYPE html>\n<html lang=\"zh-CN\" class=\"no-js\">\n{head}\n{body}\n</html>"

    # ====== å¤´é¨ / æ­£æ ======

    def _resolve_color_value(self, value: Any, fallback: str) -> str:
        """ä»é¢è²tokenä¸­æåå­ç¬¦ä¸²ï¿½?""
        if isinstance(value, str):
            value = value.strip()
            return value or fallback
        if isinstance(value, dict):
            for key in ("main", "value", "color", "base", "default"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            for candidate in value.values():
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return fallback

    def _resolve_color_family(self, value: Any, fallback: Dict[str, str]) -> Dict[str, str]:
        """è§£æï¿½?ï¿½?æä¸è²ï¼ç¼ºå¤±æ¶åè½å°é»è®¤ï¿½?""
        result = {
            "main": fallback.get("main", "#007bff"),
            "light": fallback.get("light", fallback.get("main", "#007bff")),
            "dark": fallback.get("dark", fallback.get("main", "#007bff")),
        }
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                result["main"] = stripped
            return result
        if isinstance(value, dict):
            result["main"] = self._resolve_color_value(value.get("main") or value, result["main"])
            result["light"] = self._resolve_color_value(value.get("light") or value.get("lighter"), result["light"])
            result["dark"] = self._resolve_color_value(value.get("dark") or value.get("darker"), result["dark"])
        return result

    def _render_head(self, title: str, theme_tokens: Dict[str, Any]) -> str:
        """
        æ¸²æ<head>é¨åï¼å è½½ä¸»é¢CSSä¸å¿è¦çèæ¬ä¾èµï¿½?

        åæ°:
            title: é¡µé¢titleæ ç­¾åå®¹ï¿½?
            theme_tokens: ä¸»é¢åéï¼ç¨äºæ³¨å¥CSSãæ¯æå±çº§ï¼
              - colors: {primary/secondary/bg/text/card/border/...}
              - typography: {fontFamily, fonts:{body,heading}}ï¼body/heading ä¸ºç©ºæ¶åè½å°ç³»ç»å­ä½
              - spacing: {container,gutter/pagePadding}

        è¿å:
            str: headçæ®µHTMLï¿½?
        """
        css = self._build_css(theme_tokens)

        # å è½½ç¬¬ä¸æ¹åº
        chartjs = self._load_lib("chart.js")
        chartjs_sankey = self._load_lib("chartjs-chart-sankey.js")
        html2canvas = self._load_lib("html2canvas.min.js")
        jspdf = self._load_lib("jspdf.umd.min.js")
        mathjax = self._load_lib("mathjax.js")
        wordcloud2 = self._load_lib("wordcloud2.min.js")

        # çæåµå¥å¼scriptæ ç­¾ï¼å¹¶ä¸ºæ¯ä¸ªåºæ·»å CDN fallbackæºå¶
        # ECharts - ä¸»è¦å¾è¡¨ï¿½?(æ¿æ¢åæï¿½?Chart.js)
        echarts_tag = self._build_script_with_fallback(
            inline_code="", # ææ¶ä¸åèå·¨å¤§æä»¶ï¼ç´æ¥ç¨CDN
            cdn_url="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js",
            check_expression="typeof echarts !== 'undefined'",
            lib_name="ECharts"
        )

        # wordcloud2 - è¯äºæ¸²æ
        wordcloud_tag = self._build_script_with_fallback(
            inline_code=wordcloud2,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/wordcloud2.js/1.2.2/wordcloud2.min.js",
            check_expression="typeof WordCloud !== 'undefined'",
            lib_name="wordcloud2"
        )

        # html2canvas - ç¨äºæªå¾
        html2canvas_tag = self._build_script_with_fallback(
            inline_code=html2canvas,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js",
            check_expression="typeof html2canvas !== 'undefined'",
            lib_name="html2canvas"
        )

        # jsPDF - ç¨äºPDFå¯¼åº
        jspdf_tag = self._build_script_with_fallback(
            inline_code=jspdf,
            cdn_url="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js",
            check_expression="typeof jspdf !== 'undefined'",
            lib_name="jsPDF"
        )

        # MathJax - æ°å­¦å¬å¼æ¸²æ
        mathjax_tag = self._build_script_with_fallback(
            inline_code=mathjax,
            cdn_url="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
            check_expression="typeof MathJax !== 'undefined'",
            lib_name="MathJax",
            is_defer=True
        )

        # PDFå­ä½æ°æ®ä¸ååµå¥HTMLï¼åå°æä»¶ä½ï¿½?
        pdf_font_script = ""

        return f"""
<head>
  <meta charset="utf-8" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{self._escape_html(title)}</title>
  {echarts_tag}
  {wordcloud_tag}
  {html2canvas_tag}
  {jspdf_tag}
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$','$$'], ['\\\\[','\\\\]']]
      }},
      options: {{
        skipHtmlTags: ['script','noscript','style','textarea','pre','code'],
        processEscapes: true
      }}
    }};
  </script>
  {mathjax_tag}
  {pdf_font_script}
  <style>
{css}
  </style>
  <script>
    document.documentElement.classList.remove('no-js');
    document.documentElement.classList.add('js-ready');
  </script>
</head>""".strip()

    def _render_body(self) -> str:
        """
        æ¼è£<body>ç»æï¼åå«å¤´é¨ãå¯¼èªãç« èåèæ¬ï¿½?
        æ°çæ¬ï¼ç§»é¤ç¬ç«çcover sectionï¼æ é¢åå¹¶å°hero sectionä¸­ï¿½?

        è¿å:
            str: bodyçæ®µHTMLï¿½?
        """
        header = self._render_header()
        # cover = self._render_cover()  # ä¸ååç¬æ¸²æcover
        hero = self._render_hero()
        toc_section = self._render_toc_section()
        chapters = "".join(self._render_chapter(chapter) for chapter in self.chapters)
        widget_scripts = "\n".join(self.widget_scripts)
        hydration = self._hydration_script()
        overlay = """
<div id="export-overlay" class="export-overlay no-print" aria-hidden="true">
  <div class="export-dialog" role="status" aria-live="assertive">
    <div class="export-spinner" aria-hidden="true"></div>
    <p class="export-status">æ­£å¨å¯¼åºPDFï¼è¯·ç¨ï¿½?..</p>
    <div class="export-progress" role="progressbar" aria-valuetext="æ­£å¨å¯¼åº">
      <div class="export-progress-bar"></div>
    </div>
  </div>
</div>
""".strip()

        warning_banner = """
<div class="ai-warning-banner no-print" style="background-color: #fff3cd; color: #856404; padding: 12px 20px; border-left: 4px solid #ffeeba; margin: 20px auto; max-width: 1200px; border-radius: 4px; font-size: 14px; display: flex; align-items: center; gap: 10px;">
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
  <div>
    <strong>åè´£å£°æï¿½?/strong> æ¬æ¥åç±AIåºäºå®æ¶ç½ç»æç´¢çæï¼åéäºç½ç»ç¯å¢ãåç¬ç­ç¥åLLMåºæç"å¹»è§"ç°è±¡ï¼é¨åæ°æ®ãäºå®æè§ç¹å¯è½å­å¨åå·®æèæãè¯·å¡å¿ç»å<a href="#citations" style="color: #856404; text-decoration: underline;">ææ«ä¿¡æ¯æºå¼ï¿½?/a>è¿è¡äº¤åéªè¯ï¼åå¿å°æ­¤ä½ä¸ºå¯ä¸çå³ç­ä¾æ®ï¿½?
  </div>
</div>
"""

        return f"""
<body>
{header}
{warning_banner}
{overlay}
<main>
{hero}
{toc_section}
{chapters}
</main>
{widget_scripts}
{hydration}
</body>""".strip()

    # ====== é¡µç / åä¿¡ï¿½?/ ç®å½ ======

    def _render_header(self) -> str:
        """
        æ¸²æå¸é¡¶å¤´é¨ï¼åå«æ é¢ãå¯æ é¢ä¸åè½æé®ï¿½?

        æé®/æ§ä»¶è¯´æï¼ID ç¨äº _hydration_script éç»å®äºä»¶ï¼ï¿½?
        - ç§»é¤äºåæç"åæ¢æ¨¡å¼"å"æå°é¡µé¢"æé®ï¿½?

        è¿å:
            str: header HTMLï¿½?
        """
        metadata = self.metadata
        title = metadata.get("title") or "æºè½èæåææ¥å"
        subtitle = metadata.get("subtitle") or metadata.get("templateName") or "èªå¨çæ"
        return f"""
<header class="report-header no-print">
  <div>
    <h1>{self._escape_html(title)}</h1>
    <p class="subtitle">{self._escape_html(subtitle)}</p>
    {self._render_tagline()}
  </div>
  <div class="header-actions">
    <button id="export-btn" class="action-btn" type="button" style="display: none;">â¬ï¸ å¯¼åºPDF</button>
  </div>
</header>
""".strip()

    def _render_tagline(self) -> str:
        """
        æ¸²ææ é¢ä¸æ¹çæ è¯­ï¼å¦æ æ è¯­åè¿åç©ºå­ç¬¦ä¸²ï¿½?

        è¿å:
            str: tagline HTMLæç©ºä¸²ï¿½?
        """
        tagline = self.metadata.get("tagline")
        if not tagline:
            return ""
        return f'<p class="tagline">{self._escape_html(tagline)}</p>'

    def _render_cover(self) -> str:
        """
        æç« å¼å¤´çå°é¢åºï¼å±ä¸­å±ç¤ºæ é¢ä¸"æç« æ»è§"æç¤ºï¿½?

        è¿å:
            str: cover section HTMLï¿½?
        """
        title = self.metadata.get("title") or "æºè½èææ¥å"
        subtitle = self.metadata.get("subtitle") or self.metadata.get("templateName") or ""
        overview_hint = "æç« æ»è§"
        return f"""
<section class="cover">
  <p class="cover-hint">{overview_hint}</p>
  <h1>{self._escape_html(title)}</h1>
  <p class="cover-subtitle">{self._escape_html(subtitle)}</p>
</section>
""".strip()

    def _render_hero(self) -> str:
        """
        æ ¹æ®layoutä¸­çheroå­æ®µè¾åºæè¦/KPI/äº®ç¹åºï¿½?
        æ°çæ¬ï¼å°æ é¢åæ»è§åå¹¶å¨ä¸èµ·ï¼å»ææ¤­åèæ¯ï¿½?

        è¿å:
            str: heroåºHTMLï¼è¥æ æ°æ®åä¸ºç©ºå­ç¬¦ä¸²ï¿½?
        """
        hero = self.metadata.get("hero") or {}
        if not hero:
            return ""

        # è·åæ é¢åå¯æ é¢
        title = self.metadata.get("title") or "æºè½èææ¥å"
        subtitle = self.metadata.get("subtitle") or self.metadata.get("templateName") or ""

        summary = hero.get("summary")
        summary_html = f'<p class="hero-summary">{self._escape_html(summary)}</p>' if summary else ""
        highlights = hero.get("highlights") or []
        highlight_html = "".join(
            f'<li><span class="badge">{self._escape_html(text)}</span></li>'
            for text in highlights
        )
        actions = hero.get("actions") or []
        actions_html = "".join(
            f'<button class="ghost-btn" type="button">{self._escape_html(text)}</button>'
            for text in actions
        )
        kpi_cards = ""
        for item in hero.get("kpis", []):
            delta = item.get("delta")
            tone = item.get("tone") or "neutral"
            delta_html = f'<span class="delta {tone}">{self._escape_html(delta)}</span>' if delta else ""
            kpi_cards += f"""
            <div class="hero-kpi">
                <div class="label">{self._escape_html(item.get("label"))}</div>
                <div class="value">{self._escape_html(item.get("value"))}</div>
                {delta_html}
            </div>
            """
            
        hero_side_html = f"""
    <div class="hero-side">
      {kpi_cards}
    </div>
        """ if kpi_cards else ""

        return f"""
<section class="hero-section-combined">
  <div class="hero-header">
    <p class="hero-hint">æç« æ»è§</p>
    <h1 class="hero-title">{self._escape_html(title)}</h1>
    <p class="hero-subtitle">{self._escape_html(subtitle)}</p>
  </div>
  <div class="hero-body">
    <div class="hero-content">
      {summary_html}
      <ul class="hero-highlights">{highlight_html}</ul>
      <div class="hero-actions">{actions_html}</div>
    </div>{hero_side_html}
  </div>
</section>
""".strip()

    def _render_meta_panel(self) -> str:
        """å½åéæ±ä¸å±ç¤ºåä¿¡æ¯ï¼ä¿çæ¹æ³ä¾¿äºåç»­æ©å±"""
        return ""

    def _render_toc_section(self) -> str:
        """
        çæç®å½æ¨¡åï¼å¦æ ç®å½æ°æ®åè¿åç©ºå­ç¬¦ä¸²ï¿½?

        è¿å:
            str: toc HTMLç»æï¿½?
        """
        if not self.toc_entries:
            return ""
        if self.toc_rendered:
            return ""
        toc_config = self.metadata.get("toc") or {}
        toc_title = toc_config.get("title") or "ð ç®å½"
        toc_items = "".join(
            self._format_toc_entry(entry)
            for entry in self.toc_entries
        )
        self.toc_rendered = True
        return f"""
<nav class="toc">
  <div class="toc-title">{self._escape_html(toc_title)}</div>
  <ul>
    {toc_items}
  </ul>
</nav>
""".strip()

    def _render_citation_list(self, block: Dict[str, Any]) -> str:
        """æ¸²æææ«å¼ç¨ä¿¡æ¯æºåï¿½?""
        # ç±äºæä»¬æ æ³ç´æ¥ï¿½?_render_citation_list éè·åå° task_idï¼æï¿½?seed_idï¼ï¼
        # åªè½æ¸²æä¸ä¸ªéç¨åç«¯ JS å½æ°çè°ç¨ãå¨ HTML æä»¶å¨å±å ä¸ script æ¯æï¿½?
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
            
            # å¦æ URL å­å¨ä¸å·²è§è¿ï¼è·³ï¿½?
            if url and url in seen_urls:
                continue
            # å¦æ URL ä¸ºç©ºï¿½?title å·²è§è¿ï¼è·³è¿
            if not url and title and title in seen_titles:
                continue
                
            if url:
                seen_urls.add(url)
            if title:
                seen_titles.add(title)
                
            # éæ°åéåºå·
            item["index"] = len(unique_items) + 1
            unique_items.append(item)

        lines = [
            '<div class="citation-list" style="margin-top: 3rem; border-top: 1px solid var(--border-color); padding-top: 1.5rem;">',
            '<h3 id="citations" style="margin-bottom: 1rem; color: var(--text-secondary); font-size: 1.25rem;">åèèµï¿½?/ å¼ç¨æ¥æº</h3>',
            '<ol style="padding-left: 1.5rem; font-size: 0.9em; color: var(--text-secondary); line-height: 1.6;">'
        ]

        for item in unique_items:
            index = item.get("index", "")
            title = self._escape_html(item.get("title", ""))
            url = self._escape_html(item.get("url", ""))
            source = self._escape_html(item.get("source", ""))
            pub_date = self._escape_html(item.get("publishedAt", ""))

            source_text = f" - <span style='color: var(--text-muted);'>{source}</span>" if source else ""
            date_text = f" <span style='color: var(--text-muted);'>({pub_date})</span>" if pub_date else ""

            lines.append(f'<li id="citation-{index}" style="margin-bottom: 0.5rem; word-break: break-all;">')
            if url:
                if url.startswith("seed://"):
                    # ç´æ¥çææååç«¯çå¨çº¿é¢è§é¾æ¥ï¼å¨æ°æ ç­¾é¡µæå¼
                    seed_id = url.split("seed://")[1].split("/")[0] if "seed://" in url else ""
                    display_url = f"/api/report/seed/{seed_id}"
                    lines.append(f'<a href="{display_url}" target="_blank" style="color: var(--primary-color); text-decoration: underline; cursor: pointer;">{title}</a> <span style="font-size: 0.85em; color: var(--text-muted);">[å¨çº¿é¢è§éä»¶]</span>')
                elif url.startswith("file:///"):
                    # å¼å®¹æ§çæ¬å°éä»¶ URLï¼æç¤ºæ æ³é¢ï¿½?
                    lines.append(f'<span style="color: var(--text-muted); text-decoration: line-through;">{title}</span> <span style="font-size: 0.85em; color: var(--text-muted);">[æ¬å°éä»¶æ æ³ç´æ¥é¢è§]</span>')
                else:
                    lines.append(f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color: var(--primary-color); text-decoration: none;">{title}</a>')
            else:
                lines.append(f'<span>{title}</span>')
            lines.append(f'{source_text}{date_text}')
            lines.append('</li>')

        lines.append('</ol>')
        lines.append('</div>')
        return "\n".join(lines)

    def _collect_toc_entries(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        æ ¹æ®metadataä¸­çtocPlanæç« èheadingæ¶éç®å½é¡¹ï¿½?

        åæ°:
            chapters: Document IRä¸­çç« èæ°ç»ï¿½?

        è¿å:
            list[dict]: è§èååçç®å½æ¡ç®ï¼åå«level/text/anchor/descriptionï¿½?
        """
        metadata = self.metadata
        toc_config = metadata.get("toc") or {}
        custom_entries = toc_config.get("customEntries")
        entries: List[Dict[str, Any]] = []

        if custom_entries:
            for entry in custom_entries:
                anchor = entry.get("anchor") or self.chapter_anchor_map.get(entry.get("chapterId"))

                # éªè¯anchoræ¯å¦ææ
                if not anchor:
                    logger.warning(
                        f"ç®å½ï¿½?'{entry.get('display') or entry.get('title')}' "
                        f"ç¼ºå°ææçanchorï¼å·²è·³è¿"
                    )
                    continue

                # éªè¯anchoræ¯å¦å¨chapter_anchor_mapä¸­æå¨chaptersçblocksï¿½?
                anchor_valid = self._validate_toc_anchor(anchor, chapters)
                if not anchor_valid:
                    logger.warning(
                        f"ç®å½ï¿½?'{entry.get('display') or entry.get('title')}' "
                        f"çanchor '{anchor}' å¨ææ¡£ä¸­æªæ¾å°å¯¹åºçç« è"
                    )

                # æ¸çæè¿°ææ¬
                description = entry.get("description")
                if description:
                    description = self._clean_text_from_json_artifacts(description)

                entries.append(
                    {
                        "level": entry.get("level", 2),
                        "text": entry.get("display") or entry.get("title") or "",
                        "anchor": anchor,
                        "description": description,
                    }
                )
            return entries

        for chapter in chapters or []:
            for block in chapter.get("blocks", []):
                if block.get("type") == "heading":
                    anchor = block.get("anchor") or chapter.get("anchor") or ""
                    if not anchor:
                        continue
                    mapped = self.heading_label_map.get(anchor, {})
                    # æ¸çæè¿°ææ¬
                    description = mapped.get("description")
                    if description:
                        description = self._clean_text_from_json_artifacts(description)
                    entries.append(
                        {
                            "level": block.get("level", 2),
                            "text": mapped.get("display") or block.get("text", ""),
                            "anchor": anchor,
                            "description": description,
                        }
                    )
        return entries

    def _validate_toc_anchor(self, anchor: str, chapters: List[Dict[str, Any]]) -> bool:
        """
        éªè¯ç®å½anchoræ¯å¦å¨ææ¡£ä¸­å­å¨å¯¹åºçç« èæheadingï¿½?

        åæ°:
            anchor: éè¦éªè¯çanchor
            chapters: Document IRä¸­çç« èæ°ç»

        è¿å:
            bool: anchoræ¯å¦ææ
        """
        # æ£æ¥æ¯å¦æ¯ç« èanchor
        if anchor in self.chapter_anchor_map.values():
            return True

        # æ£æ¥æ¯å¦å¨heading_label_mapï¿½?
        if anchor in self.heading_label_map:
            return True

        # æ£æ¥ç« èçblocksä¸­æ¯å¦æè¿ä¸ªanchor
        for chapter in chapters or []:
            chapter_anchor = chapter.get("anchor")
            if chapter_anchor == anchor:
                return True

            for block in chapter.get("blocks", []):
                block_anchor = block.get("anchor")
                if block_anchor == anchor:
                    return True

        return False

    def _prepare_chapters(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """å¤å¶ç« èå¹¶å±å¼å¶ä¸­åºååçblockï¼é¿åæ¸²æç¼ºï¿½?""
        prepared: List[Dict[str, Any]] = []
        for chapter in chapters or []:
            chapter_copy = copy.deepcopy(chapter)
            chapter_copy["blocks"] = self._expand_blocks_in_place(chapter_copy.get("blocks", []))
            prepared.append(chapter_copy)
        return prepared

    def _expand_blocks_in_place(self, blocks: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
        """éåblockåè¡¨ï¼å°ååµJSONä¸²æè§£ä¸ºç¬ç«block"""
        expanded: List[Dict[str, Any]] = []
        for block in blocks or []:
            extras = self._extract_embedded_blocks(block)
            expanded.append(block)
            if extras:
                expanded.extend(self._expand_blocks_in_place(extras))
        return expanded

    def _extract_embedded_blocks(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        å¨blockåé¨æ¥æ¾è¢«è¯¯åæå­ç¬¦ä¸²çblockåè¡¨ï¼å¹¶è¿åè¡¥åçblock
        """
        extracted: List[Dict[str, Any]] = []

        def traverse(node: Any) -> None:
            """éå½éåblockæ ï¼è¯å«textå­æ®µåæ½å¨çåµå¥block JSON"""
            if isinstance(node, dict):
                for key, value in list(node.items()):
                    if key == "text" and isinstance(value, str):
                        decoded = self._decode_embedded_block_payload(value)
                        if decoded:
                            node[key] = ""
                            extracted.extend(decoded)
                        continue
                    traverse(value)
            elif isinstance(node, list):
                for item in node:
                    traverse(item)

        traverse(block)
        return extracted

    def _decode_embedded_block_payload(self, raw: str) -> List[Dict[str, Any]] | None:
        """
        å°å­ç¬¦ä¸²å½¢å¼çblockæè¿°æ¢å¤ä¸ºç»æååè¡¨ï¿½?
        """
        if not isinstance(raw, str):
            return None
        stripped = raw.strip()
        if not stripped or stripped[0] not in "{[":
            return None
        payload: Any | None = None
        decode_targets = [stripped]
        if stripped and stripped[0] != "[":
            decode_targets.append(f"[{stripped}]")
        for candidate in decode_targets:
            try:
                payload = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if payload is None:
            for candidate in decode_targets:
                try:
                    payload = ast.literal_eval(candidate)
                    break
                except (ValueError, SyntaxError):
                    continue
        if payload is None:
            return None

        blocks = self._collect_blocks_from_payload(payload)
        return blocks or None

    @staticmethod
    def _looks_like_block(payload: Dict[str, Any]) -> bool:
        """ç²ç¥å¤æ­dictæ¯å¦ç¬¦åblockç»æ"""
        if not isinstance(payload, dict):
            return False
        block_type = payload.get("type")
        if block_type and isinstance(block_type, str):
            # æé¤åèç±»åï¼inlineRun ç­ï¼ï¼å®ä»¬ä¸æ¯åçº§åï¿½?
            inline_types = {"inlineRun", "inline", "text"}
            if block_type in inline_types:
                return False
            return True
        structural_keys = {"blocks", "rows", "items", "widgetId", "widgetType", "data"}
        return any(key in payload for key in structural_keys)

    def _collect_blocks_from_payload(self, payload: Any) -> List[Dict[str, Any]]:
        """éå½æ¶épayloadä¸­çblockèç¹"""
        collected: List[Dict[str, Any]] = []
        if isinstance(payload, dict):
            block_list = payload.get("blocks")
            block_type = payload.get("type")
            
            # æé¤åèç±»åï¼å®ä»¬ä¸æ¯åçº§åï¿½?
            inline_types = {"inlineRun", "inline", "text"}
            if block_type in inline_types:
                return collected
            
            if isinstance(block_list, list) and not block_type:
                for candidate in block_list:
                    collected.extend(self._collect_blocks_from_payload(candidate))
                return collected
            if payload.get("cells") and not block_type:
                for cell in payload["cells"]:
                    if isinstance(cell, dict):
                        collected.extend(self._collect_blocks_from_payload(cell.get("blocks")))
                return collected
            if payload.get("items") and not block_type:
                for item in payload["items"]:
                    collected.extend(self._collect_blocks_from_payload(item))
                return collected
            appended = False
            if block_type or payload.get("widgetId") or payload.get("rows"):
                coerced = self._coerce_block_dict(payload)
                if coerced:
                    collected.append(coerced)
                    appended = True
            items = payload.get("items")
            if isinstance(items, list) and not block_type:
                for item in items:
                    collected.extend(self._collect_blocks_from_payload(item))
                return collected
            if appended:
                return collected
        elif isinstance(payload, list):
            for item in payload:
                collected.extend(self._collect_blocks_from_payload(item))
        elif payload is None:
            return collected
        return collected

    def _coerce_block_dict(self, payload: Any) -> Dict[str, Any] | None:
        """å°è¯å°dictè¡¥åä¸ºåæ³blockç»æ"""
        if not isinstance(payload, dict):
            return None
        block = copy.deepcopy(payload)
        block_type = block.get("type")
        if not block_type:
            if "widgetId" in block:
                block_type = block["type"] = "widget"
            elif "rows" in block or "cells" in block:
                block_type = block["type"] = "table"
                if "rows" not in block and isinstance(block.get("cells"), list):
                    block["rows"] = [{"cells": block.pop("cells")}]
            elif "items" in block:
                block_type = block["type"] = "list"
        return block if block.get("type") else None

    def _format_toc_entry(self, entry: Dict[str, Any]) -> str:
        """
        å°åä¸ªç®å½é¡¹è½¬ä¸ºå¸¦æè¿°çHTMLè¡ï¿½?

        åæ°:
            entry: ç®å½æ¡ç®ï¼éåå« `text` ï¿½?`anchor`ï¿½?

        è¿å:
            str: `<li>` å½¢å¼çHTMLï¿½?
        """
        desc = entry.get("description")
        # æ¸çæè¿°ææ¬ä¸­çJSONçæ®µ
        if desc:
            desc = self._clean_text_from_json_artifacts(desc)
        desc_html = f'<p class="toc-desc">{self._escape_html(desc)}</p>' if desc else ""
        level = entry.get("level", 2)
        css_level = 1 if level <= 2 else min(level, 4)
        return f'<li class="level-{css_level}"><a href="#{self._escape_attr(entry["anchor"])}">{self._escape_html(entry["text"])}</a>{desc_html}</li>'

    def _compute_heading_labels(self, chapters: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        é¢è®¡ç®åçº§æ é¢çç¼å·ï¼ç« ï¼ä¸ãäºï¼èï¿½?.1ï¼å°èï¼1.1.1ï¼ï¿½?

        åæ°:
            chapters: Document IRä¸­çç« èæ°ç»ï¿½?

        è¿å:
            dict: éç¹å°ç¼ï¿½?æè¿°çæ å°ï¼æ¹ä¾¿TOCä¸æ­£æå¼ç¨ï¿½?
        """
        label_map: Dict[str, Dict[str, Any]] = {}

        for chap_idx, chapter in enumerate(chapters or [], start=1):
            chapter_heading_seen = False
            section_idx = 0
            subsection_idx = 0
            deep_counters: Dict[int, int] = {}

            for block in chapter.get("blocks", []):
                if block.get("type") != "heading":
                    continue
                level = block.get("level", 2)
                
                # ä¸ºé¿åå¤ä¸ªheadingä½¿ç¨ç¸åçanchorå¯¼è´IDå²çªæè¦çï¼
                # ä¼åä½¿ç¨èªèº«anchorï¼è¥æ æéå¤åéæ°çï¿½?
                original_anchor = block.get("anchor") or chapter.get("anchor")
                anchor = original_anchor
                counter = 1
                while not anchor or anchor in label_map:
                    anchor = f"{original_anchor}-{counter}"
                    counter += 1
                    
                block["anchor"] = anchor

                raw_text = block.get("text", "")
                clean_title = self._strip_order_prefix(raw_text)
                label = None
                display_text = raw_text

                if not chapter_heading_seen:
                    label = f"{self._to_chinese_numeral(chap_idx)}ï¿½?
                    display_text = f"{label} {clean_title}".strip()
                    chapter_heading_seen = True
                    section_idx = 0
                    subsection_idx = 0
                    deep_counters.clear()
                elif level <= 2:
                    section_idx += 1
                    subsection_idx = 0
                    deep_counters.clear()
                    label = f"{chap_idx}.{section_idx}"
                    display_text = f"{label} {clean_title}".strip()
                else:
                    if section_idx == 0:
                        section_idx = 1
                    if level == 3:
                        subsection_idx += 1
                        deep_counters.clear()
                        label = f"{chap_idx}.{section_idx}.{subsection_idx}"
                    else:
                        deep_counters[level] = deep_counters.get(level, 0) + 1
                        parts = [str(chap_idx), str(section_idx or 1), str(subsection_idx or 1)]
                        for lvl in sorted(deep_counters.keys()):
                            parts.append(str(deep_counters[lvl]))
                        label = ".".join(parts)
                    display_text = f"{label} {clean_title}".strip()

                # ç´æ¥åå¥ blockï¼é¿ååªä¾èµ map é æï¿½?anchor è¢«è¦ï¿½?
                block["display_text"] = display_text
                
                label_map[anchor] = {
                    "level": level,
                    "display": display_text,
                    "label": label,
                    "title": clean_title,
                }
        return label_map

    @staticmethod
    def _strip_order_prefix(text: str) -> str:
        """ç§»é¤å½¢å¦ï¿½?.0 "æ"ä¸çåç¼ï¼å¾å°çº¯æ é¢"""
        if not text:
            return ""
        separators = [" ", "ï¿½?, ".", "ï¿½?]
        stripped = text.lstrip()
        for sep in separators:
            parts = stripped.split(sep, 1)
            if len(parts) == 2 and parts[0]:
                return parts[1].strip()
        return stripped.strip()

    @staticmethod
    def _to_chinese_numeral(number: int) -> str:
        """ï¿½?/2/3æ å°ä¸ºä¸­æåºå·ï¼ååï¿½?""
        numerals = ["ï¿½?, "ä¸", "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?, "ï¿½?]
        if number <= 10:
            return numerals[number]
        tens, ones = divmod(number, 10)
        if number < 20:
            return "ï¿½? + (numerals[ones] if ones else "")
        words = ""
        if tens > 0:
            words += numerals[tens] + "ï¿½?
        if ones:
            words += numerals[ones]
        return words

    # ====== ç« èä¸åçº§æ¸²ï¿½?======

    def _render_chapter(self, chapter: Dict[str, Any]) -> str:
        """
        å°ç« èblocksåè£¹ï¿½?section>ï¼ä¾¿äºCSSæ§å¶ï¿½?

        åæ°:
            chapter: åä¸ªç« èJSONï¿½?

        è¿å:
            str: sectionåè£¹çHTMLï¿½?
        """
        section_id = self._escape_attr(chapter.get("anchor") or f"chapter-{chapter.get('chapterId', 'x')}")
        prev_chapter = self._current_chapter
        self._current_chapter = chapter
        try:
            blocks_html = self._render_blocks(chapter.get("blocks", []))
        finally:
            self._current_chapter = prev_chapter
        return f'<section id="{section_id}" class="chapter">\n{blocks_html}\n</section>'

    def _render_blocks(self, blocks: List[Dict[str, Any]]) -> str:
        """
        é¡ºåºæ¸²æç« èåææblockï¿½?

        åæ°:
            blocks: ç« èåé¨çblockæ°ç»ï¿½?

        è¿å:
            str: æ¼æ¥åçHTMLï¿½?
        """
        return "".join(self._render_block(block) for block in blocks or [])

    def _render_block(self, block: Dict[str, Any]) -> str:
        """
        æ ¹æ®block.typeåæ´¾å°ä¸åçæ¸²æå½æ°ï¿½?

        åæ°:
            block: åä¸ªblockå¯¹è±¡ï¿½?

        è¿å:
            str: æ¸²æåçHTMLï¼æªç¥ç±»åä¼è¾åºJSONè°è¯ä¿¡æ¯ï¿½?
        """
        block_type = block.get("type")
        handlers = {
            "heading": self._render_heading,
            "paragraph": self._render_paragraph,
            "list": self._render_list,
            "table": self._render_table,
            "swotTable": self._render_swot_table,
            "pestTable": self._render_pest_table,
            "blockquote": self._render_blockquote,
            "engineQuote": self._render_engine_quote,
            "hr": lambda b: "<hr />",
            "code": self._render_code,
            "math": self._render_math,
            "figure": self._render_figure,
            "callout": self._render_callout,
            "kpiGrid": self._render_kpi_grid,
            "widget": self._render_widget,
            "toc": lambda b: self._render_toc_section(),
            "citationList": self._render_citation_list,
        }
        handler = handlers.get(block_type)
        if handler:
            html_fragment = handler(block)
            return self._wrap_error_block(html_fragment, block)
        # å¼å®¹æ§æ ¼å¼ï¼ç¼ºå°typeä½åå«inlinesæ¶æparagraphå¤ç
        if isinstance(block, dict) and block.get("inlines"):
            html_fragment = self._render_paragraph({"inlines": block.get("inlines")})
            return self._wrap_error_block(html_fragment, block)
        # å¼å®¹ç´æ¥ä¼ å¥å­ç¬¦ä¸²çåºæ¯
        if isinstance(block, str):
            html_fragment = self._render_paragraph({"inlines": [{"text": block}]})
            return self._wrap_error_block(html_fragment, {"meta": {}, "type": "paragraph"})
        if isinstance(block.get("blocks"), list):
            html_fragment = self._render_blocks(block["blocks"])
            return self._wrap_error_block(html_fragment, block)
        fallback = f'<pre class="unknown-block">{self._escape_html(json.dumps(block, ensure_ascii=False, indent=2))}</pre>'
        return self._wrap_error_block(fallback, block)

    def _wrap_error_block(self, html_fragment: str, block: Dict[str, Any]) -> str:
        """è¥blockæ è®°äºerroråæ°æ®ï¼ååè£¹æç¤ºå®¹å¨å¹¶æ³¨å¥tooltipï¿½?""
        if not html_fragment:
            return html_fragment
        meta = block.get("meta") or {}
        log_ref = meta.get("errorLogRef")
        if not isinstance(log_ref, dict):
            return html_fragment
        raw_preview = (meta.get("rawJsonPreview") or "")[:1200]
        error_message = meta.get("errorMessage") or "LLMè¿ååè§£æéï¿½?
        importance = meta.get("importance") or "standard"
        ref_label = ""
        if log_ref.get("relativeFile") and log_ref.get("entryId"):
            ref_label = f"{log_ref['relativeFile']}#{log_ref['entryId']}"
        tooltip = f"{error_message} | {ref_label}".strip()
        attr_raw = self._escape_attr(raw_preview or tooltip)
        attr_title = self._escape_attr(tooltip)
        class_suffix = self._escape_attr(importance)
        return (
            f'<div class="llm-error-block importance-{class_suffix}" '
            f'data-raw="{attr_raw}" title="{attr_title}">{html_fragment}</div>'
        )

    def _render_heading(self, block: Dict[str, Any]) -> str:
        """æ¸²æheading blockï¼ç¡®ä¿éç¹å­ï¿½?""
        original_level = max(1, min(6, block.get("level", 2)))
        if original_level <= 2:
            level = 2
        elif original_level == 3:
            level = 3
        else:
            level = min(original_level, 6)
        anchor = block.get("anchor")
        if anchor:
            anchor_attr = self._escape_attr(anchor)
        else:
            self.heading_counter += 1
            anchor = f"heading-{self.heading_counter}"
            anchor_attr = self._escape_attr(anchor)
        mapping = self.heading_label_map.get(anchor, {})
        display_text = mapping.get("display") or block.get("text", "")
        subtitle = block.get("subtitle")
        subtitle_html = f'<small>{self._escape_html(subtitle)}</small>' if subtitle else ""
        return f'<h{level} id="{anchor_attr}">{self._escape_html(display_text)}{subtitle_html}</h{level}>'

    def _render_paragraph(self, block: Dict[str, Any]) -> str:
        """æ¸²ææ®µè½ï¼åé¨éè¿inline runä¿ææ··ææ ·å¼"""
        inlines_data = block.get("inlines", [])
        
        # æ£æµå¹¶è·³è¿åå«ææ¡£åæ°ï¿½?JSON çæ®µï¿½?
        if self._is_metadata_paragraph(inlines_data):
            return ""
        
        # ä»åå«åä¸ªdisplayå¬å¼æ¶ç´æ¥æ¸²æä¸ºåï¼é¿å<p>ååµ<div>
        if len(inlines_data) == 1:
            standalone = self._render_standalone_math_inline(inlines_data[0])
            if standalone:
                return standalone

        inlines = "".join(self._render_inline(run) for run in inlines_data)
        return f"<p>{inlines}</p>"

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

    def _render_standalone_math_inline(self, run: Dict[str, Any] | str) -> str | None:
        """å½æ®µè½åªåå«åä¸ªdisplayå¬å¼æ¶ï¼è½¬ä¸ºmath-blocké¿åç ´åè¡åå¸å±"""
        if isinstance(run, dict):
            text_value, marks = self._normalize_inline_payload(run)
            if marks:
                return None
            math_id_hint = run.get("mathIds") or run.get("mathId")
        else:
            text_value = "" if run is None else str(run)
            math_id_hint = None
            marks = []

        rendered = self._render_text_with_inline_math(
            text_value,
            math_id_hint,
            allow_display_block=True
        )
        if rendered and rendered.strip().startswith('<div class="math-block"'):
            return rendered
        return None

    def _render_list(self, block: Dict[str, Any]) -> str:
        """æ¸²ææåº/æ åº/ä»»å¡åè¡¨"""
        list_type = block.get("listType", "bullet")
        tag = "ol" if list_type == "ordered" else "ul"
        extra_class = "task-list" if list_type == "task" else ""
        items_html = ""
        for item in block.get("items", []):
            content = self._render_blocks(item)
            if not content.strip():
                continue
            items_html += f"<li>{content}</li>"
        class_attr = f' class="{extra_class}"' if extra_class else ""
        return f'<{tag}{class_attr}>{items_html}</{tag}>'

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
        if not rows:
            return []

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

        def _is_heading_like_cell(cell: Dict[str, Any]) -> bool:
            """æ£æµæ¯å¦çä¼¼è¢«éè¯¯å¹¶å¥è¡¨æ ¼çç« ï¿½?æ é¢ååï¿½?""
            text = _get_cell_text(cell)
            if not text:
                return False
            stripped = text.strip()
            # ç« èå·æ"ç¬¬Xï¿½?é¨å"å¸¸è§æ ¼å¼ï¼é¿åè¯¯å æ­£å¸¸æ°å­ï¿½?
            heading_patterns = (
                r"^\d{1,2}(?:\.\d{1,2}){1,3}\s+",
                r"^ç¬¬[ä¸äºä¸åäºå­ä¸å«ä¹å]+[ç« èé¨å]",
            )
            return any(re.match(pat, stripped) for pat in heading_patterns)

        # ç¬¬ä¸é¶æ®µï¼å¤ï¿½?æè¡¨å¤´è¡ + æ°æ®è¢«ä¸²å¨ä¸ï¿½?çæï¿½?
        header_cells = self._flatten_nested_cells((rows[0] or {}).get("cells", []))
        header_count = len(header_cells)
        overflow_fixed = None
        if header_count >= 2:
            rebuilt_rows: List[Dict[str, Any]] = [
                {
                    **{k: v for k, v in (rows[0] or {}).items() if k != "cells"},
                    "cells": header_cells,
                }
            ]
            changed = False
            for row in rows[1:]:
                cells = self._flatten_nested_cells((row or {}).get("cells", []))
                cell_count = len(cells)
                if cell_count <= header_count:
                    rebuilt_rows.append({**{k: v for k, v in (row or {}).items() if k != "cells"}, "cells": cells})
                    continue

                remainder = cell_count % header_count
                trimmed_cells = cells
                if remainder:
                    trailing = cells[-remainder:]
                    if all(_is_placeholder_cell(c) or _is_heading_like_cell(c) for c in trailing):
                        trimmed_cells = cells[:-remainder]
                        remainder = 0

                if remainder == 0 and len(trimmed_cells) >= header_count * 2:
                    for i in range(0, len(trimmed_cells), header_count):
                        chunk = trimmed_cells[i : i + header_count]
                        rebuilt_rows.append({"cells": chunk})
                    changed = True
                else:
                    rebuilt_rows.append({**{k: v for k, v in (row or {}).items() if k != "cells"}, "cells": cells})

            if changed:
                overflow_fixed = rebuilt_rows

        if overflow_fixed is not None:
            rows = overflow_fixed

        if len(rows) != 1:
            # åªæä¸è¡çå¼å¸¸æåµç±åç»­é»è¾å¤çï¼æ­£å¸¸å¤è¡ç´æ¥è¿ï¿½?
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
        """
        æ¸²æè¡¨æ ¼ï¼åæ¶ä¿çcaptionä¸ååæ ¼å±æ§ï¿½?

        åæ°:
            block: tableç±»åçblockï¿½?

        è¿å:
            str: åå«<table>ç»æçHTMLï¿½?
        """
        # åä¿®å¤å¯è½å­å¨çåµå¥è¡ç»æé®ï¿½?
        raw_rows = block.get("rows") or []
        fixed_rows = self._fix_nested_table_rows(raw_rows)
        rows = self._normalize_table_rows(fixed_rows)
        rows_html = ""
        for row in rows:
            row_cells = ""
            # å±å¹³å¯è½å­å¨çåµå¥ååæ ¼ç»æï¼ä½ä¸ºé¢å¤ä¿æ¤ï¼
            cells = self._flatten_nested_cells(row.get("cells", []))
            for cell in cells:
                cell_tag = "th" if cell.get("header") or cell.get("isHeader") else "td"
                attr = []
                if cell.get("rowspan"):
                    attr.append(f'rowspan="{int(cell["rowspan"])}"')
                if cell.get("colspan"):
                    attr.append(f'colspan="{int(cell["colspan"])}"')
                if cell.get("align"):
                    attr.append(f'class="align-{cell["align"]}"')
                attr_str = (" " + " ".join(attr)) if attr else ""
                content = self._render_blocks(cell.get("blocks", []))
                row_cells += f"<{cell_tag}{attr_str}>{content}</{cell_tag}>"
            rows_html += f"<tr>{row_cells}</tr>"
        caption = block.get("caption")
        caption_html = f"<caption>{self._escape_html(caption)}</caption>" if caption else ""
        return f'<div class="table-wrap"><table>{caption_html}<tbody>{rows_html}</tbody></table></div>'

    def _render_swot_table(self, block: Dict[str, Any]) -> str:
        """
        æ¸²æåè±¡éçSWOTåæï¼åæ¶çæä¸¤ç§å¸å±ï¿½?
        1. å¡çå¸å±ï¼ç¨äºHTMLç½é¡µæ¾ç¤ºï¿½? åè§ç©å½¢åè±¡ï¿½?
        2. è¡¨æ ¼å¸å±ï¼ç¨äºPDFå¯¼åºï¿½? ç»æåè¡¨æ ¼ï¼æ¯æåé¡µ
        
        PDFåé¡µç­ç¥ï¿½?
        - ä½¿ç¨è¡¨æ ¼å½¢å¼ï¼æ¯ä¸ªS/W/O/Tè±¡éä¸ºç¬ç«è¡¨æ ¼åºï¿½?
        - åè®¸å¨ä¸åè±¡éä¹é´åï¿½?
        - æ¯ä¸ªè±¡éåçæ¡ç®å°½éä¿æå¨ä¸ï¿½?
        """
        title = block.get("title") or "SWOT åæ"
        summary = block.get("summary")
        
        # ========== å¡çå¸å±ï¼HTMLç¨ï¼==========
        card_html = self._render_swot_card_layout(block, title, summary)
        
        # ========== è¡¨æ ¼å¸å±ï¼PDFç¨ï¼==========
        table_html = self._render_swot_pdf_table_layout(block, title, summary)
        
        # è¿ååå«ä¸¤ç§å¸å±çå®¹ï¿½?
        return f"""
        <div class="swot-container">
          {card_html}
          {table_html}
        </div>
        """
    
    def _render_swot_card_layout(self, block: Dict[str, Any], title: str, summary: str | None) -> str:
        """æ¸²æSWOTå¡çå¸å±ï¼ç¨äºHTMLç½é¡µæ¾ç¤ºï¿½?""
        quadrants = [
            ("strengths", "ä¼å¿ Strengths", "S", "strength"),
            ("weaknesses", "å£å¿ Weaknesses", "W", "weakness"),
            ("opportunities", "æºä¼ Opportunities", "O", "opportunity"),
            ("threats", "å¨è Threats", "T", "threat"),
        ]
        cells_html = ""
        for idx, (key, label, code, css) in enumerate(quadrants):
            items = self._normalize_swot_items(block.get(key))
            caption_text = f"{len(items)} æ¡è¦ï¿½? if items else "å¾è¡¥ï¿½?
            list_html = "".join(self._render_swot_item(item) for item in items) if items else '<li class="swot-empty">å°æªå¡«å¥è¦ç¹</li>'
            first_cell_class = " swot-cell--first" if idx == 0 else ""
            cells_html += f"""
        <div class="swot-cell swot-cell--pageable {css}{first_cell_class}" data-swot-key="{key}">
          <div class="swot-cell__meta">
            <span class="swot-pill {css}">{self._escape_html(code)}</span>
            <div>
              <div class="swot-cell__title">{self._escape_html(label)}</div>
              <div class="swot-cell__caption">{self._escape_html(caption_text)}</div>
            </div>
          </div>
          <ul class="swot-list">{list_html}</ul>
        </div>"""
        summary_html = f'<p class="swot-card__summary">{self._escape_html(summary)}</p>' if summary else ""
        title_html = f'<div class="swot-card__title">{self._escape_html(title)}</div>' if title else ""
        legend = """
            <div class="swot-legend">
              <span class="swot-legend__item strength">S ä¼å¿</span>
              <span class="swot-legend__item weakness">W å£å¿</span>
              <span class="swot-legend__item opportunity">O æºä¼</span>
              <span class="swot-legend__item threat">T å¨è</span>
            </div>
        """
        return f"""
        <div class="swot-card swot-card--html">
          <div class="swot-card__head">
            <div>{title_html}{summary_html}</div>
            {legend}
          </div>
          <div class="swot-grid">{cells_html}</div>
        </div>
        """
    
    def _render_swot_pdf_table_layout(self, block: Dict[str, Any], title: str, summary: str | None) -> str:
        """
        æ¸²æSWOTè¡¨æ ¼å¸å±ï¼ç¨äºPDFå¯¼åºï¿½?
        
        è®¾è®¡è¯´æï¿½?
        - æ´ä½ä¸ºä¸ä¸ªå¤§è¡¨æ ¼ï¼åå«æ é¢è¡ï¿½?ä¸ªè±¡éåºï¿½?
        - æ¯ä¸ªè±¡éåºåæèªå·±çå­æ é¢è¡ååå®¹è¡
        - ä½¿ç¨åå¹¶ååæ ¼æ¥æ¾ç¤ºè±¡éæ é¢
        - éè¿CSSæ§å¶åé¡µè¡ä¸º
        """
        quadrants = [
            ("strengths", "S", "ä¼å¿ Strengths", "swot-pdf-strength", "#1c7f6e"),
            ("weaknesses", "W", "å£å¿ Weaknesses", "swot-pdf-weakness", "#c0392b"),
            ("opportunities", "O", "æºä¼ Opportunities", "swot-pdf-opportunity", "#1f5ab3"),
            ("threats", "T", "å¨è Threats", "swot-pdf-threat", "#b36b16"),
        ]
        
        # æ é¢åæï¿½?
        summary_row = ""
        if summary:
            summary_row = f"""
            <tr class="swot-pdf-summary-row">
              <td colspan="4" class="swot-pdf-summary">{self._escape_html(summary)}</td>
            </tr>"""
        
        # çæåä¸ªè±¡éçè¡¨æ ¼åï¿½?
        quadrant_tables = ""
        for idx, (key, code, label, css_class, color) in enumerate(quadrants):
            items = self._normalize_swot_items(block.get(key))
            
            # çææ¯ä¸ªè±¡éçåå®¹è¡
            items_rows = ""
            if items:
                for item_idx, item in enumerate(items):
                    item_title = item.get("title") or item.get("label") or item.get("text") or "æªå½åè¦ï¿½?
                    item_detail = item.get("detail") or item.get("description") or ""
                    item_evidence = item.get("evidence") or item.get("source") or ""
                    item_impact = item.get("impact") or item.get("priority") or ""
                    # item_score = item.get("score")  # è¯ååè½å·²ç¦ï¿½?
                    
                    # æå»ºè¯¦æåå®¹
                    detail_parts = []
                    if item_detail:
                        detail_parts.append(item_detail)
                    if item_evidence:
                        detail_parts.append(f"ä½è¯ï¼{item_evidence}")
                    detail_text = "<br/>".join(detail_parts) if detail_parts else "-"
                    
                    # æå»ºæ ç­¾
                    tags = []
                    if item_impact:
                        tags.append(f'<span class="swot-pdf-tag">{self._escape_html(item_impact)}</span>')
                    # if item_score not in (None, ""):  # è¯ååè½å·²ç¦ï¿½?
                    #     tags.append(f'<span class="swot-pdf-tag swot-pdf-tag--score">è¯å {self._escape_html(item_score)}</span>')
                    tags_html = " ".join(tags)
                    
                    # ç¬¬ä¸è¡éè¦åå¹¶è±¡éæ é¢ååæ ¼
                    if item_idx == 0:
                        rowspan = len(items)
                        items_rows += f"""
            <tr class="swot-pdf-item-row {css_class}">
              <td rowspan="{rowspan}" class="swot-pdf-quadrant-label {css_class}">
                <span class="swot-pdf-code">{code}</span>
                <span class="swot-pdf-label-text">{self._escape_html(label.split()[0])}</span>
              </td>
              <td class="swot-pdf-item-num">{item_idx + 1}</td>
              <td class="swot-pdf-item-title">{self._escape_html(item_title)}</td>
              <td class="swot-pdf-item-detail">{detail_text}</td>
              <td class="swot-pdf-item-tags">{tags_html}</td>
            </tr>"""
                    else:
                        items_rows += f"""
            <tr class="swot-pdf-item-row {css_class}">
              <td class="swot-pdf-item-num">{item_idx + 1}</td>
              <td class="swot-pdf-item-title">{self._escape_html(item_title)}</td>
              <td class="swot-pdf-item-detail">{detail_text}</td>
              <td class="swot-pdf-item-tags">{tags_html}</td>
            </tr>"""
            else:
                # æ²¡æåå®¹æ¶æ¾ç¤ºå ï¿½?
                items_rows = f"""
            <tr class="swot-pdf-item-row {css_class}">
              <td class="swot-pdf-quadrant-label {css_class}">
                <span class="swot-pdf-code">{code}</span>
                <span class="swot-pdf-label-text">{self._escape_html(label.split()[0])}</span>
              </td>
              <td class="swot-pdf-item-num">-</td>
              <td colspan="3" class="swot-pdf-empty">ææ è¦ç¹</td>
            </tr>"""
            
            # æ¯ä¸ªè±¡éä½ä¸ºä¸ä¸ªç¬ç«çtbodyï¼ä¾¿äºåé¡µæ§ï¿½?
            quadrant_tables += f"""
          <tbody class="swot-pdf-quadrant {css_class}">
            {items_rows}
          </tbody>"""
        
        return f"""
        <div class="swot-pdf-wrapper">
          <table class="swot-pdf-table">
            <caption class="swot-pdf-caption">{self._escape_html(title)}</caption>
            <thead class="swot-pdf-thead">
              <tr>
                <th class="swot-pdf-th-quadrant">è±¡é</th>
                <th class="swot-pdf-th-num">åºå·</th>
                <th class="swot-pdf-th-title">è¦ç¹</th>
                <th class="swot-pdf-th-detail">è¯¦ç»è¯´æ</th>
                <th class="swot-pdf-th-tags">å½±å</th>
              </tr>
              {summary_row}
            </thead>
            {quadrant_tables}
          </table>
        </div>
        """

    def _normalize_swot_items(self, raw: Any) -> List[Dict[str, Any]]:
        """å°SWOTæ¡ç®è§æ´ä¸ºç»ä¸ç»æï¼å¼å®¹å­ç¬¦ä¸²/å¯¹è±¡ä¸¤ç§åæ³"""
        normalized: List[Dict[str, Any]] = []
        if raw is None:
            return normalized
        if isinstance(raw, (str, int, float)):
            text = self._safe_text(raw).strip()
            if text:
                normalized.append({"title": text})
            return normalized
        if not isinstance(raw, list):
            return normalized
        for entry in raw:
            if isinstance(entry, (str, int, float)):
                text = self._safe_text(entry).strip()
                if text:
                    normalized.append({"title": text})
                continue
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("label") or entry.get("text")
            detail = entry.get("detail") or entry.get("description")
            evidence = entry.get("evidence") or entry.get("source")
            impact = entry.get("impact") or entry.get("priority")
            # score = entry.get("score")  # è¯ååè½å·²ç¦ï¿½?
            if not title and isinstance(detail, str):
                title = detail
                detail = None
            if not (title or detail or evidence):
                continue
            normalized.append(
                {
                    "title": title,
                    "detail": detail,
                    "evidence": evidence,
                    "impact": impact,
                    # "score": score,  # è¯ååè½å·²ç¦ï¿½?
                }
            )
        return normalized

    def _render_swot_item(self, item: Dict[str, Any]) -> str:
        """è¾åºåä¸ªSWOTæ¡ç®çHTMLçæ®µ"""
        title = item.get("title") or item.get("label") or item.get("text") or "æªå½åè¦ï¿½?
        detail = item.get("detail") or item.get("description")
        evidence = item.get("evidence") or item.get("source")
        impact = item.get("impact") or item.get("priority")
        # score = item.get("score")  # è¯ååè½å·²ç¦ï¿½?
        tags: List[str] = []
        if impact:
            tags.append(f'<span class="swot-tag">{self._escape_html(impact)}</span>')
        # if score not in (None, ""):  # è¯ååè½å·²ç¦ï¿½?
        #     tags.append(f'<span class="swot-tag neutral">è¯å {self._escape_html(score)}</span>')
        tags_html = f'<span class="swot-item-tags">{"".join(tags)}</span>' if tags else ""
        detail_html = f'<div class="swot-item-desc">{self._escape_html(detail)}</div>' if detail else ""
        evidence_html = f'<div class="swot-item-evidence">ä½è¯ï¼{self._escape_html(evidence)}</div>' if evidence else ""
        return f"""
            <li class="swot-item">
              <div class="swot-item-title">{self._escape_html(title)}{tags_html}</div>
              {detail_html}{evidence_html}
            </li>
        """

    # ==================== PEST åæï¿½?====================
    
    def _render_pest_table(self, block: Dict[str, Any]) -> str:
        """
        æ¸²æåç»´åº¦çPESTåæï¼åæ¶çæä¸¤ç§å¸å±ï¿½?
        1. å¡çå¸å±ï¼ç¨äºHTMLç½é¡µæ¾ç¤ºï¿½? æ¨ªåæ¡ç¶å å 
        2. è¡¨æ ¼å¸å±ï¼ç¨äºPDFå¯¼åºï¿½? ç»æåè¡¨æ ¼ï¼æ¯æåé¡µ
        
        PESTåæç»´åº¦ï¿½?
        - P: Politicalï¼æ¿æ²»å ç´ ï¼
        - E: Economicï¼ç»æµå ç´ ï¼
        - S: Socialï¼ç¤¾ä¼å ç´ ï¼
        - T: Technologicalï¼ææ¯å ç´ ï¼
        """
        title = block.get("title") or "PEST åæ"
        summary = block.get("summary")
        
        # ========== å¡çå¸å±ï¼HTMLç¨ï¼==========
        card_html = self._render_pest_card_layout(block, title, summary)
        
        # ========== è¡¨æ ¼å¸å±ï¼PDFç¨ï¼==========
        table_html = self._render_pest_pdf_table_layout(block, title, summary)
        
        # è¿ååå«ä¸¤ç§å¸å±çå®¹ï¿½?
        return f"""
        <div class="pest-container">
          {card_html}
          {table_html}
        </div>
        """
    
    def _render_pest_card_layout(self, block: Dict[str, Any], title: str, summary: str | None) -> str:
        """æ¸²æPESTå¡çå¸å±ï¼ç¨äºHTMLç½é¡µæ¾ç¤ºï¿½? æ¨ªåæ¡ç¶å å è®¾è®¡"""
        dimensions = [
            ("political", "æ¿æ²»å ç´  Political", "P", "political"),
            ("economic", "ç»æµå ç´  Economic", "E", "economic"),
            ("social", "ç¤¾ä¼å ç´  Social", "S", "social"),
            ("technological", "ææ¯å ï¿½?Technological", "T", "technological"),
        ]
        strips_html = ""
        for idx, (key, label, code, css) in enumerate(dimensions):
            items = self._normalize_pest_items(block.get(key))
            caption_text = f"{len(items)} æ¡è¦ï¿½? if items else "å¾è¡¥ï¿½?
            list_html = "".join(self._render_pest_item(item) for item in items) if items else '<li class="pest-empty">å°æªå¡«å¥è¦ç¹</li>'
            first_strip_class = " pest-strip--first" if idx == 0 else ""
            strips_html += f"""
        <div class="pest-strip pest-strip--pageable {css}{first_strip_class}" data-pest-key="{key}">
          <div class="pest-strip__indicator {css}">
            <span class="pest-code">{self._escape_html(code)}</span>
          </div>
          <div class="pest-strip__content">
            <div class="pest-strip__header">
              <div class="pest-strip__title">{self._escape_html(label)}</div>
              <div class="pest-strip__caption">{self._escape_html(caption_text)}</div>
            </div>
            <ul class="pest-list">{list_html}</ul>
          </div>
        </div>"""
        summary_html = f'<p class="pest-card__summary">{self._escape_html(summary)}</p>' if summary else ""
        title_html = f'<div class="pest-card__title">{self._escape_html(title)}</div>' if title else ""
        legend = """
            <div class="pest-legend">
              <span class="pest-legend__item political">P æ¿æ²»</span>
              <span class="pest-legend__item economic">E ç»æµ</span>
              <span class="pest-legend__item social">S ç¤¾ä¼</span>
              <span class="pest-legend__item technological">T æï¿½?/span>
            </div>
        """
        return f"""
        <div class="pest-card pest-card--html">
          <div class="pest-card__head">
            <div>{title_html}{summary_html}</div>
            {legend}
          </div>
          <div class="pest-strips">{strips_html}</div>
        </div>
        """
    
    def _render_pest_pdf_table_layout(self, block: Dict[str, Any], title: str, summary: str | None) -> str:
        """
        æ¸²æPESTè¡¨æ ¼å¸å±ï¼ç¨äºPDFå¯¼åºï¿½?
        
        è®¾è®¡è¯´æï¿½?
        - æ´ä½ä¸ºä¸ä¸ªå¤§è¡¨æ ¼ï¼åå«æ é¢è¡ï¿½?ä¸ªç»´åº¦åºï¿½?
        - æ¯ä¸ªç»´åº¦æèªå·±çå­æ é¢è¡ååå®¹è¡
        - ä½¿ç¨åå¹¶ååæ ¼æ¥æ¾ç¤ºç»´åº¦æ é¢
        - éè¿CSSæ§å¶åé¡µè¡ä¸º
        """
        dimensions = [
            ("political", "P", "æ¿æ²»å ç´  Political", "pest-pdf-political", "#8e44ad"),
            ("economic", "E", "ç»æµå ç´  Economic", "pest-pdf-economic", "#16a085"),
            ("social", "S", "ç¤¾ä¼å ç´  Social", "pest-pdf-social", "#e84393"),
            ("technological", "T", "ææ¯å ï¿½?Technological", "pest-pdf-technological", "#2980b9"),
        ]
        
        # æ é¢åæï¿½?
        summary_row = ""
        if summary:
            summary_row = f"""
            <tr class="pest-pdf-summary-row">
              <td colspan="4" class="pest-pdf-summary">{self._escape_html(summary)}</td>
            </tr>"""
        
        # çæåä¸ªç»´åº¦çè¡¨æ ¼åï¿½?
        dimension_tables = ""
        for idx, (key, code, label, css_class, color) in enumerate(dimensions):
            items = self._normalize_pest_items(block.get(key))
            
            # çææ¯ä¸ªç»´åº¦çåå®¹è¡
            items_rows = ""
            if items:
                for item_idx, item in enumerate(items):
                    item_title = item.get("title") or item.get("label") or item.get("text") or "æªå½åè¦ï¿½?
                    item_detail = item.get("detail") or item.get("description") or ""
                    item_source = item.get("source") or item.get("evidence") or ""
                    item_trend = item.get("trend") or item.get("impact") or ""
                    
                    # æå»ºè¯¦æåå®¹
                    detail_parts = []
                    if item_detail:
                        detail_parts.append(item_detail)
                    if item_source:
                        detail_parts.append(f"æ¥æºï¼{item_source}")
                    detail_text = "<br/>".join(detail_parts) if detail_parts else "-"
                    
                    # æå»ºæ ç­¾
                    tags = []
                    if item_trend:
                        tags.append(f'<span class="pest-pdf-tag">{self._escape_html(item_trend)}</span>')
                    tags_html = " ".join(tags)
                    
                    # ç¬¬ä¸è¡éè¦åå¹¶ç»´åº¦æ é¢ååæ ¼
                    if item_idx == 0:
                        rowspan = len(items)
                        items_rows += f"""
            <tr class="pest-pdf-item-row {css_class}">
              <td rowspan="{rowspan}" class="pest-pdf-dimension-label {css_class}">
                <span class="pest-pdf-code">{code}</span>
                <span class="pest-pdf-label-text">{self._escape_html(label.split()[0])}</span>
              </td>
              <td class="pest-pdf-item-num">{item_idx + 1}</td>
              <td class="pest-pdf-item-title">{self._escape_html(item_title)}</td>
              <td class="pest-pdf-item-detail">{detail_text}</td>
              <td class="pest-pdf-item-tags">{tags_html}</td>
            </tr>"""
                    else:
                        items_rows += f"""
            <tr class="pest-pdf-item-row {css_class}">
              <td class="pest-pdf-item-num">{item_idx + 1}</td>
              <td class="pest-pdf-item-title">{self._escape_html(item_title)}</td>
              <td class="pest-pdf-item-detail">{detail_text}</td>
              <td class="pest-pdf-item-tags">{tags_html}</td>
            </tr>"""
            else:
                # æ²¡æåå®¹æ¶æ¾ç¤ºå ï¿½?
                items_rows = f"""
            <tr class="pest-pdf-item-row {css_class}">
              <td class="pest-pdf-dimension-label {css_class}">
                <span class="pest-pdf-code">{code}</span>
                <span class="pest-pdf-label-text">{self._escape_html(label.split()[0])}</span>
              </td>
              <td class="pest-pdf-item-num">-</td>
              <td colspan="3" class="pest-pdf-empty">ææ è¦ç¹</td>
            </tr>"""
            
            # æ¯ä¸ªç»´åº¦ä½ä¸ºä¸ä¸ªç¬ç«çtbodyï¼ä¾¿äºåé¡µæ§ï¿½?
            dimension_tables += f"""
          <tbody class="pest-pdf-dimension {css_class}">
            {items_rows}
          </tbody>"""
        
        return f"""
        <div class="pest-pdf-wrapper">
          <table class="pest-pdf-table">
            <caption class="pest-pdf-caption">{self._escape_html(title)}</caption>
            <thead class="pest-pdf-thead">
              <tr>
                <th class="pest-pdf-th-dimension">ç»´åº¦</th>
                <th class="pest-pdf-th-num">åºå·</th>
                <th class="pest-pdf-th-title">è¦ç¹</th>
                <th class="pest-pdf-th-detail">è¯¦ç»è¯´æ</th>
                <th class="pest-pdf-th-tags">è¶å¿/å½±å</th>
              </tr>
              {summary_row}
            </thead>
            {dimension_tables}
          </table>
        </div>
        """

    def _normalize_pest_items(self, raw: Any) -> List[Dict[str, Any]]:
        """å°PESTæ¡ç®è§æ´ä¸ºç»ä¸ç»æï¼å¼å®¹å­ç¬¦ä¸²/å¯¹è±¡ä¸¤ç§åæ³"""
        normalized: List[Dict[str, Any]] = []
        if raw is None:
            return normalized
        if isinstance(raw, (str, int, float)):
            text = self._safe_text(raw).strip()
            if text:
                normalized.append({"title": text})
            return normalized
        if not isinstance(raw, list):
            return normalized
        for entry in raw:
            if isinstance(entry, (str, int, float)):
                text = self._safe_text(entry).strip()
                if text:
                    normalized.append({"title": text})
                continue
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("label") or entry.get("text")
            detail = entry.get("detail") or entry.get("description")
            source = entry.get("source") or entry.get("evidence")
            trend = entry.get("trend") or entry.get("impact")
            if not title and isinstance(detail, str):
                title = detail
                detail = None
            if not (title or detail or source):
                continue
            normalized.append(
                {
                    "title": title,
                    "detail": detail,
                    "source": source,
                    "trend": trend,
                }
            )
        return normalized

    def _render_pest_item(self, item: Dict[str, Any]) -> str:
        """è¾åºåä¸ªPESTæ¡ç®çHTMLçæ®µ"""
        title = item.get("title") or item.get("label") or item.get("text") or "æªå½åè¦ï¿½?
        detail = item.get("detail") or item.get("description")
        source = item.get("source") or item.get("evidence")
        trend = item.get("trend") or item.get("impact")
        tags: List[str] = []
        if trend:
            tags.append(f'<span class="pest-tag">{self._escape_html(trend)}</span>')
        tags_html = f'<span class="pest-item-tags">{"".join(tags)}</span>' if tags else ""
        detail_html = f'<div class="pest-item-desc">{self._escape_html(detail)}</div>' if detail else ""
        source_html = f'<div class="pest-item-source">æ¥æºï¼{self._escape_html(source)}</div>' if source else ""
        return f"""
            <li class="pest-item">
              <div class="pest-item-title">{self._escape_html(title)}{tags_html}</div>
              {detail_html}{source_html}
            </li>
        """

    def _normalize_table_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        æ£æµå¹¶ä¿®æ­£ä»æååçç«æè¡¨ï¼è½¬æ¢ä¸ºæ åç½æ ¼ï¿½?

        åæ°:
            rows: åå§è¡¨æ ¼è¡ï¿½?

        è¿å:
            list[dict]: è¥æ£æµå°ç«æè¡¨åè¿åè½¬ç½®åçè¡ï¼å¦ååæ ·è¿åï¿½?
        """
        if not rows:
            return []
        if not all(len((row.get("cells") or [])) == 1 for row in rows):
            return rows
        texts = [self._extract_row_text(row) for row in rows]
        header_span = self._detect_transposed_header_span(rows, texts)
        if not header_span:
            return rows
        normalized = self._transpose_single_cell_table(rows, header_span)
        return normalized or rows

    def _detect_transposed_header_span(self, rows: List[Dict[str, Any]], texts: List[str]) -> int:
        """æ¨æ­ç«æè¡¨å¤´çè¡æ°ï¼ç¨äºåç»­è½¬ç½®"""
        max_fields = min(8, len(rows) // 2)
        header_span = 0
        for idx, text in enumerate(texts):
            if idx >= max_fields:
                break
            if self._is_potential_table_header(text):
                header_span += 1
            else:
                break
        if header_span < 2:
            return 0
        remainder = texts[header_span:]
        if not remainder or (len(rows) - header_span) % header_span != 0:
            return 0
        if not any(self._looks_like_table_value(txt) for txt in remainder):
            return 0
        return header_span

    def _is_potential_table_header(self, text: str) -> bool:
        """æ ¹æ®é¿åº¦ä¸å­ç¬¦ç¹å¾å¤æ­æ¯å¦åè¡¨å¤´å­æ®µ"""
        if not text:
            return False
        stripped = text.strip()
        if not stripped or len(stripped) > 12:
            return False
        return not any(ch.isdigit() or ch in self.TABLE_COMPLEX_CHARS for ch in stripped)

    def _looks_like_table_value(self, text: str) -> bool:
        """å¤æ­è¯¥ææ¬æ¯å¦æ´åæ°æ®å¼ï¼ç¨äºè¾å©å¤æ­è½¬ç½®"""
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) >= 12:
            return True
        return any(ch.isdigit() or ch in self.TABLE_COMPLEX_CHARS for ch in stripped)

    def _transpose_single_cell_table(self, rows: List[Dict[str, Any]], span: int) -> List[Dict[str, Any]]:
        """å°ååå¤è¡çè¡¨æ ¼è½¬æ¢ä¸ºæ åè¡¨ï¿½?+ è¥å¹²æ°æ®ï¿½?""
        total = len(rows)
        if total <= span or (total - span) % span != 0:
            return []
        header_rows = rows[:span]
        data_rows = rows[span:]
        normalized: List[Dict[str, Any]] = []
        header_cells = []
        for row in header_rows:
            cell = copy.deepcopy((row.get("cells") or [{}])[0])
            cell["header"] = True
            header_cells.append(cell)
        normalized.append({"cells": header_cells})
        for start in range(0, len(data_rows), span):
            group = data_rows[start : start + span]
            if len(group) < span:
                break
            normalized.append(
                {
                    "cells": [
                        copy.deepcopy((item.get("cells") or [{}])[0])
                        for item in group
                    ]
                }
            )
        return normalized

    def _extract_row_text(self, row: Dict[str, Any]) -> str:
        """æåè¡¨æ ¼è¡ä¸­ççº¯ææ¬ï¼æ¹ä¾¿å¯åå¼åæ"""
        cells = row.get("cells") or []
        if not cells:
            return ""
        cell = cells[0]
        texts: List[str] = []
        for block in cell.get("blocks", []):
            if isinstance(block, dict):
                if block.get("type") == "paragraph":
                    for inline in block.get("inlines") or []:
                        if isinstance(inline, dict):
                            value = inline.get("text")
                        else:
                            value = inline
                        if value is None:
                            continue
                        texts.append(str(value))
        return "".join(texts)

    def _render_blockquote(self, block: Dict[str, Any]) -> str:
        """æ¸²æå¼ç¨åï¼å¯åµå¥å¶ä»block"""
        inner = self._render_blocks(block.get("blocks", []))
        return f"<blockquote>{inner}</blockquote>"

    def _render_engine_quote(self, block: Dict[str, Any]) -> str:
        """æ¸²æåEngineåè¨åï¼å¸¦ç¬ç«éè²ä¸æ é¢"""
        engine_raw = (block.get("engine") or "").lower()
        engine = engine_raw if engine_raw in ENGINE_AGENT_TITLES else "insight"
        expected_title = ENGINE_AGENT_TITLES.get(engine, ENGINE_AGENT_TITLES["insight"])
        title_raw = block.get("title") if isinstance(block.get("title"), str) else ""
        title = title_raw if title_raw == expected_title else expected_title
        inner = self._render_blocks(block.get("blocks", []))
        return (
            f'<div class="engine-quote engine-{self._escape_attr(engine)}">'
            f'  <div class="engine-quote__header">'
            f'    <span class="engine-quote__dot"></span>'
            f'    <span class="engine-quote__title">{self._escape_html(title)}</span>'
            f'  </div>'
            f'  <div class="engine-quote__body">{inner}</div>'
            f'</div>'
        )

    def _render_code(self, block: Dict[str, Any]) -> str:
        """æ¸²æä»£ç åï¼éå¸¦è¯­è¨ä¿¡æ¯"""
        lang = block.get("lang") or ""
        content = self._escape_html(block.get("content", ""))
        return f'<pre class="code-block" data-lang="{self._escape_attr(lang)}"><code>{content}</code></pre>'

    def _render_math(self, block: Dict[str, Any]) -> str:
        """æ¸²ææ°å­¦å¬å¼ï¼å ä½ç¬¦äº¤ç»å¤é¨MathJaxæåå¤ç"""
        latex_raw = block.get("latex", "")
        latex = self._escape_html(self._normalize_latex_string(latex_raw))
        math_id = self._escape_attr(block.get("mathId", "")) if block.get("mathId") else ""
        id_attr = f' data-math-id="{math_id}"' if math_id else ""
        return f'<div class="math-block"{id_attr}>$$ {latex} $$</div>'

    def _render_figure(self, block: Dict[str, Any]) -> str:
        """æ ¹æ®æ°è§èé»è®¤ä¸æ¸²æå¤é¨å¾çï¼æ¹ä¸ºåå¥½æï¿½?""
        caption = block.get("caption") or "å¾ååå®¹å·²çç¥ï¼ä»åè®¸HTMLåçå¾è¡¨ä¸è¡¨æ ¼ï¼"
        return f'<div class="figure-placeholder">{self._escape_html(caption)}</div>'

    def _render_callout(self, block: Dict[str, Any]) -> str:
        """
        æ¸²æé«äº®æç¤ºçï¼toneå³å®é¢è²ï¿½?

        åæ°:
            block: calloutç±»åçblockï¿½?

        è¿å:
            str: callout HTMLï¼è¥åé¨åå«ä¸åè®¸çåä¼è¢«æåï¿½?
        """
        tone = block.get("tone", "info")
        title = block.get("title")
        safe_blocks, trailing_blocks = self._split_callout_content(block.get("blocks"))
        inner = self._render_blocks(safe_blocks)
        title_html = f"<strong>{self._escape_html(title)}</strong>" if title else ""
        callout_html = f'<div class="callout tone-{tone}">{title_html}{inner}</div>'
        trailing_html = self._render_blocks(trailing_blocks) if trailing_blocks else ""
        return callout_html + trailing_html

    def _split_callout_content(
        self, blocks: List[Dict[str, Any]] | None
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """éå®calloutåé¨ä»åå«è½»éåå®¹ï¼å¶ä½åå¥ç¦»å°å¤å±"""
        if not blocks:
            return [], []
        safe: List[Dict[str, Any]] = []
        trailing: List[Dict[str, Any]] = []
        for idx, child in enumerate(blocks):
            child_type = child.get("type")
            if child_type == "list":
                sanitized, overflow = self._sanitize_callout_list(child)
                if sanitized:
                    safe.append(sanitized)
                if overflow:
                    trailing.extend(overflow)
                    trailing.extend(copy.deepcopy(blocks[idx + 1 :]))
                    break
            elif child_type in self.CALLOUT_ALLOWED_TYPES:
                safe.append(child)
            else:
                trailing.extend(copy.deepcopy(blocks[idx:]))
                break
        else:
            return safe, []
        return safe, trailing

    def _sanitize_callout_list(
        self, block: Dict[str, Any]
    ) -> tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
        """å½åè¡¨é¡¹åå«ç»æåblockæ¶ï¼å°å¶æªæ­ç§»åºcallout"""
        items = block.get("items") or []
        if not items:
            return block, []
        sanitized_items: List[List[Dict[str, Any]]] = []
        trailing: List[Dict[str, Any]] = []
        for idx, item in enumerate(items):
            safe, overflow = self._split_callout_content(item)
            if safe:
                sanitized_items.append(safe)
            if overflow:
                trailing.extend(overflow)
                for rest in items[idx + 1 :]:
                    trailing.extend(copy.deepcopy(rest))
                break
        if not sanitized_items:
            return None, trailing
        new_block = copy.deepcopy(block)
        new_block["items"] = sanitized_items
        return new_block, trailing

    def _render_kpi_grid(self, block: Dict[str, Any]) -> str:
        """æ¸²æKPIå¡çæ æ ¼ï¼åå«ææ å¼ä¸æ¶¨è·ï¿½?""
        if self._should_skip_overview_kpi(block):
            return ""
        cards = ""
        items = block.get("items", [])
        for item in items:
            delta = item.get("delta")
            delta_tone = item.get("deltaTone") or "neutral"
            delta_html = f'<span class="delta {delta_tone}">{self._escape_html(delta)}</span>' if delta else ""
            cards += f"""
            <div class="kpi-card">
              <div class="kpi-value">{self._escape_html(item.get("value", ""))}<small>{self._escape_html(item.get("unit", ""))}</small></div>
              <div class="kpi-label">{self._escape_html(item.get("label", ""))}</div>
              {delta_html}
            </div>
            """
        count_attr = f' data-kpi-count="{len(items)}"' if items else ""
        return f'<div class="kpi-grid"{count_attr}>{cards}</div>'

    def _merge_dicts(
        self, base: Dict[str, Any] | None, override: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        éå½åå¹¶ä¸¤ä¸ªå­å¸ï¼overrideè¦çbaseï¼åä¸ºæ°å¯æ¬ï¼é¿åå¯ä½ç¨ï¿½?
        """
        result = copy.deepcopy(base) if isinstance(base, dict) else {}
        if not isinstance(override, dict):
            return result
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    def _looks_like_chart_dataset(self, candidate: Any) -> bool:
        """å¯åå¼å¤æ­å¯¹è±¡æ¯å¦åå«Chart.jså¸¸è§çlabels/datasetsç»æ"""
        if not isinstance(candidate, dict):
            return False
        labels = candidate.get("labels")
        datasets = candidate.get("datasets")
        return isinstance(labels, list) or isinstance(datasets, list)

    def _coerce_chart_data_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        å¼å®¹LLMè¾åºçChart.jså®æ´éç½®ï¼å«type/data/optionsï¼ï¿½?
        è¥dataä¸­åµå¥ä¸ä¸ªçæ­£çlabels/datasetsç»æï¼åæåå¹¶è¿åè¯¥ç»æï¿½?
        """
        if not isinstance(data, dict):
            return {}
        if self._looks_like_chart_dataset(data):
            return data
        for key in ("data", "chartData", "payload"):
            nested = data.get(key)
            if self._looks_like_chart_dataset(nested):
                return copy.deepcopy(nested)
        return data

    def _prepare_widget_payload(
        self, block: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        é¢å¤çwidgetæ°æ®ï¼å¼å®¹é¨åblockå°Chart.jséç½®åå¥dataå­æ®µçæåµï¿½?

        è¿å:
            tuple(props, data): å½ä¸ååçpropsä¸chartæ°æ®
        """
        props = copy.deepcopy(block.get("props") or {})
        raw_data = block.get("data")
        data_copy = copy.deepcopy(raw_data) if isinstance(raw_data, dict) else raw_data
        widget_type = block.get("widgetType") or ""
        chart_like = isinstance(widget_type, str) and widget_type.startswith("chart.js")

        if chart_like and isinstance(data_copy, dict):
            inline_options = data_copy.pop("options", None)
            inline_type = data_copy.pop("type", None)
            normalized_data = self._coerce_chart_data_structure(data_copy)
            if isinstance(inline_options, dict):
                props["options"] = self._merge_dicts(props.get("options"), inline_options)
            if isinstance(inline_type, str) and inline_type and not props.get("type"):
                props["type"] = inline_type
        elif isinstance(data_copy, dict):
            normalized_data = data_copy
        else:
            normalized_data = {}

        return props, normalized_data

    @staticmethod
    def _is_chart_data_empty(data: Dict[str, Any] | None) -> bool:
        """æ£æ¥å¾è¡¨æ°æ®æ¯å¦ä¸ºç©ºæç¼ºå°æædatasets"""
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

    def _chart_cache_key(self, block: Dict[str, Any]) -> str:
        """ä½¿ç¨ä¿®å¤å¨çç¼å­ç®æ³çæç¨³å®çkeyï¼ä¾¿äºè·¨é¶æ®µå±äº«ç»æ"""
        if hasattr(self, "chart_repairer") and block:
            try:
                return self.chart_repairer.build_cache_key(block)
            except Exception:
                pass
        return str(id(block))

    def _note_chart_failure(self, cache_key: str, reason: str) -> None:
        """è®°å½ä¿®å¤å¤±è´¥åå ï¼åç»­æ¸²æç´æ¥ä½¿ç¨å ä½æï¿½?""
        if not cache_key:
            return
        if not reason:
            reason = "LLMè¿åçå¾è¡¨ä¿¡æ¯æ ¼å¼æè¯¯ï¼æ æ³æ­£å¸¸æ¾ç¤º"
        self._chart_failure_notes[cache_key] = reason

    def _record_chart_failure_stat(self, cache_key: str | None = None) -> None:
        """ç¡®ä¿å¤±è´¥è®¡æ°åªç»è®¡ä¸ï¿½?""
        if cache_key and cache_key in self._chart_failure_recorded:
            return
        self.chart_validation_stats['failed'] += 1
        if cache_key:
            self._chart_failure_recorded.add(cache_key)

    def _apply_cached_review_stats(self, block: Dict[str, Any]) -> None:
        """
        å¨å·²å®¡æ¥è¿çå¾è¡¨ä¸éæ°ç´¯è®¡ç»è®¡ä¿¡æ¯ï¼é¿åéå¤ä¿®å¤ï¿½?

        å½æ¸²ææµç¨éç½®äºç»è®¡ä½å¾è¡¨å·²ç»å®¡æ¥è¿ï¼_chart_reviewed=Trueï¼ï¼
        ç´æ¥æ ¹æ®è®°å½çç¶æç´¯å åé¡¹è®¡æ°ï¼é²æ­¢åæ¬¡è§¦å ChartRepairerï¿½?
        """
        if not isinstance(block, dict):
            return

        status = block.get("_chart_review_status") or "valid"
        method = (block.get("_chart_review_method") or "none").lower()
        cache_key = self._chart_cache_key(block)

        self.chart_validation_stats['total'] += 1
        if status == "failed":
            self._record_chart_failure_stat(cache_key)
        elif status == "repaired":
            if method == "api":
                self.chart_validation_stats['repaired_api'] += 1
            else:
                self.chart_validation_stats['repaired_locally'] += 1
        else:
            self.chart_validation_stats['valid'] += 1

    def _format_chart_error_reason(
        self,
        validation_result: ValidationResult | None = None,
        fallback_reason: str | None = None
    ) -> str:
        """æ¼æ¥åå¥½çå¤±è´¥æï¿½?""
        base = "LLMè¿åçå¾è¡¨ä¿¡æ¯æ ¼å¼æè¯¯ï¼å·²å°è¯æ¬å°ä¸å¤æ¨¡åä¿®å¤ä½ä»æ æ³æ­£å¸¸æ¾ç¤ºï¿½?
        detail = None
        if validation_result:
            if validation_result.errors:
                detail = validation_result.errors[0]
            elif validation_result.warnings:
                detail = validation_result.warnings[0]
        if not detail and fallback_reason:
            detail = fallback_reason
        if detail:
            text = f"{base} æç¤ºï¼{detail}"
            return text[:180] + ("..." if len(text) > 180 else "")
        return base

    def _render_chart_error_placeholder(
        self,
        title: str | None,
        reason: str,
        widget_id: str | None = None
    ) -> str:
        """è¾åºå¾è¡¨å¤±è´¥æ¶çç®æ´å ä½æç¤ºï¼é¿åç ´åHTML/PDFå¸å±"""
        safe_title = self._escape_html(title or "å¾è¡¨æªè½å±ç¤º")
        safe_reason = self._escape_html(reason)
        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        return f"""
        <div class="chart-card chart-card--error"{widget_attr}>
          <div class="chart-error">
            <div class="chart-error__icon">!</div>
            <div class="chart-error__body">
              <div class="chart-error__title">{safe_title}</div>
              <p class="chart-error__desc">{safe_reason}</p>
            </div>
          </div>
        </div>
        """

    def _has_chart_failure(self, block: Dict[str, Any]) -> tuple[bool, str | None]:
        """æ£æ¥æ¯å¦å·²æä¿®å¤å¤±è´¥è®°ï¿½?""
        cache_key = self._chart_cache_key(block)
        if block.get("_chart_renderable") is False:
            return True, block.get("_chart_error_reason")
        if cache_key in self._chart_failure_notes:
            return True, self._chart_failure_notes.get(cache_key)
        return False, None

    def _normalize_chart_block(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None = None,
    ) -> None:
        """
        è¡¥å¨å¾è¡¨blockä¸­çç¼ºå¤±å­æ®µï¼å¦scalesatasetsï¼ï¼æåå®¹éæ§ï¿½?

        - å°éè¯¯æå¨blocké¡¶å±çscalesåå¹¶è¿props.optionsï¿½?
        - å½dataç¼ºå¤±ædatasetsä¸ºç©ºæ¶ï¼å°è¯ä½¿ç¨ç« èçº§çdataä½ä¸ºååºï¿½?
        """

        if not isinstance(block, dict):
            return

        if block.get("type") != "widget":
            return

        widget_type = block.get("widgetType", "")
        if not (isinstance(widget_type, str) and widget_type.startswith("chart.js")):
            return

        # ç¡®ä¿propså­å¨
        props = block.get("props")
        if not isinstance(props, dict):
            block["props"] = {}
            props = block["props"]

        # å°é¡¶å±scalesåå¹¶è¿optionsï¼é¿åéç½®ä¸¢ï¿½?
        scales = block.get("scales")
        if isinstance(scales, dict):
            options = props.get("options") if isinstance(props.get("options"), dict) else {}
            props["options"] = self._merge_dicts(options, {"scales": scales})

        # ç¡®ä¿dataå­å¨
        data = block.get("data")
        if not isinstance(data, dict):
            data = {}
            block["data"] = data

        # å¦ædatasetsä¸ºç©ºï¼å°è¯ä½¿ç¨ç« èçº§dataå¡«å
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

        # è¥ä»ç¼ºå°labelsä¸æ°æ®ç¹åå«xå¼ï¼èªå¨çæä¾¿äºfallbackååæ å»ï¿½?
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

    def _ensure_chart_reviewed(
        self,
        block: Dict[str, Any],
        chapter_context: Dict[str, Any] | None = None,
        *,
        increment_stats: bool = True
    ) -> tuple[bool, str | None]:
        """
        ç¡®ä¿å¾è¡¨å·²å®æå®¡ï¿½?ä¿®å¤ï¼å¹¶å°ç»æååå°åå§blockï¿½?

        è¿å:
            (renderable, fail_reason)
        """
        if not isinstance(block, dict):
            return True, None

        widget_type = block.get('widgetType', '')
        is_chart = isinstance(widget_type, str) and widget_type.startswith('chart.js')
        if not is_chart:
            return True, None

        is_wordcloud = 'wordcloud' in widget_type.lower() if isinstance(widget_type, str) else False
        cache_key = self._chart_cache_key(block)

        # å·²æå¤±è´¥è®°å½ææ¾å¼æ è®°ä¸ºä¸å¯æ¸²æï¼ç´æ¥å¤ç¨ç»ï¿½?
        if block.get("_chart_renderable") is False:
            if increment_stats:
                self.chart_validation_stats['total'] += 1
                self._record_chart_failure_stat(cache_key)
            reason = block.get("_chart_error_reason")
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = block.get("_chart_review_status") or "failed"
            block["_chart_review_method"] = block.get("_chart_review_method") or "none"
            if reason:
                self._note_chart_failure(cache_key, reason)
            return False, reason

        if block.get("_chart_reviewed"):
            if increment_stats:
                self._apply_cached_review_stats(block)
            failed, cached_reason = self._has_chart_failure(block)
            renderable = not failed and block.get("_chart_renderable", True) is not False
            return renderable, block.get("_chart_error_reason") or cached_reason

        # é¦æ¬¡å®¡æ¥ï¼åè¡¥å¨ç»æï¼åéªè¯/ä¿®å¤
        self._normalize_chart_block(block, chapter_context)

        if increment_stats:
            self.chart_validation_stats['total'] += 1

        if is_wordcloud:
            if increment_stats:
                self.chart_validation_stats['valid'] += 1
            block["_chart_reviewed"] = True
            block["_chart_review_status"] = "valid"
            block["_chart_review_method"] = "none"
            return True, None

        validation_result = self.chart_validator.validate(block)

        if not validation_result.is_valid:
            logger.warning(
                f"å¾è¡¨ {block.get('widgetId', 'unknown')} éªè¯å¤±è´¥: {validation_result.errors}"
            )

            repair_result = self.chart_repairer.repair(block, validation_result)

            if repair_result.success and repair_result.repaired_block:
                # ä¿®å¤æåï¼ååä¿®å¤åçæ°ï¿½?
                repaired_block = repair_result.repaired_block
                block.clear()
                block.update(repaired_block)
                method = repair_result.method or "local"
                logger.info(
                    f"å¾è¡¨ {block.get('widgetId', 'unknown')} ä¿®å¤æå "
                    f"(æ¹æ³: {method}): {repair_result.changes}"
                )

                if increment_stats:
                    if method == 'local':
                        self.chart_validation_stats['repaired_locally'] += 1
                    elif method == 'api':
                        self.chart_validation_stats['repaired_api'] += 1
                block["_chart_review_status"] = "repaired"
                block["_chart_review_method"] = method
                block["_chart_reviewed"] = True
                return True, None

            # ä¿®å¤å¤±è´¥ï¼è®°å½å¤±è´¥å¹¶è¾åºå ä½æç¤º
            fail_reason = self._format_chart_error_reason(validation_result)
            block["_chart_renderable"] = False
            block["_chart_error_reason"] = fail_reason
            block["_chart_review_status"] = "failed"
            block["_chart_review_method"] = "none"
            block["_chart_reviewed"] = True
            self._note_chart_failure(cache_key, fail_reason)
            if increment_stats:
                self._record_chart_failure_stat(cache_key)
            logger.warning(
                f"å¾è¡¨ {block.get('widgetId', 'unknown')} ä¿®å¤å¤±è´¥ï¼å·²è·³è¿æ¸²æ: {fail_reason}"
            )
            return False, fail_reason

        # éªè¯éè¿
        if increment_stats:
            self.chart_validation_stats['valid'] += 1
            if validation_result.warnings:
                logger.info(
                    f"å¾è¡¨ {block.get('widgetId', 'unknown')} éªè¯éè¿ï¿½?
                    f"ä½æè­¦å: {validation_result.warnings}"
                )
        block["_chart_review_status"] = "valid"
        block["_chart_review_method"] = "none"
        block["_chart_reviewed"] = True
        return True, None

    def review_and_patch_document(
        self,
        document_ir: Dict[str, Any],
        *,
        reset_stats: bool = True,
        clone: bool = False
    ) -> Dict[str, Any]:
        """
        å¨å±å®¡æ¥å¹¶ä¿®å¤å¾è¡¨ï¼å°ä¿®å¤ç»æååå°åå§ IRï¼é¿åå¤æ¬¡æ¸²æéå¤ä¿®å¤ï¿½?

        åæ°:
            document_ir: åå§ Document IR
            reset_stats: æ¯å¦éç½®ç»è®¡æ°æ®
            clone: æ¯å¦è¿åä¿®å¤åçæ·±æ·è´ï¼åå§ IR ä»ä¼è¢«ååä¿®å¤ç»æï¼

        è¿å:
            ä¿®å¤åç IRï¼å¯è½æ¯åå¯¹è±¡æå¶æ·±æ·è´ï¿½?
        """
        if reset_stats:
            self._reset_chart_validation_stats()

        target_ir = document_ir or {}

        def _walk_blocks(blocks: list, chapter_ctx: Dict[str, Any] | None = None) -> None:
            for blk in blocks or []:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "widget":
                    self._ensure_chart_reviewed(blk, chapter_ctx, increment_stats=True)

                nested_blocks = blk.get("blocks")
                if isinstance(nested_blocks, list):
                    _walk_blocks(nested_blocks, chapter_ctx)

                if blk.get("type") == "list":
                    for item in blk.get("items", []):
                        if isinstance(item, list):
                            _walk_blocks(item, chapter_ctx)

                if blk.get("type") == "table":
                    for row in blk.get("rows", []):
                        cells = row.get("cells", [])
                        for cell in cells:
                            if isinstance(cell, dict):
                                cell_blocks = cell.get("blocks", [])
                                if isinstance(cell_blocks, list):
                                    _walk_blocks(cell_blocks, chapter_ctx)

        for chapter in target_ir.get("chapters", []) or []:
            if not isinstance(chapter, dict):
                continue
            _walk_blocks(chapter.get("blocks", []), chapter)

        return copy.deepcopy(target_ir) if clone else target_ir

    def _render_widget(self, block: Dict[str, Any]) -> str:
        """
        æ¸²æEChartsç­äº¤äºç»ä»¶çå ä½å®¹å¨ï¼å¹¶è®°å½éç½®JSONï¿½?

        å¨æ¸²æåè¿è¡å¾è¡¨éªè¯åä¿®å¤ï¼
        1. validateï¼ChartValidator æ£ï¿½?block ï¿½?data/props/options ç»æï¿½?
        2. repairï¼è¥å¤±è´¥ï¼åæ¬å°ä¿®è¡¥ï¼åè°ç¨ LLM APIï¿½?
        3. å¤±è´¥ååºï¼åï¿½?_chart_renderable=False ï¿½?_chart_error_reasonï¼è¾åºéè¯¯å ä½èéæå¼å¸¸ï¿½?
        """
        widget_type = block.get('widgetType', '')
        # æ¯æ chart.js ï¿½?echarts åç¼çå¼ï¿½?
        is_chart = isinstance(widget_type, str) and (widget_type.startswith('chart.js') or widget_type.startswith('echarts'))
        is_wordcloud = isinstance(widget_type, str) and 'wordcloud' in widget_type.lower()
        reviewed = bool(block.get("_chart_reviewed"))
        renderable = True
        fail_reason = None

        if is_chart:
            renderable, fail_reason = self._ensure_chart_reviewed(
                block,
                getattr(self, "_current_chapter", None),
                increment_stats=not reviewed
            )

        widget_id = block.get('widgetId')
        props_snapshot = block.get("props") if isinstance(block.get("props"), dict) else {}
        display_title = props_snapshot.get("title") or block.get("title") or widget_id or "å¾è¡¨"

        if is_chart and not renderable:
            reason = fail_reason or "LLMè¿åçå¾è¡¨ä¿¡æ¯æ ¼å¼æè¯¯ï¼æ æ³æ­£å¸¸æ¾ç¤º"
            return self._render_chart_error_placeholder(display_title, reason, widget_id)

        # æ¸²æå¾è¡¨HTML
        self.chart_counter += 1
        container_id = f"echart-{self.chart_counter}"
        config_id = f"chart-config-{self.chart_counter}"

        props, normalized_data = self._prepare_widget_payload(block)
        payload = {
            "widgetId": block.get("widgetId"),
            "widgetType": block.get("widgetType"),
            "props": props,
            "data": normalized_data,
            "dataRef": block.get("dataRef"),
        }
        config_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
        self.widget_scripts.append(
            f'<script type="application/json" id="{config_id}">{config_json}</script>'
        )

        title = props.get("title")
        title_html = f'<div class="chart-title">{self._escape_html(title)}</div>' if title else ""
        fallback_html = (
            self._render_wordcloud_fallback(props, block.get("widgetId"), block.get("data"))
            if is_wordcloud
            else self._render_widget_fallback(normalized_data, block.get("widgetId"))
        )
        return f"""
        <div class="chart-card{' wordcloud-card' if is_wordcloud else ''}">
          {title_html}
          <div class="chart-container" style="position: relative; height: 400px; width: 100%;">
            <div id="{container_id}" class="echarts-container" data-config-id="{config_id}" style="width: 100%; height: 100%;"></div>
          </div>
          {fallback_html}
        </div>
        """

    def _render_widget_fallback(self, data: Dict[str, Any], widget_id: str | None = None) -> str:
        """æ¸²æå¾è¡¨æ°æ®çææ¬ååºè§å¾ï¼é¿åChart.jså è½½å¤±è´¥æ¶åºç°ç©ºï¿½?""
        if not isinstance(data, dict):
            return ""
        labels = data.get("labels") or []
        datasets = data.get("datasets") or []
        if not labels or not datasets:
            return ""

        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        header_cells = "".join(
            f"<th>{self._escape_html(ds.get('label') or f'ç³»å{idx + 1}')}</th>"
            for idx, ds in enumerate(datasets)
        )
        body_rows = ""
        for idx, label in enumerate(labels):
            row_cells = [f"<td>{self._escape_html(label)}</td>"]
            for ds in datasets:
                series = ds.get("data") or []
                value = series[idx] if idx < len(series) else ""
                row_cells.append(f"<td>{self._escape_html(value)}</td>")
            body_rows += f"<tr>{''.join(row_cells)}</tr>"
        table_html = f"""
        <div class="chart-fallback" data-prebuilt="true"{widget_attr}>
          <table>
            <thead>
              <tr><th>ç±»å«</th>{header_cells}</tr>
            </thead>
            <tbody>
              {body_rows}
            </tbody>
          </table>
        </div>
        """
        return table_html

    def _render_wordcloud_fallback(
        self,
        props: Dict[str, Any] | None,
        widget_id: str | None = None,
        block_data: Any | None = None,
    ) -> str:
        """ä¸ºè¯äºæä¾è¡¨æ ¼ååºï¼é¿åWordCloudæ¸²æå¤±è´¥åé¡µé¢ç©ºï¿½?""
        def _collect_items(raw: Any) -> list[dict]:
            """å°å¤ç§è¯äºè¾å¥æ ¼å¼ï¼æ°ç»/å¯¹è±¡/åç»/çº¯ææ¬ï¼è§æ´ä¸ºç»ä¸çè¯æ¡åï¿½?""
            collected: list[dict] = []
            skip_keys = {"items", "data", "words", "labels", "datasets", "sourceData"}
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        text = item.get("word") or item.get("text") or item.get("label")
                        weight = item.get("weight")
                        category = item.get("category") or ""
                        if text:
                            collected.append({"word": str(text), "weight": weight, "category": str(category)})
                        # è¥åµå¥äº items/words/data åè¡¨ï¼éå½æå
                        for nested_key in ("items", "words", "data"):
                            nested = item.get(nested_key)
                            if isinstance(nested, list):
                                collected.extend(_collect_items(nested))
                    elif isinstance(item, (list, tuple)) and item:
                        text = item[0]
                        weight = item[1] if len(item) > 1 else None
                        category = item[2] if len(item) > 2 else ""
                        if text:
                            collected.append({"word": str(text), "weight": weight, "category": str(category)})
                    elif isinstance(item, str):
                        collected.append({"word": item, "weight": 1.0, "category": ""})
            elif isinstance(raw, dict):
                # è¥åï¿½?items/words/data åè¡¨ï¼ä¼åéå½æåï¼ä¸æé®åå½ï¿½?
                handled = False
                for nested_key in ("items", "words", "data"):
                    nested = raw.get(nested_key)
                    if isinstance(nested, list):
                        collected.extend(_collect_items(nested))
                        handled = True
                if handled:
                    return collected

                # éChartç»æä¸ä¸åå«skip_keysæ¶ï¼ækey/valueå½ä½è¯äºæ¡ç®
                if not {"labels", "datasets"}.intersection(raw.keys()):
                    for text, weight in raw.items():
                        if text in skip_keys:
                            continue
                        collected.append({"word": str(text), "weight": weight, "category": ""})
            return collected

        words: list[dict] = []
        seen: set[str] = set()
        candidates = []
        if isinstance(props, dict):
            # ä»æ¥åæç¡®çè¯æ¡æ°ç»å­æ®µï¼é¿åå°åµå¥itemsè¯¯å½ä½è¯ï¿½?
            if "data" in props and isinstance(props.get("data"), list):
                candidates.append(props["data"])
            if "words" in props and isinstance(props.get("words"), list):
                candidates.append(props["words"])
            if "items" in props and isinstance(props.get("items"), list):
                candidates.append(props["items"])
        candidates.append((props or {}).get("sourceData"))

        # åè®¸ä½¿ç¨block.dataååºï¼é¿åç¼ºå¤±propsæ¶åºç°ç©ºï¿½?
        if block_data is not None:
            if isinstance(block_data, dict) and "items" in block_data and isinstance(block_data.get("items"), list):
                candidates.append(block_data["items"])
            else:
                candidates.append(block_data)

        for raw in candidates:
            for item in _collect_items(raw):
                key = f"{item['word']}::{item.get('category','')}"
                if key in seen:
                    continue
                seen.add(key)
                words.append(item)

        if not words:
            return ""

        def _format_weight(value: Any) -> str:
            """ç»ä¸æ ¼å¼åæéï¼æ¯æç¾åï¿½?æ°å¼ä¸å­ç¬¦ä¸²åé"""
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if 0 <= value <= 1.5:
                    return f"{value * 100:.1f}%"
                return f"{value:.2f}".rstrip("0").rstrip(".")
            return str(value)

        widget_attr = f' data-widget-id="{self._escape_attr(widget_id)}"' if widget_id else ""
        rows = "".join(
            f"<tr><td>{self._escape_html(item['word'])}</td>"
            f"<td>{self._escape_html(_format_weight(item['weight']))}</td>"
            f"<td>{self._escape_html(item['category'] or '-')}</td></tr>"
            for item in words
        )
        return f"""
        <div class="chart-fallback" data-prebuilt="true"{widget_attr}>
          <table>
            <thead>
              <tr><th>å³é®ï¿½?/th><th>æé</th><th>ç±»å«</th></tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
        """

    def _log_chart_validation_stats(self):
        """è¾åºå¾è¡¨éªè¯ç»è®¡ä¿¡æ¯"""
        stats = self.chart_validation_stats
        if stats['total'] == 0:
            return

        logger.info("=" * 60)
        logger.info("å¾è¡¨éªè¯ç»è®¡")
        logger.info("=" * 60)
        logger.info(f"æ»å¾è¡¨æ°ï¿½? {stats['total']}")
        logger.info(f"  ï¿½?éªè¯éè¿: {stats['valid']} ({stats['valid']/stats['total']*100:.1f}%)")

        if stats['repaired_locally'] > 0:
            logger.info(
                f"  ï¿½?æ¬å°ä¿®å¤: {stats['repaired_locally']} "
                f"({stats['repaired_locally']/stats['total']*100:.1f}%)"
            )

        if stats['repaired_api'] > 0:
            logger.info(
                f"  ï¿½?APIä¿®å¤: {stats['repaired_api']} "
                f"({stats['repaired_api']/stats['total']*100:.1f}%)"
            )

        if stats['failed'] > 0:
            logger.warning(
                f"  ï¿½?ä¿®å¤å¤±è´¥: {stats['failed']} "
                f"({stats['failed']/stats['total']*100:.1f}%) - "
                f"è¿äºå¾è¡¨å°å±ç¤ºç®æ´å ä½æï¿½?
            )

        logger.info("=" * 60)

    # ====== åç½®ä¿¡æ¯é²æ¤ ======

    def _kpi_signature_from_items(self, items: Any) -> tuple | None:
        """å°KPIæ°ç»è½¬æ¢ä¸ºå¯æ¯è¾çç­¾ï¿½?""
        if not isinstance(items, list):
            return None
        normalized = []
        for raw in items:
            normalized_item = self._normalize_kpi_item(raw)
            if normalized_item:
                normalized.append(normalized_item)
        return tuple(normalized) if normalized else None

    def _normalize_kpi_item(self, item: Any) -> tuple[str, str, str, str, str] | None:
        """
        å°åæ¡KPIè®°å½è§æ´ä¸ºå¯å¯¹æ¯çç­¾åï¿½?

        åæ°:
            item: KPIæ°ç»ä¸­çåå§å­å¸ï¼å¯è½ç¼ºå¤±å­æ®µæç±»åæ··æï¿½?

        è¿å:
            tuple | None: (label, value, unit, delta, tone) çäºåç»ï¼è¥è¾å¥éæ³åä¸ºNoneï¿½?
        """
        if not isinstance(item, dict):
            return None

        def normalize(value: Any) -> str:
            """ç»ä¸åç±»å¼çè¡¨ç°å½¢å¼ï¼ä¾¿äºçæç¨³å®ç­¾ï¿½?""
            if value is None:
                return ""
            if isinstance(value, (int, float)):
                return str(value)
            return str(value).strip()

        label = normalize(item.get("label"))
        value = normalize(item.get("value"))
        unit = normalize(item.get("unit"))
        delta = normalize(item.get("delta"))
        tone = normalize(item.get("deltaTone") or item.get("tone"))
        return label, value, unit, delta, tone

    def _should_skip_overview_kpi(self, block: Dict[str, Any]) -> bool:
        """è¥KPIåå®¹ä¸å°é¢ä¸è´ï¼åå¤å®ä¸ºéå¤æ»è§"""
        if not self.hero_kpi_signature:
            return False
        block_signature = self._kpi_signature_from_items(block.get("items"))
        if not block_signature:
            return False
        return block_signature == self.hero_kpi_signature

    # ====== è¡åæ¸²æ ======

    def _normalize_inline_payload(self, run: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
        """å°åµå¥inline nodeå±å¹³æåºç¡ææ¬ä¸marks"""
        if not isinstance(run, dict):
            return ("" if run is None else str(run)), []

        # å¤ç inlineRun ç±»åï¼éå½å±å¼ï¿½?inlines æ°ç»
        if run.get("type") == "inlineRun":
            inner_inlines = run.get("inlines") or []
            outer_marks = run.get("marks") or []
            # éå½åå¹¶ææåï¿½?inlines çæï¿½?
            texts = []
            all_marks = list(outer_marks)
            for inline in inner_inlines:
                inner_text, inner_marks = self._normalize_inline_payload(inline)
                texts.append(inner_text)
                all_marks.extend(inner_marks)
            return "".join(texts), all_marks

        marks = list(run.get("marks") or [])
        text_value: Any = run.get("text", "")
        seen: set[int] = set()

        while isinstance(text_value, dict):
            obj_id = id(text_value)
            if obj_id in seen:
                text_value = ""
                break
            seen.add(obj_id)
            nested_marks = text_value.get("marks")
            if nested_marks:
                marks.extend(nested_marks)
            if "text" in text_value:
                text_value = text_value.get("text")
            else:
                text_value = json.dumps(text_value, ensure_ascii=False)
                break

        if text_value is None:
            text_value = ""
        elif isinstance(text_value, (int, float)):
            text_value = str(text_value)
        elif not isinstance(text_value, str):
            try:
                text_value = json.dumps(text_value, ensure_ascii=False)
            except TypeError:
                text_value = str(text_value)

        if isinstance(text_value, str):
            stripped = text_value.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                payload = None
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    try:
                        payload = ast.literal_eval(stripped)
                    except (ValueError, SyntaxError):
                        payload = None
                if isinstance(payload, dict):
                    sentinel_keys = {"xrefs", "widgets", "footnotes", "errors", "metadata"}
                    if set(payload.keys()).issubset(sentinel_keys):
                        text_value = ""
                    else:
                        inline_payload = self._coerce_inline_payload(payload)
                        if inline_payload:
                            # å¤ç inlineRun ç±»å
                            if inline_payload.get("type") == "inlineRun":
                                return self._normalize_inline_payload(inline_payload)
                            nested_text = inline_payload.get("text")
                            if nested_text is not None:
                                text_value = nested_text
                            nested_marks = inline_payload.get("marks")
                            if isinstance(nested_marks, list):
                                marks.extend(nested_marks)
                        elif any(key in payload for key in self.INLINE_ARTIFACT_KEYS):
                            text_value = ""

        return text_value, marks

    @staticmethod
    def _normalize_latex_string(raw: Any) -> str:
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
        return latex

    def _render_text_with_inline_math(
        self,
        text: Any,
        math_id: str | list | None = None,
        allow_display_block: bool = False
    ) -> str | None:
        """
        è¯å«çº¯ææ¬ä¸­çæ°å­¦å®çç¬¦å¹¶æ¸²æä¸ºmath-inline/math-blockï¼æåå¼å®¹æ§ï¿½?

        - æ¯æ $...$ï¿½?$...$$\(\\)\[\\]ï¿½?
        - è¥æªæ£æµå°å¬å¼ï¼è¿åNoneï¿½?
        """
        if not isinstance(text, str) or not text:
            return None

        pattern = re.compile(r'(\$\$(.+?)\$\$|\$(.+?)\$|\\\((.+?)\\\)|\\\[(.+?)\\\])', re.S)
        matches = list(pattern.finditer(text))
        if not matches:
            return None

        cursor = 0
        parts: List[str] = []
        id_iter = iter(math_id) if isinstance(math_id, list) else None

        for idx, m in enumerate(matches, start=1):
            start, end = m.span()
            prefix = text[cursor:start]
            raw = next(g for g in m.groups()[1:] if g is not None)
            latex = self._normalize_latex_string(raw)
            # è¥å·²æmath_idï¼ç´æ¥ä½¿ç¨ï¼é¿åä¸SVGæ³¨å¥IDä¸ä¸è´ï¼å¦åæå±é¨åºå·çï¿½?
            if id_iter:
                mid = next(id_iter, f"auto-math-{idx}")
            else:
                mid = math_id or f"auto-math-{idx}"
            id_attr = f' data-math-id="{self._escape_attr(mid)}"'
            is_display = m.group(1).startswith('$$') or m.group(1).startswith('\\[')
            is_standalone = (
                len(matches) == 1 and
                not text[:start].strip() and
                not text[end:].strip()
            )
            use_block = allow_display_block and is_display and is_standalone
            if use_block:
                # ç¬ç«displayå¬å¼ï¼è·³è¿ä¸¤ä¾§ç©ºç½ï¼ç´æ¥æ¸²æåçº§
                parts.append(f'<div class="math-block"{id_attr}>$$ {self._escape_html(latex)} $$</div>')
                cursor = len(text)
                break
            else:
                if prefix:
                    parts.append(self._escape_html(prefix))
                parts.append(f'<span class="math-inline"{id_attr}>\\( {self._escape_html(latex)} \\)</span>')
            cursor = end

        if cursor < len(text):
            parts.append(self._escape_html(text[cursor:]))
        return "".join(parts)

    @staticmethod
    def _coerce_inline_payload(payload: Dict[str, Any]) -> Dict[str, Any] | None:
        """å°½åå°å­ç¬¦ä¸²éçåèèç¹æ¢å¤ä¸ºdictï¼ä¿®å¤æ¸²æéï¿½?""
        if not isinstance(payload, dict):
            return None
        inline_type = payload.get("type")
        # æ¯æ inlineRun ç±»åï¼åå«åµå¥ç inlines æ°ç»
        if inline_type == "inlineRun":
            return payload
        if inline_type and inline_type not in {"inline", "text"}:
            return None
        if "text" not in payload and "marks" not in payload and "inlines" not in payload:
            return None
        return payload

    def _render_inline(self, run: Dict[str, Any]) -> str:
        """
        æ¸²æåä¸ªinline runï¼æ¯æå¤ç§markså å ï¿½?

        åæ°:
            run: ï¿½?text ï¿½?marks çåèèç¹ï¿½?

        è¿å:
            str: å·²åè£¹æ ï¿½?æ ·å¼çHTMLçæ®µï¿½?
        """
        text_value, marks = self._normalize_inline_payload(run)
        math_mark = next((mark for mark in marks if mark.get("type") == "math"), None)
        if math_mark:
            latex = self._normalize_latex_string(math_mark.get("value"))
            if not isinstance(latex, str) or not latex.strip():
                latex = self._normalize_latex_string(text_value)
            math_id = self._escape_attr(run.get("mathId", "")) if run.get("mathId") else ""
            id_attr = f' data-math-id="{math_id}"' if math_id else ""
            return f'<span class="math-inline"{id_attr}>\\( {self._escape_html(latex)} \\)</span>'

        # å°è¯ä»çº¯ææ¬ä¸­æåæ°å­¦å¬å¼ï¼å³ä¾¿æ²¡æmath markï¿½?
        math_id_hint = run.get("mathIds") or run.get("mathId")
        mathified = self._render_text_with_inline_math(text_value, math_id_hint)
        if mathified is not None:
            return mathified

        text = self._escape_html(text_value)
        styles: List[str] = []
        prefix: List[str] = []
        suffix: List[str] = []
        for mark in marks:
            mark_type = mark.get("type")
            if mark_type == "bold":
                prefix.append("<strong>")
                suffix.insert(0, "</strong>")
            elif mark_type == "italic":
                prefix.append("<em>")
                suffix.insert(0, "</em>")
            elif mark_type == "code":
                prefix.append("<code>")
                suffix.insert(0, "</code>")
            elif mark_type == "highlight":
                prefix.append("<mark>")
                suffix.insert(0, "</mark>")
            elif mark_type == "link":
                href_raw = mark.get("href")
                if href_raw and href_raw != "#":
                    href = self._escape_attr(href_raw)
                    title = self._escape_attr(mark.get("title") or "")
                    # å¦ææ¯é¡µåéç¹ï¼æ¯å¦ #citation-1ï¼ï¼å°±ä¸ï¿½?target="_blank"
                    if href.startswith("#"):
                        prefix.append(f'<a href="{href}" title="{title}">')
                    else:
                        prefix.append(f'<a href="{href}" title="{title}" target="_blank" rel="noopener">')
                    suffix.insert(0, "</a>")
                else:
                    prefix.append('<span class="broken-link">')
                    suffix.insert(0, "</span>")
            elif mark_type == "color":
                value = mark.get("value")
                if value:
                    styles.append(f"color: {value}")
            elif mark_type == "font":
                family = mark.get("family")
                size = mark.get("size")
                weight = mark.get("weight")
                if family:
                    styles.append(f"font-family: {family}")
                if size:
                    styles.append(f"font-size: {size}")
                if weight:
                    styles.append(f"font-weight: {weight}")
            elif mark_type == "underline":
                styles.append("text-decoration: underline")
            elif mark_type == "strike":
                styles.append("text-decoration: line-through")
            elif mark_type == "subscript":
                prefix.append("<sub>")
                suffix.insert(0, "</sub>")
            elif mark_type == "superscript":
                prefix.append("<sup>")
                suffix.insert(0, "</sup>")

        if styles:
            style_attr = "; ".join(styles)
            prefix.insert(0, f'<span style="{style_attr}">')
            suffix.append("</span>")

        if not marks and "**" in (run.get("text") or ""):
            return self._render_markdown_bold_fallback(run.get("text", ""))

        return "".join(prefix) + text + "".join(suffix)

    def _render_markdown_bold_fallback(self, text: str) -> str:
        """å¨LLMæªä½¿ç¨marksæ¶ååºè½¬ï¿½?*ç²ä½**"""
        if not text:
            return ""
        result: List[str] = []
        cursor = 0
        while True:
            start = text.find("**", cursor)
            if start == -1:
                result.append(html.escape(text[cursor:]))
                break
            end = text.find("**", start + 2)
            if end == -1:
                result.append(html.escape(text[cursor:]))
                break
            result.append(html.escape(text[cursor:start]))
            bold_content = html.escape(text[start + 2:end])
            result.append(f"<strong>{bold_content}</strong>")
            cursor = end + 2
        return "".join(result)

    # ====== ææ¬ / å®å¨å·¥å· ======

    def _clean_text_from_json_artifacts(self, text: Any) -> str:
        """
        æ¸çææ¬ä¸­çJSONçæ®µåä¼ªé çç»ææ è®°ï¿½?

        LLMææ¶ä¼å¨ææ¬å­æ®µä¸­æ··å¥æªå®æçJSONçæ®µï¼å¦ï¿½?
        "æè¿°ææ¬ï¼{ \"chapterId\": \"S3" ï¿½?"æè¿°ææ¬ï¼{ \"level\": 2"

        æ­¤æ¹æ³ä¼ï¿½?
        1. ç§»é¤ä¸å®æ´çJSONå¯¹è±¡ï¼ä»¥ { å¼å¤´ä½æªæ­£ç¡®é­åçï¿½?
        2. ç§»é¤ä¸å®æ´çJSONæ°ç»ï¼ä»¥ [ å¼å¤´ä½æªæ­£ç¡®é­åçï¿½?
        3. ç§»é¤å­¤ç«çJSONé®å¼å¯¹çæ®µ

        åæ°:
            text: å¯è½åå«JSONçæ®µçæï¿½?

        è¿å:
            str: æ¸çåççº¯æï¿½?
        """
        if not text:
            return ""

        text_str = self._safe_text(text)

        # æ¨¡å¼1: ç§»é¤ä»¥éå·+ç©ºç½+{å¼å¤´çä¸å®æ´JSONå¯¹è±¡
        # ä¾å¦: "ææ¬ï¼{ \"key\": \"value\"" ï¿½?"ææ¬ï¼{\\n  \"key\""
        text_str = re.sub(r',\s*\{[^}]*$', '', text_str)

        # æ¨¡å¼2: ç§»é¤ä»¥éå·+ç©ºç½+[å¼å¤´çä¸å®æ´JSONæ°ç»
        text_str = re.sub(r',\s*\[[^\]]*$', '', text_str)

        # æ¨¡å¼3: ç§»é¤å­¤ç«ï¿½?{ å ä¸åç»­åå®¹ï¼å¦ææ²¡æå¹éç }ï¿½?
        # æ£æ¥æ¯å¦ææªé­åç {
        open_brace_pos = text_str.rfind('{')
        if open_brace_pos != -1:
            close_brace_pos = text_str.rfind('}')
            if close_brace_pos < open_brace_pos:
                # { ï¿½?} åé¢ææ²¡ï¿½?}ï¼è¯´ææ¯æªé­åç
                # æªæ­ï¿½?{ ä¹å
                text_str = text_str[:open_brace_pos].rstrip(',ï¼ï¿½?\t\n')

        # æ¨¡å¼4: ç±»ä¼¼å¤ç [
        open_bracket_pos = text_str.rfind('[')
        if open_bracket_pos != -1:
            close_bracket_pos = text_str.rfind(']')
            if close_bracket_pos < open_bracket_pos:
                # [ ï¿½?] åé¢ææ²¡ï¿½?]ï¼è¯´ææ¯æªé­åç
                text_str = text_str[:open_bracket_pos].rstrip(',ï¼ï¿½?\t\n')

        # æ¨¡å¼5: ç§»é¤çèµ·æ¥åJSONé®å¼å¯¹ççæ®µï¼ï¿½?"chapterId": "S3
        # è¿ç§æåµéå¸¸åºç°å¨ä¸é¢çæ¨¡å¼ä¹å
        text_str = re.sub(r',?\s*"[^"]+"\s*:\s*"[^"]*$', '', text_str)
        text_str = re.sub(r',?\s*"[^"]+"\s*:\s*[^,}\]]*$', '', text_str)

        # æ¸çæ«å°¾çéå·åç©ºï¿½?
        text_str = text_str.rstrip(',ï¼ï¿½?\t\n')

        return text_str.strip()

    def _safe_text(self, value: Any) -> str:
        """å°ä»»æå¼å®å¨è½¬æ¢ä¸ºå­ç¬¦ä¸²ï¼Noneä¸å¤æå¯¹è±¡å®¹ï¿½?""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    def _escape_html(self, value: Any) -> str:
        """HTMLææ¬ä¸ä¸æçè½¬ä¹"""
        return html.escape(self._safe_text(value), quote=False)

    def _escape_attr(self, value: Any) -> str:
        """HTMLå±æ§ä¸ä¸æè½¬ä¹å¹¶å»æå±é©æ¢ï¿½?""
        escaped = html.escape(self._safe_text(value), quote=True)
        return escaped.replace("\n", " ").replace("\r", " ")

    # ====== CSS / JSï¼æ ·å¼ä¸èæ¬ï¿½?======

    def _build_css(self, tokens: Dict[str, Any]) -> str:
        """æ ¹æ®ä¸»é¢tokenæ¼æ¥æ´é¡µCSSï¼åæ¬ååºå¼ä¸æå°æ ·ï¿½?""
        # å®å¨è·ååä¸ªéç½®é¡¹ï¼ç¡®ä¿é½æ¯å­å¸ç±»å
        colors_raw = tokens.get("colors")
        colors = colors_raw if isinstance(colors_raw, dict) else {}

        typography_raw = tokens.get("typography")
        typography = typography_raw if isinstance(typography_raw, dict) else {}

        # å®å¨è·åfontsï¼ç¡®ä¿æ¯å­å¸ç±»å
        fonts_raw = tokens.get("fonts") or typography.get("fonts")
        if isinstance(fonts_raw, dict):
            fonts = fonts_raw
        else:
            # å¦æfontsæ¯å­ç¬¦ä¸²æNoneï¼æé ä¸ä¸ªå­ï¿½?
            font_family = typography.get("fontFamily")
            if isinstance(font_family, str):
                fonts = {"body": font_family, "heading": font_family}
            else:
                fonts = {}

        spacing_raw = tokens.get("spacing")
        spacing = spacing_raw if isinstance(spacing_raw, dict) else {}

        primary_palette = self._resolve_color_family(
            colors.get("primary"),
            {"main": "#e90130", "light": "#ff4d6d", "dark": "#c1121f"},
        )
        secondary_palette = self._resolve_color_family(
            colors.get("secondary"),
            {"main": "#1a1a1a", "light": "#404040", "dark": "#000000"},
        )
        bg = self._resolve_color_value(
            colors.get("bg") or colors.get("background") or colors.get("surface"),
            "#ffffff",
        )
        text_color = self._resolve_color_value(
            colors.get("text") or colors.get("onBackground"),
            "#1a1a1a",
        )
        card = self._resolve_color_value(
            colors.get("card") or colors.get("surfaceCard"),
            "#ffffff",
        )
        border = self._resolve_color_value(
            colors.get("border") or colors.get("divider"),
            "#e5e5e5",
        )
        shadow = "rgba(0,0,0,0.06)"
        container_width = spacing.get("container") or spacing.get("containerWidth") or "1200px"
        gutter = spacing.get("gutter") or spacing.get("pagePadding") or "24px"
        body_font = fonts.get("body") or fonts.get("primary") or "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
        heading_font = fonts.get("heading") or fonts.get("primary") or fonts.get("secondary") or body_font

        return f"""
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

:root {{ /* å«ä¹ï¼äº®è²ä¸»é¢åéåºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --bg-color: {bg}; /* å«ä¹ï¼é¡µé¢èæ¯è²ä¸»è²è°ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --text-color: {text_color}; /* å«ä¹ï¼æ­£æææ¬åºç¡é¢è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color: {primary_palette["main"]}; /* å«ä¹ï¼ä¸»è²è°ï¼æï¿½?é«äº®ï¼ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color-light: {primary_palette["light"]}; /* å«ä¹ï¼ä¸»è²è°æµè²ï¼ç¨äºæ¬ï¿½?æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color-dark: {primary_palette["dark"]}; /* å«ä¹ï¼ä¸»è²è°æ·±è²ï¼ç¨äºå¼ºè°ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color: {secondary_palette["main"]}; /* å«ä¹ï¼æ¬¡çº§è²ï¼æï¿½?æ ç­¾ï¼ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color-light: {secondary_palette["light"]}; /* å«ä¹ï¼æ¬¡çº§è²æµè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color-dark: {secondary_palette["dark"]}; /* å«ä¹ï¼æ¬¡çº§è²æ·±è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --card-bg: {card}; /* å«ä¹ï¼å¡ï¿½?å®¹å¨èæ¯è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --border-color: {border}; /* å«ä¹ï¼å¸¸è§è¾¹æ¡è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --shadow-color: {shadow}; /* å«ä¹ï¼é´å½±åºè²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-bg: #f4f7ff; /* å«ä¹ï¼Insight å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-border: #dce7ff; /* å«ä¹ï¼Insight å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-text: #1f4b99; /* å«ä¹ï¼Insight å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-bg: #fff6ec; /* å«ä¹ï¼Media å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-border: #ffd9b3; /* å«ä¹ï¼Media å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-text: #b65a1a; /* å«ä¹ï¼Media å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-bg: #f1fbf5; /* å«ä¹ï¼Query å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-border: #c7ebd6; /* å«ä¹ï¼Query å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-text: #1d6b3f; /* å«ä¹ï¼Query å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-shadow: 0 12px 30px rgba(0,0,0,0.04); /* å«ä¹ï¼Engine å¼ç¨é´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-strength: #1c7f6e; /* å«ä¹ï¼SWOT ä¼å¿ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-weakness: #c0392b; /* å«ä¹ï¼SWOT å£å¿ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-opportunity: #1f5ab3; /* å«ä¹ï¼SWOT æºä¼ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-threat: #b36b16; /* å«ä¹ï¼SWOT å¨èä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-on-light: #0f1b2b; /* å«ä¹ï¼SWOT äº®åºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-on-dark: #f7fbff; /* å«ä¹ï¼SWOT æåºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-text: var(--text-color); /* å«ä¹ï¼SWOT ææ¬ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-muted: rgba(0,0,0,0.58); /* å«ä¹ï¼SWOT æ¬¡ææ¬è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-surface: rgba(255,255,255,0.92); /* å«ä¹ï¼SWOT å¡çè¡¨é¢è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-chip-bg: rgba(0,0,0,0.04); /* å«ä¹ï¼SWOT æ ç­¾åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-tag-border: var(--border-color); /* å«ä¹ï¼SWOT æ ç­¾è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-bg: linear-gradient(135deg, rgba(76,132,255,0.04), rgba(28,127,110,0.06)), var(--card-bg); /* å«ä¹ï¼SWOT å¡çèæ¯æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-border: var(--border-color); /* å«ä¹ï¼SWOT å¡çè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-shadow: 0 14px 28px var(--shadow-color); /* å«ä¹ï¼SWOT å¡çé´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-blur: none; /* å«ä¹ï¼SWOT å¡çæ¨¡ç³ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-base: linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,255,255,0.5)); /* å«ä¹ï¼SWOT è±¡éåºç¡åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-border: rgba(0,0,0,0.04); /* å«ä¹ï¼SWOT è±¡éè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-strength-bg: linear-gradient(135deg, rgba(28,127,110,0.07), rgba(255,255,255,0.78)), var(--card-bg); /* å«ä¹ï¼SWOT ä¼å¿è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-weakness-bg: linear-gradient(135deg, rgba(192,57,43,0.07), rgba(255,255,255,0.78)), var(--card-bg); /* å«ä¹ï¼SWOT å£å¿è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-opportunity-bg: linear-gradient(135deg, rgba(31,90,179,0.07), rgba(255,255,255,0.78)), var(--card-bg); /* å«ä¹ï¼SWOT æºä¼è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-threat-bg: linear-gradient(135deg, rgba(179,107,22,0.07), rgba(255,255,255,0.78)), var(--card-bg); /* å«ä¹ï¼SWOT å¨èè±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-strength-border: rgba(28,127,110,0.35); /* å«ä¹ï¼SWOT ä¼å¿è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-weakness-border: rgba(192,57,43,0.35); /* å«ä¹ï¼SWOT å£å¿è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-opportunity-border: rgba(31,90,179,0.35); /* å«ä¹ï¼SWOT æºä¼è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-threat-border: rgba(179,107,22,0.35); /* å«ä¹ï¼SWOT å¨èè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-item-border: rgba(0,0,0,0.05); /* å«ä¹ï¼SWOT æ¡ç®è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  /* PEST åæåé - ç´«éè²ç³» */
  --pest-political: #8e44ad; /* å«ä¹ï¼PEST æ¿æ²»ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-economic: #16a085; /* å«ä¹ï¼PEST ç»æµç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-social: #e84393; /* å«ä¹ï¼PEST ç¤¾ä¼ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-technological: #2980b9; /* å«ä¹ï¼PEST ææ¯ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-on-light: #1a1a2e; /* å«ä¹ï¼PEST äº®åºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-on-dark: #f8f9ff; /* å«ä¹ï¼PEST æåºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-text: var(--text-color); /* å«ä¹ï¼PEST ææ¬ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-muted: rgba(0,0,0,0.55); /* å«ä¹ï¼PEST æ¬¡ææ¬è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-surface: rgba(255,255,255,0.88); /* å«ä¹ï¼PEST å¡çè¡¨é¢è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-chip-bg: rgba(0,0,0,0.05); /* å«ä¹ï¼PEST æ ç­¾åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-tag-border: var(--border-color); /* å«ä¹ï¼PEST æ ç­¾è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-bg: linear-gradient(145deg, rgba(142,68,173,0.03), rgba(22,160,133,0.04)), var(--card-bg); /* å«ä¹ï¼PEST å¡çèæ¯æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-border: var(--border-color); /* å«ä¹ï¼PEST å¡çè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-shadow: 0 16px 32px var(--shadow-color); /* å«ä¹ï¼PEST å¡çé´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-blur: none; /* å«ä¹ï¼PEST å¡çæ¨¡ç³ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-base: linear-gradient(90deg, rgba(255,255,255,0.95), rgba(255,255,255,0.7)); /* å«ä¹ï¼PEST æ¡å¸¦åºç¡åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-border: rgba(0,0,0,0.06); /* å«ä¹ï¼PEST æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-political-bg: linear-gradient(90deg, rgba(142,68,173,0.08), rgba(255,255,255,0.85)), var(--card-bg); /* å«ä¹ï¼PEST æ¿æ²»æ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-economic-bg: linear-gradient(90deg, rgba(22,160,133,0.08), rgba(255,255,255,0.85)), var(--card-bg); /* å«ä¹ï¼PEST ç»æµæ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-social-bg: linear-gradient(90deg, rgba(232,67,147,0.08), rgba(255,255,255,0.85)), var(--card-bg); /* å«ä¹ï¼PEST ç¤¾ä¼æ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-technological-bg: linear-gradient(90deg, rgba(41,128,185,0.08), rgba(255,255,255,0.85)), var(--card-bg); /* å«ä¹ï¼PEST ææ¯æ¡å¸¦åºè²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-political-border: rgba(142,68,173,0.4); /* å«ä¹ï¼PEST æ¿æ²»æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-economic-border: rgba(22,160,133,0.4); /* å«ä¹ï¼PEST ç»æµæ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-social-border: rgba(232,67,147,0.4); /* å«ä¹ï¼PEST ç¤¾ä¼æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-technological-border: rgba(41,128,185,0.4); /* å«ä¹ï¼PEST ææ¯æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-item-border: rgba(0,0,0,0.06); /* å«ä¹ï¼PEST æ¡ç®è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
}} /* ç»æ :root */
.dark-mode {{ /* å«ä¹ï¼æè²ä¸»é¢åéåºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --bg-color: #121212; /* å«ä¹ï¼é¡µé¢èæ¯è²ä¸»è²è°ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --text-color: #e0e0e0; /* å«ä¹ï¼æ­£æææ¬åºç¡é¢è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color: #6ea8fe; /* å«ä¹ï¼ä¸»è²è°ï¼æï¿½?é«äº®ï¼ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color-light: #91caff; /* å«ä¹ï¼ä¸»è²è°æµè²ï¼ç¨äºæ¬ï¿½?æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --primary-color-dark: #1f6feb; /* å«ä¹ï¼ä¸»è²è°æ·±è²ï¼ç¨äºå¼ºè°ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color: #f28b82; /* å«ä¹ï¼æ¬¡çº§è²ï¼æï¿½?æ ç­¾ï¼ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color-light: #f9b4ae; /* å«ä¹ï¼æ¬¡çº§è²æµè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --secondary-color-dark: #d9655c; /* å«ä¹ï¼æ¬¡çº§è²æ·±è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --card-bg: #1f1f1f; /* å«ä¹ï¼å¡ï¿½?å®¹å¨èæ¯è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --border-color: #2c2c2c; /* å«ä¹ï¼å¸¸è§è¾¹æ¡è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --shadow-color: rgba(0, 0, 0, 0.4); /* å«ä¹ï¼é´å½±åºè²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-bg: rgba(145, 202, 255, 0.08); /* å«ä¹ï¼Insight å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-border: rgba(145, 202, 255, 0.45); /* å«ä¹ï¼Insight å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-insight-text: #9dc2ff; /* å«ä¹ï¼Insight å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-bg: rgba(255, 196, 138, 0.08); /* å«ä¹ï¼Media å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-border: rgba(255, 196, 138, 0.45); /* å«ä¹ï¼Media å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-media-text: #ffcb9b; /* å«ä¹ï¼Media å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-bg: rgba(141, 215, 165, 0.08); /* å«ä¹ï¼Query å¼æå¡çèæ¯ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-border: rgba(141, 215, 165, 0.45); /* å«ä¹ï¼Query å¼æè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-query-text: #a7e2ba; /* å«ä¹ï¼Query å¼ææå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-shadow: 0 12px 28px rgba(0, 0, 0, 0.35); /* å«ä¹ï¼Engine å¼ç¨é´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-strength: #1c7f6e; /* å«ä¹ï¼SWOT ä¼å¿ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-weakness: #e06754; /* å«ä¹ï¼SWOT å£å¿ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-opportunity: #5a8cff; /* å«ä¹ï¼SWOT æºä¼ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-threat: #d48a2c; /* å«ä¹ï¼SWOT å¨èä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-on-light: #0f1b2b; /* å«ä¹ï¼SWOT äº®åºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-on-dark: #e6f0ff; /* å«ä¹ï¼SWOT æåºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-text: #e6f0ff; /* å«ä¹ï¼SWOT ææ¬ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-muted: rgba(230,240,255,0.75); /* å«ä¹ï¼SWOT æ¬¡ææ¬è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-surface: rgba(255,255,255,0.08); /* å«ä¹ï¼SWOT å¡çè¡¨é¢è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-chip-bg: rgba(255,255,255,0.14); /* å«ä¹ï¼SWOT æ ç­¾åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-tag-border: rgba(255,255,255,0.24); /* å«ä¹ï¼SWOT æ ç­¾è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-bg: radial-gradient(140% 140% at 18% 18%, rgba(110,168,254,0.18), transparent 55%), radial-gradient(120% 140% at 82% 0%, rgba(28,127,110,0.16), transparent 52%), linear-gradient(160deg, #0b1424 0%, #0b1f31 52%, #0a1626 100%); /* å«ä¹ï¼SWOT å¡çèæ¯æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-border: rgba(255,255,255,0.14); /* å«ä¹ï¼SWOT å¡çè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-shadow: 0 24px 60px rgba(0, 0, 0, 0.58); /* å«ä¹ï¼SWOT å¡çé´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-card-blur: blur(12px); /* å«ä¹ï¼SWOT å¡çæ¨¡ç³ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-base: linear-gradient(135deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02)); /* å«ä¹ï¼SWOT è±¡éåºç¡åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-border: rgba(255,255,255,0.2); /* å«ä¹ï¼SWOT è±¡éè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-strength-bg: linear-gradient(150deg, rgba(28,127,110,0.28), rgba(28,127,110,0.12)), var(--swot-cell-base); /* å«ä¹ï¼SWOT ä¼å¿è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-weakness-bg: linear-gradient(150deg, rgba(192,57,43,0.32), rgba(192,57,43,0.14)), var(--swot-cell-base); /* å«ä¹ï¼SWOT å£å¿è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-opportunity-bg: linear-gradient(150deg, rgba(31,90,179,0.28), rgba(31,90,179,0.12)), var(--swot-cell-base); /* å«ä¹ï¼SWOT æºä¼è±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-threat-bg: linear-gradient(150deg, rgba(179,107,22,0.32), rgba(179,107,22,0.14)), var(--swot-cell-base); /* å«ä¹ï¼SWOT å¨èè±¡éåºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-strength-border: rgba(28,127,110,0.65); /* å«ä¹ï¼SWOT ä¼å¿è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-weakness-border: rgba(192,57,43,0.68); /* å«ä¹ï¼SWOT å£å¿è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-opportunity-border: rgba(31,90,179,0.68); /* å«ä¹ï¼SWOT æºä¼è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-cell-threat-border: rgba(179,107,22,0.68); /* å«ä¹ï¼SWOT å¨èè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --swot-item-border: rgba(255,255,255,0.14); /* å«ä¹ï¼SWOT æ¡ç®è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  /* PEST åæåé - æè²æ¨¡å¼ */
  --pest-political: #a569bd; /* å«ä¹ï¼PEST æ¿æ²»ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-economic: #48c9b0; /* å«ä¹ï¼PEST ç»æµç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-social: #f06292; /* å«ä¹ï¼PEST ç¤¾ä¼ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-technological: #5dade2; /* å«ä¹ï¼PEST ææ¯ç»´åº¦ä¸»è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-on-light: #1a1a2e; /* å«ä¹ï¼PEST äº®åºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-on-dark: #f0f4ff; /* å«ä¹ï¼PEST æåºæå­è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-text: #f0f4ff; /* å«ä¹ï¼PEST ææ¬ä¸»è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-muted: rgba(240,244,255,0.7); /* å«ä¹ï¼PEST æ¬¡ææ¬è²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-surface: rgba(255,255,255,0.06); /* å«ä¹ï¼PEST å¡çè¡¨é¢è²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-chip-bg: rgba(255,255,255,0.12); /* å«ä¹ï¼PEST æ ç­¾åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-tag-border: rgba(255,255,255,0.22); /* å«ä¹ï¼PEST æ ç­¾è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-bg: radial-gradient(130% 130% at 15% 15%, rgba(165,105,189,0.16), transparent 50%), radial-gradient(110% 130% at 85% 5%, rgba(72,201,176,0.14), transparent 48%), linear-gradient(155deg, #12162a 0%, #161b30 50%, #0f1425 100%); /* å«ä¹ï¼PEST å¡çèæ¯æ¸åï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-border: rgba(255,255,255,0.12); /* å«ä¹ï¼PEST å¡çè¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-shadow: 0 28px 65px rgba(0, 0, 0, 0.55); /* å«ä¹ï¼PEST å¡çé´å½±ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-card-blur: blur(10px); /* å«ä¹ï¼PEST å¡çæ¨¡ç³ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-base: linear-gradient(90deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02)); /* å«ä¹ï¼PEST æ¡å¸¦åºç¡åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-border: rgba(255,255,255,0.18); /* å«ä¹ï¼PEST æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-political-bg: linear-gradient(90deg, rgba(142,68,173,0.25), rgba(142,68,173,0.1)), var(--pest-strip-base); /* å«ä¹ï¼PEST æ¿æ²»æ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-economic-bg: linear-gradient(90deg, rgba(22,160,133,0.25), rgba(22,160,133,0.1)), var(--pest-strip-base); /* å«ä¹ï¼PEST ç»æµæ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-social-bg: linear-gradient(90deg, rgba(232,67,147,0.25), rgba(232,67,147,0.1)), var(--pest-strip-base); /* å«ä¹ï¼PEST ç¤¾ä¼æ¡å¸¦åºè²ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-technological-bg: linear-gradient(90deg, rgba(41,128,185,0.25), rgba(41,128,185,0.1)), var(--pest-strip-base); /* å«ä¹ï¼PEST ææ¯æ¡å¸¦åºè²ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-political-border: rgba(165,105,189,0.6); /* å«ä¹ï¼PEST æ¿æ²»æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-economic-border: rgba(72,201,176,0.6); /* å«ä¹ï¼PEST ç»æµæ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-social-border: rgba(240,98,146,0.6); /* å«ä¹ï¼PEST ç¤¾ä¼æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-strip-technological-border: rgba(93,173,226,0.6); /* å«ä¹ï¼PEST ææ¯æ¡å¸¦è¾¹æ¡ï¼è®¾ç½®ï¼å¨ themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --pest-item-border: rgba(255,255,255,0.12); /* å«ä¹ï¼PEST æ¡ç®è¾¹æ¡ï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
}} /* ç»æ .dark-mode */
* {{ box-sizing: border-box; }} /* å«ä¹ï¼å¨å±ç»ä¸çæ¨¡åï¼é¿ååå¤è¾¹è·è®¡ç®è¯¯å·®ï¼è®¾ç½®ï¼éå¸¸ä¿æ border-boxï¼å¦éåçè¡ä¸ºå¯æ¹ï¿½?content-box */
body {{ /* å«ä¹ï¼å¨å±æçä¸èæ¯è®¾ç½®ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-family: {body_font}; /* å«ä¹ï¼å­ä½æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(180deg, rgba(0,0,0,0.04), rgba(0,0,0,0)) fixed, var(--bg-color); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.7; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-height: 100vh; /* å«ä¹ï¼æå°é«åº¦ï¼é²æ­¢å¡é·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: background-color 0.45s ease, color 0.45s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ body */
.report-header, main, .hero-section, .chapter, .chart-card, .callout, .engine-quote, .kpi-card, .toc, .table-wrap {{ /* å«ä¹ï¼å¸¸ç¨å®¹å¨çç»ä¸è¿æ¸¡å¨ç»ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transition: background-color 0.45s ease, color 0.45s ease, border-color 0.45s ease, box-shadow 0.45s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .report-header, main, .hero-section, .chapter, .chart-card, .callout, .engine-quote, .kpi-card, .toc, .table-wrap */
.report-header {{ /* å«ä¹ï¼é¡µçå¸é¡¶åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  position: sticky; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  top: 0; /* å«ä¹ï¼é¡¶é¨åç§»éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  z-index: 10; /* å«ä¹ï¼å±å é¡ºåºï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--card-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 20px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-bottom: 1px solid var(--border-color); /* å«ä¹ï¼åºé¨è¾¹æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 16px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 2px 6px var(--shadow-color); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .report-header */
.tagline {{ /* å«ä¹ï¼æ é¢æ è¯­è¡ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 4px 0 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.95rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .tagline */
.hero-section {{ /* å«ä¹ï¼å°é¢æè¦ä¸»å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 24px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 24px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 20px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(135deg, rgba(0,123,255,0.1), rgba(23,162,184,0.1)); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid rgba(0,0,0,0.08); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 32px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-section */
.hero-content {{ /* å«ä¹ï¼å°é¢å·¦ä¾§æå­åºï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  flex: 2; /* å«ä¹ï¼flex å ä½æ¯ä¾ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 260px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-content */
.hero-side {{ /* å«ä¹ï¼å°é¢å³ï¿½?KPI æ ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  flex: 1; /* å«ä¹ï¼flex å ä½æ¯ä¾ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 220px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: grid; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); /* å«ä¹ï¼ç½æ ¼åæ¨¡æ¿ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-side */
@media screen {{
  .hero-side {{
    margin-top: 28px; /* å«ä¹ï¼ä»å¨å±å¹æ¾ç¤ºæ¶ä¸ç§»ï¼é¿åé®æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?*/
  }}
}}
.hero-kpi {{ /* å«ä¹ï¼å°ï¿½?KPI å¡çï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: var(--card-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 14px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 6px 16px var(--shadow-color); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-kpi */
.hero-kpi .label {{ /* å«ä¹ï¿½?hero-kpi .label æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-kpi .label */
.hero-kpi .value {{ /* å«ä¹ï¿½?hero-kpi .value æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.8rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-kpi .value */
.hero-highlights {{ /* å«ä¹ï¼å°é¢äº®ç¹åè¡¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  list-style: none; /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 16px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 10px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-highlights */
.hero-highlights li {{ /* å«ä¹ï¿½?hero-highlights li æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-highlights li */
.badge {{ /* å«ä¹ï¼å¾½ç« æ ç­¾ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 6px 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 999px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.05); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .badge */
.broken-link {{ /* å«ä¹ï¼æ æé¾æ¥æç¤ºæ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-decoration: underline dotted; /* å«ä¹ï¼ææ¬è£é¥°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--primary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .broken-link */
.hero-actions {{ /* å«ä¹ï¼å°é¢æä½æé®å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-actions */
.ghost-btn {{ /* å«ä¹ï¼æ¬¡çº§æé®æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border: 1px solid var(--primary-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: transparent; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--primary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 999px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 8px 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  cursor: pointer; /* å«ä¹ï¼é¼ æ æéæ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .ghost-btn */
.hero-summary {{ /* å«ä¹ï¼å°é¢æè¦æå­ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.05rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 500; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 0; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .hero-summary */
.llm-error-block {{ /* å«ä¹ï¼LLM éè¯¯æç¤ºå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border: 1px dashed var(--secondary-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 12px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(229,62,62,0.06); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .llm-error-block */
.llm-error-block.importance-critical {{ /* å«ä¹ï¿½?llm-error-block.importance-critical æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border-color: var(--secondary-color-dark); /* å«ä¹ï¼border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(229,62,62,0.12); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .llm-error-block.importance-critical */
.llm-error-block::after {{ /* å«ä¹ï¿½?llm-error-block::after æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  content: attr(data-raw); /* å«ä¹ï¼content æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  white-space: pre-wrap; /* å«ä¹ï¼ç©ºç½ä¸æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  left: 0; /* å«ä¹ï¼left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  right: 0; /* å«ä¹ï¼right æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  bottom: 100%; /* å«ä¹ï¼bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  max-height: 240px; /* å«ä¹ï¼max-height æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: auto; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.85); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #fff; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 8px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  pointer-events: none; /* å«ä¹ï¼pointer-events æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: opacity 0.2s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  z-index: 20; /* å«ä¹ï¼å±å é¡ºåºï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .llm-error-block::after */
.llm-error-block:hover::after {{ /* å«ä¹ï¿½?llm-error-block:hover::after æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  opacity: 1; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .llm-error-block:hover::after */
.report-header h1 {{ /* å«ä¹ï¼é¡µçä¸»æ é¢ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.6rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--primary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .report-header h1 */
.report-header .subtitle {{ /* å«ä¹ï¼é¡µçå¯æ é¢ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 4px 0 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .report-header .subtitle */
.header-actions {{ /* å«ä¹ï¼é¡µçæé®ç»ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .header-actions */
theme-button {{ /* å«ä¹ï¼ä¸»é¢åæ¢ç»ä»¶ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  vertical-align: middle; /* å«ä¹ï¼vertical-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ theme-button */
.cover {{ /* å«ä¹ï¼å°é¢åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0 40px; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .cover */
.cover h1 {{ /* å«ä¹ï¿½?cover h1 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 2.4rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0.4em 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .cover h1 */
.cover-hint {{ /* å«ä¹ï¿½?cover-hint æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  letter-spacing: 0.4em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.95rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .cover-hint */
.cover-subtitle {{ /* å«ä¹ï¿½?cover-subtitle æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .cover-subtitle */
.action-btn {{ /* å«ä¹ï¼ä¸»æé®åºç¡æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --mouse-x: 50%; /* å«ä¹ï¼ä¸»é¢åï¿½?mouse-xï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --mouse-y: 50%; /* å«ä¹ï¼ä¸»é¢åï¿½?mouse-yï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  border: none; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #fff; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 11px 22px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  cursor: pointer; /* å«ä¹ï¼é¼ æ æéæ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.92rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.025em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1); /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 140px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  white-space: nowrap; /* å«ä¹ï¼ç©ºç½ä¸æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: center; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 10px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(0, 0, 0, 0.08); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: hidden; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn */
.action-btn::before {{ /* å«ä¹ï¿½?action-btn::before æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  content: ''; /* å«ä¹ï¼content æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  top: 0; /* å«ä¹ï¼é¡¶é¨åç§»éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  left: 0; /* å«ä¹ï¼left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 100%; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(to bottom, rgba(255,255,255,0.12), transparent); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: opacity 0.35s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn::before */
.action-btn::after {{ /* å«ä¹ï¿½?action-btn::after æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  content: ''; /* å«ä¹ï¼content æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  top: var(--mouse-y); /* å«ä¹ï¼é¡¶é¨åç§»éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  left: var(--mouse-x); /* å«ä¹ï¼left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 0; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 0; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, transparent 70%); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 50%; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transform: translate(-50%, -50%); /* å«ä¹ï¼transform æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: width 0.45s ease-out, height 0.45s ease-out; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  pointer-events: none; /* å«ä¹ï¼pointer-events æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn::after */
.action-btn:hover {{ /* å«ä¹ï¿½?action-btn:hover æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transform: translateY(-2px); /* å«ä¹ï¼transform æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.18), 0 4px 10px rgba(0, 0, 0, 0.1); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn:hover */
.action-btn:hover::before {{ /* å«ä¹ï¿½?action-btn:hover::before æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  opacity: 1; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn:hover::before */
.action-btn:hover::after {{ /* å«ä¹ï¿½?action-btn:hover::after æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 280%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 280%; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn:hover::after */
.action-btn:active {{ /* å«ä¹ï¿½?action-btn:active æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transform: translateY(0) scale(0.98); /* å«ä¹ï¼transform æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn:active */
.action-btn .btn-icon {{ /* å«ä¹ï¿½?action-btn .btn-icon æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 18px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 18px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-shrink: 0; /* å«ä¹ï¼flex-shrink æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  filter: drop-shadow(0 1px 1px rgba(0,0,0,0.15)); /* å«ä¹ï¼æ»¤éææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .action-btn .btn-icon */
.theme-toggle-btn .sun-icon,
.theme-toggle-btn .moon-icon {{ /* å«ä¹ï¼ä¸»é¢åæ¢æé®å¾æ æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transition: transform 0.3s ease, opacity 0.3s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .theme-toggle-btn å¾æ  */
.theme-toggle-btn .sun-icon {{ /* å«ä¹ï¼å¤ªé³å¾æ æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: #F59E0B; /* å«ä¹ï¼å¤ªé³å¾æ é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  stroke: #F59E0B; /* å«ä¹ï¼å¤ªé³å¾æ æè¾¹é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .theme-toggle-btn .sun-icon */
.theme-toggle-btn .moon-icon {{ /* å«ä¹ï¼æäº®å¾æ æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: #6366F1; /* å«ä¹ï¼æäº®å¾æ é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  stroke: #6366F1; /* å«ä¹ï¼æäº®å¾æ æè¾¹é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .theme-toggle-btn .moon-icon */
.theme-toggle-btn:hover .sun-icon {{ /* å«ä¹ï¼æ¬åæ¶å¤ªé³å¾æ ææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transform: rotate(15deg); /* å«ä¹ï¼æè½¬åæ¢ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .theme-toggle-btn:hover .sun-icon */
.theme-toggle-btn:hover .moon-icon {{ /* å«ä¹ï¼æ¬åæ¶æäº®å¾æ ææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transform: rotate(-15deg) scale(1.1); /* å«ä¹ï¼æè½¬åç¼©æ¾åæ¢ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .theme-toggle-btn:hover .moon-icon */
body.exporting {{ /* å«ä¹ï¼body.exporting æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  cursor: progress; /* å«ä¹ï¼é¼ æ æéæ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ body.exporting */
.export-overlay {{ /* å«ä¹ï¼å¯¼åºé®ç½©å±ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  position: fixed; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  inset: 0; /* å«ä¹ï¼inset æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(3, 9, 26, 0.55); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  backdrop-filter: blur(2px); /* å«ä¹ï¼èæ¯æ¨¡ç³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: center; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  pointer-events: none; /* å«ä¹ï¼pointer-events æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: opacity 0.3s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  z-index: 999; /* å«ä¹ï¼å±å é¡ºåºï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-overlay */
.export-overlay.active {{ /* å«ä¹ï¿½?export-overlay.active æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  opacity: 1; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  pointer-events: all; /* å«ä¹ï¼pointer-events æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-overlay.active */
.export-dialog {{ /* å«ä¹ï¿½?export-dialog æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: rgba(12, 19, 38, 0.92); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 24px 32px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 18px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #fff; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 280px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 16px 40px rgba(0,0,0,0.45); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-dialog */
.export-spinner {{ /* å«ä¹ï¿½?export-spinner æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 48px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 48px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 50%; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 3px solid rgba(255,255,255,0.2); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-top-color: var(--secondary-color); /* å«ä¹ï¼border-top-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0 auto 16px; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  animation: export-spin 1s linear infinite; /* å«ä¹ï¼animation æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-spinner */
.export-status {{ /* å«ä¹ï¿½?export-status æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-status */
.exporting *,
.exporting *::before, /* å«ä¹ï¿½?exporting * æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.exporting *::after {{ /* å«ä¹ï¿½?exporting *::after æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  animation: none !important; /* å«ä¹ï¼animation æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: none !important; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .exporting *::after */
.export-progress {{ /* å«ä¹ï¿½?export-progress æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 220px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 6px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(255,255,255,0.25); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 999px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: hidden; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px auto 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-progress */
.export-progress-bar {{ /* å«ä¹ï¿½?export-progress-bar æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  top: 0; /* å«ä¹ï¼é¡¶é¨åç§»éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  bottom: 0; /* å«ä¹ï¼bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 45%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: inherit; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  animation: export-progress 1.4s ease-in-out infinite; /* å«ä¹ï¼animation æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .export-progress-bar */
@keyframes export-spin {{ /* å«ä¹ï¼@keyframes export-spin æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  from {{ transform: rotate(0deg); }} /* å«ä¹ï¼å³é®å¸§èµ·ç¹ï¼ä¿ï¿½?0�° è§åº¦ï¼è®¾ç½®ï¼å¯æ¹ä¸ºå¶ä»èµ·å§æè½¬æç¼©æ¾ç¶ï¿½?*/
  to {{ transform: rotate(360deg); }} /* å«ä¹ï¼å³é®å¸§ç»ç¹ï¼æè½¬ä¸åï¼è®¾ç½®ï¼å¯æ¹ä¸ºèªå®ä¹ç»æè§ï¿½?ææ */
}} /* ç»æ @keyframes export-spin */
@keyframes export-progress {{ /* å«ä¹ï¼@keyframes export-progress æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  0% {{ left: -45%; }} /* å«ä¹ï¼è¿åº¦å¨ç»èµ·ç¹ï¼æ¡å½¢ä»å·¦ä¾§ä¹å¤è¿å¥ï¼è®¾ç½®ï¼è°æ´èµ·ï¿½?left ç¾åï¿½?*/
  50% {{ left: 20%; }} /* å«ä¹ï¼è¿åº¦å¨ç»ä¸­ç¹ï¼æ¡å½¢ä½äºå®¹å¨ä¸­æ®µï¼è®¾ç½®ï¼æéè°æ´åç§»æ¯ä¾ */
  100% {{ left: 110%; }} /* å«ä¹ï¼è¿åº¦å¨ç»ç»ç¹ï¼æ¡å½¢æ»åºå³ä¾§ï¼è®¾ç½®ï¼è°æ´æ¶å°¾ left ç¾åï¿½?*/
}} /* ç»æ @keyframes export-progress */
main {{ /* å«ä¹ï¼ä¸»ä½åå®¹å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  max-width: {container_width}; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 40px auto; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: {gutter}; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--card-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 16px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 10px 30px var(--shadow-color); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ main */
h1, h2, h3, h4, h5, h6 {{ /* å«ä¹ï¼æ é¢éç¨æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-family: {heading_font}; /* å«ä¹ï¼å­ä½æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 2em; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 0.6em; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.35; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ h1, h2, h3, h4, h5, h6 */
h2 {{ /* å«ä¹ï¼h2 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ h2 */
h3 {{ /* å«ä¹ï¼h3 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.4rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ h3 */
h4 {{ /* å«ä¹ï¼h4 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.2rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ h4 */
p {{ /* å«ä¹ï¼æ®µè½æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 1em 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: justify; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ p */
ul, ol {{ /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-left: 1.5em; /* å«ä¹ï¼margin-left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding-left: 0; /* å«ä¹ï¼å·¦ä¾§åè¾¹è·/ç¼©è¿ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ ul, ol */
img, canvas, svg {{ /* å«ä¹ï¼åªä½åç´ å°ºå¯¸éå¶ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: auto; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ img, canvas, svg */
.meta-card {{ /* å«ä¹ï¼åä¿¡æ¯å¡çï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: rgba(0,0,0,0.02); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 20px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .meta-card */
.meta-card ul {{ /* å«ä¹ï¿½?meta-card ul æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  list-style: none; /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .meta-card ul */
.meta-card li {{ /* å«ä¹ï¿½?meta-card li æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-bottom: 1px dashed var(--border-color); /* å«ä¹ï¼åºé¨è¾¹æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 8px 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .meta-card li */
.toc {{ /* å«ä¹ï¼ç®å½å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 30px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 20px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.01); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc */
.toc-title {{ /* å«ä¹ï¿½?toc-title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 10px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc-title */
.toc ul {{ /* å«ä¹ï¿½?toc ul æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  list-style: none; /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc ul */
.toc li {{ /* å«ä¹ï¿½?toc li æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 4px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc li */
.toc li.level-1 {{ /* å«ä¹ï¿½?toc li.level-1 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.05rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 12px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc li.level-1 */
.toc li.level-2 {{ /* å«ä¹ï¿½?toc li.level-2 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-left: 12px; /* å«ä¹ï¼margin-left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc li.level-2 */
.toc li a {{ /* å«ä¹ï¿½?toc li a æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: var(--primary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-decoration: none; /* å«ä¹ï¼ææ¬è£é¥°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc li a */
.toc li.level-3 {{ /* å«ä¹ï¿½?toc li.level-3 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-left: 16px; /* å«ä¹ï¼margin-left æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.95em; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc li.level-3 */
.toc-desc {{ /* å«ä¹ï¿½?toc-desc æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 2px 0 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc-desc */
.toc-desc {{ /* å«ä¹ï¿½?toc-desc æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 2px 0 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .toc-desc */
.chapter {{ /* å«ä¹ï¼ç« èå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 40px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding-top: 32px; /* å«ä¹ï¼padding-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-top: 1px solid rgba(0,0,0,0.05); /* å«ä¹ï¼border-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chapter */
.chapter:first-of-type {{ /* å«ä¹ï¿½?chapter:first-of-type æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border-top: none; /* å«ä¹ï¼border-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding-top: 0; /* å«ä¹ï¼padding-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chapter:first-of-type */
blockquote {{ /* å«ä¹ï¼å¼ç¨å - PDFåºç¡æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 12px 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.04); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 8px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-left: none; /* å«ä¹ï¼ç§»é¤å·¦ä¾§è²æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ blockquote */
/* ==================== Blockquote æ¶²æç»çæï¿½?- ä»å±å¹æ¾ï¿½?==================== */
@media screen {{
  blockquote {{ /* å«ä¹ï¼å¼ç¨åæ¶²æç»ï¿½?- éææ¬æµ®è®¾è®¡ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·å¢å æ¬æµ®ç©ºé´ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    padding: 18px 22px; /* å«ä¹ï¼åè¾¹è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border: none; /* å«ä¹ï¼ç§»é¤é»è®¤è¾¹æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border-radius: 20px; /* å«ä¹ï¼å¤§åè§å¢å¼ºæ¶²ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0.05) 100%); /* å«ä¹ï¼ææ·¡éææ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    backdrop-filter: blur(24px) saturate(180%); /* å«ä¹ï¼å¼ºèæ¯æ¨¡ç³å®ç°ç»çéè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    -webkit-backdrop-filter: blur(24px) saturate(180%); /* å«ä¹ï¼Safari èæ¯æ¨¡ç³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 8px 32px rgba(0, 0, 0, 0.12),
      0 2px 8px rgba(0, 0, 0, 0.06),
      inset 0 0 0 1px rgba(255, 255, 255, 0.2),
      inset 0 2px 4px rgba(255, 255, 255, 0.15); /* å«ä¹ï¼å¤å±é´å½±è¥é æ¬æµ®æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    transform: translateY(0); /* å«ä¹ï¼åå§ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.4s ease; /* å«ä¹ï¼å¼¹æ§è¿æ¸¡å¨ç»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    overflow: visible; /* å«ä¹ï¼åè®¸åææº¢åºï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    isolation: isolate; /* å«ä¹ï¼åå»ºå±å ä¸ä¸æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ blockquote æ¶²æç»çåºç¡ */
  blockquote:hover {{ /* å«ä¹ï¼æ¬åæ¶å¢å¼ºæ¬æµ®ææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    transform: translateY(-3px); /* å«ä¹ï¼ä¸æµ®ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 16px 48px rgba(0, 0, 0, 0.15),
      0 4px 16px rgba(0, 0, 0, 0.08),
      inset 0 0 0 1px rgba(255, 255, 255, 0.25),
      inset 0 2px 6px rgba(255, 255, 255, 0.2); /* å«ä¹ï¼å¢å¼ºé´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ blockquote:hover */
  blockquote::after {{ /* å«ä¹ï¼é¡¶é¨é«ååå°ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    content: ''; /* å«ä¹ï¼ä¼ªåç´ åå®¹ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    top: 0; /* å«ä¹ï¼é¡¶é¨ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    left: 0; /* å«ä¹ï¼å·¦è¾¹ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    right: 0; /* å«ä¹ï¼å³è¾¹ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    height: 50%; /* å«ä¹ï¼è¦çä¸åé¨åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 100%); /* å«ä¹ï¼é¡¶é¨é«åæ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border-radius: 20px 20px 0 0; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    pointer-events: none; /* å«ä¹ï¼ä¸ååºé¼ æ ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    z-index: -1; /* å«ä¹ï¼ç½®äºåå®¹ä¸æ¹ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ blockquote::after */
  /* æè²æ¨¡å¼ blockquote æ¶²æç»ï¿½?*/
  .dark-mode blockquote {{ /* å«ä¹ï¼æè²æ¨¡å¼å¼ç¨åæ¶²æç»çï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    background: linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%); /* å«ä¹ï¼æè²éææ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 8px 32px rgba(0, 0, 0, 0.4),
      0 2px 8px rgba(0, 0, 0, 0.2),
      inset 0 0 0 1px rgba(255, 255, 255, 0.1),
      inset 0 2px 4px rgba(255, 255, 255, 0.05); /* å«ä¹ï¼æè²é´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode blockquote */
  .dark-mode blockquote:hover {{ /* å«ä¹ï¼æè²æ¬åææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    box-shadow: 
      0 20px 56px rgba(0, 0, 0, 0.5),
      0 6px 20px rgba(0, 0, 0, 0.25),
      inset 0 0 0 1px rgba(255, 255, 255, 0.15),
      inset 0 2px 6px rgba(255, 255, 255, 0.08); /* å«ä¹ï¼æè²å¢å¼ºé´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode blockquote:hover */
  .dark-mode blockquote::after {{ /* å«ä¹ï¼æè²é¡¶é¨é«åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    background: linear-gradient(180deg, rgba(255,255,255,0.06) 0%, transparent 100%); /* å«ä¹ï¼æè²é«åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode blockquote::after */
}} /* ç»æ @media screen blockquote æ¶²æç»ï¿½?*/
.engine-quote {{ /* å«ä¹ï¼å¼æåè¨åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --engine-quote-bg: var(--engine-insight-bg); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-bgï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-border: var(--engine-insight-border); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-borderï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-text: var(--engine-insight-text); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-textï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  margin: 22px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 16px 18px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 14px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--engine-quote-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--engine-quote-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: var(--engine-quote-shadow); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.65; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .engine-quote */
.engine-quote__header {{ /* å«ä¹ï¿½?engine-quote__header æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 10px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 650; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--engine-quote-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 8px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.02em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .engine-quote__header */
.engine-quote__dot {{ /* å«ä¹ï¿½?engine-quote__dot æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 10px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 10px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 50%; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--engine-quote-text); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 0 0 8px rgba(0,0,0,0.02); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .engine-quote__dot */
.engine-quote__title {{ /* å«ä¹ï¿½?engine-quote__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 0.98rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .engine-quote__title */
.engine-quote__body > *:first-child {{ margin-top: 0; }} /* å«ä¹ï¿½?engine-quote__body > * æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.engine-quote__body > *:last-child {{ margin-bottom: 0; }} /* å«ä¹ï¿½?engine-quote__body > * æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.engine-quote.engine-media {{ /* å«ä¹ï¿½?engine-quote.engine-media æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --engine-quote-bg: var(--engine-media-bg); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-bgï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-border: var(--engine-media-border); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-borderï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-text: var(--engine-media-text); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-textï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
}} /* ç»æ .engine-quote.engine-media */
.engine-quote.engine-query {{ /* å«ä¹ï¿½?engine-quote.engine-query æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  --engine-quote-bg: var(--engine-query-bg); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-bgï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-border: var(--engine-query-border); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-borderï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
  --engine-quote-text: var(--engine-query-text); /* å«ä¹ï¼ä¸»é¢åï¿½?engine-quote-textï¼è®¾ç½®ï¼ï¿½?themeTokens ä¸­è¦çææ¹æ­¤é»è®¤ï¿½?*/
}} /* ç»æ .engine-quote.engine-query */
.table-wrap {{ /* å«ä¹ï¼è¡¨æ ¼æ»å¨å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  overflow-x: auto; /* å«ä¹ï¼æ¨ªåæº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .table-wrap */
table {{ /* å«ä¹ï¼è¡¨æ ¼åºç¡æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-collapse: collapse; /* å«ä¹ï¼border-collapse æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ table */
table th, table td {{ /* å«ä¹ï¼è¡¨æ ¼ååæ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ table th, table td */
table th {{ /* å«ä¹ï¼table th æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: rgba(0,0,0,0.03); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ table th */
.align-center {{ text-align: center; }} /* å«ä¹ï¿½?align-center  text-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.align-right {{ text-align: right; }} /* å«ä¹ï¿½?align-right  text-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-card {{ /* å«ä¹ï¼SWOT å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 26px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 18px 18px 14px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 16px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-card-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--swot-card-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: var(--swot-card-shadow); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  backdrop-filter: var(--swot-card-blur); /* å«ä¹ï¼èæ¯æ¨¡ç³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: hidden; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-card */
.swot-card__head {{ /* å«ä¹ï¿½?swot-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 16px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-card__head */
.swot-card__title {{ /* å«ä¹ï¿½?swot-card__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.15rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 750; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 4px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-card__title */
.swot-card__summary {{ /* å«ä¹ï¿½?swot-card__summary æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.82; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-card__summary */
.swot-legend {{ /* å«ä¹ï¿½?swot-legend æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-legend */
.swot-legend__item {{ /* å«ä¹ï¿½?swot-legend__item æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 6px 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 999px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-on-dark); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-tag-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 4px 12px rgba(0,0,0,0.16); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-shadow: 0 1px 2px rgba(0,0,0,0.35); /* å«ä¹ï¼æå­é´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-legend__item */
.swot-legend__item.strength {{ background: var(--swot-strength); }} /* å«ä¹ï¿½?swot-legend__item.strength  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-legend__item.weakness {{ background: var(--swot-weakness); }} /* å«ä¹ï¿½?swot-legend__item.weakness  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-legend__item.opportunity {{ background: var(--swot-opportunity); }} /* å«ä¹ï¿½?swot-legend__item.opportunity  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-legend__item.threat {{ background: var(--swot-threat); }} /* å«ä¹ï¿½?swot-legend__item.threat  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-grid {{ /* å«ä¹ï¼SWOT è±¡éç½æ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: grid; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); /* å«ä¹ï¼ç½æ ¼åæ¨¡æ¿ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 14px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-grid */
.swot-cell {{ /* å«ä¹ï¼SWOT è±¡éååæ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border-radius: 14px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-cell-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px 12px 10px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--swot-cell-base); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.4); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-cell */
.swot-cell.strength {{ border-color: var(--swot-cell-strength-border); background: var(--swot-cell-strength-bg); }} /* å«ä¹ï¿½?swot-cell.strength  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-cell.weakness {{ border-color: var(--swot-cell-weakness-border); background: var(--swot-cell-weakness-bg); }} /* å«ä¹ï¿½?swot-cell.weakness  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-cell.opportunity {{ border-color: var(--swot-cell-opportunity-border); background: var(--swot-cell-opportunity-bg); }} /* å«ä¹ï¿½?swot-cell.opportunity  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-cell.threat {{ border-color: var(--swot-cell-threat-border); background: var(--swot-cell-threat-bg); }} /* å«ä¹ï¿½?swot-cell.threat  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-cell__meta {{ /* å«ä¹ï¿½?swot-cell__meta æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 10px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 8px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-cell__meta */
.swot-pill {{ /* å«ä¹ï¿½?swot-pill æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: center; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 36px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 36px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 800; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-on-dark); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-tag-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 8px 20px rgba(0,0,0,0.18); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pill */
.swot-pill.strength {{ background: var(--swot-strength); }} /* å«ä¹ï¿½?swot-pill.strength  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pill.weakness {{ background: var(--swot-weakness); }} /* å«ä¹ï¿½?swot-pill.weakness  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pill.opportunity {{ background: var(--swot-opportunity); }} /* å«ä¹ï¿½?swot-pill.opportunity  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pill.threat {{ background: var(--swot-threat); }} /* å«ä¹ï¿½?swot-pill.threat  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-cell__title {{ /* å«ä¹ï¿½?swot-cell__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 750; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.01em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-cell__title */
.swot-cell__caption {{ /* å«ä¹ï¿½?swot-cell__caption æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.7; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-cell__caption */
.swot-list {{ /* å«ä¹ï¼SWOT æ¡ç®åè¡¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  list-style: none; /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-direction: column; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-list */
.swot-item {{ /* å«ä¹ï¼SWOT æ¡ç®ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 10px 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--swot-surface); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-item-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 12px 22px rgba(0,0,0,0.08); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-item */
.swot-item-title {{ /* å«ä¹ï¿½?swot-item-title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 650; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-item-title */
.swot-item-tags {{ /* å«ä¹ï¿½?swot-item-tags æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 6px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-item-tags */
.swot-tag {{ /* å«ä¹ï¿½?swot-tag æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 4px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--swot-chip-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--swot-tag-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 6px 14px rgba(0,0,0,0.12); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.2; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-tag */
.swot-tag.neutral {{ /* å«ä¹ï¿½?swot-tag.neutral æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  opacity: 0.9; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-tag.neutral */
.swot-item-desc {{ /* å«ä¹ï¿½?swot-item-desc æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 4px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.92; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-item-desc */
.swot-item-evidence {{ /* å«ä¹ï¿½?swot-item-evidence æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 4px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.94; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-item-evidence */
.swot-empty {{ /* å«ä¹ï¿½?swot-empty æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px dashed var(--swot-card-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--swot-muted); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.7; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-empty */

/* ========== SWOT PDFè¡¨æ ¼å¸å±æ ·å¼ï¼é»è®¤éèï¼========== */
.swot-pdf-wrapper {{ /* å«ä¹ï¼SWOT PDF è¡¨æ ¼å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: none; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-wrapper */

/* SWOT PDFè¡¨æ ¼æ ·å¼å®ä¹ï¼ç¨äºPDFæ¸²ææ¶æ¾ç¤ºï¼ */
.swot-pdf-table {{ /* å«ä¹ï¿½?swot-pdf-table æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-collapse: collapse; /* å«ä¹ï¼border-collapse æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 13px; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  table-layout: fixed; /* å«ä¹ï¼è¡¨æ ¼å¸å±ç®æ³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-table */
.swot-pdf-caption {{ /* å«ä¹ï¿½?swot-pdf-caption æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  caption-side: top; /* å«ä¹ï¼caption-side æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: left; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.15rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-caption */
.swot-pdf-thead th {{ /* å«ä¹ï¿½?swot-pdf-thead th æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: #f8f9fa; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 10px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: left; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #dee2e6; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #495057; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-thead th */
.swot-pdf-th-quadrant {{ width: 80px; }} /* å«ä¹ï¿½?swot-pdf-th-quadrant  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-th-num {{ width: 50px; text-align: center; }} /* å«ä¹ï¿½?swot-pdf-th-num  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-th-title {{ width: 22%; }} /* å«ä¹ï¿½?swot-pdf-th-title  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-th-detail {{ width: auto; }} /* å«ä¹ï¿½?swot-pdf-th-detail  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-th-tags {{ width: 100px; text-align: center; }} /* å«ä¹ï¿½?swot-pdf-th-tags  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-summary {{ /* å«ä¹ï¿½?swot-pdf-summary æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: #f8f9fa; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #666; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-style: italic; /* å«ä¹ï¼font-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #dee2e6; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-summary */
.swot-pdf-quadrant {{ /* å«ä¹ï¿½?swot-pdf-quadrant æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-quadrant */
.swot-pdf-quadrant-label {{ /* å«ä¹ï¿½?swot-pdf-quadrant-label æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  vertical-align: middle; /* å«ä¹ï¼vertical-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #dee2e6; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  writing-mode: horizontal-tb; /* å«ä¹ï¼writing-mode æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-quadrant-label */
.swot-pdf-quadrant-label.swot-pdf-strength {{ background: rgba(28,127,110,0.15); color: #1c7f6e; border-left: 4px solid #1c7f6e; }} /* å«ä¹ï¿½?swot-pdf-quadrant-label.swot-pdf-strength  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-quadrant-label.swot-pdf-weakness {{ background: rgba(192,57,43,0.12); color: #c0392b; border-left: 4px solid #c0392b; }} /* å«ä¹ï¿½?swot-pdf-quadrant-label.swot-pdf-weakness  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-quadrant-label.swot-pdf-opportunity {{ background: rgba(31,90,179,0.12); color: #1f5ab3; border-left: 4px solid #1f5ab3; }} /* å«ä¹ï¿½?swot-pdf-quadrant-label.swot-pdf-opportunity  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-quadrant-label.swot-pdf-threat {{ background: rgba(179,107,22,0.12); color: #b36b16; border-left: 4px solid #b36b16; }} /* å«ä¹ï¿½?swot-pdf-quadrant-label.swot-pdf-threat  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-code {{ /* å«ä¹ï¿½?swot-pdf-code æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.5rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 800; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 4px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-code */
.swot-pdf-label-text {{ /* å«ä¹ï¿½?swot-pdf-label-text æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.75rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.02em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-label-text */
.swot-pdf-item-row td {{ /* å«ä¹ï¿½?swot-pdf-item-row td æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 10px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #dee2e6; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  vertical-align: top; /* å«ä¹ï¼vertical-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-item-row td */
.swot-pdf-item-row.swot-pdf-strength td {{ background: rgba(28,127,110,0.03); }} /* å«ä¹ï¿½?swot-pdf-item-row.swot-pdf-strength td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-item-row.swot-pdf-weakness td {{ background: rgba(192,57,43,0.03); }} /* å«ä¹ï¿½?swot-pdf-item-row.swot-pdf-weakness td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-item-row.swot-pdf-opportunity td {{ background: rgba(31,90,179,0.03); }} /* å«ä¹ï¿½?swot-pdf-item-row.swot-pdf-opportunity td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-item-row.swot-pdf-threat td {{ background: rgba(179,107,22,0.03); }} /* å«ä¹ï¿½?swot-pdf-item-row.swot-pdf-threat td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.swot-pdf-item-num {{ /* å«ä¹ï¿½?swot-pdf-item-num æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #6c757d; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-item-num */
.swot-pdf-item-title {{ /* å«ä¹ï¿½?swot-pdf-item-title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #212529; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-item-title */
.swot-pdf-item-detail {{ /* å«ä¹ï¿½?swot-pdf-item-detail æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: #495057; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.5; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-item-detail */
.swot-pdf-item-tags {{ /* å«ä¹ï¿½?swot-pdf-item-tags æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-item-tags */
.swot-pdf-tag {{ /* å«ä¹ï¿½?swot-pdf-tag æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 3px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 4px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.75rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: #e9ecef; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #495057; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 2px; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-tag */
.swot-pdf-tag--score {{ /* å«ä¹ï¿½?swot-pdf-tag--score æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: #fff3cd; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #856404; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-tag--score */
.swot-pdf-empty {{ /* å«ä¹ï¿½?swot-pdf-empty æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #adb5bd; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-style: italic; /* å«ä¹ï¼font-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .swot-pdf-empty */

/* æå°æ¨¡å¼ä¸çSWOTåé¡µæ§å¶ï¼ä¿çå¡çå¸å±çæå°æ¯æï¼ */
@media print {{ /* å«ä¹ï¼æå°æ¨¡å¼æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  .swot-card {{ /* å«ä¹ï¼SWOT å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: auto; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-card */
  .swot-card__head {{ /* å«ä¹ï¿½?swot-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-after: avoid; /* å«ä¹ï¼break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-after: avoid; /* å«ä¹ï¼page-break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-card__head */
  .swot-pdf-quadrant {{ /* å«ä¹ï¿½?swot-pdf-quadrant æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-pdf-quadrant */
}} /* ç»æ @media print */

/* ==================== PEST åææ ·å¼ ==================== */
.pest-card {{ /* å«ä¹ï¼PEST å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 28px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 20px 20px 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 18px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--pest-card-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--pest-card-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: var(--pest-card-shadow); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  backdrop-filter: var(--pest-card-blur); /* å«ä¹ï¼èæ¯æ¨¡ç³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: hidden; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-card */
.pest-card__head {{ /* å«ä¹ï¿½?pest-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 16px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 16px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-card__head */
.pest-card__title {{ /* å«ä¹ï¿½?pest-card__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.18rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 750; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 4px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(135deg, var(--pest-political), var(--pest-technological)); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  -webkit-background-clip: text; /* å«ä¹ï¿½?webkit-background-clip æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  -webkit-text-fill-color: transparent; /* å«ä¹ï¿½?webkit-text-fill-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background-clip: text; /* å«ä¹ï¼background-clip æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-card__title */
.pest-card__summary {{ /* å«ä¹ï¿½?pest-card__summary æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.8; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-card__summary */
.pest-legend {{ /* å«ä¹ï¿½?pest-legend æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-legend */
.pest-legend__item {{ /* å«ä¹ï¿½?pest-legend__item æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 6px 14px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 8px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-on-dark); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--pest-tag-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 4px 14px rgba(0,0,0,0.18); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-shadow: 0 1px 2px rgba(0,0,0,0.3); /* å«ä¹ï¼æå­é´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-legend__item */
.pest-legend__item.political {{ background: var(--pest-political); }} /* å«ä¹ï¿½?pest-legend__item.political  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-legend__item.economic {{ background: var(--pest-economic); }} /* å«ä¹ï¿½?pest-legend__item.economic  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-legend__item.social {{ background: var(--pest-social); }} /* å«ä¹ï¿½?pest-legend__item.social  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-legend__item.technological {{ background: var(--pest-technological); }} /* å«ä¹ï¿½?pest-legend__item.technological  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strips {{ /* å«ä¹ï¼PEST æ¡å¸¦å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-direction: column; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 14px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strips */
.pest-strip {{ /* å«ä¹ï¼PEST æ¡å¸¦ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 14px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--pest-strip-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--pest-strip-base); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow: hidden; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 6px 16px rgba(0,0,0,0.06); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  transition: transform 0.2s ease, box-shadow 0.2s ease; /* å«ä¹ï¼è¿æ¸¡å¨ç»æ¶ï¿½?å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip */
.pest-strip:hover {{ /* å«ä¹ï¿½?pest-strip:hover æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  transform: translateY(-2px); /* å«ä¹ï¼transform æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 10px 24px rgba(0,0,0,0.1); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip:hover */
.pest-strip.political {{ border-color: var(--pest-strip-political-border); background: var(--pest-strip-political-bg); }} /* å«ä¹ï¿½?pest-strip.political  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip.economic {{ border-color: var(--pest-strip-economic-border); background: var(--pest-strip-economic-bg); }} /* å«ä¹ï¿½?pest-strip.economic  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip.social {{ border-color: var(--pest-strip-social-border); background: var(--pest-strip-social-bg); }} /* å«ä¹ï¿½?pest-strip.social  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip.technological {{ border-color: var(--pest-strip-technological-border); background: var(--pest-strip-technological-bg); }} /* å«ä¹ï¿½?pest-strip.technological  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip__indicator {{ /* å«ä¹ï¿½?pest-strip__indicator æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: center; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 56px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 56px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 16px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-on-dark); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-shadow: 0 2px 4px rgba(0,0,0,0.25); /* å«ä¹ï¼æå­é´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip__indicator */
.pest-strip__indicator.political {{ background: linear-gradient(180deg, var(--pest-political), rgba(142,68,173,0.8)); }} /* å«ä¹ï¿½?pest-strip__indicator.political  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip__indicator.economic {{ background: linear-gradient(180deg, var(--pest-economic), rgba(22,160,133,0.8)); }} /* å«ä¹ï¿½?pest-strip__indicator.economic  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip__indicator.social {{ background: linear-gradient(180deg, var(--pest-social), rgba(232,67,147,0.8)); }} /* å«ä¹ï¿½?pest-strip__indicator.social  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-strip__indicator.technological {{ background: linear-gradient(180deg, var(--pest-technological), rgba(41,128,185,0.8)); }} /* å«ä¹ï¿½?pest-strip__indicator.technological  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-code {{ /* å«ä¹ï¿½?pest-code æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 1.6rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 900; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.02em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-code */
.pest-strip__content {{ /* å«ä¹ï¿½?pest-strip__content æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  flex: 1; /* å«ä¹ï¼flex å ä½æ¯ä¾ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 14px 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-width: 0; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip__content */
.pest-strip__header {{ /* å«ä¹ï¿½?pest-strip__header æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: baseline; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 10px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip__header */
.pest-strip__title {{ /* å«ä¹ï¿½?pest-strip__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip__title */
.pest-strip__caption {{ /* å«ä¹ï¿½?pest-strip__caption æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.65; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-strip__caption */
.pest-list {{ /* å«ä¹ï¼PEST æ¡ç®åè¡¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  list-style: none; /* å«ä¹ï¼åè¡¨æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-direction: column; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-list */
.pest-item {{ /* å«ä¹ï¼PEST æ¡ç®ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 10px 14px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--pest-surface); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--pest-item-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 8px 18px rgba(0,0,0,0.06); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-item */
.pest-item-title {{ /* å«ä¹ï¿½?pest-item-title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: space-between; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 650; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-item-title */
.pest-item-tags {{ /* å«ä¹ï¿½?pest-item-tags æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 6px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.82rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-item-tags */
.pest-tag {{ /* å«ä¹ï¿½?pest-tag æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 3px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 6px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: var(--pest-chip-bg); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--pest-tag-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 4px 10px rgba(0,0,0,0.08); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.2; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-tag */
.pest-item-desc {{ /* å«ä¹ï¿½?pest-item-desc æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 5px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.88; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.95rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-item-desc */
.pest-item-source {{ /* å«ä¹ï¿½?pest-item-source æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 4px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.88rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.9; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-item-source */
.pest-empty {{ /* å«ä¹ï¿½?pest-empty æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 14px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px dashed var(--pest-card-border); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--pest-muted); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  opacity: 0.65; /* å«ä¹ï¼éæåº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-empty */

/* ========== PEST PDFè¡¨æ ¼å¸å±æ ·å¼ï¼é»è®¤éèï¼========== */
.pest-pdf-wrapper {{ /* å«ä¹ï¼PEST PDF å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: none; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-wrapper */

/* PEST PDFè¡¨æ ¼æ ·å¼å®ä¹ï¼ç¨äºPDFæ¸²ææ¶æ¾ç¤ºï¼ */
.pest-pdf-table {{ /* å«ä¹ï¿½?pest-pdf-table æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-collapse: collapse; /* å«ä¹ï¼border-collapse æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 13px; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  table-layout: fixed; /* å«ä¹ï¼è¡¨æ ¼å¸å±ç®æ³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-table */
.pest-pdf-caption {{ /* å«ä¹ï¿½?pest-pdf-caption æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  caption-side: top; /* å«ä¹ï¼caption-side æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: left; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.15rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px 0; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-caption */
.pest-pdf-thead th {{ /* å«ä¹ï¿½?pest-pdf-thead th æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: #f5f3f7; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 10px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: left; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #e0dce3; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #4a4458; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-thead th */
.pest-pdf-th-dimension {{ width: 85px; }} /* å«ä¹ï¿½?pest-pdf-th-dimension  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-th-num {{ width: 50px; text-align: center; }} /* å«ä¹ï¿½?pest-pdf-th-num  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-th-title {{ width: 22%; }} /* å«ä¹ï¿½?pest-pdf-th-title  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-th-detail {{ width: auto; }} /* å«ä¹ï¿½?pest-pdf-th-detail  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-th-tags {{ width: 100px; text-align: center; }} /* å«ä¹ï¿½?pest-pdf-th-tags  width æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-summary {{ /* å«ä¹ï¿½?pest-pdf-summary æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: #f8f6fa; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #666; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-style: italic; /* å«ä¹ï¼font-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #e0dce3; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-summary */
.pest-pdf-dimension {{ /* å«ä¹ï¿½?pest-pdf-dimension æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-dimension */
.pest-pdf-dimension-label {{ /* å«ä¹ï¿½?pest-pdf-dimension-label æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  vertical-align: middle; /* å«ä¹ï¼vertical-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 12px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #e0dce3; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  writing-mode: horizontal-tb; /* å«ä¹ï¼writing-mode æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-dimension-label */
.pest-pdf-dimension-label.pest-pdf-political {{ background: rgba(142,68,173,0.12); color: #8e44ad; border-left: 4px solid #8e44ad; }} /* å«ä¹ï¿½?pest-pdf-dimension-label.pest-pdf-political  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-dimension-label.pest-pdf-economic {{ background: rgba(22,160,133,0.12); color: #16a085; border-left: 4px solid #16a085; }} /* å«ä¹ï¿½?pest-pdf-dimension-label.pest-pdf-economic  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-dimension-label.pest-pdf-social {{ background: rgba(232,67,147,0.12); color: #e84393; border-left: 4px solid #e84393; }} /* å«ä¹ï¿½?pest-pdf-dimension-label.pest-pdf-social  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-dimension-label.pest-pdf-technological {{ background: rgba(41,128,185,0.12); color: #2980b9; border-left: 4px solid #2980b9; }} /* å«ä¹ï¿½?pest-pdf-dimension-label.pest-pdf-technological  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-code {{ /* å«ä¹ï¿½?pest-pdf-code æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.5rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 800; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-bottom: 4px; /* å«ä¹ï¼margin-bottom æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-code */
.pest-pdf-label-text {{ /* å«ä¹ï¿½?pest-pdf-label-text æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.75rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  letter-spacing: 0.02em; /* å«ä¹ï¼å­é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-label-text */
.pest-pdf-item-row td {{ /* å«ä¹ï¿½?pest-pdf-item-row td æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 10px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid #e0dce3; /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  vertical-align: top; /* å«ä¹ï¼vertical-align æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-item-row td */
.pest-pdf-item-row.pest-pdf-political td {{ background: rgba(142,68,173,0.03); }} /* å«ä¹ï¿½?pest-pdf-item-row.pest-pdf-political td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-item-row.pest-pdf-economic td {{ background: rgba(22,160,133,0.03); }} /* å«ä¹ï¿½?pest-pdf-item-row.pest-pdf-economic td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-item-row.pest-pdf-social td {{ background: rgba(232,67,147,0.03); }} /* å«ä¹ï¿½?pest-pdf-item-row.pest-pdf-social td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-item-row.pest-pdf-technological td {{ background: rgba(41,128,185,0.03); }} /* å«ä¹ï¿½?pest-pdf-item-row.pest-pdf-technological td  background æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.pest-pdf-item-num {{ /* å«ä¹ï¿½?pest-pdf-item-num æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #6c757d; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-item-num */
.pest-pdf-item-title {{ /* å«ä¹ï¿½?pest-pdf-item-title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #212529; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-item-title */
.pest-pdf-item-detail {{ /* å«ä¹ï¿½?pest-pdf-item-detail æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: #495057; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.5; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-item-detail */
.pest-pdf-item-tags {{ /* å«ä¹ï¿½?pest-pdf-item-tags æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-item-tags */
.pest-pdf-tag {{ /* å«ä¹ï¿½?pest-pdf-tag æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 3px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 4px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.75rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: #ece9f1; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #5a4f6a; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 2px; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-tag */
.pest-pdf-empty {{ /* å«ä¹ï¿½?pest-pdf-empty æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #adb5bd; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-style: italic; /* å«ä¹ï¼font-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .pest-pdf-empty */

/* æå°æ¨¡å¼ä¸çPESTåé¡µæ§å¶ */
@media print {{ /* å«ä¹ï¼æå°æ¨¡å¼æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  .pest-card {{ /* å«ä¹ï¼PEST å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: auto; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-card */
  .pest-card__head {{ /* å«ä¹ï¿½?pest-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-after: avoid; /* å«ä¹ï¼break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-after: avoid; /* å«ä¹ï¼page-break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-card__head */
  .pest-pdf-dimension {{ /* å«ä¹ï¿½?pest-pdf-dimension æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-pdf-dimension */
  .pest-strip {{ /* å«ä¹ï¼PEST æ¡å¸¦ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-strip */
}} /* ç»æ @media print */
.callout {{ /* å«ä¹ï¼é«äº®æç¤ºæ¡ - PDFåºç¡æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 8px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.02); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-left: none; /* å«ä¹ï¼ç§»é¤å·¦ä¾§è²æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .callout */
.callout.tone-warning {{ border-color: #ff9800; }} /* å«ä¹ï¿½?callout.tone-warning  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.callout.tone-success {{ border-color: #2ecc71; }} /* å«ä¹ï¿½?callout.tone-success  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.callout.tone-danger {{ border-color: #e74c3c; }} /* å«ä¹ï¿½?callout.tone-danger  border-color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
/* ==================== Callout æ¶²æç»çæï¿½?- ä»å±å¹æ¾ï¿½?==================== */
@media screen {{
  .callout {{ /* å«ä¹ï¼é«äº®æç¤ºæ¡æ¶²æç»ï¿½?- éææ¬æµ®è®¾è®¡ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-accent: var(--primary-color); /* å«ä¹ï¼callout ä¸»è²è°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    --callout-glow-color: rgba(0, 123, 255, 0.35); /* å«ä¹ï¼callout ååè²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    margin: 24px 0; /* å«ä¹ï¼å¢å å¤è¾¹è·å¼ºåæ¬æµ®æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    padding: 20px 24px; /* å«ä¹ï¼åè¾¹è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border: none; /* å«ä¹ï¼ç§»é¤é»è®¤è¾¹æ¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border-radius: 24px; /* å«ä¹ï¼å¤§åè§å¢å¼ºæ¶²ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    background: linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.04) 100%); /* å«ä¹ï¼ææ·¡éææ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    backdrop-filter: blur(28px) saturate(200%); /* å«ä¹ï¼å¼ºèæ¯æ¨¡ç³å®ç°ç»çéè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    -webkit-backdrop-filter: blur(28px) saturate(200%); /* å«ä¹ï¼Safari èæ¯æ¨¡ç³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 12px 40px rgba(0, 0, 0, 0.1),
      0 4px 12px rgba(0, 0, 0, 0.05),
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.18),
      inset 0 2px 6px rgba(255, 255, 255, 0.12); /* å«ä¹ï¼å¤å±é´å½±è¥é æ¬æµ®æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    transform: translateY(0); /* å«ä¹ï¼åå§ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    transition: transform 0.45s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.45s ease; /* å«ä¹ï¼å¼¹æ§è¿æ¸¡å¨ç»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    overflow: hidden; /* å«ä¹ï¼éèæº¢åºåå®¹ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    isolation: isolate; /* å«ä¹ï¼åå»ºå±å ä¸ä¸æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout æ¶²æç»çåºç¡ */
  .callout:hover {{ /* å«ä¹ï¼æ¬åæ¶å¢å¼ºæ¬æµ®ææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    transform: translateY(-4px); /* å«ä¹ï¼ä¸æµ®ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 20px 56px rgba(0, 0, 0, 0.12),
      0 8px 20px rgba(0, 0, 0, 0.06),
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.22),
      inset 0 3px 8px rgba(255, 255, 255, 0.15); /* å«ä¹ï¼å¢å¼ºé´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout:hover */
  .callout::after {{ /* å«ä¹ï¼é¡¶é¨å¼§å½¢é«ååå°ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    content: ''; /* å«ä¹ï¼ä¼ªåç´ åå®¹ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    position: absolute; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    top: 0; /* å«ä¹ï¼é¡¶é¨ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    left: 0; /* å«ä¹ï¼å·¦è¾¹ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    right: 0; /* å«ä¹ï¼å³è¾¹ä½ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    height: 55%; /* å«ä¹ï¼è¦çä¸åé¨åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    background: linear-gradient(180deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.03) 60%, transparent 100%); /* å«ä¹ï¼é¡¶é¨é«åæ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border-radius: 24px 24px 0 0; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    pointer-events: none; /* å«ä¹ï¼ä¸ååºé¼ æ ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    z-index: -1; /* å«ä¹ï¼ç½®äºåå®¹ä¸æ¹ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout::after */
  /* Callout tone åä½ - ä¸åé¢è²åå */
  .callout.tone-info {{ /* å«ä¹ï¼ä¿¡æ¯ç±»ï¿½?calloutï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-accent: #3b82f6; /* å«ä¹ï¼ä¿¡æ¯èè²è°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    --callout-glow-color: rgba(59, 130, 246, 0.4); /* å«ä¹ï¼ä¿¡æ¯èååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout.tone-info */
  .callout.tone-warning {{ /* å«ä¹ï¼è­¦åç±»ï¿½?calloutï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-accent: #f59e0b; /* å«ä¹ï¼è­¦åæ©è²è°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    --callout-glow-color: rgba(245, 158, 11, 0.4); /* å«ä¹ï¼è­¦åæ©ååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout.tone-warning */
  .callout.tone-success {{ /* å«ä¹ï¼æåç±»ï¿½?calloutï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-accent: #10b981; /* å«ä¹ï¼æåç»¿è²è°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    --callout-glow-color: rgba(16, 185, 129, 0.4); /* å«ä¹ï¼æåç»¿ååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout.tone-success */
  .callout.tone-danger {{ /* å«ä¹ï¼å±é©ç±»ï¿½?calloutï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-accent: #ef4444; /* å«ä¹ï¼å±é©çº¢è²è°ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    --callout-glow-color: rgba(239, 68, 68, 0.4); /* å«ä¹ï¼å±é©çº¢ååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .callout.tone-danger */
  /* æè²æ¨¡å¼ callout æ¶²æç»ï¿½?*/
  .dark-mode .callout {{ /* å«ä¹ï¼æè²æ¨¡ï¿½?callout æ¶²æç»çï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.01) 100%); /* å«ä¹ï¼æè²éææ¸åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-shadow: 
      0 12px 40px rgba(0, 0, 0, 0.35),
      0 4px 12px rgba(0, 0, 0, 0.18),
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.08),
      inset 0 2px 6px rgba(255, 255, 255, 0.04); /* å«ä¹ï¼æè²é´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout */
  .dark-mode .callout:hover {{ /* å«ä¹ï¼æè²æ¬åææï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    box-shadow: 
      0 24px 64px rgba(0, 0, 0, 0.45),
      0 10px 28px rgba(0, 0, 0, 0.22),
      inset 0 0 0 1.5px rgba(255, 255, 255, 0.12),
      inset 0 3px 8px rgba(255, 255, 255, 0.06); /* å«ä¹ï¼æè²å¢å¼ºé´å½±ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout:hover */
  .dark-mode .callout::after {{ /* å«ä¹ï¼æè²é¡¶é¨é«åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    background: linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.01) 50%, transparent 100%); /* å«ä¹ï¼æè²é«åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout::after */
  /* æè²æ¨¡å¼ååé¢è²å¢å¼º */
  .dark-mode .callout.tone-info {{ /* å«ä¹ï¼æè²ä¿¡æ¯ç±»åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-glow-color: rgba(96, 165, 250, 0.5); /* å«ä¹ï¼æè²ä¿¡æ¯ååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout.tone-info */
  .dark-mode .callout.tone-warning {{ /* å«ä¹ï¼æè²è­¦åç±»åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-glow-color: rgba(251, 191, 36, 0.5); /* å«ä¹ï¼æè²è­¦åååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout.tone-warning */
  .dark-mode .callout.tone-success {{ /* å«ä¹ï¼æè²æåç±»åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-glow-color: rgba(52, 211, 153, 0.5); /* å«ä¹ï¼æè²æåååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout.tone-success */
  .dark-mode .callout.tone-danger {{ /* å«ä¹ï¼æè²å±é©ç±»åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    --callout-glow-color: rgba(248, 113, 113, 0.5); /* å«ä¹ï¼æè²å±é©ååï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .dark-mode .callout.tone-danger */
}} /* ç»æ @media screen callout æ¶²æç»ï¿½?*/
.kpi-grid {{ /* å«ä¹ï¼KPI æ æ ¼å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: grid; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); /* å«ä¹ï¼ç½æ ¼åæ¨¡æ¿ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 16px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .kpi-grid */
.kpi-card {{ /* å«ä¹ï¼KPI å¡çï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-direction: column; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 8px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.02); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .kpi-card */
.kpi-value {{ /* å«ä¹ï¿½?kpi-value æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 2rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: nowrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 4px 6px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.25; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  word-break: break-word; /* å«ä¹ï¼åè¯æ­è¡è§åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-wrap: break-word; /* å«ä¹ï¼é¿åè¯æ¢è¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .kpi-value */
.kpi-value small {{ /* å«ä¹ï¿½?kpi-value small æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-size: 0.65em; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-self: baseline; /* å«ä¹ï¼align-self æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  white-space: nowrap; /* å«ä¹ï¼ç©ºç½ä¸æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .kpi-value small */
.kpi-label {{ /* å«ä¹ï¿½?kpi-label æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.35; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  word-break: break-word; /* å«ä¹ï¼åè¯æ­è¡è§åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-wrap: break-word; /* å«ä¹ï¼é¿åè¯æ¢è¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .kpi-label */
.delta.up {{ color: #27ae60; }} /* å«ä¹ï¿½?delta.up  color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.delta.down {{ color: #e74c3c; }} /* å«ä¹ï¿½?delta.down  color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.delta.neutral {{ color: var(--secondary-color); }} /* å«ä¹ï¿½?delta.neutral  color æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
.delta {{ /* å«ä¹ï¿½?delta æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.3; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  word-break: break-word; /* å«ä¹ï¼åè¯æ­è¡è§åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-wrap: break-word; /* å«ä¹ï¼é¿åè¯æ¢è¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .delta */
.chart-card {{ /* å«ä¹ï¼å¾è¡¨å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 30px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 20px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.01); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-card */
.chart-card.chart-card--error {{ /* å«ä¹ï¿½?chart-card.chart-card--error æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border-style: dashed; /* å«ä¹ï¼border-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(135deg, rgba(0,0,0,0.015), rgba(0,0,0,0.04)); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-card.chart-card--error */
.chart-error {{ /* å«ä¹ï¿½?chart-error æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 12px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 14px 12px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 10px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.03); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-error */
.chart-error__icon {{ /* å«ä¹ï¿½?chart-error__icon æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 28px; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: 28px; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-shrink: 0; /* å«ä¹ï¼flex-shrink æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 50%; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  justify-content: center; /* å«ä¹ï¼flex ä¸»è½´å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 700; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color-dark); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: rgba(0,0,0,0.06); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.9rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-error__icon */
.chart-error__title {{ /* å«ä¹ï¿½?chart-error__title æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-error__title */
.chart-error__desc {{ /* å«ä¹ï¿½?chart-error__desc æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 4px 0 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  line-height: 1.6; /* å«ä¹ï¼è¡é«ï¼æåå¯è¯»æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-error__desc */
.chart-card.wordcloud-card .chart-container {{ /* å«ä¹ï¿½?chart-card.wordcloud-card .chart-container æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  min-height: 180px; /* å«ä¹ï¼æå°é«åº¦ï¼é²æ­¢å¡é·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-card.wordcloud-card .chart-container */
.chart-container {{ /* å«ä¹ï¼å¾ï¿½?canvas å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  position: relative; /* å«ä¹ï¼å®ä½æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  min-height: 220px; /* å«ä¹ï¼æå°é«åº¦ï¼é²æ­¢å¡é·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-container */
.chart-fallback {{ /* å«ä¹ï¼å¾è¡¨ååºè¡¨æ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: none; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 12px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-x: auto; /* å«ä¹ï¼æ¨ªåæº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-fallback */
.no-js .chart-fallback {{ /* å«ä¹ï¿½?no-js .chart-fallback æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: block; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .no-js .chart-fallback */
.no-js .chart-container {{ /* å«ä¹ï¿½?no-js .chart-container æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: none; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .no-js .chart-container */
.chart-fallback table {{ /* å«ä¹ï¿½?chart-fallback table æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-collapse: collapse; /* å«ä¹ï¼border-collapse æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-fallback table */
.chart-fallback th,
.chart-fallback td {{ /* å«ä¹ï¿½?chart-fallback td æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  border: 1px solid var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 6px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: left; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-fallback td */
.chart-fallback th {{ /* å«ä¹ï¿½?chart-fallback th æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: rgba(0,0,0,0.04); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-fallback th */
.wordcloud-fallback .wordcloud-badges {{ /* å«ä¹ï¿½?wordcloud-fallback .wordcloud-badges æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 6px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin-top: 6px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .wordcloud-fallback .wordcloud-badges */
.wordcloud-badge {{ /* å«ä¹ï¼è¯äºå¾½ç« ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  display: inline-flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  align-items: center; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  gap: 4px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 4px 8px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 999px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px solid rgba(74, 144, 226, 0.35); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--text-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  background: linear-gradient(135deg, rgba(74, 144, 226, 0.14) 0%, rgba(74, 144, 226, 0.24) 100%); /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .wordcloud-badge */
.dark-mode .wordcloud-badge {{ /* å«ä¹ï¿½?dark-mode .wordcloud-badge æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.35); /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .dark-mode .wordcloud-badge */
.wordcloud-badge small {{ /* å«ä¹ï¿½?wordcloud-badge small æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-weight: 600; /* å«ä¹ï¼å­éï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.75rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .wordcloud-badge small */
.chart-note {{ /* å«ä¹ï¼å¾è¡¨éçº§æç¤ºï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin-top: 8px; /* å«ä¹ï¼margin-top æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.85rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .chart-note */
figure {{ /* å«ä¹ï¼figure æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ figure */
figure img {{ /* å«ä¹ï¼figure img æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ figure img */
.figure-placeholder {{ /* å«ä¹ï¿½?figure-placeholder æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  padding: 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border: 1px dashed var(--border-color); /* å«ä¹ï¼è¾¹æ¡æ ·å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: var(--secondary-color); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 0.95rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 20px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .figure-placeholder */
.math-block {{ /* å«ä¹ï¼åçº§å¬å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  text-align: center; /* å«ä¹ï¼ææ¬å¯¹é½ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-size: 1.1rem; /* å«ä¹ï¼å­å·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  margin: 24px 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .math-block */
.math-inline {{ /* å«ä¹ï¼è¡åå¬å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  font-family: {fonts.get("heading", fonts.get("body", "sans-serif"))}; /* å«ä¹ï¼å­ä½æï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  font-style: italic; /* å«ä¹ï¼font-style æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  white-space: nowrap; /* å«ä¹ï¼ç©ºç½ä¸æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 0 0.15em; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .math-inline */
pre.code-block {{ /* å«ä¹ï¼ä»£ç åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  background: #1e1e1e; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  color: #fff; /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  padding: 16px; /* å«ä¹ï¼åè¾¹è·ï¼æ§å¶åå®¹ä¸å®¹å¨è¾¹ç¼çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  border-radius: 12px; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-x: auto; /* å«ä¹ï¼æ¨ªåæº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ pre.code-block */
@media (max-width: 768px) {{ /* å«ä¹ï¼ç§»å¨ç«¯æ­ç¹æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  .report-header {{ /* å«ä¹ï¼é¡µçå¸é¡¶åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    flex-direction: column; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    align-items: flex-start; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .report-header */
  main {{ /* å«ä¹ï¼ä¸»ä½åå®¹å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    border-radius: 0; /* å«ä¹ï¼åè§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ main */
}} /* ç»æ @media (max-width: 768px) */
@media print {{ /* å«ä¹ï¼æå°æ¨¡å¼æ ·å¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  .no-print {{ display: none !important; }} /* å«ä¹ï¿½?no-print  display æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  body {{ /* å«ä¹ï¼å¨å±æçä¸èæ¯è®¾ç½®ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    background: #fff; /* å«ä¹ï¼èæ¯è²ææ¸åææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ body */
  main {{ /* å«ä¹ï¼ä¸»ä½åå®¹å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    box-shadow: none; /* å«ä¹ï¼é´å½±ææï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    margin: 0; /* å«ä¹ï¼å¤è¾¹è·ï¼æ§å¶ä¸å¨å´åç´ çè·ç¦»ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ main */
  .chapter > *,
  .hero-section,
  .callout,
  .engine-quote,
  .chart-card,
  .kpi-grid,
.swot-card,
.pest-card,
.table-wrap,
figure,
blockquote {{ /* å«ä¹ï¼å¼ç¨åï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ blockquote */
  .chapter h2,
  .chapter h3,
  .chapter h4 {{ /* å«ä¹ï¿½?chapter h4 æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-after: avoid; /* å«ä¹ï¼break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-after: avoid; /* å«ä¹ï¼page-break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .chapter h4 */
  .chart-card,
  .table-wrap {{ /* å«ä¹ï¼è¡¨æ ¼æ»å¨å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    overflow: visible !important; /* å«ä¹ï¼æº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    max-width: 100% !important; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    box-sizing: border-box; /* å«ä¹ï¼å°ºå¯¸è®¡ç®æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .table-wrap */
  .chart-card canvas {{ /* å«ä¹ï¿½?chart-card canvas æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    width: 100% !important; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    height: auto !important; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    max-width: 100% !important; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .chart-card canvas */
  .swot-card,
  .swot-cell {{ /* å«ä¹ï¼SWOT è±¡éååæ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-cell */
  .swot-card {{ /* å«ä¹ï¼SWOT å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    color: var(--swot-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    /* åè®¸å¡çåé¨åé¡µï¼é¿åæ´ä½è¢«æ¬å°ä¸ä¸ï¿½?*/
    break-inside: auto !important; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto !important; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-card */
  .swot-card__head {{ /* å«ä¹ï¿½?swot-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-after: avoid; /* å«ä¹ï¼break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-after: avoid; /* å«ä¹ï¼page-break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-card__head */
  .swot-grid {{ /* å«ä¹ï¼SWOT è±¡éç½æ ¼ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-before: avoid; /* å«ä¹ï¼break-before æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-before: avoid; /* å«ä¹ï¼page-break-before æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    break-inside: auto; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    display: flex; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    flex-wrap: wrap; /* å«ä¹ï¼æ¢è¡ç­ç¥ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    gap: 10px; /* å«ä¹ï¼å­åç´ é´è·ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    align-items: stretch; /* å«ä¹ï¼flex å¯¹é½æ¹å¼ï¼äº¤åè½´ï¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-grid */
  .swot-grid .swot-cell {{ /* å«ä¹ï¿½?swot-grid .swot-cell æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-grid .swot-cell */
  .swot-legend {{ /* å«ä¹ï¿½?swot-legend æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    display: none !important; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-legend */
  .swot-grid .swot-cell {{ /* å«ä¹ï¿½?swot-grid .swot-cell æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    flex: 1 1 320px; /* å«ä¹ï¼flex å ä½æ¯ä¾ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    min-width: 240px; /* å«ä¹ï¼æå°å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    height: auto; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .swot-grid .swot-cell */
  /* PEST æå°æ ·å¼ */
  .pest-card,
  .pest-strip {{ /* å«ä¹ï¼PEST æ¡å¸¦ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-inside: avoid; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: avoid; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-strip */
  .pest-card {{ /* å«ä¹ï¼PEST å¡çå®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    color: var(--pest-text); /* å«ä¹ï¼æå­é¢è²ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    break-inside: auto !important; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto !important; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-card */
  .pest-card__head {{ /* å«ä¹ï¿½?pest-card__head æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-after: avoid; /* å«ä¹ï¼break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-after: avoid; /* å«ä¹ï¼page-break-after æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-card__head */
  .pest-strips {{ /* å«ä¹ï¼PEST æ¡å¸¦å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    break-before: avoid; /* å«ä¹ï¼break-before æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-before: avoid; /* å«ä¹ï¼page-break-before æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    break-inside: auto; /* å«ä¹ï¼break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
    page-break-inside: auto; /* å«ä¹ï¼page-break-inside æ ·å¼å±æ§ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-strips */
  .pest-legend {{ /* å«ä¹ï¿½?pest-legend æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    display: none !important; /* å«ä¹ï¼å¸å±å±ç¤ºæ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-legend */
  .pest-strip {{ /* å«ä¹ï¼PEST æ¡å¸¦ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
    flex-direction: row; /* å«ä¹ï¼flex ä¸»è½´æ¹åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  }} /* ç»æ .pest-strip */
.table-wrap {{ /* å«ä¹ï¼è¡¨æ ¼æ»å¨å®¹å¨ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  overflow-x: auto; /* å«ä¹ï¼æ¨ªåæº¢åºå¤çï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .table-wrap */
.table-wrap table {{ /* å«ä¹ï¿½?table-wrap table æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  table-layout: fixed; /* å«ä¹ï¼è¡¨æ ¼å¸å±ç®æ³ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  width: 100%; /* å«ä¹ï¼å®½åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .table-wrap table */
.table-wrap table th,
.table-wrap table td {{ /* å«ä¹ï¿½?table-wrap table td æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  word-break: break-word; /* å«ä¹ï¼åè¯æ­è¡è§åï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  overflow-wrap: break-word; /* å«ä¹ï¼é¿åè¯æ¢è¡ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ .table-wrap table td */
/* é²æ­¢å¾çåå¾è¡¨æº¢ï¿½?*/
img, canvas, svg {{ /* å«ä¹ï¼åªä½åç´ å°ºå¯¸éå¶ï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  max-width: 100% !important; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  height: auto !important; /* å«ä¹ï¼é«åº¦è®¾ç½®ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ img, canvas, svg */
/* ç¡®ä¿ææå®¹å¨ä¸è¶åºé¡µé¢å®½åº¦ */
* {{ /* å«ä¹ï¿½? æ ·å¼åºåï¼è®¾ç½®ï¼å¨æ¬ååè°æ´ç¸å³å±ï¿½?*/
  box-sizing: border-box; /* å«ä¹ï¼å°ºå¯¸è®¡ç®æ¹å¼ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
  max-width: 100%; /* å«ä¹ï¼æå¤§å®½åº¦ï¼è®¾ç½®ï¼æéè°æ´æ°ï¿½?é¢è²/åé */
}} /* ç»æ * */
}} /* ç»æ @media print */

"""

    def _hydration_script(self) -> str:
        """
        è¿åé¡µé¢åºé¨çJSï¼è´ï¿½?Chart.js æ³¨æ°´ãè¯äºæ¸²æåæé®äº¤äºï¿½?

        äº¤äºå±çº§æ¢³çï¿½?
        1) ä¸»é¢åæ¢ï¿½?theme-toggleï¼ï¼çå¬èªå®ä¹ç»ï¿½?change äºä»¶ï¼detail ï¿½?'light'/'dark'ï¿½?
           ä½ç¨ï¼åï¿½?body.dark-modeãå·ï¿½?Chart.js ä¸è¯äºé¢è²ï¿½?
        2) æå°æé®ï¿½?print-btnï¼ï¼è§¦å window.print()ï¼å CSS @media print æ§å¶çå¼ï¿½?
        3) å¯¼åºæé®ï¿½?export-btnï¼ï¼è°ç¨ exportPdf()ï¼åé¨ä½¿ï¿½?html2canvas + jsPDFï¿½?
           å¹¶æ¾ï¿½?#export-overlayï¼é®ç½©ãç¶æææ¡ãè¿åº¦æ¡ï¼ï¿½?
        4) å¾è¡¨æ³¨æ°´ï¼æ«ææï¿½?data-config-id ï¿½?canvasï¼è§£æç¸ï¿½?JSONï¼å®ä¾å Chart.jsï¿½?
           å¤±è´¥æ¶éçº§ä¸ºè¡¨æ ¼/è¯äºå¾½ç« å±ç¤ºï¼å¹¶å¨å¡çä¸æ è®° data-chart-stateï¿½?
        5) çªå£ resizeï¼debounce åéç»è¯äºï¼ç¡®ä¿ååºå¼ï¿½?
        """
        return """
<script>
document.documentElement.classList.remove('no-js');
document.documentElement.classList.add('js-ready');

/* ========== Theme Button Web Component (å·²æ³¨éï¼æ¹ç¨ action-btn é£æ ¼) ========== */
/*
(() => {
  const themeButtonFunc = (root, initTheme, changeTheme) => {
    const checkbox = root.querySelector('.theme-checkbox');
    // åå§åç¶ï¿½?
    if (initTheme === 'dark') {
      checkbox.checked = true;
    }
    // æ ¸å¿äº¤äºï¼å¾éåï¿½?dark/lightï¼å¤é¨éè¿ changeTheme åè°åæ­¥ä¸»é¢
    checkbox.addEventListener('change', (e) => {
      const isDark = e.target.checked;
      changeTheme(isDark ? 'dark' : 'light');
    });
  };

  class ThemeButton extends HTMLElement {
    constructor() { super(); }
    connectedCallback() {
      const initTheme = this.getAttribute("value") || "light";
      const size = +this.getAttribute("size") || 1.5;
      
      const shadow = this.attachShadow({ mode: "closed" });
      const container = document.createElement("div");
      container.setAttribute("class", "container");
      container.style.fontSize = `${size * 10}px`;

      // ç»ä»¶ç»æï¼checkbox + labelï¼label åå«å¤©ç©º/ææ/äºå±ä¸æäº®åç¹ï¼è§è§ä¸æ¯ä¸»é¢åæ¢æ¨é®
      container.innerHTML = [
        '<div class="toggle-wrapper">',
        '  <input type="checkbox" class="theme-checkbox" id="theme-toggle-input">',
        '  <label for="theme-toggle-input" class="toggle-label">',
        '    <div class="toggle-background">',
        '      <div class="stars">',
        '        <span class="star"></span>',
        '        <span class="star"></span>',
        '        <span class="star"></span>',
        '        <span class="star"></span>',
        '      </div>',
        '      <div class="clouds">',
        '        <span class="cloud"></span>',
        '        <span class="cloud"></span>',
        '      </div>',
        '    </div>',
        '    <div class="toggle-circle">',
        '      <div class="moon-crater"></div>',
        '      <div class="moon-crater"></div>',
        '      <div class="moon-crater"></div>',
        '    </div>',
        '  </label>',
        '</div>'
      ].join('');

      const style = document.createElement("style");
      style.textContent = [
        '* { box-sizing: border-box; margin: 0; padding: 0; }',
        '.container { display: inline-block; position: relative; width: 5.4em; height: 2.6em; vertical-align: middle; }',
        '.toggle-wrapper { width: 100%; height: 100%; }',
        '.theme-checkbox { display: none; }',
        '.toggle-label { display: block; width: 100%; height: 100%; border-radius: 2.6em; background-color: #87CEEB; cursor: pointer; position: relative; overflow: hidden; transition: background-color 0.5s ease; box-shadow: inset 0 0.1em 0.3em rgba(0,0,0,0.2); }',
        '.theme-checkbox:checked + .toggle-label { background-color: #1F2937; }',
        '.toggle-circle { position: absolute; top: 0.2em; left: 0.2em; width: 2.2em; height: 2.2em; border-radius: 50%; background-color: #FFD700; box-shadow: 0 0.1em 0.2em rgba(0,0,0,0.3); transition: transform 0.5s cubic-bezier(0.4, 0.0, 0.2, 1), background-color 0.5s ease; z-index: 2; }',
        '.theme-checkbox:checked + .toggle-label .toggle-circle { transform: translateX(2.8em); background-color: #F3F4F6; box-shadow: inset -0.2em -0.2em 0.2em rgba(0,0,0,0.1), 0 0.1em 0.2em rgba(255,255,255,0.2); }',
        '.moon-crater { position: absolute; background-color: rgba(200, 200, 200, 0.6); border-radius: 50%; opacity: 0; transition: opacity 0.3s ease; }',
        '.theme-checkbox:checked + .toggle-label .toggle-circle .moon-crater { opacity: 1; }',
        '.moon-crater:nth-child(1) { width: 0.6em; height: 0.6em; top: 0.4em; left: 0.8em; }',
        '.moon-crater:nth-child(2) { width: 0.4em; height: 0.4em; top: 1.2em; left: 0.4em; }',
        '.moon-crater:nth-child(3) { width: 0.3em; height: 0.3em; top: 1.4em; left: 1.2em; }',
        '.toggle-background { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }',
        '.clouds { position: absolute; width: 100%; height: 100%; transition: transform 0.5s ease, opacity 0.5s ease; opacity: 1; }',
        '.theme-checkbox:checked + .toggle-label .clouds { transform: translateY(100%); opacity: 0; }',
        '.cloud { position: absolute; background-color: #fff; border-radius: 2em; opacity: 0.9; }',
        '.cloud::before { content: ""; position: absolute; top: -40%; left: 15%; width: 50%; height: 100%; background-color: inherit; border-radius: 50%; }',
        '.cloud::after { content: ""; position: absolute; top: -55%; left: 45%; width: 50%; height: 120%; background-color: inherit; border-radius: 50%; }',
        '.cloud:nth-child(1) { width: 1.4em; height: 0.5em; top: 0.8em; right: 1.0em; }',
        '.cloud:nth-child(2) { width: 1.0em; height: 0.4em; top: 1.6em; right: 2.0em; opacity: 0.7; }',
        '.stars { position: absolute; width: 100%; height: 100%; transition: transform 0.5s ease, opacity 0.5s ease; transform: translateY(-100%); opacity: 0; }',
        '.theme-checkbox:checked + .toggle-label .stars { transform: translateY(0); opacity: 1; }',
        '.star { position: absolute; background-color: #FFF; border-radius: 50%; width: 0.15em; height: 0.15em; box-shadow: 0 0 0.2em #FFF; animation: twinkle 2s infinite ease-in-out; }',
        '.star:nth-child(1) { top: 0.6em; left: 1.0em; animation-delay: 0s; }',
        '.star:nth-child(2) { top: 1.6em; left: 1.8em; width: 0.1em; height: 0.1em; animation-delay: 0.5s; }',
        '.star:nth-child(3) { top: 0.8em; left: 2.4em; width: 0.12em; height: 0.12em; animation-delay: 1s; }',
        '.star:nth-child(4) { top: 1.8em; left: 0.8em; width: 0.08em; height: 0.08em; animation-delay: 1.5s; }',
        '@keyframes twinkle { 0%, 100% { opacity: 0.4; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }'
      ].join(' ');

      const changeThemeWrapper = (detail) => {
        this.dispatchEvent(new CustomEvent("change", { detail }));
      };
      
      themeButtonFunc(container, initTheme, changeThemeWrapper);
      shadow.appendChild(style);
      shadow.appendChild(container);
    }
  }
  customElements.define("theme-button", ThemeButton);
})();
*/
/* ========== End Theme Button Web Component ========== */
 
 const chartRegistry = [];
const wordCloudRegistry = new Map();
const STABLE_CHART_TYPES = ['line', 'bar'];
const CHART_TYPE_LABELS = {
  line: 'æçº¿ï¿½?,
  bar: 'æ±ç¶ï¿½?,
  doughnut: 'åç¯ï¿½?,
  pie: 'é¥¼å¾',
  radar: 'é·è¾¾ï¿½?,
  polarArea: 'æå°åºåï¿½?
};

// ä¸PDFç¢éæ¸²æä¿æä¸è´çé¢è²æ¿æ¢/æäº®è§å
const DEFAULT_CHART_COLORS = [
  '#4A90E2', '#E85D75', '#50C878', '#FFB347',
  '#9B59B6', '#3498DB', '#E67E22', '#16A085',
  '#F39C12', '#D35400', '#27AE60', '#8E44AD'
];
const CSS_VAR_COLOR_MAP = {
  'var(--chart-color-green)': '#4BC0C0',
  'var(--chart-color-red)': '#FF6384',
  'var(--chart-color-blue)': '#36A2EB',
  'var(--color-accent)': '#4A90E2',
  'var(--re-accent-color)': '#4A90E2',
  'var(--re-accent-color-translucent)': 'rgba(74, 144, 226, 0.08)',
  'var(--color-kpi-down)': '#E85D75',
  'var(--re-danger-color)': '#E85D75',
  'var(--re-danger-color-translucent)': 'rgba(232, 93, 117, 0.08)',
  'var(--color-warning)': '#FFB347',
  'var(--re-warning-color)': '#FFB347',
  'var(--re-warning-color-translucent)': 'rgba(255, 179, 71, 0.08)',
  'var(--color-success)': '#50C878',
  'var(--re-success-color)': '#50C878',
  'var(--re-success-color-translucent)': 'rgba(80, 200, 120, 0.08)',
  'var(--color-accent-positive)': '#50C878',
  'var(--color-accent-negative)': '#E85D75',
  'var(--color-text-secondary)': '#6B7280',
  'var(--accentPositive)': '#50C878',
  'var(--accentNegative)': '#E85D75',
  'var(--sentiment-positive, #28A745)': '#28A745',
  'var(--sentiment-negative, #E53E3E)': '#E53E3E',
  'var(--sentiment-neutral, #FFC107)': '#FFC107',
  'var(--sentiment-positive)': '#28A745',
  'var(--sentiment-negative)': '#E53E3E',
  'var(--sentiment-neutral)': '#FFC107',
  'var(--color-primary)': '#3498DB',
  'var(--color-secondary)': '#95A5A6'
};
const WORDCLOUD_CATEGORY_COLORS = {
  positive: '#10b981',
  negative: '#ef4444',
  neutral: '#6b7280',
  controversial: '#f59e0b'
};

function normalizeColorToken(color) {
  if (typeof color !== 'string') return color;
  const trimmed = color.trim();
  if (!trimmed) return null;
  // æ¯æ var(--token, fallback) å½¢å¼ï¼ä¼åè§£æfallback
  const varWithFallback = trimmed.match(/^var\(\s*--[^,)+]+,\s*([^)]+)\)/i);
  if (varWithFallback && varWithFallback[1]) {
    const fallback = varWithFallback[1].trim();
    const normalizedFallback = normalizeColorToken(fallback);
    if (normalizedFallback) return normalizedFallback;
  }
  if (CSS_VAR_COLOR_MAP[trimmed]) {
    return CSS_VAR_COLOR_MAP[trimmed];
  }
  if (trimmed.startsWith('var(')) {
    if (/accent|primary/i.test(trimmed)) return '#4A90E2';
    if (/danger|down|error/i.test(trimmed)) return '#E85D75';
    if (/warning/i.test(trimmed)) return '#FFB347';
    if (/success|up/i.test(trimmed)) return '#50C878';
    return '#3498DB';
  }
  return trimmed;
}

function hexToRgb(color) {
  if (typeof color !== 'string') return null;
  const normalized = color.replace('#', '');
  if (!(normalized.length === 3 || normalized.length === 6)) return null;
  const hex = normalized.length === 3 ? normalized.split('').map(c => c + c).join('') : normalized;
  const intVal = parseInt(hex, 16);
  if (Number.isNaN(intVal)) return null;
  return [(intVal >> 16) & 255, (intVal >> 8) & 255, intVal & 255];
}

function parseRgbString(color) {
  if (typeof color !== 'string') return null;
  const match = color.match(/rgba?\s*\(([^)]+)\)/i);
  if (!match) return null;
  const parts = match[1].split(',').map(p => parseFloat(p.trim())).filter(v => !Number.isNaN(v));
  if (parts.length < 3) return null;
  return [parts[0], parts[1], parts[2]].map(v => Math.max(0, Math.min(255, v)));
}

function alphaFromColor(color) {
  if (typeof color !== 'string') return null;
  const raw = color.trim();
  if (!raw) return null;
  if (raw.toLowerCase() === 'transparent') return 0;

  const extractAlpha = (source) => {
    const match = source.match(/rgba?\s*\(([^)]+)\)/i);
    if (!match) return null;
    const parts = match[1].split(',').map(p => p.trim());
    if (source.toLowerCase().startsWith('rgba') && parts.length >= 2) {
      const alphaToken = parts[parts.length - 1];
      const isPercent = /%$/.test(alphaToken);
      const alphaVal = parseFloat(alphaToken.replace('%', ''));
      if (!Number.isNaN(alphaVal)) {
        const normalizedAlpha = isPercent ? alphaVal / 100 : alphaVal;
        return Math.max(0, Math.min(1, normalizedAlpha));
      }
    }
    if (parts.length >= 3) return 1;
    return null;
  };

  const rawAlpha = extractAlpha(raw);
  if (rawAlpha !== null) return rawAlpha;

  const normalized = normalizeColorToken(raw);
  if (typeof normalized === 'string' && normalized !== raw) {
    const normalizedAlpha = extractAlpha(normalized);
    if (normalizedAlpha !== null) return normalizedAlpha;
  }

  return null;
}

function rgbFromColor(color) {
  const normalized = normalizeColorToken(color);
  return hexToRgb(normalized) || parseRgbString(normalized);
}

function colorLuminance(color) {
  const rgb = rgbFromColor(color);
  if (!rgb) return null;
  const [r, g, b] = rgb.map(v => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function lightenColor(color, ratio) {
  const rgb = rgbFromColor(color);
  if (!rgb) return color;
  const factor = Math.min(1, Math.max(0, ratio || 0.25));
  const mixed = rgb.map(v => Math.round(v + (255 - v) * factor));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function ensureAlpha(color, alpha) {
  const rgb = rgbFromColor(color);
  if (!rgb) return color;
  const clamped = Math.min(1, Math.max(0, alpha));
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${clamped})`;
}

function liftDarkColor(color) {
  const normalized = normalizeColorToken(color);
  const lum = colorLuminance(normalized);
  if (lum !== null && lum < 0.12) {
    return lightenColor(normalized, 0.35);
  }
  return normalized;
}

function mixColors(colorA, colorB, amount) {
  const rgbA = rgbFromColor(colorA);
  const rgbB = rgbFromColor(colorB);
  if (!rgbA && !rgbB) return colorA || colorB;
  if (!rgbA) return colorB;
  if (!rgbB) return colorA;
  const t = Math.min(1, Math.max(0, amount || 0));
  const mixed = rgbA.map((v, idx) => Math.round(v * (1 - t) + rgbB[idx] * t));
  return `rgb(${mixed[0]}, ${mixed[1]}, ${mixed[2]})`;
}

function pickComputedColor(keys, fallback, styles) {
  const styleRef = styles || getComputedStyle(document.body);
  for (const key of keys) {
    const val = styleRef.getPropertyValue(key);
    if (val && val.trim()) {
      const normalized = normalizeColorToken(val.trim());
      if (normalized) return normalized;
    }
  }
  return fallback;
}

function resolveWordcloudTheme() {
  const styles = getComputedStyle(document.body);
  const isDark = document.body.classList.contains('dark-mode');
  const text = pickComputedColor(['--text-color'], isDark ? '#e5e7eb' : '#111827', styles);
  const secondary = pickComputedColor(['--secondary-color', '--color-text-secondary'], isDark ? '#cbd5e1' : '#475569', styles);
  const accent = liftDarkColor(
    pickComputedColor(['--primary-color', '--color-accent', '--re-accent-color'], '#4A90E2', styles)
  );
  const cardBg = pickComputedColor(
    ['--card-bg', '--paper-bg', '--bg', '--bg-color', '--background', '--page-bg'],
    isDark ? '#0f172a' : '#ffffff',
    styles
  );
  return { text, secondary, accent, cardBg, isDark };
}

function normalizeDatasetColors(payload, chartType) {
  const changes = [];
  const data = payload && payload.data;
  if (!data || !Array.isArray(data.datasets)) {
    return changes;
  }
  const type = chartType || 'bar';
  const needsArrayColors = type === 'pie' || type === 'doughnut' || type === 'polarArea';
  const MIN_PIE_ALPHA = 0.6;
  const pickColor = (value, fallback) => {
    if (Array.isArray(value) && value.length) return value[0];
    return value || fallback;
  };

  data.datasets.forEach((dataset, idx) => {
    if (!isPlainObject(dataset)) return;
    if (type === 'line') {
      dataset.fill = true;  // å¯¹æçº¿å¾å¼ºå¶å¼å¯å¡«åï¼ä¾¿äºåºåå¯¹æ¯
    }
    const paletteColor = normalizeColorToken(DEFAULT_CHART_COLORS[idx % DEFAULT_CHART_COLORS.length]);
    const borderInput = dataset.borderColor;
    const backgroundInput = dataset.backgroundColor;
    const borderIsArray = Array.isArray(borderInput);
    const bgIsArray = Array.isArray(backgroundInput);
    const baseCandidate = pickColor(borderInput, pickColor(backgroundInput, dataset.color || paletteColor));
    const liftedBase = liftDarkColor(baseCandidate || paletteColor);

    if (needsArrayColors) {
      const labelCount = Array.isArray(data.labels) ? data.labels.length : 0;
      const rawColors = bgIsArray ? backgroundInput : [];
      const dataLength = Array.isArray(dataset.data) ? dataset.data.length : 0;
      const total = Math.max(labelCount, rawColors.length, dataLength, 1);
      const normalizedColors = [];
      let fixedTransparentCount = 0;
      for (let i = 0; i < total; i++) {
        const fallbackColor = DEFAULT_CHART_COLORS[(idx + i) % DEFAULT_CHART_COLORS.length];
        const normalizedRaw = normalizeColorToken(rawColors[i]);
        const alpha = alphaFromColor(normalizedRaw);
        const isInvisible = typeof normalizedRaw === 'string' && normalizedRaw.toLowerCase() === 'transparent';
        if (alpha === 0 || isInvisible) {
          fixedTransparentCount += 1;
        }
        const baseColor = (!normalizedRaw || isInvisible) ? fallbackColor : normalizedRaw;
        const targetAlpha = alpha === null ? 1 : alpha;
        const normalizedColor = ensureAlpha(
          liftDarkColor(baseColor),
          Math.max(MIN_PIE_ALPHA, targetAlpha)
        );
        normalizedColors.push(normalizedColor);
      }
      dataset.backgroundColor = normalizedColors;
      dataset.borderColor = normalizedColors.map(col => ensureAlpha(liftDarkColor(col), 1));
      const changeLabel = fixedTransparentCount
        ? `dataset${idx}: ä¿®æ­£${fixedTransparentCount}ä¸ªéææåº`
        : `dataset${idx}: æ ååæåºé¢ï¿½?${normalizedColors.length})`;
      changes.push(changeLabel);
      return;
    }

    if (!borderInput) {
      dataset.borderColor = liftedBase;
      changes.push(`dataset${idx}: è¡¥å¨è¾¹æ¡è²`);
    } else if (borderIsArray) {
      dataset.borderColor = borderInput.map(col => liftDarkColor(col));
    } else {
      dataset.borderColor = liftDarkColor(borderInput);
    }

    const typeAlpha = type === 'line'
      ? (dataset.fill ? 0.25 : 0.18)
      : type === 'radar'
        ? 0.25
        : type === 'scatter' || type === 'bubble'
          ? 0.6
          : type === 'bar'
            ? 0.85
            : null;

    if (typeAlpha !== null) {
      if (bgIsArray && dataset.backgroundColor.length) {
        dataset.backgroundColor = backgroundInput.map(col => ensureAlpha(liftDarkColor(col), typeAlpha));
      } else {
        const bgSeed = pickColor(backgroundInput, pickColor(dataset.borderColor, paletteColor));
        dataset.backgroundColor = ensureAlpha(liftDarkColor(bgSeed), typeAlpha);
      }
      if (dataset.fill || type !== 'line') {
        changes.push(`dataset${idx}: åºç¨æ·¡åå¡«åä»¥é¿åé®æ¡`);
      }
    } else if (!dataset.backgroundColor) {
      dataset.backgroundColor = ensureAlpha(liftedBase, 0.85);
    } else if (bgIsArray) {
      dataset.backgroundColor = backgroundInput.map(col => liftDarkColor(col));
    } else if (!bgIsArray) {
      dataset.backgroundColor = liftDarkColor(dataset.backgroundColor);
    }

    if (type === 'line' && !dataset.pointBackgroundColor) {
      dataset.pointBackgroundColor = Array.isArray(dataset.borderColor)
        ? dataset.borderColor[0]
        : dataset.borderColor;
    }
  });

  if (changes.length) {
    payload._colorAudit = changes;
  }
  return changes;
}

function getThemePalette() {
  const styles = getComputedStyle(document.body);
  return {
    text: styles.getPropertyValue('--text-color').trim(),
    grid: styles.getPropertyValue('--border-color').trim()
  };
}

function applyChartTheme(chart) {
  if (!chart) return;
  try {
    chart.update('none');
  } catch (err) {
    console.error('Chart refresh failed', err);
  }
}

function isPlainObject(value) {
  return Object.prototype.toString.call(value) === '[object Object]';
}

function cloneDeep(value) {
  if (Array.isArray(value)) {
    return value.map(cloneDeep);
  }
  if (isPlainObject(value)) {
    const obj = {};
    Object.keys(value).forEach(key => {
      obj[key] = cloneDeep(value[key]);
    });
    return obj;
  }
  return value;
}

function mergeOptions(base, override) {
  const result = isPlainObject(base) ? cloneDeep(base) : {};
  if (!isPlainObject(override)) {
    return result;
  }
  Object.keys(override).forEach(key => {
    const overrideValue = override[key];
    if (Array.isArray(overrideValue)) {
      result[key] = cloneDeep(overrideValue);
    } else if (isPlainObject(overrideValue)) {
      result[key] = mergeOptions(result[key], overrideValue);
    } else {
      result[key] = overrideValue;
    }
  });
  return result;
}

function resolveChartTypes(payload) {
  const explicit = payload && payload.props && payload.props.type;
  const widgetType = payload && payload.widgetType ? payload.widgetType : 'chart.js/bar';
  const derived = widgetType && widgetType.includes('/') ? widgetType.split('/').pop() : widgetType;
  const extra = Array.isArray(payload && payload.preferredTypes) ? payload.preferredTypes : [];
  const pipeline = [explicit, derived, ...extra, ...STABLE_CHART_TYPES].filter(Boolean);
  const result = [];
  pipeline.forEach(type => {
    if (type && !result.includes(type)) {
      result.push(type);
    }
  });
  return result.length ? result : ['bar'];
}

function describeChartType(type) {
  return CHART_TYPE_LABELS[type] || type || 'å¾è¡¨';
}

function setChartDegradeNote(card, fromType, toType) {
  if (!card) return;
  card.setAttribute('data-chart-state', 'degraded');
  let note = card.querySelector('.chart-note');
  if (!note) {
    note = document.createElement('p');
    note.className = 'chart-note';
    card.appendChild(note);
  }
  note.textContent = `${describeChartType(fromType)}æ¸²æå¤±è´¥ï¼å·²èªå¨åæ¢ï¿½?{describeChartType(toType)}ä»¥ç¡®ä¿å¼å®¹;
}

function clearChartDegradeNote(card) {
  if (!card) return;
  card.removeAttribute('data-chart-state');
  const note = card.querySelector('.chart-note');
  if (note) {
    note.remove();
  }
}

function isWordCloudWidget(payload) {
  const type = payload && payload.widgetType;
  return typeof type === 'string' && type.toLowerCase().includes('wordcloud');
}

function hashString(str) {
  let h = 0;
  if (!str) return h;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return h;
}

function normalizeWordcloudItems(payload) {
  const sources = [];
  const props = payload && payload.props;
  const dataField = payload && payload.data;
  if (props) {
    ['data', 'items', 'words', 'sourceData'].forEach(key => {
      if (props[key]) sources.push(props[key]);
    });
  }
  if (dataField) {
    sources.push(dataField);
  }

  const seen = new Map();
  const pushItem = (word, weight, category) => {
    if (!word) return;
    let numeric = 1;
    if (typeof weight === 'number' && Number.isFinite(weight)) {
      numeric = weight;
    } else if (typeof weight === 'string') {
      const parsed = parseFloat(weight);
      numeric = Number.isFinite(parsed) ? parsed : 1;
    }
    if (!(numeric > 0)) numeric = 1;
    const cat = (category || '').toString().toLowerCase();
    const key = `${word}__${cat}`;
    const existing = seen.get(key);
    const payloadItem = { word: String(word), weight: numeric, category: cat };
    if (!existing || numeric > existing.weight) {
      seen.set(key, payloadItem);
    }
  };

  const consume = (raw) => {
    if (!raw) return;
    if (Array.isArray(raw)) {
      raw.forEach(item => {
        if (!item) return;
        if (Array.isArray(item)) {
          pushItem(item[0], item[1], item[2]);
        } else if (typeof item === 'object') {
          pushItem(item.word || item.text || item.label, item.weight, item.category);
        } else if (typeof item === 'string') {
          pushItem(item, 1, '');
        }
      });
    } else if (typeof raw === 'object') {
      Object.entries(raw).forEach(([word, weight]) => pushItem(word, weight, ''));
    }
  };

  sources.forEach(consume);

  const items = Array.from(seen.values());
  items.sort((a, b) => (b.weight || 0) - (a.weight || 0));
  return items.slice(0, 150);
}

function wordcloudColor(category) {
  const key = typeof category === 'string' ? category.toLowerCase() : '';
  const palette = resolveWordcloudTheme();
  const base = WORDCLOUD_CATEGORY_COLORS[key] || palette.accent || palette.secondary || '#334155';
  return liftDarkColor(base);
}

function renderWordCloudFallback(canvas, items, reason) {
  // è¯äºå¤±è´¥æ¶çæ¾ç¤ºå½¢å¼ï¼éï¿½?canvasï¼å±ç¤ºå¾½ç« åè¡¨ï¼ï¿½?æéï¼ï¼ä¿è¯"å¯è§æ°æ®"èéç©ºç½
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  if (!card) return;
  const wrapper = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (wrapper) {
    wrapper.style.display = 'none';
  } else {
    canvas.style.display = 'none';
  }
  let fallback = card.querySelector('.chart-fallback[data-dynamic="true"]');
  if (!fallback) {
    fallback = card.querySelector('.chart-fallback');
  }
  if (!fallback) {
    fallback = document.createElement('div');
    card.appendChild(fallback);
  }
  fallback.className = 'chart-fallback wordcloud-fallback';
  fallback.setAttribute('data-dynamic', 'true');
  fallback.style.display = 'block';
  fallback.innerHTML = '';
  card.setAttribute('data-chart-state', 'fallback');
  const buildBadge = (item, maxWeight) => {
    const badge = document.createElement('span');
    badge.className = 'wordcloud-badge';
    const clampedWeight = Math.max(0.5, (item.weight || 1));
    const normalized = Math.min(1, clampedWeight / (maxWeight || 1));
    const fontSize = 0.85 + normalized * 0.9;
    badge.style.fontSize = `${fontSize}rem`;
    badge.style.background = `linear-gradient(135deg, ${lightenColor(wordcloudColor(item.category), 0.05)} 0%, ${lightenColor(wordcloudColor(item.category), 0.15)} 100%)`;
    badge.style.borderColor = lightenColor(wordcloudColor(item.category), 0.25);
    badge.textContent = item.word;
    if (item.weight !== undefined && item.weight !== null) {
      const meta = document.createElement('small');
      meta.textContent = item.weight >= 0 && item.weight <= 1.5
        ? `${(item.weight * 100).toFixed(0)}%`
        : item.weight.toFixed(1).replace(/\.0+$/, '').replace(/0+$/, '').replace(/\.$/, '');
      badge.appendChild(meta);
    }
    return badge;
  };

  if (reason) {
    const notice = document.createElement('p');
    notice.className = 'chart-fallback__notice';
    notice.textContent = `è¯äºæªè½æ¸²æ${reason ? `ï¿½?{reason}ï¼` : ''}ï¼å·²å±ç¤ºå³é®è¯åè¡¨;
    fallback.appendChild(notice);
  }
  if (!items || !items.length) {
    const empty = document.createElement('p');
    empty.textContent = 'ææ å¯ç¨æ°æ®ï¿½?;
    fallback.appendChild(empty);
    return;
  }
  const badges = document.createElement('div');
  badges.className = 'wordcloud-badges';
  const maxWeight = items.reduce((max, item) => Math.max(max, item.weight || 0), 1);
  items.forEach(item => {
    badges.appendChild(buildBadge(item, maxWeight));
  });
  fallback.appendChild(badges);
}

function renderWordCloud(canvas, payload, skipRegistry) {
  const items = normalizeWordcloudItems(payload);
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  const container = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (!items.length) {
    renderWordCloudFallback(canvas, items, 'æ æææ°ï¿½?);
    return;
  }
  if (typeof WordCloud === 'undefined') {
    renderWordCloudFallback(canvas, items, 'è¯äºä¾èµæªå ï¿½?);
    return;
  }
  const theme = resolveWordcloudTheme();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const width = Math.max(260, (container ? container.clientWidth : canvas.clientWidth || canvas.width || 320));
  const height = Math.max(120, Math.round(width / 5)); // 5:1 å®½é«ï¿½?
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  canvas.style.backgroundColor = 'transparent';

  const resolveBgColor = () => {
    const cardEl = card || container || document.body;
    const style = getComputedStyle(cardEl);
    const tokens = ['--card-bg', '--panel-bg', '--paper-bg', '--bg', '--background', '--page-bg'];
    for (const key of tokens) {
      const val = style.getPropertyValue(key);
      if (val && val.trim() && val.trim() !== 'transparent') return val.trim();
    }
    if (style.backgroundColor && style.backgroundColor !== 'rgba(0, 0, 0, 0)') return style.backgroundColor;
    const bodyStyle = getComputedStyle(document.body);
    for (const key of tokens) {
      const val = bodyStyle.getPropertyValue(key);
      if (val && val.trim() && val.trim() !== 'transparent') return val.trim();
    }
    if (bodyStyle.backgroundColor && bodyStyle.backgroundColor !== 'rgba(0, 0, 0, 0)') {
      return bodyStyle.backgroundColor;
    }
    return 'transparent';
  };
  const bgColor = resolveBgColor() || theme.cardBg || 'transparent';

  const maxWeight = items.reduce((max, item) => Math.max(max, item.weight || 0), 0) || 1;
  const weightLookup = new Map();
  const categoryLookup = new Map();
  items.forEach(it => {
    weightLookup.set(it.word, it.weight || 1);
    categoryLookup.set(it.word, it.category || '');
  });
  const list = items.map(item => [item.word, item.weight && item.weight > 0 ? item.weight : 1]);
  try {
    WordCloud(canvas, {
      list,
      gridSize: Math.max(3, Math.floor(Math.sqrt(canvas.width * canvas.height) / 170)),
      weightFactor: (val) => {
        const normalized = Math.max(0, val) / maxWeight;
        const cap = Math.min(width, height);
        const base = Math.max(9, cap / 5.5);
        const size = base * (0.8 + normalized * 1.3);
        return size * dpr;
      },
      color: (word) => {
        const w = weightLookup.get(word) || 1;
        const ratio = Math.max(0, Math.min(1, w / (maxWeight || 1)));
        const category = categoryLookup.get(word) || '';
        const base = wordcloudColor(category);
        const target = theme.isDark ? '#ffffff' : (theme.text || '#111827');
        const mixAmount = theme.isDark
          ? 0.28 + (1 - ratio) * 0.22
          : 0.12 + (1 - ratio) * 0.35;
        const mixed = mixColors(base, target, mixAmount);
        return ensureAlpha(mixed || base, theme.isDark ? 0.95 : 1);
      },
      rotateRatio: 0,
      rotationSteps: 0,
      shuffle: false,
      shrinkToFit: true,
      drawOutOfBound: false,
      shape: 'square',
      ellipticity: 0.45,
      clearCanvas: true,
      backgroundColor: bgColor
    });
    if (container) {
      container.style.display = '';
      container.style.minHeight = `${height}px`;
      container.style.background = 'transparent';
    }
    const fallback = card && card.querySelector('.chart-fallback');
    if (fallback) {
      fallback.style.display = 'none';
    }
    card && card.removeAttribute('data-chart-state');
    if (!skipRegistry) {
      wordCloudRegistry.set(canvas, () => renderWordCloud(canvas, payload, true));
    }
  } catch (err) {
    console.error('WordCloud æ¸²æå¤±è´¥', err);
    renderWordCloudFallback(canvas, items, err && err.message ? err.message : '');
  }
}

function createFallbackTable(labels, datasets) {
  if (!Array.isArray(datasets) || !datasets.length) {
    return null;
  }
  const primaryDataset = datasets.find(ds => Array.isArray(ds && ds.data));
  const resolvedLabels = Array.isArray(labels) && labels.length
    ? labels
    : (primaryDataset && primaryDataset.data ? primaryDataset.data.map((_, idx) => `æ°æ®ï¿½?${idx + 1}`) : []);
  if (!resolvedLabels.length) {
    return null;
  }
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  const categoryHeader = document.createElement('th');
  categoryHeader.textContent = 'ç±»å«';
  headRow.appendChild(categoryHeader);
  datasets.forEach((dataset, index) => {
    const th = document.createElement('th');
    th.textContent = dataset && dataset.label ? dataset.label : `ç³»å${index + 1}`;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  resolvedLabels.forEach((label, rowIdx) => {
    const row = document.createElement('tr');
    const labelCell = document.createElement('td');
    labelCell.textContent = label;
    row.appendChild(labelCell);
    datasets.forEach(dataset => {
      const cell = document.createElement('td');
      const series = dataset && Array.isArray(dataset.data) ? dataset.data[rowIdx] : undefined;
      if (typeof series === 'number') {
        cell.textContent = series.toLocaleString();
      } else if (series !== undefined && series !== null && series !== '') {
        cell.textContent = series;
      } else {
        cell.textContent = 'ï¿½?;
      }
      row.appendChild(cell);
    });
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  return table;
}

function renderChartFallback(canvas, payload, reason) {
  // å¾è¡¨å¤±è´¥æ¶çæ¾ç¤ºå½¢å¼ï¼åæ¢å°è¡¨æ ¼æ°æ®ï¼categories x seriesï¼ï¼å¹¶å¨å¡çä¸æ ï¿½?fallback ç¶ï¿½?
  const card = canvas.closest('.chart-card') || canvas.parentElement;
  if (!card) return;
  clearChartDegradeNote(card);
  const wrapper = canvas.parentElement && canvas.parentElement.classList && canvas.parentElement.classList.contains('chart-container')
    ? canvas.parentElement
    : null;
  if (wrapper) {
    wrapper.style.display = 'none';
  } else {
    canvas.style.display = 'none';
  }
  let fallback = card.querySelector('.chart-fallback[data-dynamic="true"]');
  let prebuilt = false;
  if (!fallback) {
    fallback = card.querySelector('.chart-fallback');
    if (fallback) {
      prebuilt = fallback.hasAttribute('data-prebuilt');
    }
  }
  if (!fallback) {
    fallback = document.createElement('div');
    fallback.className = 'chart-fallback';
    fallback.setAttribute('data-dynamic', 'true');
    card.appendChild(fallback);
  } else if (!prebuilt) {
    fallback.innerHTML = '';
  }
  const titleFromOptions = payload && payload.props && payload.props.options &&
    payload.props.options.plugins && payload.props.options.plugins.title &&
    payload.props.options.plugins.title.text;
  const fallbackTitle = titleFromOptions ||
    (payload && payload.props && payload.props.title) ||
    (payload && payload.widgetId) ||
    canvas.getAttribute('id') ||
    'å¾è¡¨';
  const existingNotice = fallback.querySelector('.chart-fallback__notice');
  if (existingNotice) {
    existingNotice.remove();
  }
  const notice = document.createElement('p');
  notice.className = 'chart-fallback__notice';
  notice.textContent = `${fallbackTitle}ï¼å¾è¡¨æªè½æ¸²æï¼å·²å±ç¤ºè¡¨æ ¼æ°ï¿½?{reason ? `ï¿½?{reason}ï¼` : ''}`;
  fallback.insertBefore(notice, fallback.firstChild || null);
  if (!prebuilt) {
    const table = createFallbackTable(
      payload && payload.data && payload.data.labels,
      payload && payload.data && payload.data.datasets
    );
    if (table) {
      fallback.appendChild(table);
    }
  }
  fallback.style.display = 'block';
  card.setAttribute('data-chart-state', 'fallback');
}

function buildChartOptions(payload) {
  const rawLegend = payload && payload.props ? payload.props.legend : undefined;
  let legendConfig;
  if (isPlainObject(rawLegend)) {
    legendConfig = mergeOptions({
      display: rawLegend.display !== false,
      position: rawLegend.position || 'top'
    }, rawLegend);
  } else {
    legendConfig = {
      display: rawLegend === 'hidden' ? false : true,
      position: typeof rawLegend === 'string' ? rawLegend : 'top'
    };
  }
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: legendConfig
    }
  };
  if (payload && payload.props && payload.props.title) {
    baseOptions.plugins.title = {
      display: true,
      text: payload.props.title
    };
  }
  const overrideOptions = payload && payload.props && payload.props.options;
  return mergeOptions(baseOptions, overrideOptions);
}

function validateChartData(payload, type) {
  /**
   * åç«¯éªè¯å¾è¡¨æ°æ®
   * è¿å: { valid: boolean, errors: string[] }
   */
  const errors = [];

  if (!payload || typeof payload !== 'object') {
    errors.push('æ æçpayload');
    return { valid: false, errors };
  }

  const data = payload.data;
  if (!data || typeof data !== 'object') {
    errors.push('ç¼ºå°dataå­æ®µ');
    return { valid: false, errors };
  }

  // ç¹æ®å¾è¡¨ç±»åï¼scatter, bubbleï¿½?
  const specialTypes = { 'scatter': true, 'bubble': true };
  if (specialTypes[type]) {
    // è¿äºç±»åéè¦ç¹æ®çæ°æ®æ ¼å¼ {x, y} ï¿½?{x, y, r}
    // è·³è¿æ åéªè¯
    return { valid: true, errors };
  }

  // æ åå¾è¡¨ç±»åéªè¯
  const datasets = data.datasets;
  if (!Array.isArray(datasets)) {
    errors.push('datasetså¿é¡»æ¯æ°ï¿½?);
    return { valid: false, errors };
  }

  if (datasets.length === 0) {
    errors.push('datasetsæ°ç»ä¸ºç©º');
    return { valid: false, errors };
  }

  // éªè¯æ¯ä¸ªdataset
  for (let i = 0; i < datasets.length; i++) {
    const dataset = datasets[i];
    if (!dataset || typeof dataset !== 'object') {
      errors.push(`datasets[${i}]ä¸æ¯å¯¹è±¡`);
      continue;
    }

    if (!Array.isArray(dataset.data)) {
      errors.push(`datasets[${i}].dataä¸æ¯æ°ç»`);
    } else if (dataset.data.length === 0) {
      errors.push(`datasets[${i}].dataä¸ºç©º`);
    }
  }

  // éè¦labelsçå¾è¡¨ç±»ï¿½?
  const labelRequiredTypes = {
    'line': true, 'bar': true, 'radar': true,
    'polarArea': true, 'pie': true, 'doughnut': true
  };

  if (labelRequiredTypes[type]) {
    const labels = data.labels;
    if (!Array.isArray(labels)) {
      errors.push('ç¼ºå°labelsæ°ç»');
    } else if (labels.length === 0) {
      errors.push('labelsæ°ç»ä¸ºç©º');
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function instantiateChart(ctx, payload, optionsTemplate, type) {
  if (!ctx) {
    return null;
  }
  if (ctx.canvas && typeof Chart !== 'undefined' && typeof Chart.getChart === 'function') {
    const existing = Chart.getChart(ctx.canvas);
    if (existing) {
      existing.destroy();
    }
  }
  const data = cloneDeep(payload && payload.data ? payload.data : {});
  const config = {
    type,
    data,
    options: cloneDeep(optionsTemplate)
  };
  return new Chart(ctx, config);
}

function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(null, args), wait || 200);
  };
}

function hydrateCharts() {
  document.querySelectorAll('.echarts-container[data-config-id]').forEach(container => {
    const configScript = document.getElementById(container.dataset.configId);
    if (!configScript) return;
    let payload;
    try {
      payload = JSON.parse(configScript.textContent);
    } catch (err) {
      console.error('Widget JSON è§£æå¤±è´¥', err);
      renderChartFallback(container, { widgetId: container.dataset.configId }, 'éç½®è§£æå¤±è´¥');
      return;
    }
    if (isWordCloudWidget(payload)) {
      // è¯äºææ¶ä¿çæåç»­ä¹æ¿æ¢ï¿½?echarts-wordcloudï¼å½åå¯ç¥è¿æç¨åæé»è¾æè½½å°canvas
      renderWordCloud(container, payload);
      return;
    }
    if (typeof echarts === 'undefined') {
      renderChartFallback(container, payload, 'ECharts æªå ï¿½?);
      return;
    }

    try {
      const myChart = echarts.init(container);
      let options = payload.data;
      if (!options || !options.series) {
         options = {
            title: { text: payload.props?.title || '' },
            tooltip: {},
            xAxis: { data: payload.data?.labels || [] },
            yAxis: {},
            series: (payload.data?.datasets || []).map(ds => ({
                name: ds.label,
                type: payload.widgetType.split('/')[1] || 'bar',
                data: ds.data
            }))
         };
      }
      myChart.setOption(options);
      chartRegistry.push(myChart);
      
      // æ·»å  resize çå¬
      window.addEventListener('resize', () => {
          myChart.resize();
      });
    } catch (err) {
      console.error('å¾è¡¨æ¸²æå¤±è´¥', err);
      renderChartFallback(container, payload, err.message);
    }
  });
}

function getExportOverlayParts() {
  const overlay = document.getElementById('export-overlay');
  if (!overlay) {
    return null;
  }
  return {
    overlay,
    status: overlay.querySelector('.export-status')
  };
}

function showExportOverlay(message) {
  const parts = getExportOverlayParts();
  if (!parts) return;
  if (message && parts.status) {
    parts.status.textContent = message;
  }
  parts.overlay.classList.add('active');
  document.body.classList.add('exporting');
}

function updateExportOverlay(message) {
  if (!message) return;
  const parts = getExportOverlayParts();
  if (parts && parts.status) {
    parts.status.textContent = message;
  }
}

function hideExportOverlay(delay) {
  const parts = getExportOverlayParts();
  if (!parts) return;
  const close = () => {
    parts.overlay.classList.remove('active');
    document.body.classList.remove('exporting');
  };
  if (delay && delay > 0) {
    setTimeout(close, delay);
  } else {
    close();
  }
}

// exportPdfå·²ç§»ï¿½?
function exportPdf() {
  // å¯¼åºæé®äº¤äºï¼ç¦ç¨æï¿½?æå¼é®ç½©ï¼ä½¿ï¿½?html2canvas + jsPDF æ¸²æ mainï¼åæ¢å¤æé®ä¸é®ï¿½?
  const target = document.querySelector('main');
  if (!target || typeof jspdf === 'undefined' || typeof jspdf.jsPDF !== 'function') {
    alert('PDFå¯¼åºä¾èµæªå°±ï¿½?);
    return;
  }
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    exportBtn.disabled = true;
  }
  showExportOverlay('æ­£å¨å¯¼åºPDFï¼è¯·ç¨ï¿½?..');
  document.body.classList.add('exporting');
  const pdf = new jspdf.jsPDF('p', 'mm', 'a4');
  try {
    if (window.pdfFontData) {
      pdf.addFileToVFS('SourceHanSerifSC-Medium.ttf', window.pdfFontData);
      pdf.addFont('SourceHanSerifSC-Medium.ttf', 'SourceHanSerif', 'normal');
      pdf.setFont('SourceHanSerif');
      console.log('PDFå­ä½å·²æåå ï¿½?);
    } else {
      console.warn('PDFå­ä½æ°æ®æªæ¾å°ï¼å°ä½¿ç¨é»è®¤å­ï¿½?);
    }
  } catch (err) {
    console.warn('Custom PDF font setup failed, fallback to default', err);
  }
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pxWidth = Math.max(
    target.scrollWidth,
    document.documentElement.scrollWidth,
    Math.round(pageWidth * 3.78)
  );
  const restoreButton = () => {
    if (exportBtn) {
      exportBtn.disabled = false;
    }
    document.body.classList.remove('exporting');
  };
  let renderTask;
  try {
    // force charts to rerender at full width before capture
    chartRegistry.forEach(chart => {
      if (chart && typeof chart.resize === 'function') {
        chart.resize();
      }
    });
    wordCloudRegistry.forEach(fn => {
      if (typeof fn === 'function') {
        try {
          fn();
        } catch (err) {
          console.error('è¯äºéæ°æ¸²æå¤±è´¥', err);
        }
      }
    });
    renderTask = pdf.html(target, {
      x: 8,
      y: 12,
      width: pageWidth - 16,
      margin: [12, 12, 20, 12],
      autoPaging: 'text',
      windowWidth: pxWidth,
      html2canvas: {
        scale: Math.min(1.5, Math.max(1.0, pageWidth / (target.clientWidth || pageWidth))),
        useCORS: true,
        scrollX: 0,
        scrollY: -window.scrollY,
        logging: false,
        allowTaint: true,
        backgroundColor: '#ffffff'
      },
      pagebreak: {
        mode: ['css', 'legacy'],
        avoid: [
          '.chapter > *',
          '.callout',
          '.chart-card',
          '.table-wrap',
          '.kpi-grid',
          '.hero-section'
        ],
        before: '.chapter-divider'
      },
      callback: (doc) => doc.save('report.pdf')
    });
  } catch (err) {
    console.error('PDF å¯¼åºå¤±è´¥', err);
    updateExportOverlay('å¯¼åºå¤±è´¥ï¼è¯·ç¨åéè¯');
    hideExportOverlay(1200);
    restoreButton();
    alert('PDFå¯¼åºå¤±è´¥ï¼è¯·ç¨åéè¯');
    return;
  }
  if (renderTask && typeof renderTask.then === 'function') {
    renderTask.then(() => {
      updateExportOverlay('å¯¼åºå®æï¼æ­£å¨ä¿ï¿½?..');
      hideExportOverlay(800);
      restoreButton();
    }).catch(err => {
      console.error('PDF å¯¼åºå¤±è´¥', err);
      updateExportOverlay('å¯¼åºå¤±è´¥ï¼è¯·ç¨åéè¯');
      hideExportOverlay(1200);
      restoreButton();
      alert('PDFå¯¼åºå¤±è´¥ï¼è¯·ç¨åéè¯');
    });
  } else {
    hideExportOverlay();
    restoreButton();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const rerenderWordclouds = debounce(() => {
    wordCloudRegistry.forEach(fn => {
      if (typeof fn === 'function') {
        fn();
      }
    });
  }, 260);
  // æ§ç Web Component ä¸»é¢æé®ï¼å·²æ³¨éï¿½?
  // const themeBtn = document.getElementById('theme-toggle');
  // if (themeBtn) {
  //   themeBtn.addEventListener('change', (e) => {
  //     if (e.detail === 'dark') {
  //       document.body.classList.add('dark-mode');
  //     } else {
  //       document.body.classList.remove('dark-mode');
  //     }
  //     chartRegistry.forEach(applyChartTheme);
  //     rerenderWordclouds();
  //   });
  // }

  // æ°ç action-btn é£æ ¼ä¸»é¢æé®
  const themeBtnNew = document.getElementById('theme-toggle-btn');
  if (themeBtnNew) {
    const sunIcon = themeBtnNew.querySelector('.sun-icon');
    const moonIcon = themeBtnNew.querySelector('.moon-icon');
    let isDark = document.body.classList.contains('dark-mode');

    const updateThemeUI = () => {
      if (isDark) {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
      } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
      }
    };
    updateThemeUI();

    themeBtnNew.addEventListener('click', () => {
      isDark = !isDark;
      if (isDark) {
        document.body.classList.add('dark-mode');
      } else {
        document.body.classList.remove('dark-mode');
      }
      updateThemeUI();
      chartRegistry.forEach(applyChartTheme);
      rerenderWordclouds();
    });
  }
  const printBtn = document.getElementById('print-btn');
  if (printBtn) {
    // æå°æé®ï¼ç´æ¥è°ç¨æµè§å¨æå°ï¼ä¾ï¿½?@media print æ§å¶å¸å±
    printBtn.addEventListener('click', () => window.print());
  }
  // ä¸ºæï¿½?action-btn æ·»å é¼ æ è¿½è¸ªåæææ
  document.querySelectorAll('.action-btn').forEach(btn => {
    btn.addEventListener('mousemove', (e) => {
      const rect = btn.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      btn.style.setProperty('--mouse-x', x + '%');
      btn.style.setProperty('--mouse-y', y + '%');
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.setProperty('--mouse-x', '50%');
      btn.style.setProperty('--mouse-y', '50%');
    });
  });
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    // å¯¼åºæé®ï¼è°ï¿½?exportPdfï¼html2canvas + jsPDFï¼ï¼å¹¶é©±å¨é®ï¿½?è¿åº¦æç¤º
    exportBtn.addEventListener('click', exportPdf);
  }
  window.addEventListener('resize', rerenderWordclouds);
  hydrateCharts();
});
</script>
""".strip()


__all__ = ["HTMLRenderer"]
