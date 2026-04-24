ï»¿#!/usr/bin/env python3
"""
çæè¦çå¨é¨åè®¸blockç±»åçæ¼ï¿½?IRï¼ç¨äºéªï¿½?HTML / PDF / Markdown æ¸²æï¿½?

æ§è¡åä¼ï¿½?`final_reports/ir` åå¥ä¸ä»½å¸¦æ¶é´æ³ç IRï¿½?
å¹¶åå«å¨ `final_reports/html`final_reports/pdf` ï¿½?`final_reports/md`
è¾åºå¯¹åºçæ¸²ææä»¶ï¿½?
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# åè®¸ç´æ¥ä»¥èæ¬å½¢å¼è¿ï¿½?
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.engines.report.core import DocumentComposer
from backend.engines.report.ir import IRValidator
from backend.engines.report.ir.schema import ENGINE_AGENT_TITLES
from backend.engines.report.renderers import HTMLRenderer, MarkdownRenderer, PDFRenderer
from backend.engines.report.utils.config import settings


def build_inline_marks_demo() -> dict:
    """çæè¦çå¨é¨åèæ è®°ï¿½?paragraph blockï¿½?""
    return {
        "type": "paragraph",
        "inlines": [
            {"text": "è¿ä¸æ®µè¦çå¨é¨åèæ è®°ï¼"},
            {"text": "ç²ä½", "marks": [{"type": "bold"}]},
            {"text": " / æä½", "marks": [{"type": "italic"}]},
            {"text": " / ä¸åï¿½?, "marks": [{"type": "underline"}]},
            {"text": " / å é¤ï¿½?, "marks": [{"type": "strike"}]},
            {"text": " / ä»£ç ", "marks": [{"type": "code"}]},
            {
                "text": " / é¾æ¥",
                "marks": [
                    {
                        "type": "link",
                        "href": "https://example.com/demo",
                        "title": "ç¤ºä¾é¾æ¥",
                    }
                ],
            },
            {"text": " / é¢è²", "marks": [{"type": "color", "value": "#c0392b"}]},
            {
                "text": " / å­ä½",
                "marks": [
                    {
                        "type": "font",
                        "family": "Georgia, serif",
                        "size": "15px",
                        "weight": "600",
                    }
                ],
            },
            {"text": " / é«äº®", "marks": [{"type": "highlight"}]},
            {"text": " / ä¸æ ", "marks": [{"type": "subscript"}]},
            {"text": " / ä¸æ ", "marks": [{"type": "superscript"}]},
            {"text": " / è¡åå¬å¼", "marks": [{"type": "math", "value": "E=mc^2"}]},
            {"text": "ï¿½?},
        ],
    }


def build_widget_block() -> dict:
    """æé ä¸ä¸ªåæ³ç Chart.js widget blockï¿½?""
    return {
        "type": "widget",
        "widgetId": "demo-volume-trend",
        "widgetType": "chart.js/line",
        "props": {
            "type": "line",
            "options": {
                "responsive": True,
                "plugins": {"legend": {"position": "bottom"}},
                "scales": {"y": {"title": {"display": True, "text": "æåï¿½?}}},
            },
        },
        "data": {
            "labels": ["T0", "T0+6h", "T0+12h", "T0+18h", "T0+24h"],
            "datasets": [
                {
                    "label": "ä¸»æµåªä½",
                    "data": [12, 18, 23, 30, 26],
                    "borderColor": "#2980b9",
                    "backgroundColor": "rgba(41,128,185,0.18)",
                    "tension": 0.25,
                    "fill": False,
                },
                {
                    "label": "ç¤¾äº¤å¹³å°",
                    "data": [8, 10, 15, 28, 40],
                    "borderColor": "#c0392b",
                    "backgroundColor": "rgba(192,57,43,0.2)",
                    "tension": 0.35,
                    "fill": False,
                },
            ],
        },
    }


def build_chapters() -> list[dict]:
    """æé è¦çæï¿½?block ç±»åçç« èåè¡¨ï¿½?""
    inline_demo = build_inline_marks_demo()

    bullet_list = {
        "type": "list",
        "listType": "bullet",
        "items": [
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "ç¤¾äº¤åªä½ç­åº¦ï¿½?48 å°æ¶åç¿»ï¿½?}],
                }
            ],
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "ä¸»æµåªä½æ¥ééä¸­å¨æ©é´æ¶ï¿½?}],
                },
                {
                    "type": "list",
                    "listType": "ordered",
                    "items": [
                        [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "07:00-09:00ï¼é¦è½®æ¥ï¿½?}],
                            }
                        ],
                        [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "10:00-12:00ï¼è¯è®ºæ©ï¿½?}],
                            }
                        ],
                    ],
                },
            ],
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "å°æ¹æ¿å¡å·å¼å§ååºå¹¶åæ­¥çº¿ä¸éç¨¿"}],
                }
            ],
        ],
    }

    task_list = {
        "type": "list",
        "listType": "task",
        "items": [
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "è·è¸ªæå¨è¾è°£ç´ ææ¯å¦ä¸çº¿"}],
                }
            ],
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "çæµæ°å¢å³èå³é®è¯ä¸é¿å°¾é®é¢"}],
                }
            ],
            [
                {
                    "type": "paragraph",
                    "inlines": [{"text": "åå¤ FAQ ä¾å®¢æç»ä¸ç­å¤"}],
                }
            ],
        ],
    }

    table_block = {
        "type": "table",
        "caption": "æ ¸å¿ä¿¡æºä¸ä¼ æ­è·¯ï¿½?,
        "zebra": True,
        "colgroup": [{"width": "22%"}, {"width": "38%"}, {"width": "40%"}],
        "rows": [
            {
                "cells": [
                    {
                        "align": "center",
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "æ¶é´èç¹", "marks": [{"type": "bold"}]}],
                            }
                        ],
                    },
                    {
                        "align": "center",
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "äºä»¶åå®¹", "marks": [{"type": "bold"}]}],
                            }
                        ],
                    },
                    {
                        "align": "center",
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "ä¸»è¦æ¸ é", "marks": [{"type": "bold"}]}],
                            }
                        ],
                    },
                ]
            },
            {
                "cells": [
                    {"blocks": [{"type": "paragraph", "inlines": [{"text": "T0"}]}]},
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "çº¿ä¸å²çªè§é¢é¦æ¬¡ä¸ä¼ "}],
                            }
                        ]
                    },
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "ç­è§é¢å¹³ï¿½?/ ç§èè½¬å"}],
                            }
                        ]
                    },
                ]
            },
            {
                "cells": [
                    {"blocks": [{"type": "paragraph", "inlines": [{"text": "T0+6h"}]}]},
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "ç»ä¸ç­æï¼åºç°äºæ¬¡åªï¿½?}],
                            }
                        ]
                    },
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "å¾®å / æåï¿½?}],
                            }
                        ]
                    },
                ]
            },
            {
                "cells": [
                    {"blocks": [{"type": "paragraph", "inlines": [{"text": "T0+18h"}]}]},
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "å®æ¹ååºå¹¶åå¸äºå®æ¾ï¿½?}],
                            }
                        ]
                    },
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "æ¿å¡ï¿½?/ æ°é»å®¢æ·ï¿½?}],
                            }
                        ]
                    },
                ]
            },
            {
                "cells": [
                    {"blocks": [{"type": "paragraph", "inlines": [{"text": "T0+24h"}]}]},
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "ä¸å®¶è§£è¯»ï¼èè®ºéå¿è½¬åè´£ä»»å½ï¿½?}],
                            }
                        ]
                    },
                    {
                        "blocks": [
                            {
                                "type": "paragraph",
                                "inlines": [{"text": "è§é¢å·ç´ï¿½?/ è¡ä¸ç¤¾ç¾¤"}],
                            }
                        ]
                    },
                ]
            },
        ],
    }

    blockquote_block = {
        "type": "blockquote",
        "variant": "accent",
        "blocks": [
            {
                "type": "paragraph",
                "inlines": [{"text": ""å¬ä¼æå³å¿çä¿¡æ¯æ¯çç¸ä¸è´£ä»»è¾¹çãï¿½?}],
            },
            {
                "type": "paragraph",
                "inlines": [{"text": "-ï¿½?æ¨¡æå¼ç¨ï¼éªè¯å¼ç¨åæ ·å¼"}],
            },
        ],
    }

    engine_quote_block = {
        "type": "engineQuote",
        "engine": "insight",
        "title": ENGINE_AGENT_TITLES["insight"],
        "blocks": [
            {
                "type": "paragraph",
                "inlines": [
                    {
                        "text": "æ¨¡åè®¤ä¸º 24 å°æ¶åä¿æååºé¢æ¬¡ï¼å¯é¿åä¿¡æ¯çç©ºï¿½?,
                        "marks": [{"type": "bold"}],
                    }
                ],
            },
            {
                "type": "paragraph",
                "inlines": [
                    {"text": "å»ºè®®åæ¶åå¤ç®ï¿½?FAQï¼ä¾¿äºå¤æ¸ éç»ä¸å£å¾ï¿½?}
                ],
            },
        ],
    }

    swot_block = {
        "type": "swotTable",
        "title": "èè®ºï¿½?SWOT éè§",
        "summary": "è¦çå½åæç»ªåå¸ãæ½å¨é£é©ä¸æºä¼ï¿½?,
        "strengths": [
            {"title": "å®æ¹å¿«éåï¿½?, "detail": "é¦æ¡æ¾æ¸è§é¢ 3 å°æ¶åä¸ï¿½?},
            {"title": "åååªä½éå", "impact": "ï¿½?, "score": 8},
        ],
        "weaknesses": [
            {"title": "æ©æè°£è¨å­éï¿½?, "detail": "ç¸å³è½¬åä»å  30%"},
            "å¤é¨ä¸å®¶å°æªç»ä¸å£å¾",
        ],
        "opportunities": [
            {
                "title": "ç¤¾åºå±å»ºè®¨è®º",
                "detail": "èªåç»ç»"è¾è°£å¿æ¿è"è¯é¢ï¼æç»ªæ­£å",
            },
            {"title": "å¬çåä½çªå£", "impact": "ï¿½?},
        ],
        "threats": [
            {"title": "è·¨å¹³å°åªè¾ç»§ç»­åï¿½?, "impact": "ï¿½?, "score": 9},
            {"title": "ä¸ªå«èªåªä½ç½å¨æï¿½?, "evidence": "å­å¨å°åæ ç­¾åå¾å"},
        ],
    }

    pest_block = {
        "type": "pestTable",
        "title": "å®è§ç¯å¢èå²æ«æï¼PESTï¿½?,
        "summary": "æ¨¡æåå¤§ç»´åº¦çå¤é¨çº¦æä¸æºä¼ï¼éªï¿½?pestTable çæ¸²ææ ·å¼ï¿½?,
        "political": [
            {
                "title": "å°æ¹æ¡ä¾å¾æ±æè§",
                "detail": "ç­è§é¢åå¸éå®åæº¯æºï¼å¹³å°åè§æ²éçªå£æå¼ï¿½?,
                "trend": "æ­£é¢å©å¥½",
                "impact": 7,
            },
            {
                "title": "çç®¡å³æ³¨æç»ªç½å¨",
                "detail": "å¯¹å¤¸å¤§çç¾çè´¦å·éç¹å·¡æ¥ï¼èè®ºéå¼ä¸ï¿½?,
                "trend": "æç»­è§å¯",
                "impact": 6,
            },
        ],
        "economic": [
            {
                "title": "å¨è¾¹åæ·è¥æ¶æ³¢å¨",
                "detail": "å®¢æµç­æä¸æ» 12%ï¼ä½ç´æ­å¸¦è´§è®¢åä¸å",
                "trend": "ä¸­ï¿½?,
                "impact": 5,
            },
            {
                "title": "åçèµå©è°¨æ",
                "detail": "èµå©å»¶æè§å¯å£°èªé£é©ï¼å¯¹å®å®£èå¥æåï¿½?,
                "trend": "ä¸ç¡®ï¿½?,
                "impact": 4,
            },
        ],
        "social": [
            {
                "title": "æ ¸å¿ç¾¤ä½æç»ªåå",
                "detail": "æ¬å°å±æ°å³æ³¨å®å¨ï¼å¤å°æ¸¸å®¢å³æ³¨ä½éªä¸éï¿½?,
                "trend": "è´é¢å½±å",
                "impact": 8,
            },
            {
                "title": "é«æ ¡ç¤¾ç¾¤èªåæ±è¯",
                "detail": "æ ¡åªä¸å­¦çä¼ç»ç»"ä»¥å¾æå¾"ç§æ®è´´ï¼æç»ªè¶ï¿½?,
                "trend": "æ­£é¢å©å¥½",
                "impact": 6,
            },
        ],
        "technological": [
            {
                "title": "AI çæåå®¹è¢«æ··ï¿½?,
                "detail": "å±é¨ç»é¢è¢«æ¾å¤§ååä¼ æ­ï¼éæ°´å°æº¯æºå·¥å·è¾å©é´ä¼ª",
                "trend": "è´é¢å½±å",
                "impact": 7,
            },
            {
                "title": "å¤æ¨¡ææ£ç´¢ä¸ï¿½?,
                "detail": "å¹³å°è¯è¡"è§é¢åè¯"æ¨¡åï¼èªå¨æç¤ºåªè¾çè¿¹",
                "trend": "æ­£é¢å©å¥½",
                "impact": 5,
            },
        ],
    }

    callout_block = {
        "type": "callout",
        "tone": "warning",
        "title": "æçè¾¹çæç¤º",
        "blocks": [
            {
                "type": "paragraph",
                "inlines": [
                    {"text": "callout åé¨ä»æ¾è½»éåå®¹ï¼è¶åºé¨åä¼èªå¨æº¢åºå°å¤å±ï¿½?}
                ],
            },
            {
                "type": "list",
                "listType": "bullet",
                "items": [
                    [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "æ¯æåµå¥åè¡¨ / è¡¨æ ¼ / æ°å­¦å¬å¼"}],
                        }
                    ],
                    [
                        {
                            "type": "paragraph",
                            "inlines": [{"text": "å¯å¨è¿éæ¾ç½®æéææä½æ­¥ï¿½?}],
                        }
                    ],
                ],
            },
        ],
    }

    code_block = {
        "type": "code",
        "lang": "json",
        "caption": "æ¼ç¤ºä»£ç ï¿½?,
        "content": '{\n  "event": "ç­ç¹ç¤ºä¾",\n  "topic": "å¬å±äºä»¶",\n  "status": "monitoring"\n}',
    }

    math_block = {
        "type": "math",
        "latex": r"E = mc^2",
        "displayMode": True,
    }

    figure_block = {
        "type": "figure",
        "img": {
            "src": "https://dummyimage.com/600x320/eeeeee/333333&text=Placeholder",
            "alt": "å ä½ç¤ºæï¿½?,
            "width": 600,
            "height": 320,
        },
        "caption": "å¾åå¤é¾è¢«æ¿æ¢ä¸ºåå¥½æç¤ºï¼å¯éªè¯ figure å ä½ææï¿½?,
        "responsive": True,
    }

    widget_block = build_widget_block()
    stacked_bar_chart_block = {
        "type": "widget",
        "widgetId": "demo-stacked-sentiment",
        "widgetType": "chart.js/bar",
        "props": {
            "type": "bar",
            "options": {
                "responsive": True,
                "plugins": {"legend": {"position": "bottom"}},
                "scales": {
                    "x": {"stacked": True},
                    "y": {"stacked": True, "title": {"display": True, "text": "ä¿¡æ¯ï¿½?}},
                },
            },
        },
        "data": {
            "labels": ["å¨ä¸", "å¨äº", "å¨ä¸", "å¨å", "å¨äº"],
            "datasets": [
                {"label": "æ­£å", "data": [18, 22, 24, 19, 16], "backgroundColor": "#27ae60"},
                {"label": "ä¸­ï¿½?, "data": [22, 20, 18, 21, 23], "backgroundColor": "#f39c12"},
                {"label": "è´å", "data": [12, 14, 10, 9, 11], "backgroundColor": "#c0392b"},
            ],
        },
    }
    horizontal_bar_chart_block = {
        "type": "widget",
        "widgetId": "demo-horizontal-voice",
        "widgetType": "chart.js/bar",
        "props": {
            # éè¿ indexAxis åæ¢æ¨ªåæ±ç¶ï¿½?
            "type": "bar",
            "options": {
                "indexAxis": "y",
                "plugins": {"legend": {"position": "right"}},
                "scales": {"x": {"title": {"display": True, "text": "æåï¿½?ï¿½?"}}},
            },
        },
        "data": {
            "labels": ["å¾®å", "ç­è§ï¿½?, "ç¤¾åºè®ºå", "æ°é»å®¢æ·ï¿½?],
            "datasets": [
                {
                    "label": "å£°éå¯¹æ¯",
                    "data": [42, 58, 27, 36],
                    "backgroundColor": ["#2ecc71", "#3498db", "#9b59b6", "#f39c12"],
                }
            ],
        },
    }
    pie_chart_block = {
        "type": "widget",
        "widgetId": "demo-stance-pie",
        "widgetType": "chart.js/pie",
        "props": {
            "type": "pie",
            "options": {"plugins": {"legend": {"position": "bottom"}}},
        },
        "data": {
            "labels": ["æ¯æ", "ä¸­ç«", "è´¨ç"],
            "datasets": [
                {
                    "label": "ç«åºåå¸",
                    "data": [36, 28, 21],
                    "backgroundColor": ["#27ae60", "#f1c40f", "#c0392b"],
                }
            ],
        },
    }
    doughnut_chart_block = {
        "type": "widget",
        "widgetId": "demo-sentiment-share",
        "widgetType": "chart.js/doughnut",
        "props": {
            "type": "doughnut",
            "options": {"plugins": {"legend": {"position": "right"}, "tooltip": {"enabled": True}}},
        },
        "data": {
            "labels": ["æ¿ç­", "ç»æµ", "ç¤¾ä¼", "æï¿½?],
            "datasets": [
                {
                    "label": "å³æ³¨åº¦å ï¿½?,
                    "data": [24, 30, 28, 18],
                    "backgroundColor": ["#8e44ad", "#16a085", "#e67e22", "#2980b9"],
                    "hoverOffset": 6,
                }
            ],
        },
    }
    radar_chart_block = {
        "type": "widget",
        "widgetId": "demo-response-radar",
        "widgetType": "chart.js/radar",
        "props": {
            "type": "radar",
            "options": {
                "plugins": {"legend": {"position": "top"}},
                "scales": {"r": {"beginAtZero": True, "max": 100}},
            },
        },
        "data": {
            "labels": ["éæï¿½?, "ååºéåº¦", "ä¸è´ï¿½?, "äºå¨ï¿½?, "ä¿¡æ¯ï¿½?],
            "datasets": [
                {
                    "label": "å®æ¹æ¸ é",
                    "data": [78, 88, 82, 66, 91],
                    "backgroundColor": "rgba(46,204,113,0.15)",
                    "borderColor": "#2ecc71",
                    "pointBackgroundColor": "#27ae60",
                },
                {
                    "label": "æ°é´è®¨è®º",
                    "data": [64, 72, 58, 74, 63],
                    "backgroundColor": "rgba(52,152,219,0.12)",
                    "borderColor": "#3498db",
                    "pointBackgroundColor": "#2980b9",
                },
            ],
        },
    }
    polar_area_chart_block = {
        "type": "widget",
        "widgetId": "demo-channel-polar",
        "widgetType": "chart.js/polarArea",
        "props": {"type": "polarArea"},
        "data": {
            "labels": ["ç­è§ï¿½?, "å¾®å", "ç¤¾åºè®ºå", "æ°é»å®¢æ·ï¿½?, "çº¿ä¸åé¦"],
            "datasets": [
                {
                    "label": "æ¸ éæ¸éåº¦",
                    "data": [62, 54, 38, 45, 28],
                    "backgroundColor": [
                        "rgba(231,76,60,0.65)",
                        "rgba(142,68,173,0.6)",
                        "rgba(52,152,219,0.55)",
                        "rgba(46,204,113,0.55)",
                        "rgba(241,196,15,0.6)",
                    ],
                }
            ],
        },
    }
    scatter_chart_block = {
        "type": "widget",
        "widgetId": "demo-correlation-scatter",
        "widgetType": "chart.js/scatter",
        "props": {
            "type": "scatter",
            "options": {
                "plugins": {"legend": {"position": "bottom"}},
                "scales": {
                    "x": {"title": {"display": True, "text": "æç»ªæï¿½?}, "min": -1, "max": 1},
                    "y": {"title": {"display": True, "text": "äºå¨ï¿½?}, "beginAtZero": True},
                },
            },
        },
        "data": {
            "datasets": [
                {
                    "label": "å¸å­æ£ç¹",
                    "data": [
                        {"x": -0.65, "y": 120},
                        {"x": -0.25, "y": 190},
                        {"x": 0.05, "y": 260},
                        {"x": 0.42, "y": 340},
                        {"x": 0.78, "y": 410},
                    ],
                    "backgroundColor": "rgba(52,152,219,0.7)",
                }
            ],
        },
    }
    bubble_chart_block = {
        "type": "widget",
        "widgetId": "demo-impact-bubble",
        "widgetType": "chart.js/bubble",
        "props": {
            "type": "bubble",
            "options": {
                "plugins": {"legend": {"position": "bottom"}},
                "scales": {
                    "x": {"title": {"display": True, "text": "æåï¿½?(ï¿½?"}, "beginAtZero": True},
                    "y": {"title": {"display": True, "text": "æç»ªå¼ºåº¦"}, "min": -100, "max": 100},
                },
            },
        },
        "data": {
            "datasets": [
                {
                    "label": "æ¸ éåå¸",
                    "data": [
                        {"x": 8, "y": 35, "r": 12},
                        {"x": 12, "y": -28, "r": 10},
                        {"x": 18, "y": 22, "r": 14},
                        {"x": 25, "y": 48, "r": 16},
                        {"x": 6, "y": -12, "r": 8},
                    ],
                    "backgroundColor": "rgba(192,57,43,0.55)",
                    "borderColor": "#c0392b",
                }
            ],
        },
    }

    chapter_1 = {
        "chapterId": "S1",
        "title": "å°é¢ä¸ç®ï¿½?,
        "anchor": "overview",
        "order": 10,
        "blocks": [
            {"type": "heading", "level": 2, "text": "ä¸ãå°é¢ä¸ç®å½", "anchor": "overview"},
            {
                "type": "paragraph",
                "inlines": [
                    {
                        "text": "æ¨¡æç¤¾ä¼å¬å±ç­ç¹äºä»¶çæè¦ï¼ä¾¿äºå¿«éç¡®è®¤æçä¸å­ä½ææï¿½?,
                    }
                ],
            },
            inline_demo,
            {
                "type": "kpiGrid",
                "items": [
                    {"label": "24hæåï¿½?, "value": "98K", "delta": "+41%", "deltaTone": "up"},
                    {"label": "æ­£åå æ¯", "value": "32%", "delta": "+5pp", "deltaTone": "up"},
                    {"label": "è´åå æ¯", "value": "18%", "delta": "-3pp", "deltaTone": "down"},
                    {"label": "é«é¢æ¸ é", "value": "ç­è§ï¿½?/ å¾®å"},
                ],
                "cols": 4,
            },
            {"type": "toc"},
            {"type": "hr"},
        ],
    }

    chapter_2 = {
        "chapterId": "S2",
        "title": "åç±»åæ¼ï¿½?,
        "anchor": "blocks-showcase",
        "order": 20,
        "blocks": [
            {
                "type": "heading",
                "level": 2,
                "text": "äºãåç±»åæ¼ç¤º",
                "anchor": "blocks-showcase",
            },
            {
                "type": "paragraph",
                "inlines": [
                    {
                        "text": "ä»¥ä¸åå®¹éä¸è¦ç paragraph/list/table/swot/pest/widget ç­å¨é¨åç±»åï¿½?,
                    }
                ],
            },
            {
                "type": "heading",
                "level": 3,
                "text": "2.1 åè¡¨ä¸è¡¨ï¿½?,
                "anchor": "lists-and-tables",
            },
            bullet_list,
            task_list,
            table_block,
            {
                "type": "heading",
                "level": 3,
                "text": "2.2 å¾è¡¨ç»ä»¶æ¼ç¤º",
                "anchor": "charts-demo",
            },
            {
                "type": "paragraph",
                "inlines": [
                    {
                        "text": "æçº¿ / æ±ç¶ï¼å«æ¨ªåãå å ï¼/ é¥¼å¾ / åç¯ / é·è¾¾ / æåº / æ£ç¹ / æ°æ³¡ç­å¤ç±»åå¾è¡¨ï¼ç¨äºéªï¿½?Chart.js å¼å®¹æ§ï¿½?,
                    }
                ],
            },
            widget_block,
            stacked_bar_chart_block,
            horizontal_bar_chart_block,
            pie_chart_block,
            doughnut_chart_block,
            radar_chart_block,
            polar_area_chart_block,
            scatter_chart_block,
            bubble_chart_block,
            {
                "type": "heading",
                "level": 3,
                "text": "2.3 é«é¶åä¸å¯åªï¿½?,
                "anchor": "advanced-blocks",
            },
            blockquote_block,
            callout_block,
            engine_quote_block,
            swot_block,
            pest_block,
            code_block,
            math_block,
            figure_block,
            {
                "type": "hr",
                "variant": "dashed",
            },
            {
                "type": "paragraph",
                "align": "justify",
                "inlines": [
                    {
                        "text": "æ¬ç« èç inline math ååºéªè¯ï¿½?,
                    },
                    {"text": "p(t)=p_0 e^{\\lambda t}", "marks": [{"type": "math"}]},
                    {"text": "ï¼ä»¥ä¸è¦çææåè®¸ååæ è®°ï¿½?},
                ],
            },
        ],
    }

    return [chapter_1, chapter_2]


def validate_chapters(chapters: list[dict]) -> None:
    """ä½¿ç¨ IRValidator æ ¡éªç« èç»æï¼åç°éè¯¯æ¶æåºå¼å¸¸ï¿½?""
    validator = IRValidator()
    for chapter in chapters:
        ok, errors = validator.validate_chapter(chapter)
        if not ok:
            raise ValueError(f"{chapter.get('chapterId', 'unknown')} æ ¡éªå¤±è´¥: {errors}")


def render_and_save(document_ir: dict, timestamp: str) -> tuple[Path, Path, Path, Path]:
    """ï¿½?IR ä¿å­ï¿½?JSONï¼å¹¶æ¸²æ HTML / PDF / Markdownï¼è¿ååä¸ªè·¯å¾ï¿½?""
    ir_dir = Path(settings.DOCUMENT_IR_OUTPUT_DIR)
    html_dir = Path(settings.OUTPUT_DIR) / "html"
    pdf_dir = Path(settings.OUTPUT_DIR) / "pdf"
    md_dir = Path(settings.OUTPUT_DIR) / "md"
    ir_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    ir_path = ir_dir / f"report_ir_all_blocks_demo_{timestamp}.json"
    ir_path.write_text(json.dumps(document_ir, ensure_ascii=False, indent=2), encoding="utf-8")

    html_renderer = HTMLRenderer()
    html_content = html_renderer.render(document_ir)
    html_path = html_dir / f"report_html_all_blocks_demo_{timestamp}.html"
    html_path.write_text(html_content, encoding="utf-8")

    pdf_renderer = PDFRenderer()
    pdf_path = pdf_dir / f"report_pdf_all_blocks_demo_{timestamp}.pdf"
    pdf_renderer.render_to_pdf(document_ir, pdf_path)

    md_renderer = MarkdownRenderer()
    md_content = md_renderer.render(document_ir, ir_file_path=str(ir_path))
    md_path = md_dir / f"report_md_all_blocks_demo_{timestamp}.md"
    md_path.write_text(md_content, encoding="utf-8")

    return ir_path, html_path, pdf_path, md_path


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = f"all-blocks-demo-{timestamp}"
    metadata = {
        "title": "ç¤¾ä¼å¬å±ç­ç¹äºä»¶æ¸²ææµè¯",
        "subtitle": "è¦çå¨é¨ IR åç±»åçç¤ºä¾æ°æ®ï¼å«å¤ç§å¾è¡¨ï¿½?PEST æ¼ç¤º",
        "query": "å¬å±äºä»¶æ¸²æè½åèªæ£ / Chart & PEST",
        "toc": {"title": "ç®å½", "depth": 3},
        "hero": {
            "summary": "ç¨äºéªè¯ Report Engine ï¿½?HTML / PDF æ¸²ææ¶å¯¹åç±»åºåhart.js ç»ä»¶ï¿½?PEST æ¨¡åçå¼å®¹æ§ï¿½?,
            "kpis": [
                {"label": "ç¤ºä¾åæ°ï¿½?, "value": "20+", "delta": "ï¿½?PEST", "tone": "up"},
                {"label": "å¾è¡¨ï¿½?, "value": "7", "delta": "æ°å¢å¤ç±»ï¿½?, "tone": "neutral"},
            ],
            "highlights": ["è¦çå¨é¨ block", "å«è¡ï¿½?åçº§å¬å¼", "Chart.js å¤ç±»ï¿½?, "PEST + SWOT"],
            "actions": ["éæ°çæ", "å¯¼åº PDF"],
        },
    }

    chapters = build_chapters()
    validate_chapters(chapters)

    composer = DocumentComposer()
    document_ir = composer.build_document(report_id, metadata, chapters)

    ir_path, html_path, pdf_path, md_path = render_and_save(document_ir, timestamp)

    print("ï¿½?æ¼ç¤º IR çæå®æ")
    print(f"IR:   {ir_path}")
    print(f"HTML: {html_path}")
    print(f"PDF:  {pdf_path}")
    print(f"MD:   {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
