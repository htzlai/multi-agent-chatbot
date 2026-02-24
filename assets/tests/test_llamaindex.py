#!/usr/bin/env python3
"""
RAG vs 非RAG 对比测试 - 使用 LlamaIndex 增强版接口
"""

import requests
import time

BACKEND_URL = "http://localhost:8000"

# 同样的问题
QUESTIONS = [
    ("q1", "税务", "新加坡公司所得税的标准税率是多少？", ["17%"]),
    ("q2", "EP准证", "COMPASS评估框架包含哪些评分维度？", ["4", "核心", "加成"]),
    ("q3", "公司注册", "新加坡私人有限公司注册需要哪些基本文件？", ["身份证", "注册地址", "章程", "秘书"]),
    ("q5", "ODI投资", "中国企业进行境外直接投资(ODI)需要办理哪些备案？", ["发改委", "商务部", "外汇"]),
    ("q8", "数据保护", "PDPC对违规企业罚款上限是多少？", ["100万", "10%"]),
]

def test_llamaindex(question):
    """使用 LlamaIndex 增强版接口"""
    r = requests.post(f"{BACKEND_URL}/rag/llamaindex/query", json={
        "query": question,
        "top_k": 5,
        "use_cache": False
    }, timeout=60)
    data = r.json()
    return data.get("answer", ""), len(data.get("sources", []))

def test_no_rag(question):
    """不使用RAG"""
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": question}],
        "max_tokens": 600,
        "temperature": 0.2
    }, timeout=60)
    data = r.json()
    return data["choices"][0]["message"]["content"] if data.get("choices") else ""

def score(ans, kw):
    if not ans: return 0, []
    m = [k for k in kw if k in ans]
    return len(m) / max(1, len(kw)), m

print("=" * 70)
print("  🔬 LlamaIndex增强版 RAG vs 非RAG 对比测试")
print("=" * 70)

results = []
for qid, domain, q, kw in QUESTIONS:
    print(f"\n[{qid}] {q[:30]}...")
    
    # LlamaIndex
    ans_idx, srcs = test_llamaindex(q)
    sc_idx, mt_idx = score(ans_idx, kw)
    
    # 无RAG
    ans_no = test_no_rag(q)
    sc_no, mt_no = score(ans_no, kw)
    
    winner = "LlamaIndex" if sc_idx > sc_no else "无RAG" if sc_no > sc_idx else "平手"
    results.append((qid, domain, sc_idx, sc_no, winner))
    
    print(f"    📚 LlamaIndex: {sc_idx:.0%} | 🤖 无RAG: {sc_no:.0%} | 胜:{winner}")

# 汇总
llama_wins = sum(1 for r in results if r[4] == "LlamaIndex")
no_rag_wins = sum(1 for r in results if r[4] == "无RAG")
avg_llama = sum(r[2] for r in results) / len(results)
avg_no = sum(r[3] for r in results) / len(results)

print(f"\n{'='*70}")
print(f"  📊 汇总 (使用LlamaIndex增强版)")
print(f"{'='*70}")
print(f"  LlamaIndex胜: {llama_wins}/5 ({llama_wins/5*100:.0f}%)")
print(f"  无RAG胜: {no_rag_wins}/5 ({no_rag_wins/5*100:.0f}%)")
print(f"  LlamaIndex平均: {avg_llama:.0%}")
print(f"  无RAG平均: {avg_no:.0%}")
print("=" * 70)
