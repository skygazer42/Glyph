"""
政务智能问答初始化 QA 对数据
基于济南市实际政策生成的高质量问答对
"""

import json

# ==================== 汽车消费补贴 QA 对 ====================

CAR_SUBSIDY_QA = [
    {
        "question": "2025年济南市汽车消费补贴的活动时间是什么时候？",
        "answer": "购车时间：2025年1月25日0时至2025年3月31日24时（以机动车销售统一发票时间为准）；补贴申报时间：2025年2月12日10时至2025年4月15日24时；申领资料修改时间：2025年2月12日10时至2025年4月30日24时。补贴额度共计3000万元，先到先得，用完即止。",
        "category": "汽车消费补贴",
        "keywords": "活动时间,购车时间,申报时间,汽车补贴",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "购买新能源汽车可以获得多少补贴？",
        "answer": "新能源汽车补贴标准：1. 购车发票金额10万元（含）至30万元（不含）的，每辆补贴4000元；2. 购车发票金额30万元（含）以上的，每辆补贴5000元。发票金额以机动车销售统一发票上不含税价为准，不含车辆装潢、挂牌等其它费用。",
        "category": "汽车消费补贴",
        "keywords": "新能源汽车,补贴金额,电动汽车,购车补贴",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "购买燃油车可以获得多少补贴？",
        "answer": "燃油车补贴标准：1. 购车发票金额10万元（含）至30万元（不含）的，每辆补贴3000元；2. 购车发票金额30万元（含）以上的，每辆补贴4000元。发票金额以机动车销售统一发票上不含税价为准，不含车辆装潢、挂牌等其它费用。",
        "category": "汽车消费补贴",
        "keywords": "燃油车,补贴金额,购车补贴",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "申请汽车消费补贴需要提交哪些资料？",
        "answer": "需要提交以下资料：1. 购车人身份证原件正反面照片；2. 机动车销售统一发票原件照片（第一联发票联，发票日期须在活动期内）；3. 机动车行驶证原件（主、副页）照片（新能源汽车副页须有"新能源"标注）；4. 机动车登记证书原件（第1、2页）照片；5. 购车人银行卡照片；6. 可接收短信的手机号码。所有照片请保持完整、清晰。",
        "category": "汽车消费补贴",
        "keywords": "申请资料,提交材料,汽车补贴申请",
        "difficulty_level": 3,
        "query_type": "procedural",
        "verified": True
    },
    {
        "question": "如何申请济南市汽车消费补贴？",
        "answer": "申请流程：1. 完成车辆上牌和注册登记，取得《机动车登记证书》和《机动车行驶证》；2. 通过微信扫描活动二维码或关注"齐鲁银行公众号"→点击"领优惠"→"权益中心"→"济南市政府汽车消费补贴申报"；3. 填写购车信息，上传所需资料；4. 等待系统初审和第三方机构复审；5. 审核通过后公示5个工作日；6. 公示无异议后补贴发放至银行卡。",
        "category": "汽车消费补贴",
        "keywords": "申请流程,办理流程,如何申请",
        "difficulty_level": 3,
        "query_type": "procedural",
        "verified": True
    },
    {
        "question": "谁可以申请汽车消费补贴？有户籍限制吗？",
        "answer": "参与对象：活动时间内，在参与企业购置非营运乘用车新车并完成车辆初次登记上牌的个人消费者。不限户籍和上牌地区。注意：非个人购车、二手车不在补贴范围内。",
        "category": "汽车消费补贴",
        "keywords": "申请条件,参与对象,户籍限制,资格条件",
        "difficulty_level": 2,
        "query_type": "eligibility",
        "verified": True
    },
    {
        "question": "新能源汽车包括哪些类型？",
        "answer": "新能源乘用车包含三类：1. 纯电动汽车；2. 插电式混合动力汽车（含增程式）；3. 燃料电池汽车。判断标准：机动车行驶证副页有"新能源"标注，挂绿色车牌。",
        "category": "汽车消费补贴",
        "keywords": "新能源汽车,车辆类型,电动汽车类型",
        "difficulty_level": 1,
        "query_type": "informational",
        "verified": True
    }
]

# ==================== 家电以旧换新 QA 对 ====================

