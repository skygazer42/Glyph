"""Regression cases for source jurisdiction, title recall and evidence boundaries."""

import asyncio
from calendar import monthrange
from datetime import date
import json
import time
from types import SimpleNamespace
from unittest.mock import Mock


from app.models.policy import PolicyDocument, PolicyType
from test_python_guidelines_knowledge_pipeline import load_subject_definitions


def document(title, scope, source, *, body="办理地点：区政务服务中心"):
    return PolicyDocument(
        title=title,
        content=f"资料名称：{title}\n适用地区：{scope}\n\n{body}",
        source=source,
        doc_type=PolicyType.GUIDELINE,
    )


def knowledge_agent(tool, **extra):
    cls = load_subject_definitions(
        "app/agents/pipeline/knowledge_agent.py", "KnowledgeAgent", date=date, monthrange=monthrange, **extra
    )["KnowledgeAgent"]
    return cls(tool)


def test_exact_matter_recalls_district_source_below_semantic_threshold():
    title = "投资项目代码发放及查询"
    city = document(title, "江苏省常州市", "local-city-corpus")
    district = document(title, "江苏省常州市经开区", "district-government")
    wrong_district = document(title, "江苏省常州市溧阳市", "other-government")
    calls = []

    class Tool:
        async def search(self, query, **kwargs):
            calls.append(kwargs)
            if kwargs.get("filters") == {"title": title}:
                return [city, wrong_district, district], [.83, .7, .55]
            return [city], [.83]

    agent = knowledge_agent(Tool())
    context = SimpleNamespace(
        search_variants=[], region="常州经开区"
    )
    docs, scores, _ = asyncio.run(agent._domain_aware_search(
        "常州经开区投资项目代码发放及查询在哪里办理？", context
    ))
    assert docs[0].source == "district-government"
    assert scores[0] == .55  # lexical rescue must not inflate confidence
    assert any(call.get("threshold") == 0 for call in calls)
    assert "other-government" not in {doc.source for doc in docs}


def test_title_rescue_preserves_explicit_caller_filter():
    title = "资格认证"
    source = document(title, "江苏省常州市", "approved-only")
    calls = []

    class Tool:
        async def search(self, query, **kwargs):
            calls.append(kwargs)
            return [source], [.8]

    docs, _ = asyncio.run(knowledge_agent(Tool())._search_knowledge(
        "资格认证怎么办？", filters={"source": "approved-only"}
    ))
    assert docs == [source]
    assert all(call["filters"].get("source") == "approved-only" for call in calls)


def test_existing_title_filter_is_not_replaced_by_a_broader_title():
    source = document("资格认证", "江苏省常州市", "approved-only")
    calls = []

    class Tool:
        async def search(self, query, **kwargs):
            calls.append(kwargs)
            return [source], [.8]

    asyncio.run(knowledge_agent(Tool())._search_knowledge(
        "资格认证怎么办？", filters={"title": "具体资格认证"}
    ))
    assert all(call["filters"]["title"] == "具体资格认证" for call in calls)


def test_title_filter_is_escaped_and_combined_with_source_filter():
    cls = load_subject_definitions(
        "app/knowledge/milvus.py", "MilvusStore"
    )["MilvusStore"]
    title = '项目"查询\\材料'
    result = cls._build_filter({"title": title, "source": "gov.cn"})
    assert f'title like {json.dumps("%" + title + "%", ensure_ascii=False)}' in result
    assert " && " in result


def test_title_filter_does_not_admit_unfiltered_hierarchical_hits():
    source = document("资格认证", "江苏省常州市", "filtered-source")

    class Hierarchical:
        has_index = True

        async def search(self, *args, **kwargs):
            raise AssertionError("hierarchical hits do not preserve title filters")

    cls = load_subject_definitions(
        "app/knowledge/service.py", "KnowledgeService", time=time
    )["KnowledgeService"]
    service = cls(
        SimpleNamespace(search=lambda **kwargs: ([source], [.8])),
        use_hierarchical=False,
    )
    service.hierarchical_store = Hierarchical()
    docs, _ = asyncio.run(service.search("资格认证", filters={"title": "资格认证"}))
    assert docs[0].source == "filtered-source"


