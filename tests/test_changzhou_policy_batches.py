"""Official imports batch across source boundaries and publish only verified data."""

import json
from types import SimpleNamespace

import pytest

from scripts.import_changzhou_policies import build_source_header, import_document_groups, validate_prior_source_ids


def document(index, content=None):
    return SimpleNamespace(
        id=f"stable-{index}", title=f"真实事项{index}",
        content=f"完整正文{index}" if content is None else content,
        source=f"https://example.gov.cn/source/{index}",
    )


def row(doc):
    return {field: str(getattr(doc, field)) for field in ("id", "title", "content", "source")}


class Collection:
    def __init__(self, existing=(), corrupt_after_flush=False):
        self.rows = {str(doc.id): row(doc) for doc in existing}
        self.flushes = 0
        self.queries = []
        self.corrupt_after_flush = corrupt_after_flush

    def query(self, *, expr, output_fields, limit, consistency_level):
        assert consistency_level == "Strong"
        ids = json.loads(expr.removeprefix("id in "))
        self.queries.append(ids)
        found = [dict(self.rows[identity]) for identity in ids if identity in self.rows]
        if self.flushes and self.corrupt_after_flush and found:
            found[-1]["content"] = "被截断的正文"
        return found

    def flush(self):
        self.flushes += 1


class Store:
    def __init__(self, existing=(), corrupt_after_flush=False):
        self.collection = Collection(existing, corrupt_after_flush)
        self.batches = []

    def add_documents(self, docs, *, upsert, flush):
        assert upsert is True and flush is False
        self.batches.append([str(doc.id) for doc in docs])
        self.collection.rows.update((str(doc.id), row(doc)) for doc in docs)


def test_batches_span_sources_and_skip_unchanged_documents():
    docs = [document(index) for index in range(20)]
    store = Store([docs[0], document(1, "旧正文")])
    published = []

    def publish(index):
        assert store.collection.flushes == 1
        assert all(store.collection.rows[str(doc.id)] == row(doc) for doc in docs)
        published.append(index)

    changed = import_document_groups(store, [[doc] for doc in docs], publish)
    assert changed == 19
    assert sorted(map(len, store.batches)) == [3, 16]
    assert {identity for batch in store.batches for identity in batch} == {
        str(doc.id) for doc in docs[1:]
    }
    assert published == list(range(20))
    assert store.collection.rows[str(docs[0].id)] == row(docs[0])


def test_failed_exact_readback_cannot_publish_any_source():
    store = Store(corrupt_after_flush=True)
    published = []
    with pytest.raises(RuntimeError, match="readback mismatch"):
        import_document_groups(store, [[document(1)], [document(2)]], published.append)
    assert published == []


def test_rerun_reads_and_publishes_without_embedding_or_flush():
    docs = [document(1), document(2)]
    store = Store(docs)
    published = []
    assert import_document_groups(store, [docs], published.append) == 0
    assert not store.batches
    assert store.collection.flushes == 0
    assert published == [0]
    assert len(store.collection.queries) == 2


def test_duplicate_identity_is_rejected_before_any_write():
    store = Store()
    with pytest.raises(ValueError, match="Duplicate"):
        import_document_groups(store, [[document(1)], [document(1)]], lambda index: None)
    assert not store.batches
    assert not store.collection.queries


def test_removed_or_rechunked_sources_require_explicit_retirement_review():
    receipt = {"policies": [{"url": "https://example.gov.cn/old", "vector_ids": ["retained"]}]}
    with pytest.raises(ValueError, match="withdrawal review"):
        validate_prior_source_ids(receipt, {})
    with pytest.raises(ValueError, match="withdrawal review"):
        validate_prior_source_ids(receipt, {"https://example.gov.cn/old": {"replacement"}})
    validate_prior_source_ids(receipt, {
        "https://example.gov.cn/old": {"retained"}, "https://example.gov.cn/new": {"new"},
    })


def test_unit_snapshot_header_preserves_unit_identity_and_inventory_limits():
    item = {
        "title": "公开逐套快照", "issuer": "常州住房一体化平台", "scope": "常州市",
        "document_kind": "official_platform_public_unit_snapshot",
        "source_type": "first_party_official_housing_platform",
        "snapshot_kind": "housing_unit_details", "url": "https://www.zwfc.com/website/gfzz/building?id=1",
    }
    header = build_source_header(item)
    assert "逐套" in header and "ZT" in header
    assert "不是实时可售" in header
    assert "项目记录不等于逐套房源" not in header


def test_unit_snapshot_header_preserves_granularity_and_status_limits():
    header = build_source_header({
        "title": "常州住房公开资助房源逐套快照", "issuer": "常州住房一体化平台",
        "scope": "江苏省常州市", "document_kind": "official_platform_public_unit_snapshot",
        "url": "https://www.zwfc.com/website/gfzz/building?id=reviewed",
        "source_type": "first_party_official_housing_platform",
        "snapshot_kind": "housing_unit_details",
    })
    assert "逐套列表" in header
    assert "项目记录不等于逐套房源" not in header
    assert "实时可售" in header and "ZT" in header


def test_source_header_keeps_explicit_effective_period_for_current_answers():
    item = {
        "title": "历史期间标准", "issuer": "常州市医疗保障局", "scope": "常州市",
        "document_kind": "official_policy", "url": "https://www.changzhou.gov.cn/period",
        "published_date": "2025-06-30", "effective_date": "2025-07-01", "expires_date": "2026-06-30",
    }
    header = build_source_header(item)
    assert "施行日期：2025-07-01\n" in header
    assert "到期日期：2026-06-30\n" in header


def test_source_header_does_not_infer_effective_dates_from_publication():
    header = build_source_header({
        "title": "发布日期与生效日期分开", "issuer": "发布机关", "scope": "常州市",
        "document_kind": "official_policy", "url": "https://www.changzhou.gov.cn/news",
        "published_date": "2026-01-01", "effective_date": None, "expires_date": None,
    })
    assert "施行日期：" not in header and "到期日期：" not in header