APPLIANCE_QA = [
    {
        "question": "济南市家电以旧换新补贴包括哪些产品？",
        "answer": "补贴产品包括12类：电冰箱（含冰吧、冰柜、冷柜）、洗衣机（含干衣机、洗烘一体机）、电视机（含激光电视、智慧屏）、空调（含家用中央空调、风管机）、电脑（限台式电脑和笔记本电脑）、热水器（含燃气壁挂炉热水器）、家用灶具（含家用集成灶）、吸油烟机、净水器（含家用净水机）、洗碗机、微波炉、电饭煲（含电饭锅）。还包括其他大宗耐用家电，品种动态调整。",
        "category": "家电以旧换新",
        "keywords": "补贴产品,家电类型,以旧换新产品",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "家电以旧换新的补贴标准是多少？",
        "answer": "补贴标准：1. 购买2级及以上能效或水效标准的产品，按最终销售价格的15%给予补贴；2. 购买1级及以上能效或水效标准的产品，额外再给予5%补贴（即总共20%）；3. 无能效或水效标识的产品补贴标准不超过2级能效产品；4. 每位消费者每类产品可补贴1件（空调类产品最多补贴3件），每件补贴不超过2000元。",
        "category": "家电以旧换新",
        "keywords": "补贴标准,补贴金额,以旧换新补贴",
        "difficulty_level": 3,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "如何领取家电以旧换新补贴资格？",
        "answer": "领取流程：1. 通过济南市"泉城购"服务平台完成实名认证；2. 根据需求领取补贴资格（实行总量控制）；3. 补贴资格须在2个自然日内使用（即领取之日起至第二日的23:59:59），未使用自动失效；4. 每个品类的补贴资格有3次领取机会。",
        "category": "家电以旧换新",
        "keywords": "领取资格,补贴资格,泉城购",
        "difficulty_level": 2,
        "query_type": "procedural",
        "verified": True
    },
    {
        "question": "家电以旧换新一定要交售旧家电吗？",
        "answer": "不是强制的。鼓励消费者在购新的同时交售12类废旧家电，但不是必须条件。有交旧意愿的个人消费者可通过济南市"泉城购"服务平台或电商平台预约回收服务，回收的废家电应全部交予有资质的拆解企业。",
        "category": "家电以旧换新",
        "keywords": "旧家电回收,是否必须,交旧要求",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "2024年已经享受过家电补贴，2025年还能再享受吗？",
        "answer": "可以。2024年已享受某类家电产品以旧换新补贴的个人消费者，2025年购买同类家电产品可继续享受补贴。",
        "category": "家电以旧换新",
        "keywords": "重复享受,多次申请,补贴资格",
        "difficulty_level": 1,
        "query_type": "eligibility",
        "verified": True
    },
    {
        "question": "购买空调可以补贴几件？",
        "answer": "空调类产品最多可以补贴3件，其他类别的产品每类只能补贴1件。每件补贴不超过2000元。",
        "category": "家电以旧换新",
        "keywords": "空调补贴,数量限制,补贴件数",
        "difficulty_level": 1,
        "query_type": "informational",
        "verified": True
    }
]

# ==================== 消费券 QA 对 ====================

COUPON_QA = [
    {
        "question": "济南市2025年"泉城购"消费券包括哪些类型？",
        "answer": ""泉城购"消费券主要包括：1. 零售消费券；2. 餐饮消费券；3. 新车首保消费券。消费券通过线上平台发放，市民可以在指定商家使用。具体使用规则请关注济南市商务局官方网站或"泉城购"服务平台。",
        "category": "消费券",
        "keywords": "消费券类型,泉城购,券种类",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "新车首保消费券是什么？谁可以领取？",
        "answer": "新车首保消费券是针对在济南市购买新车并进行首次保养的消费者发放的补贴。符合条件的车主可以在指定的汽车服务商户进行首保时使用消费券抵扣费用。具体领取条件和使用规则请关注活动公告。",
        "category": "消费券",
        "keywords": "首保消费券,新车首保,汽车保养券",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    }
]

# ==================== 数码产品补贴 QA 对 ====================

