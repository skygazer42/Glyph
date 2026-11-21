"""Prepare the supplied Changzhou archive without promoting it to current policy.

The archive is read only. Text records retain exact decoded spans; workbooks and
Word files retain cell/XML locations and their original hashes. No document
content is interpreted as an instruction and no network or database is used.
"""

import argparse
import hashlib
import json
import re
from bisect import bisect_right
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "resources/data/raw/changzhou_user_corpus_20261121"
PROCESS_ROOT = ROOT / "resources/data/process/changzhou_user_corpus_20261121"
AS_OF = date(2026, 11, 21)
SEPARATOR = re.compile(r"(?m)^[=\-]{2}#{5,}[=\-]{2}[^\S\r\n]*(?:\r?\n|$)")
FIELD = re.compile(r"(?m)^([^\r\n：:\[\]]{1,24})[:：]")
URL = re.compile(r"https?://[^\s<>\[\]（）\"'，。；、]+")
DISTRICTS = ("天宁区", "新北区", "武进区", "溧阳市", "经开区", "金坛区", "钟楼区")
SERVICE_FIELDS = frozenset(
    (
        "行使层级",
        "办理形式",
        "办理地点",
        "办理时间",
        "受理条件",
        "办件类型",
        "法定办结时限",
        "承诺办结时限",
        "收费情况",
        "咨询方式",
        "监督投诉方式",
        "办理材料",
        "办理流程",
        "在线办理地址",
    )
)
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DATE_RANGE = re.compile(
    r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?"
    r"(?:至|到|—|～|~)"
    r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?期间"
)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _archive_entries(root: Path) -> list[dict[str, Any]]:
    entries = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["files"]
    for entry in entries:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Archive path escapes root: {entry['path']}")
        body = path.read_bytes()
        if _sha256(body) != entry["sha256"] or len(body) != entry["bytes"]:
            raise ValueError(f"Archive sha256/size mismatch: {entry['path']}")
    return entries


def _district(path: str) -> str:
    filename = Path(path).name
    return next((name for name in DISTRICTS if filename.startswith(name)), "常州市")


def _record(
    entry: dict[str, Any],
    content: str,
    title: str,
    record_type: str,
    locator: dict[str, Any],
    fields: dict[str, str],
    as_of: date,
) -> dict[str, Any]:
    identity = json.dumps(locator, ensure_ascii=False, sort_keys=True)
    record = {
        "id": str(
            uuid5(
                NAMESPACE_URL,
                f"glyph:changzhou-corpus:{entry['path']}:{entry['sha256']}:{identity}",
            )
        ),
        "title": title,
        "content": content,
        "raw_path": entry["path"],
        "raw_sha256": entry["sha256"],
        "source_type": "user_provided_local_corpus",
        "record_type": record_type,
        "district": _district(entry["path"]),
        "district_evidence": "archive_filename_or_city_collection; not independently verified",
        "locator": locator,
        "fields": fields,
        "source_urls": list(
            dict.fromkeys(url.rstrip("*）)。，；") for url in URL.findall(content))
        ),
        "published_date": None,
        "effective_date": None,
        "expiry_date": None,
        "referenced_years": sorted(set(re.findall(r"(?:19|20)\d{2}(?=年)", content))),
        "version_status": "unverified",
        "quality_flags": ["publisher_and_policy_freshness_not_independently_verified"],
        "eligible_for_retrieval": True,
        "usage_note": "用户提供的真实本地原件，原发布单位、采集时间和现行效力未独立核验；办理前应与现行官方依据核对。",
    }
    if "适用区域" in fields and fields["适用区域"].strip():
        record["district"] = fields["适用区域"]
        record["district_evidence"] = "original_spreadsheet_cell"
    if "答案" in fields and not fields["答案"].strip():
        record["quality_flags"].append("empty_answer")
        record["eligible_for_retrieval"] = False
    # A date in a citation or an example does not establish the record's term.
    # Explicit periods in the question itself are a supported term boundary.
    term = DATE_RANGE.search(title)
    if term:
        values = [int(value) for value in term.groups()]
        start, end = date(*values[:3]), date(*values[3:])
        record["effective_date"] = start.isoformat()
        record["expiry_date"] = end.isoformat()
        if end < as_of:
            record["version_status"] = "historical"
            record["quality_flags"].append("explicit_term_expired")
            record["eligible_for_retrieval"] = False
        if any("长期有效" in value for value in fields.values()):
            record["quality_flags"].append(
                "explicit_term_conflicts_with_long_term_label"
            )
            if end < as_of:
                record["quality_flags"].append("expired_validity_label_conflict")
    if "法规汇编" in entry["path"]:
        if Path(entry["path"]).suffix.lower() == ".txt":
            record["quality_flags"].append(
                "aggregate_duplicates_individual_legal_documents"
            )
            record["eligible_for_retrieval"] = False
        # All raw legal documents stay out of current-answer retrieval until
        # the separate edition review supplies verified current replacements.
        record["quality_flags"].append("legal_edition_requires_independent_review")
        record["eligible_for_retrieval"] = False
        heading = content[:1200]
        obsolete = (
            "行政复议法" in title and "2017" in heading and "2023" not in heading
        ) or (
            any(name in title for name in ("不动产登记暂行条例", "不动产登记资料查询"))
            and "2019" in heading
            and "2024" not in heading
        )
        if obsolete:
            record["version_status"] = "historical"
            record["quality_flags"].append("known_superseded_legal_edition")
    return record


