# -*- coding: utf-8 -*-
"""
政务智能问答初始化数据 - 简化版JSON
"""

import json

# 初始QA数据
qa_data = {
    "metadata": {
        "name": "济南市政务智能问答初始QA数据",
        "version": "1.0.0",
        "description": "基于2025年济南市实际政策生成的高质量问答对",
        "created_at": "2025-11-09"
    },
    "qa_pairs": [
        {
            "question": "2025年济南市汽车消费补贴的活动时间是什么时候？",
            "answer": "购车时间：2025年1月25日0时至2025年3月31日24时（以机动车销售统一发票时间为准）；补贴申报时间：2025年2月12日10时至2025年4月15日24时。补贴额度共计3000万元，先到先得，用完即止。",
            "category": "汽车消费补贴",
            "keywords": "活动时间,购车时间,申报时间,汽车补贴",
            "difficulty_level": 2,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "购买新能源汽车可以获得多少补贴？",
            "answer": "新能源汽车补贴标准：1. 购车发票金额10万元（含）至30万元（不含）的，每辆补贴4000元；2. 购车发票金额30万元（含）以上的，每辆补贴5000元。",
            "category": "汽车消费补贴",
            "keywords": "新能源汽车,补贴金额,电动汽车",
            "difficulty_level": 2,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "购买燃油车可以获得多少补贴？",
            "answer": "燃油车补贴标准：1. 购车发票金额10万元（含）至30万元（不含）的，每辆补贴3000元；2. 购车发票金额30万元（含）以上的，每辆补贴4000元。",
            "category": "汽车消费补贴",
            "keywords": "燃油车,补贴金额",
            "difficulty_level": 2,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "谁可以申请汽车消费补贴？",
            "answer": "活动时间内，在参与企业购置非营运乘用车新车并完成车辆初次登记上牌的个人消费者。不限户籍和上牌地区。非个人购车、二手车不在补贴范围内。",
            "category": "汽车消费补贴",
            "keywords": "申请条件,参与对象",
            "difficulty_level": 2,
            "query_type": "eligibility",
            "verified": True
        },
        {
            "question": "济南市家电以旧换新补贴包括哪些产品？",
            "answer": "补贴产品包括12类：电冰箱、洗衣机、电视机、空调、电脑、热水器、家用灶具、吸油烟机、净水器、洗碗机、微波炉、电饭煲。",
            "category": "家电以旧换新",
            "keywords": "补贴产品,家电类型",
            "difficulty_level": 2,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "家电以旧换新的补贴标准是多少？",
            "answer": "1. 购买2级及以上能效产品，按销售价格的15%给予补贴；2. 购买1级能效产品，额外再给予5%补贴（即总共20%）；3. 每件补贴不超过2000元。",
            "category": "家电以旧换新",
            "keywords": "补贴标准,补贴金额",
            "difficulty_level": 3,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "购买空调可以补贴几件？",
            "answer": "空调类产品最多可以补贴3件，其他类别的产品每类只能补贴1件。",
            "category": "家电以旧换新",
            "keywords": "空调补贴,数量限制",
            "difficulty_level": 1,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "如何查询济南市最新的消费补贴政策？",
            "answer": "可通过以下渠道：1. 济南市商务局官方网站；2. 泉城购服务平台；3. 关注齐鲁银行、济南商务等官方微信公众号。",
            "category": "通用政策",
            "keywords": "政策查询,信息获取",
            "difficulty_level": 1,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "补贴什么时候能到账？",
            "answer": "审核通过后会在官方网站公示5个工作日，公示期满且无异议后，补贴将发放至申请时提交的银行卡中。",
            "category": "通用政策",
            "keywords": "到账时间,补贴发放",
            "difficulty_level": 2,
            "query_type": "informational",
            "verified": True
        },
        {
            "question": "提供虚假信息申请补贴会有什么后果？",
            "answer": "后果包括：1. 取消补贴资格；2. 追缴已发放的补贴资金；3. 依法追究法律责任；4. 可能影响个人信用记录。",
            "category": "通用政策",
            "keywords": "虚假信息,法律后果",
            "difficulty_level": 1,
            "query_type": "informational",
            "verified": True
        }
    ]
}

# 导出
with open("policy_qa_初始数据.json", "w", encoding="utf-8") as f:
    json.dump(qa_data, f, ensure_ascii=False, indent=2)

print(f"已生成 {len(qa_data['qa_pairs'])} 个QA对")
print("文件：policy_qa_初始数据.json")
