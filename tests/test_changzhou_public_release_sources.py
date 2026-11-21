"""Non-government official releases require exact identity and frozen evidence."""

import hashlib
import json
from pathlib import Path

import pytest

from scripts import official_policy_data as subject

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def housing_source(tmp_path, monkeypatch):
    catalog = ROOT / "resources/data/policy_catalog/changzhou_alignment_housing_round2_20261121.json"
    item = json.loads(catalog.read_text(encoding="utf-8"))[0]
    for field in ("raw_path", "markdown_path", "authority_chain_manifest"):
        destination = tmp_path / item[field]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / item[field]).read_bytes())
    path = tmp_path / "resources/data/policy_catalog/test_release.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(subject, "CATALOGS", [path.name])
    return tmp_path, path, item


def test_verified_official_media_release_keeps_publisher_identity(housing_source):
    root, _, item = housing_source
    loaded = subject.load_official_policies(root)
    assert len(loaded) == 1
    assert loaded[0]["issuer"] == "常州市新闻传媒中心（常观）"
    assert loaded[0]["body"].strip()
    assert loaded[0]["url"] == item["url"]


@pytest.mark.parametrize("field", ["raw_path", "authority_chain_manifest"])
def test_changed_evidence_cannot_reuse_a_dated_approval(housing_source, field):
    root, _, item = housing_source
    evidence = root / item[field]
    evidence.write_bytes(evidence.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="[Uu]nverified|[Cc]hanged"):
        subject.load_official_policies(root)


def test_a_neighboring_unverified_url_is_still_rejected(housing_source):
    root, path, item = housing_source
    item["url"] += "-unverified"
    path.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Expected official source"):
        subject.load_official_policies(root)


@pytest.fixture
def pinned_platform_snapshot(tmp_path, monkeypatch):
    catalog = ROOT / "resources/data/policy_catalog/changzhou_alignment_housing_round2_20261121.json"
    item = next(
        row for row in json.loads(catalog.read_text(encoding="utf-8"))
        if row.get("source_type") == "first_party_official_housing_platform"
    )
    for field in ("raw_path", "markdown_path", "authority_chain_manifest"):
        destination = tmp_path / item[field]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / item[field]).read_bytes())
    approvals = tmp_path / "resources/data/policy_catalog/snapshot_approvals.json"
    approvals.parent.mkdir(parents=True, exist_ok=True)
    approvals.write_text(json.dumps({item["url"]: [
        hashlib.sha256((tmp_path / item["raw_path"]).read_bytes()).hexdigest(),
        hashlib.sha256((tmp_path / item["authority_chain_manifest"]).read_bytes()).hexdigest(),
    ]}), encoding="utf-8")
    catalog_path = approvals.parent / "snapshot_catalog.json"
    catalog_path.write_text(json.dumps([item]), encoding="utf-8")
    monkeypatch.setattr(subject, "CATALOGS", [catalog_path.name])
    monkeypatch.setattr(subject, "VERIFIED_PUBLIC_RELEASES", {})
    monkeypatch.setattr(subject, "PUBLIC_SNAPSHOT_APPROVALS", (
        str(approvals.relative_to(tmp_path)),
        hashlib.sha256(approvals.read_bytes()).hexdigest(),
    ), raising=False)
    return tmp_path, approvals, catalog_path, item


def test_pinned_snapshot_manifest_accepts_exact_platform_evidence(pinned_platform_snapshot):
    root, _, _, item = pinned_platform_snapshot
    loaded = subject.load_official_policies(root)
    assert [row["url"] for row in loaded] == [item["url"]]


def test_changed_snapshot_approval_manifest_cannot_expand_trust(pinned_platform_snapshot):
    root, approvals, _, _ = pinned_platform_snapshot
    approvals.write_bytes(approvals.read_bytes() + b" ")
    with pytest.raises(ValueError, match="[Aa]pproval manifest"):
        subject.load_official_policies(root)


def test_pinned_approval_does_not_accept_changed_raw_snapshot(pinned_platform_snapshot):
    root, _, _, item = pinned_platform_snapshot
    raw = root / item["raw_path"]
    raw.write_bytes(raw.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Unverified public release evidence"):
        subject.load_official_policies(root)


def test_pinned_approval_does_not_accept_another_project_url(pinned_platform_snapshot):
    root, _, catalog_path, item = pinned_platform_snapshot
    item["url"] += "?id=unreviewed"
    catalog_path.write_text(json.dumps([item]), encoding="utf-8")
    with pytest.raises(ValueError, match="Expected official source"):
        subject.load_official_policies(root)
