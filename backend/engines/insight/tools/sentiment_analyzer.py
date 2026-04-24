"""
å¤è¯­è¨ææåæå·¥å·
åºäºWeiboMultilingualSentimentæ¨¡åä¸ºInsightEngineæä¾ææåæåè½
"""

import os
import sys
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
import re

try:
    import torch

    TORCH_AVAILABLE = True
    torch.classes.__path__ = []
except ImportError:
    torch = None  # type: ignore
    TORCH_AVAILABLE = False

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    AutoTokenizer = None  # type: ignore
    AutoModelForSequenceClassification = None  # type: ignore
    TRANSFORMERS_AVAILABLE = False

from dotenv import load_dotenv
load_dotenv()

# éç½®å½åéåæºï¼è§£å³ä¸è½½ connection refused éè¯¯
if os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT")
elif "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# INFOï¼è¥æ³è·³è¿ææåæï¼å¯æå¨åæ¢æ­¤å¼å³ä¸ºFalse
SENTIMENT_ANALYSIS_ENABLED = True


def _describe_missing_dependencies() -> str:
    missing = []
    if not TORCH_AVAILABLE:
        missing.append("PyTorch")
    if not TRANSFORMERS_AVAILABLE:
        missing.append("Transformers")
    return " / ".join(missing)


# æ·»å é¡¹ç®æ ¹ç®å½å°è·¯å¾ï¼ä»¥ä¾¿å¯¼å¥WeiboMultilingualSentiment
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
weibo_sentiment_path = os.path.join(
    project_root, "SentimentAnalysisModel", "WeiboMultilingualSentiment"
)
sys.path.append(weibo_sentiment_path)


@dataclass
class SentimentResult:
    """ææåæç»ææ°æ®ç±?""

    text: str
    sentiment_label: str
    confidence: float
    probability_distribution: Dict[str, float]
    success: bool = True
    error_message: Optional[str] = None
    analysis_performed: bool = True


@dataclass
class BatchSentimentResult:
    """æ¹éææåæç»ææ°æ®ç±?""

    results: List[SentimentResult]
    total_processed: int
    success_count: int
    failed_count: int
    average_confidence: float
    analysis_performed: bool = True


