"""Real corpus extraction keeps source identity and unsafe-version boundaries."""

import hashlib
import importlib
import json
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest
from openpyxl import Workbook


def subject():
    return importlib.import_module("scripts.changzhou_corpus_data")


def archive(tmp_path: Path, files: dict[str, bytes]) -> Path:
    entries = []
    for name, body in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        entries.append(
            {
                "path": name,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"files": entries}), encoding="utf-8"
    )
    return tmp_path


def test_service_long_fields_and_original_offsets_are_lossless(tmp_path):
    long_value = "材料不能被截断" * 1600
    text = (
        f"[事项名称：购房登记]\r\n办理材料：{long_value}\r\n"
        "补充材料继续保留\r\n在线办理地址：https://cz.jszwfw.gov.cn/item?id=1\r\n"
        "==##########==\r\n[事项名称：住房证明]\r\n办理材料：身份证\r\n"
    )
    root = archive(tmp_path, {"01政务服务事项知识/天宁区事项清单.txt": text.encode()})
    records = subject().load_corpus_records(root)
    assert len(records) == 2
    first = records[0]
    assert first["fields"]["办理材料"] == long_value + "\r\n补充材料继续保留"
    assert first["district"] == "天宁区"
    assert first["source_type"] == "user_provided_local_corpus"
    assert first["source_urls"] == ["https://cz.jszwfw.gov.cn/item?id=1"]
    loc = first["locator"]
    assert text[loc["char_start"] : loc["char_end"]] == first["content"]
    assert loc["line_start"] == 1
    assert first["version_status"] == "unverified"
    assert first["published_date"] is None


def test_district_duplicate_is_preserved_but_not_claimed_as_coverage(tmp_path):
    text = "[事项名称：同一事项]\n行使层级：市级\n==##########==\n".encode()
    root = archive(
        tmp_path,
        {
            "01政务服务事项知识/常州市事项清单.txt": text,
            "01政务服务事项知识/经开区事项清单.txt": text,
        },
    )
    records = subject().load_corpus_records(root)
    assert len(records) == 2
    city, duplicate = records
    assert city["eligible_for_retrieval"]
    assert not duplicate["eligible_for_retrieval"]
    assert duplicate["duplicate_of"] == city["raw_path"]
    assert "duplicate_mislabeled_district" in duplicate["quality_flags"]


def test_empty_faq_answer_is_not_filled_from_department(tmp_path):
    text = (
        "问题：[目前公积金中心有哪些个人线上业务渠道？]\n答案：\n"
        "来源部门：常州市住房公积金管理中心\n==##########==\n"
        "问题：[正常问题]\n答案：完整答案\n来源部门：真实部门\n"
    )
    root = archive(tmp_path, {"03常州市常见问题/常州市本级12345QA.txt": text.encode()})
    records = subject().load_corpus_records(root)
    assert records[0]["fields"]["答案"] == ""
    assert not records[0]["eligible_for_retrieval"]
    assert "empty_answer" in records[0]["quality_flags"]
    assert records[1]["eligible_for_retrieval"]


def test_one_thing_operations_use_real_separator_not_numbered_steps(tmp_path):
    guide = "[残疾人服务‘一件事’]\r\n涉及事项\r\n说明甲\r\n==##########==\r\n[退休‘一件事’]\r\n说明乙"
    operation = "残疾人服务‘一件事’操作指引\r\n1.第一步\r\n2.第二步\r\n--##########--\r\n退休‘一件事’操作指引\r\n1.申领"
    root = archive(
        tmp_path,
        {
            "02高效办成一件事/一件事指南.txt": guide.encode(),
            "02高效办成一件事/一件事操作指引.txt": operation.encode(),
        },
    )
    records = subject().load_corpus_records(root)
    assert [record["record_type"] for record in records] == [
        "one_thing_guide",
        "one_thing_guide",
        "one_thing_operation",
        "one_thing_operation",
    ]
    assert "2.第二步" in records[2]["content"]


