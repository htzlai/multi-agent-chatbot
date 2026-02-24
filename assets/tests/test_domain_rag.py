#!/usr/bin/env python3
"""
专业领域 RAG 测试与分析 v2.0
==============================

针对企业出海新加坡的专业领域进行深入测试:
- 公司注册 (ACRA)
- 税务合规 (IRAS)
- 就业准证 (EP/COMPASS)
- 数据保护 (PDPA)
- ODI境外投资
- 雇佣法规

新增功能 v2.0:
- 真实答案对比评估
- 语义相似度计算
- 多维度质量评分
- 知识覆盖度分析
- 答案结构化评估
- 幻觉检测
- 详细测试报告导出

使用方法:
    python3 test_domain_rag.py              # 运行所有测试
    python3 test_domain_rag.py --company    # 仅测试公司注册
    python3 test_domain_rag.py --compare   # 运行并显示答案对比
    python3 test_domain_rag.py --export    # 导出JSON报告
"""

import requests
import json
import time
import sys
import re
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from collections import Counter

# ============================================================
# 配置
# ============================================================

BACKEND_URL = "http://localhost:8000"
TIMEOUT = 120


# ============================================================
# 专业领域测试用例 (含真实答案)
# ============================================================

DOMAIN_TESTS = {
    "公司注册 (ACRA)": {
        "color": "\033[94m",
        "queries": [
            {
                "id": "acra_001",
                "question": "新加坡私人有限公司注册需要哪些基本文件？",
                "domain": "公司注册",
                "key_points": ["身份证件", "注册地址", "公司章程", "秘书任命"],
                "expected_answer": """新加坡私人有限公司注册需要的基本文件包括：
1. 身份证件：股东和董事的护照或身份证复印件
2. 注册地址：新加坡本地注册地址（不能是邮政信箱）
3. 公司章程：详细说明公司治理结构的文件
4. 秘书任命：需在成立后6个月内任命合格公司秘书
5. 董事声明：确保符合注册要求的声明文件""",
                "difficulty": "easy"
            },
            {
                "id": "acra_002",
                "question": "新加坡公司秘书的任职资格要求是什么？",
                "domain": "公司注册",
                "key_points": ["专业资质", "居住要求", "任命时间"],
                "expected_answer": """新加坡公司秘书的任职资格要求：
1. 专业资质：需具备相关专业知识，如会计、法律或商务管理背景
2. 居住要求：必须是新加坡公民、永久居民或持有有效工作准证
3. 经验要求：具备公司秘书工作经验，熟悉新加坡公司法规定
4. 禁止兼职：同一公司秘书不能同时担任董事职位
5. 任命时间：必须在公司成立后6个月内任命""",
                "difficulty": "medium"
            },
            {
                "id": "acra_003",
                "question": "ACRA商业信息下载服务需要支付多少费用？",
                "domain": "公司注册",
                "key_points": ["费用标准", "不同类型文件价格"],
                "expected_answer": """ACRA商业信息下载费用：
1. 公司基本资料（公司名称、注册号、成立日期等）：免费
2. 公司业务简介（Company Profile）：每次$27.50
3. 股东和董事资料：每次$27.50
4. 秘书和审计师资料：每次$27.50
5. 年度申报表副本：每次$27.50
6. 财务报表：每次$27.50
7. bizfile查询服务年费：$350/年""",
                "difficulty": "medium"
            },
            {
                "id": "acra_004",
                "question": "新加坡公司注册后必须保存哪些法定记录？",
                "domain": "公司注册",
                "key_points": ["会计记录", "会议记录", "董事决议"],
                "expected_answer": """新加坡公司必须保存的法定记录：
1. 会计记录：所有交易记录，需保存至少7年
2. 会议记录：股东会和董事会会议记录
3. 董事决议：所有董事会书面决议
4. 股东名册：所有股东及其持股信息
5. 董事名册：所有董事及其个人信息
6. 秘书名册：公司秘书相关信息
7. 重要控制人登记册（PSC Register）
8. 股本变动记录：公司股本的任何变动""",
                "difficulty": "medium"
            }
        ]
    },

    "税务合规 (IRAS)": {
        "color": "\033[92m",
        "queries": [
            {
                "id": "tax_001",
                "question": "新加坡公司所得税的标准税率是多少？",
                "domain": "税务",
                "key_points": ["17%标准税率", "免税额", "部分免税"],
                "expected_answer": """新加坡公司所得税：
1. 标准税率：17%（这是统一的税率，无分级）
2. 应税收入计算：总收入 - 可扣除费用 = 应税收入
3. 部分免税计划：
   - 首10万新元应税收入：减免75%（实缴4.25%）
   - 接下来的19万新元：减免50%（实缴8.5%）
   - 超过30万新元：全额17%
4. 新公司豁免：符合条件的新设公司首3年可享受更多减免
5. 境外收入豁免：符合条件的境外股息、分公司利润可免税""",
                "difficulty": "easy"
            },
            {
                "id": "tax_002",
                "question": "什么是Form C-S？哪些公司可以使用简化申报？",
                "domain": "税务",
                "key_points": ["收入门槛", "适用范围", "简化要求"],
                "expected_answer": """Form C-S 简化申报：
1. 定义：Form C-S是新加坡公司所得税的简化申报表
2. 适用范围：
   - 年收入不超过500万新元
   - 无海外分支或外国子公司
   - 不涉及特定复杂税务情况
3. 优势：
   - 无需提交财务报表
   - 简化申报流程
   - 减少合规成本
4. 申报要求：
   - 仍需保留完整会计记录
   - 税务局保留要求补充资料的权利
5. 不适用情况：年收入超过500万或涉及复杂税务""",
                "difficulty": "medium"
            },
            {
                "id": "tax_003",
                "question": "新加坡转让定价文档要求有哪些？",
                "domain": "税务",
                "key_points": ["主体文档", "本地文档", "国别报告"],
                "expected_answer": """新加坡转让定价文档要求：
1. 文档要求层级：
   - 主体文档（Master File）：集团整体信息
   - 本地文档（Local File）：新加坡公司具体交易
   - 国别报告（Country-by-Country Report）：跨境集团
2. 文档门槛（2023年起）：
   - 年收入超过10亿新元：需准备主体文档
   - 年收入超过800万新元：需准备本地文档
   - 跨国集团：需准备国别报告
3. 同期文档要求：需在财年结束后2个月内准备
4. 保留期限：需保存至少5年
5. 安全港规则：某些低风险交易可简化""",
                "difficulty": "hard"
            },
            {
                "id": "tax_004",
                "question": "新加坡股息收入是否需要缴纳所得税？",
                "domain": "税务",
                "key_points": ["参股豁免", "条件要求"],
                "expected_answer": """新加坡股息征税规则：
1. 参股豁免（Participating Exemption）：
   - 符合条件的股息收入可完全免税
2. 豁免条件：
   - 持股比例：投资公司在被投资公司持有至少10%股权
   - 被投资公司税率：需在注册地缴纳至少15%所得税
   - 持股时间：无最短要求，但需为真实商业投资
3. 不符合条件的情况：
   - 股息作为营业收入而非投资收益
   - 被投资公司不在新加坡或无充分税率
4. 境外股息：符合条件也可免税""",
                "difficulty": "medium"
            }
        ]
    },

    "就业准证 (EP/COMPASS)": {
        "color": "\033[93m",
        "queries": [
            {
                "id": "ep_001",
                "question": "新加坡EP准证申请的基本薪资要求是多少？",
                "domain": "就业准证",
                "key_points": ["最低薪资", "行业差异", "经验要求"],
                "expected_answer": """新加坡EP准证薪资要求：
1. 最低薪资（2024年标准）：
   - 一般申请人：月薪至少5,000新元
   - 金融行业：月薪至少5,500新元
2. 经验要求：通常需要相关工作经验
3. 薪资评估：
   - 薪资应与候选人的资质和经验匹配
   - 需证明无法在本地劳动力市场找到合适人选
4. COMPASS加分：
   - 薪资超过90分位：可获得额外加分
5. 续签要求：薪资需持续满足标准""",
                "difficulty": "easy"
            },
            {
                "id": "ep_002",
                "question": "COMPASS评估框架包含哪些评分维度？",
                "domain": "就业准证",
                "key_points": ["4项核心指标", "2项加成指标", "及格分数"],
                "expected_answer": """COMPASS评估框架：
1. 4项核心指标（每项20分，共80分）：
   - C1 薪资：与当地PMET薪资水平比较
   - C2 资质：候选人学历资质
   - C3 工作经历：相关工作经验
   - C4 多元化：团队国籍多样性支持
2. 2项加成指标（每项10分，共20分）：
   - C5 技能加分：紧缺职业清单技能
   - C6 战略业务加分：公司符合战略重点
3. 及格分数：40分（需每项至少达到C级）
4. 等级划分：
   - A级：≥40分且每项≥10分
   - B级：≥40分但某项<10分
   - C级：<40分""",
                "difficulty": "medium"
            },
            {
                "id": "ep_003",
                "question": "哪些职业可以通过COMPASS获得加分？",
                "domain": "就业准证",
                "key_points": ["紧缺职业清单", "技能加分", "战略业务加分"],
                "expected_answer": """COMPASS加分职业：
1. 紧缺职业清单（SOL）：
   - 涵盖多个行业，如金融、科技、医疗等
   - 需查看MOM最新发布的清单
2. 技能加分（C5）：
   - 从事清单上职业可获得10分
   - 需提供相关资格证明
3. 战略业务加分（C6）：
   - 符合新加坡经济战略的公司
   - 创新或高增长企业
   - 总部或区域总部
4. 证明要求：
   - 雇主需证明职位与战略业务相关""",
                "difficulty": "medium"
            },
            {
                "id": "ep_004",
                "question": "EP准证持有人的家属是否可以留在新加坡？",
                "domain": "就业准证",
                "key_points": ["DP签证", "LTVP", "申请条件"],
                "expected_answer": """EP持有人家属准证：
1. 家属准证（DP）：
   - 合法配偶
   - 21岁以下未婚子女
   - 申请要求：EP持有人月薪≥6,000新元
2. 长期访问准证（LTVP）：
   - 合法配偶（同性和异性）
   - 21岁以上未婚残疾子女
   - 父母（仅限EP≥10,000新元）
3. 申请流程：
   - 需由雇主或EP持有人代为申请
   - 审批时间约3周
4. 权利限制：
   - DP不能直接工作，需申请工作准证
   - LTVP逗留期限与EP挂钩""",
                "difficulty": "medium"
            }
        ]
    },

    "数据保护 (PDPA)": {
        "color": "\033[96m",
        "queries": [
            {
                "id": "pdpa_001",
                "question": "新加坡PDPA规定的个人信息保护原则有哪些？",
                "domain": "数据保护",
                "key_points": ["通知原则", "选择原则", "访问原则", "更正原则"],
                "expected_answer": """PDPA 10大保护原则：
1. 通知原则：收集信息时需告知目的
2. 同意原则：需获得明确同意才能收集
3. 目的原则：信息仅用于指定目的
4. 限制原则：只收集必要信息
5. 访问原则：个人可查看收集的信息
6. 更正原则：个人可要求更正错误信息
7. 准确原则：需确保信息准确完整
8. 存储限制：不再需要时删除
9. 传输安全：保护数据传输安全
10. 保留限制：保留期限不超过必要时间""",
                "difficulty": "easy"
            },
            {
                "id": "pdpa_002",
                "question": "企业需要任命数据保护官(DPO)吗？要求是什么？",
                "domain": "数据保护",
                "key_points": ["强制性", "资质要求", "职责范围"],
                "expected_answer": """数据保护官（DPO）要求：
1. 任命要求：
   - 并非强制所有企业都需任命DPO
   - 但建议所有企业设立该职位
2. 适用情况（强制任命）：
   - 政府机构
   - 大型企业（视业务性质决定）
3. DPO职责：
   - 监督PDPA合规
   - 处理数据保护投诉
   - 培训员工数据保护意识
   - 与PDPC沟通
4. 资质要求：
   - 需了解数据保护法律
   - 具备相关培训或经验
5. 可由内部人员兼任或外包""",
                "difficulty": "medium"
            },
            {
                "id": "pdpa_003",
                "question": "跨境数据传输需要满足什么条件？",
                "domain": "数据保护",
                "key_points": ["充分性认定", "约束性公司规则", "合同条款"],
                "expected_answer": """跨境数据传输合规要求：
1. 充分性认定：
   - 目的地国家有足够的数据保护水平
   - 新加坡已与部分国家签订认定协议
2. 约束性公司规则（BCR）：
   - 跨国企业内部数据传输规则
   - 需获PDPC批准
3. 合同保障措施：
   - 与接收方签订数据保护协议
   - 标准合同条款（SCC）
4. 通知并同意：
   - 告知用户跨境传输风险
   - 获得明确同意
5. 风险评估：
   - 评估目的地国家保护水平
   - 采取适当保护措施""",
                "difficulty": "hard"
            },
            {
                "id": "pdpa_004",
                "question": "PDPC可以对违规企业处以多高的罚款？",
                "domain": "数据保护",
                "key_points": ["罚款上限", "计算方式", "严重情节"],
                "expected_answer": """PDPA违规罚款：
1. 一般违规：
   - 最高罚款100万新元
   - 或年营业额10%（取较高者）
2. 严重情节：
   - 故意违规或屡次违规
   - 导致严重后果
   - 可能面临更高处罚
3. 其他处罚：
   - 强制性命令
   - 通知整改
   - 暂停数据处理活动
4. 执行方式：
   - 2024年起引入强制性罚款
   - 考虑企业规模和违规程度
5. 辩护理由：
   - 已尽合理努力
   - 不可抗力因素""",
                "difficulty": "medium"
            }
        ]
    },

    "ODI境外投资": {
        "color": "\033[95m",
        "queries": [
            {
                "id": "odi_001",
                "question": "中国企业进行境外直接投资(ODI)需要办理哪些备案？",
                "domain": "境外投资",
                "key_points": ["发改委备案", "商务部备案", "外汇登记"],
                "expected_answer": """中国企业ODI备案流程：
1. 发改委备案：
   - 审核项目合规性
   - 3亿美元以下：省级发改委
   - 3亿美元以上：国家发改委
2. 商务部备案：
   - 审核投资主体资格
   - 地方商务部门办理
   - 颁发《企业境外投资证书》
3. 外汇登记：
   - 完成后需进行外汇登记
   - 登记后方可汇出资金
4. 注意事项：
   - 敏感行业需审批而非备案
   - 投资额巨大需额外审查
   - 需提供真实性证明材料""",
                "difficulty": "easy"
            },
            {
                "id": "odi_002",
                "question": "哪些类型的境外投资需要进行ODI备案？",
                "domain": "境外投资",
                "key_points": ["敏感行业", "敏感国家", "大额投资"],
                "expected_answer": """ODI备案/审批范围：
1. 敏感行业（需审批）：
   - 房地产
   - 酒店
   - 影城
   - 娱乐业
   - 体育俱乐部
   - 赌博业
   - 武器制造
2. 敏感国家/地区：
   - 朝鲜
   - 伊朗
   - 叙利亚
   - 部分受制裁国家
3. 大额投资：
   - 中方投资额≥3亿美元
   - 需国家发改委审批
4. 备案vs审批：
   - 一般项目：备案制
   - 敏感项目：审批制
   - 地方vs中央：视金额和行业""",
                "difficulty": "medium"
            },
            {
                "id": "odi_003",
                "question": "新加坡对跨境资金管理有哪些便利政策？",
                "domain": "境外投资",
                "key_points": ["外汇自由", "税收优惠", "资金池"],
                "expected_answer": """新加坡跨境资金便利政策：
1. 外汇管理：
   - 无外汇管制
   - 资金自由进出
   - 兑换无限制
2. 税收优惠：
   - 企业所得税17%
   - 无资本利得税
   - 股息免税（符合条件的境外收入）
   - 参与豁免计划
3. 资金池功能：
   - 集团内部资金调拨
   - 多币种账户
   - 集中管理现金流
4. 金融基础设施：
   - 亚洲最大外汇市场
   - 完善的银行体系
   - 丰富的金融产品
5. 区域总部激励：
   - 区域总部享有税务优惠
   - 就业优惠""",
                "difficulty": "medium"
            }
        ]
    },

    "雇佣法规": {
        "color": "\033[91m",
        "queries": [
            {
                "id": "emp_001",
                "question": "新加坡雇佣法令(EA)对工资支付有什么规定？",
                "domain": "雇佣法规",
                "key_points": ["支付周期", "加班费", "扣款限制"],
                "expected_answer": """新加坡雇佣法令工资规定：
1. 支付周期：
   - 工资必须在工作后7天内支付
   - 每月至少支付一次
   - 不得拖欠超过14天
2. 加班费：
   - 工作超过44小时/周为加班
   - 加班费不低于正常工资1.5倍
   - 节假日加班：2倍工资
3. 扣款限制：
   - 工资扣款不得超过25%
   - 罚款需有合理依据
   - 不得扣除培训费用
4. 工资单：
   - 雇主需提供详细工资单
   - 列明工资、扣款、加班费等
5. 拖欠处罚：
   - 违法可被罚至5000新元
   - 或监禁6个月""",
                "difficulty": "easy"
            },
            {
                "id": "emp_002",
                "question": "新加坡外籍员工工作准证有哪些类型？",
                "domain": "雇佣法规",
                "key_points": ["EP", "SP", "WP", "申请条件"],
                "expected_answer": """新加坡外籍员工准证类型：
1. Employment Pass (EP)：
   - 适用：专业人士、管理人员
   - 薪资：≥5,000新元/月
   - 评估：COMPASS
2. S Pass (SP)：
   - 适用：中等技术人员
   - 薪资：≥3,000新元/月
   - 评估：COMPASS
   - 配额限制
3. Work Permit (WP)：
   - 适用：低技能劳工
   - 行业限制
   - 配额严格控制
   - 不可为家属申请准证
4. 其他：
   - EntrePass：创业者
   - PEP：个人化就业准证
5. 家属准证：
   - EP/SP可申请
   - WP不可申请""",
                "difficulty": "easy"
            },
            {
                "id": "emp_003",
                "question": "雇主需要为员工缴纳哪些强制性公积金(CPF)？",
                "domain": "雇佣法规",
                "key_points": ["公积金比例", "雇主承担", "员工承担"],
                "expected_answer": """新加坡CPF公积金：
1. 适用范围：
   - 新加坡公民
   - 永久居民
   - 55岁以下
2. 缴纳比例（2024年）：
   - 员工：20%
   - 雇主：17%
   - 总计：37%
3. 缴交上限：
   - 工资上限：6,800新元/月
   - 超过部分不计入
4. 年龄调整：
   - 55-60岁：降低比例
   - 60-65岁：进一步降低
   - 65岁以上：最低比例
5. 用途：
   - 住房
   - 医疗
   - 养老
   - 教育（部分）""",
                "difficulty": "medium"
            }
        ]
    }
}

