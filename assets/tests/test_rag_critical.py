#!/usr/bin/env python3
"""
RAG vs 非RAG 批判性验证测试
===========================

设计原则：
1. 展示实际答案内容，便于人工判断
2. 多维度评估（准确性、完整性、来源追溯）
3. 标注关键差异点

验证合理性：
- 关键词匹配是基础，但需要人工复核
- 不同问题有不同的"正确答案"
- 需要展示上下文便于判断质量
"""

import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

# 精选8个有代表性的问题
QUESTIONS = [
    {
        "id": "q1",
        "domain": "税务",
        "question": "新加坡公司所得税的标准税率是多少？",
        "expected": "17%",  # 正确答案的关键点
        "keywords": ["17%"],
        "why": "这是新加坡公司所得税的核心知识点"
    },
    {
        "id": "q2", 
        "domain": "EP准证",
        "question": "COMPASS评估框架包含哪些评分维度？",
        "expected": "6个维度:4个核心+2个加成",
        "keywords": ["4", "核心", "加成", "40"],
        "why": "这是EP准证申请的关键知识点，容易出错"
    },
    {
        "id": "q3",
        "domain": "公司注册", 
        "question": "新加坡私人有限公司注册需要哪些基本文件？",
        "expected": "身份证件、注册地址、公司章程、秘书任命",
        "keywords": ["身份证", "注册地址", "章程", "秘书"],
        "why": "这是公司注册的基础知识"
    },
    {
        "id": "q4",
        "domain": "数据保护",
        "question": "新加坡PDPA规定的个人信息保护原则有哪些？",
        "expected": "9-10项保护原则",
        "keywords": ["通知", "选择", "访问", "更正", "9", "10"],
        "why": "检查模型是否混淆概念"
    },
    {
        "id": "q5",
        "domain": "ODI投资",
        "question": "中国企业进行境外直接投资(ODI)需要办理哪些备案？",
        "expected": "发改委、商务部、外汇局",
        "keywords": ["发改委", "商务部", "外汇"],
        "why": "检查中国特色政策知识"
    },
    {
        "id": "q6",
        "domain": "雇佣法规",
        "question": "新加坡雇佣法令对工资支付有什么规定？",
        "expected": "支付周期、加班费、扣款限制",
        "keywords": ["7天", "支付周期", "加班费", "扣款"],
        "why": "检查劳动法知识"
    },
    {
        "id": "q7",
        "domain": "EP准证", 
        "question": "新加坡EP准证申请的基本薪资要求是多少？",
        "expected": "5000新元以上",
        "keywords": ["5000", "5000新元"],
        "why": "这是动态变化的标准"
    },
    {
        "id": "q8",
        "domain": "数据保护",
        "question": "PDPC对违规企业罚款上限是多少？",
        "expected": "100万新元或年营业额10%",
        "keywords": ["100万", "10%", "罚款"],
        "why": "检查具体数字准确性"
    },
]


def test_rag(question):
    """RAG查询"""
    r = requests.get(f"{BACKEND_URL}/test/rag", 
                    params={"query": question, "k": 5}, 
                    timeout=60)
    data = r.json()
    return {
        "answer": data.get("answer", ""),
        "sources": data.get("sources", [])
    }


def test_no_rag(question):
    """非RAG查询"""
    r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
        "model": "gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "你是一位专业、严谨的新加坡企业服务顾问。请基于准确的事实回答，不要猜测。"},
            {"role": "user", "content": question}
        ],
        "max_tokens": 800,
        "temperature": 0.2  # 降低随机性
    }, timeout=60)
    data = r.json()
    return {
        "answer": data["choices"][0]["message"]["content"] if data.get("choices") else "",
        "sources": []
    }


def check_keywords(answer, keywords):
    """检查关键词匹配"""
    if not answer:
        return 0, []
    found = [kw for kw in keywords if kw in answer]
    return len(found) / len(keywords), found


