"""
ç« èè£è®¢å¨ï¼è´è´£æå¤ä¸ªç« èJSONåå¹¶ä¸ºæ´æ¬IR

DocumentComposer ä¼æ³¨å¥ç¼ºå¤±éç¹ãç»ä¸é¡ºåºï¼å¹¶è¡¥é½ IR çº§åæ°æ®
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from ..ir import IR_VERSION


class DocumentComposer:
    """
    å°ç« èæ¼æ¥æDocument IRçç®åè£è®¢å¨

    ä½ç¨ï¼?
        - æorderæåºç« èï¼è¡¥åé»è®¤chapterIdï¼?
        - é²æ­¢anchoréå¤ï¼çæå¨å±å¯ä¸éç¹ï¼?
        - æ³¨å¥ IR çæ¬ä¸çææ¶é´æ³
    """

    def __init__(self):
        """åå§åè£è®¢å¨å¹¶è®°å½å·²ä½¿ç¨çéç¹ï¼é¿åéå¤"""
        self._seen_anchors: Set[str] = set()

    def build_document(
        self,
        report_id: str,
        metadata: Dict[str, object],
        chapters: List[Dict[str, object]],
    ) -> Dict[str, object]:
        """
        æææç« èæorderæåºå¹¶æ³¨å¥å¯ä¸éç¹ï¼å½¢ææ´æ¬IR

        åæ¶åå¹¶ metadata/themeTokens/assetsï¼ä¾æ¸²æå¨ç´æ¥æ¶è´¹

        åæ°:
            report_id: æ¬æ¬¡æ¥åID
            metadata: å¨å±åä¿¡æ¯ï¼æ é¢ãä¸»é¢ocç­ï¼
            chapters: ç« èpayloadåè¡¨

        è¿å:
            dict: æ»¡è¶³æ¸²æå¨éæ±çDocument IR
        """
        # å¨å±å¤çåå¹¶ææçå¼ç¨æç®ï¼å¹¶éæ°ç¼å·
        self._consolidate_citations(chapters)

        # æå»ºä»chapterIdå°toc anchorçæ å°?
        toc_anchor_map = self._build_toc_anchor_map(metadata)

        ordered = sorted(chapters, key=lambda c: c.get("order", 0))
        for idx, chapter in enumerate(ordered, start=1):
            chapter.setdefault("chapterId", f"S{idx}")

            # ä¼åçº§ï¼1. ç®å½éç½®çanchor 2. ç« èèªå¸¦çanchor 3. é»è®¤anchor
            chapter_id = chapter.get("chapterId")
            anchor = (
                toc_anchor_map.get(chapter_id) or
                chapter.get("anchor") or
                f"section-{idx}"
            )
            chapter["anchor"] = self._ensure_unique_anchor(anchor)
            chapter.setdefault("order", idx * 10)
            if chapter.get("errorPlaceholder"):
                self._ensure_heading_block(chapter)

        document = {
            "version": IR_VERSION,
            "reportId": report_id,
            "metadata": {
                **metadata,
                "generatedAt": metadata.get("generatedAt")
                or datetime.utcnow().isoformat() + "Z",
            },
            "themeTokens": metadata.get("themeTokens", {}),
            "chapters": ordered,
            "assets": metadata.get("assets", {}),
        }
        return document

    def _ensure_unique_anchor(self, anchor: str) -> str:
        """è¥å­å¨éå¤éç¹åè¿½å åºå·ï¼ç¡®ä¿å¨å±å¯ä¸""
        base = anchor
        counter = 2
        while anchor in self._seen_anchors:
            anchor = f"{base}-{counter}"
            counter += 1
        self._seen_anchors.add(anchor)
        return anchor

    def _build_toc_anchor_map(self, metadata: Dict[str, object]) -> Dict[str, str]:
        """
        ä»metadata.toc.customEntriesæå»ºchapterIdå°anchorçæ å°
        """
        toc_config = metadata.get("toc") or {}
        custom_entries = toc_config.get("customEntries") or []
        anchor_map = {}

        for entry in custom_entries:
            if isinstance(entry, dict):
                chapter_id = entry.get("chapterId")
                anchor = entry.get("anchor")
                if chapter_id and anchor:
                    anchor_map[chapter_id] = anchor

        return anchor_map

    def _consolidate_citations(self, chapters: List[Dict[str, object]]) -> None:
        """
        æææç« èä¸­ç?citationList åå¹¶ä¸ºä¸ä»½å¨å±åèèµæï¼å¹¶ä¿®æ­£æ­£æä¸­ç?inline citation ç¼å·
        """
        global_citations = []
        url_to_global_index = {}
        title_to_global_index = {}
        global_index_counter = 1
        
        chapter_index_maps = []

        for chapter in chapters:
            blocks = chapter.get("blocks", [])
            if not isinstance(blocks, list):
                chapter_index_maps.append({})
                continue
                
            local_map = {}
            new_blocks = []
            
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "citationList":
                    items = block.get("items", [])
                    for item in items:
                        url = item.get("url", "").strip()
                        title = item.get("title", "").strip()
                        local_idx = str(item.get("index", ""))
                        
                        if url and url in url_to_global_index:
                            g_idx = url_to_global_index[url]
                        elif not url and title and title in title_to_global_index:
                            g_idx = title_to_global_index[title]
                        else:
                            g_idx = global_index_counter
                            global_index_counter += 1
                            new_item = dict(item)
                            new_item["index"] = g_idx
                            global_citations.append(new_item)
                            
                            if url:
                                url_to_global_index[url] = g_idx
                            if title:
                                title_to_global_index[title] = g_idx
                                
                        if local_idx:
                            local_map[local_idx] = g_idx
                else:
                    new_blocks.append(block)
            
            chapter["blocks"] = new_blocks
            chapter_index_maps.append(local_map)
            
        import re
        
        def walk_and_replace_inlines(node, local_map):
            if isinstance(node, dict):
                if "inlines" in node and isinstance(node["inlines"], list):
                    new_inlines = []
                    for inline in node["inlines"]:
                        if not isinstance(inline, dict):
                            new_inlines.append(inline)
                            continue
                        
                        marks = inline.get("marks", [])
                        is_citation = False
                        href = ""
                        for m in marks:
                            if isinstance(m, dict) and m.get("type") == "link":
                                link_href = str(m.get("href", ""))
                                if link_href.startswith("#citation-"):
                                    is_citation = True
                                    href = link_href
                                    break
                        
                        if is_citation:
                            match = re.search(r'#citation-(\d+)', href)
                            if match:
                                local_idx = match.group(1)
                                if local_idx in local_map:
                                    g_idx = local_map[local_idx]
                                    
                                    actual_url = ""
                                    for gc in global_citations:
                                        if gc["index"] == g_idx:
                                            actual_url = gc.get("url", "")
                                            break
                                            
                                    inline_text = str(inline.get("text", ""))
                                    
                                    # éå¯¹è¡¨æ ¼ä¸­é¿ææ¬å¼ç¨çä¼åï¼å¦æ text å¾é¿ï¼åå«æè¿°ï¼ï¼åç´æ¥å°?href æ¿æ¢ä¸ºçå®?url
                                    # å¦ååªæ¿æ¢ç¼å·å¹¶æåææ«
                                    if len(inline_text) > 5 and actual_url:
                                        if f"[{local_idx}]" in inline_text:
                                            inline["text"] = inline_text.replace(f"[{local_idx}]", f"[{g_idx}]")
                                        for m in marks:
                                            if isinstance(m, dict) and m.get("type") == "link":
                                                m["href"] = actual_url
                                    else:
                                        inline["text"] = f"[{g_idx}]"
                                        for m in marks:
                                            if isinstance(m, dict) and m.get("type") == "link":
                                                m["href"] = f"#citation-{g_idx}"
                                    new_inlines.append(inline)
                                else:
                                    # å¦æå?citationList ä¸­æ¾ä¸å°è¯¥ç¼å·ï¼è¯´ææ?LLM å¹»è§ç¼é çè¶çå¼ç¨ï¼ç´æ¥ä¸¢å¼è¯¥æ è®°
                                    pass
                            else:
                                new_inlines.append(inline)
                        else:
                            new_inlines.append(inline)
                    node["inlines"] = new_inlines
                
                for k, v in node.items():
                    if k != "inlines":
                        walk_and_replace_inlines(v, local_map)
            elif isinstance(node, list):
                for item in node:
                    walk_and_replace_inlines(item, local_map)

        for chapter, local_map in zip(chapters, chapter_index_maps):
            walk_and_replace_inlines(chapter.get("blocks"), local_map)
            
        if global_citations and chapters:
            last_chapter = chapters[-1]
            last_chapter["blocks"].append({
                "type": "citationList",
                "items": global_citations
            })

    def _ensure_heading_block(self, chapter: Dict[str, object]) -> None:
        """ä¿è¯å ä½ç« èä»ç¶æ¥æå¯ç¨äºç®å½çheading block""
        blocks = chapter.get("blocks")
        if isinstance(blocks, list):
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "heading":
                    return
        heading = {
            "type": "heading",
            "level": 2,
            "text": chapter.get("title") or "å ä½ç« è",
            "anchor": chapter.get("anchor"),
        }
        if isinstance(blocks, list):
            blocks.insert(0, heading)
        else:
            chapter["blocks"] = [heading]


__all__ = ["DocumentComposer"]
