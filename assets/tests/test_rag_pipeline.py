# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the RAG pipeline components.

Covers: reciprocal_rank_fusion, HyDE, Reranker, BM25Indexer.
All external dependencies are mocked — no Milvus/LLM/network required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Reciprocal Rank Fusion ─────────────────────────────────


class TestReciprocalRankFusion:
    """Tests for rag.fusion.reciprocal_rank_fusion (pure function)."""

    def test_empty_inputs(self):
        from rag.fusion import reciprocal_rank_fusion

        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_vector_only(self):
        from rag.fusion import reciprocal_rank_fusion

        vector = [
            {"name": "doc1.pdf", "score": 0.9, "excerpt": "hello"},
            {"name": "doc2.pdf", "score": 0.7, "excerpt": "world"},
        ]
        result = reciprocal_rank_fusion(vector, [])
        assert len(result) == 2
        assert result[0]["name"] == "doc1.pdf"  # rank 1 → higher RRF
        assert result[0]["score"] > result[1]["score"]

    def test_bm25_only(self):
        from rag.fusion import reciprocal_rank_fusion

        bm25 = [
            {"name": "doc3.pdf", "score": 5.0, "excerpt": "foo"},
        ]
        result = reciprocal_rank_fusion([], bm25)
        assert len(result) == 1
        assert result[0]["name"] == "doc3.pdf"
        assert result[0]["bm25_score"] == 5.0
        assert result[0]["vector_score"] == 0

    def test_overlapping_sources_get_higher_rrf(self):
        """A source appearing in both lists should score higher than one in only one."""
        from rag.fusion import reciprocal_rank_fusion

        vector = [
            {"name": "both.pdf", "score": 0.9, "excerpt": "overlap"},
            {"name": "vec_only.pdf", "score": 0.5, "excerpt": "vec"},
        ]
        bm25 = [
            {"name": "both.pdf", "score": 3.0, "excerpt": "overlap"},
            {"name": "bm25_only.pdf", "score": 2.0, "excerpt": "bm25"},
        ]
        result = reciprocal_rank_fusion(vector, bm25, k=60)

        names = [r["name"] for r in result]
        assert names[0] == "both.pdf"  # appears in both → highest RRF
        assert len(result) == 3

    def test_rrf_score_formula(self):
        """Verify RRF score = 1/(k+rank) per list, summed for overlapping docs."""
        from rag.fusion import reciprocal_rank_fusion

        k = 60
        vector = [{"name": "a", "score": 1.0, "excerpt": "x"}]
        bm25 = [{"name": "a", "score": 1.0, "excerpt": "x"}]
        result = reciprocal_rank_fusion(vector, bm25, k=k)

        expected_score = 1.0 / (k + 1) + 1.0 / (k + 1)
        assert abs(result[0]["score"] - expected_score) < 1e-10

    def test_preserves_excerpt_from_vector(self):
        """Excerpt comes from vector results when available."""
        from rag.fusion import reciprocal_rank_fusion

        vector = [{"name": "a", "score": 1.0, "excerpt": "from_vector"}]
        bm25 = [{"name": "a", "score": 1.0, "excerpt": "from_bm25"}]
        result = reciprocal_rank_fusion(vector, bm25)
        assert result[0]["excerpt"] == "from_vector"

    def test_items_without_name_are_skipped(self):
        from rag.fusion import reciprocal_rank_fusion

        vector = [{"score": 0.9, "excerpt": "no name"}]
        bm25 = [{"name": "", "score": 0.5, "excerpt": "empty name"}]
        result = reciprocal_rank_fusion(vector, bm25)
        assert result == []


# ── HyDE Query Expansion ──────────────────────────────────


