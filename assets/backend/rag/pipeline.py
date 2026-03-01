# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Enhanced RAG pipeline — orchestrates the full retrieval flow.

Stages: cache check → HyDE expansion → parallel vector+BM25 search →
RRF fusion → cross-encoder reranking → LLM answer generation → cache store.

Fully async — no ``asyncio.new_event_loop()`` anti-patterns.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from infrastructure.cache import get_query_cache, get_redis_query_cache
from infrastructure.embedding_client import DEFAULT_DIMENSIONS, get_embedding_client
from infrastructure.llm_client import get_llm_client, get_llm_model
from infrastructure.milvus_client import (
    detect_metric_type,
    get_collection,
    get_connection,
    get_vector_counts,
)

from rag.bm25 import bm25_query, get_bm25_indexer
from rag.fusion import reciprocal_rank_fusion
from rag.hyde import expand_query_with_hyde
from rag.reranker import rerank_documents

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# LLM answer generation (async — fixed event-loop bug)
# ------------------------------------------------------------------

_ANSWER_SYSTEM = """你是一个专业的问答助手。请根据以下检索到的文档内容来回答用户的问题。

要求：
1. 只根据提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，请明确说明"根据检索到的文档，未找到相关信息"
3. 回答要准确、简洁、使用中文

检索到的文档内容：
{context}

请根据以上文档内容回答问题。"""


async def generate_answer(query: str, context: str) -> str:
    """Generate an LLM answer grounded in *context*.

    Falls back to a raw context snippet on any failure.
    """
    client = get_llm_client()
    model = get_llm_model()

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ANSWER_SYSTEM.format(context=context[:3000])},
                {"role": "user", "content": query},
            ],
            max_tokens=1000,
            temperature=0.3,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"LLM answer generation failed: {e}")
        return f"根据检索到的文档，以下是相关信息：\n\n{context[:1000]}..."


# ------------------------------------------------------------------
# Vector search (async via infrastructure clients)
# ------------------------------------------------------------------