def _fields(content: str, *, service: bool = False) -> dict[str, str]:
    fields: dict[str, str] = {}
    matches = [
        match
        for match in FIELD.finditer(content)
        if not service or match.group(1).strip() in SERVICE_FIELDS
    ]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        key = match.group(1).strip()
        value = content[match.end() : end].strip(" \t\r\n")
        fields[key] = fields[key] + "\n" + value if key in fields else value
    return fields


def _text_records(
    entry: dict[str, Any], text: str, as_of: date
) -> list[dict[str, Any]]:
    path = entry["path"]
    if path.startswith("01政务服务事项知识/"):
        kind = "service_item"
    elif path.endswith("一件事指南.txt"):
        kind = "one_thing_guide"
    elif path.endswith("一件事操作指引.txt"):
        kind = "one_thing_operation"
    elif "法规汇编" in path:
        kind = "legal_aggregate"
    else:
        kind = "faq" if re.search(r"(?m)^问题[:：]", text) else "text"
    boundaries = []
    start = 0
    for separator in SEPARATOR.finditer(text):
        boundaries.append((start, separator.start()))
        start = separator.end()
    boundaries.append((start, len(text)))
    newline_offsets = [match.start() for match in re.finditer("\n", text)]
    records = []
    for ordinal, (start, end) in enumerate(boundaries, 1):
        content = text[start:end]
        if not content.strip():
            continue
        first_line = content.strip().splitlines()[0]
        title = re.sub(r"^(?:问题[:：]|\[事项名称[:：])", "", first_line).strip("[] \t")
        fields = _fields(content, service=kind == "service_item")
        if kind == "service_item":
            fields["事项名称"] = title
        locator = {
            "kind": "decoded_text_span",
            "encoding": "utf-8-sig",
            "ordinal": ordinal,
            "char_start": start,
            "char_end": end,
            "line_start": bisect_right(newline_offsets, start - 1) + 1,
            "line_end": bisect_right(newline_offsets, end - 1) + 1,
        }
        records.append(_record(entry, content, title, kind, locator, fields, as_of))
    return records


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def _spreadsheet_records(
    root: Path, entry: dict[str, Any], as_of: date
) -> list[dict[str, Any]]:
    workbook = load_workbook(root / entry["path"], read_only=False, data_only=False)
    records = []
    try:
        for sheet in workbook:
            populated = [
                row
                for row in sheet.iter_rows()
                if any(cell.value is not None for cell in row)
            ]
            if not populated:
                continue
            header_row = next(
                (
                    row
                    for row in populated[:5]
                    if any("答案" in _cell_text(cell.value) for cell in row)
                    and any(
                        "问题" in _cell_text(cell.value)
                        or "问答标题" in _cell_text(cell.value)
                        for cell in row
                    )
                ),
                populated[0],
            )
            headers = {
                cell.column: _cell_text(cell.value).strip("[] \t")
                for cell in header_row
                if cell.value is not None
            }
            for row in populated:
                row_number = row[0].row
                if row_number <= header_row[0].row:
                    continue
                values = {
                    cell.coordinate: _cell_text(cell.value)
                    for cell in row
                    if cell.value is not None
                }
                fields = {
                    headers.get(cell.column, cell.column_letter): _cell_text(cell.value)
                    for cell in row
                    if cell.value is not None
                }
                for column, header in headers.items():
                    if "答案" in header:
                        fields["答案"] = _cell_text(
                            sheet.cell(row_number, column).value
                        )
                question = next(
                    (
                        value
                        for key, value in fields.items()
                        if key in ("问题", "问答标题")
                    ),
                    next(iter(values.values())),
                )
                title = question.strip("[] \t")
                content = "\n".join(
                    f"{coordinate}（{headers.get(sheet[coordinate].column, sheet[coordinate].column_letter)}）：{value}"
                    for coordinate, value in values.items()
                )
                locator = {
                    "kind": "spreadsheet_row",
                    "sheet": sheet.title,
                    "row": row_number,
                    "cells": list(values),
                }
                locator["cell_range"] = f"{next(iter(values))}:{next(reversed(values))}"
                kind = "spreadsheet_faq" if "答案" in fields else "spreadsheet_row"
                record = _record(entry, content, title, kind, locator, fields, as_of)
                record["cells"] = {
                    cell.coordinate: {
                        "value": _cell_text(cell.value),
                        "data_type": cell.data_type,
                    }
                    for cell in row
                    if cell.value is not None
                }
                record["sheet_headers"] = {
                    str(column): header for column, header in headers.items()
                }
                records.append(record)
    finally:
        workbook.close()
    return records


