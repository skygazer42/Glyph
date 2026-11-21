"""Windows file sharing cannot turn a completed write into a truncated receipt."""

import errno
import sys
from pathlib import Path

import pytest

from app.knowledge import document_workspace as subject


def windows_lock(code):
    error = PermissionError(errno.EACCES, "file temporarily locked")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
def test_atomic_write_retries_only_bounded_windows_sharing_failures(tmp_path, monkeypatch, code):
    destination = tmp_path / "receipt.json"
    destination.write_text("old complete receipt", encoding="utf-8")
    original = subject.os.replace
    attempts = []
    delays = []

    def replace(source, target):
        attempts.append(source)
        assert destination.read_text(encoding="utf-8") == "old complete receipt"
        assert subject.Path(source).read_text(encoding="utf-8") == "new complete receipt"
        if len(attempts) < 3:
            raise windows_lock(code)
        return original(source, target)

    monkeypatch.setattr(subject.os, "replace", replace)
    monkeypatch.setattr(subject, "sleep", delays.append, raising=False)
    subject.atomic_write(destination, "new complete receipt")

    assert destination.read_text(encoding="utf-8") == "new complete receipt"
    assert len(attempts) == 3 and len(delays) == 2
    assert not list(tmp_path.glob("*.tmp"))


def test_persistent_windows_lock_propagates_and_preserves_prior_receipt(tmp_path, monkeypatch):
    destination = tmp_path / "receipt.json"
    destination.write_text("prior", encoding="utf-8")
    attempts = []

    def replace(source, target):
        attempts.append(source)
        raise windows_lock(5)

    monkeypatch.setattr(subject.os, "replace", replace)
    monkeypatch.setattr(subject, "sleep", lambda delay: None, raising=False)
    with pytest.raises(PermissionError):
        subject.atomic_write(destination, "new")
    assert destination.read_text(encoding="utf-8") == "prior"
    assert 1 < len(attempts) <= 6
    assert not list(tmp_path.glob("*.tmp"))


def test_unrelated_permission_failure_is_not_retried(tmp_path, monkeypatch):
    attempts = []

    def replace(source, target):
        attempts.append(source)
        raise PermissionError(errno.EACCES, "permission denied")

    monkeypatch.setattr(subject.os, "replace", replace)
    with pytest.raises(PermissionError):
        subject.atomic_write(tmp_path / "receipt.json", "new")
    assert len(attempts) == 1
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows extended path spelling")
def test_extended_windows_path_spelling_keeps_containment(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    workspace = subject.DocumentWorkspace(root, root / "parsed", root / "status", root / "embedded")
    lock = root / "policy.processing.lock"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        return Path("\\\\?\\" + str(result)) if path == lock else result

    monkeypatch.setattr(Path, "resolve", resolve)
    assert workspace.contained_path(root, lock.name) == lock


@pytest.mark.skipif(sys.platform != "win32", reason="Windows extended path spelling")
def test_extended_windows_path_does_not_admit_outside_target(tmp_path, monkeypatch):
    root = tmp_path / "uploads"
    root.mkdir()
    workspace = subject.DocumentWorkspace(root, root / "parsed", root / "status", root / "embedded")
    target = root / "outside.txt"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == target:
            return Path("\\\\?\\" + str(tmp_path / "outside.txt"))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(subject.HTTPException) as error:
        workspace.contained_path(root, target.name)
    assert error.value.status_code == 400