async def vector_search(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Async vector search via Milvus + Qwen3 embeddings.

    Returns ``{"answer": ..., "sources": [...], "num_sources": N, "search_type": "vector"}``.
    """
    embedding_client = get_embedding_client()
    query_embedding = await embedding_client.embed_single(query)

    collection = get_collection("context")
    metric_type = detect_metric_type("context")
    search_params = {"metric_type": metric_type, "params": {}}

    expr = f"source in {sources}" if sources else None

    results = collection.search(
        data=[query_embedding],
        anns_field="vector",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["text", "source", "file_path", "filename"],
    )

    sources_data: List[Dict[str, Any]] = []
    answer_parts: List[str] = []

    for hits in results:
        for hit in hits:
            source = hit.entity.get("source", "unknown")
            text = hit.entity.get("text", "")
            score = hit.distance

            if not any(s["name"] == source for s in sources_data):
                sources_data.append(
                    {
                        "name": source,
                        "score": float(score) if score else None,
                        "excerpt": text[:500] if text else "",
                    }
                )
            answer_parts.append(text)

    context = "\n\n".join(answer_parts[:3])
    answer = await generate_answer(query, context)

    return {
        "answer": answer,
        "sources": sources_data,
        "num_sources": len(sources_data),
        "search_type": "vector",
    }


# ------------------------------------------------------------------
# Hybrid search (parallel vector + BM25 via asyncio.gather)
# ------------------------------------------------------------------


async def hybrid_search(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
    use_reranker: bool = True,
    rerank_top_k: int = 5,
) -> Dict[str, Any]:
    """Hybrid search: vector + BM25 → RRF fusion → optional reranking.

    Runs vector search and BM25 in parallel via ``asyncio.gather``.
    """

    async def _run_bm25():
        return bm25_query(query, top_k=top_k, sources=sources)

    # Run vector search (async) and BM25 (sync, wrapped) in parallel
    vector_result, bm25_result = await asyncio.gather(
        vector_search(query, top_k=top_k, sources=sources),
        asyncio.to_thread(_run_bm25),
    )

    vector_sources = vector_result.get("sources", [])
    bm25_sources = bm25_result.get("sources", [])

    # RRF fusion
    fused_sources = reciprocal_rank_fusion(vector_sources, bm25_sources, k=60)

    # Prepare reranking candidates
    rerank_candidates = [
        {
            "name": item["name"],
            "score": item["score"],
            "vector_score": item.get("vector_score"),
            "bm25_score": item.get("bm25_score"),
            "excerpt": item["excerpt"][:500] if item.get("excerpt") else "",
            "text": item.get("text", item.get("excerpt", "")),
        }
        for item in fused_sources[: top_k * 2]
    ]

    # Rerank
    if use_reranker and rerank_candidates:
        try:
            reranked = await rerank_documents(
                query=query,
                documents=rerank_candidates,
                top_k=rerank_top_k,
                use_reranker=True,
            )
            final_sources = [
                {
                    "name": doc["name"],
                    "score": doc.get("rerank_score", doc["score"]),
                    "vector_score": doc.get("vector_score"),
                    "bm25_score": doc.get("bm25_score"),
                    "excerpt": doc["excerpt"][:500] if doc.get("excerpt") else "",
                }
                for doc in reranked
            ]
            search_type = "hybrid+reranked"
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, using fused results")
            final_sources = _truncate_sources(fused_sources, top_k)
            search_type = "hybrid"
    else:
        final_sources = _truncate_sources(fused_sources, top_k)
        search_type = "hybrid"

    # Generate answer from top excerpts
    answer_parts = [s["excerpt"] for s in final_sources[:3] if s.get("excerpt")]
    context = "\n\n".join(answer_parts)
    answer = await generate_answer(query, context)

    return {
        "answer": answer,
        "sources": final_sources,
        "num_sources": len(final_sources),
        "search_type": search_type,
        "reranking_enabled": use_reranker,
    }


def _truncate_sources(sources: List[Dict], top_k: int) -> List[Dict]:
    """Return formatted source dicts, truncated to *top_k*."""
    return [
        {
            "name": item["name"],
            "score": item["score"],
            "vector_score": item.get("vector_score"),
            "bm25_score": item.get("bm25_score"),
            "excerpt": item["excerpt"][:500] if item.get("excerpt") else "",
        }
        for item in sources[:top_k]
    ]


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------


async def enhanced_rag_query(
    query: str,
    sources: Optional[List[str]] = None,
    use_cache: bool = True,
    top_k: int = 10,
    use_hybrid: bool = True,
    use_reranker: bool = True,
    rerank_top_k: int = 5,
    use_hyde: bool = False,
) -> Dict[str, Any]:
    """Full enhanced RAG pipeline: cache → HyDE → search → fuse → rerank → answer → cache.

    Args:
        query: The search query.
        sources: Optional source filter list.
        use_cache: Whether to use query cache.
        top_k: Candidate count before reranking.
        use_hybrid: Use hybrid (vector + BM25) or vector-only.
        use_reranker: Apply cross-encoder reranking.
        rerank_top_k: Final result count after reranking.
        use_hyde: Apply HyDE query expansion.
    """
    # HyDE expansion
    expanded_queries = [query]
    hyde_applied = False

    if use_hyde:
        try:
            expanded_queries = await expand_query_with_hyde(query, use_hyde=True)
            hyde_applied = len(expanded_queries) > 1
            logger.info(f"HyDE expanded query to {len(expanded_queries)} variants")
        except Exception as e:
            logger.warning(f"HyDE expansion failed: {e}, using original query")

    # Cache lookup
    if use_cache:
        cache = get_query_cache()
        cached = cache.get(query, sources, top_k, use_hybrid)
        if cached:
            logger.info(f"Cache hit for query: {query[:50]}...")
            result = json.loads(cached)
            result["hyde_applied"] = hyde_applied
            return result

    # Execute search for each expanded query
    all_results: List[Dict[str, Any]] = []
    try:
        for eq in expanded_queries:
            if use_hybrid:
                result = await hybrid_search(
                    eq,
                    top_k=top_k,
                    sources=sources,
                    use_reranker=False,
                    rerank_top_k=rerank_top_k,
                )
            else:
                result = await vector_search(eq, top_k=top_k, sources=sources)
            all_results.append(result)

        # Merge results from expanded queries
        if len(all_results) > 1:
            combined: Dict[str, Dict] = {}
            for r in all_results:
                for src in r.get("sources", []):
                    name = src.get("name")
                    if name and (
                        name not in combined
                        or src.get("score", 0) > combined[name].get("score", 0)
                    ):
                        combined[name] = src

            final_sources = list(combined.values())[:top_k]
            if use_reranker:
                final_sources = await rerank_documents(
                    query, final_sources, rerank_top_k
                )

            final_result = {**all_results[0], "sources": final_sources}
            final_result["num_sources"] = len(final_sources)
            final_result["search_type"] = "hybrid+hyde"
        else:
            final_result = all_results[0]
            if use_reranker:
                reranked = await rerank_documents(
                    query, final_result.get("sources", []), rerank_top_k
                )
                final_result["sources"] = reranked
            if hyde_applied:
                final_result["search_type"] = "hybrid+hyde"

        final_result["hyde_applied"] = hyde_applied
        final_result["reranking_enabled"] = use_reranker

    except Exception as e:
        logger.error(f"RAG pipeline error: {e}")
        # Fallback to VectorStore
        try:
            from services.vector_store_service import VectorStore

            vs = VectorStore()
            docs = vs.get_documents(query, k=top_k, sources=sources)

            sources_data: List[Dict] = []
            answer_parts: List[str] = []
            for doc in docs:
                source = doc.metadata.get("source", "unknown")
                if not any(s["name"] == source for s in sources_data):
                    sources_data.append(
                        {"name": source, "excerpt": doc.page_content[:500]}
                    )
                answer_parts.append(doc.page_content)

            context = "\n\n".join(answer_parts[:3])
            final_result = {
                "answer": f"根据检索到的文档：\n\n{context[:1000]}...",
                "sources": sources_data,
                "num_sources": len(sources_data),
                "search_type": "fallback",
            }
        except Exception as fallback_err:
            logger.error(f"Fallback search also failed: {fallback_err}")
            final_result = {
                "answer": "搜索服务暂时不可用，请稍后重试。",
                "sources": [],
                "num_sources": 0,
                "search_type": "error",
            }

    # Cache result
    if use_cache:
        cache = get_query_cache()
        cache.set(query, json.dumps(final_result), sources, top_k, use_hybrid)

    return final_result


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------


def get_stats() -> Dict[str, Any]:
    """Return system statistics (Milvus + cache)."""
    try:
        stats = get_vector_counts("context")
        total_entities = stats.get("count", 0)
    except Exception as e:
        logger.error(f"Error getting Milvus stats: {e}")
        total_entities = 0

    redis_cache = get_redis_query_cache()
    redis_stats = redis_cache.get_stats()

    return {
        "index": {
            "collection": "context",
            "milvus_uri": "http://milvus:19530",
            "embedding_dimensions": DEFAULT_DIMENSIONS,
            "total_entities": total_entities,
        },
        "cache": {
            "enabled": True,
            "backend": redis_stats.get("backend", "memory"),
            "redis_available": redis_stats.get("redis_available"),
            "ttl": redis_stats.get("ttl"),
            "cached_queries": redis_stats.get("redis_keys", 0),
        },
    }
