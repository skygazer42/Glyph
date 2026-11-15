"""Offline HTTP tests against the production knowledge router and local files."""

from __future__ import annotations

import importlib.util
import ast
import asyncio
import io
import json
import os
import sys
import subprocess
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import quote

import fitz
import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def api(monkeypatch, tmp_path):
    """Replace only external parser/vector boundaries, never production routes."""
    monkeypatch.chdir(tmp_path)

    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    def load(name, relative):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    for name in ("app", "app.api", "app.api.endpoints", "app.models", "app.knowledge", "app.config"):
        stub(name)
    settings = SimpleNamespace(mineru=SimpleNamespace(enabled=False, api_key=None))
    stub("app.config.app_config", settings=settings)
    load("app.models.base", "app/models/base.py")
    schemas = load("app.api.schemas", "app/api/schemas.py")
    workspace_module = load("app.knowledge.document_workspace", "app/knowledge/document_workspace.py")
    processors = []

    class Processor:
        def __init__(self, config=None):
            self.config = {} if config is None else config
            processors.append(self)

        async def extract_with_metadata(self, path):
            return {"success": True, "text": path.read_text(encoding="utf-8"),
                    "file_name": path.name, "extraction_method": "test-parser"}

    processor = Processor()
    dependency_calls = Mock(side_effect=AssertionError("vector service must stay lazy"))
    deps = stub("app.api.deps", get_knowledge_service=dependency_calls,
                get_enhanced_doc_processor=lambda: processor)
    stub("app.knowledge.doc_enhanced", EnhancedDocumentProcessor=Processor)
    stub("app.knowledge.service", KnowledgeService=type("KnowledgeService", (), {}))
    router = load("_knowledge_workspace_api", "app/api/endpoints/knowledge.py")
    app = FastAPI()
    app.include_router(router.router, prefix="/api/knowledge")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, router=router, workspace=router._workspace(),
                              schemas=schemas, module=workspace_module, root=tmp_path,
                              app=app, deps=deps, dependency_calls=dependency_calls,
                              processors=processors, settings=settings)


def source(api, name="policy.txt", text="政策正文。第二句话。" * 20):
    path = api.router.UPLOAD_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def workspace(api, name="policy.txt"):
    response = api.client.get(f"/api/knowledge/documents/{quote(name, safe='')}/workspace")
    assert response.status_code == 200, response.text
    return response.json()


def cached(api, name="policy.txt", text="政策正文。第二句话。" * 20):
    path = source(api, name, text)
    api.workspace.store_parsed(name, text, api.workspace.source_version(name), "text")
    return path, workspace(api, name)


def preview(api, current, **changes):
    payload = {"size": 32, "overlap": 7, "boundary": "fixed",
               "source_version": current["source_version"], "parsed_version": current["parsed"]["version"]}
    payload.update(changes)
    return api.client.post(f"/api/knowledge/documents/{current['doc_id']}/chunks/preview", json=payload)


def save(api, current, **changes):
    payload = {**current["config"], "source_version": current["source_version"],
               "revision": current["config_revision"]}
    payload.update(changes)
    return api.client.put(f"/api/knowledge/documents/{current['doc_id']}/processing-config", json=payload)


def install_upsert_store(api):
    vectors = {}

    def write(documents, *, upsert=False):
        assert upsert is True
        for document in documents:
            vectors[str(document.id)] = document.content

    store = SimpleNamespace(add_documents=Mock(side_effect=write), vectors=vectors)
    api.app.dependency_overrides[api.deps.get_knowledge_service] = lambda: SimpleNamespace(vector_store=store)
    return store


def embed(api, current):
    return api.client.post("/api/knowledge/embed", json={
        "doc_id": current["doc_id"], "source_version": current["source_version"],
        "parsed_version": current["parsed"]["version"],
    })


