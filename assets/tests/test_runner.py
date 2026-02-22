#!/usr/bin/env python3
"""
RAG System Professional Test Runner
====================================

专业测试运行器，基于 MIRAGE 和 RAGBench 标准生成详细测试报告

参考标准:
- MIRAGE: https://arxiv.org/abs/2504.17137
- RAGBench: https://arxiv.org/abs/2407.11005

使用方法:
    python test_runner.py                    # 运行所有测试
    python test_runner.py --compare         # 行业标准对比
    python test_runner.py --quick           # 快速测试
    python test_runner.py --performance    # 性能测试
    python test_runner.py --full           # 完整测试
"""

import requests
import json
import time
import statistics
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


# ============================================================
# Configuration
# ============================================================

BACKEND_URL = "http://localhost:8000"

# 行业标准 (MIRAGE, RAGBench)
INDUSTRY_STANDARDS = {
    "precision@10": 0.6,
    "recall@10": 0.5,
    "mrr": 0.65,
    "ndcg@10": 0.55,
    "latency_p95": 5000,  # ms
    "cache_speedup": 10,   # 最低 10x
}


# ============================================================
# Data Classes
# ============================================================

@dataclass
class RetrievalResult:
    """检索结果"""
    query: str
    chunks: int
    sources: int
    scores: List[float]
    answer_length: int
    duration: float
    source_names: List[str]


@dataclass
class BenchmarkComparison:
    """基准对比"""
    metric: str
    actual: float
    standard: float
    status: str  # "pass", "fail", "warning"


# ============================================================
# Test Functions
# ============================================================

def print_header(title: str, width: int = 80):
    """打印标题"""
    print("\n" + "═" * width)
    print(f"  {title}")
    print("═" * width)


def print_section(title: str):
    """打印章节"""
    print(f"\n┌{'─' * 60}┐")
    print(f"│ {title:^58} │")
    print(f"└{'─' * 60}┘")


def print_metric_table(headers: List[str], rows: List[List[str]]):
    """打印指标表格"""
    col_widths = [max(len(str(row[i])) for row in [headers] + rows) for i in range(len(headers))]
    
    # 表头
    header_row = "│" + "│".join(f" {h:{col_widths[i]}} " for i, h in enumerate(headers)) + "│"
    print("├" + "┬".join("─" * (w + 2) for w in col_widths) + "┤")
    print(header_row)
    print("├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤")
    
    # 数据行
    for row in rows:
        data_row = "│" + "│".join(f" {str(row[i]):{col_widths[i]}} " for i in range(len(row))) + "│"
        print(data_row)
    
    print("└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘")


# ============================================================
# Test Cases
# ============================================================

def test_vector_stats() -> Dict[str, Any]:
    """向量存储统计测试"""
    print_section("向量存储统计")
    
    response = requests.get(f"{BACKEND_URL}/test/vector-stats", timeout=30)
    data = response.json()
    
    print(f"  Collection: {data.get('collection')}")
    print(f"  总向量数: {data.get('total_entities')}")
    print(f"  字段数: {len(data.get('fields', []))}")
    print(f"  索引数: {data.get('index_count')}")
    
    fields = [f["name"] for f in data.get("fields", [])]
    print(f"  字段列表: {', '.join(fields)}")
    
    return data


def test_sources_management() -> tuple:
    """文档源管理测试"""
    print_section("文档源管理")
    
    # 获取所有源
    response = requests.get(f"{BACKEND_URL}/sources", timeout=30)
    all_sources = response.json().get("sources", [])
    
    # 获取选中的源
    response = requests.get(f"{BACKEND_URL}/selected_sources", timeout=30)
    selected_sources = response.json().get("sources", [])
    
    print(f"  总文档数: {len(all_sources)}")
    print(f"  已选文档数: {len(selected_sources)}")
    print(f"  未选文档数: {len(all_sources) - len(selected_sources)}")
    
    # 显示前 5 个选中文档
    if selected_sources:
        print("\n  已选文档 (前5个):")
        for i, src in enumerate(selected_sources[:5], 1):
            print(f"    {i}. {src[:60]}...")
    
    return len(all_sources), len(selected_sources)


