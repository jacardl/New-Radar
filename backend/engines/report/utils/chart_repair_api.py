ï»¿"""
å¾è¡¨APIä¿®å¤æ¨¡åï¿½?

æä¾è°ç¨4ä¸ªEngineï¼ReportEngine, ForumEngine, InsightEngine, MediaEngineï¼çLLM API
æ¥ä¿®å¤å¾è¡¨æ°æ®çåè½ï¿½?
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from loguru import logger

from backend.engines.report.utils.config import settings


# å¾è¡¨ä¿®å¤æç¤ºï¿½?
CHART_REPAIR_SYSTEM_PROMPT = """ä½ æ¯ä¸ä¸ªä¸ä¸çå¾è¡¨æ°æ®ä¿®å¤å©æãä½ çä»»å¡æ¯ä¿®å¤Chart.jså¾è¡¨æ°æ®ä¸­çæ ¼å¼éè¯¯ï¼ç¡®ä¿å¾è¡¨è½å¤æ­£å¸¸æ¸²æï¿½?

**Chart.jsæ åæ°æ®æ ¼å¼ï¿½?*

1. æ åå¾è¡¨ï¼line, bar, pie, doughnut, radar, polarAreaï¼ï¼
```json
{
  "type": "widget",
  "widgetType": "chart.js/bar",
  "widgetId": "chart-001",
  "props": {
    "type": "bar",
    "title": "å¾è¡¨æ é¢",
    "options": {
      "responsive": true,
      "plugins": {
        "legend": {
          "display": true
        }
      }
    }
  },
  "data": {
    "labels": ["A", "B", "C"],
    "datasets": [
      {
        "label": "ç³»å1",
        "data": [10, 20, 30]
      }
    ]
  }
}
```

2. ç¹æ®å¾è¡¨ï¼scatter, bubbleï¼ï¼
```json
{
  "data": {
    "datasets": [
      {
        "label": "ç³»å1",
        "data": [
          {"x": 10, "y": 20},
          {"x": 15, "y": 25}
        ]
      }
    ]
  }
}
```

**ä¿®å¤ååï¿½?*
1. **å®æ¿ä¸æ¹ï¼ä¹ä¸è¦æ¹é** - å¦æä¸ç¡®å®å¦ä½ä¿®å¤ï¼ä¿æåå§æ°æ®
2. **æå°æ¹ï¿½?* - åªä¿®å¤æç¡®çéè¯¯ï¼ä¸è¦è¿åº¦ä¿®ï¿½?
3. **ä¿ææ°æ®å®æ´ï¿½?* - ä¸è¦ä¸¢å¤±åå§æ°æ®
4. **éªè¯ä¿®å¤ç»æ** - ç¡®ä¿ä¿®å¤åç¬¦åChart.jsæ ¼å¼

**å¸¸è§éè¯¯åä¿®å¤æ¹æ³ï¼**
1. ç¼ºå°labelså­æ®µ ï¿½?æ ¹æ®æ°æ®çæé»è®¤labels
2. datasetsä¸æ¯æ°ç» ï¿½?è½¬æ¢ä¸ºæ°ç»æ ¼ï¿½?
3. æ°æ®é¿åº¦ä¸å¹ï¿½?ï¿½?æªæ­æè¡¥null
4. éæ°å¼æ°ï¿½?ï¿½?å°è¯è½¬æ¢æè®¾ä¸ºnull
5. ç¼ºå°å¿éå­æ®µ ï¿½?æ·»å é»è®¤ï¿½?

è¯·æ ¹æ®éè¯¯ä¿¡æ¯ä¿®å¤å¾è¡¨æ°æ®ï¼å¹¶è¿åä¿®å¤åçå®æ´widget blockï¼JSONæ ¼å¼ï¼ï¿½?
"""


# è¡¨æ ¼ä¿®å¤æç¤ºï¿½?
TABLE_REPAIR_SYSTEM_PROMPT = """ä½ æ¯ä¸ä¸ªä¸ä¸çè¡¨æ ¼æ°æ®ä¿®å¤å©æãä½ çä»»å¡æ¯ä¿®å¤IRè¡¨æ ¼æ°æ®ä¸­çæ ¼å¼éè¯¯ï¼ç¡®ä¿è¡¨æ ¼è½å¤æ­£å¸¸æ¸²æï¿½?