def test_capabilities_and_workspace_never_initialize_vector_service(api):
    response = api.client.get("/api/knowledge/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert capabilities["ocr"] is False
    assert capabilities["hierarchical_index"] is False
    assert next(item for item in capabilities["parsers"] if item["value"] == "mineru")["available"] is False
    source(api)
    current = workspace(api)
    assert current["parsed"]["available"] is False
    assert current["parsed"]["text"] is None
    assert current["pages"][0]["text"].startswith("政策正文")
    assert current["config_revision"] == "0"
    assert current["saved_at"] is None
    api.dependency_calls.assert_not_called()


def test_pdf_source_and_page_are_original_bytes_and_actual_png(api):
    path = api.router.UPLOAD_DIR / "original.pdf"
    with fitz.open() as document:
        document.new_page(width=200, height=300).insert_text((30, 40), "Original page one")
        document.new_page(width=200, height=300).insert_text((30, 40), "Page two")
        data = document.tobytes()
    path.write_bytes(data)
    current = workspace(api, "original.pdf")
    assert current["page_count"] == 2
    assert "Original page one" in current["pages"][0]["text"]
    assert current["parsed"]["available"] is False
    response = api.client.get(current["source_url"])
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    image = api.client.get(current["pages"][0]["image_url"])
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert image.headers["cache-control"] == "no-store"
    pixmap = fitz.Pixmap(image.content)
    assert (pixmap.width, pixmap.height) == (300, 450)
    assert api.client.get("/api/knowledge/documents/original.pdf/pages/0").status_code == 404
    assert api.client.get("/api/knowledge/documents/original.pdf/pages/3").status_code == 404


@pytest.mark.parametrize("name", ["..%5cprivate.txt", "..%5c..%5cprivate.txt", "C:%5cprivate.txt", "nul.txt"])
def test_document_ids_reject_noncanonical_paths(api, name):
    (api.root / "private.txt").write_text("private", encoding="utf-8")
    response = api.client.get(f"/api/knowledge/documents/{name}/source")
    assert response.status_code == 400
    assert "private" not in response.text


def test_root_boundary_rejects_metadata_or_source_escape(api):
    with pytest.raises(HTTPException) as error:
        api.workspace.contained_path(api.root, "private.txt")
    assert error.value.status_code == 400
    for doc_id in ("../private.txt", "..\\private.txt", "", ".", "policy.txt "):
        with pytest.raises(HTTPException):
            api.workspace.source_path(doc_id)


def test_cached_markdown_is_real_and_legacy_cache_remains_compatible(api):
    path = source(api)
    parsed_path = api.workspace.parsed_path(path.name)
    parsed_path.write_text("# Actual parser Markdown\nDifferent content", encoding="utf-8")
    current = workspace(api)
    assert current["parsed"]["text"] == parsed_path.read_text(encoding="utf-8")
    assert current["parsed"]["parser"] == "legacy"
    assert current["parsed"]["page_mapping"] == "unavailable"
    response = preview(api, current)
    assert response.status_code == 200
    assert all(chunk["pages"] == [] for chunk in response.json()["chunks"])
    documents = api.client.get("/api/knowledge/documents").json()["documents"]
    assert documents[0]["parsed"] is True
    assert documents[0]["content_length"] == len(current["parsed"]["text"])


@pytest.mark.parametrize("legacy", [False, True])
def test_source_hash_invalidates_cache_and_preview_even_with_same_mtime(api, legacy):
    path = source(api, text="A" * 120)
    if legacy:
        api.workspace.parsed_path(path.name).write_text("A" * 120, encoding="utf-8")
    else:
        api.workspace.store_parsed(path.name, "A" * 120, api.workspace.source_version(path.name), "text")
    current = workspace(api)
    stamp = path.stat()
    path.write_text("B" * 120, encoding="utf-8")
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    refreshed = workspace(api)
    assert refreshed["source_version"] != current["source_version"]
    assert refreshed["parsed"]["available"] is False
    assert preview(api, current).status_code == 409
    assert save(api, current).status_code == 409
    assert api.client.get(current["source_url"]).status_code == 409
    assert api.client.get("/api/knowledge/documents").json()["documents"][0]["parsed"] is False


@pytest.mark.parametrize("boundary", ["fixed", "sentence"])
@pytest.mark.parametrize("overlap", [0, 7, 31])
def test_preview_covers_entire_unicode_text_and_exact_overlap(api, boundary, overlap):
    text = "政策😀第一句话。第二句保留全部空格  和标点！\n" * 15
    _, current = cached(api, text=text)
    response = preview(api, current, boundary=boundary, overlap=overlap)
    assert response.status_code == 200, response.text
    result = response.json()
    chunks = result["chunks"]
    assert result["total"] == len(chunks)
    assert chunks[0]["start"] == 0
    assert chunks[-1]["end"] == len(text)
    reconstructed = chunks[0]["text"]
    for index, chunk in enumerate(chunks):
        assert chunk["text"] == text[chunk["start"]:chunk["end"]]
        assert len(chunk["text"]) <= 32
        assert chunk["pages"] == [1]
        if index:
            previous = chunks[index - 1]
            assert chunk["start"] == previous["end"] - overlap
            assert chunk["overlap"] == overlap
            reconstructed += chunk["text"][chunk["overlap"]:]
        else:
            assert chunk["overlap"] == 0
    assert reconstructed == text


def test_preview_rejects_stale_parsed_version_and_invalid_chunk_config(api):
    _, current = cached(api)
    api.workspace.store_parsed(current["doc_id"], "replacement text", current["source_version"], "text")
    assert preview(api, current).status_code == 409
    assert preview(api, current, overlap=32).status_code == 422
    assert preview(api, current, size=0).status_code == 422


def test_config_save_refresh_conflict_and_restart_readback(api):
    _, current = cached(api)
    response = save(api, current, size=640, overlap=64, boundary="fixed", parser="text")
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["revision"] != "0"
    assert saved["saved_at"]
    refreshed = workspace(api)
    assert refreshed["config"] == saved["config"]
    assert refreshed["config_revision"] == saved["revision"]
    assert save(api, current, size=320).status_code == 409
    restarted = api.router._workspace()
    config, revision, saved_at = restarted.config(current["doc_id"])
    assert config.size == 640
    assert revision == saved["revision"]
    assert saved_at == saved["saved_at"]


def test_failed_atomic_save_preserves_previous_file_and_revision(api, monkeypatch):
    _, current = cached(api)
    assert save(api, current).status_code == 200
    current = workspace(api)
    path = api.workspace.marker_path(api.workspace.config_dir, current["doc_id"])
    previous = path.read_bytes()
    monkeypatch.setattr(api.module.os, "replace", Mock(side_effect=OSError("disk unavailable")))
    response = save(api, current, size=320)
    assert response.status_code == 500
    assert path.read_bytes() == previous
    assert not list(path.parent.glob("*.tmp"))
    assert workspace(api)["config_revision"] == current["config_revision"]


def test_concurrent_config_updates_have_one_winner(api):
    _, current = cached(api)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda value: save(api, current, size=value).status_code, (320, 640)))
    assert sorted(results) == [200, 409]