DIGITAL_QA = [
    {
        "question": "济南市手机、平板、智能手表购新补贴包括哪些产品？",
        "answer": "补贴产品包括：1. 手机；2. 平板电脑；3. 智能手表；4. 智能手环。这些产品需要符合相关技术标准和补贴条件，具体产品型号以活动页面公布为准。",
        "category": "数码产品补贴",
        "keywords": "手机补贴,平板补贴,智能手表,数码产品",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "购买手机、平板、智能手表有什么补贴标准？",
        "answer": "具体补贴标准根据山东省和济南市的实施细则执行。一般根据产品价格区间设定不同的补贴比例或固定金额。建议查看《济南市2025年手机、平板、智能手表（手环）购新补贴实施细则》或《山东省手机、平板、智能手表（手环）购新补贴实施细则》了解详细标准。",
        "category": "数码产品补贴",
        "keywords": "补贴标准,手机补贴金额,数码补贴",
        "difficulty_level": 3,
        "query_type": "informational",
        "verified": True
    }
]

# ==================== 通用政策 QA 对 ====================

GENERAL_QA = [
    {
        "question": "如何查询济南市最新的消费补贴政策？",
        "answer": "可以通过以下渠道查询：1. 济南市商务局官方网站；2. 济南市发展和改革委员会官网；3. 济南市财政局官网；4. "泉城购"服务平台；5. 关注"齐鲁银行"、"济南商务"等官方微信公众号。建议定期关注官方渠道，以获取最新政策信息。",
        "category": "通用政策",
        "keywords": "政策查询,信息获取,官方渠道",
        "difficulty_level": 1,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "如果补贴申请被退回怎么办？",
        "answer": "如果申请被退回：1. 及时登录平台查看退回原因；2. 根据提示修改资料；3. 务必在规定时间内完成修改（通常需要在规定截止日期前）；4. 重新提交审核。如果到期审核依旧不通过，将不予承兑。建议仔细核对所有资料，确保照片清晰完整、信息准确无误。",
        "category": "通用政策",
        "keywords": "申请被退回,资料修改,审核不通过",
        "difficulty_level": 2,
        "query_type": "procedural",
        "verified": True
    },
    {
        "question": "补贴什么时候能到账？",
        "answer": "补贴到账时间：1. 审核通过后会在官方网站进行公示（通常5个工作日）；2. 公示期满且无异议后，按公示结果发放补贴；3. 补贴将发放至申请时提交的银行卡中；4. 具体到账时间可能因审核进度和资金拨付情况而有所不同。建议定期查询申请进度。",
        "category": "通用政策",
        "keywords": "到账时间,补贴发放,何时到账",
        "difficulty_level": 2,
        "query_type": "informational",
        "verified": True
    },
    {
        "question": "提供虚假信息申请补贴会有什么后果？",
        "answer": "提供虚假信息骗取财政补贴的后果：1. 取消补贴资格；2. 追缴已发放的补贴资金；3. 依法追究法律责任；4. 可能影响个人信用记录。申请人要对所提交资料的真实性负责，严禁通过虚假、伪造材料骗取补贴。",
        "category": "通用政策",
        "keywords": "虚假信息,法律后果,骗取补贴",
        "difficulty_level": 1,
        "query_type": "informational",
        "verified": True
    }
]

# ==================== 汇总所有 QA 对 ====================

ALL_QA_PAIRS = {
    "car_subsidy": CAR_SUBSIDY_QA,
    "appliance": APPLIANCE_QA,
    "coupon": COUPON_QA,
    "digital": DIGITAL_QA,
    "general": GENERAL_QA
}

# ==================== 导出为 JSON ====================

def export_qa_to_json(output_file="policy_qa_初始数据.json"):
    """导出QA对为JSON格式"""
    all_qa = []
    for category_name, qa_list in ALL_QA_PAIRS.items():
        all_qa.extend(qa_list)

    data = {
        "metadata": {
            "name": "济南市政务智能问答初始QA数据",
            "version": "1.0.0",
            "description": "基于2025年济南市实际政策生成的高质量问答对",
            "total_qa_pairs": len(all_qa),
            "categories": list(ALL_QA_PAIRS.keys()),
            "created_at": "2025-11-09"
        },
        "qa_pairs": all_qa
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已导出 {len(all_qa)} 个QA对到 {output_file}")
    return output_file


if __name__ == "__main__":
    # 统计信息
    total_count = sum(len(qa_list) for qa_list in ALL_QA_PAIRS.values())
    print("=" * 60)
    print("政务智能问答初始QA数据统计")
    print("=" * 60)
    for category_name, qa_list in ALL_QA_PAIRS.items():
        print(f"{category_name:20s}: {len(qa_list):3d} 个问答对")
    print("-" * 60)
    print(f"{'总计':20s}: {total_count:3d} 个问答对")
    print("=" * 60)

    # 导出JSON
    export_qa_to_json()