class TestHyDE:
    """Tests for rag.hyde.HyDEQueryExpander."""

    @pytest.mark.asyncio
    async def test_expand_success(self):
        """HyDE returns [query, hypothetical_doc] on success."""
        from rag.hyde import HyDEQueryExpander

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "hypothetical answer"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("rag.hyde.get_llm_client", return_value=mock_client), \
             patch("rag.hyde.get_llm_model", return_value="test-model"):
            expander = HyDEQueryExpander()
            result = await expander.expand("What is DGX Spark?")

        assert len(result) == 2
        assert result[0] == "What is DGX Spark?"
        assert result[1] == "hypothetical answer"

    @pytest.mark.asyncio
    async def test_expand_fallback_on_error(self):
        """HyDE returns [query] when LLM call fails."""
        from rag.hyde import HyDEQueryExpander

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("LLM unavailable")
        )

        with patch("rag.hyde.get_llm_client", return_value=mock_client), \
             patch("rag.hyde.get_llm_model", return_value="test-model"):
            expander = HyDEQueryExpander()
            result = await expander.expand("test query")

        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_expand_query_with_hyde_disabled(self):
        """expand_query_with_hyde returns [query] when use_hyde=False."""
        from rag.hyde import expand_query_with_hyde

        result = await expand_query_with_hyde("test", use_hyde=False)
        assert result == ["test"]


# ── Reranker ───────────────────────────────────────────────