def _word_text(element: ElementTree.Element) -> str:
    parts = []
    for node in element.iter():
        if node.tag == WORD_NS + "t":
            parts.append(node.text if node.text is not None else "")
        elif node.tag == WORD_NS + "tab":
            parts.append("\t")
        elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
            parts.append("\n")
    return "".join(parts)


def _word_records(
    root: Path, entry: dict[str, Any], entries: list[dict[str, Any]], as_of: date
) -> list[dict[str, Any]]:
    parsed_entry = entry
    if Path(entry["path"]).suffix.lower() == ".doc":
        filename = Path(entry["path"]).stem + ".docx"
        matches = [
            candidate
            for candidate in entries
            if "/.pandoc/" in candidate["path"]
            and Path(candidate["path"]).name == filename
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Legacy DOC needs exactly one archived conversion: {entry['path']}"
            )
        parsed_entry = matches[0]
    with ZipFile(root / parsed_entry["path"]) as zipped:
        xml = ElementTree.fromstring(zipped.read("word/document.xml"))
    body = xml.find(WORD_NS + "body")
    if body is None:
        raise ValueError(f"Word document has no body: {entry['path']}")
    blocks: list[dict[str, Any]] = []
    for index, element in enumerate(body, 1):
        if element.tag == WORD_NS + "p":
            text = _word_text(element)
        elif element.tag == WORD_NS + "tbl":
            text = "\n".join(
                "\t".join(
                    "\n".join(_word_text(p) for p in cell.iter(WORD_NS + "p"))
                    for cell in row.findall(WORD_NS + "tc")
                )
                for row in element.findall(WORD_NS + "tr")
            )
        else:
            continue
        blocks.append(
            {"body_child": index, "tag": element.tag.rsplit("}", 1)[-1], "text": text}
        )
    content = "\n".join(block["text"] for block in blocks)
    if not content.strip():
        raise ValueError(f"Word document has no extractable text: {entry['path']}")
    title = Path(entry["path"]).stem
    locator = {
        "kind": "word_xml_body",
        "xml_part": "word/document.xml",
        "body_children": [block["body_child"] for block in blocks],
    }
    kind = "legal_text" if "法规汇编" in entry["path"] else "document"
    record = _record(entry, content, title, kind, locator, {}, as_of)
    record["xml_blocks"] = blocks
    if parsed_entry is not entry:
        record["parsed_from"] = {
            "raw_path": parsed_entry["path"],
            "raw_sha256": parsed_entry["sha256"],
            "method": "archived_docx_conversion_of_legacy_doc; conversion_fidelity_not_independently_verified",
        }
        record["quality_flags"].append("legacy_doc_parsed_from_archived_conversion")
    return [record]


