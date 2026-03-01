# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Cross-encoder reranker for improving retrieval precision.

Fully async — uses ``httpx.AsyncClient`` for the external service path
instead of the original ``asyncio.new_event_loop()`` anti-pattern.
"""

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class Reranker:
    """Cross-encoder reranker with external-service and simple fallback paths."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        host: Optional[str] = None,
        top_k: int = 5,
    ):
        self.model_name = model_name
        self.host = host
        self.top_k = top_k

    # ------------------------------------------------------------------
    # Public API (async)
    # ------------------------------------------------------------------

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rerank *documents* by relevance to *query*.

        Returns at most *top_k* documents with an added ``rerank_score``.
        """
        if not documents:
            return []

        top_k = top_k or self.top_k

        doc_texts = [
            doc.get("text") or doc.get("excerpt", "")
            for doc in documents
            if doc.get("text") or doc.get("excerpt")
        ]

        if not doc_texts:
            return documents[:top_k]

        try:
            if self.host:
                return await self._rerank_external(
                    query, doc_texts, documents, top_k
                )
            return self._rerank_simple(query, doc_texts, documents, top_k)
        except Exception as e:
            logger.warning(f"Reranking failed: {e}, returning original order")
            return documents[:top_k]

    # ------------------------------------------------------------------
    # External reranking service (async, no new event-loop)
    # ------------------------------------------------------------------

    async def _rerank_external(
        self,
        query: str,
        doc_texts: List[str],
        original_docs: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """Call an external reranking HTTP service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.host}/rerank",
                    json={
                        "query": query,
                        "documents": doc_texts,
                        "top_k": top_k,
                    },
                )
                response.raise_for_status()
                results = response.json()

            reranked: List[Dict] = []
            indices = results.get("indices", [])
            scores = results.get("scores", [])
            for i, idx in enumerate(indices[:top_k]):
                if idx < len(original_docs):
                    doc = {**original_docs[idx]}
                    doc["rerank_score"] = scores[i] if i < len(scores) else 0.0
                    reranked.append(doc)
            return reranked

        except Exception as e:
            logger.warning(f"External reranking service failed: {e}")
            return self._rerank_simple(query, doc_texts, original_docs, top_k)

    # ------------------------------------------------------------------
    # Simple keyword-overlap fallback (sync, cheap)
    # ------------------------------------------------------------------

    @staticmethod
    def _rerank_simple(
        query: str,
        doc_texts: List[str],
        original_docs: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """Lightweight fallback: keyword overlap scoring."""
        query_terms = set(query.lower().split())

        scored: List[Dict] = []
        for i, doc in enumerate(original_docs):
            text = doc_texts[i] if i < len(doc_texts) else ""
            text_terms = set(text.lower().split())

            overlap = len(query_terms & text_terms)
            relevance = overlap / max(len(query_terms), 1)

            scored.append({**doc, "rerank_score": relevance})

        scored.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return scored[:top_k]


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


@lru_cache()
def get_reranker() -> Reranker:
    """Return the shared ``Reranker`` singleton."""
    return Reranker(
        host=os.getenv("RERANKER_HOST"),
        top_k=int(os.getenv("RERANKER_TOP_K", "5")),
    )


async def rerank_documents(
    query: str,
    documents: List[Dict[str, Any]],
    top_k: int = 5,
    use_reranker: bool = True,
) -> List[Dict[str, Any]]:
    """Convenience wrapper: rerank *documents* if enabled."""
    if not use_reranker or not documents:
        return documents[:top_k]

    reranker = get_reranker()
    return await reranker.rerank(query, documents, top_k)
