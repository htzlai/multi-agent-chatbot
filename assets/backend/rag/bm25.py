# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""BM25 full-text search indexer.

Loads documents from Milvus into an in-memory BM25 index and provides
keyword-based retrieval as a complement to vector search.

Uses ``infrastructure.milvus_client`` instead of direct ``pymilvus`` imports.
"""

import logging
import math
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.milvus_client import get_collection, get_connection

logger = logging.getLogger(__name__)


class BM25Indexer:
    """In-memory BM25 indexer over a Milvus collection."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

        self.documents: List[Dict[str, Any]] = []
        self.doc_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self._doc_len: List[int] = []
        self._avgdl: float = 0.0
        self._initialized = False

    # ------------------------------------------------------------------
    # Tokenisation
    # ------------------------------------------------------------------

    _TOKEN_RE = re.compile(r"[a-z0-9]+")

    def _tokenize(self, text: str) -> List[str]:
        """Lowercase + split on non-alphanumeric boundaries."""
        return self._TOKEN_RE.findall(text.lower())

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def initialize(self, collection_name: str = "context") -> None:
        """Build the BM25 index from documents in a Milvus collection.

        NOTE: This loads the *entire* collection into memory.  For very
        large collections consider paging via ``offset``/``limit`` or
        incremental indexing.
        """
        try:
            get_connection()
            collection = get_collection(collection_name)

            results = collection.query(
                expr="pk >= 0",
                output_fields=["pk", "text", "source", "file_path", "filename"],
            )

            self.documents = []
            self.doc_ids = []
            self.tokenized_corpus = []
            self._doc_len = []

            for i, doc in enumerate(results):
                text = doc.get("text", "")
                if text and text.strip():
                    self.documents.append(doc)
                    self.doc_ids.append(str(doc.get("pk", i)))
                    tokens = self._tokenize(text)
                    self.tokenized_corpus.append(tokens)
                    self._doc_len.append(len(tokens))

            self._avgdl = (
                sum(self._doc_len) / len(self._doc_len) if self._doc_len else 0
            )
            self._initialized = True
            logger.info(f"BM25 index initialized with {len(self.documents)} documents")

        except Exception as e:
            logger.error(f"Error initializing BM25 index: {e}")
            self._initialized = False

    # ------------------------------------------------------------------
    # IDF
    # ------------------------------------------------------------------

    def _calc_idf(self) -> Dict[str, float]:
        """Calculate IDF for every term in the corpus."""
        n = len(self.tokenized_corpus)
        df: Dict[str, int] = {}

        for doc_tokens in self.tokenized_corpus:
            for term in set(doc_tokens):
                df[term] = df.get(term, 0) + 1

        return {
            term: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Return ``(doc_index, bm25_score)`` pairs, descending by score."""
        if not self._initialized:
            self.initialize()

        if not self.tokenized_corpus:
            return []

        query_tokens = self._tokenize(query)
        idf = self._calc_idf()

        scores: List[Tuple[int, float]] = []
        for i, doc_tokens in enumerate(self.tokenized_corpus):
            doc_freq: Dict[str, int] = {}
            for t in doc_tokens:
                doc_freq[t] = doc_freq.get(t, 0) + 1

            score = 0.0
            doc_len = self._doc_len[i]
            for qt in query_tokens:
                tf = doc_freq.get(qt, 0)
                if tf > 0:
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (
                        1 - self.b + self.b * doc_len / self._avgdl
                    )
                    score += idf.get(qt, 0) * numerator / denominator

            scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @property
    def is_initialized(self) -> bool:
        return self._initialized


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


@lru_cache()
def get_bm25_indexer() -> BM25Indexer:
    """Return the shared ``BM25Indexer`` singleton."""
    return BM25Indexer()


def bm25_query(
    query: str,
    top_k: int = 10,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Query using BM25 full-text search.

    Returns a dict with ``answer_parts``, ``sources``, ``num_sources``.
    """
    indexer = get_bm25_indexer()

    if not indexer.is_initialized:
        indexer.initialize()

    results = indexer.search(query, top_k=top_k * 2)

    sources_data: List[Dict[str, Any]] = []
    answer_parts: List[str] = []
    seen_sources: set = set()

    for idx, score in results:
        if idx >= len(indexer.documents):
            continue

        doc = indexer.documents[idx]
        source = doc.get("source", "unknown")

        if sources and source not in sources:
            continue

        if source not in seen_sources and len(sources_data) < top_k:
            seen_sources.add(source)
            text = doc.get("text", "")
            sources_data.append(
                {
                    "name": source,
                    "score": float(score),
                    "excerpt": text[:500] if text else "",
                }
            )
            answer_parts.append(text)

    return {
        "answer_parts": answer_parts,
        "sources": sources_data,
        "num_sources": len(sources_data),
    }
