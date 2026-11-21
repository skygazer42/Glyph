"""Verified document metadata, reused while filesystem fingerprints stay unchanged.

This is a listing cache, never a substitute for the workspace's content hashes
before opening, parsing or indexing a document.
"""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.knowledge.document_workspace import DocumentWorkspace, SUPPORTED_FORMATS, atomic_write
from app.schemas.knowledge import DocumentInfo

logger = logging.getLogger(__name__)
FileStamp = tuple[int, int, int, int]
Fingerprint = tuple[FileStamp | None, FileStamp | None, FileStamp | None, FileStamp | None]


def _stamp(info: os.stat_result, inode: int) -> FileStamp:
    return info.st_size, info.st_mtime_ns, info.st_ctime_ns, inode


class CatalogEntry(BaseModel):
    """Persist only metadata and the files that were checked to produce it."""

    fingerprint: Fingerprint
    document: DocumentInfo


class CatalogSnapshot(BaseModel):
    version: Literal[1] = 1
    entries: dict[str, CatalogEntry]


class DocumentCatalog:
    """Scan directory metadata cheaply, rechecking bodies only for changed entries."""

    def __init__(self, workspace: DocumentWorkspace):
        self.workspace = workspace
        self._lock = RLock()
        self._invalidated: set[str] = set()
        self._snapshot_path = workspace.contained_path(workspace.root / ".status", "document_catalog.json")
        self._entries = self._load()

    def _load(self) -> dict[str, CatalogEntry]:
        try:
            snapshot = CatalogSnapshot.model_validate_json(self._snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError, ValidationError):
            logger.warning("资料目录快照无法读取，将重新校验目录")
            return {}
        return {name: entry for name, entry in snapshot.entries.items()
                if entry.document.id == name and entry.document.name == name}

    def invalidate(self, doc_id: str) -> None:
        """A strict workspace check may discover edits with preserved timestamps."""
        with self._lock:
            self._invalidated.add(doc_id)

    def _scan(self, directory: Path) -> dict[str, FileStamp]:
        self.workspace.contained_path(directory, ".catalog-boundary")
        files = {}
        source_directory = directory == self.workspace.root
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_file(follow_symlinks=False):
                            # Windows needs a separate syscall for inode(). Keep source
                            # identity, but use timestamps/size for derived cache files.
                            inode = entry.inode() if source_directory else 0
                            files[entry.name] = _stamp(entry.stat(follow_symlinks=False), inode)
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            pass
        return files

    def _fingerprint(self, name: str) -> Fingerprint:
        paths = (self.workspace.root / name, self.workspace.parsed_dir / f"{name}.md",
                 self.workspace.parsed_status_dir / f"{name}.json", self.workspace.embedded_dir / f"{name}.json")
        stamps: list[FileStamp | None] = []
        for index, path in enumerate(paths):
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                stamps.append(None)
            else:
                stamps.append(_stamp(info, info.st_ino if index == 0 else 0) if stat.S_ISREG(info.st_mode) else None)
        return stamps[0], stamps[1], stamps[2], stamps[3]

    def _describe(self, name: str, fingerprint: Fingerprint) -> CatalogEntry:
        for _ in range(2):
            source_version = self.workspace.source_version(name)
            parsed = self.workspace.parsed_content(name, source_version)
            embedded = self.workspace.embedded(name, source_version, parsed=parsed)
            after = self._fingerprint(name)
            if after[0] is None:
                raise FileNotFoundError(name)
            if fingerprint == after:
                return CatalogEntry(fingerprint=after, document=DocumentInfo(
                    id=name, name=name, size=after[0][0], modified=after[0][1] / 1_000_000_000,
                    source_version=source_version, parsed=parsed.available,
                    embedded=embedded, content_length=parsed.content_length,
                ))
            fingerprint = after
        raise HTTPException(status_code=409, detail="资料正在更新，请稍后刷新列表")

    def documents(self) -> list[DocumentInfo]:
        """Return a verified snapshot; scanning never reads unmodified document bodies."""
        with self._lock:
            source = self._scan(self.workspace.root)
            parsed = self._scan(self.workspace.parsed_dir)
            parsed_status = self._scan(self.workspace.parsed_status_dir)
            embedded = self._scan(self.workspace.embedded_dir)
            current = {}
            changed = bool(self._invalidated)
            for name, source_stamp in source.items():
                if Path(name).suffix.lower() not in SUPPORTED_FORMATS:
                    continue
                fingerprint = (source_stamp, parsed.get(f"{name}.md"),
                               parsed_status.get(f"{name}.json"), embedded.get(f"{name}.json"))
                entry = self._entries.get(name)
                if entry is None or entry.fingerprint != fingerprint or name in self._invalidated:
                    changed = True
                    try:
                        entry = self._describe(name, fingerprint)
                    except FileNotFoundError:
                        continue
                    except HTTPException as exc:
                        if exc.status_code == 404:
                            continue
                        raise
                current[name] = entry
            changed = changed or current.keys() != self._entries.keys()
            self._entries = current
            self._invalidated.clear()
            if changed:
                snapshot = CatalogSnapshot(entries=current)
                try:
                    atomic_write(self._snapshot_path, snapshot.model_dump_json())
                except OSError:
                    logger.warning("资料目录快照无法保存，本次继续使用已校验的内存目录")
            return [entry.document for entry in current.values()]
