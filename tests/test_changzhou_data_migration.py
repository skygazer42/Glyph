"""Behavior checks for regional replacement and source-backed FAQ answers."""

import hashlib
import json
from pathlib import Path
from datetime import date, timedelta

import pytest

from app.knowledge.faq_responder import FAQResponder


@pytest.fixture
def faq_entry(tmp_path):
    body = "常州市参保人员可以通过官方渠道办理异地就医备案。\n"
    source = tmp_path / "official.md"
    source.write_text("# 官方办理指南\n\n## 正文\n" + body, encoding="utf-8")
    return {
        "question": "常州异地就医怎么备案？",
        "answer": body.strip(),
        "tags": ["医保"],
        "source": "https://ybj.changzhou.gov.cn/example.html",
        "region": "常州市",
        "source_title": "官方办理指南",
        "source_quote": body.strip(),
        "source_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "source_markdown_path": str(source),
        "verified_date": "2026-11-21",
    }


def responder(tmp_path, entries):
    path = tmp_path / "faq.json"
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return FAQResponder(str(path))


def test_sourced_faq_returns_auditable_document(tmp_path, faq_entry):
    result = responder(tmp_path, [faq_entry]).maybe_answer(faq_entry["question"])
    assert result is not None
    assert result.sources and result.sources[0].source == faq_entry["source"]
    assert result.metadata["region"] == "常州市"
    assert result.metadata["source_body_sha256"] == faq_entry["source_body_sha256"]


@pytest.mark.parametrize(
    "change",
    [
        {"source": ""},
        {"source": "https://example.com/policy"},
        {"region": "济南市"},
        {"source_quote": "不存在的金额标准"},
        {"source_body_sha256": "0" * 64},
        {"source_markdown_path": "missing.md"},
        {"valid_until": (date.today() - timedelta(days=1)).isoformat()},
        {"valid_from": (date.today() + timedelta(days=1)).isoformat()},
    ],
)
def test_unverified_wrong_region_or_outdated_faq_abstains(tmp_path, faq_entry, change):
    faq_entry.update(change)
    assert responder(tmp_path, [faq_entry]).maybe_answer(faq_entry["question"]) is None


def test_changing_city_in_similar_question_does_not_reuse_local_faq(
    tmp_path, faq_entry
):
    faq_entry["question"] = (
        "在常州缴纳职工医保以后到外地看病需要如何办理异地就医备案手续？"
    )
    query = faq_entry["question"].replace("常州", "济南")
    assert responder(tmp_path, [faq_entry]).maybe_answer(query) is None


def test_different_year_does_not_reuse_annual_faq(tmp_path, faq_entry):
    faq_entry["question"] = "常州2026年度居民医疗保险缴费和待遇的办理条件是什么？"
    assert (
        responder(tmp_path, [faq_entry]).maybe_answer(
            faq_entry["question"].replace("2026", "2025")
        )
        is None
    )


def test_legacy_unsourced_faq_never_short_circuits_retrieval(tmp_path):
    entry = {"question": "创业补贴条件是什么？", "answer": "员工少于50人"}
    assert responder(tmp_path, [entry]).maybe_answer(entry["question"]) is None


def test_district_specific_faq_does_not_extend_to_another_district(tmp_path, faq_entry):
    faq_entry["region"] = "江苏省常州市钟楼区"
    faq_entry["question"] = "常州钟楼区居民医疗保险缴费和待遇的办理条件是什么？"
    assert (
        responder(tmp_path, [faq_entry]).maybe_answer(
            faq_entry["question"].replace("钟楼", "武进")
        )
        is None
    )


def test_invalid_faq_calendar_date_is_reported(tmp_path, faq_entry):
    faq_entry["valid_until"] = "2026-02-30"
    with pytest.raises(ValueError):
        responder(tmp_path, [faq_entry])


@pytest.mark.parametrize(
    "original, changed",
    [
        (
            "常州有未结清公转商贷款还能提装修或物业费吗？",
            "常州没有未结清公转商贷款还能提装修或物业费吗？",
        ),
        (
            "婚前房配偶不在产权证上能申请常州装修提取吗？",
            "婚前房配偶在产权证上能申请常州装修提取吗？",
        ),
    ],
)
def test_opposite_eligibility_conditions_never_fuzzy_match(
    tmp_path, faq_entry, original, changed
):
    faq_entry["question"] = original
    assert responder(tmp_path, [faq_entry]).maybe_answer(changed) is None


def test_question_punctuation_can_vary_without_changing_facts(tmp_path, faq_entry):
    assert (
        responder(tmp_path, [faq_entry]).maybe_answer(" 常州异地就医怎么备案? ")
        is not None
    )


def test_running_responder_reloads_new_source_backed_question(tmp_path, faq_entry):
    matcher = responder(tmp_path, [faq_entry])
    added = {**faq_entry, "question": "常州新增医保办理渠道有哪些？"}
    matcher.data_path.write_text(json.dumps([faq_entry, added], ensure_ascii=False), encoding="utf-8")
    answer = matcher.maybe_answer(added["question"])
    assert answer is not None
    assert answer.answer == added["answer"]
    assert answer.metadata["route"] == "faq_cache"


def test_running_responder_replaces_old_answer(tmp_path, faq_entry):
    matcher = responder(tmp_path, [faq_entry])
    updated = {**faq_entry, "answer": "更新后的官方办理答复。"}
    matcher.data_path.write_text(json.dumps([updated], ensure_ascii=False), encoding="utf-8")
    answer = matcher.maybe_answer(faq_entry["question"])
    assert answer is not None
    assert answer.answer == updated["answer"]


@pytest.mark.parametrize("replacement", ["invalid_source", "invalid_json", "deleted"])
def test_invalid_update_does_not_continue_serving_old_faq(tmp_path, faq_entry, replacement):
    matcher = responder(tmp_path, [faq_entry])
    assert matcher.maybe_answer(faq_entry["question"]) is not None
    if replacement == "invalid_source":
        updated = {**faq_entry, "source_body_sha256": "0" * 64}
        matcher.data_path.write_text(json.dumps([updated]), encoding="utf-8")
    elif replacement == "invalid_json":
        matcher.data_path.write_text("[{", encoding="utf-8")
    else:
        matcher.data_path.unlink()
    assert matcher.maybe_answer(faq_entry["question"]) is None


def test_running_responder_rejects_changed_source_evidence(tmp_path, faq_entry):
    matcher = responder(tmp_path, [faq_entry])
    Path(faq_entry["source_markdown_path"]).write_text("# 新版\n\n## 正文\n原证据已变更。\n", encoding="utf-8")
    assert matcher.maybe_answer(faq_entry["question"]) is None