def test_verified_same_business_evidence_excludes_unverified_other_business():
    old = document("购买新建住房申请公积金贷款材料", "江苏省常州市", "local")
    old.content = "来源身份：用户提供的常州原始语料解析件\n" + old.content
    official = document("购房资助申领操作指南", "江苏省常州市", "official")
    official.content += "\n说明：官方传媒第一方操作指南快照，发布主体和发布链单独核验。"

    class Tool:
        async def search(self, *args, **kwargs):
            return [old, official], [.82, .78]

    docs, scores, _ = asyncio.run(knowledge_agent(Tool())._domain_aware_search(
        "常州购房资助已婚需要上传哪些材料？", None
    ))
    assert docs == [official]
    assert scores == [.78]


def test_verified_other_business_does_not_enter_same_business_answer():
    housing = document("购房资助申领操作指南", "江苏省常州市", "housing")
    housing.content += "\n说明：官方传媒第一方操作指南快照，发布链单独核验。"
    loan = document("购买新建住房申请公积金贷款材料", "江苏省常州市", "loan")
    loan.content += "\n说明：官方公开资料快照；以现行规定为准。"

    class Tool:
        async def search(self, *args, **kwargs):
            return [loan, housing], [.82, .78]

    docs, _, _ = asyncio.run(knowledge_agent(Tool())._domain_aware_search(
        "购房资助已婚需要上传哪些材料？", None
    ))
    assert docs == [housing]


def test_real_rent_title_does_not_share_loan_business_from_four_topic_characters():
    loan = document("关于调整住房公积金贷款相关规定的通知", "常州市", "loan")
    rent = document("关于调整我市提取住房公积金支付房租政策的通知", "常州市", "rent")
    for source in (loan, rent):
        source.content += "\n说明：官方公开资料快照；以现行规定为准。"
    docs, scores = knowledge_agent(None)._prefer_verified_evidence(
        "常州住房公积金租房提取额度是多少？", [loan, rent], [.83, .78]
    )
    assert docs == [rent]
    assert scores == [.78]


def test_unrelated_official_loan_does_not_authorize_removing_rent_corpus():
    loan = document("关于调整住房公积金贷款相关规定的通知", "常州市", "loan")
    loan.content += "\n说明：官方公开资料快照；以现行规定为准。"
    rent = document("公积金租房提取条件", "常州市", "rent-corpus")
    rent.content = "来源身份：用户提供的常州原始语料解析件\n" + rent.content
    docs, _ = knowledge_agent(None)._prefer_verified_evidence(
        "常州住房公积金租房提取额度是多少？", [loan, rent], [.83, .78]
    )
    assert rent in docs


def test_unknown_business_does_not_drop_corpus_from_shared_four_characters():
    official = document("住房保障登记业务通知", "常州市", "official")
    official.content += "\n说明：官方公开资料快照；以现行规定为准。"
    original = document("住房保障腾退手续", "常州市", "original")
    original.content = "来源身份：用户提供的常州原始语料解析件\n" + original.content
    docs, _ = knowledge_agent(None)._prefer_verified_evidence(
        "住房保障腾退需要哪些手续？", [official, original], [.83, .78]
    )
    assert original in docs


def test_title_rescue_has_room_for_all_districts_before_region_selection():
    title = "投资项目代码发放及查询"
    others = [document(title, f"其他第{index}区", f"other-{index}") for index in range(7)]
    target = document(title, "江苏省常州市经开区", "target")

    class Tool:
        async def search(self, query, **kwargs):
            if kwargs.get("filters"):
                candidates = others + [target]
                count = kwargs["top_k"]
                return candidates[:count], [.8] * len(candidates[:count])
            return [others[0]], [.85]

    docs, _, _ = asyncio.run(knowledge_agent(Tool())._domain_aware_search(
        f"常州经开区{title}在哪里办理？",
        SimpleNamespace(search_variants=[], region="常州经开区"),
    ))
    assert docs[0].source == "target"


def test_missing_requested_district_does_not_return_another_district_guide():
    other = document("办事指南", "江苏省常州市金坛区", "other")
    general = document("全市政策", "江苏省常州市", "city")
    docs, scores = knowledge_agent(None)._prefer_requested_region(
        [other, general], [.85, .7], "常州经开区"
    )
    assert docs == [general]
    assert scores == [.7]
    assert knowledge_agent(None)._prefer_requested_region(
        [other], [.85], "常州经开区"
    ) == ([], [])


def test_official_scope_keeps_jingkai_applicability_after_semicolon():
    source = document(
        "居民养老办法", "常州市武进区、新北区、天宁区、钟楼区；经开区按规定职责", "pension"
    )
    docs, _ = knowledge_agent(None)._prefer_requested_region([source], [.8], "常州经开区")
    assert docs == [source]


