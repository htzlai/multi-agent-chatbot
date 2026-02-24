#!/usr/bin/env python3
"""
RAG vs 非RAG 对比测试
=======================

使用与 test_domain_rag.py 相同的专业问题进行对比测试：
- A组: 使用RAG（知识库检索增强）
- B组: 不使用RAG（直接问模型）

帮助理解RAG的实际价值
"""

import requests
import json
import time
import sys
from datetime import datetime

BACKEND_URL = "http://localhost:8000"
TIMEOUT = 120

# 使用与 test_domain_rag.py 相同的问题 (精简版)
TEST_QUERIES = [
    # 公司注册 (ACRA)
    {
        "question": "新加坡私人有限公司注册需要哪些基本文件？",
        "domain": "公司注册",
        "key_points": ["身份证件", "注册地址", "公司章程", "秘书任命"]
    },
    {
        "question": "新加坡公司秘书的任职资格要求是什么？",
        "domain": "公司注册",
        "key_points": ["专业资质", "居住要求", "任命时间"]
    },
    # 税务 (IRAS)
    {
        "question": "新加坡公司所得税的标准税率是多少？",
        "domain": "税务",
        "key_points": ["17%标准税率", "免税额", "部分免税"]
    },
    # 就业准证 (EP/COMPASS)
    {
        "question": "COMPASS评估框架包含哪些评分维度？",
        "domain": "EP准证",
        "key_points": ["4项核心指标", "2项加成指标", "及格分数"]
    },
    # 数据保护 (PDPA)
    {
        "question": "新加坡PDPA规定的个人信息保护原则有哪些？",
        "domain": "数据保护",
        "key_points": ["通知原则", "选择原则", "访问原则", "更正原则"]
    },
]


