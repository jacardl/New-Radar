"""
LaTeX æ°å­¦å¬å¼è½?SVG æ¸²æå?
ä½¿ç¨ matplotlib å°?LaTeX å¬å¼æ¸²æä¸?SVG æ ¼å¼ï¼ç¨äº?PDF å¯¼åº
"""

import io
import re
from typing import Optional
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import mathtext
from loguru import logger

# ä½¿ç¨éäº¤äºå¼åç«¯
matplotlib.use('Agg')


class MathToSVG:
    """å°?LaTeX æ°å­¦å¬å¼è½¬æ¢ä¸?SVG çè½¬æ¢å¨"""

    def __init__(self, font_size: int = 14, color: str = 'black'):
        """
        åå§åå¬å¼è½¬æ¢å¨

        Args:
            font_size: å­ä½å¤§å°ï¼ç¹ï¼?
            color: æå­é¢è²
        """
        self.font_size = font_size
        self.color = color

    def convert_to_svg(self, latex: str, display_mode: bool = True) -> Optional[str]:
        """
        å°?LaTeX å¬å¼è½¬æ¢ä¸?SVG å­ç¬¦ä¸?

        Args:
            latex: LaTeX å¬å¼å­ç¬¦ä¸²ï¼ä¸åå?$$ æ?$ ç¬¦å·ï¼?
            display_mode: True ä¸ºæ¾ç¤ºæ¨¡å¼ï¼åçº§å¬å¼ï¼ï¼False ä¸ºè¡åæ¨¡å¼?

        Returns:
            SVG å­ç¬¦ä¸²ï¼å¦æè½¬æ¢å¤±è´¥åè¿å?None
        """
        try:
            # æ¸ç LaTeX å­ç¬¦ä¸²ï¼å»é¤å¤å±å®çç¬¦ï¼å¼å®¹ $...$ / $$...$$ / \\( \\) / \\[ \\]
            latex = (latex or "").strip()
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
            # æ¸çæ§å¶å­ç¬¦å¹¶åå¸¸è§å¼å®¹
            latex = re.sub(r'[\x00-\x1f\x7f]', '', latex)
            latex = latex.replace(r'\\tfrac', r'\\frac').replace(r'\\dfrac', r'\\frac')
            if not latex:
                logger.warning("ç©ºç LaTeX å¬å¼")
                return None

            # åå»ºå¾å½¢
            fig = plt.figure(figsize=(10, 2) if display_mode else (6, 1))
            fig.patch.set_alpha(0)  # éæèæ¯

            # æ¸²æ LaTeX
            # ä½¿ç¨ mathtext è¿è¡æ¸²æ
            if display_mode:
                # æ¾ç¤ºæ¨¡å¼ï¼å±ä¸­ï¼è¾å¤§å­ä½
                text = fig.text(
                    0.5, 0.5,
                    f'${latex}$',
                    fontsize=self.font_size * 1.2,
                    color=self.color,
                    ha='center',
                    va='center',
                    usetex=False  # ä½¿ç¨ matplotlib åç½®ç?mathtext èéå®æ´ LaTeX
                )
            else:
                # è¡åæ¨¡å¼ï¼å·¦å¯¹é½ï¼æ­£å¸¸å­ä½?
                text = fig.text(
                    0.1, 0.5,
                    f'${latex}$',
                    fontsize=self.font_size,
                    color=self.color,
                    ha='left',
                    va='center',
                    usetex=False
                )

            # è·åææ¬è¾¹çæ¡?
            fig.canvas.draw()
            bbox = text.get_window_extent(renderer=fig.canvas.get_renderer())

            # è½¬æ¢ä¸ºè±å¯¸ï¼matplotlib ä½¿ç¨çåä½ï¼
            bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())

            # è°æ´å¾å½¢å¤§å°ä»¥éåºææ¬ï¼æ·»å è¾¹è·?
            margin = 0.1  # è±å¯¸
            fig.set_size_inches(
                bbox_inches.width + 2 * margin,
                bbox_inches.height + 2 * margin
            )

            # éæ°å®ä½ææ¬å°ä¸­å¿?
            text.set_position((0.5, 0.5))

            # ä¿å­ä¸?SVG
            svg_buffer = io.StringIO()
            plt.savefig(
                svg_buffer,
                format='svg',
                bbox_inches='tight',
                pad_inches=0.1,
                transparent=True,
                dpi=300
            )
            plt.close(fig)

            # è·å SVG åå®¹
            svg_content = svg_buffer.getvalue()
            svg_buffer.close()

            return svg_content

        except Exception as e:
            logger.error(f"LaTeX å¬å¼è½¬æ¢å¤±è´¥: {latex[:100]}... éè¯¯: {str(e)}")
            return None

    def convert_inline_to_svg(self, latex: str) -> Optional[str]:
        """
        å°è¡å?LaTeX å¬å¼è½¬æ¢ä¸?SVG

        Args:
            latex: LaTeX å¬å¼å­ç¬¦ä¸?

        Returns:
            SVG å­ç¬¦ä¸²ï¼å¦æè½¬æ¢å¤±è´¥åè¿å?None
        """
        return self.convert_to_svg(latex, display_mode=False)

    def convert_display_to_svg(self, latex: str) -> Optional[str]:
        """
        å°æ¾ç¤ºæ¨¡å¼?LaTeX å¬å¼è½¬æ¢ä¸?SVG

        Args:
            latex: LaTeX å¬å¼å­ç¬¦ä¸?

        Returns:
            SVG å­ç¬¦ä¸²ï¼å¦æè½¬æ¢å¤±è´¥åè¿å?None
        """
        return self.convert_to_svg(latex, display_mode=True)