def test_unit_snapshot_remains_available_alongside_housing_guide():
    unit = document("常州住房公开资助房源逐套快照——融创·龙宸映", "常州市", "units")
    guide = document("购房资助申领操作指南", "常州市", "guide")
    for source in (unit, guide):
        source.content += "\n说明：官方公开资料快照；以现行规定为准。"
    docs, scores = knowledge_agent(None)._prefer_verified_evidence(
        "常州购房资助融创龙宸映有哪些公开房源？", [unit, guide], [.83, .77]
    )
    assert docs == [unit, guide]
    assert scores == [.83, .77]


def test_unknown_verified_support_is_not_removed_without_business_conflict():
    unit = document("融创龙宸映专项房源数据", "常州市", "units")
    guide = document("购房资助申领操作指南", "常州市", "guide")
    for source in (unit, guide):
        source.content += "\n说明：官方公开资料快照；以现行规定为准。"
    docs, _ = knowledge_agent(None)._prefer_verified_evidence(
        "常州购房资助融创龙宸映有哪些公开房源？", [unit, guide], [.83, .77]
    )
    assert unit in docs


def test_closing_one_store_preserves_shared_collection_and_other_connection():
    disconnected = []
    cls = load_subject_definitions(
        "app/knowledge/milvus.py", "MilvusStore",
        connections=SimpleNamespace(disconnect=disconnected.append),
    )["MilvusStore"]
    shared = SimpleNamespace(release=Mock(), num_entities=20)
    first, second = object.__new__(cls), object.__new__(cls)
    for store, alias in ((first, "first"), (second, "second")):
        store.collection = shared
        store._connection_alias = alias
        store._connected = True
    first.close()
    first.close()
    assert shared.release.call_count == 0
    assert disconnected == ["first"]
    assert second.collection is shared and second._connected
    second.close()
    assert disconnected == ["first", "second"]


def test_unrelated_official_hit_does_not_suppress_matching_corpus():
    old = document("退休医保待遇申请", "江苏省常州市", "local")
    old.content = "来源身份：用户提供的常州原始语料解析件\n" + old.content
    official = document("公积金贷款申请", "江苏省常州市", "official")
    official.content += "\n说明：官方公开资料快照；后续修改以现行规定为准。"

    class Tool:
        async def search(self, *args, **kwargs):
            return [old, official], [.82, .6]

    docs, _, _ = asyncio.run(knowledge_agent(Tool())._domain_aware_search(
        "退休医保待遇需要什么材料？", None
    ))
    assert old in docs


def test_ivf_search_probes_existing_partitions_for_filtered_title():
    cls = load_subject_definitions(
        "app/knowledge/milvus.py", "MilvusStore"
    )["MilvusStore"]
    store = object.__new__(cls)
    store.collection = SimpleNamespace(
        indexes=[SimpleNamespace(params={"index_type": "IVF_FLAT", "params": {"nlist": 1024}})],
        search=Mock(return_value=[]),
    )
    store._embed_texts = lambda texts: [SimpleNamespace(tolist=lambda: [.1])]
    store.search("完整事项标题", filters={"title": "完整事项标题"})
    assert store.collection.search.call_args.kwargs["param"]["params"]["nprobe"] == 1024


def test_document_context_preserves_restrictive_parenthesis_and_date_labels():
    source = document(
        "缴费档次通知", "金坛区", "government",
        body="发布日期：2022-12-09\n缴费标准：100元、300元、1000元\n（其中100元、300元为困难群体标准）。",
    )
    settings = SimpleNamespace(system=SimpleNamespace(knowledge_max_context_per_doc=6000))
    context = knowledge_agent(None, settings=settings)._format_documents([source])
    assert "\n缴费标准：" in context
    assert "\n（其中100元、300元为困难群体标准）。" in context


def test_summary_prompt_requires_answering_eligibility_and_separating_date_roles():
    agent = knowledge_agent(None)
    prompt = agent._build_summary_prompt(
        "普通居民能否选择低档？", "eligibility", "来源原文", context_label="参考资料"
    )
    assert "先直接回答用户所问的能否" in prompt
    assert "限制人群" in prompt
    assert "发布日期不等于生效日期" in prompt
    assert "不得把不同位置的年份与月日拼接" in prompt
    assert "用户问题中的身份、金额和日期不是已经核实的事实" in prompt