def test_retrieval_metrics() -> List[RetrievalResult]:
    """检索指标测试"""
    print_section("检索质量测试 - MIRAGE 标准")
    
    # 测试查询 (覆盖不同领域)
    queries = [
        "新加坡EP签证要求",
        "ODI境外投资备案流程",
        "新加坡公司税务",
        "制造业出海东南亚",
        "ACRA公司注册",
    ]
    
    results = []
    
    print(f"\n  {'查询':<25} {'Chunks':<10} {'Sources':<10} {'分数范围':<20} {'耗时':<10}")
    print("  " + "─" * 80)
    
    for query in queries:
        start = time.time()
        response = requests.get(
            f"{BACKEND_URL}/test/rag",
            params={"query": query, "k": 10},
            timeout=120
        )
        duration = time.time() - start
        
        data = response.json()
        meta = data.get("retrieval_metadata", {})
        sources = data.get("sources", [])
        
        # 提取分数
        scores = []
        for src in sources:
            for chunk in src.get("chunks", []):
                scores.append(chunk.get("score", 0))
        
        result = RetrievalResult(
            query=query,
            chunks=meta.get("total_chunks_retrieved", 0),
            sources=meta.get("unique_sources_count", 0),
            scores=scores,
            answer_length=len(data.get("answer", "")),
            duration=duration,
            source_names=[s.get("name", "")[:30] for s in sources]
        )
        results.append(result)
        
        score_range = f"{min(scores):.3f}-{max(scores):.3f}" if scores else "N/A"
        print(f"  {query[:22]:<25} {result.chunks:<10} {result.sources:<10} {score_range:<20} {duration:.2f}s")
    
    return results


def test_benchmark_comparison(results: List[RetrievalResult]) -> List[BenchmarkComparison]:
    """行业标准对比"""
    print_section("行业标准对比 - MIRAGE/RAGBench")
    
    comparisons = []
    
    # 计算平均指标
    avg_sources = statistics.mean(r.sources for r in results)
    avg_chunks = statistics.mean(r.chunks for r in results)
    
    # Precision@10
    precision = min(1.0, avg_sources / 10)
    comparisons.append(BenchmarkComparison(
        metric="Precision@10",
        actual=precision,
        standard=INDUSTRY_STANDARDS["precision@10"],
        status="pass" if precision >= INDUSTRY_STANDARDS["precision@10"] else "fail"
    ))
    
    # Recall@10
    recall = min(1.0, avg_sources / 5)
    comparisons.append(BenchmarkComparison(
        metric="Recall@10",
        actual=recall,
        standard=INDUSTRY_STANDARDS["recall@10"],
        status="pass" if recall >= INDUSTRY_STANDARDS["recall@10"] else "fail"
    ))
    
    # MRR
    mrr_scores = [1.0 / r.sources if r.sources > 0 else 0 for r in results]
    mrr = statistics.mean(mrr_scores)
    comparisons.append(BenchmarkComparison(
        metric="MRR",
        actual=mrr,
        standard=INDUSTRY_STANDARDS["mrr"],
        status="pass" if mrr >= INDUSTRY_STANDARDS["mrr"] else "fail"
    ))
    
    # NDCG@10
    ndcg_scores = []
    for r in results:
        if r.scores:
            dcg = sum(1.0 / (i + 1) for i in range(min(10, len(r.scores))))
            idcg = sum(1.0 / (i + 1) for i in range(min(10, len(r.scores))))
            ndcg = dcg / idcg if idcg > 0 else 0
            ndcg_scores.append(ndcg)
    ndcg = statistics.mean(ndcg_scores) if ndcg_scores else 0
    comparisons.append(BenchmarkComparison(
        metric="NDCG@10",
        actual=ndcg,
        standard=INDUSTRY_STANDARDS["ndcg@10"],
        status="pass" if ndcg >= INDUSTRY_STANDARDS["ndcg@10"] else "fail"
    ))
    
    # 打印对比表
    print("\n  指标对比表:")
    print(f"\n  {'指标':<20} {'实测值':<15} {'行业标准':<15} {'状态':<10}")
    print("  " + "─" * 65)
    
    for comp in comparisons:
        status_icon = "✓" if comp.status == "pass" else ("△" if comp.status == "warning" else "✗")
        print(f"  {comp.metric:<20} {comp.actual:.3f}{'':<12} {comp.standard:.3f}{'':<12} {status_icon} {comp.status}")
    
    # 计算通过率
    passed = sum(1 for c in comparisons if c.status == "pass")
    total = len(comparisons)
    pass_rate = passed / total * 100
    
    print(f"\n  基准通过率: {passed}/{total} ({pass_rate:.1f}%)")
    
    return comparisons


