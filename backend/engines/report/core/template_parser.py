"""
Markdownæ¨¡æ¿åçå·¥å·

LLMéè¦"æç« è°ç¨"ï¼å æ­¤å¿é¡»æMarkdownæ¨¡æ¿è§£æä¸ºç»æåç« èéå
è¿ééè¿è½»éæ­£ååç¼©è¿å¯åå¼ï¼å¼å®¹â? æ é¢"ä¸
â? **1.0 æ é¢** /   - 1.1 å­æ é¢"ç­å¤ç§åæ³
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

SECTION_ORDER_STEP = 10


@dataclass
class TemplateSection:
    """
    æ¨¡æ¿ç« èå®ä½

    è®°å½æ é¢lugãåºå·ãå±çº§ãåå§æ é¢ãç« èç¼å·ä¸æçº²ï¼?
    æ¹ä¾¿åç»­èç¹å¨æç¤ºè¯ä¸­å¼ç¨å¹¶ä¿æéç¹ä¸è´
    """

    title: str
    slug: str
    order: int
    depth: int
    raw_title: str
    number: str = ""
    chapter_id: str = ""
    outline: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        å°ç« èå®ä½åºååä¸ºå­å¸

        è¯¥ç»æå¹¿æ³ç¨äºæç¤ºè¯ä¸ä¸æä»¥å?layout/word budget èç¹çè¾å¥
        """
        return {
            "title": self.title,
            "slug": self.slug,
            "order": self.order,
            "depth": self.depth,
            "number": self.number,
            "chapterId": self.chapter_id,
            "outline": self.outline,
        }


# è§£æè¡¨è¾¾å¼å»æé¿åä½¿ç?`.*`ï¼ä»¥ä¿æå¹éçç¡®å®æ§ï¼
# å¹¶è§é¿ä¸å¯ä¿¡æ¨¡æ¿ææ¬ä¸­å¸¸è§çæ­£åDoSé£é©
heading_pattern = re.compile(
    r"""
    (?P<marker>\#{1,6})       # Markdownæ é¢æ è®°
    [ \t]+                    # å¿éçç©ºç½å­ç¬?
    (?P<title>[^\r\n]+)       # ä¸åå«æ¢è¡çæ é¢ææ¬
    """,
    re.VERBOSE,
)
bullet_pattern = re.compile(
    r"""
    (?P<marker>[-*+])         # åè¡¨é¡¹ç®ç¬¦å·
    [ \t]+
    (?P<title>[^\r\n]+)
    """,
    re.VERBOSE,
)
number_pattern = re.compile(
    r"""
    (?P<num>
        (?:0|[1-9]\d*)
        (?:\.(?:0|[1-9]\d*))*
    )
    (?:
        (?:[ \t\u00A0\u3000ï¼?]+|\.(?!\d))+
        (?P<label>[^\r\n]*)
    )?
    """,
    re.VERBOSE,
)


def parse_template_sections(template_md: str) -> List[TemplateSection]:
    """
    å°Markdownæ¨¡æ¿ååæç« èåè¡¨ï¼æå¤§æ é¢ï¼

    è¿åçæ¯ä¸ªTemplateSectioné½æºå¸¦slug/order/ç« èå·ï¼
    æ¹ä¾¿åç»­åç« è°ç¨ä¸éç¹çæãè§£ææ¶ä¼åæ¶å¼å®?
    â? æ é¢""æ ç¬¦å·ç¼å·""åè¡¨æçº²"ç­ä¸ååæ³

    åæ°:
        template_md: æ¨¡æ¿Markdownå¨æ

    è¿å:
        list[TemplateSection]: ç»æåçç« èåºå
    """

    sections: List[TemplateSection] = []
    current: Optional[TemplateSection] = None
    order = SECTION_ORDER_STEP
    used_slugs = set()

    for raw_line in template_md.splitlines():
        if not raw_line.strip():
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        meta = _classify_line(stripped, indent)
        if not meta:
            continue

        if meta["is_section"]:
            slug = _ensure_unique_slug(meta["slug"], used_slugs)
            section = TemplateSection(
                title=meta["title"],
                slug=slug,
                order=order,
                depth=meta["depth"],
                raw_title=meta["raw"],
                number=meta["number"],
            )
            sections.append(section)
            current = section
            order += SECTION_ORDER_STEP
            continue

        # æçº²æ¡ç®
        if current:
            current.outline.append(meta["title"])

    for idx, section in enumerate(sections, start=1):
        # ä¸ºæ¯ä¸ªç« èçæç¨³å®çchapter_idï¼ä¾¿äºåç»­å¼ç?
        section.chapter_id = f"S{idx}"

    return sections