**æ åè¡¨æ ¼æ°æ®æ ¼å¼ï¿½?*

```json
{
  "type": "table",
  "rows": [
    {
      "cells": [
        {
          "header": true,
          "blocks": [
            {
              "type": "paragraph",
              "inlines": [{"text": "åæ ï¿½?, "marks": []}]
            }
          ]
        },
        {
          "header": true,
          "blocks": [
            {
              "type": "paragraph",
              "inlines": [{"text": "å¦ä¸ï¿½?, "marks": []}]
            }
          ]
        }
      ]
    },
    {
      "cells": [
        {
          "blocks": [
            {
              "type": "paragraph",
              "inlines": [{"text": "æ°æ®åå®¹", "marks": []}]
            }
          ]
        },
        {
          "blocks": [
            {
              "type": "paragraph",
              "inlines": [{"text": "å¦ä¸æ°æ®", "marks": []}]
            }
          ]
        }
      ]
    }
  ]
}
```

**â ï¸ å¸¸è§éè¯¯ï¼åµï¿½?cells ç»æ**

è¿æ¯ä¸ä¸ªéå¸¸å¸¸è§çéè¯¯ï¼LLM ç»å¸¸æåçº§ç cells éè¯¯å°åµå¥èµ·æ¥ï¼

ï¿½?**éè¯¯ç¤ºä¾ï¿½?*
```json
{
  "cells": [
    { "blocks": [...], "colspan": 1 },
    { "cells": [
        { "blocks": [...] },
        { "cells": [...] }
      ]
    }
  ]
}
```

ï¿½?**æ­£ç¡®æ ¼å¼ï¿½?*
```json
{
  "cells": [
    { "blocks": [...], "colspan": 1 },
    { "blocks": [...] },
    { "blocks": [...] }
  ]
}
```

**ä¿®å¤ååï¿½?*
1. **å±å¹³åµå¥ cells** - å°éè¯¯åµå¥ç cells å±å¹³ä¸ºåï¿½?
2. **ç¡®ä¿æ¯ä¸ª cell ï¿½?blocks** - æ¯ä¸ªååæ ¼å¿é¡»æ blocks æ°ç»
3. **blocks åä½¿ï¿½?paragraph** - ææ¬åå®¹åºæ¾ï¿½?paragraph block ï¿½?
4. **ä¿ææ°æ®å®æ´ï¿½?* - ä¸è¦ä¸¢å¤±åå§åå®¹

**ä¿®å¤æ¹æ³ï¿½?*
1. åµå¥ cells ç»æ ï¿½?å±å¹³ä¸ºåï¿½?cells æ°ç»
2. ç¼ºå° blocks å­æ®µ ï¿½?æ·»å åå« paragraph ï¿½?blocks
3. ï¿½?cells æ°ç» ï¿½?æ·»å é»è®¤ç©ºååæ ¼
4. éæ³ cell ç±»å ï¿½?è½¬æ¢ä¸ºæ åæ ¼ï¿½?

è¯·æ ¹æ®éè¯¯ä¿¡æ¯ä¿®å¤è¡¨æ ¼æ°æ®ï¼å¹¶è¿åä¿®å¤åçå®ï¿½?table blockï¼JSONæ ¼å¼ï¼ï¿½?
"""


# è¯äºä¿®å¤æç¤ºï¿½?
WORDCLOUD_REPAIR_SYSTEM_PROMPT = """ä½ æ¯ä¸ä¸ªä¸ä¸çè¯äºæ°æ®ä¿®å¤å©æãä½ çä»»å¡æ¯ä¿®å¤è¯äº widget æ°æ®ä¸­çæ ¼å¼éè¯¯ï¼ç¡®ä¿è¯äºè½å¤æ­£å¸¸æ¸²æï¿½?

**æ åè¯äºæ°æ®æ ¼å¼ï¿½?*

