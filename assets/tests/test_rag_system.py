#!/usr/bin/env python3
"""
# 方式 1: 快速测试运行器 (推荐 - 输出详细)
python3 test_runner.py

# 方式 2: pytest 测试套件 (更规范)
python3 -m pytest test_rag_system.py -v
RAG System Test Suite
=====================

Comprehensive test suite for RAG (Retrieval-Augmented Generation) system.
Tests vector retrieval, metadata extraction, and integration with Milvus.

Usage:
    # Run all tests
    python -m pytest test_rag_system.py -v

    # Run specific test
    python -m pytest test_rag_system.py::TestRAGSystem::test_vector_stats -v

    # Run with coverage
    python -m pytest test_rag_system.py --cov=backend --cov-report=html
"""

import pytest
import requests
import json
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================
# Test Configuration
# ============================================================

BACKEND_URL = "http://localhost:8000"
MILVUS_URL = "http://localhost:19530"
TIMEOUT = 120  # seconds


# ============================================================
# Test Data Classes
# ============================================================

@dataclass
class RetrievalResult:
    """Represents a retrieval result with metadata."""
    total_chunks: int
    unique_sources: int
    score_range: Dict[str, float]
    sources: List[Dict[str, Any]]
    answer: str


@dataclass
class TestResult:
    """Represents a test result."""
    name: str
    passed: bool
    duration: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# Test Client
# ============================================================