class WeiboMultilingualSentimentAnalyzer:
    """
    å¤è¯­è¨ææåæå?
    å°è£WeiboMultilingualSentimentæ¨¡åï¼ä¸ºAI Agentæä¾ææåæåè½
    """

    def __init__(self):
        """åå§åææåæå¨"""
        self.model = None
        self.tokenizer = None
        self.device = None
        self.is_initialized = False
        self.is_disabled = False
        self.disable_reason: Optional[str] = None

        # æææ ç­¾æ å°ï¼?çº§åç±»ï¼
        self.sentiment_map = {
            0: "éå¸¸è´é¢",
            1: "è´é¢",
            2: "ä¸­æ?,
            3: "æ­£é¢",
            4: "éå¸¸æ­£é¢",
        }

        if not SENTIMENT_ANALYSIS_ENABLED:
            self.disable("ææåæåè½å·²å¨éç½®ä¸­å³é­)
        elif not (TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE):
            missing = _describe_missing_dependencies() or "æªç¥ä¾èµ"
            self.disable(f"ç¼ºå°ä¾èµ: {missing}ï¼ææåæå·²ç¦ç¨)

        if self.is_disabled:
            reason = self.disable_reason or "Sentiment analysis disabled."
            print(
                f"WeiboMultilingualSentimentAnalyzer initialized but disabled: {reason}"
            )
        else:
            print(
                "WeiboMultilingualSentimentAnalyzer å·²åå»ºï¼è°ç¨ initialize() æ¥å è½½æ¨¡å?
            )

    def disable(self, reason: Optional[str] = None, drop_state: bool = False) -> None:
        """Disable sentiment analysis, optionally clearing loaded resources."""
        self.is_disabled = True
        self.disable_reason = reason or "Sentiment analysis disabled."
        if drop_state:
            self.model = None
            self.tokenizer = None
            self.device = None
            self.is_initialized = False

    def enable(self) -> bool:
        """Attempt to enable sentiment analysis; returns True if enabled."""
        if not SENTIMENT_ANALYSIS_ENABLED:
            self.disable("ææåæåè½å·²å¨éç½®ä¸­å³é­)
            return False
        if not (TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE):
            missing = _describe_missing_dependencies() or "æªç¥ä¾èµ"
            self.disable(f"ç¼ºå°ä¾èµ: {missing}ï¼ææåæå·²ç¦ç¨)
            return False
        self.is_disabled = False
        self.disable_reason = None
        return True

    def _select_device(self):
        """Select the best available torch device."""
        if not TORCH_AVAILABLE:
            return None
        assert torch is not None
        if torch.cuda.is_available():
            return torch.device("cuda")
        mps_backend = getattr(torch.backends, "mps", None)
        if (
            mps_backend
            and getattr(mps_backend, "is_available", lambda: False)()
            and getattr(mps_backend, "is_built", lambda: False)()
        ):
            return torch.device("mps")
        return torch.device("cpu")

    def initialize(self) -> bool:
        """
        åå§åæ¨¡åååè¯å?

        Returns:
            æ¯å¦åå§åæå?
        """
        if self.is_disabled:
            reason = self.disable_reason or "ææåæåè½å·²ç¦ç?
            print(f"ææåæåè½å·²ç¦ç¨ï¼è·³è¿æ¨¡åå è½½ï¼{reason}")
            return False

        if not (TORCH_AVAILABLE and TRANSFORMERS_AVAILABLE):
            missing = _describe_missing_dependencies() or "æªç¥ä¾èµ"
            self.disable(f"ç¼ºå°ä¾èµ: {missing}ï¼ææåæå·²ç¦ç¨, drop_state=True)
            print(f"ç¼ºå°ä¾èµ: {missing}ï¼æ æ³å è½½ææåææ¨¡å)
            return False

        if self.is_initialized:
            print("æ¨¡åå·²ç»åå§åï¼æ ééå¤å è½½")
            return True

        try:
            print("æ­£å¨å è½½å¤è¯­è¨ææåææ¨¡å...")
            assert AutoTokenizer is not None
            assert AutoModelForSequenceClassification is not None

            # ä½¿ç¨å¤è¯­è¨ææåææ¨¡å
            model_name = "tabularisai/multilingual-sentiment-analysis"
            local_model_path = os.path.join(weibo_sentiment_path, "model")

            # æ£æ¥æ¬å°æ¯å¦å·²ææ¨¡å?
            if os.path.exists(local_model_path) and os.path.exists(os.path.join(local_model_path, "config.json")):
                print("ä»æ¬å°å è½½æ¨¡å?..")
                self.tokenizer = AutoTokenizer.from_pretrained(local_model_path)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    local_model_path
                )
            else:
                print("é¦æ¬¡ä½¿ç¨ï¼æ­£å¨ä¸è½½æ¨¡åå°æ¬å°...")
                # ä¸è½½å¹¶ä¿å­å°æ¬å°
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    model_name
                )

                # ä¿å­å°æ¬å?
                os.makedirs(local_model_path, exist_ok=True)
                self.tokenizer.save_pretrained(local_model_path)
                self.model.save_pretrained(local_model_path)
                print(f"æ¨¡åå·²ä¿å­å°: {local_model_path}")

            # è®¾ç½®è®¾å¤
            device = self._select_device()
            if device is None:
                raise RuntimeError("æªæ£æµå°å¯ç¨çè®¡ç®è®¾å¤?)

            self.device = device
            self.model.to(self.device)
            self.model.eval()
            self.is_initialized = True
            self.enable()

            device_type = getattr(self.device, "type", str(self.device))
            if device_type == "cuda":
                print("æ£æµå°å¯ç¨ GPUï¼å·²ä¼åä½¿ç¨ CUDA è¿è¡æ¨ç)
            elif device_type == "mps":
                print("æ£æµå° Apple MPS è®¾å¤ï¼å·²ä½¿ç¨ MPS è¿è¡æ¨ç)
            else:
                print("æªæ£æµå° GPUï¼èªå¨ä½¿ç?CPU è¿è¡æ¨ç)

            print(f"æ¨¡åå è½½æå! ä½¿ç¨è®¾å¤: {self.device}")
            print("æ¯æè¯­è¨: ä¸­æãè±æãè¥¿ç­çæãé¿æä¼¯æãæ¥æãé©æç­22ç§è¯­è¨")
            print("ææç­çº§: éå¸¸è´é¢ãè´é¢ãä¸­æ§ãæ­£é¢ãéå¸¸æ­£é?)

            return True

        except Exception as e:
            error_message = f"æ¨¡åå è½½å¤±è´¥: {e}"
            print(error_message)
            print("è¯·æ£æ¥ç½ç»è¿æ¥ææ¨¡åæä»¶")
            self.disable(error_message, drop_state=True)
            return False

    def _preprocess_text(self, text: str) -> str:
        """
        ææ¬é¢å¤ç?

        Args:
            text: è¾å¥ææ¬

        Returns:
            å¤çåçææ¬
        """
        # åºæ¬ææ¬æ¸ç
        if not text or not text.strip():
            return ""

        # å»é¤å¤ä½ç©ºæ ¼
        text = re.sub(r"\s+", " ", text.strip())

        return text

    def analyze_single_text(self, text: str) -> SentimentResult:
        """
        å¯¹åä¸ªææ¬è¿è¡ææåæ?

        Args:
            text: è¦åæçææ¬

        Returns:
            SentimentResultå¯¹è±¡
        """
        if self.is_disabled:
            return SentimentResult(
                text=text,
                sentiment_label="ææåææªæ§è¡?,
                confidence=0.0,
                probability_distribution={},
                success=False,
                error_message=self.disable_reason or "ææåæåè½å·²ç¦ç?,
                analysis_performed=False,
            )

        if not self.is_initialized:
            return SentimentResult(
                text=text,
                sentiment_label="æªåå§å",
                confidence=0.0,
                probability_distribution={},
                success=False,
                error_message="æ¨¡åæªåå§åï¼è¯·åè°ç¨initialize() æ¹æ³",
                analysis_performed=False,
            )

        try:
            # é¢å¤çææ?
            processed_text = self._preprocess_text(text)

            if not processed_text:
                return SentimentResult(
                    text=text,
                    sentiment_label="è¾å¥éè¯¯",
                    confidence=0.0,
                    probability_distribution={},
                    success=False,
                    error_message="è¾å¥ææ¬ä¸ºç©ºææ æåå®?,
                    analysis_performed=False,
                )
            assert self.tokenizer is not None
            # åè¯ç¼ç 
            inputs = self.tokenizer(
                processed_text,
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )

            # è½¬ç§»å°è®¾å¤?
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # é¢æµ
            assert torch is not None
            assert self.model is not None
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probabilities = torch.softmax(logits, dim=1)
                prediction = int(torch.argmax(probabilities, dim=1).item())

            # æå»ºç»æ
            confidence = probabilities[0][prediction].item()
            label = self.sentiment_map[prediction]

            # æå»ºæ¦çåå¸å­å¸
            prob_dist = {}
            for label_name, prob in zip(self.sentiment_map.values(), probabilities[0]):
                prob_dist[label_name] = prob.item()

            return SentimentResult(
                text=text,
                sentiment_label=label,
                confidence=confidence,
                probability_distribution=prob_dist,
                success=True,
            )

        except Exception as e:
            return SentimentResult(
                text=text,
                sentiment_label="åæå¤±è´¥",
                confidence=0.0,
                probability_distribution={},
                success=False,
                error_message=f"é¢æµæ¶åçéè¯? {str(e)}",
                analysis_performed=False,
            )

    def analyze_batch(
        self, texts: List[str], show_progress: bool = True
    ) -> BatchSentimentResult:
        """
        æ¹éææåæ

        Args:
            texts: ææ¬åè¡¨
            show_progress: æ¯å¦æ¾ç¤ºè¿åº¦

        Returns:
            BatchSentimentResultå¯¹è±¡
        """
        if not texts:
            return BatchSentimentResult(
                results=[],
                total_processed=0,
                success_count=0,
                failed_count=0,
                average_confidence=0.0,
                analysis_performed=not self.is_disabled and self.is_initialized,
            )

        if self.is_disabled or not self.is_initialized:
            passthrough_results = [
                SentimentResult(
                    text=text,
                    sentiment_label="ææåææªæ§è¡?,
                    confidence=0.0,
                    probability_distribution={},
                    success=False,
                    error_message=self.disable_reason or "ææåæåè½ä¸å¯ç?,
                    analysis_performed=False,
                )
                for text in texts
            ]
            return BatchSentimentResult(
                results=passthrough_results,
                total_processed=len(texts),
                success_count=0,
                failed_count=len(texts),
                average_confidence=0.0,
                analysis_performed=False,
            )

        results = []
        success_count = 0
        total_confidence = 0.0

        for i, text in enumerate(texts):
            if show_progress and len(texts) > 1:
                print(f"å¤çè¿åº¦: {i + 1}/{len(texts)}")

            result = self.analyze_single_text(text)
            results.append(result)

            if result.success:
                success_count += 1
                total_confidence += result.confidence

        average_confidence = (
            total_confidence / success_count if success_count > 0 else 0.0
        )
        failed_count = len(texts) - success_count

        return BatchSentimentResult(
            results=results,
            total_processed=len(texts),
            success_count=success_count,
            failed_count=failed_count,
            average_confidence=average_confidence,
            analysis_performed=True,
        )

    def _build_passthrough_analysis(
        self,
        original_data: List[Dict[str, Any]],
        reason: str,
        texts: Optional[List[str]] = None,
        results: Optional[List[SentimentResult]] = None,
    ) -> Dict[str, Any]:
        """
        æå»ºå¨ææåæä¸å¯ç¨æ¶çéä¼ ç»æ
        """
        total_items = len(texts) if texts is not None else len(original_data)
        response: Dict[str, Any] = {
            "sentiment_analysis": {
                "available": False,
                "reason": reason,
                "total_analyzed": 0,
                "success_rate": f"0/{total_items}",
                "average_confidence": 0.0,
                "sentiment_distribution": {},
                "high_confidence_results": [],
                "summary": f"ææåææªæ§è¡ï¼{reason}",
                "original_texts": original_data,
            }
        }

        if texts is not None:
            response["sentiment_analysis"]["passthrough_texts"] = texts

        if results is not None:
            response["sentiment_analysis"]["results"] = [
                result.__dict__ if isinstance(result, SentimentResult) else result
                for result in results
            ]

        return response

    def analyze_query_results(
        self,
        query_results: List[Dict[str, Any]],
        text_field: str = "content",
        min_confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        å¯¹æ¥è¯¢ç»æè¿è¡ææåæ?
        ä¸é¨ç¨äºåæä»MediaCrawlerDBè¿åçæ¥è¯¢ç»æ?

        Args:
            query_results: æ¥è¯¢ç»æåè¡¨ï¼æ¯ä¸ªåç´ åå«ææ¬åå®?
            text_field: ææ¬åå®¹å­æ®µåï¼é»è®¤ä¸?content"
            min_confidence: æå°ç½®ä¿¡åº¦éå?

        Returns:
            åå«ææåæç»æçå­å?
        """
        if not query_results:
            return {
                "sentiment_analysis": {
                    "total_analyzed": 0,
                    "sentiment_distribution": {},
                    "high_confidence_results": [],
                    "summary": "æ²¡æåå®¹éè¦åæ?,
                }
            }

        # æåææ¬åå®¹
        texts_to_analyze = []
        original_data = []

        for item in query_results:
            # å°è¯å¤ä¸ªå¯è½çææ¬å­æ®?
            text_content = ""
            for field in [text_field, "title_or_content", "content", "title", "text"]:
                if field in item and item[field]:
                    text_content = str(item[field])
                    break

            if text_content.strip():
                texts_to_analyze.append(text_content)
                original_data.append(item)

        if not texts_to_analyze:
            return {
                "sentiment_analysis": {
                    "total_analyzed": 0,
                    "sentiment_distribution": {},
                    "high_confidence_results": [],
                    "summary": "æ¥è¯¢ç»æä¸­æ²¡ææ¾å°å¯åæçææ¬åå®?,
                }
            }

        if self.is_disabled:
            return self._build_passthrough_analysis(
                original_data=original_data,
                reason=self.disable_reason or "ææåææ¨¡åä¸å¯ç?,
                texts=texts_to_analyze,
            )

        # æ§è¡æ¹éææåæ
        print(f"æ­£å¨å¯¹{len(texts_to_analyze)}æ¡åå®¹è¿è¡ææåæ?..")
        batch_result = self.analyze_batch(texts_to_analyze, show_progress=True)

        if not batch_result.analysis_performed:
            reason = self.disable_reason or "ææåæåè½ä¸å¯ç?
            if batch_result.results:
                candidate_error = next(
                    (r.error_message for r in batch_result.results if r.error_message),
                    None,
                )
                if candidate_error:
                    reason = candidate_error
            return self._build_passthrough_analysis(
                original_data=original_data,
                reason=reason,
                texts=texts_to_analyze,
                results=batch_result.results,
            )

        # ç»è®¡ææåå¸
        sentiment_distribution = {}
        high_confidence_results = []

        for result, original_item in zip(batch_result.results, original_data):
            if result.success:
                # ç»è®¡ææåå¸
                sentiment = result.sentiment_label
                if sentiment not in sentiment_distribution:
                    sentiment_distribution[sentiment] = 0
                sentiment_distribution[sentiment] += 1

                # æ¶éé«ç½®ä¿¡åº¦ç»æ
                if result.confidence >= min_confidence:
                    high_confidence_results.append(
                        {
                            "original_data": original_item,
                            "sentiment": result.sentiment_label,
                            "confidence": result.confidence,
                            "text_preview": result.text[:100] + "..."
                            if len(result.text) > 100
                            else result.text,
                        }
                    )

        # çæææåææè¦
        total_analyzed = batch_result.success_count
        if total_analyzed > 0:
            dominant_sentiment = max(sentiment_distribution.items(), key=lambda x: x[1])
            sentiment_summary = f"å±åæ{total_analyzed}æ¡åå®¹ï¼ä¸»è¦ææå¾åä¸?{dominant_sentiment[0]}'({dominant_sentiment[1]}æ¡ï¼å {dominant_sentiment[1] / total_analyzed * 100:.1f}%)"
        else:
            sentiment_summary = "ææåæå¤±è´¥"

        return {
            "sentiment_analysis": {
                "total_analyzed": total_analyzed,
                "success_rate": f"{batch_result.success_count}/{batch_result.total_processed}",
                "average_confidence": round(batch_result.average_confidence, 4),
                "sentiment_distribution": sentiment_distribution,
                "high_confidence_results": high_confidence_results,  # è¿åææé«ç½®ä¿¡åº¦ç»æï¼ä¸åéå¶
                "summary": sentiment_summary,
            }
        }

    def get_model_info(self) -> Dict[str, Any]:
        """
        è·åæ¨¡åä¿¡æ¯

        Returns:
            æ¨¡åä¿¡æ¯å­å¸
        """
        return {
            "model_name": "tabularisai/multilingual-sentiment-analysis",
            "supported_languages": [
                "ä¸­æ",
                "è±æ",
                "è¥¿ç­çæ",
                "é¿æä¼¯æ",
                "æ¥æ",
                "é©æ",
                "å¾·æ",
                "æ³æ",
                "æå¤§å©æ",
                "è¡èçæ",
                "ä¿æ",
                "è·å°æ?,
                "æ³¢å°æ?,
                "åè³å¶æ?,
                "ä¸¹éº¦æ?,
                "å¸èæ?,
                "è¬å°æ?,
                "çå¸æ?,
                "æªå¨æ?,
                "åçå©æ",
                "æ·åæ?,
                "ä¿å å©äºæ?,
            ],
            "sentiment_levels": list(self.sentiment_map.values()),
            "is_initialized": self.is_initialized,
            "device": str(self.device) if self.device else "æªè®¾ç½?,
        }


# åå»ºå¨å±å®ä¾ï¼å»¶è¿åå§åï¼?
multilingual_sentiment_analyzer = WeiboMultilingualSentimentAnalyzer()


def enable_sentiment_analysis() -> bool:
    """Public helper to enable sentiment analysis at runtime."""
    return multilingual_sentiment_analyzer.enable()


def disable_sentiment_analysis(
    reason: Optional[str] = None, drop_state: bool = False
) -> None:
    """Public helper to disable sentiment analysis at runtime."""
    multilingual_sentiment_analyzer.disable(reason=reason, drop_state=drop_state)


def analyze_sentiment(
    text_or_texts: Union[str, List[str]], initialize_if_needed: bool = True
) -> Union[SentimentResult, BatchSentimentResult]:
    """
    ä¾¿æ·çææåæå½æ?

    Args:
        text_or_texts: åä¸ªææ¬æææ¬åè¡?
        initialize_if_needed: å¦ææ¨¡åæªåå§åï¼æ¯å¦èªå¨åå§å

    Returns:
        SentimentResultæBatchSentimentResult
    """
    if (
        initialize_if_needed
        and not multilingual_sentiment_analyzer.is_initialized
        and not multilingual_sentiment_analyzer.is_disabled
    ):
        multilingual_sentiment_analyzer.initialize()

    if isinstance(text_or_texts, str):
        return multilingual_sentiment_analyzer.analyze_single_text(text_or_texts)
    else:
        texts_list = list(text_or_texts)
        return multilingual_sentiment_analyzer.analyze_batch(texts_list)


if __name__ == "__main__":
    # æµè¯ä»£ç 
    analyzer = WeiboMultilingualSentimentAnalyzer()

    if analyzer.initialize():
        # æµè¯åä¸ªææ¬
        result = analyzer.analyze_single_text("ä»å¤©å¤©æ°çå¥½ï¼å¿æç¹å«æ£ï¼?)
        print(
            f"åä¸ªææ¬åæ: {result.sentiment_label} (ç½®ä¿¡åº? {result.confidence:.4f})"
        )

        # æµè¯æ¹éææ¬
        test_texts = [
            "è¿å®¶é¤åçèå³ééå¸¸æ£ï¼",
            "æå¡æåº¦å¤ªå·®äºï¼å¾å¤±æ?,
            "I absolutely love this product!",
            "The customer service was disappointing.",
        ]

        batch_result = analyzer.analyze_batch(test_texts)
        print(
            f"\næ¹éåæ: æå {batch_result.success_count}/{batch_result.total_processed}"
        )

        for result in batch_result.results:
            print(
                f"'{result.text[:30]}...' -> {result.sentiment_label} ({result.confidence:.4f})"
            )
    else:
        print("æ¨¡ååå§åå¤±è´¥ï¼æ æ³è¿è¡æµè¯")