def main():
    print("=" * 80)
    print("  🔬 RAG vs 非RAG 批判性验证测试")
    print("  目的: 验证RAG在实际场景中的价值")
    print("=" * 80)
    
    results = []
    
    for q in QUESTIONS:
        print(f"\n{'='*80}")
        print(f"  [{q['id']}] {q['domain']} - {q['question']}")
        print(f"  预期关键点: {q['expected']}")
        print(f"  验证原因: {q['why']}")
        print(f"{'='*80}")
        
        # RAG测试
        print(f"\n📚 【RAG】答案:")
        print("-" * 60)
        rag_result = test_rag(q['question'])
        rag_answer = rag_result["answer"]
        rag_score, rag_found = check_keywords(rag_answer, q["keywords"])
        
        # 显示RAG答案（前500字）
        display_rag = rag_answer[:500] + "..." if len(rag_answer) > 500 else rag_answer
        print(display_rag)
        
        if rag_result["sources"]:
            print(f"\n  📎 来源文档: {len(rag_result['sources'])}个")
            for s in rag_result["sources"][:2]:
                src = s.get("source", s.get("file", "Unknown"))
                print(f"     - {src[:60]}")
        
        # 非RAG测试
        print(f"\n🤖 【无RAG】答案:")
        print("-" * 60)
        no_rag_result = test_no_rag(q["question"])
        no_rag_answer = no_rag_result["answer"]
        no_rag_score, no_rag_found = check_keywords(no_rag_answer, q["keywords"])
        
        # 显示无RAG答案（前500字）
        display_no_rag = no_rag_answer[:500] + "..." if len(no_rag_answer) > 500 else no_rag_answer
        print(display_no_rag)
        
        # 对比分析
        print(f"\n" + "=" * 60)
        print("  📊 对比分析:")
        print(f"     RAG关键词匹配: {rag_score:.0%} ({rag_found})")
        print(f"     无RAG关键词匹配: {no_rag_score:.0%} ({no_rag_found})")
        
        # 人工判断建议
        print(f"\n  💡 人工验证要点:")
        
        # 检查是否包含正确答案
        if q["expected"] in rag_answer:
            print(f"     ✅ RAG包含正确答案: '{q['expected']}'")
        else:
            print(f"     ⚠️ RAG可能遗漏正确答案")
            
        if q["expected"] in no_rag_answer:
            print(f"     ✅ 无RAG包含正确答案")
        else:
            print(f"     ⚠️ 无RAG可能遗漏正确答案")
        
        # 记录结果
        results.append({
            "id": q["id"],
            "domain": q["domain"],
            "question": q["question"],
            "expected": q["expected"],
            "rag_answer": rag_answer[:300],
            "no_rag_answer": no_rag_answer[:300],
            "rag_score": rag_score,
            "no_rag_score": no_rag_score,
            "rag_sources": len(rag_result["sources"]),
            "has_expected_rag": q["expected"] in rag_answer,
            "has_expected_no_rag": q["expected"] in no_rag_answer
        })
    
    # ========== 汇总 ==========
    print(f"\n\n{'='*80}")
    print("  📊 验证结果汇总")
    print("=" * 80)
    
    # 关键词匹配统计
    rag_wins = sum(1 for r in results if r["rag_score"] > r["no_rag_score"])
    no_rag_wins = sum(1 for r in results if r["no_rag_score"] > r["rag_score"])
    ties = len(results) - rag_wins - no_rag_wins
    
    # 正确答案包含统计
    rag_correct = sum(1 for r in results if r["has_expected_rag"])
    no_rag_correct = sum(1 for r in results if r["has_expected_no_rag"])
    
    print(f"\n  关键词匹配统计 (共{len(results)}题):")
    print(f"     RAG胜: {rag_wins} ({rag_wins/len(results)*100:.0f}%)")
    print(f"     无RAG胜: {no_rag_wins} ({no_rag_wins/len(results)*100:.0f}%)")
    print(f"     平手: {ties}")
    
    print(f"\n  正确答案包含统计:")
    print(f"     RAG包含正确答案: {rag_correct}/{len(results)} ({rag_correct/len(results)*100:.0f}%)")
    print(f"     无RAG包含正确答案: {no_rag_correct}/{len(results)} ({no_rag_correct/len(results)*100:.0f}%)")
    
    # 关键发现
    print(f"\n  🔍 关键发现:")
    
    # RAG好于无RAG的案例
    rag_better = [r for r in results if r["rag_score"] > r["no_rag_score"]]
    if rag_better:
        print(f"\n  RAG表现更好的问题 ({len(rag_better)}个):")
        for r in rag_better:
            print(f"     - {r['id']} {r['domain']}: {r['question'][:30]}...")
    
    # 无RAG好于RAG的案例
    no_rag_better = [r for r in results if r["no_rag_score"] > r["rag_score"]]
    if no_rag_better:
        print(f"\n  无RAG表现更好的问题 ({len(no_rag_better)}个):")
        for r in no_rag_better:
            print(f"     - {r['id']} {r['domain']}: {r['question'][:30]}...")
    
    # 错误案例分析
    print(f"\n  ⚠️ 需要关注的案例:")
    for r in results:
        if r["has_expected_rag"] and not r["has_expected_no_rag"]:
            print(f"     RAG正确但无RAG错误: {r['id']}")
        elif not r["has_expected_rag"] and r["has_expected_no_rag"]:
            print(f"     无RAG正确但RAG错误: {r['id']}")
        elif not r["has_expected_rag"] and not r["has_expected_no_rag"]:
            print(f"     ⚠️ 两者都错误: {r['id']} - {r['question'][:30]}")
    
    print("\n" + "=" * 80)
    
    # 测试验证合理性说明
    print("""
  📋 测试验证合理性说明:
  
  1. 为什么用关键词匹配?
     - 快速量化评估基础
     - 不能完全依赖，需要人工复核
     
  2. 为什么展示完整答案?
     - 关键词匹配可能有误判
     - 实际质量需要人工判断
     - 可发现潜在幻觉问题
     
  3. 为什么检查"expected"包含?
     - 验证是否包含核心知识点
     - 更直接的准确性判断
     
  4. 测试局限性:
     - 样本量小(8题)
     - 不同时间的模型输出可能有变化
     - 建议定期重新验证
    """)


if __name__ == "__main__":
    main()