RESET_COLOR = "\033[0m"


# ============================================================
# 数据类
# ============================================================

@dataclass
class AnswerAnalysis:
    """答案分析结果"""
    query_id: str
    question: str
    domain: str
    difficulty: str

    # 原始数据
    answer: str = ""
    sources: List[Dict] = field(default_factory=list)
    duration: float = 0.0
    expected_answer: str = ""

    # 语义分析
    semantic_similarity: float = 0.0     # 语义相似度 (新增)

    # 多维度评分
    relevance_score: float = 0.0         # 相关性
    completeness_score: float = 0.0       # 完整性
    accuracy_score: float = 0.0         # 准确性
    source_quality_score: float = 0.0   # 来源质量
    structure_score: float = 0.0        # 结构化程度
    hallucination_score: float = 0.0     # 幻觉检测 (新增)
    overall_score: float = 0.0           # 综合评分

    # 检测结果
    matched_key_points: List[str] = field(default_factory=list)
    missing_key_points: List[str] = field(default_factory=list)
    hallucination_flags: List[str] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)

    # 来源分析
    source_count: int = 0
    source_types: List[str] = field(default_factory=list)

    def calculate_scores(self, expected_key_points: List[str]):
        """计算各维度分数 - 增强版"""

        # 0. 语义相似度 (简化版 - 基于关键词重叠)
        if self.expected_answer:
            # 计算答案与期望答案的关键词重叠
            answer_words = set(self.answer.lower().split())
            expected_words = set(self.expected_answer.lower().split())
            overlap = len(answer_words & expected_words)
            self.semantic_similarity = min(1.0, overlap / max(1, len(expected_words)))

        # 1. 相关性分数
        if not self.answer:
            self.relevance_score = 0.0
        else:
            answer_lower = self.answer.lower()
            matched = sum(1 for pt in expected_key_points if pt.lower() in answer_lower)
            self.relevance_score = min(1.0, matched / max(1, len(expected_key_points)))
            self.matched_key_points = [pt for pt in expected_key_points if pt.lower() in answer_lower]
            self.missing_key_points = [pt for pt in expected_key_points if pt.lower() not in answer_lower]

        # 2. 完整性分数
        min_length = 100
        max_length = 3000
        length_ratio = min(1.0, max(0, len(self.answer) - min_length) / (max_length - min_length))
        key_coverage = min(1.0, len(self.matched_key_points) / max(1, len(expected_key_points)))
        self.completeness_score = (length_ratio * 0.3 + key_coverage * 0.7)

        # 3. 准确性分数
        self.accuracy_score = 1.0 if self.source_count > 0 else 0.0

        # 4. 来源质量分数
        if self.sources:
            type_diversity = len(set(self.source_types)) / 3
            count_score = min(1.0, self.source_count / 3)
            self.source_quality_score = (type_diversity * 0.5 + count_score * 0.5)
        else:
            self.source_quality_score = 0.0

        # 5. 结构化分数
        structure_markers = ["1.", "2.", "3.", "•", "-", "：", "第一", "第二", "首先"]
        self.structure_score = 1.0 if any(marker in self.answer for marker in structure_markers) else 0.5

        # 6. 幻觉检测分数 (新增)
        # 检查答案中是否有过于肯定但来源不支持的表述
        certainty_words = ["肯定", "绝对", "100%", "毫无疑问"]
        unsupported_claims = []
        for word in certainty_words:
            if word in self.answer and self.source_count == 0:
                unsupported_claims.append(word)
        self.hallucination_score = 1.0 - (len(unsupported_claims) * 0.2) if self.source_count > 0 else 0.5
        self.hallucination_flags = unsupported_claims

        # 7. 综合评分 (加权平均)
        weights = {
            'relevance': 0.20,
            'semantic': 0.15,
            'completeness': 0.20,
            'accuracy': 0.15,
            'source_quality': 0.10,
            'structure': 0.10,
            'hallucination': 0.10
        }

        self.overall_score = (
            self.relevance_score * weights['relevance'] +
            self.semantic_similarity * weights['semantic'] +
            self.completeness_score * weights['completeness'] +
            self.accuracy_score * weights['accuracy'] +
            self.source_quality_score * weights['source_quality'] +
            self.structure_score * weights['structure'] +
            self.hallucination_score * weights['hallucination']
        )


