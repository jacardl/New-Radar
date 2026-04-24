"""
å¾è¡¨å°SVGè½¬æ¢å?- å°Chart.jsæ°æ®è½¬æ¢ä¸ºç¢éSVGå¾å½¢

æ¯æçå¾è¡¨ç±»å?
- line: æçº¿å?
- bar: æ±ç¶å?
- pie: é¥¼å¾
- doughnut: åç¯å?
- radar: é·è¾¾å?
- polarArea: æå°åºåå?
- scatter: æ£ç¹å?
"""

from __future__ import annotations

import base64
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

try:
    import matplotlib
    matplotlib.use('Agg')  # ä½¿ç¨éGUIåç«¯
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm
    from matplotlib.patches import Wedge, Rectangle
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("Matplotlibæªå®è£ï¼PDFå¾è¡¨ç¢éæ¸²æåè½å°ä¸å¯ç¨")

# å¯éä¾èµï¼scipyç¨äºæ²çº¿å¹³æ»
try:
    from scipy.interpolate import make_interp_spline
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.info("Scipyæªå®è£ï¼æçº¿å¾å°ä¸æ¯ææ²çº¿å¹³æ»åè½ï¼ä¸å½±ååºæ¬æ¸²æï¼")


class ChartToSVGConverter:
    """
    å°Chart.jså¾è¡¨æ°æ®è½¬æ¢ä¸ºSVGç¢éå¾å½¢
    """

    # é»è®¤é¢è²è°è²æ¿ï¼ä¼åçï¼æäº®ä¸æåºåï¼?
    DEFAULT_COLORS = [
        '#4A90E2', '#E85D75', '#50C878', '#FFB347',  # æäº®èãçççº¢ãç¿ ç»¿ãæ©é»?
        '#9B59B6', '#3498DB', '#E67E22', '#16A085',  # ç´«è²ãå¤©èãæ©è²ãéè?
        '#F39C12', '#D35400', '#27AE60', '#8E44AD'   # éè²ãæ·±æ©ãç»¿è²ãç´«ç½å°
    ]

    # CSSåéå°é¢è²çæ å°è¡¨ï¼ä¼åçï¼ä½¿ç¨æ´æäº®ãæ´æµçé¢è²ï¼?
    CSS_VAR_COLOR_MAP = {
        'var(--color-accent)': '#4A90E2',        # æäº®èè²ï¼ä»#007AFFæ¹ä¸ºæ´æµï¼?
        'var(--re-accent-color)': '#4A90E2',     # æäº®èè²
        'var(--re-accent-color-translucent)': (0.29, 0.565, 0.886, 0.08),  # èè²ææµéæ rgba(74, 144, 226, 0.08)
        'var(--color-kpi-down)': '#E85D75',      # çççº¢è²ï¼ä»#DC3545æ¹ä¸ºæ´æåï¼
        'var(--re-danger-color)': '#E85D75',     # çççº¢è²
        'var(--re-danger-color-translucent)': (0.91, 0.365, 0.459, 0.08),  # çº¢è²ææµéæ rgba(232, 93, 117, 0.08)
        'var(--color-warning)': '#FFB347',       # æåæ©é»è²ï¼ä»?FFC107æ¹ä¸ºæ´æµï¼?
        'var(--re-warning-color)': '#FFB347',    # æåæ©é»è?
        'var(--re-warning-color-translucent)': (1.0, 0.702, 0.278, 0.08),  # é»è²ææµéæ rgba(255, 179, 71, 0.08)
        'var(--color-success)': '#50C878',       # ç¿ ç»¿è²ï¼ä»?28A745æ¹ä¸ºæ´æäº®ï¼
        'var(--re-success-color)': '#50C878',    # ç¿ ç»¿è?
        'var(--re-success-color-translucent)': (0.314, 0.784, 0.471, 0.08),  # ç»¿è²ææµéæ rgba(80, 200, 120, 0.08)
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
        'var(--color-primary)': '#3498DB',       # å¤©èè?
        'var(--color-secondary)': '#95A5A6',     # æµç°è?
    }

    # æ¯æè§£æ rgba(var(--color-primary-rgb), 0.5) è¿ç±»æ ¼å¼çååºæ å°?
    CSS_VAR_RGB_MAP = {
        'color-primary-rgb': (52, 152, 219),
        'color-tone-up-rgb': (80, 200, 120),
        'color-tone-down-rgb': (232, 93, 117),
        'color-accent-positive-rgb': (80, 200, 120),
        'color-accent-neutral-rgb': (149, 165, 166),
    }

    def __init__(self, font_path: Optional[str] = None):
        """
        åå§åè½¬æ¢å¨

        åæ°:
            font_path: ä¸­æå­ä½è·¯å¾ï¼å¯éï¼
        """
        if not MATPLOTLIB_AVAILABLE:
            raise RuntimeError("Matplotlibæªå®è£ï¼è¯·è¿è¡? pip install matplotlib")

        self.font_path = font_path
        self._setup_chinese_font()

    def _setup_chinese_font(self):
        """éç½®ä¸­æå­ä½"""
        if self.font_path:
            try:
                # æ·»å èªå®ä¹å­ä½?
                fm.fontManager.addfont(self.font_path)
                # è®¾ç½®é»è®¤å­ä½
                font_prop = fm.FontProperties(fname=self.font_path)
                plt.rcParams['font.family'] = font_prop.get_name()
                plt.rcParams['axes.unicode_minus'] = False  # è§£å³è´å·æ¾ç¤ºé®é¢
                logger.info(f"å·²å è½½ä¸­æå­ä½? {self.font_path}")
            except Exception as e:
                logger.warning(f"å è½½ä¸­æå­ä½å¤±è´¥: {e}ï¼å°ä½¿ç¨ç³»ç»é»è®¤å­ä½")
        else:
            # å°è¯ä½¿ç¨ç³»ç»ä¸­æå­ä½
            try:
                plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as e:
                logger.warning(f"éç½®ä¸­æå­ä½å¤±è´¥: {e}")

    def convert_widget_to_svg(
        self,
        widget_data: Dict[str, Any],
        width: int = 800,
        height: int = 500,
        dpi: int = 100
    ) -> Optional[str]:
        """
        å°widgetæ°æ®è½¬æ¢ä¸ºSVGå­ç¬¦ä¸?

        åæ°:
            widget_data: widgetåæ°æ®ï¼åå«widgetTypeataropsï¼?
            width: å¾è¡¨å®½åº¦ï¼åç´ ï¼
            height: å¾è¡¨é«åº¦ï¼åç´ ï¼
            dpi: DPIè®¾ç½®

        è¿å:
            str: SVGå­ç¬¦ä¸²ï¼å¤±è´¥è¿åNone
        """
        try:
            # æåå¾è¡¨ç±»å
            widget_type = widget_data.get('widgetType', '')
            if not widget_type or not widget_type.startswith('chart.js'):
                logger.warning(f"ä¸æ¯æçwidgetç±»å: {widget_type}")
                return None

            # ä»widgetTypeä¸­æåå¾è¡¨ç±»åï¼ä¾å¦ "chart.js/line" -> "line"
            chart_type = widget_type.split('/')[-1] if '/' in widget_type else 'bar'

            # ä¹æ£æ¥propsä¸­çtype
            props = widget_data.get('props', {})
            if props.get('type'):
                chart_type = props['type']

            # Chart.js v4å·²ç§»é¤horizontalBarç±»åï¼è¿éèªå¨éçº§ä¸ºbarå¹¶è®¾ç½®æ¨ªååæ ?
            horizontal_bar = False
            if chart_type and str(chart_type).lower() == 'horizontalbar':
                chart_type = 'bar'
                horizontal_bar = True

            # æ¯æéè¿indexAxis: 'y' å¼ºå¶æ¨ªåæ±ç¶å?
            if isinstance(props, dict):
                options = props.get('options') or {}
                index_axis = (options.get('indexAxis') or props.get('indexAxis') or '').lower()
                if index_axis == 'y':
                    horizontal_bar = True

            # æåæ°æ®
            data = widget_data.get('data', {})
            if not data:
                logger.warning("å¾è¡¨æ°æ®ä¸ºç©º")
                return None

            # æ ¹æ®å¾è¡¨ç±»åè°ç¨ç¸åºçæ¸²ææ¹æ³?
            if 'wordcloud' in str(chart_type).lower():
                # è¯äºç±ä¸ç¨æ¸²æé»è¾å¤çï¼è¿éè·³è¿SVGè½¬æ¢ä»¥é¿ååè­?
                logger.debug("æ£æµå°è¯äºå¾è¡¨ï¼è·³è¿chart_to_svgè½¬æ¢")
                return None

            # åæ´¾æ¸²ææ¹æ³ï¼ç¹æ®å¤çæ¨ªåæ±ç¶å¾
            if chart_type == 'bar':
                return self._render_bar(data, props, width, height, dpi, horizontal=horizontal_bar)
            elif chart_type == 'bubble':
                return self._render_bubble(data, props, width, height, dpi)
            else:
                render_method = getattr(self, f'_render_{chart_type}', None)
                if not render_method:
                    logger.warning(f"ä¸æ¯æçå¾è¡¨ç±»å: {chart_type}")
                    return None

            # åå»ºå¾è¡¨å¹¶è½¬æ¢ä¸ºSVG
            return render_method(data, props, width, height, dpi)

        except Exception as e:
            logger.error(f"è½¬æ¢å¾è¡¨ä¸ºSVGå¤±è´¥: {e}", exc_info=True)
            return None

    def _create_figure(
        self,
        width: int,
        height: int,
        dpi: int,
        title: Optional[str] = None
    ) -> Tuple[Any, Any]:
        """
        åå»ºmatplotlibå¾è¡¨

        è¿å:
            tuple: (fig, ax)
        """
        fig, ax = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)

        if title:
            ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        return fig, ax

    def _parse_color(self, color: Any) -> Any:
        """
        è§£æé¢è²å¼ï¼å°CSSæ ¼å¼è½¬æ¢ä¸ºmatplotlibæ¯æçæ ¼å¼?

        åæ°:
            color: é¢è²å¼ï¼å¯è½æ¯CSSæ ¼å¼å¦rgba()æåå­è¿å¶æCSSåéï¼?

        è¿å:
            matplotlibæ¯æçé¢è²æ ¼å¼ï¼hexå­ç¬¦ä¸²æRGB(A)åç»ï¼?
        """
        if color is None:
            return None

        # å¤çnumpyæ°ç»ï¼ç»ä¸è½¬ä¸ºåçåè¡¨
        _np = globals().get("np")
        if _np is not None and hasattr(_np, "ndarray") and isinstance(color, _np.ndarray):
            color = color.tolist()

        # ç´æ¥éä¼ å·²ç»æ¯åºåçé¢è²ï¼å¦ (r,g,b,a)ï¼ï¼é¿åè¢«è½¬æå­ç¬¦ä¸²åå¤±æ?
        if isinstance(color, (list, tuple)):
            if len(color) in (3, 4) and all(isinstance(c, (int, float)) for c in color):
                normalized = []
                for idx, channel in enumerate(color):
                    # Matplotlibæ¥å0-1ä¹é´çæµ®ç¹æ°ï¼è¥å?1åæ0-255æ¥æºå½ä¸å?
                    value = float(channel)
                    if value > 1:
                        value = value / 255.0
                    # åªå¯¹RGBééåå¼ºå¶è£åªï¼alphaæ?-1è£åª
                    if idx < 3:
                        value = max(0.0, min(value, 1.0))
                    else:
                        value = max(0.0, min(value, 1.0))
                    normalized.append(value)
                return tuple(normalized)

            try:
                return tuple(color)
            except Exception:
                return color

        # å¶ä½éå­ç¬¦ä¸²ç±»åä¿æåæå­ç¬¦ä¸²åéç­ç¥
        if not isinstance(color, str):
            return str(color)

        color = color.strip()

        # å¤ç rgba(var(--color-primary-rgb), 0.5) / rgb(var(--color-primary-rgb))
        var_rgba_pattern = r'rgba?\(var\(--([\w-]+)\)\s*(?:,\s*([\d.]+))?\)'
        match = re.match(var_rgba_pattern, color)
        if match:
            var_name, alpha_str = match.groups()
            rgb_tuple = self.CSS_VAR_RGB_MAP.get(var_name)

            # å¼å®¹ç¼ºå° -rgb åç¼çåæ³?
            if not rgb_tuple:
                if var_name.endswith('-rgb'):
                    rgb_tuple = self.CSS_VAR_RGB_MAP.get(var_name[:-4])
                else:
                    rgb_tuple = self.CSS_VAR_RGB_MAP.get(f"{var_name}-rgb")

            if rgb_tuple:
                r, g, b = rgb_tuple
                alpha = float(alpha_str) if alpha_str is not None else 1.0
                return (r / 255, g / 255, b / 255, alpha)

        # ãå¢å¼ºãå¤çCSSåéï¼ä¾å¦?var(--color-accent)
        # ä½¿ç¨é¢å®ä¹çé¢è²æ å°è¡¨æ¿ä»£CSSåéï¼ç¡®ä¿ä¸ååéæä¸åçé¢è?
        if color.startswith('var('):
            # è§£æ var(--token, fallback) å½¢å¼
            fb_match = re.match(r'^var\(\s*--[^,)+]+,\s*([^)]+)\)', color)
            if fb_match:
                fb_raw = fb_match.group(1).strip()
                fb_color = self._parse_color(fb_raw)
                if fb_color:
                    return fb_color
            # å°è¯ä»æ å°è¡¨ä¸­æ¥æ¾å¯¹åºçé¢è²
            mapped_color = self.CSS_VAR_COLOR_MAP.get(color)
            if mapped_color:
                return mapped_color
            # å¦ææ å°è¡¨ä¸­æ²¡æï¼å°è¯ä»åéåæ¨æ­é¢è²ç±»å?
            if 'accent' in color or 'primary' in color:
                return '#007AFF'  # èè²
            elif 'danger' in color or 'down' in color or 'error' in color:
                return '#DC3545'  # çº¢è²
            elif 'warning' in color:
                return '#FFC107'  # é»è²
            elif 'success' in color or 'up' in color:
                return '#28A745'  # ç»¿è²
            # é»è®¤è¿åèè²
            return '#36A2EB'

        # å¤çrgba(r, g, b, a)æ ¼å¼
        rgba_pattern = r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)'
        match = re.match(rgba_pattern, color)
        if match:
            r, g, b, a = match.groups()
            # è½¬æ¢ä¸ºmatplotlibæ ¼å¼ (r/255, g/255, b/255, a)
            return (int(r)/255, int(g)/255, int(b)/255, float(a))

        # å¤çrgb(r, g, b)æ ¼å¼
        rgb_pattern = r'rgb\((\d+),\s*(\d+),\s*(\d+)\)'
        match = re.match(rgb_pattern, color)
        if match:
            r, g, b = match.groups()
            # è½¬æ¢ä¸ºmatplotlibæ ¼å¼ (r/255, g/255, b/255)
            return (int(r)/255, int(g)/255, int(b)/255)

        # å¶ä»æ ¼å¼ï¼åå­è¿å¶ãé¢è²åç­ï¼ç´æ¥è¿å
        return color

    def _ensure_visible_color(self, color: Any, fallback: str, min_alpha: float = 0.6) -> Any:
        """
        ç¡®ä¿é¢è²å¨æ¸²ææ¶å¯è§ï¼é¿åéæå¼å¹¶æåè¿ä½çä¸éæåº?
        """
        base_color = fallback if color in (None, "", "transparent") else color
        parsed = self._parse_color(base_color)
        fallback_parsed = self._parse_color(fallback)

        if isinstance(parsed, tuple):
            if len(parsed) == 4:
                r, g, b, a = parsed
                return (r, g, b, max(a, min_alpha))
            return parsed

        if isinstance(parsed, str) and parsed.lower() == "transparent":
            return fallback_parsed

        return parsed if parsed is not None else fallback_parsed

    def _get_colors(self, datasets: List[Dict[str, Any]]) -> List[str]:
        """
        è·åå¾è¡¨é¢è²

        ä¼åä½¿ç¨datasetä¸­å®ä¹çé¢è²ï¼å¦åä½¿ç¨é»è®¤è°è²æ¿
        """
        colors = []
        for i, dataset in enumerate(datasets):
            # å°è¯è·ååç§å¯è½çé¢è²å­æ®?
            color = (
                dataset.get('backgroundColor') or
                dataset.get('borderColor') or
                dataset.get('color') or
                self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
            )

            # å¦ææ¯é¢è²æ°ç»ï¼åç¬¬ä¸ä¸?
            if isinstance(color, list):
                color = color[0] if color else self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]

            # è§£æé¢è²æ ¼å¼
            color = self._parse_color(color)

            colors.append(color)

        return colors

    def _align_labels_and_data(
        self,
        labels: Any,
        dataset_data: Any,
        chart_type: str,
        require_positive_sum: bool = False
    ) -> Tuple[List[str], List[float]]:
        """
        å¯¹é½ç±»å«åå¾è¡¨çæ ç­¾ä¸æ°æ®é¿åº¦ï¼å¹¶æ¸çéæ°å¼å¼

        Matplotlibçé¥¼å?åç¯å¾è¦æ±labelsä¸æ°æ®é¿åº¦ä¸è´ï¼å¦åä¼æåºéè¯¯
        """
        original_label_len = len(labels) if isinstance(labels, list) else 0
        original_data_len = len(dataset_data) if isinstance(dataset_data, list) else 0

        aligned_labels = [str(label) for label in labels] if isinstance(labels, list) else []
        raw_data = dataset_data if isinstance(dataset_data, list) else []

        cleaned_data: List[float] = []
        for value in raw_data:
            try:
                numeric = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                numeric = 0.0
            if numeric < 0:
                numeric = 0.0
            cleaned_data.append(numeric)

        target_len = max(len(aligned_labels), len(cleaned_data))
        if target_len == 0:
            return [], []

        if len(aligned_labels) < target_len:
            start = len(aligned_labels)
            aligned_labels.extend([f"æªå½å{start + idx + 1}" for idx in range(target_len - start)])

        if len(cleaned_data) < target_len:
            cleaned_data.extend([0.0] * (target_len - len(cleaned_data)))

        if original_label_len != original_data_len:
            logger.warning(
                f"{chart_type}å¾labelsé¿åº¦({original_label_len})ä¸dataé¿åº¦({original_data_len})ä¸ä¸è´ï¼"
                f"å·²å¯¹é½ä¸º{target_len}"
            )

        if require_positive_sum and not any(value > 0 for value in cleaned_data):
            logger.warning(f"{chart_type}å¾æ°æ®ä¸ºç©ºï¼è·³è¿æ¸²æ")
            return [], []

        return aligned_labels[:target_len], cleaned_data[:target_len]

    def _figure_to_svg(self, fig: Any) -> str:
        """
        å°matplotlibå¾è¡¨è½¬æ¢ä¸ºSVGå­ç¬¦ä¸?
        """
        svg_buffer = io.BytesIO()
        fig.savefig(svg_buffer, format='svg', bbox_inches='tight', transparent=False, facecolor='white')
        plt.close(fig)

        svg_buffer.seek(0)
        svg_string = svg_buffer.getvalue().decode('utf-8')

        return svg_string

    def _render_line(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """
        æ¸²ææçº¿å¾ï¼å¢å¼ºçï¼

        æ¯æç¹æ§ï¼
        - å¤yè½´ï¼yAxisID: 'y', 'y1', 'y2', 'y3'...ï¼?
        - å¡«ååºåï¼fill: trueï¼?
        - éæåº¦ï¼backgroundColorä¸­çalphaééï¼?
        - çº¿æ¡æ ·å¼ï¼tensionæ²çº¿å¹³æ»ï¼?
        """
        try:
            labels = data.get('labels') or []
            datasets = data.get('datasets') or []

            has_object_points = any(
                isinstance(ds, dict)
                and isinstance(ds.get('data'), list)
                and any(isinstance(pt, dict) and ('x' in pt or 'y' in pt) for pt in ds.get('data'))
                for ds in datasets
            )

            if (not datasets) or ((not labels) and not has_object_points):
                return None

            # æ¶éææå¯ä¸çyAxisID
            y_axis_ids = []
            for dataset in datasets:
                y_axis_id = dataset.get('yAxisID', 'y')
                if y_axis_id not in y_axis_ids:
                    y_axis_ids.append(y_axis_id)

            # ç¡®ä¿'y'æ¯ç¬¬ä¸ä¸ªè½´
            if 'y' in y_axis_ids:
                y_axis_ids.remove('y')
                y_axis_ids.insert(0, 'y')

            # æ£æ¥æ¯å¦æå¤ä¸ªyè½?
            has_multiple_axes = len(y_axis_ids) > 1

            title = props.get('title')
            options = props.get('options', {})
            scales = options.get('scales', {})
            x_tick_labels = list(labels) if isinstance(labels, list) else []

            # åå»ºå¾è¡¨åå¤ä¸ªyè½?
            fig, ax1 = plt.subplots(figsize=(width/dpi, height/dpi), dpi=dpi)

            if title:
                ax1.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # åå»ºyè½´æ å°å­å?
            axes = {'y': ax1}

            if has_multiple_axes:
                # ç»è®¡æ¯ä¸ªä½ç½®(left/right)çè½´æ°é,ç¨äºè®¡ç®åç§»
                left_axes_count = 0
                right_axes_count = 0

                # ä¸ºæ¯ä¸ªé¢å¤çyAxisIDåå»ºæ°çyè½?
                for y_axis_id in y_axis_ids[1:]:
                    if y_axis_id == 'y':
                        continue

                    # åå»ºæ°çyè½?
                    new_ax = ax1.twinx()
                    axes[y_axis_id] = new_ax

                    # ä»scaleséç½®ä¸­è·åè½´çä½ç½?
                    y_config = scales.get(y_axis_id, {})
                    position = y_config.get('position', 'right')

                    if position == 'left':
                        # å·¦ä¾§é¢å¤è½?åå·¦åç§»
                        if left_axes_count > 0:
                            new_ax.spines['left'].set_position(('outward', 60 * left_axes_count))
                        new_ax.yaxis.set_label_position('left')
                        new_ax.yaxis.set_ticks_position('left')
                        left_axes_count += 1
                    else:
                        # å³ä¾§é¢å¤è½?åå³åç§»
                        if right_axes_count > 0:
                            new_ax.spines['right'].set_position(('outward', 60 * right_axes_count))
                        right_axes_count += 1

            colors = self._get_colors(datasets)

            # æ¶éæ¯ä¸ªyè½´ççº¿æ¡åå¡«åä¿¡æ¯ç¨äºå¾ä¾?
            axis_lines = {axis_id: [] for axis_id in y_axis_ids}
            legend_handles = []  # å¾ä¾å¥æ
            legend_labels = []   # å¾ä¾æ ç­¾

            # ç»å¶æ¯ä¸ªæ°æ®ç³»å
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'ç³»å{i+1}')
                color = colors[i]

                # è·åéç½®
                y_axis_id = dataset.get('yAxisID', 'y')
                fill = True  # å¼ºå¶å¼å¯å¡«åï¼ä¾¿äºå¯¹æ¯
                tension = dataset.get('tension', 0)  # 0è¡¨ç¤ºç´çº¿ï¼?.4è¡¨ç¤ºå¹³æ»æ²çº¿
                border_color = self._parse_color(dataset.get('borderColor', color))
                background_color = self._parse_color(dataset.get('backgroundColor', color))

                # éæ©å¯¹åºçåæ è½´
                ax = axes.get(y_axis_id, ax1)

                is_object_data = isinstance(dataset_data, list) and any(
                    isinstance(point, dict) and ('x' in point or 'y' in point)
                    for point in dataset_data
                )

                if is_object_data:
                    x_data = []
                    y_data = []
                    annotations = []

                    for idx, point in enumerate(dataset_data):
                        if not isinstance(point, dict):
                            continue

                        label_text = str(point.get('x', f"ç¹{idx + 1}"))
                        if len(x_tick_labels) < len(dataset_data):
                            x_tick_labels.append(label_text)

                        x_data.append(len(x_data))

                        y_val = point.get('y', 0)
                        try:
                            y_val = float(y_val)
                        except (TypeError, ValueError):
                            y_val = 0
                        y_data.append(y_val)
                        annotations.append(point.get('event'))

                    if not x_data:
                        continue

                    line, = ax.plot(x_data, y_data, marker='o', label=label,
                                    color=border_color, linewidth=2, markersize=6)

                    if fill:
                        ax.fill_between(x_data, y_data, alpha=0.2, color=background_color)

                    for pos, y_val, text in zip(x_data, y_data, annotations):
                        if text:
                            ax.annotate(
                                text,
                                (pos, y_val),
                                textcoords='offset points',
                                xytext=(0, 8),
                                ha='center',
                                fontsize=8,
                                rotation=20
                            )
                else:
                    # ç»å¶æçº¿
                    x_data = range(len(labels))

                    # æ ¹æ®tensionå¼å³å®æ¯å¦å¹³æ»?
                    if tension > 0 and SCIPY_AVAILABLE:
                        # ä½¿ç¨æ ·æ¡æå¼å¹³æ»æ²çº¿ï¼éè¦scipyï¼?
                        if len(dataset_data) >= 4:  # è³å°éè¦?ä¸ªç¹æè½å¹³æ»
                            try:
                                x_smooth = np.linspace(0, len(labels)-1, len(labels)*3)
                                spl = make_interp_spline(x_data, dataset_data, k=min(3, len(dataset_data)-1))
                                y_smooth = spl(x_smooth)
                                line, = ax.plot(x_smooth, y_smooth, label=label, color=border_color, linewidth=2)

                                # å¦æéè¦å¡«åï¼ä½¿ç¨æä½éæåº¦é¿åé®æ¡ï¼
                                if fill:
                                    ax.fill_between(x_smooth, y_smooth, alpha=0.2, color=background_color)
                            except:
                                # å¦æå¹³æ»å¤±è´¥ï¼ä½¿ç¨æ®éæçº?
                                line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                              color=border_color, linewidth=2, markersize=6)
                                if fill:
                                    ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)
                        else:
                            line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                          color=border_color, linewidth=2, markersize=6)
                            if fill:
                                ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)
                    else:
                        # ç´çº¿è¿æ¥ï¼tension=0æscipyä¸å¯ç¨ï¼
                        line, = ax.plot(x_data, dataset_data, marker='o', label=label,
                                      color=border_color, linewidth=2, markersize=6)

                        # å¦æéè¦å¡«åï¼ä½¿ç¨æä½éæåº¦é¿åé®æ¡ï¼
                        if fill:
                            ax.fill_between(x_data, dataset_data, alpha=0.2, color=background_color)

                # è®°å½è¿æ¡çº¿å±äºåªä¸ªè½´
                axis_lines[y_axis_id].append(line)

                # åå»ºå¾ä¾é¡¹ï¼å¦ææå¡«åï¼åå»ºå¸¦å¡«åèæ¯çå¾ä¾
                if fill:
                    # åå»ºä¸ä¸ªç©å½¢patchä½ä¸ºå¡«åèæ¯ï¼ä½¿ç¨ç¨é«éæåº¦ä»¥ä¾¿å¨å¾ä¾ä¸­å¯è§ï¼
                    fill_patch = Rectangle((0, 0), 1, 1,
                                          facecolor=background_color,
                                          edgecolor='none',
                                          alpha=0.15)
                    # ç»åçº¿æ¡åå¡«åpatch
                    legend_handles.append((line, fill_patch))
                    legend_labels.append(label)
                else:
                    legend_handles.append(line)
                    legend_labels.append(label)

            # è®¾ç½®xè½´æ ç­?
            if x_tick_labels:
                ax1.set_xticks(range(len(x_tick_labels)))
                ax1.set_xticklabels(x_tick_labels, rotation=45, ha='right')

            # è®¾ç½®yè½´æ ç­¾åæ é¢
            for y_axis_id, ax in axes.items():
                y_config = scales.get(y_axis_id, {})
                y_title = y_config.get('title', {}).get('text', '')

                if y_title:
                    ax.set_ylabel(y_title, fontsize=11)

                # è®¾ç½®yè½´æ ç­¾é¢è²ï¼å¦æè¯¥è½´åªæä¸æ¡çº¿ï¼ä½¿ç¨è¯¥çº¿çé¢è²ï¼?
                if len(axis_lines[y_axis_id]) == 1:
                    line_color = axis_lines[y_axis_id][0].get_color()
                    ax.tick_params(axis='y', labelcolor=line_color)
                    ax.yaxis.label.set_color(line_color)

            # è®¾ç½®ç½æ ¼ï¼åªå¨ä¸»è½´æ¾ç¤ºï¼
            ax1.grid(True, alpha=0.3, linestyle='--')
            for y_axis_id in y_axis_ids[1:]:
                if y_axis_id in axes:
                    axes[y_axis_id].grid(False)

            # åå»ºå¾ä¾
            if has_multiple_axes or len(datasets) > 1:
                # ä½¿ç¨èªå®ä¹çlegend_handlesålegend_labels
                from matplotlib.legend_handler import HandlerTuple

                ax1.legend(legend_handles, legend_labels,
                          loc='best',
                          framealpha=0.9,
                          handler_map={tuple: HandlerTuple(ndivide=None)})

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²ææçº¿å¾å¤±è´? {e}", exc_info=True)
            return None

    def _render_bar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int,
        horizontal: bool = False
    ) -> Optional[str]:
        """æ¸²ææ±ç¶å¾ï¼æ¯ææ¨ªåbarhï¼?""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # è®¡ç®æ±å­ä½ç½®
            positions = np.arange(len(labels))
            width_bar = 0.8 / len(datasets) if len(datasets) > 1 else 0.6

            # æ¨ªå/çºµåç»å¶
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'ç³»å{i+1}')
                color = colors[i]

                offset = (i - len(datasets)/2 + 0.5) * width_bar

                if horizontal:
                    ax.barh(
                        positions + offset,
                        dataset_data,
                        height=width_bar,
                        label=label,
                        color=color,
                        alpha=0.8,
                        edgecolor='white',
                        linewidth=0.5
                    )
                else:
                    ax.bar(
                        positions + offset,
                        dataset_data,
                        width_bar,
                        label=label,
                        color=color,
                        alpha=0.8,
                        edgecolor='white',
                        linewidth=0.5
                    )

            # è½´æ ç­?ç½æ ¼
            if horizontal:
                ax.set_yticks(positions)
                ax.set_yticklabels(labels)
                ax.invert_yaxis()  # ä¸Chart.jsæ¨ªåæåä¿æä¸è?
                ax.grid(True, alpha=0.3, linestyle='--', axis='x')
            else:
                ax.set_xticks(positions)
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.grid(True, alpha=0.3, linestyle='--', axis='y')

            # æ¾ç¤ºå¾ä¾
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²ææ±ç¶å¾å¤±è´? {e}")
            return None

    def _render_bubble(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²ææ°æ³¡å?""
        try:
            datasets = data.get('datasets', [])
            if not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)
            colors = self._get_colors(datasets)

            def _safe_radius(raw) -> float:
                """å°è¾å¥åå¾å®å¨è½¬ä¸ºæµ®ç¹å¹¶è®¾ç½®æå°éå¼ï¼é¿åæ°æ³¡å®å¨æ¶å¤±"""
                try:
                    val = float(raw)
                    return max(val, 0.5)
                except Exception:
                    return 1.0

            all_x: list[float] = []
            all_y: list[float] = []
            max_r: float = 0.0

            for i, dataset in enumerate(datasets):
                points = dataset.get('data', [])
                label = dataset.get('label', f'ç³»å{i+1}')
                color = colors[i]

                if points and isinstance(points[0], dict):
                    xs = [p.get('x', 0) for p in points]
                    ys = [p.get('y', 0) for p in points]
                    rs = [_safe_radius(p.get('r', 1)) for p in points]
                else:
                    xs = list(range(len(points)))
                    ys = points
                    rs = [1.0 for _ in points]

                all_x.extend(xs)
                all_y.extend(ys)
                if rs:
                    max_r = max(max_r, max(rs))

                # éåº¦æ¾å¤§åå¾ï¼è¿ä¼¼Chart.jsåç´ å°ºå¯¸ï¼å¨æå°ºåº¦ï¼é¿åè¿å¤§é®æ¡ï¼?
                size_scale = 8.0 if max_r <= 20 else 6.5
                sizes = [(r * size_scale) ** 2 for r in rs]

                ax.scatter(
                    xs,
                    ys,
                    s=sizes,
                    label=label,
                    color=color,
                    alpha=0.45,
                    edgecolors='white',
                    linewidth=0.6
                )

            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # éåº¦çç½ï¼é¿åå¤§æ°æ³¡è¢«è£å?
            if all_x and all_y:
                x_min, x_max = min(all_x), max(all_x)
                y_min, y_max = min(all_y), max(all_y)
                x_span = max(x_max - x_min, 1e-6)
                y_span = max(y_max - y_min, 1e-6)
                pad_x = max(x_span * 0.12, max_r * 1.2)
                pad_y = max(y_span * 0.12, max_r * 1.2)
                ax.set_xlim(x_min - pad_x, x_max + pad_x)
                ax.set_ylim(y_min - pad_y, y_max + pad_y)
                # é¢å¤å®å¨è¾¹è·
                ax.margins(x=0.05, y=0.05)

            ax.grid(True, alpha=0.3, linestyle='--')
            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²ææ°æ³¡å¾å¤±è´? {e}", exc_info=True)
            return None

    def _render_pie(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²æé¥¼å¾"""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # é¥¼å¾åªä½¿ç¨ç¬¬ä¸ä¸ªæ°æ®é
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="é¥?,
                require_positive_sum=True
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # è·åé¢è²
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # ç»å¶é¥¼å¾
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 10}
            )

            # è®¾ç½®ç¾åæ¯æå­ä¸ºç½è²
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')  # ä¿æåå½¢

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²æé¥¼å¾å¤±è´¥: {e}")
            return None

    def _render_doughnut(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²æåç¯å?""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # åç¯å¾åªä½¿ç¨ç¬¬ä¸ä¸ªæ°æ®é
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="åç¯",
                require_positive_sum=True
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            # è·åé¢è²
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # ç»å¶åç¯å¾ï¼éè¿è®¾ç½®wedgepropså®ç°ä¸­ç©ºææï¼?
            wedges, texts, autotexts = ax.pie(
                dataset_data,
                labels=labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                wedgeprops=dict(width=0.5, edgecolor='white'),
                textprops={'fontsize': 10}
            )

            # è®¾ç½®ç¾åæ¯æå­?
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')

            ax.axis('equal')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²æåç¯å¾å¤±è´? {e}")
            return None

    def _render_radar(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²æé·è¾¾å?""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)

            # åå»ºæåæ å­å?
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            colors = self._get_colors(datasets)

            # è®¡ç®è§åº¦
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
            angles += angles[:1]  # é­åå¾å½¢

            # ç»å¶æ¯ä¸ªæ°æ®ç³»å
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'ç³»å{i+1}')
                color = colors[i]

                # é­åæ°æ®
                values = dataset_data + dataset_data[:1]

                # ç»å¶é·è¾¾å?
                ax.plot(angles, values, 'o-', linewidth=2, label=label, color=color)
                ax.fill(angles, values, alpha=0.25, color=color)

            # è®¾ç½®æ ç­¾
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels)

            # æ¾ç¤ºå¾ä¾
            if len(datasets) > 1:
                ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²æé·è¾¾å¾å¤±è´? {e}")
            return None

    def _render_scatter(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²ææ£ç¹å?""
        try:
            datasets = data.get('datasets', [])

            if not datasets:
                return None

            title = props.get('title')
            fig, ax = self._create_figure(width, height, dpi, title)

            colors = self._get_colors(datasets)

            # ç»å¶æ¯ä¸ªæ°æ®ç³»å
            for i, dataset in enumerate(datasets):
                dataset_data = dataset.get('data', [])
                label = dataset.get('label', f'ç³»å{i+1}')
                color = colors[i]

                # æåxåyåæ 
                if dataset_data and isinstance(dataset_data[0], dict):
                    x_values = [point.get('x', 0) for point in dataset_data]
                    y_values = [point.get('y', 0) for point in dataset_data]
                else:
                    # å¦æä¸æ¯{x,y}æ ¼å¼ï¼ä½¿ç¨ç´¢å¼ä½ä¸ºx
                    x_values = range(len(dataset_data))
                    y_values = dataset_data

                ax.scatter(
                    x_values,
                    y_values,
                    label=label,
                    color=color,
                    s=50,
                    alpha=0.6,
                    edgecolors='white',
                    linewidth=0.5
                )

            # æ¾ç¤ºå¾ä¾
            if len(datasets) > 1:
                ax.legend(loc='best', framealpha=0.9)

            # ç½æ ¼
            ax.grid(True, alpha=0.3, linestyle='--')

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²ææ£ç¹å¾å¤±è´? {e}")
            return None

    def _render_polarArea(
        self,
        data: Dict[str, Any],
        props: Dict[str, Any],
        width: int,
        height: int,
        dpi: int
    ) -> Optional[str]:
        """æ¸²ææå°åºåå?""
        try:
            labels = data.get('labels', [])
            datasets = data.get('datasets', [])

            if not labels or not datasets:
                return None

            # åªä½¿ç¨ç¬¬ä¸ä¸ªæ°æ®é
            dataset = datasets[0]
            dataset_data = dataset.get('data', [])

            labels, dataset_data = self._align_labels_and_data(
                labels,
                dataset_data,
                chart_type="æå°åºå",
                require_positive_sum=False
            )

            if not labels or not dataset_data:
                return None

            title = props.get('title')
            fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
            ax = fig.add_subplot(111, projection='polar')

            if title:
                ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

            # è·åé¢è²
            raw_colors = dataset.get('backgroundColor', self.DEFAULT_COLORS[:len(labels)])
            if not isinstance(raw_colors, list):
                raw_colors = self.DEFAULT_COLORS[:len(labels)]

            colors = [
                self._ensure_visible_color(
                    raw_colors[i] if i < len(raw_colors) else None,
                    self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
                )
                for i in range(len(labels))
            ]

            # è®¡ç®è§åº¦
            theta = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
            width_bar = 2 * np.pi / len(labels)

            # ç»å¶æå°åºåå?
            bars = ax.bar(
                theta,
                dataset_data,
                width=width_bar,
                bottom=0.0,
                color=colors,
                alpha=0.7,
                edgecolor='white',
                linewidth=1
            )

            # è®¾ç½®æ ç­¾
            ax.set_xticks(theta)
            ax.set_xticklabels(labels)

            return self._figure_to_svg(fig)

        except Exception as e:
            logger.error(f"æ¸²ææå°åºåå¾å¤±è´? {e}")
            return None


def create_chart_converter(font_path: Optional[str] = None) -> ChartToSVGConverter:
    """
    åå»ºå¾è¡¨è½¬æ¢å¨å®ä¾?

    åæ°:
        font_path: ä¸­æå­ä½è·¯å¾ï¼å¯éï¼

    è¿å:
        ChartToSVGConverter: è½¬æ¢å¨å®ä¾?
    """
    return ChartToSVGConverter(font_path=font_path)


__all__ = ["ChartToSVGConverter", "create_chart_converter"]