@pytest.mark.parametrize("changes", [{"ocr": "on"}, {"ocr": "off"}, {"index": "hierarchical"}, {"parser": "mineru"}])
def test_unsupported_processing_options_are_rejected_not_persisted(api, changes):
    _, current = cached(api)
    assert save(api, current, **changes).status_code == 422
    assert workspace(api)["config_revision"] == "0"


def test_upload_caches_real_validation_text_and_refuses_existing_name(api):
    payload = b"actual uploaded text"
    response = api.client.post("/api/knowledge/upload", files={"file": ("new.txt", io.BytesIO(payload), "text/plain")})
    assert response.status_code == 200, response.text
    assert response.json()["parsed"] is True
    assert workspace(api, "new.txt")["parsed"]["text"] == payload.decode()
    duplicate = api.client.post("/api/knowledge/upload", files={"file": ("new.txt", io.BytesIO(b"replacement"), "text/plain")})
    assert duplicate.status_code == 409
    assert (api.router.UPLOAD_DIR / "new.txt").read_bytes() == payload


def test_parse_consumes_saved_config_and_explicit_parser_fields(api):
    source(api)
    current = workspace(api)
    assert save(api, current, parser="text").status_code == 200
    response = api.client.post("/api/knowledge/parse", json={"doc_id": "policy.txt", "source_version": current["source_version"]})
    assert response.status_code == 200, response.text
    assert api.processors[-1].config == {"mineru_enabled": False, "llamaindex_enabled": False}
    assert workspace(api)["parsed"]["available"] is True
    response = api.client.post("/api/knowledge/parse", json={"doc_id": "policy.txt", "parser": "llamaindex", "ocr": "auto"})
    assert response.status_code == 200
    assert api.processors[-1].config == {"mineru_enabled": False, "llamaindex_enabled": True}
    assert api.client.post("/api/knowledge/parse", json={"doc_id": "policy.txt", "ocr": "on"}).status_code == 422
    assert api.client.post("/api/knowledge/parse", json={"doc_id": "policy.txt", "ignored_parser": "mineru"}).status_code == 422


