# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Health-check business logic — infrastructure status aggregation.

Consolidates service-health probing from ``routers/health.py``.
All Milvus access goes through ``infrastructure.milvus_client`` (R2 compliant).
"""

import os
import time
from typing import Any, Dict

import httpx

from infrastructure.cache import get_query_cache, get_redis_query_cache
from infrastructure.milvus_client import (
    get_collection,
    get_connection,
    health_check as milvus_health_check,
)
from logger import logger


async def check_all_services(storage) -> Dict[str, Any]:
    """Aggregate health status across all infrastructure services.

    Checks: PostgreSQL, Milvus, Embedding, LLM, Langfuse, Redis.
    Returns dict with ``status``, ``timestamp``, ``services``.
    """
    status: Dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {},
    }

    # PostgreSQL
    try:
        await storage.init_pool()
        status["services"]["postgres"] = "healthy"
    except Exception as e:
        status["services"]["postgres"] = f"unhealthy: {str(e)[:50]}"
        status["status"] = "degraded"

    # Milvus
    try:
        result = milvus_health_check()
        status["services"]["milvus"] = result.get("status", "unknown")
    except Exception as e:
        status["services"]["milvus"] = f"unhealthy: {str(e)[:50]}"
        status["status"] = "degraded"

    # Embedding service
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://qwen3-embedding:8000/v1/embeddings",
                json={"input": "test", "model": "qwen3-embedding"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                status["services"]["embedding"] = "healthy"
            else:
                status["services"]["embedding"] = f"degraded: {resp.status_code}"
    except Exception as e:
        status["services"]["embedding"] = f"unhealthy: {str(e)[:50]}"
        status["status"] = "degraded"

    # LLM service
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://gpt-oss-120b:8000/v1/models",
                timeout=5.0,
            )
            status["services"]["llm"] = "healthy"
    except Exception as e:
        status["services"]["llm"] = f"unhealthy: {str(e)[:50]}"
        status["status"] = "degraded"

    # Langfuse
    try:
        langfuse_host = os.getenv("LANGFUSE_BASE_URL", "http://langfuse:3000")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{langfuse_host}/api/health", timeout=5.0)
            if resp.status_code == 200:
                status["services"]["langfuse"] = "healthy"
            else:
                status["services"]["langfuse"] = f"degraded: {resp.status_code}"
    except Exception as e:
        status["services"]["langfuse"] = f"unhealthy: {str(e)[:50]}"

    # Redis
    try:
        redis_cache = get_redis_query_cache()
        if redis_cache.is_healthy():
            status["services"]["redis"] = "healthy"
        else:
            status["services"]["redis"] = "degraded: using memory fallback"
    except Exception as e:
        status["services"]["redis"] = f"unhealthy: {str(e)[:50]}"

    return status


def get_rag_health() -> Dict[str, Any]:
    """RAG system health — BM25 index + cache stats."""
    from rag import get_bm25_indexer, get_stats

    stats = get_stats()
    bm25 = get_bm25_indexer()
    redis_cache = get_redis_query_cache()
    cache_stats = redis_cache.get_stats()

    return {
        "status": "healthy",
        "rag_index": stats.get("index", {}),
        "cache": {
            "backend": cache_stats.get("backend", "memory"),
            "ttl": cache_stats.get("ttl"),
            "memory_entries": cache_stats.get("memory_entries", 0),
            "redis_available": cache_stats.get("redis_available"),
            "redis_keys": cache_stats.get("redis_keys", "N/A"),
        },
        "bm25_index": {
            "initialized": bm25._initialized,
            "document_count": len(bm25.documents) if bm25._initialized else 0,
        },
    }


async def get_metrics(storage) -> Dict[str, Any]:
    """System performance metrics — Milvus, conversations, cache."""
    get_connection()
    collection = get_collection("context", load=True)
    milvus_metrics = {
        "total_entities": collection.num_entities,
        "index_count": len(collection.indexes),
    }

    chat_ids = await storage.list_conversations()
    cache = get_query_cache()

    return {
        "timestamp": time.time(),
        "milvus": milvus_metrics,
        "conversations": {"total": len(chat_ids)},
        "rag_cache": {
            "cached_queries": len(cache.cache),
            "ttl": cache.ttl,
        },
        "system": {
            "python_version": "3.12",
            "environment": "production",
        },
    }
