# -*- coding: utf-8 -*-
"""
Lightweight embedding utility for MediaCrawler.

Computes text embeddings using sentence-transformers and stores
them as JSON strings in the crawled_data.embedding column.
"""

import json
import logging

logger = logging.getLogger(__name__)

# Set HF mirror for Chinese users
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading Embedding Model: shibing624/text2vec-base-chinese...")
        _model = SentenceTransformer('shibing624/text2vec-base-chinese', device='cpu')
        logger.info("Embedding Model loaded successfully.")
    return _model


def compute_embedding(text: str) -> str:
    """
    Compute embedding vector for a single text.

    Args:
        text: The text to embed.

    Returns:
        JSON string of the embedding vector (list of floats).
    """
    if not text or not text.strip():
        return json.dumps([0.0] * 768)

    model = _get_model()
    vector = model.encode(text)
    return json.dumps(vector.tolist())


def compute_embeddings(texts: list) -> list:
    """
    Compute embedding vectors for multiple texts in batch.

    Args:
        texts: List of texts to embed.

    Returns:
        List of JSON strings of embedding vectors.
    """
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(texts)
    return [json.dumps(v.tolist()) for v in vectors]