def test_embed_uses_real_cached_document_and_preserves_shared_hierarchical_index(api):
    _, current = cached(api)
    add = Mock()
    hierarchy = Mock(side_effect=AssertionError("must not rebuild shared index"))
    service = SimpleNamespace(vector_store=SimpleNamespace(add_documents=add), hierarchical_store=hierarchy)
    api.app.dependency_overrides[api.deps.get_knowledge_service] = lambda: service
    response = api.client.post("/api/knowledge/embed", json={"doc_id": current["doc_id"]})
    assert response.status_code == 200, response.text
    assert add.call_args.args[0][0].content == current["parsed"]["text"]
    assert add.call_args.kwargs == {"upsert": True}
    hierarchy.assert_not_called()
    assert workspace(api)["embedded"] is True


def test_embed_rejects_stale_source_and_parsed_versions_before_indexing(api):
    _, current = cached(api)
    add = Mock()
    api.app.dependency_overrides[api.deps.get_knowledge_service] = lambda: SimpleNamespace(
        vector_store=SimpleNamespace(add_documents=add)
    )
    for field in ("source_version", "parsed_version"):
        request = {"doc_id": current["doc_id"], field: "0" * 64}
        response = api.client.post("/api/knowledge/embed", json=request)
        assert response.status_code == 409
    add.assert_not_called()


def test_failed_embed_does_not_retry_or_create_success_marker(api):
    _, current = cached(api)
    add = Mock(side_effect=RuntimeError("offline vector write failed"))
    api.app.dependency_overrides[api.deps.get_knowledge_service] = lambda: SimpleNamespace(
        vector_store=SimpleNamespace(add_documents=add)
    )
    response = api.client.post("/api/knowledge/embed", json={"doc_id": current["doc_id"]})
    assert response.status_code == 500
    add.assert_called_once()
    assert workspace(api)["embedded"] is False


def test_embed_is_idempotent_and_reparse_replaces_the_same_vector(api):
    _, current = cached(api)
    store = install_upsert_store(api)
    assert embed(api, current).status_code == 200
    marker = api.workspace.marker_path(api.router.EMBED_STATUS_DIR, current["doc_id"])
    saved = json.loads(marker.read_text(encoding="utf-8"))
    assert saved["parsed_version"] == current["parsed"]["version"]
    assert saved["source_version"] == current["source_version"]
    assert saved["vector_id"] in store.vectors
    assert embed(api, current).status_code == 200
    store.add_documents.assert_called_once()
    api.workspace.store_parsed(current["doc_id"], current["parsed"]["text"], current["source_version"], "another-parser")
    assert workspace(api)["embedded"] is True
    api.workspace.store_parsed(current["doc_id"], "更正后的解析正文", current["source_version"], "text")
    refreshed = workspace(api)
    assert refreshed["embedded"] is False
    assert api.client.get("/api/knowledge/documents").json()["documents"][0]["embedded"] is False
    assert embed(api, current).status_code == 409
    assert embed(api, refreshed).status_code == 200
    assert store.add_documents.call_count == 2
    assert store.vectors == {saved["vector_id"]: "更正后的解析正文"}
    assert workspace(api)["embedded"] is True


@pytest.mark.parametrize("failure", ["marker", "flush"])
def test_embed_retry_after_uncertain_write_keeps_one_stable_vector(api, monkeypatch, failure):
    _, current = cached(api)
    store = install_upsert_store(api)
    original_mark = api.router._mark_embedded
    original_write = store.add_documents.side_effect
    if failure == "marker":
        monkeypatch.setattr(api.router, "_mark_embedded", Mock(side_effect=OSError("marker unavailable")))
    else:
        def failed_flush(documents, *, upsert=False):
            original_write(documents, upsert=upsert)
            raise RuntimeError("uncertain vector flush")
        store.add_documents.side_effect = failed_flush
    assert embed(api, current).status_code == 500
    assert len(store.vectors) == 1
    assert workspace(api)["embedded"] is False
    monkeypatch.setattr(api.router, "_mark_embedded", original_mark)
    store.add_documents.side_effect = original_write
    assert embed(api, current).status_code == 200
    assert len(store.vectors) == 1
    first, second = store.add_documents.call_args_list
    assert first.args[0][0].id == second.args[0][0].id


