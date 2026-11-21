"""Retire the reviewed wrong-region IDs and prove national vectors unchanged."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from pymilvus import Collection, connections

from scripts.snapshot_changzhou_migration import ARCHIVE, ROOT


def main() -> None:
    """Delete only frozen retirement IDs after checking the recovery snapshot."""
    load_dotenv(ROOT / ".env.siliconflow.local", override=True)
    os.chdir(ROOT)
    from app.config.app_config import settings

    baseline = json.loads((ARCHIVE / "milvus_before.json").read_text(encoding="utf-8"))
    plan = json.loads((ARCHIVE / "retirement_plan.json").read_text(encoding="utf-8"))
    original = {row["id"]: row for row in baseline["records"]}
    ids = plan["retired_vector_ids"]
    assert set(ids).issubset(original)
    assert baseline["collection"] == settings.database.milvus_collection_name
    alias = "changzhou-retirement"
    connections.connect(
        alias=alias,
        host=settings.database.milvus_host,
        port=str(settings.database.milvus_port),
    )
    try:
        collection = Collection(baseline["collection"], using=alias)
        collection.load()
        prior = collection.query(
            expr="id in " + json.dumps(ids),
            output_fields=["*"],
            limit=len(ids),
            consistency_level="Strong",
        )
        for row in prior:
            assert all(
                row[field] == original[row["id"]][field]
                for field in ["title", "source", "content", "doc_type"]
            )
        collection.delete("id in " + json.dumps(ids))
        collection.flush()
        assert (
            collection.query(
                expr="id in " + json.dumps(ids),
                output_fields=["id"],
                limit=len(ids),
                consistency_level="Strong",
            )
            == []
        )
        retained = collection.query(
            expr="id in " + json.dumps(plan["retained_national_ids"]),
            output_fields=["*"],
            limit=16384,
            consistency_level="Strong",
        )
        assert {row["id"] for row in retained} == set(plan["retained_national_ids"])
        for row in retained:
            assert all(
                row[field] == original[row["id"]][field]
                for field in ["title", "source", "content", "doc_type"]
            )
            assert [float(value) for value in row["embedding"]] == original[row["id"]][
                "embedding"
            ]
        report = {
            "retired_vector_count": len(ids),
            "retired_ids_absent": True,
            "retained_national_vectors": len(retained),
            "retained_vectors_unchanged": True,
            "collection": collection.name,
        }
        (ARCHIVE / "retirement_verified.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))
    finally:
        connections.disconnect(alias)


if __name__ == "__main__":
    main()
