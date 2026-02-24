#!/usr/bin/env python3
"""
RAG vs 非RAG 全面对比测试
=========================

使用 test_domain_rag.py 中的所有专业问题进行对比测试
"""

import requests
import time

BACKEND_URL = "http://localhost:8000"

# 使用 test_domain_rag.py 中的所有问题
QUESTIONS = [
    # 公司注册 (ACRA)
    ("acra_001", "公司注册", "新加坡私人有限公司注册需要哪些基本文件？", ["身份证件", "注册地址", "公司章程", "秘书"]),
    ("acra_002", "公司注册", "新加坡公司秘书的任职资格要求是什么？", ["专业资质", "居住要求", "任命时间"]),
    ("acra_003", "公司注册", "ACRA商业信息下载服务需要支付多少费用？", ["费用", "价格", "$27.50", "免费"]),
    ("acra_004", "公司注册", "新加坡公司注册后必须保存哪些法定记录？", ["会计记录", "会议记录", "7年"]),
    
    # 税务 (IRAS)
    ("tax_001", "税务", "新加坡公司所得税的标准税率是多少？", ["17%", "17%标准税率"]),
    ("tax_002", "税务", "什么是Form C-S？哪些公司可以使用简化申报？", ["500万", "简化", "收入门槛"]),
    ("tax_003", "税务", "新加坡转让定价文档要求有哪些？", ["主体文档", "本地文档", "国别报告"]),
    ("tax_004", "税务", "新加坡股息收入是否需要缴纳所得税？", ["参股豁免", "免税", "10%"]),
    
    # 就业准证 (EP/COMPASS)
    ("ep_001", "EP准证", "新加坡EP准证申请的基本薪资要求是多少？", ["5000", "最低薪资", "金融"]),
    ("ep_002", "EP准证", "COMPASS评估框架包含哪些评分维度？", ["4项", "核心指标", "加成", "40分"]),
    ("ep_003", "EP准证", "哪些职业可以通过COMPASS获得加分？", ["紧缺职业", "技能加分", "战略业务"]),
    ("ep_004", "EP准证", "EP准证持有人的家属是否可以留在新加坡？", ["DP", "LTVP", "6000"]),
    
    # 数据保护 (PDPA)
    ("pdpa_001", "数据保护", "新加坡PDPA规定的个人信息保护原则有哪些？", ["通知原则", "选择原则", "访问原则"]),
    ("pdpa_002", "数据保护", "企业需要任命数据保护官(DPO)吗？要求是什么？", ["DPO", "强制性", "任命"]),
    ("pdpa_003", "数据保护", "跨境数据传输需要满足什么条件？", ["充分性", "BCR", "合同"]),
    ("pdpa_004", "数据保护", "PDPC可以对违规企业处以多高的罚款？", ["100万", "10%", "罚款上限"]),
    
    # ODI境外投资
    ("odi_001", "ODI投资", "中国企业进行境外直接投资(ODI)需要办理哪些备案？", ["发改委", "商务部", "外汇"]),
    ("odi_002", "ODI投资", "哪些类型的境外投资需要进行ODI备案？", ["敏感行业", "敏感国家", "审批"]),
    ("odi_003", "ODI投资", "新加坡对跨境资金管理有哪些便利政策？", ["外汇自由", "税收优惠", "资金池"]),
    
    # 雇佣法规
    ("emp_001", "雇佣法规", "新加坡雇佣法令(EA)对工资支付有什么规定？", ["支付周期", "加班费", "7天"]),
    ("emp_002", "雇佣法规", "新加坡外籍员工工作准证有哪些类型？", ["EP", "SP", "WP"]),
    ("emp_003", "雇佣法规", "雇主需要为员工缴纳哪些强制性公积金(CPF)？", ["17%", "20%", "雇主"]),
]

def test_rag(q):
    start = time.time()
    try:
        r = requests.get(f"{BACKEND_URL}/test/rag", params={"query": q, "k": 5}, timeout=60)
        data = r.json()
        duration = time.time() - start
        answer = data.get("answer", "")
        sources = data.get("sources", [])
        return duration, answer, len(sources), None
    except Exception as e:
        return time.time() - start, "", 0, str(e)

def test_no_rag(q):
    start = time.time()
    try:
        r = requests.post(f"{BACKEND_URL}/v1/chat/completions", json={
            "model": "gpt-oss-120b",
            "messages": [
                {"role": "system", "content": "你是一位专业的新加坡企业服务顾问。请用中文准确回答，包含具体数字。"},
                {"role": "user", "content": q}
            ],
            "max_tokens": 800,
            "temperature": 0.3
        }, timeout=60)
        data = r.json()
        duration = time.time() - start
        answer = data["choices"][0]["message"]["content"] if data.get("choices") else ""
        return duration, answer, None
    except Exception as e:
        return time.time() - start, "", str(e)

def score_answer(answer, keywords):
    """评分：关键词覆盖率"""
    if not answer:
        return 0, []
    answer_lower = answer.lower()
    matched = [k for k in keywords if k.lower() in answer_lower]
    return len(matched) / max(1, len(keywords)), matched

