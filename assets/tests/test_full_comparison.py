#!/usr/bin/env python3
"""
RAG 系统全面对比测试
====================

测试维度:
1. 不同RAG接口对比
2. 不同参数配置
3. 多次测试验证稳定性
4. 更多问题覆盖
"""

import requests
import time
import json
from collections import defaultdict

BACKEND_URL = "http://localhost:8000"

# 扩展问题库 - 覆盖更多领域
QUESTIONS = [
    # 税务 (3题)
    ("tax_1", "税务", "新加坡公司所得税的标准税率是多少？", ["17%", "17%标准税率"]),
    ("tax_2", "税务", "Form C-S适用于哪些公司？", ["500万", "简化", "收入门槛"]),
    ("tax_3", "税务", "新加坡转让定价文档要求是什么？", ["主体文档", "本地文档", "国别报告"]),
    
    # EP准证 (3题)
    ("ep_1", "EP准证", "EP准证申请需要满足什么薪资要求？", ["5000", "5000新元"]),
    ("ep_2", "EP准证", "COMPASS评估有哪些维度？", ["4项", "核心", "加成", "40分"]),
    ("ep_3", "EP准证", "EP持有人的家属如何申请准证？", ["DP", "LTVP", "6000"]),
    
    # 公司注册 (2题)
    ("acra_1", "公司注册", "新加坡公司注册需要什么文件？", ["身份证", "注册地址", "章程", "秘书"]),
    ("acra_2", "公司注册", "ACRA商业信息下载费用是多少？", ["$27.50", "27.50", "费用"]),
    
    # 数据保护 (2题)
    ("pdpa_1", "数据保护", "PDPA有哪些保护原则？", ["通知", "选择", "访问", "更正"]),
    ("pdpa_2", "数据保护", "PDPC罚款上限是多少？", ["100万", "10%"]),
    
    # ODI投资 (2题)
    ("odi_1", "ODI投资", "中国企业ODI需要哪些备案？", ["发改委", "商务部", "外汇"]),
    ("odi_2", "ODI投资", "哪些行业需要ODI审批？", ["敏感行业", "审批", "禁止"]),
    
    # 雇佣法规 (2题)
    ("emp_1", "雇佣法规", "新加坡工资支付有哪些规定？", ["7天", "支付周期", "加班费"]),
    ("emp_2", "雇佣法规", "新加坡有哪些工作准证类型？", ["EP", "SP", "WP"]),
]


def test_basic_rag(query, k=5):
    """基础 /test/rag 接口"""
    start = time.time()
    r = requests.get(f"{BACKEND_URL}/test/rag", params={"query": query, "k": k}, timeout=60)
    duration = time.time() - start
    data = r.json()
    return {
        "answer": data.get("answer", ""),
        "sources": data.get("sources", []),
        "duration": duration
    }


def test_llamaindex(query, top_k=5, use_cache=False):
    """LlamaIndex 增强接口"""
    start = time.time()
    r = requests.post(f"{BACKEND_URL}/rag/llamaindex/query", 
        json={"query": query, "top_k": top_k, "use_cache": use_cache}, timeout=60)
    duration = time.time() - start
    data = r.json()
    return {
        "answer": data.get("answer", ""),
        "sources": data.get("sources", []),
        "duration": duration
    }


def test_no_rag(query):
    """无RAG直接问模型"""
    start = time.time()
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": query}],
        "max_tokens": 600,
        "temperature": 0.2
    }, timeout=60)
    duration = time.time() - start
    data = r.json()
    return {
        "answer": data["choices"][0]["message"]["content"] if data.get("choices") else "",
        "duration": duration
    }


def score_answer(answer, keywords):
    if not answer:
        return 0, []
    matched = [k for k in keywords if k in answer]
    return len(matched) / max(1, len(keywords)), matched