def test_workbook_retains_cells_and_blocks_expired_long_term_label(tmp_path):
    book_path = tmp_path / "source.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "问答导出"
    sheet.append(["医保局近期上传问答"])
    sheet.append(
        ["序号", "问答标题", "问答答案", "内容生效时间", "内容失效时间", "问答提供部门"]
    )
    sheet.append(
        [
            8,
            "2025年7月1日至2026年6月30日期间，营养补助费是多少？",
            "2025年7月1日至2026年6月30日期间，全市标准为2705元。",
            "2025-07-01 00:00:00",
            "长期有效",
            "常州市医疗保障局",
        ]
    )
    sheet.append([9, "线上查询", "原表完整答案", None, "长期有效", "医保局"])
    book.save(book_path)
    root = archive(
        tmp_path / "archive",
        {"03常州市常见问题/医保局近期问答.xlsx": book_path.read_bytes()},
    )
    records = subject().load_corpus_records(root, as_of=date(2026, 11, 21))
    assert len(records) == 2
    old = records[0]
    assert old["locator"]["sheet"] == "问答导出"
    assert old["locator"]["cell_range"] == "A3:F3"
    assert old["cells"]["C3"]["value"].endswith("2705元。")
    assert old["expiry_date"] == "2026-06-30"
    assert "expired_validity_label_conflict" in old["quality_flags"]
    assert not old["eligible_for_retrieval"]
    assert records[1]["eligible_for_retrieval"]


def test_docx_paragraphs_and_tables_keep_xml_locations(tmp_path):
    doc_path = tmp_path / "document.docx"
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>第一段正文</w:t><w:tab/><w:t>制表内容</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>单元格一</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>单元格二</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    with ZipFile(doc_path, "w") as zipped:
        zipped.writestr("word/document.xml", xml)
    root = archive(
        tmp_path / "archive",
        {"05业务部门常见问题/测试正文.docx": doc_path.read_bytes()},
    )
    records = subject().load_corpus_records(root)
    assert len(records) == 1
    assert "第一段正文\t制表内容" in records[0]["content"]
    assert "单元格一\t单元格二" in records[0]["content"]
    assert records[0]["locator"]["xml_part"] == "word/document.xml"


def test_integrity_failure_is_visible_and_never_overwrites_original(tmp_path):
    root = archive(tmp_path, {"03常州市常见问题/问答.txt": "原件".encode()})
    path = root / "03常州市常见问题/问答.txt"
    path.write_text("变更原件", encoding="utf-8")
    with pytest.raises(ValueError, match="hash|sha256|checksum"):
        subject().load_corpus_records(root)
    assert path.read_text(encoding="utf-8") == "变更原件"


def test_preparation_is_deterministic_and_reports_empty_source(tmp_path):
    root = archive(
        tmp_path / "archive",
        {
            "04专题常见问答/汽车置换补贴常见问题.txt": b"",
            "03常州市常见问题/问答.txt": "问题：[真实问题]\n答案：真实答案".encode(),
        },
    )
    output = tmp_path / "processed"
    first = subject().prepare_corpus(root, output)
    snapshot = (output / "records.jsonl").read_bytes()
    second = subject().prepare_corpus(root, output)
    assert snapshot == (output / "records.jsonl").read_bytes()
    assert first == second
    assert first["record_count"] == 1
    assert first["source_file_count"] == 2
    assert first["excluded_files"][0]["reason"] == "empty_file"


def test_material_and_condition_subheadings_do_not_truncate_fields(tmp_path):
    text = (
        "[事项名称：材料完整性]\n行使层级：区级\n受理条件：条件正文\n"
        "经营限制使用农药的，还应当具备下列条件：条件原文继续\n"
        "办理材料：第一项材料\n申请说明：保留本段\n"
        "办理流程：提交、受理、决定\n在线办理地址：https://cz.jszwfw.gov.cn/item\n"
    )
    root = archive(tmp_path, {"01政务服务事项知识/天宁区事项清单.txt": text.encode()})
    fields = subject().load_corpus_records(root)[0]["fields"]
    assert fields["受理条件"].endswith(
        "经营限制使用农药的，还应当具备下列条件：条件原文继续"
    )
    assert fields["办理材料"].endswith("申请说明：保留本段")


def test_old_law_retains_original_and_cannot_enter_current_retrieval(tmp_path):
    path = "05业务部门常见问题/法规汇编/中华人民共和国行政复议法.txt"
    text = "中华人民共和国行政复议法\n（2017年9月1日第二次修正）\n第一条 原文。"
    root = archive(tmp_path, {path: text.encode()})
    old = subject().load_corpus_records(root)[0]
    assert old["content"] == text
    assert not old["eligible_for_retrieval"]
    assert old["version_status"] == "historical"