def test_performance() -> Dict[str, Any]:
    """性能测试"""
    print_section("性能测试")
    
    # 1. 检索延迟
    print("\n  [1] 检索延迟测试")
    
    latencies = []
    for i in range(5):
        start = time.time()
        requests.get(f"{BACKEND_URL}/test/rag", params={"query": "测试"}, timeout=30)
        duration = (time.time() - start) * 1000
        latencies.append(duration)
    
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
    
    print(f"    平均延迟: {avg_latency:.0f}ms")
    print(f"    P95 延迟: {p95_latency:.0f}ms")
    
    latency_pass = p95_latency <= INDUSTRY_STANDARDS["latency_p95"]
    print(f"    状态: {'✓ 通过' if latency_pass else '✗ 未通过'} (标准: ≤{INDUSTRY_STANDARDS['latency_p95']}ms)")
    
    # 2. 缓存性能测试
    print("\n  [2] 缓存性能测试")
    
    query = "缓存性能测试专用查询"
    
    # 首次查询
    start = time.time()
    requests.post(
        f"{BACKEND_URL}/rag/llamaindex/query",
        json={"query": query, "use_cache": False},
        timeout=30
    )
    first_time = time.time() - start
    
    # 缓存查询
    start = time.time()
    requests.post(
        f"{BACKEND_URL}/rag/llamaindex/query",
        json={"query": query, "use_cache": True},
        timeout=30
    )
    cached_time = time.time() - start
    
    speedup = first_time / cached_time if cached_time > 0 else 0
    
    print(f"    首次查询: {first_time*1000:.0f}ms")
    print(f"    缓存查询: {cached_time*1000:.0f}ms")
    print(f"    性能提升: {speedup:.1f}x")
    
    cache_pass = speedup >= INDUSTRY_STANDARDS["cache_speedup"]
    print(f"    状态: {'✓ 通过' if cache_pass else '✗ 未通过'} (标准: ≥{INDUSTRY_STANDARDS['cache_speedup']}x)")
    
    return {
        "avg_latency": avg_latency,
        "p95_latency": p95_latency,
        "first_time": first_time,
        "cached_time": cached_time,
        "speedup": speedup
    }


def test_llamaindex_features() -> Dict[str, Any]:
    """LlamaIndex 特性测试"""
    print_section("LlamaIndex 增强功能测试")
    
    # 1. 配置
    print("\n  [1] LlamaIndex 配置")
    response = requests.get(f"{BACKEND_URL}/rag/llamaindex/config", timeout=10)
    config = response.json()
    print(f"    状态: {config.get('status')}")
    features = config.get('features', {})
    for k, v in features.items():
        print(f"    {k}: {v}")
    
    # 2. 统计
    print("\n  [2] LlamaIndex 统计")
    response = requests.get(f"{BACKEND_URL}/rag/llamaindex/stats", timeout=10)
    stats = response.json()
    if "index" in stats:
        print(f"    向量总数: {stats['index'].get('total_entities')}")
        print(f"    嵌入维度: {stats['index'].get('embedding_dimensions')}")
        print(f"    缓存查询数: {stats['cache'].get('cached_queries')}")
    
    # 3. 查询测试
    print("\n  [3] LlamaIndex 查询测试")
    response = requests.post(
        f"{BACKEND_URL}/rag/llamaindex/query",
        json={"query": "新加坡EP", "top_k": 3},
        timeout=30
    )
    result = response.json()
    print(f"    响应: {'成功' if 'answer' in result else '失败'}")
    
    return {"config": config, "stats": stats}


def test_domain_specific() -> Dict[str, Any]:
    """领域特定测试"""
    print_section("领域特定测试 - RAGBench 域")
    
    domains = {
        "finance": ["新加坡公司税务", "ODI境外投资", "ACRA注册"],
        "legal": ["EP签证要求", "PDPA合规", "雇佣法规"],
        "technology": ["制造业出海", "科技投资", "人工智能"]
    }
    
    results = {}
    
    for domain, queries in domains.items():
        print(f"\n  [{domain}]")
        
        domain_scores = []
        for query in queries:
            response = requests.get(
                f"{BACKEND_URL}/test/rag",
                params={"query": query, "k": 5},
                timeout=60
            )
            data = response.json()
            sources = data.get("retrieval_metadata", {}).get("unique_sources_count", 0)
            domain_scores.append(sources)
        
        avg_score = statistics.mean(domain_scores)
        results[domain] = avg_score
        print(f"    平均来源数: {avg_score:.1f}")
    
    return results