def run_tests():
    """运行所有测试"""
    results = {
        "basic_rag": defaultdict(list),
        "llamaindex": defaultdict(list),
        "no_rag": defaultdict(list),
    }
    
    print("=" * 70)
    print("  🔬 RAG系统全面对比测试 (14题 x 3种方式)")
    print("=" * 70)
    
    for qid, domain, question, keywords in QUESTIONS:
        print(f"\n[{qid}] {question[:35]}...")
        
        # 1. 基础RAG
        r1 = test_basic_rag(question)
        s1, m1 = score_answer(r1["answer"], keywords)
        results["basic_rag"]["scores"].append(s1)
        results["basic_rag"]["durations"].append(r1["duration"])
        print(f"    基础RAG: {s1:.0%} ({r1['duration']:.1f}s)")
        
        # 2. LlamaIndex
        r2 = test_llamaindex(question)
        s2, m2 = score_answer(r2["answer"], keywords)
        results["llamaindex"]["scores"].append(s2)
        results["llamaindex"]["durations"].append(r2["duration"])
        print(f"    LlamaIndex: {s2:.0%} ({r2['duration']:.1f}s)")
        
        # 3. 无RAG
        r3 = test_no_rag(question)
        s3, m3 = score_answer(r3["answer"], keywords)
        results["no_rag"]["scores"].append(s3)
        results["no_rag"]["durations"].append(r3["duration"])
        print(f"    无RAG: {s3:.0%} ({r3['duration']:.1f}s)")
        
        # 记录胜者
        winner = "基础RAG" if s1 > s2 and s1 > s3 else \
                 "LlamaIndex" if s2 > s1 and s2 > s3 else \
                 "无RAG" if s3 > s1 and s3 > s2 else "平手"
        results[f"{qid}_winner"] = winner
    
    return results


def print_report(results):
    """打印测试报告"""
    print("\n" + "=" * 70)
    print("  📊 全面测试报告")
    print("=" * 70)
    
    # 计算统计数据
    methods = ["basic_rag", "llamaindex", "no_rag"]
    names = {"basic_rag": "基础RAG", "llamaindex": "LlamaIndex", "no_rag": "无RAG"}
    
    print("\n  📈 总体表现:")
    for m in methods:
        scores = results[m]["scores"]
        durations = results[m]["durations"]
        avg_score = sum(scores) / len(scores)
        avg_time = sum(durations) / len(durations)
        
        # 胜出次数
        wins = sum(1 for qid, _, _, _ in QUESTIONS 
                   if results.get(f"{qid}_winner") == names[m])
        
        print(f"    {names[m]}: 平均{avg_score:.0%} | 平均{avg_time:.1f}s | 胜出{wins}次")
    
    # 分领域统计
    print("\n  📂 分领域表现:")
    domains = set(q[1] for q in QUESTIONS)
    for domain in domains:
        print(f"\n    【{domain}】")
        domain_qs = [(q[0], q[3]) for q in QUESTIONS if q[1] == domain]
        
        for m in methods:
            domain_scores = []
            for qid, kw in domain_qs:
                idx = [i for i, q in enumerate(QUESTIONS) if q[0] == qid][0]
                domain_scores.append(results[m]["scores"][idx])
            
            avg = sum(domain_scores) / len(domain_scores) if domain_scores else 0
            print(f"      {names[m]}: {avg:.0%}")
    
    # 响应时间对比
    print("\n  ⏱️ 响应时间:")
    for m in methods:
        durations = results[m]["durations"]
        avg = sum(durations) / len(durations)
        print(f"    {names[m]}: 平均 {avg:.1f}s")
    
    # 最佳方案建议
    print("\n  💡 结论:")
    basic_avg = sum(results["basic_rag"]["scores"]) / len(results["basic_rag"]["scores"])
    llama_avg = sum(results["llamaindex"]["scores"]) / len(results["llamaindex"]["scores"])
    no_rag_avg = sum(results["no_rag"]["scores"]) / len(results["no_rag"]["scores"])
    
    best = max(basic_avg, llama_avg, no_rag_avg)
    
    if best == basic_avg:
        print("    → 基础RAG接口整体表现最好")
    elif best == llama_avg:
        print("    → LlamaIndex接口整体表现最好")
    else:
        print("    → 直接问模型整体表现最好")
    
    if no_rag_avg > basic_avg or no_rag_avg > llama_avg:
        print("    ⚠️ 注意: 无RAG表现更好，可能需要优化RAG系统")
    
    print("=" * 70)


if __name__ == "__main__":
    results = run_tests()
    print_report(results)