```json
{
  "type": "widget",
  "widgetType": "wordcloud",
  "widgetId": "wordcloud-001",
  "title": "è¯äºæ é¢",
  "data": {
    "words": [
      {"text": "å³é®ï¿½?", "weight": 10},
      {"text": "å³é®ï¿½?", "weight": 8},
      {"text": "å³é®ï¿½?", "weight": 6}
    ]
  }
}
```

**â ï¸ æ°æ®è·¯å¾è¯´æï¿½?*

è¯äºæ°æ®å¯ä»¥ä½äºä»¥ä¸è·¯å¾ï¼æä¼åçº§ï¼ï¿½?
1. `data.words` - æ¨èè·¯å¾
2. `data.items` - å¤éè·¯ï¿½?
3. `props.words` - å¤éè·¯ï¿½?
4. `props.items` - å¤éè·¯ï¿½?
5. `props.data` - å¤éè·¯ï¿½?

**è¯äºé¡¹ç®æ ¼å¼ï¿½?*

æ¯ä¸ªè¯äºé¡¹ç®åºè¯¥æ¯ä¸ä¸ªå¯¹è±¡ï¼åå«ï¿½?
- `text` ï¿½?`word` ï¿½?`label`: è¯è¯­ææ¬ï¼å¿éï¿½?
- `weight` ï¿½?`value`: æé/é¢çï¼å¿éï¿½?
- `category`: ç±»å«ï¼å¯éï¼

**ä¿®å¤ååï¿½?*
1. **è§èåæ°æ®è·¯ï¿½?* - ä¼åä½¿ç¨ `data.words`
2. **ç¡®ä¿å¿éå­æ®µ** - æ¯ä¸ªè¯é¡¹å¿é¡»æææ¬åæé
3. **è½¬æ¢å¼å®¹æ ¼å¼** - å°å¶ä»æ ¼å¼è½¬æ¢ä¸ºæ åæ ¼å¼
4. **ä¿ææ°æ®å®æ´ï¿½?* - ä¸è¦ä¸¢å¤±åå§è¯è¯­

**å¸¸è§éè¯¯åä¿®å¤æ¹æ³ï¼**
1. æ°æ®ä½äºéè¯¯è·¯å¾ ï¿½?ç§»å¨ï¿½?`data.words`
2. ç¼ºå° weight å­æ®µ ï¿½?æ ¹æ®ä½ç½®çæé»è®¤æé
3. ä½¿ç¨ word èé text ï¿½?ç»ä¸ï¿½?text å­æ®µ
4. æ°ç»åç´ æ¯å­ç¬¦ä¸² ï¿½?è½¬æ¢ä¸ºå¯¹è±¡æ ¼ï¿½?

è¯·æ ¹æ®éè¯¯ä¿¡æ¯ä¿®å¤è¯äºæ°æ®ï¼å¹¶è¿åä¿®å¤åçå®ï¿½?widget blockï¼JSONæ ¼å¼ï¼ï¿½?
"""


def build_table_repair_prompt(
    table_block: Dict[str, Any],
    validation_errors: List[str]
) -> str:
    """
    æå»ºè¡¨æ ¼ä¿®å¤æç¤ºè¯ï¿½?

    Args:
        table_block: åå§ table block
        validation_errors: éªè¯éè¯¯åè¡¨

    Returns:
        str: æç¤ºï¿½?
    """
    block_json = json.dumps(table_block, ensure_ascii=False, indent=2)
    errors_text = "\n".join(f"- {error}" for error in validation_errors)

    prompt = f"""è¯·ä¿®å¤ä»¥ä¸è¡¨æ ¼æ°æ®ä¸­çéè¯¯ï¼

**åå§æ°æ®ï¿½?*
```json
{block_json}
```

**æ£æµå°çéè¯¯ï¼**
{errors_text}

**è¦æ±ï¿½?*
1. è¿åä¿®å¤åçå®æ´ table blockï¼JSONæ ¼å¼ï¿½?
2. ç¹å«æ³¨æå±å¹³åµå¥ï¿½?cells ç»æ
3. ç¡®ä¿æ¯ä¸ª cell é½æ blocks æ°ç»
4. å¦ææ æ³ç¡®å®å¦ä½ä¿®å¤ï¼ä¿æåå§æ°ï¿½?

