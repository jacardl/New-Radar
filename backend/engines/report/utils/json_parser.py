"""
ç»ä¸çJSONè§£æåä¿®å¤å·¥å·

æä¾é²æ£çJSONè§£æè½åï¼æ¯æï¼
1. èªå¨æ¸çmarkdownä»£ç åæ è®°åæèåå®?
2. æ¬å°è¯­æ³ä¿®å¤ï¼æ¬å·å¹³è¡¡ãéå·è¡¥å¨ãæ§å¶å­ç¬¦è½¬ä¹ç­ï¼?
3. ä½¿ç¨json_repairåºè¿è¡é«çº§ä¿®å¤?
4. LLMè¾å©ä¿®å¤ï¼å¯éï¼
5. è¯¦ç»çéè¯¯æ¥å¿åè°è¯ä¿¡æ¯
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Callable
from loguru import logger

try:
    from json_repair import repair_json as _json_repair_fn
except ImportError:
    _json_repair_fn = None


class JSONParseError(ValueError):
    """JSONè§£æå¤±è´¥æ¶æåºçå¼å¸¸ï¼éå¸¦åå§ææ¬æ¹ä¾¿ææ¥""

    def __init__(self, message: str, raw_text: Optional[str] = None):
        """
        æé å¼å¸¸å¹¶éå åå§è¾åºï¼ä¾¿äºæ¥å¿ä¸­å®ä½

        Args:
            message: äººç±»å¯è¯»çéè¯¯æè¿°
            raw_text: è§¦åå¼å¸¸çå®æ´LLMè¾åº
        """
        super().__init__(message)
        self.raw_text = raw_text


