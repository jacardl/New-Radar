# -*- coding: utf-8 -*-
"""
Sentiment Analysis Tool - wraps WeiboMultilingualSentimentAnalyzer as a Hermes Tool.

Provides sentiment analysis (positive/negative/neutral) for crawled content.
Exposed as:
1. Hermes Tool: dynamically mounted in BaseHermesAgent via ENABLE_SENTIMENT_TOOL
2. Flask API: POST /v1/sentiment
"""
import os
import json
import logging
from typing import Union, List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

# Set HF mirror for Chinese users
if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

logger = logging.getLogger(__name__)

# Singleton sentiment analyzer instance
_analyzer = None


def _get_analyzer():
    """Lazy-load the sentiment analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        from backend.engines.insight.tools.sentiment_analyzer import (
            WeiboMultilingualSentimentAnalyzer,
            SentimentResult,
            BatchSentimentResult,
        )
        _analyzer = WeiboMultilingualSentimentAnalyzer()
        # Auto-initialize if dependencies available
        if not _analyzer.is_disabled and not _analyzer.is_initialized:
            _analyzer.initialize()
    return _analyzer


def analyze_sentiment(texts: Union[str, List[str]]) -> str:
    """
    Hermes Tool function for sentiment analysis.

    Accepts a single text string or a JSON string array of texts.
    Returns JSON string with sentiment results.

    Args:
        texts: Single text string or JSON array string like '["text1", "text2"]'

    Returns:
        JSON string with sentiment analysis results
    """
    try:
        analyzer = _get_analyzer()

        if analyzer.is_disabled:
            return json.dumps({
                "success": False,
                "error": analyzer.disable_reason or "Sentiment analysis is disabled",
                "results": []
            }, ensure_ascii=False)

        # Parse input - could be JSON array string or plain text
        if isinstance(texts, str):
            texts = texts.strip()
            # Try parsing as JSON array
            if texts.startswith("["):
                try:
                    texts = json.loads(texts)
                except json.JSONDecodeError:
                    texts = [texts]
            else:
                texts = [texts]

        if not texts:
            return json.dumps({
                "success": False,
                "error": "No text provided for sentiment analysis",
                "results": []
            }, ensure_ascii=False)

        # Single text
        if len(texts) == 1:
            result = analyzer.analyze_single_text(texts[0])
            return json.dumps({
                "success": True,
                "results": [{
                    "text": result.text,
                    "sentiment_label": result.sentiment_label,
                    "confidence": result.confidence,
                    "probability_distribution": result.probability_distribution,
                    "success": result.success,
                    "error_message": result.error_message,
                }]
            }, ensure_ascii=False)

        # Batch texts
        batch_result = analyzer.analyze_batch(texts)
        return json.dumps({
            "success": True,
            "results": [
                {
                    "text": r.text,
                    "sentiment_label": r.sentiment_label,
                    "confidence": r.confidence,
                    "probability_distribution": r.probability_distribution,
                    "success": r.success,
                    "error_message": r.error_message,
                }
                for r in batch_result.results
            ],
            "total_processed": batch_result.total_processed,
            "success_count": batch_result.success_count,
            "failed_count": batch_result.failed_count,
            "average_confidence": batch_result.average_confidence,
        }, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Sentiment analysis failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e),
            "results": []
        }, ensure_ascii=False)


def get_sentiment_tool_info() -> Dict[str, Any]:
    """Return info about the sentiment analyzer for tool description."""
    try:
        analyzer = _get_analyzer()
        return {
            "name": "sentiment_analysis",
            "description": "Analyze sentiment (positive/negative/neutral) of text content. Supports 22 languages including Chinese, English, Japanese, Korean. Input: single text or JSON array of texts. Output: sentiment label, confidence score, probability distribution.",
            "model": "tabularisai/multilingual-sentiment-analysis",
            "is_initialized": analyzer.is_initialized,
            "is_disabled": analyzer.is_disabled,
            "disable_reason": analyzer.disable_reason,
            "supported_languages": [
                "Chinese", "English", "Spanish", "Arabic", "Japanese",
                "Korean", "German", "French", "Italian", "Portuguese",
                "Russian", "Dutch", "Polish", "Turkish", "Danish",
                "Greek", "Finnish", "Swedish", "Norwegian", "Hungarian",
                "Czech", "Bulgarian"
            ],
            "sentiment_labels": ["非常负面", "负面", "中性", "正面", "非常正面"],
        }
    except Exception as e:
        return {
            "name": "sentiment_analysis",
            "error": str(e),
        }


class SentimentAnalysisTool:
    """
    Hermes Tool wrapper for sentiment analysis.
    Can be dynamically mounted in BaseHermesAgent.
    """
    name = "sentiment_analysis"
    description = (
        "Analyze sentiment (positive/negative/neutral) of text content. "
        "Supports 22 languages including Chinese, English, Japanese, Korean. "
        "Input: a single text string or a JSON array of texts. "
        "Output: sentiment label (非常负面/负面/中性/正面/非常正面), confidence score (0-1), "
        "and probability distribution across all sentiment levels. "
        "Higher confidence means more certain the prediction. "
        "Use this tool when you need to understand the emotional tone of crawled content, "
        "social media posts, comments, or news articles."
    )

    def __call__(self, texts: Union[str, List[str]]) -> str:
        """Execute sentiment analysis."""
        return analyze_sentiment(texts)
