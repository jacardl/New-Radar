# -*- coding: utf-8 -*-
"""
OpenAI-compatible API Blueprint for New Radar.

Exposes:
- POST /v1/chat/completions  - OpenAI Chat Completions API
- GET  /v1/models            - List available models
- GET  /health               - Health check

Supports streaming (text/event-stream) and non-streaming responses.
Designed for integration with Open WebUI, LobeChat, and other OpenAI-compatible frontends.
"""
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

from flask import Blueprint, request, jsonify, Response, stream_with_context

from backend.engines.base import MultiEngineDispatcher
from backend.core.sentiment_tool import analyze_sentiment, get_sentiment_tool_info
from backend.config import settings

logger = logging.getLogger(__name__)

# Default model name advertised to OpenAI clients
DEFAULT_MODEL_NAME = getattr(settings, 'OPENAI_MODEL_NAME', None) or "new-radar-agent"

# Create Blueprint
openai_bp = Blueprint("openai_compat", __name__, url_prefix="/v1")

# Global dispatcher instance
_dispatcher: Optional[MultiEngineDispatcher] = None


def _get_dispatcher() -> MultiEngineDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = MultiEngineDispatcher(model_name=DEFAULT_MODEL_NAME)
    return _dispatcher


def _normalize_messages(messages: List[Dict[str, Any]]) -> str:
    """
    Extract the user message from an OpenAI messages array.
    Handles both string content and array content (e.g., [{"type": "text", "text": "..."}]).
    """
    for msg in reversed(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        part_type = part.get("type", "")
                        if part_type in ("text", "input_text"):
                            text_parts.append(part.get("text", ""))
                return "\n".join(text_parts) if text_parts else ""
    return ""


def _check_api_key() -> Optional[str]:
    """Validate API key from Authorization header. Returns None if valid, error message if not."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Accept any non-empty key for local development
        # In production, validate against settings.API_KEY
        expected_key = getattr(settings, 'OPENAI_API_KEY', None) or "new-radar-local"
        if token and (token == expected_key or expected_key == ""):
            return None
    elif not auth_header:
        # No auth required for local development
        return None

    return "Invalid API key"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@openai_bp.route("/chat/completions", methods=["POST"])
def chat_completions():
    """
    OpenAI-compatible Chat Completions endpoint.

    POST /v1/chat/completions
    Body (JSON):
        - model: str (optional, default "new-radar-agent")
        - messages: List[{"role": "user"|"assistant"|"system", "content": str}]
        - stream: bool (optional, default False)
        - temperature: float (optional, default 0.7)
        - max_tokens: int (optional)
    """
    # Validate API key
    api_key_error = _check_api_key()
    if api_key_error:
        return jsonify({
            "error": {
                "message": api_key_error,
                "type": "invalid_request_error",
                "code": "invalid_api_key",
            }
        }), 401

    # Parse request body
    body = request.get_json(silent=True) or {}
    model = body.get("model", DEFAULT_MODEL_NAME)
    messages: List[Dict[str, Any]] = body.get("messages", [])
    stream: bool = body.get("stream", False)

    if not messages:
        return jsonify({
            "error": {
                "message": "messages is required and cannot be empty",
                "type": "invalid_request_error",
                "code": "missing_messages",
            }
        }), 400

    # Extract user message
    user_message = _normalize_messages(messages)
    if not user_message:
        return jsonify({
            "error": {
                "message": "No user message found in messages",
                "type": "invalid_request_error",
                "code": "missing_user_message",
            }
        }), 400

    dispatcher = _get_dispatcher()

    if stream:
        # Streaming response via SSE
        def generate():
            for chunk in dispatcher.stream_analyze(user_message):
                yield chunk

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
            }
        )
    else:
        # Non-streaming response
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        try:
            content = dispatcher.analyze(user_message)
        except Exception as e:
            logger.exception("Non-streaming chat completion failed")
            content = f"åæå¤±è´¥: {str(e)}"

        response = dispatcher._build_non_stream_response(completion_id, model, created, content)
        return jsonify(response)


@openai_bp.route("/models", methods=["GET"])
def list_models():
    """
    OpenAI-compatible models list endpoint.

    GET /v1/models

    Returns a list of available models.
    """
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": DEFAULT_MODEL_NAME,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "new-radar",
                "permission": [],
                "root": DEFAULT_MODEL_NAME,
                "parent": None,
            }
        ]
    })


@openai_bp.route("/models", methods=["POST"])
def retrieve_model():
    """Retrieve a specific model (compatibility)."""
    body = request.get_json(silent=True) or {}
    model_id = body.get("model", DEFAULT_MODEL_NAME)
    return jsonify({
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "new-radar",
        "permission": [],
        "root": model_id,
        "parent": None,
    })


@openai_bp.route("/sentiment", methods=["POST"])
def sentiment_analysis():
    """
    Sentiment analysis endpoint.

    POST /v1/sentiment
    Body (JSON):
        - texts: str or List[str] - text(s) to analyze
    """
    api_key_error = _check_api_key()
    if api_key_error:
        return jsonify({
            "error": {
                "message": api_key_error,
                "type": "invalid_request_error",
                "code": "invalid_api_key",
            }
        }), 401

    body = request.get_json(silent=True) or {}
    texts = body.get("texts")

    if not texts:
        return jsonify({
            "error": {
                "message": "texts field is required",
                "type": "invalid_request_error",
                "code": "missing_texts",
            }
        }), 400

    result = analyze_sentiment(texts)
    try:
        return jsonify(json.loads(result))
    except json.JSONDecodeError:
        return jsonify({"success": False, "raw": result})


@openai_bp.route("/sentiment/info", methods=["GET"])
def sentiment_info():
    """Get sentiment analysis tool information."""
    return jsonify(get_sentiment_tool_info())


@openai_bp.route("/health", methods=["GET"])
@openai_bp.route("/v1/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "model": DEFAULT_MODEL_NAME,
        "timestamp": int(time.time()),
    })
