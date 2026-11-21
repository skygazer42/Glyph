"""Lossless chunking and source identity requirements for the real corpus."""

import pytest

from scripts.import_changzhou_corpus import (
    build_chunks, render_file, upload_name, validate_receipt_scope,
)


def record(**updates):
    data = {
        "id": "record-1", "title": "购房公积金提取", "content": "办理材料：身份证原件。",
        "raw_path": "01事项/常州市事项.txt", "raw_sha256": "a" * 64,
        "record_type": "service", "district": "常州市", "locator": {"line_start": 1},
        "quality_flags": [], "eligible_for_retrieval": True, "version_status": "unverified",
    }
    return {**data, **updates}


def test_long_chinese_fields_are_completely_covered_and_fit_storage():
    item = record(content="完整材料：" + "原件与复印件🙂\n" * 14000)
    chunks = build_chunks([item], "/api/knowledge/documents/source.md/source?source_version=abc")
    assert len(chunks) > 1
    assert "".join(chunk["body"] for chunk in chunks) == item["content"]
    assert all(len(chunk["content"].encode("utf-8")) < 65535 for chunk in chunks)
    assert all("时效：未核验" in chunk["content"] for chunk in chunks)
    assert all(item["raw_sha256"] in chunk["content"] for chunk in chunks)


def test_identity_is_repeatable_and_tracks_content_and_provenance():
    source = "/api/knowledge/documents/source.md/source?source_version=abc"
    first = build_chunks([record()], source)
    assert first == build_chunks([record()], source)
    assert first[0]["id"] != build_chunks([record(content="新正文")], source)[0]["id"]
    assert first[0]["id"] != build_chunks([record(raw_path="另一区/事项.txt")], source)[0]["id"]


def test_historical_and_empty_records_cannot_be_in_current_vectors():
    rows = [record(), record(id="old", eligible_for_retrieval=False, content="旧金额2705"),
            record(id="empty", content="")]
    chunks = build_chunks(rows, "/actual/source")
    assert len(chunks) == 1
    assert chunks[0]["record_id"] == "record-1"
    text = render_file(rows)
    assert "旧金额2705" not in text
    assert "原始语料解析件" in text
    assert "办理材料" in text


def test_upload_name_is_safe_short_and_path_specific():
    assert upload_name("区甲/事项.txt") == upload_name("区甲/事项.txt")
    assert upload_name("区甲/事项.txt") != upload_name("区乙/事项.txt")
    assert upload_name("区甲/事项.txt").isascii()
    assert "/" not in upload_name("区甲/事项.txt")


def test_previous_file_cannot_disappear_or_keep_replaced_vectors():
    receipt = {"files": [{"raw_path": "a.txt", "vector_ids": ["old"]}]}
    with pytest.raises(ValueError, match="withdrawal review"):
        validate_receipt_scope(receipt, {})
    with pytest.raises(ValueError, match="withdrawal review"):
        validate_receipt_scope(receipt, {"a.txt": {"new"}})
    validate_receipt_scope(receipt, {"a.txt": {"old"}, "additional.txt": {"new"}})


def test_embedding_throttle_retries_without_publishing_success(monkeypatch):
    import httpx
    from openai import RateLimitError

    from scripts.import_changzhou_corpus import upsert_batch

    class Store:
        calls = 0

        def add_documents(self, documents, **options):
            self.calls += 1
            if self.calls == 1:
                response = httpx.Response(429, request=httpx.Request("POST", "https://embedding.invalid"))
                raise RateLimitError("TPM limit", response=response, body=None)

    waits = []
    monkeypatch.setattr("scripts.import_changzhou_corpus.time.sleep", waits.append)
    store = Store()
    upsert_batch(store, ["pending"])
    assert store.calls == 2
    assert waits == [15]
