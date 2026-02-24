#!/usr/bin/env python3
"""
RAG vs 非RAG 快速对比测试
"""

import requests
import time

BACKEND_URL = "http://localhost:8000"

# 精简问题
QUESTIONS = [
    ("新加坡公司所得税标准税率", ["17%", "17%标准税率"]),
    ("COMPASS评分维度", ["4项", "核心指标", "加成"]),
    ("PDPA保护原则", ["通知", "选择", "访问", "更正"]),
]

def test_rag(q):
    start = time.time()
    r = requests.get(f"{BACKEND_URL}/test/rag", params={"query": q, "k": 3}, timeout=60)
    data = r.json()
    duration = time.time() - start
    answer = data.get("answer", "")[:300]
    sources = len(data.get("sources", []))
    return duration, answer, sources

def test_no_rag(q):
    start = time.time()
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [{"role": "user", "content": q}],
        "max_tokens": 500
    }, timeout=60)
    data = r.json()
    duration = time.time() - start
    answer = data["choices"][0]["message"]["content"][:300] if data.get("choices") else ""
    return duration, answer

print("=" * 60)
print("  🔬 RAG vs 非RAG 快速对比")
print("=" * 60)

for q, keywords in QUESTIONS:
    print(f"\n📋 问题: {q}")
    
    # RAG
    t1, ans1, srcs = test_rag(q)
    matched = sum(1 for k in keywords if k in ans1)
    print(f"  📚 RAG: {t1:.1f}s | 来源:{srcs} | 关键点:{matched}/{len(keywords)}")
    
    # No RAG
    t2, ans2 = test_no_rag(q)
    matched2 = sum(1 for k in keywords if k in ans2)
    print(f"  🤖 无RAG: {t2:.1f}s | 关键点:{matched2}/{len(keywords)}")
    
    winner = "RAG" if matched > matched2 else "无RAG" if matched2 > matched else "="
    print(f"  🏆 胜者: {winner}")

print("\n" + "=" * 60)