def load_corpus_records(
    root: Path = RAW_ROOT, *, as_of: date = AS_OF
) -> list[dict[str, Any]]:
    """Extract every supported source, keeping excluded/unsafe records explicit."""
    root = Path(root)
    entries = _archive_entries(root)
    records = []
    canonical_by_hash: dict[str, str] = {}
    for entry in entries:
        path = entry["path"]
        if entry["bytes"] == 0 or "/.pandoc/" in path:
            continue
        suffix = Path(path).suffix.lower()
        if suffix == ".txt":
            extracted = _text_records(
                entry, (root / path).read_bytes().decode("utf-8-sig"), as_of
            )
        elif suffix == ".xlsx":
            extracted = _spreadsheet_records(root, entry, as_of)
        elif suffix in (".docx", ".doc"):
            extracted = _word_records(root, entry, entries, as_of)
        else:
            raise ValueError(f"Unsupported archive type: {path}")
        canonical = canonical_by_hash.setdefault(entry["sha256"], path)
        if canonical != path:
            for record in extracted:
                record["eligible_for_retrieval"] = False
                record["quality_flags"].append(
                    "duplicate_file_not_independent_region_coverage"
                )
                record["canonical_raw_path"] = canonical
                record["duplicate_of"] = canonical
                if _district(path) != _district(canonical):
                    record["quality_flags"].append("duplicate_mislabeled_district")
        records.extend(extracted)
    return records


def prepare_corpus(
    root: Path = RAW_ROOT, output: Path = PROCESS_ROOT, *, as_of: date = AS_OF
) -> dict[str, Any]:
    """Write deterministic JSONL and integrity/coverage manifests, not a DB import."""
    root, output = Path(root), Path(output)
    entries = _archive_entries(root)
    records = load_corpus_records(root, as_of=as_of)
    output.mkdir(parents=True, exist_ok=True)
    records_body = "".join(
        json.dumps(record, ensure_ascii=False) + "\n" for record in records
    )
    (output / "records.jsonl").write_text(records_body, encoding="utf-8", newline="\n")
    by_path = Counter(record["raw_path"] for record in records)
    eligible_by_path = Counter(
        record["raw_path"] for record in records if record["eligible_for_retrieval"]
    )
    excluded = []
    for entry in entries:
        if entry["bytes"] == 0:
            excluded.append({"path": entry["path"], "reason": "empty_file"})
        elif "/.pandoc/" in entry["path"]:
            excluded.append(
                {
                    "path": entry["path"],
                    "reason": "conversion_intermediate_used_only_for_legacy_doc",
                }
            )
    report = {
        "checked_as_of": as_of.isoformat(),
        "source_file_count": len(entries),
        "source_bytes": sum(entry["bytes"] for entry in entries),
        "raw_hashes_verified": True,
        "source_type": "user_provided_local_corpus",
        "source_freshness": "not independently verified; preparation is not current-policy certification",
        "record_count": len(records),
        "eligible_record_count": sum(
            record["eligible_for_retrieval"] for record in records
        ),
        "record_type_counts": dict(
            Counter(record["record_type"] for record in records)
        ),
        "eligible_record_type_counts": dict(
            Counter(
                record["record_type"]
                for record in records
                if record["eligible_for_retrieval"]
            )
        ),
        "quality_flag_counts": dict(
            Counter(flag for record in records for flag in record["quality_flags"])
        ),
        "records_sha256": _sha256(records_body.encode("utf-8")),
        "excluded_files": excluded,
        "files": [
            {
                **entry,
                "record_count": by_path[entry["path"]],
                "eligible_record_count": eligible_by_path[entry["path"]],
            }
            for entry in entries
        ],
        "application_import_status": "prepared_only_not_imported",
    }
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=RAW_ROOT)
    parser.add_argument("--output", type=Path, default=PROCESS_ROOT)
    parser.add_argument("--as-of", type=date.fromisoformat, default=AS_OF)
    args = parser.parse_args()
    report = prepare_corpus(args.root, args.output, as_of=args.as_of)
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "source_file_count",
                    "record_count",
                    "eligible_record_count",
                    "record_type_counts",
                    "eligible_record_type_counts",
                    "quality_flag_counts",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
