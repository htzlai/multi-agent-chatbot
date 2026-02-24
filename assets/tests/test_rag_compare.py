#!/usr/bin/env python3
"""
RAG vs 非RAG 精简对比测试
"""

import requests
import time

BACKEND_URL = "http://localhost:8000"

# 精简到8个核心问题
QUESTIONS = [
    ("acra_001", "公司注册", "新加坡私人有限公司注册需要哪些基本文件？", ["身份证件", "注册地址", "公司章程", "秘书"]),
    ("tax_001", "税务", "新加坡公司所得税的标准税率是多少？", ["17%", "17%标准税率"]),
    ("tax_002", "税务", "什么是Form C-S？哪些公司可以使用简化申报？", ["500万", "简化", "收入"]),
    ("ep_002", "EP准证", "COMPASS评估框架包含哪些评分维度？", ["4项", "核心指标", "加成", "40分"]),
    ("pdpa_001", "数据保护", "新加坡PDPA规定的个人信息保护原则有哪些？", ["通知原则", "选择原则", "访问"]),
    ("odi_001", "ODI投资", "中国企业进行境外直接投资(ODI)需要办理哪些备案？", ["发改委", "商务部", "外汇"]),
    ("emp_001", "雇佣法规", "新加坡雇佣法令(EA)对工资支付有什么规定？", ["支付周期", "加班费", "7天"]),
    ("emp_002", "雇佣法规", "新加坡外籍员工工作准证有哪些类型？", ["EP", "SP", "WP"]),
]

def test_rag(q):
    r = requests.get(f"{BACKEND_URL}/test/rag", params={"query": q, "k": 5}, timeout=60)
    data = r.json()
    return data.get("answer", ""), len(data.get("sources", []))

def test_no_rag(q):
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": q}],
        "max_tokens": 600, "temperature": 0.3
    }, timeout=60)
    data = r.json()
    return data["choices"][0]["message"]["content"] if data.get("choices") else ""

def score(ans, kw):
    if not ans: return 0, []
    m = [k for k in kw if k in ans]
    return len(m) / max(1, len(kw)), m

print("=" * 70)
print("  🔬 RAG vs 非RAG 精简对比测试 (8题)")
print("=" * 70)

results = []
for qid, domain, q, kw in QUESTIONS:
    print(f"\n[{qid}] {q[:30]}...")
    
    ans_rag, srcs = test_rag(q)
    sc_rag, mt_rag = score(ans_rag, kw)
    
    ans_no = test_no_rag(q)
    sc_no, mt_no = score(ans_no, kw)
    
    winner = "RAG" if sc_rag > sc_no else "无RAG" if sc_no > sc_rag else "平手"
    results.append((qid, domain, sc_rag, sc_no, winner, srcs))
    
    print(f"    RAG: {sc_rag:.0%} | 无RAG: {sc_no:.0%} | 胜:{winner}")

# 汇总
rag_wins = sum(1 for r in results if r[4] == "RAG")
no_rag_wins = sum(1 for r in results if r[4] == "无RAG")
avg_rag = sum(r[2] for r in results) / len(results)
avg_no = sum(r[3] for r in results) / len(results)

print(f"\n{'='*70}")
print(f"  📊 汇总")
print(f"{'='*70}")
print(f"  RAG胜: {rag_wins}/8 ({rag_wins/8*100:.0f}%)")
print(f"  无RAG胜: {no_rag_wins}/8 ({no_rag_wins/8*100:.0f}%)")
print(f"  RAG平均覆盖率: {avg_rag:.0%}")
print(f"  无RAG平均覆盖率: {avg_no:.0%}")

# 分领域
print(f"\n  📂 分领域:")
domains = {}
for r in results:
    d = r[1]
    if d not in domains: domains[d] = []
    domains[d].append((r[2], r[3], r[4]))
for d, scores in domains.items():
    rag = sum(s[0] for s in scores) / len(scores)
    no = sum(s[1] for s in scores) / len(scores)
    wins = sum(1 for s in scores if s[2] == "RAG")
    print(f"    {d}: RAG {rag:.0%}({wins}) vs 无RAG {no:.0%}")
print("=" * 70)
