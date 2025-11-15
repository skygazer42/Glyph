#!/usr/bin/env python3
"""
Derive FAQ tags strictly from resources/data/process content.

Rules:
- Only add tags that appear in the process markdown corpus.
- Additionally, to keep relevance, only add tags that also appear in the
  FAQ's question or answer text (to avoid unrelated tokens).

Usage:
  python scripts/build_faq_tags_from_process.py \
    --process-dir resources/data/process \
    --faq resources/faq/qa_pairs.json \
    --write

If --write is not passed, it will print a preview.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import List, Set


DEFAULT_TOKENS: List[str] = [
    # 平台/流程
    "泉城购", "领取资格", "实名认证", "核销", "支付立减", "发票", "签收", "回收", "旧家电",
    # 时间/限制
    "2个自然日", "两天", "有效期", "截止", "用完即止",
    # 金额/比例/封顶
    "2000元", "15%", "20%", "封顶", "上限",
    # 品类/范围
    "家电", "空调", "冰箱", "洗衣机", "电视", "电脑", "热水器", "油烟机", "净水器", "洗碗机", "微波炉", "电饭煲",
    "范围", "品类",
]


def read_texts(process_dir: Path) -> str:
    buf: List[str] = []
    for p in process_dir.rglob("*.md"):
        try:
            buf.append(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
    return "\n".join(buf)


def tokens_present(corpus: str, tokens: List[str]) -> Set[str]:
    present: Set[str] = set()
    for t in tokens:
        if not t:
            continue
        if t in corpus:
            present.add(t)
    return present


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--process-dir", default="resources/data/process")
    ap.add_argument("--faq", default="resources/faq/qa_pairs.json")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    process_dir = Path(args.process_dir)
    faq_path = Path(args.faq)
    if not process_dir.exists() or not faq_path.exists():
        raise SystemExit("process-dir or faq path not found")

    corpus = read_texts(process_dir)
    present = tokens_present(corpus, DEFAULT_TOKENS)

    faq = json.loads(faq_path.read_text(encoding="utf-8"))
    changed = False
    for item in faq:
        q = (item.get("question") or "").strip()
        a = (item.get("answer") or "").strip()
        base_tags: Set[str] = set(item.get("tags") or [])
        text = q + "\n" + a
        extra = {t for t in present if t in text}
        new_tags = sorted(base_tags.union(extra))
        if new_tags != item.get("tags"):
            item["tags"] = new_tags
            changed = True

    if args.write and changed:
        faq_path.write_text(json.dumps(faq, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✅ Updated tags in {faq_path}")
    else:
        print(json.dumps(faq, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

