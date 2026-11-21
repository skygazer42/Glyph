"""Prepare exact file and vector identities for the regional data retirement."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

from scripts.snapshot_changzhou_migration import ARCHIVE, ROOT, write_json


def main() -> None:
    """Classify by catalog jurisdiction, keeping national texts on local websites."""
    output = ARCHIVE / "retirement_plan.json"
    if output.exists():
        print("Existing frozen retirement plan:", output)
        return
    catalog = ROOT / "resources/data/policy_catalog"
    policies = []
    for name in ["import_20261121.json", "import_expansion_20261121.json"]:
        policies.extend(
            json.loads((catalog / name).read_text(encoding="utf-8"))["policies"]
        )
    local = [item for item in policies if item["scope"] != "全国"]
    vector_ids = {identity for item in local for identity in item["vector_ids"]}
    national_ids = {
        identity
        for item in policies
        if item["scope"] == "全国"
        for identity in item["vector_ids"]
    }
    snapshot = json.loads((ARCHIVE / "milvus_before.json").read_text(encoding="utf-8"))
    legacy = [
        row for row in snapshot["records"] if row["id"] not in vector_ids | national_ids
    ]
    # All twelve pre-catalog vectors were reviewed against the original Jinan/Shandong files.
    assert len(legacy) == 12
    assert all(not row["source"].startswith("http") for row in legacy)
    vector_ids.update(row["id"] for row in legacy)

    paths: set[Path] = set()
    for item in local:
        paths.update(
            ROOT / item[field] for field in ["raw_path", "markdown_path", "upload_path"]
        )
    for name in ["md2025年家电和数码以旧换新政策文件", "md市级消费活动政策"]:
        paths.add(ROOT / "resources/data/process" / name)
    paths.update(
        path for path in (ROOT / "resources/data/raw").iterdir() if path.is_file()
    )
    paths.update(
        [
            ROOT / "resources/data/raw/official_20261121_expansion/regional",
            ROOT / "resources/data/process/official_20261121_expansion/regional",
            ROOT / "resources/data/lightrag",
        ]
    )
    paths.update(
        path
        for path in (ROOT / "rules").glob("*.yaml")
        if not path.name.startswith(("Rule_National_", "Rule_Changzhou_"))
    )
    for path in (ROOT / "uploads").iterdir():
        if path.is_file() and (
            "济南" in path.name or path.name in ["以旧换新.docx", "消费活动.docx"]
        ):
            paths.add(path)
    uploads = [path for path in paths if path.parent == ROOT / "uploads"]
    for source in uploads:
        for directory, suffix in [
            ("uploads/parsed", ".md"),
            ("uploads/.status/parsed", ".json"),
            ("uploads/.status/embedded", ".json"),
            ("uploads/.status/processing", ".json"),
        ]:
            paths.add(ROOT / directory / (source.name + suffix))
    # Retire static unsupported seed data; source-backed replacements are generated separately.
    paths.update(
        ROOT / path
        for path in [
            "resources/sql/policy_demo.sql",
            "resources/faq/qa_pairs.json",
            "resources/data/sample_policies.json",
            "resources/data/user_profiles.json",
            "resources/database/seed_data/policy_qa_初始数据.json",
            "resources/database/seed_data/policy_qa_seed.py",
            "resources/database/seed_data/generate_qa_data.py",
        ]
    )
    paths = {path for path in paths if path.exists()}
    paths = {
        path for path in paths if not any(parent in paths for parent in path.parents)
    }
    file_moves = []
    for source in sorted(paths):
        assert source.resolve().is_relative_to(ROOT.resolve())
        target = ARCHIVE / "files" / source.relative_to(ROOT)
        files = [source] if source.is_file() else list(source.rglob("*"))
        hashes = {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in files
            if path.is_file()
        }
        file_moves.append(
            {
                "source": str(source),
                "target": str(target),
                "relative_path": source.relative_to(ROOT).as_posix(),
                "sha256": hashes,
            }
        )
    write_json(
        output,
        {
            "retired_local_policies": len(local),
            "retired_legacy_vectors": len(legacy),
            "retired_vector_ids": sorted(vector_ids),
            "retained_national_ids": sorted(national_ids),
            "file_moves": file_moves,
        },
    )
    print(
        json.dumps(
            {
                "retired_local_policies": len(local),
                "retired_vectors": len(vector_ids),
                "retained_national_vectors": len(national_ids),
                "file_moves": len(file_moves),
            }
        )
    )


if __name__ == "__main__":
    main()
