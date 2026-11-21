"""Bulk imports may defer a flush while ordinary uploads keep their contract."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.knowledge.milvus import MilvusStore


@pytest.mark.parametrize("flush,expected_calls", [(True, 1), (False, 0)])
def test_flush_can_be_deferred_without_changing_upsert(flush, expected_calls):
    store = MilvusStore.__new__(MilvusStore)
    store.collection = MagicMock()
    store._embed_texts = MagicMock(return_value=np.array([[0.1, 0.2]]))
    document = SimpleNamespace(id="stable-id", title="事项", content="真实全文", source="/actual/source", doc_type="guideline")
    store.add_documents([document], upsert=True, flush=flush)
    store.collection.upsert.assert_called_once()
    assert store.collection.flush.call_count == expected_calls
    assert store.collection.upsert.call_args.args[0][0]["content"] == "真实全文"


def test_ordinary_uploads_still_flush_by_default():
    store = MilvusStore.__new__(MilvusStore)
    store.collection = MagicMock()
    store._embed_texts = MagicMock(return_value=np.array([[0.1, 0.2]]))
    document = SimpleNamespace(id="stable-id", title="事项", content="全文", source="/actual/source", doc_type="guideline")
    store.add_documents([document])
    store.collection.insert.assert_called_once()
    store.collection.flush.assert_called_once()
