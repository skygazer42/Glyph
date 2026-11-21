"""Export the current source-backed Changzhou Q&A for explicit SQL seeding."""

import json
from pathlib import Path

from scripts.official_policy_data import load_curated_faq, load_official_policies

ROOT = Path(__file__).resolve().parents[3]


def export_qa_to_json(output_file: str | Path | None = None) -> Path:
    """Revalidate all supporting quotations before writing the seed file."""
    target = (
        Path(__file__).with_name("policy_qa_初始数据.json")
        if output_file is None
        else Path(output_file)
    )
    pairs = load_curated_faq(ROOT, load_official_policies(ROOT))
    payload = {
        "metadata": {
            "name": "常州市政务官方资料问答",
            "collected_date": "2026-11-21",
            "total_qa_pairs": len(pairs),
            "verification_scope": "source snapshot and quote",
        },
        "qa_pairs": pairs,
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target


if __name__ == "__main__":
    print(export_qa_to_json())