def main():
    print("\n" + "=" * 70)
    print("  🔬 RAG vs 非RAG 全面对比测试")
    print("  使用 test_domain_rag.py 中的全部22个问题")
    print("=" * 70)
    
    results = []
    
    for qid, domain, question, keywords in QUESTIONS:
        print(f"\n[{qid}] {question[:35]}...")
        
        # RAG测试
        t1, ans_rag, srcs, err1 = test_rag(question)
        score_rag, matched_rag = score_answer(ans_rag, keywords)
        
        # 无RAG测试
        t2, ans_no_rag, err2 = test_no_rag(question)
        score_no_rag, matched_no_rag = score_answer(ans_no_rag, keywords)
        
        # 记录结果
        winner = "RAG" if score_rag > score_no_rag else "无RAG" if score_no_rag > score_rag else "平手"
        
        results.append({
            "qid": qid,
            "domain": domain,
            "question": question,
            "score_rag": score_rag,
            "score_no_rag": score_no_rag,
            "winner": winner,
            "matched_rag": matched_rag,
            "matched_no_rag": matched_no_rag,
            "time_rag": t1,
            "time_no_rag": t2,
            "sources": srcs
        })
        
        # 显示结果
        r = "✅" if score_rag > 0 else "⚠️"
        n = "✅" if score_no_rag > 0 else "⚠️"
        print(f"    📚 RAG: {r} {score_rag:.0%} ({t1:.1f}s) | {srcs}来源")
        print(f"    🤖 无RAG: {n} {score_no_rag:.0%} ({t2:.1f}s)")
        print(f"    🏆 胜: {winner}")
    
    # ========== 汇总报告 ==========
    print("\n" + "=" * 70)
    print("  📊 全面对比测试结果汇总")
    print("=" * 70)
    
    # 总体统计
    rag_wins = sum(1 for r in results if r["winner"] == "RAG")
    no_rag_wins = sum(1 for r in results if r["winner"] == "无RAG")
    ties = len(results) - rag_wins - no_rag_wins
    
    avg_rag = sum(r["score_rag"] for r in results) / len(results)
    avg_no_rag = sum(r["score_no_rag"] for r in results) / len(results)
    
    avg_time_rag = sum(r["time_rag"] for r in results) / len(results)
    avg_time_no_rag = sum(r["time_no_rag"] for r in results) / len(results)
    
    print(f"\n  📈 总体胜率:")
    print(f"     RAG胜: {rag_wins}/{len(results)} ({rag_wins/len(results)*100:.0f}%)")
    print(f"     无RAG胜: {no_rag_wins}/{len(results)} ({no_rag_wins/len(results)*100:.0f}%)")
    print(f"     平手: {ties}/{len(results)}")
    
    print(f"\n  📊 平均关键词覆盖率:")
    print(f"     RAG: {avg_rag:.1%}")
    print(f"     无RAG: {avg_no_rag:.1%}")
    
    print(f"\n  ⏱️  平均响应时间:")
    print(f"     RAG: {avg_time_rag:.1f}s")
    print(f"     无RAG: {avg_time_no_rag:.1f}s")
    
    # 分领域统计
    print(f"\n  📂 分领域对比:")
    domains = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"rag": [], "no_rag": [], "wins": {"rag": 0, "no_rag": 0}}
        domains[d]["rag"].append(r["score_rag"])
        domains[d]["no_rag"].append(r["score_no_rag"])
        if r["winner"] == "RAG":
            domains[d]["wins"]["rag"] += 1
        elif r["winner"] == "无RAG":
            domains[d]["wins"]["no_rag"] += 1
    
    for domain, data in sorted(domains.items()):
        rag_avg = sum(data["rag"]) / len(data["rag"])
        no_rag_avg = sum(data["no_rag"]) / len(data["no_rag"])
        total = len(data["rag"])
        print(f"     {domain}: RAG {rag_avg:.0%}({data['wins']['rag']}) vs 无RAG {no_rag_avg:.0%}({data['wins']['no_rag']})")
    
    # 关键发现
    print(f"\n  💡 关键发现:")
    if avg_rag > avg_no_rag:
        diff = (avg_rag - avg_no_rag) * 100
        print(f"     → RAG整体表现更好，关键词覆盖率高出 {diff:.1f}%")
        print(f"     → RAG的优势在于：基于文档，回答更准确，可追溯")
    elif avg_no_rag > avg_rag:
        diff = (avg_no_rag - avg_rag) * 100
        print(f"     → 无RAG关键词覆盖更高，差异 {diff:.1f}%")
        print(f"     → 警告：无RAG可能有幻觉风险")
    else:
        print(f"     → 两者整体相当")
    
    # 显示具体差异大的案例
    print(f"\n  🔍 差异最大的案例:")
    diffs = [(r["question"][:30], r["score_rag"] - r["score_no_rag"], r["winner"]) 
             for r in results]
    diffs.sort(key=lambda x: abs(x[1]), reverse=True)
    
    for q, diff, winner in diffs[:5]:
        sign = "+" if diff > 0 else ""
        print(f"     {winner:4s}: {sign}{diff:.0%} | {q}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
