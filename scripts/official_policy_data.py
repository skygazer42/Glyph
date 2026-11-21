"""Read the accepted official catalogs shared by import and SQL seed commands."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

CATALOGS = [
    "livelihood_20261121.json",
    "employment_business_20261121.json",
    "business_expansion_20261121.json",
    "social_expansion_20261121.json",
    "rules_2026_national.json",
    "national_faq_20261121.json",
    "changzhou_housing_20261121.json",
    "changzhou_services_20261121.json",
    "changzhou_vehicle_finance_20261121.json",
    "changzhou_benefit_finance_20261121.json",
    "changzhou_provident_finance_20261121.json",
    "changzhou_insurance_supplement_20261121.json",
    "changzhou_financial_accuracy_20261121.json",
    "changzhou_official_followup_20261121.json",
    "changzhou_alignment_welfare_20261121.json",
    "changzhou_alignment_insurance_20261121.json",
    "changzhou_alignment_quality_20261121.json",
    "changzhou_alignment_provident_round2_20261121.json",
    "changzhou_alignment_retirement_round2_20261121.json",
    "changzhou_alignment_welfare_round2_20261121.json",
    "changzhou_alignment_housing_round2_20261121.json",
    "changzhou_alignment_quality_round2_20261121.json",
    "changzhou_alignment_housing_units_round2_20261121.json",
    "changzhou_alignment_law_round3_20261121.json",
    "changzhou_alignment_pension_round3_20261121.json",
    "changzhou_alignment_provident_round3_20261121.json",
    "changzhou_alignment_medical_round4_20261121.json",
]

# These exact public assets were independently traced to the product platform.
# This is a dated snapshot approval, not a general non-government host allowlist.
FIRST_PARTY_CONTRACTS = {
    "https://cx-hmb.zkydib.com/js27/assets/js/agreement~index~myAccount.9c910c51.js": "b6471b1a71f2c43aa8070430e1c0460eef5a521bb5dbb703cbef5f853db6131a",
    "https://cx-hmb.zkydib.com/js26/assets/js/agreement~index~myAccount.e1e167bf.js": "2711a9fbddbfb59990d3d13e022bb4b622af20299b92b054aa45792036f28d84",
}

# Individually verified public releases. Host-wide trust would accept unrelated
# social posts or platform data, so approval binds URL, bytes and authority chain.
VERIFIED_PUBLIC_RELEASES = {
    "https://mp.weixin.qq.com/s/Jc6Gvnc29fwd4mVKqkNuIw": (
        "d8cffb06b07bbf86a9196c172cd95274093de0ebf749aea7a35aff92a05f5d42",
        "566bd478c839e2dfbf8c440c6b72c7b42c08c7aa855972322ad71d34fe0ce0c3",
    ),
    "https://www.zwfc.com/website/gfzz/home": (
        "b39fba96925a6daf8e08fc644ff32f879c0c7f77808ca317745fba5e59fe7b49",
        "566bd478c839e2dfbf8c440c6b72c7b42c08c7aa855972322ad71d34fe0ce0c3",
    ),
    "https://www.zwfc.com/website/gfzz/homeReady": (
        "b39fba96925a6daf8e08fc644ff32f879c0c7f77808ca317745fba5e59fe7b49",
        "566bd478c839e2dfbf8c440c6b72c7b42c08c7aa855972322ad71d34fe0ce0c3",
    ),
}

PUBLIC_SNAPSHOT_APPROVALS = (
    "resources/data/policy_catalog/changzhou_housing_snapshot_approvals_20261121.json",
    "e7266627a8caf963abaa8afc2ad2135f858d5b623d42ec472c949241a04f411c",
)


def load_official_policies(root: Path) -> list[dict]:
    """Validate frozen text and jurisdiction before accepting a source for import."""
    accepted: dict[str, dict] = {}
    approval_path, approval_sha256 = PUBLIC_SNAPSHOT_APPROVALS
    public_releases = dict(VERIFIED_PUBLIC_RELEASES)
    approval_file = root / approval_path
    if approval_file.is_file():
        approval_bytes = approval_file.read_bytes()
        if hashlib.sha256(approval_bytes).hexdigest() != approval_sha256:
            raise ValueError("Public snapshot approval manifest changed")
        public_releases.update(json.loads(approval_bytes))
    for name in CATALOGS:
        path = root / "resources/data/policy_catalog" / name
        for item in json.loads(path.read_text(encoding="utf-8-sig")):
            scope = item["scope"]
            if scope not in {"全国", "江苏", "江苏省"} and "常州" not in scope:
                continue
            host = urlparse(item["url"]).hostname
            official = host is not None and (
                host.endswith(".gov.cn") or host in {"lt.cas.cn", "www.cdpf.org.cn"}
            )
            contract = (
                item["url"] in FIRST_PARTY_CONTRACTS
                and item.get("source_type") == "first_party_insurance_product"
                and item.get("authority_chain_verified") is True
            )
            public_release = item["url"] in public_releases
            if not official and not contract and not public_release:
                raise ValueError(f"Expected official source: {item['title']}")
            raw = root / item["raw_path"]
            source = root / item["markdown_path"]
            if not raw.is_file() or not source.is_file():
                raise FileNotFoundError(item["title"])
            if public_release:
                expected_raw, expected_chain = public_releases[item["url"]]
                chain_path = root / item["authority_chain_manifest"]
                if (
                    hashlib.sha256(raw.read_bytes()).hexdigest() != expected_raw
                    or hashlib.sha256(chain_path.read_bytes()).hexdigest() != expected_chain
                ):
                    raise ValueError(f"Unverified public release evidence: {item['title']}")
            if contract:
                if hashlib.sha256(raw.read_bytes()).hexdigest() != FIRST_PARTY_CONTRACTS[item["url"]]:
                    raise ValueError(f"Unverified insurance asset bytes: {item['title']}")
                chain = json.loads((root / item["authority_chain_manifest"]).read_text(encoding="utf-8"))
                if chain["verified_host"] != host or not urlparse(chain["official_2026_entry"]["page_url"]).hostname.endswith(".gov.cn"):
                    raise ValueError(f"Missing verified insurance authority chain: {item['title']}")
            markdown = source.read_text(encoding="utf-8-sig")
            body = markdown.split("\n## 正文\n", 1)[1].strip() + "\n"
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != item["body_sha256"]:
                raise ValueError(f"Source hash changed: {item['title']}")
            for field in ["published_date", "issued_date"]:
                value = item.get(field)
                if value is not None and date.fromisoformat(value) > date.today():
                    raise ValueError(f"Future publication: {item['title']}")
            prior = accepted.get(item["url"])
            if prior is not None and prior["body_sha256"] != item["body_sha256"]:
                raise ValueError(f"Conflicting versions: {item['url']}")
            if prior is None:
                accepted[item["url"]] = {**item, "body": body, "markdown": markdown}
    return list(accepted.values())


def load_curated_faq(root: Path, policies: list[dict]) -> list[dict]:
    """Reject unsupported Q&A, ambiguous duplicates and changed source quotations."""
    sources = {item["url"]: item for item in policies}
    accepted: dict[str, dict] = {}
    for name in [
        "changzhou_housing_20261121.json",
        "changzhou_services_20261121.json",
        "national_2026_20261121.json",
        "changzhou_vehicle_finance_20261121.json",
        "changzhou_benefit_finance_20261121.json",
        "changzhou_provident_finance_20261121.json",
        "changzhou_financial_accuracy_20261121.json",
        "changzhou_official_followup_20261121.json",
        "changzhou_alignment_round2_20261121.json",
    ]:
        path = root / "resources/faq" / name
        if not path.exists():
            continue
        for entry in json.loads(path.read_text(encoding="utf-8-sig")):
            source = sources[entry["source"]]
            evidence = root / entry["source_markdown_path"]
            evidence_body = (
                evidence.read_text(encoding="utf-8-sig")
                .split("\n## 正文\n", 1)[1]
                .strip()
                + "\n"
            )
            if (
                entry["source_body_sha256"] != source["body_sha256"]
                or entry["source_quote"] not in source["body"]
                or hashlib.sha256(evidence_body.encode("utf-8")).hexdigest()
                != source["body_sha256"]
                or entry["source_quote"] not in evidence_body
            ):
                raise ValueError(f"Unverified FAQ evidence: {entry['question']}")
            prior = accepted.get(entry["question"])
            if prior is not None and prior["answer"] != entry["answer"]:
                raise ValueError(f"Conflicting FAQ: {entry['question']}")
            period = {}
            for source_key, target_key in [
                ("effective_date", "valid_from"),
                ("expires_date", "valid_until"),
            ]:
                value = source.get(source_key)
                if value is not None:
                    period[target_key] = value
            accepted[entry["question"]] = {**period, **entry}
    return list(accepted.values())