def convert_math_block_to_svg(
    latex: str,
    font_size: int = 16,
    color: str = 'black'
) -> Optional[str]:
    """
    ä¾¿æ·å½æ°ï¼å°æ°å­¦å¬å¼åè½¬æ¢ä¸º SVG

    Args:
        latex: LaTeX å¬å¼å­ç¬¦ä¸?
        font_size: å­ä½å¤§å°
        color: æå­é¢è²

    Returns:
        SVG å­ç¬¦ä¸²ï¼å¦æè½¬æ¢å¤±è´¥åè¿å?None
    """
    converter = MathToSVG(font_size=font_size, color=color)
    return converter.convert_display_to_svg(latex)


def convert_math_inline_to_svg(
    latex: str,
    font_size: int = 14,
    color: str = 'black'
) -> Optional[str]:
    """
    ä¾¿æ·å½æ°ï¼å°è¡åæ°å­¦å¬å¼è½¬æ¢ä¸?SVG

    Args:
        latex: LaTeX å¬å¼å­ç¬¦ä¸?
        font_size: å­ä½å¤§å°
        color: æå­é¢è²

    Returns:
        SVG å­ç¬¦ä¸²ï¼å¦æè½¬æ¢å¤±è´¥åè¿å?None
    """
    converter = MathToSVG(font_size=font_size, color=color)
    return converter.convert_inline_to_svg(latex)


if __name__ == "__main__":
    # æµè¯ä»£ç 
    import sys

    # æµè¯å¬å¼
    test_formulas = [
        r"E = mc^2",
        r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        r"\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}",
        r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
    ]

    converter = MathToSVG(font_size=16)

    for i, formula in enumerate(test_formulas):
        logger.info(f"æµè¯å¬å¼ {i+1}: {formula}")
        svg = converter.convert_display_to_svg(formula)
        if svg:
            # ä¿å­å°æä»?
            filename = f"test_math_{i+1}.svg"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(svg)
            logger.info(f"æåä¿å­å?{filename}")
        else:
            logger.error(f"å¬å¼ {i+1} è½¬æ¢å¤±è´¥")

    logger.info("æµè¯å®æ")
