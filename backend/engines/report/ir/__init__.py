"""
Report Engineçå¯æ§è¡JSONå¥çº¦(IR)å®ä¹ä¸æ ¡éªå·¥å·

è¯¥æ¨¡åæ´é²ç»ä¸çSchemaææ¬ä¸æ ¡éªå¨ï¼ä¾æç¤ºè¯ãç« èçæ
ä»¥åæç»è£è®¢æµç¨å±åå¤ç¨ï¼ç¡®ä¿ä»LLMå°æ¸²æçäº§ç©ç»æä¸è´
"""

from .schema import (
    IR_VERSION,
    CHAPTER_JSON_SCHEMA,
    CHAPTER_JSON_SCHEMA_TEXT,
    ALLOWED_BLOCK_TYPES,
    ALLOWED_INLINE_MARKS,
    ENGINE_AGENT_TITLES,
)
from .validator import IRValidator

__all__ = [
    "IR_VERSION",
    "CHAPTER_JSON_SCHEMA",
    "CHAPTER_JSON_SCHEMA_TEXT",
    "ALLOWED_BLOCK_TYPES",
    "ALLOWED_INLINE_MARKS",
    "ENGINE_AGENT_TITLES",
    "IRValidator",
]
