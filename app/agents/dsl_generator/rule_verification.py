"""Bind reviewed policy conclusions to their rule, source and implementation versions."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
PROCESS_IMPLEMENTATIONS = {
    f"app/agents/dsl_generator/{name}": hashlib.sha256(
        (Path(__file__).resolve().parent / name).read_bytes()
    ).hexdigest()
    for name in (
        "rule_engine.py", "rule_verification.py", "trade_in_calculations.py",
        "housing_calculations.py", "provident_fund_calculations.py",
        "changzhou_vehicle_calculations.py", "changzhou_benefit_calculations.py",
    )
}


def rule_fingerprint(rule: dict[str, Any]) -> str:
    """Hash rule semantics; runtime review labels cannot certify their own contents."""
    content = {key: value for key, value in rule.items() if key not in {"verification", "is_active"}}
    encoded = yaml.safe_dump(content, allow_unicode=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RuleVerificationRegistry:
    """Read the audit ledger without treating user supplied YAML labels as evidence."""

    def __init__(self, root: Path = ROOT, *, loaded_implementations: dict[str, str] | None = None) -> None:
        self.root = root.resolve()
        self.manifest = self.root / "resources/data/policy_catalog/rules_2026_manifest.json"
        # A new registry during YAML hot reload must retain this process's code version.
        self.loaded_implementations = dict(PROCESS_IMPLEMENTATIONS if loaded_implementations is None else loaded_implementations)

    def review(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Return the recorded conclusion only while its reviewed artifacts match.

        Hashes detect version drift, not policy correctness. The recorded claims
        and limitations come from the separate, clause-by-clause official audit.
        """
        try:
            data = json.loads(self.manifest.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"rules": []}
        record = next((row for row in data["rules"] if row["rule_id"] == rule["rule_id"]), None)
        if record is None or "verification" not in record:
            return {"status": "unverified", "message": "此版本尚无官方条款核验记录；草稿试算不代表政策金额已核实。"}
        review = deepcopy(record["verification"])
        changed = record["semantic_sha256"] != rule_fingerprint(rule)
        for artifact in review["implementation_files"]:
            changed |= self.loaded_implementations.get(artifact["path"]) != artifact["sha256"]
        for artifact in review["evidence_files"] + review["implementation_files"]:
            path = (self.root / artifact["path"]).resolve()
            if not path.is_relative_to(self.root):
                changed = True
                continue
            try:
                changed |= hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]
            except OSError:
                changed = True
        if changed:
            review["status"] = "needs_review"
            review["message"] = "规则、来源或运行中的计算实现与核验版本不一致，需要重新核验；实现更新后须重启服务，才能用于对话金额答复。"
        return review
