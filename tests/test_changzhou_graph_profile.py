"""The local graph profile can skip an unavailable optional rerank service."""

import os

from test_python_guidelines_knowledge_pipeline import load_subject_definitions


def test_disabled_graph_reranking_does_not_construct_a_remote_client(monkeypatch):

    def unavailable():
        raise AssertionError("Disabled reranking must not contact or construct the provider")

    monkeypatch.setenv("LIGHTRAG_RERANK_ENABLED", "false")
    cls = load_subject_definitions(
        'app/agents/packs/graph_retriever/node.py', 'GraphRetrieverAgent',
        os=os, Reranker=unavailable, StatefulAgent=object,
    )['GraphRetrieverAgent']
    agent = object.__new__(cls)
    assert agent._create_rerank_callback() is None
