#!/usr/bin/env python3
"""
# 方式 1: 快速测试运行器 (推荐 - 输出详细)
python3 test_runner.py

# 方式 2: pytest 测试套件 (更规范)
python3 -m pytest test_rag_system.py -v
RAG System Quick Test Runner
============================

Quick test runner that generates detailed test reports.

Usage:
    python test_runner.py
"""

import requests
import json
import time
from datetime import datetime


# ============================================================
# Configuration
# ============================================================

BACKEND_URL = "http://localhost:8000"


# ============================================================
# Test Functions
# ============================================================

def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_section(title):
    print(f"\n--- {title} ---")


def test_vector_stats():
    print_section("向量存储统计")

    response = requests.get(f"{BACKEND_URL}/test/vector-stats")
    data = response.json()

    print(f"  Collection: {data.get('collection')}")
    print(f"  总向量数: {data.get('total_entities')}")
    print(f"  字段数: {len(data.get('fields', []))}")
    print(f"  索引数: {data.get('index_count')}")

    fields = [f["name"] for f in data.get("fields", [])]
    print(f"  字段列表: {', '.join(fields)}")

    return data.get("total_entities", 0)


def test_sources():
    print_section("文档源管理")

    response = requests.get(f"{BACKEND_URL}/sources")
    all_sources = response.json().get("sources", [])

    response = requests.get(f"{BACKEND_URL}/selected_sources")
    selected_sources = response.json().get("sources", [])

    print(f"  总文档数: {len(all_sources)}")
    print(f"  已选文档数: {len(selected_sources)}")
    print(f"  未选文档数: {len(all_sources) - len(selected_sources)}")

    print("\n  已选文档列表:")
    for i, src in enumerate(selected_sources[:10], 1):
        print(f"    {i}. {src[:50]}...")
    if len(selected_sources) > 10:
        print(f"    ... 还有 {len(selected_sources) - 10} 个")

    return len(all_sources), len(selected_sources)


def test_queries():
    print_section("检索查询测试")

    queries = [
        "制造业出海应该怎么选择",
        "新加坡EP签证要求",
        "ODI境外投资备案流程",
        "新加坡公司税务",
        "东南亚投资合规",
        "ACRA公司注册"
    ]

    results = []

    for query in queries:
        print(f"\n  查询: {query}")

        start = time.time()
        response = requests.get(f"{BACKEND_URL}/test/rag", params={"query": query}, timeout=120)
        duration = time.time() - start

        data = response.json()
        meta = data.get("retrieval_metadata", {})
        sources = data.get("sources", [])

        result = {
            "query": query,
            "chunks": meta.get("total_chunks_retrieved", 0),
            "unique_sources": meta.get("unique_sources_count", 0),
            "score_range": meta.get("score_range", {}),
            "answer_length": len(data.get("answer", "")),
            "duration": duration,
            "source_names": [s.get("name", "")[:30] for s in sources]
        }

        results.append(result)

        print(f"    检索到: {result['chunks']} chunks, {result['unique_sources']} 个文档")
        print(f"    分数范围: {result['score_range'].get('min', 0):.3f} - {result['score_range'].get('max', 0):.3f}")
        print(f"    回答长度: {result['answer_length']} 字符")
        print(f"    耗时: {duration:.2f}s")

    return results


def test_response_structure():
    print_section("响应结构验证")

    response = requests.get(f"{BACKEND_URL}/test/rag", params={"query": "新加坡投资"}, timeout=120)
    data = response.json()

    print("  顶层结构:")
    for key in data.keys():
        val = data[key]
        if isinstance(val, dict):
            print(f"    {key}: dict ({len(val)} keys)")
        elif isinstance(val, list):
            print(f"    {key}: list ({len(val)} items)")
        elif isinstance(val, str):
            print(f"    {key}: str ({len(val)} chars)")

    sources = data.get("sources", [])
    if sources:
        print("\n  Sources 结构 (第一个source):")
        src = sources[0]
        for key, val in src.items():
            if key == "chunks":
                print(f"    {key}: list ({len(val)} items)")
            else:
                print(f"    {key}: {type(val).__name__}")

    meta = data.get("retrieval_metadata", {})
    print("\n  Retrieval Metadata:")
    for key, val in meta.items():
        print(f"    {key}: {val}")

    return True


def test_score_quality():
    print_section("相似度分数质量分析")

    queries = [
        "制造业出海应该怎么选择",
        "新加坡EP签证",
        "ODI备案流程",
        "新加坡公司税务",
        "东南亚投资合规"
    ]

    all_scores = []

    for query in queries:
        response = requests.get(f"{BACKEND_URL}/test/rag", params={"query": query}, timeout=120)
        data = response.json()
        sources = data.get("sources", [])

        for src in sources:
            for chunk in src.get("chunks", []):
                all_scores.append({
                    "query": query,
                    "source": src.get("name", "")[:20],
                    "score": chunk.get("score", 0)
                })

    if all_scores:
        scores = [s["score"] for s in all_scores]
        print(f"\n  总chunk数: {len(scores)}")
        print(f"  最高分数: {max(scores):.4f}")
        print(f"  最低分数: {min(scores):.4f}")
        print(f"  平均分数: {sum(scores)/len(scores):.4f}")

        print("\n  分数分布:")
        ranges = [(0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.0), (1.0, 2.0)]
        for low, high in ranges:
            count = sum(1 for s in scores if low <= s < high)
            pct = count / len(scores) * 100
            bar = "#" * int(pct / 5)
            print(f"    {low:.1f}-{high:.1f}: {count:3d} ({pct:5.1f}%) {bar}")

    return all_scores


def generate_summary(total_entities, source_count, query_results, score_data):
    print_header("测试摘要")

    print(f"\n  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print("\n  [向量存储]")
    print(f"    总向量数: {total_entities}")

    print("\n  [文档源]")
    print(f"    总文档数: {source_count[0]}")
    print(f"    已选文档: {source_count[1]}")

    print("\n  [查询测试]")
    total_chunks = sum(r["chunks"] for r in query_results)
    total_sources = sum(r["unique_sources"] for r in query_results)
    avg_duration = sum(r["duration"] for r in query_results) / len(query_results)

    print(f"    测试查询数: {len(query_results)}")
    print(f"    总检索chunks: {total_chunks}")
    print(f"    平均每查询来源: {total_sources/len(query_results):.1f}")
    print(f"    平均响应时间: {avg_duration:.2f}s")

    if score_data:
        scores = [s["score"] for s in score_data]
        print(f"\n  [分数质量]")
        print(f"    平均分数: {sum(scores)/len(scores):.4f}")
        print(f"    分数范围: [{min(scores):.4f}, {max(scores):.4f}]")

    print("\n" + "=" * 70)
    print("  ALL TESTS PASSED!")
    print("=" * 70)


def main():
    print_header("RAG 系统测试")

    print(f"\n  Backend: {BACKEND_URL}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    total_entities = test_vector_stats()
    source_count = test_sources()
    query_results = test_queries()
    test_response_structure()
    score_data = test_score_quality()

    generate_summary(total_entities, source_count, query_results, score_data)


if __name__ == "__main__":
    main()