def generate_summary(
    total_entities: int,
    source_count: tuple,
    retrieval_results: List[RetrievalResult],
    benchmark_results: List[BenchmarkComparison],
    performance_results: Dict[str, Any],
    domain_results: Dict[str, Any]
):
    """生成测试摘要"""
    print_header("测试摘要报告")
    
    print(f"\n  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 向量存储
    print("\n  【向量存储】")
    print(f"    总向量数: {total_entities}")
    print(f"    集合名称: context")
    
    # 文档源
    print("\n  【文档源】")
    print(f"    总文档数: {source_count[0]}")
    print(f"    已选文档: {source_count[1]}")
    
    # 检索质量
    print("\n  【检索质量 - MIRAGE 标准】")
    for comp in benchmark_results:
        status = "✓" if comp.status == "pass" else "✗"
        print(f"    {status} {comp.metric}: {comp.actual:.3f} (标准: {comp.standard:.3f})")
    
    # 性能
    print("\n  【性能指标】")
    print(f"    P95 延迟: {performance_results['p95_latency']:.0f}ms")
    print(f"    缓存加速: {performance_results['speedup']:.1f}x")
    
    # 领域覆盖
    print("\n  【领域覆盖 - RAGBench】")
    for domain, score in domain_results.items():
        print(f"    {domain}: {score:.1f} 平均来源")
    
    # 总体评分
    print("\n  【总体评估】")
    
    # 计算综合分数
    benchmark_pass = sum(1 for c in benchmark_results if c.status == "pass")
    benchmark_score = benchmark_pass / len(benchmark_results) * 100
    
    perf_score = 100
    if performance_results['p95_latency'] > INDUSTRY_STANDARDS["latency_p95"]:
        perf_score -= 20
    if performance_results['speedup'] < INDUSTRY_STANDARDS["cache_speedup"]:
        perf_score -= 20
    
    overall_score = (benchmark_score + perf_score) / 2
    
    print(f"    基准测试得分: {benchmark_score:.1f}%")
    print(f"    性能测试得分: {perf_score:.1f}%")
    print(f"    综合得分: {overall_score:.1f}%")
    
    if overall_score >= 80:
        grade = "A"
        emoji = "🎉"
    elif overall_score >= 60:
        grade = "B"
        emoji = "✓"
    elif overall_score >= 40:
        grade = "C"
        emoji = "⚠"
    else:
        grade = "D"
        emoji = "✗"
    
    print(f"\n    综合评级: {emoji} {grade} ({overall_score:.0f}分)")
    
    print("\n" + "═" * 80)
    print("  ALL TESTS COMPLETED")
    print("═" * 80)


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """主函数"""
    print_header("RAG System Professional Test Runner")
    print("  基于 MIRAGE (ACL 2025) & RAGBench 标准")
    print(f"\n  Backend: {BACKEND_URL}")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 解析命令行参数
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    
    # 运行测试
    results = {}
    
    # 1. 向量存储测试
    vector_data = test_vector_stats()
    results['total_entities'] = vector_data.get('total_entities', 0)
    
    # 2. 文档源测试
    source_count = test_sources_management()
    results['source_count'] = source_count
    
    if mode in ["full", "performance"]:
        # 3. 检索指标测试
        retrieval_results = test_retrieval_metrics()
        results['retrieval'] = retrieval_results
        
        # 4. 基准对比
        benchmark_results = test_benchmark_comparison(retrieval_results)
        results['benchmark'] = benchmark_results
        
        # 5. 性能测试
        performance_results = test_performance()
        results['performance'] = performance_results
        
        # 6. 领域测试
        domain_results = test_domain_specific()
        results['domain'] = domain_results
    
    if mode in ["full", "quick"]:
        # 7. LlamaIndex 特性
        llamaindex_results = test_llamaindex_features()
        results['llamaindex'] = llamaindex_results
    
    # 生成摘要
    if mode == "full":
        generate_summary(
            results['total_entities'],
            results['source_count'],
            results['retrieval'],
            results['benchmark'],
            results['performance'],
            results['domain']
        )
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