def test_concurrent_embed_submissions_never_write_twice(api):
    _, current = cached(api)
    store = install_upsert_store(api)
    started, finish = threading.Event(), threading.Event()
    original_write = store.add_documents.side_effect

    def slow_write(documents, *, upsert=False):
        started.set()
        assert finish.wait(5)
        original_write(documents, upsert=upsert)

    store.add_documents.side_effect = slow_write
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(embed, api, current)
        assert started.wait(5)
        try:
            assert embed(api, current).status_code == 409
        finally:
            finish.set()
        assert first.result(timeout=5).status_code == 200
    assert embed(api, current).status_code == 200
    store.add_documents.assert_called_once()


def test_embedding_lock_also_excludes_another_process(api):
    _, current = cached(api)
    store = install_upsert_store(api)
    lock_path = api.workspace.config_dir / f"{current['doc_id']}.embedding.lock"
    script = """
import sys
stream = open(sys.argv[1], 'a+b')
try:
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)
sys.exit(1)
"""
    with api.workspace.document_lock(current["doc_id"], "embedding"):
        result = subprocess.run([sys.executable, "-c", script, str(lock_path)], capture_output=True, timeout=5)
        assert result.returncode == 0, result.stderr
        assert embed(api, current).status_code == 409
    store.add_documents.assert_not_called()


def test_reparse_during_vector_write_cannot_mark_new_parser_text_embedded(api):
    _, current = cached(api)
    store = install_upsert_store(api)
    original_write = store.add_documents.side_effect

    def reparse_during_write(documents, *, upsert=False):
        original_write(documents, upsert=upsert)
        api.workspace.store_parsed(current["doc_id"], "new parse after embedding started", current["source_version"], "text")

    store.add_documents.side_effect = reparse_during_write
    assert embed(api, current).status_code == 409
    refreshed = workspace(api)
    assert refreshed["embedded"] is False
    store.add_documents.side_effect = original_write
    assert embed(api, refreshed).status_code == 200
    assert len(store.vectors) == 1
    assert list(store.vectors.values()) == [refreshed["parsed"]["text"]]


@pytest.mark.parametrize("legacy", [{}, {"source_version": "current"}])
def test_legacy_embed_markers_are_not_proof_of_current_parsed_content(api, legacy):
    _, current = cached(api)
    if legacy:
        legacy["source_version"] = current["source_version"]
    marker = api.workspace.marker_path(api.router.EMBED_STATUS_DIR, current["doc_id"])
    marker.write_text(json.dumps(legacy), encoding="utf-8")
    assert workspace(api)["embedded"] is False


@pytest.mark.parametrize("upsert", [False, True])
def test_milvus_add_documents_shares_entity_preparation_and_explicit_write_mode(upsert):
    """Exercise the production method without importing SDK clients or connecting."""
    tree = ast.parse((ROOT / "app/knowledge/milvus.py").read_text(encoding="utf-8"))
    store_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MilvusStore")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future, store_class], type_ignores=[])), "milvus.py", "exec"), namespace)
    store = object.__new__(namespace["MilvusStore"])
    store.collection = SimpleNamespace(insert=Mock(), upsert=Mock(), flush=Mock())
    store._embed_texts = Mock(return_value=[SimpleNamespace(tolist=lambda: [0.1, 0.2])])
    document = SimpleNamespace(id="stable-id", title="title", content="text", source="uploads/policy.txt", doc_type="guideline")
    if upsert:
        store.add_documents([document], upsert=True)
    else:
        store.add_documents([document])
    written = store.collection.upsert if upsert else store.collection.insert
    unused = store.collection.insert if upsert else store.collection.upsert
    written.assert_called_once_with([{"id": "stable-id", "embedding": [0.1, 0.2], "title": "title", "content": "text",
                                      "source": "uploads/policy.txt", "doc_type": "guideline"}])
    unused.assert_not_called()
    store.collection.flush.assert_called_once()


def test_failed_upload_can_retry_the_same_filename(api, monkeypatch):
    processor = api.processors[0]
    original_extract = processor.extract_with_metadata

    async def fail(path):
        raise RuntimeError("transient parser failure")

    monkeypatch.setattr(processor, "extract_with_metadata", fail)
    response = api.client.post("/api/knowledge/upload", files={"file": ("retry.txt", b"policy", "text/plain")})
    assert response.status_code == 500
    assert not (api.router.UPLOAD_DIR / "retry.txt").exists()
    monkeypatch.setattr(processor, "extract_with_metadata", original_extract)
    response = api.client.post("/api/knowledge/upload", files={"file": ("retry.txt", b"policy", "text/plain")})
    assert response.status_code == 200


