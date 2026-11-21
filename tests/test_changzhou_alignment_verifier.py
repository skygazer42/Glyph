"""Guard whole-library verification when real user corpus joins official sources."""

import json

import pytest

from scripts.verify_changzhou_migration import (
    expected_vector_ids,
    load_corpus_manifest,
    read_library_rows,
    source_type_counts,
    verify_corpus_record_counts,
)


def test_source_totals_distinguish_government_insurer_and_public_institutions():
    policies = [
        {"url": "https://ybj.changzhou.gov.cn/notice.html"},
        {"url": "https://cx-hmb.zkydib.com/js27/terms.pdf",
         "source_type": "first_party_insurance_product"},
        {"url": "https://www.cdpf.org.cn/public.html"},
        {"url": "https://mp.weixin.qq.com/s/verified", "source_type": "official_media_release"},
        {"url": "https://www.zwfc.com/website/gfzz/home", "source_type": "first_party_official_housing_platform"},
    ]

    assert source_type_counts(policies) == {
        "official_government_sources": 1,
        "first_party_insurance_sources": 1,
        "official_public_institution_sources": 1,
        "official_media_sources": 1,
        "official_housing_platform_sources": 1,
    }


class _Iterator:
    def __init__(self, pages):
        self.pages = iter(pages)
        self.closed = False

    def next(self):
        return next(self.pages, [])

    def close(self):
        self.closed = True


class _Collection:
    def __init__(self, pages):
        self.iterator = _Iterator(pages)
        self.options = None

    def query_iterator(self, **options):
        self.options = options
        return self.iterator


def test_library_scan_includes_rows_after_old_result_window():
    pages = [
        [{"id": str(index)} for index in range(start, min(start + 1000, 17001))]
        for start in range(0, 17001, 1000)
    ]
    collection = _Collection(pages)

    actual = read_library_rows(collection)

    assert len(actual) == 17001
    assert "17000" in actual
    assert collection.iterator.closed
    assert collection.options["consistency_level"] == "Strong"
    assert collection.options["limit"] == -1


def test_library_scan_rejects_duplicate_primary_keys_and_closes_iterator():
    collection = _Collection([[{"id": "a"}], [{"id": "a"}]])

    with pytest.raises(ValueError, match="Duplicate live vector"):
        read_library_rows(collection)

    assert collection.iterator.closed


def test_expected_ids_include_corpus_without_weakening_pollution_check():
    official = [{"vector_ids": ["official-1", "official-2"]}]
    corpus = [{"vector_ids": ["corpus-1"]}]

    expected = expected_vector_ids(official, corpus)

    assert expected == {"official-1", "official-2", "corpus-1"}
    assert expected != expected | {"unexpected-vector"}


def test_cross_source_vector_id_collisions_are_rejected():
    with pytest.raises(ValueError, match="Duplicate manifest vector"):
        expected_vector_ids(
            [{"vector_ids": ["shared"]}], [{"vector_ids": ["shared"]}]
        )


def test_absent_corpus_manifest_keeps_official_only_verification(tmp_path):
    assert load_corpus_manifest(tmp_path) is None


@pytest.mark.parametrize("status", ["importing", "failed", None])
def test_partial_corpus_manifest_cannot_be_reported_as_verified(tmp_path, status):
    path = tmp_path / "import_changzhou_corpus_20261121.json"
    path.write_text(json.dumps({"status": status, "files": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="Corpus import is not verified"):
        load_corpus_manifest(tmp_path)


def test_verified_corpus_manifest_requires_file_evidence(tmp_path):
    path = tmp_path / "import_changzhou_corpus_20261121.json"
    path.write_text(
        json.dumps({"status": "verified", "files": [{"vector_ids": ["a"]}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Incomplete corpus file"):
        load_corpus_manifest(tmp_path)


def test_corpus_counts_exclude_history_and_detect_missing_imported_records(tmp_path):
    records_path = (
        tmp_path / "resources/data/process/changzhou_user_corpus_20261121/records.jsonl"
    )
    records_path.parent.mkdir(parents=True)
    records = [
        {"id": "a", "raw_path": "01/items.txt", "raw_sha256": "digest", "eligible_for_retrieval": True},
        {"id": "b", "raw_path": "01/items.txt", "raw_sha256": "digest", "eligible_for_retrieval": True},
        {"id": "old", "raw_path": "01/items.txt", "raw_sha256": "digest", "eligible_for_retrieval": False},
    ]
    records_path.write_text(
        "\n".join(json.dumps(row) for row in records), encoding="utf-8"
    )
    files = [{
        "raw_path": "resources/data/raw/changzhou_user_corpus_20261121/01/items.txt",
        "raw_sha256": "digest", "records_count": 2,
    }]
    verify_corpus_record_counts(tmp_path, files)

    files[0]["records_count"] = 1
    with pytest.raises(ValueError, match="Corpus record count mismatch"):
        verify_corpus_record_counts(tmp_path, files)


def test_corpus_counts_reject_omitted_source_files(tmp_path):
    records_path = (
        tmp_path / "resources/data/process/changzhou_user_corpus_20261121/records.jsonl"
    )
    records_path.parent.mkdir(parents=True)
    records_path.write_text(json.dumps({
        "id": "a", "raw_path": "missing.txt", "raw_sha256": "digest",
        "eligible_for_retrieval": True,
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="Corpus record file set mismatch"):
        verify_corpus_record_counts(tmp_path, [])