class RAGTestClient:
    """Client for testing RAG system via REST API."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def get_vector_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        response = self.session.get(f"{self.base_url}/test/vector-stats", timeout=10)
        response.raise_for_status()
        return response.json()

    def get_all_sources(self) -> List[str]:
        """Get all available sources."""
        response = self.session.get(f"{self.base_url}/sources", timeout=10)
        response.raise_for_status()
        return response.json().get("sources", [])

    def get_selected_sources(self) -> List[str]:
        """Get currently selected sources."""
        response = self.session.get(f"{self.base_url}/selected_sources", timeout=10)
        response.raise_for_status()
        return response.json().get("sources", [])

    def test_rag(self, query: str, k: int = 8) -> RetrievalResult:
        """Test RAG with a query."""
        response = self.session.get(
            f"{self.base_url}/test/rag",
            params={"query": query, "k": k},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        return RetrievalResult(
            total_chunks=data["retrieval_metadata"]["total_chunks_retrieved"],
            unique_sources=data["retrieval_metadata"]["unique_sources_count"],
            score_range=data["retrieval_metadata"]["score_range"],
            sources=data.get("sources", []),
            answer=data.get("answer", "")
        )


# ============================================================
# Test Cases
# ============================================================

class TestRAGSystem:
    """Test cases for RAG system."""

    @classmethod
    def setup_class(cls):
        """Setup test class."""
        cls.client = RAGTestClient()
        cls.results: List[TestResult] = []

    def _record_result(self, name: str, passed: bool, duration: float,
                       message: str = "", details: Dict = None):
        """Record a test result."""
        self.results.append(TestResult(
            name=name,
            passed=passed,
            duration=duration,
            message=message,
            details=details or {}
        ))

    # --------------------------------------------------------
    # Test 1: Vector Store Statistics
    # --------------------------------------------------------
    def test_vector_stats(self):
        """Test vector store basic statistics."""
        start = time.time()
        try:
            stats = self.client.get_vector_stats()

            # Validate response structure
            assert "collection" in stats, "Missing 'collection' field"
            assert "total_entities" in stats, "Missing 'total_entities' field"
            assert "fields" in stats, "Missing 'fields' field"

            # Validate data
            assert stats["collection"] == "context", "Wrong collection name"
            assert stats["total_entities"] > 0, "No entities in collection"

            # Check required fields
            field_names = [f["name"] for f in stats.get("fields", [])]
            required_fields = ["text", "vector", "source", "file_path", "filename"]
            for field_name in required_fields:
                assert field_name in field_names, f"Missing required field: {field_name}"

            duration = time.time() - start
            self._record_result(
                "test_vector_stats",
                True,
                duration,
                f"Vector store has {stats['total_entities']} entities",
                {"entities": stats["total_entities"], "fields": field_names}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_vector_stats", False, duration, str(e))
            pytest.fail(f"test_vector_stats failed: {e}")

    # --------------------------------------------------------
    # Test 2: Sources Management
    # --------------------------------------------------------
    def test_sources_management(self):
        """Test sources retrieval and selection."""
        start = time.time()
        try:
            all_sources = self.client.get_all_sources()
            selected_sources = self.client.get_selected_sources()

            # Validate
            assert len(all_sources) > 0, "No sources available"
            assert len(selected_sources) > 0, "No selected sources"
            assert len(selected_sources) <= len(all_sources), "Selected > Total"

            # Check overlap
            overlap = set(selected_sources) & set(all_sources)
            assert len(overlap) == len(selected_sources), "Invalid selected sources"

            duration = time.time() - start
            self._record_result(
                "test_sources_management",
                True,
                duration,
                f"Total: {len(all_sources)}, Selected: {len(selected_sources)}",
                {"total_sources": len(all_sources), "selected_sources": len(selected_sources)}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_sources_management", False, duration, str(e))
            pytest.fail(f"test_sources_management failed: {e}")

    # --------------------------------------------------------
    # Test 3: Basic RAG Retrieval
    # --------------------------------------------------------
    def test_basic_rag_retrieval(self):
        """Test basic RAG retrieval with query."""
        start = time.time()
        try:
            query = "新加坡投资优势"
            result = self.client.test_rag(query)

            # Validate response
            assert result.total_chunks > 0, "No chunks retrieved"
            assert result.unique_sources > 0, "No sources retrieved"
            assert len(result.answer) > 0, "Empty answer"

            # Validate score range
            assert result.score_range["min"] is not None, "Missing min score"
            assert result.score_range["max"] is not None, "Missing max score"
            assert result.score_range["min"] <= result.score_range["max"], "Invalid score range"

            duration = time.time() - start
            self._record_result(
                "test_basic_rag_retrieval",
                True,
                duration,
                f"Retrieved {result.total_chunks} chunks from {result.unique_sources} sources",
                {
                    "query": query,
                    "chunks": result.total_chunks,
                    "sources": result.unique_sources,
                    "score_range": result.score_range
                }
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_basic_rag_retrieval", False, duration, str(e))
            pytest.fail(f"test_basic_rag_retrieval failed: {e}")

    # --------------------------------------------------------
    # Test 4: Response Structure Validation
    # --------------------------------------------------------
    def test_response_structure(self):
        """Test response structure and metadata completeness."""
        start = time.time()
        try:
            result = self.client.test_rag("新加坡EP签证")

            # Check top-level keys
            assert result.total_chunks > 0, "No chunks"
            assert result.unique_sources > 0, "No sources"

            # Check source structure
            if result.sources:
                for src in result.sources:
                    assert "name" in src, "Missing 'name' in source"
                    assert "chunks" in src, "Missing 'chunks' in source"
                    assert "chunk_count" in src, "Missing 'chunk_count'"
                    assert "max_score" in src, "Missing 'max_score'"
                    assert "avg_score" in src, "Missing 'avg_score'"

                    # Check chunks structure
                    for chunk in src.get("chunks", []):
                        assert "excerpt" in chunk, "Missing 'excerpt'"
                        assert "score" in chunk, "Missing 'score'"
                        assert "text_length" in chunk, "Missing 'text_length'"

            duration = time.time() - start
            self._record_result(
                "test_response_structure",
                True,
                duration,
                "Response structure is valid",
                {"sources_validated": len(result.sources)}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_response_structure", False, duration, str(e))
            pytest.fail(f"test_response_structure failed: {e}")

    # --------------------------------------------------------
    # Test 5: Multiple Query Scenarios
    # --------------------------------------------------------
    @pytest.mark.parametrize("query,expected_min_sources", [
        ("新加坡EP签证要求", 1),
        ("ODI境外投资备案", 1),
        ("新加坡公司税务", 1),
        ("制造业出海东南亚", 1),
        ("ACRA公司注册", 1),
    ])
    def test_multiple_queries(self, query: str, expected_min_sources: int):
        """Test multiple query scenarios."""
        start = time.time()
        try:
            result = self.client.test_rag(query)

            # Validate
            assert result.total_chunks > 0, f"No chunks for query: {query}"
            assert result.unique_sources >= expected_min_sources, \
                f"Expected >= {expected_min_sources} sources, got {result.unique_sources}"

            # Check score quality
            avg_score = result.score_range.get("avg")
            assert avg_score is not None, f"No avg score for query: {query}"

            duration = time.time() - start
            self._record_result(
                f"test_query_{query[:10]}",
                True,
                duration,
                f"Query '{query}' -> {result.unique_sources} sources",
                {"query": query, "sources": result.unique_sources, "avg_score": avg_score}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result(f"test_query_{query[:10]}", False, duration, str(e))
            pytest.fail(f"test_multiple_queries failed for '{query}': {e}")

    # --------------------------------------------------------
    # Test 6: Score Quality Analysis
    # --------------------------------------------------------
    def test_score_quality(self):
        """Test retrieval score quality metrics."""
        start = time.time()
        try:
            queries = [
                "制造业出海应该怎么选择",
                "新加坡EP签证",
                "ODI备案流程",
                "新加坡公司税务",
                "东南亚投资合规"
            ]

            score_analysis = []
            for query in queries:
                result = self.client.test_rag(query)
                score_analysis.append({
                    "query": query,
                    "unique_sources": result.unique_sources,
                    "score_range": result.score_range,
                    "avg_score": result.score_range.get("avg", 0)
                })

            # Calculate aggregate metrics
            avg_scores = [s["avg_score"] for s in score_analysis if s["avg_score"]]
            overall_avg = sum(avg_scores) / len(avg_scores) if avg_scores else 0
            min_avg = min(avg_scores) if avg_scores else 0
            max_avg = max(avg_scores) if avg_scores else 0

            duration = time.time() - start
            self._record_result(
                "test_score_quality",
                True,
                duration,
                f"Score quality: avg={overall_avg:.3f}, range=[{min_avg:.3f}, {max_avg:.3f}]",
                {
                    "queries_tested": len(queries),
                    "overall_avg_score": overall_avg,
                    "score_analysis": score_analysis
                }
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_score_quality", False, duration, str(e))
            pytest.fail(f"test_score_quality failed: {e}")

    # --------------------------------------------------------
    # Test 7: Answer Quality
    # --------------------------------------------------------
    def test_answer_quality(self):
        """Test answer generation quality."""
        start = time.time()
        try:
            queries = [
                "制造业出海应该怎么选择",
                "新加坡EP签证要求是什么",
                "新加坡公司税务有哪些"
            ]

            answer_lengths = []
            for query in queries:
                result = self.client.test_rag(query)
                answer_lengths.append(len(result.answer))

            avg_length = sum(answer_lengths) / len(answer_lengths) if answer_lengths else 0

            # Basic quality checks
            assert avg_length > 100, f"Answers too short: {avg_length} chars"

            duration = time.time() - start
            self._record_result(
                "test_answer_quality",
                True,
                duration,
                f"Avg answer length: {avg_length:.0f} chars",
                {"avg_length": avg_length, "queries": len(queries)}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_answer_quality", False, duration, str(e))
            pytest.fail(f"test_answer_quality failed: {e}")

    # --------------------------------------------------------
    # Test 8: Chunk Content Validation
    # --------------------------------------------------------
    def test_chunk_content(self):
        """Test chunk content extraction."""
        start = time.time()
        try:
            result = self.client.test_rag("新加坡投资")

            # Validate chunks have content
            total_chunk_content = 0
            for src in result.sources:
                for chunk in src.get("chunks", []):
                    excerpt = chunk.get("excerpt", "")
                    text_length = chunk.get("text_length", 0)
                    total_chunk_content += len(excerpt)

                    # Validate chunk
                    assert len(excerpt) > 0, "Empty chunk excerpt"
                    assert text_length > 0, "Zero text length"

            duration = time.time() - start
            self._record_result(
                "test_chunk_content",
                True,
                duration,
                f"Total chunk content: {total_chunk_content} chars",
                {"total_content": total_chunk_content}
            )

        except Exception as e:
            duration = time.time() - start
            self._record_result("test_chunk_content", False, duration, str(e))
            pytest.fail(f"test_chunk_content failed: {e}")

    # --------------------------------------------------------
    # Generate Test Report
    # --------------------------------------------------------
    @classmethod
    def generate_report(cls):
        """Generate test report."""
        passed = sum(1 for r in cls.results if r.passed)
        failed = sum(1 for r in cls.results if not r.passed)
        total = len(cls.results)
        total_time = sum(r.duration for r in cls.results)

        report = []
        report.append("=" * 70)
        report.append("RAG System Test Report")
        report.append("=" * 70)
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append(f"Total Tests: {total}")
        report.append(f"Passed: {passed}")
        report.append(f"Failed: {failed}")
        report.append(f"Total Duration: {total_time:.2f}s")
        report.append("=" * 70)
        report.append("")

        # Group by status
        report.append("Test Results:")
        report.append("-" * 70)

        for result in cls.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            report.append(f"{status} [{result.duration:.2f}s] {result.name}")
            if result.message:
                report.append(f"         {result.message}")
            if not result.passed and result.details:
                report.append(f"         Details: {result.details}")
            report.append("")

        # Summary
        report.append("-" * 70)
        report.append("Summary:")
        report.append(f"  Success Rate: {passed/total*100:.1f}%")
        report.append(f"  Avg Duration: {total_time/total:.2f}s")
        report.append("")

        return "\n".join(report)


# ============================================================
# Pytest Hooks
# ============================================================

def pytest_sessionfinish(session, exitstatus):
    """Generate report after all tests."""
    if hasattr(session, 'testresult'):
        # Print report to stdout
        print("\n" + TestRAGSystem.generate_report())


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """Main entry point for running tests."""
    import sys

    # Run pytest with verbose output
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-s",  # Show print output
        "--color=yes"
    ])

    print("\n" + "=" * 70)
    print("Test execution completed")
    print("=" * 70)

    return exit_code


if __name__ == "__main__":
    main()