# ============================================================
# 测试客户端
# ============================================================

class DomainRAGTester:
    """专业领域 RAG 测试客户端 v2.0"""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.session.timeout = TIMEOUT
        self.results: List[AnswerAnalysis] = []
        self.show_comparison = "--compare" in sys.argv
        self.export_json = "--export" in sys.argv

    def query_rag(self, question: str) -> Dict[str, Any]:
        """执行 RAG 查询"""
        start = time.time()

        try:
            response = self.session.get(
                f"{self.base_url}/test/rag",
                params={"query": question, "k": 5},
                timeout=TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            duration = time.time() - start

            sources = data.get("sources", [])
            source_types = []
            for s in sources:
                source_name = s.get("source", s.get("file", ""))
                if ".pdf" in source_name:
                    source_types.append("PDF")
                elif ".md" in source_name:
                    source_types.append("Markdown")
                elif ".html" in source_name or ".htm" in source_name:
                    source_types.append("HTML")
                else:
                    source_types.append("Other")

            return {
                "success": True,
                "answer": data.get("answer", ""),
                "sources": sources,
                "source_count": len(sources),
                "source_types": source_types,
                "duration": duration,
                "error": None
            }

        except Exception as e:
            duration = time.time() - start
            return {
                "success": False,
                "answer": "",
                "sources": [],
                "source_count": 0,
                "source_types": [],
                "duration": duration,
                "error": str(e)
            }

    def analyze_query(self, query_config: Dict) -> AnswerAnalysis:
        """测试并分析单个查询"""

        analysis = AnswerAnalysis(
            query_id=query_config["id"],
            question=query_config["question"],
            domain=query_config["domain"],
            difficulty=query_config.get("difficulty", "medium"),
            expected_answer=query_config.get("expected_answer", "")
        )

        result = self.query_rag(query_config["question"])

        if result["success"]:
            analysis.answer = result["answer"]
            analysis.sources = result["sources"]
            analysis.duration = result["duration"]
            analysis.source_count = result["source_count"]
            analysis.source_types = result["source_types"]
        else:
            analysis.hallucination_flags.append(result["error"])

        analysis.calculate_scores(query_config["key_points"])

        return analysis

    def run_domain_tests(self, domain_name: str) -> List[AnswerAnalysis]:
        """运行指定领域的测试"""

        if domain_name not in DOMAIN_TESTS:
            print(f"  ⚠️ 未知领域: {domain_name}")
            return []

        domain_config = DOMAIN_TESTS[domain_name]
        queries = domain_config["queries"]

        print(f"\n{domain_config['color']}{'='*60}")
        print(f"  {domain_name} 领域测试")
        print(f"{'='*60}{RESET_COLOR}")

        results = []

        for query in queries:
            print(f"\n  📋 [{query['id']}] {query['question'][:40]}...")

            analysis = self.analyze_query(query)
            results.append(analysis)

            # 打印结果摘要
            status = "✅" if analysis.overall_score >= 0.6 else "⚠️"
            print(f"     {status} 综合: {analysis.overall_score:.0%} | "
                  f"相关: {analysis.relevance_score:.0%} | "
                  f"语义: {analysis.semantic_similarity:.0%} | "
                  f"来源: {analysis.source_count}")

            # 显示答案对比（如果启用）
            if self.show_comparison:
                print(f"\n     📝 实际回答:")
                print(f"     {'─'*50}")
                # 只显示前300字
                preview = analysis.answer[:300] + "..." if len(analysis.answer) > 300 else analysis.answer
                for line in preview.split('\n')[:5]:
                    print(f"     {line}")
                print(f"     {'─'*50}")

            if analysis.missing_key_points:
                print(f"     ⚠️ 缺失: {', '.join(analysis.missing_key_points[:2])}")

        return results

    def generate_report(self, all_results: List[AnswerAnalysis]) -> str:
        """生成测试报告 - 增强版"""

        report = []
        report.append("\n" + "=" * 70)
        report.append("  📊 专业领域 RAG 测试分析报告 v2.0")
        report.append("=" * 70)
        report.append(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"  测试数量: {len(all_results)}")
        report.append(f"  后端地址: {BACKEND_URL}")

        # 按领域分组
        domain_groups = {}
        for r in all_results:
            if r.domain not in domain_groups:
                domain_groups[r.domain] = []
            domain_groups[r.domain].append(r)

        # 总体统计
        total_score = sum(r.overall_score for r in all_results)
        avg_score = total_score / len(all_results) if all_results else 0

        avg_semantic = sum(r.semantic_similarity for r in all_results) / len(all_results)
        avg_relevance = sum(r.relevance_score for r in all_results) / len(all_results)
        avg_completeness = sum(r.completeness_score for r in all_results) / len(all_results)

        report.append(f"\n  🎯 综合评分: {avg_score:.1%}")
        report.append(f"  📈 语义相似度: {avg_semantic:.1%}")
        report.append(f"  📈 关键词相关: {avg_relevance:.1%}")
        report.append(f"  📈 回答完整度: {avg_completeness:.1%}")

        # 评级
        if avg_score >= 0.85:
            report.append("  评级: ⭐⭐⭐⭐⭐ 优秀 - 可投入生产")
        elif avg_score >= 0.70:
            report.append("  评级: ⭐⭐⭐⭐ 良好 - 建议优化后上线")
        elif avg_score >= 0.55:
            report.append("  评级: ⭐⭐⭐ 一般 - 需要改进")
        elif avg_score >= 0.40:
            report.append("  评级: ⭐⭐ 较差 - 需重点优化")
        else:
            report.append("  评级: ⭐ 差 - 不建议上线")

        # 各领域分析
        report.append("\n" + "-" * 70)
        report.append("  📂 各领域详细分析")
        report.append("-" * 70)

        domain_scores = []
        for domain, results in domain_groups.items():
            domain_avg = sum(r.overall_score for r in results) / len(results)
            domain_scores.append((domain, domain_avg, results))

        # 按分数排序
        domain_scores.sort(key=lambda x: x[1], reverse=True)

        for domain, domain_avg, results in domain_scores:
            domain_color = ""
            for name, config in DOMAIN_TESTS.items():
                if name.split(" ")[0] in domain:
                    domain_color = config["color"]
                    break

            report.append(f"\n  {domain_color}{domain}{RESET_COLOR}")
            report.append(f"  测试数: {len(results)} | 综合分: {domain_avg:.1%}")

            for r in results:
                status = "✅" if r.overall_score >= 0.6 else "⚠️"
                difficulty_emoji = {"easy": "★", "medium": "★★", "hard": "★★★"}.get(r.difficulty, "")
                report.append(f"    {status} {difficulty_emoji} {r.query_id}: "
                            f"综合:{r.overall_score:.0%} 语义:{r.semantic_similarity:.0%} "
                            f"相关:{r.relevance_score:.0%} 完整:{r.completeness_score:.0%}")

                if r.missing_key_points:
                    report.append(f"        缺失关键点: {', '.join(r.missing_key_points[:2])}")

        # 来源分析
        report.append("\n" + "-" * 70)
        report.append("  📚 来源引用分析")
        report.append("-" * 70)

        source_counter = Counter()
        for r in all_results:
            for st in r.source_types:
                source_counter[st] += 1

        total_sources = sum(source_counter.values())
        report.append(f"  总来源引用: {total_sources} 次")
        for stype, count in source_counter.most_common():
            pct = count / total_sources * 100 if total_sources > 0 else 0
            report.append(f"  {stype}: {count} 次 ({pct:.0f}%)")

        # 知识盲区
        report.append("\n" + "-" * 70)
        report.append("  🔍 知识盲区检测")
        report.append("-" * 70)

        low_score_queries = [r for r in all_results if r.overall_score < 0.5]
        if low_score_queries:
            for r in low_score_queries:
                report.append(f"  ⚠️ [{r.query_id}] {r.question[:40]}...")
                if r.knowledge_gaps:
                    report.append(f"      错误: {r.knowledge_gaps[0]}")
                if r.missing_key_points:
                    report.append(f"      缺失: {', '.join(r.missing_key_points[:3])}")
        else:
            report.append("  ✅ 未发现明显知识盲区")

        # 改进建议
        report.append("\n" + "-" * 70)
        report.append("  💡 改进建议")
        report.append("-" * 70)

        # 按缺失关键点统计
        all_missing = []
        for r in all_results:
            all_missing.extend(r.missing_key_points)

        if all_missing:
            missing_counter = Counter(all_missing)
            report.append("  常见缺失知识点 (Top 10):")
            for point, count in missing_counter.most_common(10):
                report.append(f"    • {point}: {count}次")

        # 优化建议
        report.append("\n  优化方向:")
        if avg_semantic < 0.5:
            report.append("    1. 语义相似度较低 - 建议增加领域相关训练数据")
        if avg_completeness < 0.5:
            report.append("    2. 回答完整度不足 - 建议调整检索策略获取更多chunk")
        if avg_relevance < 0.5:
            report.append("    3. 关键词匹配度低 - 建议优化分词策略")

        report.append("\n" + "=" * 70)

        return "\n".join(report)

    def export_json_report(self, all_results: List[AnswerAnalysis]):
        """导出JSON报告"""
        export_data = {
            "test_time": datetime.now().isoformat(),
            "backend_url": BACKEND_URL,
            "total_tests": len(all_results),
            "summary": {
                "overall_score": sum(r.overall_score for r in all_results) / len(all_results),
                "semantic_similarity": sum(r.semantic_similarity for r in all_results) / len(all_results),
                "relevance_score": sum(r.relevance_score for r in all_results) / len(all_results),
                "completeness_score": sum(r.completeness_score for r in all_results) / len(all_results),
            },
            "results": [asdict(r) for r in all_results]
        }

        filename = f"rag_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"\n  📄 JSON报告已导出: {filename}")


# ============================================================
# 主函数
# ============================================================

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    tester = DomainRAGTester()
    all_results = []

    print("\n" + "=" * 60)
    print("  🔬 专业领域 RAG 测试与分析 v2.0")
    print("  后端: " + BACKEND_URL)
    print("=" * 60)

    # 确定要测试的领域
    if mode == "--all":
        domains_to_test = list(DOMAIN_TESTS.keys())
    elif mode == "--company":
        domains_to_test = ["公司注册 (ACRA)"]
    elif mode == "--tax":
        domains_to_test = ["税务合规 (IRAS)"]
    elif mode == "--ep":
        domains_to_test = ["就业准证 (EP/COMPASS)"]
    elif mode == "--pdpa":
        domains_to_test = ["数据保护 (PDPA)"]
    elif mode == "--odi":
        domains_to_test = ["ODI境外投资"]
    elif mode == "--emp":
        domains_to_test = ["雇佣法规"]
    elif mode == "--compare":
        domains_to_test = list(DOMAIN_TESTS.keys())
    elif mode == "--export":
        domains_to_test = list(DOMAIN_TESTS.keys())
    else:
        print(f"  ⚠️ 未知模式: {mode}")
        print("  可用模式:")
        print("    --all      : 全部测试")
        print("    --company  : 公司注册")
        print("    --tax      : 税务")
        print("    --ep       : EP准证")
        print("    --pdpa     : 数据保护")
        print("    --odi      : ODI投资")
        print("    --emp      : 雇佣法规")
        print("    --compare  : 测试并显示答案对比")
        print("    --export   : 测试并导出JSON")
        return

    # 运行测试
    for domain in domains_to_test:
        results = tester.run_domain_tests(domain)
        all_results.extend(results)

    # 生成报告
    report = tester.generate_report(all_results)
    print(report)

    # 导出JSON（如果启用）
    if tester.export_json:
        tester.export_json_report(all_results)


if __name__ == "__main__":
    main()
