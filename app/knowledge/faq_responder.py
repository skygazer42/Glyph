"""Lightweight FAQ matcher that short-circuits common queries."""

from __future__ import annotations

import logging
import hashlib
from datetime import date
from pathlib import Path
from threading import RLock
from typing import List, Optional, Tuple
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from app.models.policy import FinalAnswer, PolicyDocument, PolicyType


logger = logging.getLogger(__name__)


class FAQEntry(BaseModel):
    """保存问答及官方正文证据；缺少证据的历史条目不参与直答。"""

    model_config = ConfigDict(strict=True, str_strip_whitespace=True)

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    region: str = ""
    source_title: str = ""
    source_quote: str = ""
    source_body_sha256: str = ""
    source_markdown_path: str = ""
    verified_date: str = ""
    valid_from: str | None = None
    valid_until: str | None = None

    @field_validator("verified_date", "valid_from", "valid_until")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        """日期必须为真实 ISO 日期；历史条目的空核验日期留待来源检查排除。"""
        if value is not None and value != "":
            date.fromisoformat(value)
        return value


class FAQResponder:
    """Simple FAQ matcher that returns canned answers for high-frequency queries."""

    def __init__(
        self,
        data_path: str = "resources/faq/qa_pairs.json",
    ) -> None:
        self.data_path = Path(data_path)
        self.entries: List[FAQEntry] = []
        self._data_version: tuple[int, int, int, int] | None = None
        self._reload_lock = RLock()
        self._load_entries()

    def _file_version(self) -> tuple[int, int, int, int] | None:
        """识别原位写入及原子替换；文件消失也使缓存失效。"""
        try:
            stat = self.data_path.stat()
        except FileNotFoundError:
            return None
        return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino

    def _load_entries(self) -> None:
        """从本地 JSON 校验并加载 FAQ；文件不存在仅记录警告，格式错误向上传播。"""
        version = self._file_version()
        if version is None:
            self.entries = []
            self._data_version = None
            logger.warning("FAQResponder 找不到数据文件：%s", self.data_path)
            return
        entries = TypeAdapter(list[FAQEntry]).validate_json(
            self.data_path.read_text(encoding="utf-8")
        )
        verified = [entry for entry in entries if self._verify_source(entry)]
        if self._file_version() != version:
            raise OSError("FAQ file changed during validation")
        self.entries = verified
        self._data_version = version
        logger.info(
            "FAQResponder loaded %s entries from %s", len(self.entries), self.data_path
        )

    def _refresh_entries(self) -> None:
        """热更新仍走来源校验；无效更新清空直答，交由正式检索处理。"""
        with self._reload_lock:
            version = None
            try:
                version = self._file_version()
                if version != self._data_version:
                    self._load_entries()
            except (OSError, ValueError):
                self.entries = []
                self._data_version = version
                logger.warning("FAQResponder 更新校验失败，暂停直答：%s", self.data_path)

    def _verify_source(self, entry: FAQEntry) -> bool:
        """核对官方来源、适用地区、正文哈希和原文摘录，不推定法律有效性。"""
        parsed = urlparse(entry.source)
        host = parsed.hostname
        if parsed.scheme != "https" or host is None or not host.endswith(".gov.cn"):
            return False
        if entry.region not in {
            "全国",
            "全国（含江苏省常州市）",
            "江苏",
            "江苏省",
            "常州",
            "常州市",
        } and not entry.region.startswith(("常州市", "江苏省常州市")):
            return False
        if not all(
            [
                entry.source_title,
                entry.source_quote,
                entry.source_body_sha256,
                entry.source_markdown_path,
                entry.verified_date,
            ]
        ):
            return False
        source = Path(entry.source_markdown_path)
        if not source.is_absolute():
            source = Path(__file__).resolve().parents[2] / source
        try:
            markdown = source.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            return False
        if "\n## 正文\n" not in markdown:
            return False
        body = markdown.split("\n## 正文\n", 1)[1].strip() + "\n"
        return (
            hashlib.sha256(body.encode("utf-8")).hexdigest() == entry.source_body_sha256
            and entry.source_quote in body
        )

    def maybe_answer(self, query: str) -> Optional[FinalAnswer]:
        """仅对文字事实一致的问句直答；其他表达继续进入正式检索。"""

        if not query:
            return None
        self._refresh_entries()
        if not self.entries:
            return None

        match = self._best_match(query)
        if not match:
            return None

        entry, score = match
        if not self._verify_source(entry):
            return None
        source = PolicyDocument(
            id=uuid5(NAMESPACE_URL, f"glyph:official-faq:{entry.source}"),
            title=entry.source_title,
            content=entry.source_quote,
            source=entry.source,
            doc_type=PolicyType.GUIDELINE,
            regions=[entry.region],
            metadata={
                "source_body_sha256": entry.source_body_sha256,
                "verified_date": entry.verified_date,
            },
        )
        return FinalAnswer(
            query_id=uuid4(),
            answer=entry.answer,
            sources=[source],
            confidence=round(score, 3),
            verification_passed=True,
            metadata={
                "route": "faq_cache",
                "faq_question": entry.question,
                "faq_source": entry.source,
                "region": entry.region,
                "source_body_sha256": entry.source_body_sha256,
                "source_quote": entry.source_quote,
                "verified_date": entry.verified_date,
                "verification_scope": "official source snapshot and supporting quote",
                "similarity": score,
            },
            total_processing_time=0.0,
        )

    def _best_match(self, query: str) -> Optional[Tuple[FAQEntry, float]]:
        """只忽略空白、大小写与标点，避免单字否定或资格差异导致反义误答。"""
        normalized_query = query.strip().casefold().rstrip("？?。")
        if not normalized_query:
            return None
        for entry in self.entries:
            candidate = entry.question.strip().casefold().rstrip("？?。")
            if normalized_query == candidate and self._applies(entry):
                return entry, 1.0
        return None

    @staticmethod
    def _applies(entry: FAQEntry) -> bool:
        """已逐字匹配的问句仍须处于明确的适用日期内。"""
        today = date.today().isoformat()
        if entry.valid_from is not None and today < entry.valid_from:
            return False
        if entry.valid_until is not None and today > entry.valid_until:
            return False
        return True


__all__ = ["FAQResponder"]