def _classify_line(stripped: str, indent: int) -> Optional[dict]:
    """
    æ ¹æ®ç¼©è¿ä¸ç¬¦å·åç±»è¡

    åå©æ­£åå¤æ­å½åè¡æ¯ç« èæ é¢ãæçº²è¿æ¯æ®éåè¡¨é¡¹ï¼?
    å¹¶è¡ç?depth/slug/number ç­æ´¾çä¿¡æ¯

    åæ°:
        stripped: å»é¤ååç©ºæ ¼åçåå§è¡
        indent: è¡é¦ç©ºæ ¼æ°éï¼ç¨äºåºåå±çº§

    è¿å:
        dict | None: è¯å«åçåæ°æ®ï¼æ æ³è¯å«æ¶è¿åNone
    """

    heading_match = heading_pattern.fullmatch(stripped)
    if heading_match:
        level = len(heading_match.group("marker"))
        payload = _strip_markup(heading_match.group("title").strip())
        title_info = _split_number(payload)
        slug = _build_slug(title_info["number"], title_info["title"])
        return {
            "is_section": level <= 2,
            "depth": level,
            "title": title_info["display"],
            "raw": payload,
            "number": title_info["number"],
            "slug": slug,
        }

    bullet_match = bullet_pattern.fullmatch(stripped)
    if bullet_match:
        payload = _strip_markup(bullet_match.group("title").strip())
        title_info = _split_number(payload)
        slug = _build_slug(title_info["number"], title_info["title"])
        is_section = indent <= 1
        depth = 1 if indent <= 1 else 2
        return {
            "is_section": is_section,
            "depth": depth,
            "title": title_info["display"],
            "raw": payload,
            "number": title_info["number"],
            "slug": slug,
        }

    # å¼å®¹â?.1 ..."æ²¡æåç¼ç¬¦å·çè¡
    number_match = number_pattern.fullmatch(stripped)
    if number_match and number_match.group("label"):
        payload = stripped
        title = number_match.group("label").strip()
        number = number_match.group("num")
        slug = _build_slug(number, title)
        is_section = indent == 0 and number.count(".") <= 1
        depth = 1 if is_section else 2
        display = f"{number} {title}" if title else number
        return {
            "is_section": is_section,
            "depth": depth,
            "title": display,
            "raw": payload,
            "number": number,
            "slug": slug,
        }

    return None


def _strip_markup(text: str) -> str:
    """å»é¤åè£¹ç?*_ç­å¼ºè°æ è®°ï¼é¿åå¹²æ°æ é¢å¹é""
    if text.startswith(("**", "__")) and text.endswith(("**", "__")) and len(text) > 4:
        return text[2:-2].strip()
    return text


def _split_number(payload: str) -> dict:
    """
    æåç¼å·ä¸æ é¢

    ä¾å¦ `1.2 å¸åºè¶å¿` ä¼è¢«ææ number=1.2abel=å¸åºè¶å¿ï¼?
    å¹¶æä¾?display ç¨äºåå¡«æ é¢

    åæ°:
        payload: åå§æ é¢å­ç¬¦ä¸²

    è¿å:
        dict: åå« number/title/display
    """
    match = number_pattern.fullmatch(payload)
    number = match.group("num") if match else ""
    label = match.group("label") if match else payload
    label = (label or "").strip()
    display = f"{number} {label}".strip() if number else label or payload
    title_core = label or payload
    return {
        "number": number,
        "title": title_core,
        "display": display,
    }


def _build_slug(number: str, title: str) -> str:
    """
    æ ¹æ®ç¼å·/æ é¢çæéç¹ï¼ä¼åå¤ç¨ç¼å·ï¼ç¼ºå¤±æ¶å¯¹æ é¢slugå

    åæ°:
        number: ç« èç¼å·
        title: æ é¢ææ¬

    è¿å:
        str: å½¢å¦ `section-1-0` çslug
    """
    if number:
        token = number.replace(".", "-")
    else:
        token = _slugify_text(title)
    token = token or "section"
    return f"section-{token}"


def _slugify_text(text: str) -> str:
    """
    å¯¹ä»»æææ¬åéåªä¸è½¬åï¼å¾å°URLåå¥½çslugçæ®µ

    ä¼è§æ´å¤§å°åãç§»é¤ç¹æ®ç¬¦å·å¹¶ä¿çæ±å­ï¼ç¡®ä¿éç¹å¯è¯»
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("�·", "-").replace(" ", "-")
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-").lower()


def _ensure_unique_slug(slug: str, used: set) -> str:
    """
    è¥slugéå¤åèªå¨è¿½å åºå·ï¼ç´å°å¨usedéåä¸­å¯ä¸

    éè¿ `-2/-3...` çæ¹å¼ä¿è¯ç¸åæ é¢ä¸ä¼äº§çéå¤éç¹

    åæ°:
        slug: åå§slug
        used: å·²ä½¿ç¨éå

    è¿å:
        str: å»éåçslug
    """
    if slug not in used:
        used.add(slug)
        return slug
    base = slug
    idx = 2
    while slug in used:
        slug = f"{base}-{idx}"
        idx += 1
    used.add(slug)
    return slug


__all__ = ["TemplateSection", "parse_template_sections"]