def test_partial_upload_copy_failure_removes_only_its_new_file(api):
    class BrokenSource(io.BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise OSError("interrupted upload stream")
            return super().read(3)

    file = UploadFile(file=BrokenSource(b"policy bytes"), filename="partial.txt")
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.router.upload_document(file=file, processor=api.processors[0]))
    assert error.value.status_code == 500
    assert not (api.router.UPLOAD_DIR / "partial.txt").exists()


def test_failed_upload_does_not_remove_concurrently_modified_source(api, monkeypatch):
    async def fail_after_external_edit(path):
        path.write_text("external edit", encoding="utf-8")
        raise RuntimeError("transient parser failure")

    monkeypatch.setattr(api.processors[0], "extract_with_metadata", fail_after_external_edit)
    response = api.client.post("/api/knowledge/upload", files={"file": ("concurrent.txt", b"policy", "text/plain")})
    assert response.status_code == 500
    assert (api.router.UPLOAD_DIR / "concurrent.txt").read_text(encoding="utf-8") == "external edit"


@pytest.mark.parametrize("existing_cache", [False, True])
def test_failed_upload_cache_write_rolls_back_created_files_and_preserves_older_cache(api, monkeypatch, existing_cache):
    parsed_path = api.workspace.parsed_path("retry.txt")
    marker_path = api.workspace.marker_path(api.router.PARSED_STATUS_DIR, "retry.txt")
    if existing_cache:
        parsed_path.write_text("previous cache", encoding="utf-8")
        marker_path.write_text(json.dumps({"source_version": "previous-version"}), encoding="utf-8")
    previous = {path: path.read_bytes() if path.is_file() else None for path in (parsed_path, marker_path)}
    original_write = api.module.atomic_write

    def fail_marker(path, text):
        if path == marker_path:
            raise OSError("marker unavailable")
        return original_write(path, text)

    monkeypatch.setattr(api.module, "atomic_write", fail_marker)
    response = api.client.post("/api/knowledge/upload", files={"file": ("retry.txt", b"new policy", "text/plain")})
    assert response.status_code == 500
    assert not (api.router.UPLOAD_DIR / "retry.txt").exists()
    for path, before in previous.items():
        assert (path.read_bytes() if path.is_file() else None) == before


def test_missing_document_and_missing_parse_are_not_successful_workspace_states(api):
    assert api.client.get("/api/knowledge/documents/missing.txt/workspace").status_code == 404
    source(api)
    current = workspace(api)
    request = {"source_version": current["source_version"], "parsed_version": "0" * 64}
    response = api.client.post("/api/knowledge/documents/policy.txt/chunks/preview", json=request)
    assert response.status_code == 409


def test_generated_urls_encode_unicode_spaces_and_url_punctuation(api):
    name = "政策 # $ file.txt"
    path = source(api, name=name, text="Original source")
    current = workspace(api, name)
    assert "#" not in current["source_url"]
    assert " " not in current["source_url"]
    assert "%23" in current["source_url"]
    assert "%24" in current["source_url"]
    response = api.client.get(current["source_url"])
    assert response.status_code == 200
    assert response.content == path.read_bytes()


def test_local_pdf_and_file_reads_are_executed_off_event_loop(api, monkeypatch):
    source(api)
    threads = []
    original = api.module.DocumentWorkspace.workspace

    def record_thread(self, *args, **kwargs):
        threads.append(threading.get_ident())
        return original(self, *args, **kwargs)

    monkeypatch.setattr(api.module.DocumentWorkspace, "workspace", record_thread)
    workspace(api)
    # TestClient's ASGI event-loop thread is exposed by an async test-only probe.
    @api.app.get("/loop-thread")
    async def loop_thread():
        return threading.get_ident()

    assert threads[0] != api.client.get("/loop-thread").json()


def test_corrupt_config_is_visible_instead_of_silently_resetting_preferences(api):
    source(api)
    path = api.workspace.marker_path(api.workspace.config_dir, "policy.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"config": {"size": 0}, "revision": "broken", "saved_at": "now"}), encoding="utf-8")
    assert api.client.get("/api/knowledge/documents/policy.txt/workspace").status_code == 500