**éè¦çè¾åºæ ¼å¼è¦æ±ï¼**
1. åªè¿åçº¯JSONå¯¹è±¡ï¼ä¸è¦æ·»å ä»»ä½è¯´ææï¿½?
2. ä¸è¦ä½¿ç¨```json```æ è®°åè£¹
3. ç¡®ä¿JSONè¯­æ³å®å¨æ­£ç¡®
4. ææå­ç¬¦ä¸²ä½¿ç¨åå¼ï¿½?
"""
    return prompt


def build_wordcloud_repair_prompt(
    widget_block: Dict[str, Any],
    validation_errors: List[str]
) -> str:
    """
    æå»ºè¯äºä¿®å¤æç¤ºè¯ï¿½?

    Args:
        widget_block: åå§ wordcloud widget block
        validation_errors: éªè¯éè¯¯åè¡¨

    Returns:
        str: æç¤ºï¿½?
    """
    block_json = json.dumps(widget_block, ensure_ascii=False, indent=2)
    errors_text = "\n".join(f"- {error}" for error in validation_errors)

    prompt = f"""è¯·ä¿®å¤ä»¥ä¸è¯äºæ°æ®ä¸­çéè¯¯ï¼

**åå§æ°æ®ï¿½?*
```json
{block_json}
```

**æ£æµå°çéè¯¯ï¼**
{errors_text}

**è¦æ±ï¿½?*
1. è¿åä¿®å¤åçå®æ´ widget blockï¼JSONæ ¼å¼ï¿½?
2. ç¡®ä¿è¯äºæ°æ®ä½äº data.words è·¯å¾
3. æ¯ä¸ªè¯é¡¹å¿é¡»ï¿½?text ï¿½?weight å­æ®µ
4. å¦ææ æ³ç¡®å®å¦ä½ä¿®å¤ï¼ä¿æåå§æ°ï¿½?

**éè¦çè¾åºæ ¼å¼è¦æ±ï¼**
1. åªè¿åçº¯JSONå¯¹è±¡ï¼ä¸è¦æ·»å ä»»ä½è¯´ææï¿½?
2. ä¸è¦ä½¿ç¨```json```æ è®°åè£¹
3. ç¡®ä¿JSONè¯­æ³å®å¨æ­£ç¡®
4. ææå­ç¬¦ä¸²ä½¿ç¨åå¼ï¿½?
"""
    return prompt


def build_chart_repair_prompt(
    widget_block: Dict[str, Any],
    validation_errors: List[str]
) -> str:
    """
    æå»ºå¾è¡¨ä¿®å¤æç¤ºè¯ï¿½?

    Args:
        widget_block: åå§widget block
        validation_errors: éªè¯éè¯¯åè¡¨

    Returns:
        str: æç¤ºï¿½?
    """
    block_json = json.dumps(widget_block, ensure_ascii=False, indent=2)
    errors_text = "\n".join(f"- {error}" for error in validation_errors)

    prompt = f"""è¯·ä¿®å¤ä»¥ä¸å¾è¡¨æ°æ®ä¸­çéè¯¯ï¼

**åå§æ°æ®ï¿½?*
```json
{block_json}
```

**æ£æµå°çéè¯¯ï¼**
{errors_text}

**è¦æ±ï¿½?*
1. è¿åä¿®å¤åçå®æ´widget blockï¼JSONæ ¼å¼ï¿½?
2. åªä¿®å¤æç¡®çéè¯¯ï¼ä¿æå¶ä»æ°æ®ä¸ï¿½?
3. ç¡®ä¿ä¿®å¤åçæ°æ®ç¬¦åChart.jsæ ¼å¼è¦æ±
4. å¦ææ æ³ç¡®å®å¦ä½ä¿®å¤ï¼ä¿æåå§æ°ï¿½?