class RobustJSONParser:
    """
    é²æ£çJSONè§£æå¨

    éæå¤ç§ä¿®å¤ç­ç¥ï¼ç¡®ä¿LLMè¿åçåå®¹è½å¤è¢«æ­£ç¡®è§£æï¼?
    - æ¸çmarkdownåè£¹ãæèåå®¹ç­é¢å¤ä¿¡æ¯
    - ä¿®å¤å¸¸è§è¯­æ³éè¯¯ï¼ç¼ºå°éå·ãæ¬å·ä¸å¹³è¡¡ç­ï¼
    - è½¬ä¹æªè½¬ä¹çæ§å¶å­ç¬¦
    - ä½¿ç¨ç¬¬ä¸æ¹åºè¿è¡é«çº§ä¿®å¤
    - å¯éçLLMè¾å©ä¿®å¤
    """

    # å¸¸è§çLLMæèåå®¹æ¨¡å¼?
    _THINKING_PATTERNS = [
        r"^\s*<thinking>.*?</thinking>\s*",
        r"^\s*<thought>.*?</thought>\s*",
        r"^\s*è®©ææ³æ³.*?(?=\{|\[|$)",
        r"^\s*é¦å.*?(?=\{|\[|$)",
        r"^\s*åæ.*?(?=\{|\[|$)",
        r"^\s*æ ¹æ®.*?(?=\{|\[|$)",
    ]

    # åå·ç­å·æ¨¡å¼ï¼LLMå¸¸è§éè¯¯ï¼?
    _COLON_EQUALS_PATTERN = re.compile(r'(":\s*)=')

    def __init__(
        self,
        llm_repair_fn: Optional[Callable[[str, str], Optional[str]]] = None,
        enable_json_repair: bool = True,
        enable_llm_repair: bool = False,
        max_repair_attempts: int = 3,
    ):
        """
        åå§åJSONè§£æå¨

        Args:
            llm_repair_fn: å¯éçLLMä¿®å¤å½æ°ï¼æ¥æ?åå§JSON, éè¯¯ä¿¡æ¯)è¿åä¿®å¤åçJSON
            enable_json_repair: æ¯å¦å¯ç¨json_repairåº?
            enable_llm_repair: æ¯å¦å¯ç¨LLMè¾å©ä¿®å¤
            max_repair_attempts: æå¤§ä¿®å¤å°è¯æ¬¡æ?
        """
        self.llm_repair_fn = llm_repair_fn
        self.enable_json_repair = enable_json_repair and _json_repair_fn is not None
        self.enable_llm_repair = enable_llm_repair
        self.max_repair_attempts = max_repair_attempts

    def parse(
        self,
        raw_text: str,
        context_name: str = "JSON",
        expected_keys: Optional[List[str]] = None,
        extract_wrapper_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        è§£æLLMè¿åçJSONææ¬

        åæ°:
            raw_text: LLMåå§è¾åºï¼å¯è½åå«```åè£¹ãæèåå®¹ç­ï¼?
            context_name: ä¸ä¸æåç§°ï¼ç¨äºéè¯¯ä¿¡æ¯
            expected_keys: ææçé®åè¡¨ï¼ç¨äºéªè¯?
            extract_wrapper_key: å¦æJSONè¢«åè£¹å¨æä¸ªé®ä¸­ï¼æå®è¯¥é®åè¿è¡æå

        è¿å:
            dict: è§£æåçJSONå¯¹è±¡

        å¼å¸¸:
            JSONParseError: å¤ç§ä¿®å¤ç­ç¥ä»æ æ³è§£æåæ³JSON
        """
        if not raw_text or not raw_text.strip():
            raise JSONParseError(f"{context_name}è¿åç©ºåå®?)

        # åå§ææ¬ç¨äºåç»­æ¥å¿
        original_text = raw_text

        # æ­¥éª¤1: æé åééï¼åå«ä¸åæ¸çç­ç?
        candidates = self._build_candidate_payloads(raw_text, context_name)

        # æ­¥éª¤2: å°è¯è§£æææåé?
        last_error: Optional[json.JSONDecodeError] = None
        for i, candidate in enumerate(candidates):
            try:
                data = json.loads(candidate)
                logger.debug(f"{context_name} JSONè§£ææåï¼åé{i + 1}/{len(candidates)}ï¼?)
                return self._extract_and_validate(
                    data, expected_keys, extract_wrapper_key, context_name
                )
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.debug(f"{context_name} åé{i + 1}è§£æå¤±è´¥: {exc}")

        cleaned = candidates[0] if candidates else original_text

        # æ­¥éª¤3: ä½¿ç¨json_repairåº?
        if self.enable_json_repair:
            repaired = self._attempt_json_repair(cleaned, context_name)
            if repaired:
                try:
                    data = json.loads(repaired)
                    logger.info(f"{context_name} JSONéè¿json_repairåºä¿®å¤æå?)
                    return self._extract_and_validate(
                        data, expected_keys, extract_wrapper_key, context_name
                    )
                except json.JSONDecodeError as exc:
                    last_error = exc
                    logger.debug(f"{context_name} json_repairä¿®å¤åä»æ æ³è§£æ: {exc}")

        # æ­¥éª¤4: ä½¿ç¨LLMä¿®å¤ï¼å¦æå¯ç¨ï¼
        if self.enable_llm_repair and self.llm_repair_fn:
            llm_repaired = self._attempt_llm_repair(cleaned, str(last_error), context_name)
            if llm_repaired:
                try:
                    data = json.loads(llm_repaired)
                    logger.info(f"{context_name} JSONéè¿LLMä¿®å¤æå")
                    return self._extract_and_validate(
                        data, expected_keys, extract_wrapper_key, context_name
                    )
                except json.JSONDecodeError as exc:
                    last_error = exc
                    logger.warning(f"{context_name} LLMä¿®å¤åä»æ æ³è§£æ: {exc}")

        # ææç­ç¥é½å¤±è´¥äº?
        error_msg = f"{context_name} JSONè§£æå¤±è´¥: {last_error}"
        logger.error(error_msg)
        logger.debug(f"åå§ææ¬å?00å­ç¬¦: {original_text[:500]}")
        raise JSONParseError(error_msg, raw_text=original_text) from last_error

    def _build_candidate_payloads(self, raw_text: str, context_name: str) -> List[str]:
        """
        éå¯¹åå§ææ¬æé å¤ä¸ªåéJSONå­ç¬¦ä¸²ï¼è¦çä¸åçæ¸çç­ç¥

        è¿å:
            List[str]: åéJSONææ¬åè¡¨
        """
        cleaned = self._clean_response(raw_text)
        candidates = [cleaned]

        local_repaired = self._apply_local_repairs(cleaned)
        if local_repaired != cleaned:
            candidates.append(local_repaired)

        # å¯¹å«æä¸å±åè¡¨ç»æçåå®¹å¼ºå¶æå¹³ä¸æ¬?
        flattened = self._flatten_nested_arrays(local_repaired)
        if flattened not in candidates:
            candidates.append(flattened)

        return candidates

    def _clean_response(self, raw: str) -> str:
        """
        æ¸çLLMååºï¼å»é¤markdownæ è®°åæèåå®¹

        åæ°:
            raw: LLMåå§è¾åº

        è¿å:
            str: æ¸çåçææ¬
        """
        cleaned = raw.strip()

        # ç§»é¤æèåå®¹ï¼å¤è¯­è¨æ¯æï¼?
        for pattern in self._THINKING_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL | re.IGNORECASE)

        # ä¼åæåä»»æä½ç½®ç```json```åè£¹åå®¹
        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()
        else:
            # å¦ææ²¡ææ¾å°å®æ´ä»£ç åï¼åå°è¯ç§»é¤ååç¼
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]

            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            cleaned = cleaned.strip()

        # å°è¯æåç¬¬ä¸ä¸ªå®æ´çJSONå¯¹è±¡ææ°ç»?
        cleaned = self._extract_first_json_structure(cleaned)

        return cleaned

    def _extract_first_json_structure(self, text: str) -> str:
        """
        ä»ææ¬ä¸­æåç¬¬ä¸ä¸ªå®æ´çJSONå¯¹è±¡ææ°ç»

        è¿å¯¹äºå¤çLLMå¨JSONååæ·»å è¯´ææå­çæåµå¾æç¨

        åæ°:
            text: å¯è½åå«JSONçææ?

        è¿å:
            str: æåçJSONææ¬ï¼å¦ææ¾ä¸å°åè¿ååææ¬
        """
        # æ¥æ¾ç¬¬ä¸ä¸?{ æ?[
        start_brace = text.find("{")
        start_bracket = text.find("[")

        if start_brace == -1 and start_bracket == -1:
            return text

        # ç¡®å®èµ·å§ä½ç½®
        if start_brace == -1:
            start = start_bracket
            opener = "["
            closer = "]"
        elif start_bracket == -1:
            start = start_brace
            opener = "{"
            closer = "}"
        else:
            start = min(start_brace, start_bracket)
            opener = text[start]
            closer = "}" if opener == "{" else "]"

        # æ¥æ¾å¯¹åºçç»æä½ç½?
        depth = 0
        in_string = False
        escaped = False

        for i in range(start, len(text)):
            ch = text[i]

            if escaped:
                escaped = False
                continue

            if ch == "\\":
                escaped = True
                continue

            if ch == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        # å¦ææ²¡æ¾å°å®æ´çç»æï¼è¿åä»èµ·å§ä½ç½®å°ç»å°?
        return text[start:] if start < len(text) else text

    def _apply_local_repairs(self, text: str) -> str:
        """
        åºç¨æ¬å°ä¿®å¤ç­ç¥

        åæ°:
            text: åå§JSONææ¬

        è¿å:
            str: ä¿®å¤åçææ¬
        """
        repaired = text
        mutated = False

        # ä¿®å¤ ":=" éè¯¯
        new_text = self._COLON_EQUALS_PATTERN.sub(r"\1", repaired)
        if new_text != repaired:
            logger.warning("æ£æµå°\":=\"å­ç¬¦ï¼å·²èªå¨ç§»é¤å¤ä½ç?='å?)
            repaired = new_text
            mutated = True

        # è½¬ä¹æ§å¶å­ç¬¦
        repaired, escaped = self._escape_control_characters(repaired)
        if escaped:
            logger.warning("æ£æµå°æªè½¬ä¹çæ§å¶å­ç¬¦ï¼å·²èªå¨è½¬æ¢ä¸ºè½¬ä¹åºå?)
            mutated = True

        # ä¿®å¤ç¼ºå°çéå·
        repaired, commas_fixed = self._fix_missing_commas(repaired)
        if commas_fixed:
            logger.warning("æ£æµå°å¯¹è±¡/æ°ç»ä¹é´ç¼ºå°éå·ï¼å·²èªå¨è¡¥é½")
            mutated = True

        # åå¹¶å¤ä½çæ¹æ¬å·ï¼LLMå¸¸è§æäºç»´åè¡¨å±çº§åæä¸å±ï¼
        repaired, brackets_collapsed = self._collapse_redundant_brackets(repaired)
        if brackets_collapsed:
            logger.warning("æ£æµå°è¿ç»­çæ¹æ¬å·åµå¥ï¼å·²å°è¯æå ä¸ºäºç»´ç»æ?)
            mutated = True

        # å¹³è¡¡æ¬å·
        repaired, balanced = self._balance_brackets(repaired)
        if balanced:
            logger.warning("æ£æµå°æ¬å·ä¸å¹³è¡¡ï¼å·²èªå¨è¡¥é½?åé¤å¼å¸¸æ¬å·")
            mutated = True

        # ç§»é¤å°¾ééå·
        repaired, trailing_removed = self._remove_trailing_commas(repaired)
        if trailing_removed:
            logger.warning("æ£æµå°å°¾ééå·ï¼å·²èªå¨ç§»é¤")
            mutated = True

        return repaired if mutated else text

    def _escape_control_characters(self, text: str) -> Tuple[str, bool]:
        """
        å°å­ç¬¦ä¸²å­é¢éä¸­çè£¸æ¢è¡/å¶è¡¨ç¬?æ§å¶å­ç¬¦æ¿æ¢ä¸ºJSONåæ³çè½¬ä¹åºå

        åæ°:
            text: åå§JSONææ¬

        è¿å:
            Tuple[str, bool]: (ä¿®å¤åçææ¬, æ¯å¦æä¿®æ?
        """
        if not text:
            return text, False

        result: List[str] = []
        in_string = False
        escaped = False
        mutated = False
        control_map = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string and ch in control_map:
                result.append(control_map[ch])
                mutated = True
                continue

            if in_string and ord(ch) < 0x20:
                result.append(f"\\u{ord(ch):04x}")
                mutated = True
                continue

            result.append(ch)

        return "".join(result), mutated

    def _fix_missing_commas(self, text: str) -> Tuple[str, bool]:
        """
        å¨å¯¹è±?æ°ç»åç´ ä¹é´èªå¨è¡¥éå·

        åæ°:
            text: åå§JSONææ¬

        è¿å:
            Tuple[str, bool]: (ä¿®å¤åçææ¬, æ¯å¦æä¿®æ?
        """
        if not text:
            return text, False

        chars: List[str] = []
        mutated = False
        in_string = False
        escaped = False
        length = len(text)
        i = 0

        while i < length:
            ch = text[i]
            chars.append(ch)

            if escaped:
                escaped = False
                i += 1
                continue

            if ch == "\\":
                escaped = True
                i += 1
                continue

            if ch == '"':
                # å¦ææä»¬æ­£å¨éåºå­ç¬¦ä¸²ï¼æ£æ¥åé¢æ¯å¦éè¦éå·
                if in_string:
                    # æ¥æ¾ä¸ä¸ä¸ªéç©ºç½å­ç¬¦
                    j = i + 1
                    while j < length and text[j] in " \t\r\n":
                        j += 1
                    # å¦æä¸ä¸ä¸ªå­ç¬¦æ¯ " { [ ææ°å­ï¼å¯è½éè¦éå·
                    if j < length:
                        next_ch = text[j]
                        if next_ch in "\"[{" or next_ch.isdigit():
                            # æ£æ¥æ¯å¦å·²ç»å¨å¯¹è±¡ææ°ç»ä¸­
                            # éè¿æ£æ¥åé¢æ¯å¦ææªé­åç { æ?[
                            has_opener = False
                            for k in range(len(chars) - 1, -1, -1):
                                if chars[k] in "{[":
                                    has_opener = True
                                    break
                                elif chars[k] in "]}":
                                    break

                            if has_opener:
                                chars.append(",")
                                mutated = True

                in_string = not in_string
                i += 1
                continue

            # å?} æ?] åé¢æ£æ¥æ¯å¦éè¦éå·
            if not in_string and ch in "}]":
                j = i + 1
                # è·³è¿ç©ºç½
                while j < length and text[j] in " \t\r\n":
                    j += 1
                # å¦æä¸ä¸ä¸ªéç©ºç½å­ç¬¦æ?{ [ " ææ°å­ï¼æ·»å éå·
                if j < length:
                    next_ch = text[j]
                    if next_ch in "{[\"" or next_ch.isdigit():
                        chars.append(",")
                        mutated = True

            i += 1

        return "".join(chars), mutated

    def _collapse_redundant_brackets(self, text: str) -> Tuple[str, bool]:
        """
        éå¯¹LLMçæçä¸å±ææ´å¤å±æ°ç»ï¼å¦]]], [[ / [[[ï¼è¿è¡æå ï¼é¿åè¡¨æ ¼/åè¡¨ååºé¢å¤ç»´åº¦

        è¿å:
            Tuple[str, bool]: (ä¿®å¤åçææ¬, æ¯å¦æä¿®æ?
        """
        if not text:
            return text, False

        mutated = False

        patterns = [
            # å¸åéè¯¯: "]]], [[{...}" -> "]], [{...}"
            (re.compile(r"\]\s*\]\s*\]\s*,\s*\[\s*\["), "]],["),
            # æç«¯æåµ: è¿ç»­ä¸å±å¼å¤?"[[[" -> "[["
            (re.compile(r"\[\s*\[\s*\["), "[["),
            # æç«¯æåµ: ç»å°¾ "]]]" -> "]]"
            (re.compile(r"\]\s*\]\s*\]"), "]]"),
        ]

        repaired = text
        for pattern, replacement in patterns:
            new_text, count = pattern.subn(replacement, repaired)
            if count > 0:
                mutated = True
                repaired = new_text

        return repaired, mutated

    def _flatten_nested_arrays(self, text: str) -> str:
        """
        å¯¹ææ¾å¤ä½çä¸å±åè¡¨è¿è¡æå ï¼ä¾å¦ [[[x]]] -> [[x]]
        """
        if not text:
            return text
        text = re.sub(r"\]\s*\]\s*\]", "]]", text)
        text = re.sub(r"\[\s*\[\s*\[", "[[", text)
        return text

    def _balance_brackets(self, text: str) -> Tuple[str, bool]:
        """
        å°è¯ä¿®å¤å LLMå¤å/å°åæ¬å·å¯¼è´çä¸å¹³è¡¡ç»æ

        åæ°:
            text: åå§JSONææ¬

        è¿å:
            Tuple[str, bool]: (ä¿®å¤åçææ¬, æ¯å¦æä¿®æ?
        """
        if not text:
            return text, False

        result: List[str] = []
        stack: List[str] = []
        mutated = False
        in_string = False
        escaped = False

        opener_map = {"{": "}", "[": "]"}

        for ch in text:
            if escaped:
                result.append(ch)
                escaped = False
                continue

            if ch == "\\":
                result.append(ch)
                escaped = True
                continue

            if ch == '"':
                result.append(ch)
                in_string = not in_string
                continue

            if in_string:
                result.append(ch)
                continue

            if ch in "{[":
                stack.append(ch)
                result.append(ch)
                continue

            if ch in "}]":
                if stack and (
                    (ch == "}" and stack[-1] == "{") or (ch == "]" and stack[-1] == "[")
                ):
                    stack.pop()
                    result.append(ch)
                else:
                    # ä¸å¹éçé­æ¬å·ï¼å¿½ç¥
                    mutated = True
                continue

            result.append(ch)

        # è¡¥é½æªé­åçæ¬å·
        while stack:
            opener = stack.pop()
            result.append(opener_map[opener])
            mutated = True

        return "".join(result), mutated

    def _remove_trailing_commas(self, text: str) -> Tuple[str, bool]:
        """
        ç§»é¤JSONå¯¹è±¡åæ°ç»ä¸­çå°¾ééå·

        åæ°:
            text: åå§JSONææ¬

        è¿å:
            Tuple[str, bool]: (ä¿®å¤åçææ¬, æ¯å¦æä¿®æ?
        """
        if not text:
            return text, False

        # ä½¿ç¨æ­£åè¡¨è¾¾å¼ç§»é¤å°¾ééå·
        # å¹é , åé¢è·çç©ºç½å?} æ?] çæå?
        pattern = r",(\s*[}\]])"
        new_text = re.sub(pattern, r"\1", text)

        return new_text, new_text != text

    def _attempt_json_repair(self, text: str, context_name: str) -> Optional[str]:
        """
        ä½¿ç¨json_repairåºè¿è¡é«çº§ä¿®å¤

        åæ°:
            text: åå§JSONææ¬
            context_name: ä¸ä¸æåç§?

        è¿å:
            Optional[str]: ä¿®å¤åçJSONææ¬ï¼å¤±è´¥è¿åNone
        """
        if not _json_repair_fn:
            return None

        try:
            fixed = _json_repair_fn(text)
            if fixed and fixed != text:
                logger.info(f"{context_name} ä½¿ç¨json_repairåºèªå¨ä¿®å¤JSON")
                return fixed
        except Exception as exc:
            logger.debug(f"{context_name} json_repairä¿®å¤å¤±è´¥: {exc}")

        return None

    def _attempt_llm_repair(
        self, text: str, error_msg: str, context_name: str
    ) -> Optional[str]:
        """
        ä½¿ç¨LLMè¿è¡JSONä¿®å¤

        åæ°:
            text: åå§JSONææ¬
            error_msg: è§£æéè¯¯ä¿¡æ¯
            context_name: ä¸ä¸æåç§?

        è¿å:
            Optional[str]: ä¿®å¤åçJSONææ¬ï¼å¤±è´¥è¿åNone
        """
        if not self.llm_repair_fn:
            return None

        try:
            logger.info(f"{context_name} å°è¯ä½¿ç¨LLMä¿®å¤JSON")
            repaired = self.llm_repair_fn(text, error_msg)
            if repaired and repaired != text:
                return repaired
        except Exception as exc:
            logger.warning(f"{context_name} LLMä¿®å¤å¤±è´¥: {exc}")

        return None

    def _extract_and_validate(
        self,
        data: Any,
        expected_keys: Optional[List[str]],
        extract_wrapper_key: Optional[str],
        context_name: str,
    ) -> Dict[str, Any]:
        """
        æåå¹¶éªè¯JSONæ°æ®

        åæ°:
            data: è§£æåçæ°æ®
            expected_keys: ææçé®åè¡¨
            extract_wrapper_key: åè£¹é®å
            context_name: ä¸ä¸æåç§?

        è¿å:
            Dict[str, Any]: æåå¹¶éªè¯åçæ°æ?

        å¼å¸¸:
            JSONParseError: å¦ææ°æ®æ ¼å¼ä¸ç¬¦åé¢æ?
        """
        # æååè£¹çæ°æ?
        if extract_wrapper_key and isinstance(data, dict):
            if extract_wrapper_key in data:
                data = data[extract_wrapper_key]
            else:
                logger.warning(
                    f"{context_name} æªæ¾å°åè£¹é®'{extract_wrapper_key}'ï¼ä½¿ç¨åå§æ°æ?
                )

        # éªè¯æ°æ®ç±»å
        if not isinstance(data, dict):
            if isinstance(data, list):
                if len(data) > 0:
                    # å°è¯æ¾å°æç¬¦åææçåç´?
                    best_match = None
                    max_match_count = 0

                    for item in data:
                        if isinstance(item, dict):
                            if expected_keys:
                                # è®¡ç®å¹éçé®æ°é
                                match_count = sum(1 for key in expected_keys if key in item)
                                if match_count > max_match_count:
                                    max_match_count = match_count
                                    best_match = item
                            elif best_match is None:
                                best_match = item

                    if best_match:
                        logger.warning(
                            f"{context_name} è¿åæ°ç»ï¼èªå¨æåæä½³å¹éåç´ ï¼å¹é{max_match_count}/{len(expected_keys or [])}ä¸ªé®ï¼?
                        )
                        data = best_match
                    else:
                        raise JSONParseError(
                            f"{context_name} è¿åçæ°ç»ä¸­æ²¡æææçå¯¹è±?
                        )
                else:
                    raise JSONParseError(f"{context_name} è¿åç©ºæ°ç»?)
            else:
                raise JSONParseError(
                    f"{context_name} è¿åçä¸æ¯JSONå¯¹è±¡: {type(data).__name__}"
                )

        # éªè¯å¿éçé®
        if expected_keys:
            missing_keys = [key for key in expected_keys if key not in data]
            if missing_keys:
                logger.warning(
                    f"{context_name} ç¼ºå°é¢æçé®: {', '.join(missing_keys)}"
                )
                # å°è¯ä¿®å¤å¸¸è§çé®ååä½?
                data = self._try_recover_missing_keys(data, missing_keys, context_name)

        return data

    def _try_recover_missing_keys(
        self, data: Dict[str, Any], missing_keys: List[str], context_name: str
    ) -> Dict[str, Any]:
        """
        å°è¯ä»æ°æ®ä¸­æ¢å¤ç¼ºå¤±çé®ï¼éè¿æ¥æ¾ç¸ä¼¼çé®å

        åæ°:
            data: åå§æ°æ®
            missing_keys: ç¼ºå¤±çé®åè¡¨
            context_name: ä¸ä¸æåç§?

        è¿å:
            Dict[str, Any]: ä¿®å¤åçæ°æ®
        """
        # å¸¸è§çé®åæ å°?
        key_aliases = {
            "template_name": ["templateName", "name", "template"],
            "selection_reason": ["selectionReason", "reason", "explanation"],
            "title": ["reportTitle", "documentTitle"],
            "chapters": ["chapterList", "chapterPlan", "sections"],
            "totalWords": ["total_words", "wordCount", "totalWordCount"],
        }

        for missing_key in missing_keys:
            if missing_key in key_aliases:
                for alias in key_aliases[missing_key]:
                    if alias in data:
                        logger.info(
                            f"{context_name} æ¾å°é?{missing_key}'çå«å?{alias}'ï¼èªå¨æ å°?
                        )
                        data[missing_key] = data[alias]
                        break

        return data


__all__ = ["RobustJSONParser", "JSONParseError"]
