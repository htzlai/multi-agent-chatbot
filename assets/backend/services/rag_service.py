# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""RAG service layer — thin wrapper over the rag package.

Provides a service-level API so routers don't import from ``rag`` directly.
Follows the Router → Service → RAG/Infrastructure call chain.
"""

from typing import Any, Dict, List, Optional


async def query(
    query: str,
    sources: Optional[List[str]] = None,
    top_k: int = 10,
    use_hybrid: bool = True,
    use_cache: bool = True,
    use_reranker: bool = True,
    rerank_top_k: int = 5,
    use_hyde: bool = False,
) -> Dict[str, Any]:
    """Execute a RAG query using hybrid search (BM25 + Vector)."""
    from rag import enhanced_rag_query

    return await enhanced_rag_query(
        query=query,
        sources=sources,
        top_k=top_k,
        use_hybrid=use_hybrid,
        use_cache=use_cache,
        use_reranker=use_reranker,
        rerank_top_k=rerank_top_k,
        use_hyde=use_hyde,
    )


def get_stats() -> Dict[str, Any]:
    """Get RAG system statistics."""
    from rag import get_stats as _get_stats

    return _get_stats()


def rebuild_bm25() -> Dict[str, Any]:
    """Rebuild the BM25 index and return document count."""
    from rag import get_bm25_indexer

    indexer = get_bm25_indexer()
    indexer.initialize()
    return {
        "status": "success",
        "document_count": len(indexer.documents),
    }