**éè¦çè¾åºæ ¼å¼è¦æ±ï¼**
1. åªè¿åçº¯JSONå¯¹è±¡ï¼ä¸è¦æ·»å ä»»ä½è¯´ææï¿½?
2. ä¸è¦ä½¿ç¨```json```æ è®°åè£¹
3. ç¡®ä¿JSONè¯­æ³å®å¨æ­£ç¡®
4. ææå­ç¬¦ä¸²ä½¿ç¨åå¼ï¿½?
"""
    return prompt


def create_llm_repair_functions() -> List:
    """
    åå»ºLLMä¿®å¤å½æ°åè¡¨ï¿½?

    è¿å4ä¸ªEngineçä¿®å¤å½æ°ï¼
    1. ReportEngine
    2. ForumEngine (éè¿ForumHost)
    3. InsightEngine
    4. MediaEngine

    Returns:
        List[Callable]: ä¿®å¤å½æ°åè¡¨
    """
    repair_functions = []

    # 1. ReportEngineä¿®å¤å½æ°
    if settings.REPORT_ENGINE_API_KEY and settings.REPORT_ENGINE_BASE_URL:
        def repair_with_report_engine(widget_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨ReportEngineçLLMä¿®å¤å¾è¡¨"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.REPORT_ENGINE_API_KEY,
                    base_url=settings.REPORT_ENGINE_BASE_URL,
                    model_name=settings.REPORT_ENGINE_MODEL_NAME or "gpt-4",
                )

                prompt = build_chart_repair_prompt(widget_block, errors)
                response = client.invoke(
                    CHART_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                # è§£æååº
                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"ReportEngineå¾è¡¨ä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_with_report_engine)
        logger.debug("å·²æ·»å ReportEngineå¾è¡¨ä¿®å¤å½æ°")

    # 2. ForumEngineä¿®å¤å½æ°
    if settings.FORUM_HOST_API_KEY and settings.FORUM_HOST_BASE_URL:
        def repair_with_forum_engine(widget_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨ForumEngineçLLMä¿®å¤å¾è¡¨"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.FORUM_HOST_API_KEY,
                    base_url=settings.FORUM_HOST_BASE_URL,
                    model_name=settings.FORUM_HOST_MODEL_NAME or "gpt-4",
                )

                prompt = build_chart_repair_prompt(widget_block, errors)
                response = client.invoke(
                    CHART_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"ForumEngineå¾è¡¨ä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_with_forum_engine)
        logger.debug("å·²æ·»å ForumEngineå¾è¡¨ä¿®å¤å½æ°")

    # 3. InsightEngineä¿®å¤å½æ°
    if settings.INSIGHT_ENGINE_API_KEY and settings.INSIGHT_ENGINE_BASE_URL:
        def repair_with_insight_engine(widget_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨InsightEngineçLLMä¿®å¤å¾è¡¨"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.INSIGHT_ENGINE_API_KEY,
                    base_url=settings.INSIGHT_ENGINE_BASE_URL,
                    model_name=settings.INSIGHT_ENGINE_MODEL_NAME or "gpt-4",
                )

                prompt = build_chart_repair_prompt(widget_block, errors)
                response = client.invoke(
                    CHART_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"InsightEngineå¾è¡¨ä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_with_insight_engine)
        logger.debug("å·²æ·»å InsightEngineå¾è¡¨ä¿®å¤å½æ°")

    # 4. MediaEngineä¿®å¤å½æ°
    if settings.MEDIA_ENGINE_API_KEY and settings.MEDIA_ENGINE_BASE_URL:
        def repair_with_media_engine(widget_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨MediaEngineçLLMä¿®å¤å¾è¡¨"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.MEDIA_ENGINE_API_KEY,
                    base_url=settings.MEDIA_ENGINE_BASE_URL,
                    model_name=settings.MEDIA_ENGINE_MODEL_NAME or "gpt-4",
                )

                prompt = build_chart_repair_prompt(widget_block, errors)
                response = client.invoke(
                    CHART_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"MediaEngineå¾è¡¨ä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_with_media_engine)
        logger.debug("å·²æ·»å MediaEngineå¾è¡¨ä¿®å¤å½æ°")

    if not repair_functions:
        logger.warning("æªéç½®ä»»ä½Engine APIï¼å¾è¡¨APIä¿®å¤åè½å°ä¸å¯ç¨")
    else:
        logger.info(f"å¾è¡¨APIä¿®å¤åè½å·²å¯ç¨ï¼ï¿½?{len(repair_functions)} ä¸ªEngineå¯ç¨")

    return repair_functions


def create_table_repair_functions() -> List:
    """
    åå»ºè¡¨æ ¼ LLM ä¿®å¤å½æ°åè¡¨ï¿½?

    ä½¿ç¨ä¸å¾è¡¨ä¿®å¤ç¸åç Engine éç½®ï¿½?

    Returns:
        List[Callable]: ä¿®å¤å½æ°åè¡¨
    """
    repair_functions = []

    # ä½¿ç¨ ReportEngine ä¿®å¤è¡¨æ ¼
    if settings.REPORT_ENGINE_API_KEY and settings.REPORT_ENGINE_BASE_URL:
        def repair_table_with_report_engine(table_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨ ReportEngine ï¿½?LLM ä¿®å¤è¡¨æ ¼"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.REPORT_ENGINE_API_KEY,
                    base_url=settings.REPORT_ENGINE_BASE_URL,
                    model_name=settings.REPORT_ENGINE_MODEL_NAME or "gpt-4",
                )

                prompt = build_table_repair_prompt(table_block, errors)
                response = client.invoke(
                    TABLE_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                # è§£æååº
                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"ReportEngine è¡¨æ ¼ä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_table_with_report_engine)
        logger.debug("å·²æ·»ï¿½?ReportEngine è¡¨æ ¼ä¿®å¤å½æ°")

    if not repair_functions:
        logger.warning("æªéç½®ä»»ï¿½?Engine APIï¼è¡¨ï¿½?API ä¿®å¤åè½å°ä¸å¯ç¨")
    else:
        logger.info(f"è¡¨æ ¼ API ä¿®å¤åè½å·²å¯ç¨ï¼ï¿½?{len(repair_functions)} ï¿½?Engine å¯ç¨")

    return repair_functions


def create_wordcloud_repair_functions() -> List:
    """
    åå»ºè¯äº LLM ä¿®å¤å½æ°åè¡¨ï¿½?

    ä½¿ç¨ä¸å¾è¡¨ä¿®å¤ç¸åç Engine éç½®ï¿½?

    Returns:
        List[Callable]: ä¿®å¤å½æ°åè¡¨
    """
    repair_functions = []

    # ä½¿ç¨ ReportEngine ä¿®å¤è¯äº
    if settings.REPORT_ENGINE_API_KEY and settings.REPORT_ENGINE_BASE_URL:
        def repair_wordcloud_with_report_engine(widget_block: Dict[str, Any], errors: List[str]) -> Optional[Dict[str, Any]]:
            """ä½¿ç¨ ReportEngine ï¿½?LLM ä¿®å¤è¯äº"""
            try:
                from backend.engines.report.llms import LLMClient

                client = LLMClient(
                    api_key=settings.REPORT_ENGINE_API_KEY,
                    base_url=settings.REPORT_ENGINE_BASE_URL,
                    model_name=settings.REPORT_ENGINE_MODEL_NAME or "gpt-4",
                )

                prompt = build_wordcloud_repair_prompt(widget_block, errors)
                response = client.invoke(
                    WORDCLOUD_REPAIR_SYSTEM_PROMPT,
                    prompt,
                    temperature=0.0,
                    top_p=0.05
                )

                if not response:
                    return None

                # è§£æååº
                repaired = json.loads(response)
                return repaired

            except Exception as e:
                logger.exception(f"ReportEngine è¯äºä¿®å¤å¤±è´¥: {e}")
                return None

        repair_functions.append(repair_wordcloud_with_report_engine)
        logger.debug("å·²æ·»ï¿½?ReportEngine è¯äºä¿®å¤å½æ°")

    if not repair_functions:
        logger.warning("æªéç½®ä»»ï¿½?Engine APIï¼è¯ï¿½?API ä¿®å¤åè½å°ä¸å¯ç¨")
    else:
        logger.info(f"è¯äº API ä¿®å¤åè½å·²å¯ç¨ï¼ï¿½?{len(repair_functions)} ï¿½?Engine å¯ç¨")

    return repair_functions