class TestReranker:
    """Tests for rag.reranker.Reranker."""

    def test_rerank_simple_keyword_overlap(self):
        """Simple reranker scores by keyword overlap ratio."""
        from rag.reranker import Reranker

        docs = [
            {"name": "doc1", "text": "apple banana cherry"},
            {"name": "doc2", "text": "apple banana"},
            {"name": "doc3", "text": "grape mango"},
        ]
        doc_texts = [d["text"] for d in docs]

        result = Reranker._rerank_simple("apple banana", doc_texts, docs, top_k=3)

        assert len(result) == 3
        # doc2 has perfect overlap (2/2), doc1 also (2/2), doc3 has 0
        assert result[-1]["name"] == "doc3"
        assert result[-1]["rerank_score"] == 0.0

    def test_rerank_simple_top_k(self):
        """Simple reranker respects top_k limit."""
        from rag.reranker import Reranker

        docs = [{"name": f"doc{i}", "text": f"word{i}"} for i in range(10)]
        doc_texts = [d["text"] for d in docs]

        result = Reranker._rerank_simple("word0", doc_texts, docs, top_k=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Rerank returns empty list for empty input."""
        from rag.reranker import Reranker

        reranker = Reranker()
        result = await reranker.rerank("query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_no_host_uses_simple(self):
        """Without host, rerank uses simple keyword fallback."""
        from rag.reranker import Reranker

        reranker = Reranker(host=None, top_k=2)
        docs = [
            {"name": "a", "text": "machine learning deep"},
            {"name": "b", "text": "cooking recipe pasta"},
        ]
        result = await reranker.rerank("machine learning", docs)
        assert len(result) == 2
        assert result[0]["name"] == "a"

    @pytest.mark.asyncio
    async def test_rerank_external_success(self):
        """External reranker returns reordered results with rerank_score."""
        from rag.reranker import Reranker

        reranker = Reranker(host="http://fake-reranker:8080", top_k=2)
        docs = [
            {"name": "a", "text": "first doc"},
            {"name": "b", "text": "second doc"},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "indices": [1, 0],
            "scores": [0.95, 0.3],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("rag.reranker.httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("query", docs, top_k=2)

        assert len(result) == 2
        assert result[0]["name"] == "b"  # index 1 first
        assert result[0]["rerank_score"] == 0.95

    @pytest.mark.asyncio
    async def test_rerank_external_fallback_on_error(self):
        """External reranker falls back to simple on HTTP error."""
        from rag.reranker import Reranker

        reranker = Reranker(host="http://fake:8080", top_k=2)
        docs = [
            {"name": "a", "text": "relevant content"},
            {"name": "b", "text": "other stuff"},
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("rag.reranker.httpx.AsyncClient", return_value=mock_client):
            result = await reranker.rerank("relevant", docs, top_k=2)

        assert len(result) == 2
        assert all("rerank_score" in r for r in result)

    @pytest.mark.asyncio
    async def test_rerank_documents_disabled(self):
        """rerank_documents returns original docs when disabled."""
        from rag.reranker import rerank_documents

        docs = [{"name": f"d{i}"} for i in range(10)]
        result = await rerank_documents("q", docs, top_k=3, use_reranker=False)
        assert len(result) == 3


# ── BM25 Indexer ───────────────────────────────────────────


class TestBM25Indexer:
    """Tests for rag.bm25.BM25Indexer (unit tests with manual population)."""

    def test_tokenize(self):
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        tokens = indexer._tokenize("Hello, World! Test-123")
        assert tokens == ["hello", "world", "test", "123"]

    def test_tokenize_empty(self):
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        assert indexer._tokenize("") == []

    def test_search_uninitialised_returns_empty(self):
        """Search on uninitialized indexer (with mocked initialize) returns empty."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        # Mock initialize to prevent actual Milvus connection
        indexer.initialize = MagicMock()
        result = indexer.search("test query")
        assert result == []

    def test_search_with_manual_corpus(self):
        """Search works correctly on a manually populated BM25 index."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        indexer.documents = [
            {"text": "machine learning is great", "source": "ml.pdf"},
            {"text": "cooking pasta recipe italian", "source": "cook.pdf"},
            {"text": "machine learning deep neural networks", "source": "dl.pdf"},
        ]
        indexer.doc_ids = ["0", "1", "2"]
        indexer.tokenized_corpus = [
            indexer._tokenize(d["text"]) for d in indexer.documents
        ]
        indexer._doc_len = [len(t) for t in indexer.tokenized_corpus]
        indexer._avgdl = sum(indexer._doc_len) / len(indexer._doc_len)
        indexer._initialized = True

        results = indexer.search("machine learning", top_k=2)

        assert len(results) == 2
        # Both ML docs should score higher than cooking doc
        indices = [r[0] for r in results]
        assert 0 in indices  # ml.pdf
        assert 2 in indices  # dl.pdf
        # Scores should be positive
        assert all(score > 0 for _, score in results)

    def test_search_no_match(self):
        """Query with no matching terms returns zero scores."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        indexer.documents = [{"text": "alpha beta gamma", "source": "a.pdf"}]
        indexer.doc_ids = ["0"]
        indexer.tokenized_corpus = [indexer._tokenize("alpha beta gamma")]
        indexer._doc_len = [3]
        indexer._avgdl = 3.0
        indexer._initialized = True

        results = indexer.search("zebra unicorn", top_k=5)
        assert len(results) == 1
        assert results[0][1] == 0.0  # zero score

    def test_initialize_with_mocked_milvus(self):
        """initialize() builds index from mocked Milvus collection."""
        from rag.bm25 import BM25Indexer

        mock_collection = MagicMock()
        mock_collection.query.return_value = [
            {"pk": 1, "text": "hello world", "source": "doc1.pdf"},
            {"pk": 2, "text": "foo bar baz", "source": "doc2.pdf"},
            {"pk": 3, "text": "", "source": "empty.pdf"},  # should be skipped
        ]

        with patch("rag.bm25.get_connection"), \
             patch("rag.bm25.get_collection", return_value=mock_collection):
            indexer = BM25Indexer()
            indexer.initialize("context")

        assert indexer.is_initialized
        assert len(indexer.documents) == 2  # empty text skipped
        assert indexer._avgdl > 0

    def test_calc_idf(self):
        """IDF calculation produces expected values."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        indexer.tokenized_corpus = [
            ["hello", "world"],
            ["hello", "foo"],
            ["bar", "baz"],
        ]

        idf = indexer._calc_idf()
        # "hello" appears in 2/3 docs, "bar" in 1/3
        assert idf["hello"] < idf["bar"]  # rarer terms get higher IDF


# ── Pipeline generate_answer ───────────────────────────────


class TestGenerateAnswer:
    """Tests for rag.pipeline.generate_answer."""

    @pytest.mark.asyncio
    async def test_generate_answer_success(self):
        from rag.pipeline import generate_answer

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LLM answer"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("rag.pipeline.get_llm_client", return_value=mock_client), \
             patch("rag.pipeline.get_llm_model", return_value="test-model"):
            result = await generate_answer("What is X?", "Context about X")

        assert result == "LLM answer"

    @pytest.mark.asyncio
    async def test_generate_answer_fallback_on_error(self):
        from rag.pipeline import generate_answer

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("LLM down")
        )

        with patch("rag.pipeline.get_llm_client", return_value=mock_client), \
             patch("rag.pipeline.get_llm_model", return_value="test-model"):
            result = await generate_answer("query", "some context")

        assert "some context" in result


# ── _truncate_sources ─────────────────────────────────────


class TestTruncateSources:
    """Tests for rag.pipeline._truncate_sources (pure function)."""

    def test_truncates_to_top_k(self):
        from rag.pipeline import _truncate_sources

        sources = [
            {"name": f"doc{i}.pdf", "score": 1.0 - i * 0.1, "excerpt": f"text{i}"}
            for i in range(5)
        ]
        result = _truncate_sources(sources, top_k=2)
        assert len(result) == 2
        assert result[0]["name"] == "doc0.pdf"
        assert result[1]["name"] == "doc1.pdf"

    def test_excerpt_truncated_to_500_chars(self):
        from rag.pipeline import _truncate_sources

        long_excerpt = "x" * 1000
        sources = [{"name": "long.pdf", "score": 0.9, "excerpt": long_excerpt}]
        result = _truncate_sources(sources, top_k=1)
        assert len(result[0]["excerpt"]) == 500

    def test_missing_optional_fields(self):
        """vector_score and bm25_score absent → returned as None."""
        from rag.pipeline import _truncate_sources

        sources = [{"name": "a.pdf", "score": 0.8, "excerpt": "hello"}]
        result = _truncate_sources(sources, top_k=1)
        assert result[0]["vector_score"] is None
        assert result[0]["bm25_score"] is None

    def test_empty_excerpt_returns_empty_string(self):
        from rag.pipeline import _truncate_sources

        sources = [{"name": "a.pdf", "score": 0.5, "excerpt": ""}]
        result = _truncate_sources(sources, top_k=1)
        assert result[0]["excerpt"] == ""

    def test_none_excerpt_returns_empty_string(self):
        from rag.pipeline import _truncate_sources

        sources = [{"name": "a.pdf", "score": 0.5}]
        result = _truncate_sources(sources, top_k=1)
        assert result[0]["excerpt"] == ""

    def test_empty_sources_returns_empty(self):
        from rag.pipeline import _truncate_sources

        assert _truncate_sources([], top_k=5) == []


# ── bm25_query ────────────────────────────────────────────


class TestBm25Query:
    """Tests for rag.bm25.bm25_query (module-level wrapper)."""

    def _make_indexer(self, documents):
        """Create a pre-populated BM25Indexer."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        indexer.documents = documents
        indexer.doc_ids = [str(i) for i in range(len(documents))]
        indexer.tokenized_corpus = [
            indexer._tokenize(d["text"]) for d in documents
        ]
        indexer._doc_len = [len(t) for t in indexer.tokenized_corpus]
        indexer._avgdl = (
            sum(indexer._doc_len) / len(indexer._doc_len)
            if indexer._doc_len
            else 0
        )
        indexer._initialized = True
        return indexer

    @patch("rag.bm25.get_bm25_indexer")
    def test_source_filtering(self, mock_get):
        from rag.bm25 import bm25_query

        docs = [
            {"text": "machine learning intro", "source": "ml.pdf"},
            {"text": "machine learning advanced", "source": "ml2.pdf"},
            {"text": "cooking recipe", "source": "cook.pdf"},
        ]
        mock_get.return_value = self._make_indexer(docs)

        result = bm25_query("machine learning", top_k=5, sources=["ml.pdf"])
        source_names = [s["name"] for s in result["sources"]]
        assert "ml.pdf" in source_names
        assert "ml2.pdf" not in source_names
        assert "cook.pdf" not in source_names

    @patch("rag.bm25.get_bm25_indexer")
    def test_deduplication(self, mock_get):
        """Each source name appears at most once."""
        from rag.bm25 import bm25_query

        docs = [
            {"text": "page one content", "source": "same.pdf"},
            {"text": "page two content", "source": "same.pdf"},
        ]
        mock_get.return_value = self._make_indexer(docs)

        result = bm25_query("page content", top_k=10)
        assert result["num_sources"] == 1

    @patch("rag.bm25.get_bm25_indexer")
    def test_top_k_limit(self, mock_get):
        from rag.bm25 import bm25_query

        docs = [
            {"text": f"topic{i} words", "source": f"doc{i}.pdf"}
            for i in range(10)
        ]
        mock_get.return_value = self._make_indexer(docs)

        result = bm25_query("topic0 topic1 topic2 topic3 topic4", top_k=3)
        assert len(result["sources"]) <= 3

    @patch("rag.bm25.get_bm25_indexer")
    def test_uninitialized_auto_initializes(self, mock_get):
        """If indexer is not initialized, bm25_query calls initialize()."""
        from rag.bm25 import BM25Indexer

        indexer = BM25Indexer()
        # initialize() sets _initialized=True so search() won't call it again
        indexer.initialize = MagicMock(side_effect=lambda: setattr(indexer, '_initialized', True))
        indexer._initialized = False
        mock_get.return_value = indexer

        from rag.bm25 import bm25_query

        result = bm25_query("test")
        indexer.initialize.assert_called_once()
        assert result["num_sources"] == 0


# ── enhanced_rag_query ────────────────────────────────────


class TestEnhancedRagQuery:
    """Tests for rag.pipeline.enhanced_rag_query (main entry point)."""

    @pytest.mark.asyncio
    @patch("rag.pipeline.get_query_cache")
    async def test_cache_hit_returns_cached_result(self, mock_cache_factory):
        import json
        from rag.pipeline import enhanced_rag_query

        cached_data = {
            "answer": "cached answer",
            "sources": [{"name": "c.pdf", "score": 0.9}],
            "num_sources": 1,
            "search_type": "hybrid",
        }
        mock_cache = MagicMock()
        mock_cache.get.return_value = json.dumps(cached_data)
        mock_cache_factory.return_value = mock_cache

        result = await enhanced_rag_query("test query", use_cache=True)
        assert result["answer"] == "cached answer"
        assert result["search_type"] == "hybrid"

    @pytest.mark.asyncio
    async def test_total_failure_returns_error_type(self):
        """Both primary search and VectorStore fallback fail → error result."""
        from rag.pipeline import enhanced_rag_query

        with patch("rag.pipeline.get_query_cache") as mock_cf, \
             patch("rag.pipeline.hybrid_search", new_callable=AsyncMock,
                   side_effect=Exception("primary fail")), \
             patch("services.vector_store_service.VectorStore",
                   side_effect=Exception("fallback fail")):
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cf.return_value = mock_cache

            result = await enhanced_rag_query("broken query", use_cache=True)

        assert result["search_type"] == "error"
        assert result["num_sources"] == 0

    @pytest.mark.asyncio
    async def test_cache_disabled_skips_lookup(self):
        """use_cache=False skips cache entirely."""
        from rag.pipeline import enhanced_rag_query

        search_result = {
            "answer": "live answer",
            "sources": [],
            "num_sources": 0,
            "search_type": "hybrid",
            "reranking_enabled": False,
        }

        with patch("rag.pipeline.hybrid_search", new_callable=AsyncMock,
                   return_value=search_result), \
             patch("rag.pipeline.rerank_documents", new_callable=AsyncMock,
                   return_value=[]), \
             patch("rag.pipeline.get_query_cache") as mock_cf:
            result = await enhanced_rag_query(
                "test", use_cache=False, use_reranker=False
            )
            mock_cf.assert_not_called()

        assert result["answer"] == "live answer"


# ── get_stats ─────────────────────────────────────────────


class TestGetStats:
    """Tests for rag.pipeline.get_stats."""

    @patch("rag.pipeline.get_redis_query_cache")
    @patch("rag.pipeline.get_vector_counts")
    def test_successful_stats(self, mock_counts, mock_redis):
        from rag.pipeline import get_stats

        mock_counts.return_value = {"count": 500}
        mock_redis.return_value = MagicMock(
            get_stats=MagicMock(return_value={
                "backend": "redis",
                "redis_available": True,
                "ttl": 3600,
                "redis_keys": 42,
            })
        )

        result = get_stats()
        assert result["index"]["total_entities"] == 500
        assert result["cache"]["backend"] == "redis"
        assert result["cache"]["cached_queries"] == 42

    @patch("rag.pipeline.get_redis_query_cache")
    @patch("rag.pipeline.get_vector_counts", side_effect=Exception("Milvus down"))
    def test_milvus_failure_returns_zero(self, mock_counts, mock_redis):
        from rag.pipeline import get_stats

        mock_redis.return_value = MagicMock(
            get_stats=MagicMock(return_value={
                "backend": "memory",
                "redis_available": False,
            })
        )

        result = get_stats()
        assert result["index"]["total_entities"] == 0
