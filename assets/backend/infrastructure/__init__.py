# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Infrastructure layer — thin wrappers around external services."""

from infrastructure.cache import (
    QueryCache,
    RedisQueryCache,
    get_query_cache,
    get_redis_query_cache,
)
from infrastructure.embedding_client import AsyncQwen3Embedding, get_embedding_client
from infrastructure.llm_client import get_llm_client, get_llm_model
from infrastructure.milvus_client import (
    detect_metric_type,
    drop_collection,
    get_collection,
    get_collection_stats,
    get_connection,
    get_vector_counts,
    health_check,
    list_collections,
    query_source_counts,
    query_unique_sources,
)

__all__ = [
    "AsyncQwen3Embedding",
    "QueryCache",
    "RedisQueryCache",
    "detect_metric_type",
    "drop_collection",
    "get_collection",
    "get_collection_stats",
    "get_connection",
    "get_embedding_client",
    "get_llm_client",
    "get_llm_model",
    "get_query_cache",
    "get_redis_query_cache",
    "get_vector_counts",
    "health_check",
    "list_collections",
    "query_source_counts",
    "query_unique_sources",
]
