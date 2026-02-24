#!/usr/bin/env python3
"""
RAG vs 非RAG 详细对比测试
显示完整答案，便于人工对比
"""

import requests
import time

BACKEND_URL = "http://localhost:8000"

QUESTIONS = [
    "新加坡公司所得税的标准税率是多少？",
    "COMPASS评估框架包含哪些评分维度？",
    "新加坡PDPA规定的个人信息保护原则有哪些？",
]

def test_rag(q):
    r = requests.get(f"{BACKEND_URL}/test/rag", params={"query": q, "k": 5}, timeout=120)
    data = r.json()
    return data.get("answer", ""), data.get("sources", [])

def test_no_rag(q):
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "你是一位专业的新加坡企业服务顾问。请用中文详细回答。"},
            {"role": "user", "content": q}
        ],
        "max_tokens": 1000
    }, timeout=120)
    data = r.json()
    return data["choices"][0]["message"]["content"] if data.get("choices") else ""

print("=" * 70)
print("  🔬 RAG vs 非RAG 详细答案对比")
print("=" * 70)

for i, q in enumerate(QUESTIONS, 1):
    print(f"\n{'='*70}")
    print(f"  问题 {i}: {q}")
    print(f"{'='*70}")
    
    # RAG
    print(f"\n📚 【A组】使用RAG:")
    print("-" * 50)
    ans_rag, sources = test_rag(q)
    print(ans_rag[:1500])
    if ans_rag:
        print(f"\n  来源文档数: {len(sources)}")
        for s in sources[:3]:
            print(f"    - {s.get('source', s.get('file', 'Unknown'))[:50]}")
    
    # No RAG
    print(f"\n🤖 【B组】不使用RAG (直接问模型):")
    print("-" * 50)
    ans_no_rag = test_no_rag(q)
    print(ans_no_rag[:1500])
    
    print(f"\n{'='*70}")

print("\n✅ 对比完成!")
