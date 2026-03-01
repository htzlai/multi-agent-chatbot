# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG pipeline — public API.

Usage::

    from rag import enhanced_rag_query, get_stats
    result = await enhanced_rag_query("my question")
"""

from rag.bm25 import bm25_query, get_bm25_indexer
from rag.fusion import reciprocal_rank_fusion
from rag.hyde import expand_query_with_hyde
from rag.pipeline import enhanced_rag_query, get_stats, hybrid_search, vector_search
from rag.reranker import rerank_documents

__all__ = [
    # Pipeline (main entry points)
    "enhanced_rag_query",
    "hybrid_search",
    "vector_search",
    "get_stats",
    # Sub-modules
    "bm25_query",
    "get_bm25_indexer",
    "reciprocal_rank_fusion",
    "expand_query_with_hyde",
    "rerank_documents",
]