def query_with_rag(question: str) -> dict:
    """使用RAG查询"""
    start = time.time()
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/test/rag",
            params={"query": question, "k": 5},
            timeout=TIMEOUT
        )
        data = response.json()
        duration = time.time() - start
        
        return {
            "success": True,
            "answer": data.get("answer", ""),
            "sources": data.get("sources", []),
            "duration": duration,
            "source_count": len(data.get("sources", []))
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def query_without_rag(question: str) -> dict:
    """不使用RAG，直接问模型"""
    start = time.time()
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/v1/chat/completions",
            json={
                "model": "gpt-oss-120b",
                "messages": [
                    {"role": "system", "content": "你是一位专业的新加坡企业服务顾问，专门帮助中国企业出海新加坡。请用中文详细回答关于新加坡公司注册、税务申报、就业准证、数据保护、境外投资、雇佣法规等领域的专业问题。回答要具体、准确，包含必要的数字和条款。"},
                    {"role": "user", "content": question}
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=TIMEOUT
        )
        data = response.json()
        duration = time.time() - start
        
        # 提取回答
        choices = data.get("choices", [])
        answer = choices[0].get("message", {}).get("content", "") if choices else ""
        
        return {
            "success": True,
            "answer": answer,
            "sources": [],  # 无来源
            "duration": duration,
            "source_count": 0
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_answer(answer: str, key_points: list, min_length: int = 100) -> dict:
    """分析回答质量"""
    
    if not answer:
        return {
            "length": 0,
            "has_structure": False,
            "key_coverage": 0,
            "quality_score": 0
        }
    
    # 长度
    length = len(answer)
    
    # 结构性
    structure_markers = ["1.", "2.", "3.", "•", "-", "：", "第一", "第二", "首先", "以下"]
    has_structure = any(marker in answer for marker in structure_markers)
    
    # 关键点覆盖率
    answer_lower = answer.lower()
    matched_points = [pt for pt in key_points if pt.lower() in answer_lower]
    key_coverage = len(matched_points) / max(1, len(key_points))
    
    # 评分
    length_score = min(1.0, length / 500) if length >= min_length else length / min_length * 0.5
    structure_score = 1.0 if has_structure else 0.5
    
    quality_score = (
        length_score * 0.25 + 
        structure_score * 0.25 + 
        key_coverage * 0.50
    )
    
    return {
        "length": length,
        "has_structure": has_structure,
        "matched_points": matched_points,
        "key_coverage": key_coverage,
        "quality_score": quality_score
    }


def main():
    print("\n" + "=" * 70)
    print("  🔬 RAG vs 非RAG 对比测试")
    print("  (使用与 test_domain_rag.py 相同的问题)")
    print("=" * 70)
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    
    for i, query_data in enumerate(TEST_QUERIES, 1):
        question = query_data["question"]
        domain = query_data["domain"]
        key_points = query_data["key_points"]
        
        print(f"\n{'─'*70}")
        print(f"  [{domain}] 问题 {i}: {question[:40]}...")
        print(f"{'─'*70}")
        
        # A组: 使用RAG
        print(f"\n  📚 [A组] 使用RAG...")
        rag_result = query_with_rag(question)
        
        if rag_result["success"]:
            rag_analysis = analyze_answer(rag_result["answer"], key_points)
            print(f"     ✅ 耗时: {rag_result['duration']:.1f}s")
            print(f"     📝 长度: {rag_analysis['length']} 字")
            print(f"     📊 关键点覆盖: {rag_analysis['key_coverage']:.0%}")
            print(f"     📚 来源数: {rag_result['source_count']}")
            if rag_analysis['matched_points']:
                print(f"     ✓ 已覆盖: {', '.join(rag_analysis['matched_points'][:3])}")
        else:
            print(f"     ❌ 错误: {rag_result['error']}")
            rag_analysis = {"quality_score": 0, "length": 0, "key_coverage": 0, "matched_points": []}
        
        # B组: 不使用RAG
        print(f"\n  🤖 [B组] 不使用RAG (直接问模型)...")
        no_rag_result = query_without_rag(question)
        
        if no_rag_result["success"]:
            no_rag_analysis = analyze_answer(no_rag_result["answer"], key_points)
            print(f"     ✅ 耗时: {no_rag_result['duration']:.1f}s")
            print(f"     📝 长度: {no_rag_analysis['length']} 字")
            print(f"     📊 关键点覆盖: {no_rag_analysis['key_coverage']:.0%}")
            if no_rag_analysis['matched_points']:
                print(f"     ✓ 已覆盖: {', '.join(no_rag_analysis['matched_points'][:3])}")
        else:
            print(f"     ❌ 错误: {no_rag_result['error']}")
            no_rag_analysis = {"quality_score": 0, "length": 0, "key_coverage": 0, "matched_points": []}
        
        # 对比
        if rag_result["success"] and no_rag_result["success"]:
            if rag_analysis["key_coverage"] > no_rag_analysis["key_coverage"]:
                winner = "A组 (RAG)"
            elif no_rag_analysis["key_coverage"] > rag_analysis["key_coverage"]:
                winner = "B组 (无RAG)"
            else:
                winner = "平手"
            
            diff = abs(rag_analysis["key_coverage"] - no_rag_analysis["key_coverage"])
            print(f"\n  🏆 关键点覆盖对比: {winner} (+{diff:.0%})")
        else:
            winner = "N/A"
        
        results.append({
            "question": question,
            "domain": domain,
            "key_points": key_points,
            "rag": rag_result,
            "no_rag": no_rag_result,
            "rag_analysis": rag_analysis,
            "no_rag_analysis": no_rag_analysis,
            "winner": winner
        })
    
    # 汇总报告
    print(f"\n\n{'='*70}")
    print("  📊 对比测试汇总报告")
    print("="*70)
    
    rag_wins = sum(1 for r in results if r["winner"] == "A组 (RAG)")
    no_rag_wins = sum(1 for r in results if r["winner"] == "B组 (无RAG)")
    ties = len(results) - rag_wins - no_rag_wins
    
    # 计算各维度平均值
    rag_avg_key_coverage = sum(r["rag_analysis"]["key_coverage"] for r in results) / len(results)
    no_rag_avg_key_coverage = sum(r["no_rag_analysis"]["key_coverage"] for r in results) / len(results)
    
    rag_avg_length = sum(r["rag_analysis"]["length"] for r in results) / len(results)
    no_rag_avg_length = sum(r["no_rag_analysis"]["length"] for r in results) / len(results)
    
    rag_avg_time = sum(r["rag"]["duration"] for r in results if r["rag"]["success"]) / len(results)
    no_rag_avg_time = sum(r["no_rag"]["duration"] for r in results if r["no_rag"]["success"]) / len(results)
    
    print(f"\n  📈 胜率统计 (按关键点覆盖):")
    print(f"     A组 (RAG) 胜出: {rag_wins}/{len(results)} ({rag_wins/len(results)*100:.0f}%)")
    print(f"     B组 (无RAG) 胜出: {no_rag_wins}/{len(results)} ({no_rag_wins/len(results)*100:.0f}%)")
    print(f"     平手: {ties}/{len(results)}")
    
    print(f"\n  📊 平均关键点覆盖率:")
    print(f"     A组 (RAG): {rag_avg_key_coverage:.1%}")
    print(f"     B组 (无RAG): {no_rag_avg_key_coverage:.1%}")
    
    print(f"\n  📊 平均回答长度:")
    print(f"     A组 (RAG): {rag_avg_length:.0f} 字")
    print(f"     B组 (无RAG): {no_rag_avg_length:.0f} 字")
    
    print(f"\n  ⏱️  平均响应时间:")
    print(f"     A组 (RAG): {rag_avg_time:.1f}s")
    print(f"     B组 (无RAG): {no_rag_avg_time:.1f}s")
    
    print(f"\n  💡 分析结论:")
    if rag_avg_key_coverage > no_rag_avg_key_coverage:
        diff = rag_avg_key_coverage - no_rag_avg_key_coverage
        print(f"     RAG提升了 {diff:.1%} 的关键信息覆盖率")
        print(f"     → 知识库检索对于专业领域问题有帮助")
        print(f"     → 优势: 答案来源于实际文档, 可追溯, 不易产生幻觉")
    elif no_rag_avg_key_coverage > rag_avg_key_coverage:
        diff = no_rag_avg_key_coverage - rag_avg_key_coverage
        print(f"     直接问模型覆盖率更高 {diff:.1%}")
        print(f"     → 模型训练数据可能已包含这些知识")
        print(f"     → 警告: 无来源验证, 可能有幻觉风险")
    else:
        print(f"     两者覆盖率相当")
    
    # 按领域分析
    print(f"\n  📂 分领域对比:")
    domains = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"rag": [], "no_rag": []}
        domains[d]["rag"].append(r["rag_analysis"]["key_coverage"])
        domains[d]["no_rag"].append(r["no_rag_analysis"]["key_coverage"])
    
    for domain, scores in domains.items():
        rag_avg = sum(scores["rag"]) / len(scores["rag"])
        no_rag_avg = sum(scores["no_rag"]) / len(scores["no_rag"])
        winner = "RAG" if rag_avg > no_rag_avg else "无RAG" if no_rag_avg > rag_avg else "="
        print(f"     {domain}: RAG={rag_avg:.0%} | 无RAG={no_rag_avg:.0%} → {winner}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
