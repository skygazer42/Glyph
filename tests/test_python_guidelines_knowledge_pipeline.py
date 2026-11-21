"""Offline behavior regressions for knowledge storage and pipeline contracts."""

import asyncio
from contextvars import ContextVar
from collections import OrderedDict
import hashlib
import io
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from threading import RLock
import re
import runpy
import tempfile
import threading
from types import SimpleNamespace
import zipfile

import pytest
import anyio

from test_python_guidelines_tooling import ROOT, load_definitions

FinalAnswer = runpy.run_path(str(ROOT / 'app/models/policy.py'))['FinalAnswer']


@pytest.mark.parametrize('payload', ['', 'invalid', '{bad}', '[]', '{}', '{"rule_id": null}'])
def test_rule_planner_rejects_malformed_or_incomplete_plan(payload):
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    agent = object.__new__(cls)
    with pytest.raises((ValueError, KeyError)):
        agent._parse_execution_plan(payload)


def test_graph_ingest_failure_is_distinct_from_disabled_graph():
    async def fail(documents):
        raise OSError('graph write failed')

    cls = load_subject_definitions('app/agents/pipeline/graph_agent.py', 'GraphAgent')['GraphAgent']
    agent = object.__new__(cls)
    agent.logger = logging.getLogger('test')
    agent._graph_agent = SimpleNamespace(add_documents=fail)
    with pytest.raises(OSError, match='graph write failed'):
        asyncio.run(agent.ingest([object()]))


def test_graph_query_failure_does_not_fabricate_a_knowledge_answer():
    async def fail(*args):
        raise OSError('graph query failed')

    cls = load_subject_definitions('app/agents/pipeline/graph_agent.py', 'GraphAgent')['GraphAgent']
    agent = object.__new__(cls)
    agent.logger = logging.getLogger('test')
    agent._graph_agent = SimpleNamespace(process_request=fail)
    agent._build_message_context = lambda: object()
    agent.knowledge_agent = SimpleNamespace(answer=lambda *args, **kwargs: pytest.fail('unexpected route switch'))
    with pytest.raises(OSError, match='graph query failed'):
        asyncio.run(agent.answer('policy'))


@pytest.mark.parametrize('text', ['invalid', '[{"question": "q"}]'])
def test_invalid_faq_data_does_not_silently_disable_faq(tmp_path, text):
    cls = load_subject_definitions('app/knowledge/faq_responder.py', 'FAQEntry', 'FAQResponder',
                      dataclass=dataclass, SequenceMatcher=SequenceMatcher, os=os, RLock=RLock,
                      logger=logging.getLogger('test'))['FAQResponder']
    path = tmp_path / 'faq.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises((ValueError, KeyError)):
        cls(str(path))


def test_loader_parse_failure_is_distinct_from_empty_document(tmp_path):
    cls = load_subject_definitions('app/knowledge/document_loader.py', 'DocumentLoader')['DocumentLoader']
    loader = cls()
    path = tmp_path / 'bad.txt'
    path.write_text('body', encoding='utf-8')

    def fail(path):
        raise OSError('parse failed')

    loader._extract_from_text = fail
    with pytest.raises(OSError, match='parse failed'):
        list(loader.iter_documents_from_directory(str(tmp_path)))


def test_hybrid_retriever_requires_stable_document_id():
    cls = load_subject_definitions('app/knowledge/hybrid_retrieval.py', 'HybridRetriever')['HybridRetriever']
    with pytest.raises(KeyError):
        cls([{'text': 'body', 'title': 't'}], {})


@pytest.mark.parametrize('amount', ['bad', '1.2.3'])
def test_invalid_template_amount_is_not_silently_replaced(amount):
    from app.agents.dsl_generator.template_registry import TemplateRegistry
    with pytest.raises(ValueError):
        TemplateRegistry._prepare_appliance_payload({'per_item_cap': amount})


def load_subject_definitions(path, *names, **extra):
    from app.agents.service.progress import emit_progress, progress_step, progress_tool, source_references

    return load_definitions(path, names, asyncio=asyncio, Path=Path,
                            logging=logging, json=json, re=re,
                            ContextVar=ContextVar, anyio=anyio,
                            emit_progress=emit_progress, progress_step=progress_step,
                            progress_tool=progress_tool, source_references=source_references, **extra)


def test_knowledge_search_failure_is_distinct_from_no_results():
    cls = load_subject_definitions('app/agents/pipeline/knowledge_agent.py', 'KnowledgeAgent')['KnowledgeAgent']

    class Tool:
        async def search(self, *args, **kwargs):
            raise OSError('store unavailable')

    agent = cls(Tool())
    with pytest.raises(OSError, match='store unavailable'):
        asyncio.run(agent._search_knowledge('policy'))


def test_enabled_hierarchical_search_failure_is_visible():
    async def fail(*args, **kwargs):
        raise OSError('hierarchical search failed')

    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService', time=__import__('time'), logger=SimpleNamespace(opt=lambda **kwargs: SimpleNamespace(warning=lambda *args: None)))['KnowledgeService']
    service = object.__new__(cls)
    service._last_timings = ContextVar('failed_hierarchical_timings')
    service.hierarchical_store = SimpleNamespace(has_index=True, search=fail)
    service.vector_store = SimpleNamespace(search=lambda **kwargs: pytest.fail('unexpected search fallback'))
    with pytest.raises(OSError, match='hierarchical search failed'):
        asyncio.run(service.search('query'))


def test_document_processor_keeps_parse_failure_visible_and_accepts_short_text():
    cls = load_subject_definitions('app/knowledge/document_processor.py', 'EnhancedDocumentProcessor')['EnhancedDocumentProcessor']
    processor = object.__new__(cls)
    processor.logger = logging.getLogger('test')
    processor.mineru_enabled = False
    processor.llamaindex_enabled = True

    async def short_text(path):
        return '短政策原文'

    processor._extract_with_llamaindex = short_text
    assert asyncio.run(processor.extract_text('policy.pdf')) == '短政策原文'

    async def fail(path):
        raise OSError('selected extractor failed')

    processor._extract_with_llamaindex = fail
    with pytest.raises(OSError, match='selected extractor failed'):
        asyncio.run(processor.extract_text('policy.pdf'))


def test_rewrite_cache_respects_conversation_context():
    from dataclasses import dataclass
    ns = load_subject_definitions('app/agents/pipeline/rewrite_agent.py', 'ContextHints', 'RewriteAgent',
                     dataclass=dataclass, OrderedDict=OrderedDict,
                     PolicyDomainContextBuilder=lambda: SimpleNamespace(build=lambda text: SimpleNamespace(normalized_query=text, keywords=[])))
    agent = ns['RewriteAgent']()
    query = '是否符合条件'
    a = asyncio.run(agent.rewrite(query, {'history': ['用户:家电以旧换新政策']}))
    b = asyncio.run(agent.rewrite(query, {'history': ['用户:汽车消费政策']}))
    assert '汽车' in b and a != b


@pytest.mark.parametrize('query,product,energy,price', [
    ('电视1级能效3000元能补贴多少', '电视', '1级能效', '3000元'),
    ('能补贴多少', '空调', '2级能效', '2000元'),
])
def test_rewrite_current_values_override_the_most_recent_history(query, product, energy, price):
    namespace = load_subject_definitions(
        'app/agents/pipeline/rewrite_agent.py', 'ContextHints', 'RewriteAgent', dataclass=dataclass,
    )
    agent = object.__new__(namespace['RewriteAgent'])
    hints = agent._build_context_hints({'history': [
        '用户:冰箱1级能效1000元', '用户:空调2级能效2000元',
    ]}, query)
    assert (hints.product, hints.energy, hints.price) == (product, energy, price)


@pytest.mark.parametrize('kind,value,expected', [
    ('float', True, 'INVALID_INPUT'), ('integer', True, 'INVALID_INPUT'),
    ('integer', 1.5, 'INVALID_INPUT'), ('integer', '0', 'QUALIFIED'), ('float', 0, 'QUALIFIED'),
])
def test_rule_agent_coercion_keeps_invalid_numeric_values_visible_to_engine(tmp_path, kind, value, expected):
    from app.agents.dsl_generator.rule_engine import PolicyEngine

    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    rule = {'rule_id': 'numeric', 'inputs': [{'name': 'amount', 'type': kind}],
            'output': {'status': 'QUALIFIED', 'final_result': '{{ inputs.amount }}'}}
    inputs = cls._coerce_inputs(rule, {'amount': value})
    engine = PolicyEngine(str(tmp_path))
    engine.rules['numeric'] = rule
    result = engine.execute('numeric', inputs)
    assert result['status'] == expected
    if expected == 'QUALIFIED':
        assert float(result['final_result']) == 0


def test_qualified_reviewed_rule_is_reported_as_verified():
    ns = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent',
                     PolicyEngine=lambda **kwargs: None, FinalAnswer=FinalAnswer, uuid4=__import__('uuid').uuid4)
    agent = ns['RuleEngineAgent']()
    agent.engine = SimpleNamespace(rules={'r': {}}, get_rule_info=lambda key: {},
                                   execute=lambda *args: {'status': 'QUALIFIED', 'final_result': 0,
                                                          'verification': {'status': 'verified_for_estimate', 'reviewed_on': '2026-11-21'}})
    agent._collect_rules = lambda: [{'rule_id': 'r', 'keywords': ['policy']}]

    async def plan(*args):
        return ns['RuleExecutionPlan'](rule_id='r', inputs={})

    agent._plan_execution = plan
    intent = {'intent': 'benefit_calculation'}
    answer = asyncio.run(agent.compute('policy', intent=intent))
    assert answer.verification_passed is True and answer.confidence == .85
    assert answer.metadata['intent'] == intent


def test_knowledge_service_runs_sync_vector_operations_off_loop():
    ns = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService',
                     settings=SimpleNamespace(system=SimpleNamespace(hybrid_retrieval_enabled=False)),
                     time=__import__('time'))
    thread_ids = []

    class Store:
        def search(self, **kwargs):
            thread_ids.append(threading.get_ident())
            return [], []

    service = ns['KnowledgeService'](Store(), use_hierarchical=False)
    asyncio.run(service.search('policy'))
    assert thread_ids and thread_ids[0] != threading.get_ident()


def test_loader_zero_limit_yields_nothing(tmp_path):
    cls = load_subject_definitions('app/knowledge/document_loader.py', 'DocumentLoader')['DocumentLoader']
    (tmp_path / 'policy.txt').write_text('policy', encoding='utf-8')
    loader = cls()
    loader.load_single_file = lambda path: object()
    assert list(loader.iter_documents_from_directory(str(tmp_path), limit=0)) == []


def test_loader_preserves_the_day_when_a_month_pattern_also_matches():
    cls = load_subject_definitions(
        'app/knowledge/document_loader.py', 'DocumentLoader', datetime=datetime,
    )['DocumentLoader']
    assert cls()._extract_dates('发布日期：2025年11月17日')['publish_date'] == datetime(2025, 11, 17)


def test_markdown_image_title_is_not_part_of_file_path(tmp_path):
    from dataclasses import dataclass
    ns = load_subject_definitions('app/knowledge/image_retrieval.py', 'ImageInfo', 'ImageExtractor',
                     dataclass=dataclass, hashlib=hashlib, os=__import__('os'))
    images = ns['ImageExtractor']().extract_images_from_markdown(str(tmp_path / 'p.md'), '![流程](images/a.png "标题")')
    assert len(images) == 1 and images[0].relative_path == 'images/a.png'


def test_reranker_zero_limit_does_not_make_request():
    cls = load_subject_definitions('app/knowledge/rerank.py', 'Reranker')['Reranker']
    ranker = object.__new__(cls)
    ranker.settings = SimpleNamespace(top_n=5)
    ranker.backend = 'dashscope'
    ranker._call_dashscope = lambda *args: pytest.fail('zero limit should not request')
    assert ranker.rerank('q', ['a'], top_n=0) == []


def test_hierarchy_preserves_last_subsection_when_new_top_heading_begins():
    cls = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor')['HierarchicalMarkdownProcessor']
    processor = cls(config=SimpleNamespace(), enable_images=False)
    result = processor.extract_hierarchy('# 标题\n# 第一章\n## 子章\n旧正文\n# 第二章\n新正文', 'd')
    assert result['sections'][0]['subsections'][0]['content'] == '旧正文'


def test_hierarchy_indexes_plain_text_without_headings():
    cls = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor')['HierarchicalMarkdownProcessor']
    result = cls(config=SimpleNamespace(), enable_images=False).extract_hierarchy('无标题正文', 'd')
    assert result['sections'][0]['content'] == '无标题正文'


def test_hierarchy_keeps_text_on_both_sides_of_a_deeper_heading():
    cls = load_subject_definitions(
        'app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
    )['HierarchicalMarkdownProcessor']
    processor = cls(config=SimpleNamespace(), enable_images=False)
    result = processor.extract_hierarchy('# 标题\n# 第一章\n## 子章\n前文\n### 细节\n后文', 'd')
    assert result['sections'][0]['subsections'][0]['content'] == '前文\n### 细节\n后文'


def test_simple_chunking_stops_at_the_end_instead_of_repeating_trailing_overlap():
    cls = load_subject_definitions(
        'app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
    )['HierarchicalMarkdownProcessor']
    processor = cls(config=SimpleNamespace(chunk_size=5, chunk_overlap=2), enable_images=False)
    assert processor._split_simple('abcdefgh') == ['abcde', 'defgh']


def test_keyword_chunking_preserves_prefix_and_short_tail():
    cls = load_subject_definitions(
        'app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
    )['HierarchicalMarkdownProcessor']
    processor = cls(config=SimpleNamespace(
        chunk_size=20, chunk_overlap=0, min_chunk_size=8, max_chunk_size=20,
        keyword_context_window=1, keywords={'补贴'},
    ), enable_images=False)
    text = '前言说明必须保留补贴和短尾'
    chunks = processor._split_by_keywords(text)
    assert ''.join(chunks).replace(' ', '') == text


@pytest.mark.parametrize('size,overlap', [(0, 0), (5, -1), (5, 5)])
def test_chunk_configuration_rejects_windows_that_cannot_advance(size, overlap):
    cls = load_subject_definitions(
        'app/knowledge/hierarchical_index.py', 'ChunkConfig', dataclass=dataclass, field=field,
    )['ChunkConfig']
    with pytest.raises(ValueError):
        cls(chunk_size=size, chunk_overlap=overlap)


def test_image_index_roundtrip_preserves_all_metadata_and_reads_legacy_entries(tmp_path):
    namespace = load_subject_definitions(
        'app/knowledge/image_retrieval.py', 'ImageInfo', 'ImageIndexer',
        dataclass=dataclass, asdict=asdict,
    )
    image = namespace['ImageInfo'](
        image_id='image', file_path='/images/p.png', relative_path='images/p.png',
        doc_id='policy', section_id='section', width=640, height=480, file_size=128,
        file_hash='hash', alt_text='流程', caption='申请步骤', context_before='前文',
        context_after='后文', qr_content='https://example.invalid/apply', is_qrcode=True,
        line_number=7, char_position=42, embedding_text='申请步骤和流程图',
    )
    indexer = object.__new__(namespace['ImageIndexer'])
    indexer.image_store = {'image': image}
    path = tmp_path / 'images.json'
    indexer.save_index(str(path))
    restored = object.__new__(namespace['ImageIndexer'])
    restored.load_index(str(path))
    assert restored.image_store == indexer.image_store

    path.write_text(json.dumps({'images': [{
        'image_id': 'legacy', 'file_path': '/old.png', 'relative_path': 'old.png', 'doc_id': 'policy',
    }]}), encoding='utf-8')
    restored.load_index(str(path))
    assert restored.image_store['legacy'].section_id == ''


def test_hierarchy_consumes_real_reranker_tuples():
    cls = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalRetriever')['HierarchicalRetriever']
    retriever = object.__new__(cls)
    retriever.reranker = SimpleNamespace(rerank=lambda **kwargs: [(1, .9, 'second'), (0, .2, 'first')])
    from llama_index.core.schema import TextNode
    nodes = [TextNode(text='first'), TextNode(text='second')]
    assert retriever._dashscope_rerank(nodes, 'q', 2) == [nodes[1], nodes[0]]


def test_hierarchy_rejects_missing_scores_and_selected_reranker_failure():
    cls = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalRetriever')['HierarchicalRetriever']
    retriever = object.__new__(cls)
    from llama_index.core.schema import TextNode
    node = TextNode(text='unscored result')
    with pytest.raises(ValueError, match='score'):
        retriever._scored_node(SimpleNamespace(node=node, score=None))

    def fail(**kwargs):
        raise OSError('configured reranker failed')

    retriever.reranker = SimpleNamespace(rerank=fail)
    with pytest.raises(OSError, match='configured reranker failed'):
        retriever._dashscope_rerank([node], 'query', 1)


def test_disabled_enhanced_index_does_not_claim_success():
    cls = load_subject_definitions('app/knowledge/llamaindex_integration.py', 'EnhancedVectorRetrieverAgent')['EnhancedVectorRetrieverAgent']
    agent = cls(use_llamaindex=False)
    assert asyncio.run(agent.add_documents([object()])) is False


def test_mineru_reads_nested_zip_without_extracting_to_disk():
    cls = load_subject_definitions('app/knowledge/mineru_adapter.py', 'MinerUAdapter',
                      io=io, zipfile=zipfile)['MinerUAdapter']
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive:
        archive.writestr('nested/full.md', '政策正文')
    assert cls._read_result_archive(payload.getvalue()) == '政策正文'


def test_ocr_failed_temp_write_removes_owned_file(tmp_path, monkeypatch):
    import numpy as np
    from PIL import Image
    ns = load_subject_definitions('app/knowledge/rapid_ocr_processor.py', 'OCRException', 'RapidOCRProcessor',
                     tempfile=tempfile, np=np, Image=Image, os=__import__('os'))
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    agent = object.__new__(ns['RapidOCRProcessor'])
    with pytest.raises(ns['OCRException']):
        agent._create_temp_image_file(object())
    assert list(tmp_path.iterdir()) == []


def test_llamaindex_reranker_uses_real_query_bundle_and_model_fields():
    from llama_index.core.postprocessor.types import BaseNodePostprocessor
    from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
    from pydantic import PrivateAttr

    calls = []

    class Service:
        def __init__(self, logger):
            pass

        def rerank(self, query, texts, **kwargs):
            calls.append((query, texts))
            return [(1, .9, texts[1]), (0, .2, texts[0])]

    config = SimpleNamespace(backend='dashscope', rerank_top_k=2)
    ns = load_subject_definitions('app/knowledge/rerank.py', 'LlamaIndexReranker',
                     BaseNodePostprocessor=BaseNodePostprocessor, PrivateAttr=PrivateAttr,
                     Reranker=Service, settings=SimpleNamespace(reranker=config),
                     _log=lambda: logging.getLogger('test'), NodeWithScore=NodeWithScore,
                     QueryBundle=QueryBundle, Any=__import__('typing').Any,
                     List=__import__('typing').List, Optional=__import__('typing').Optional)
    ranker = ns['LlamaIndexReranker']()
    nodes = [NodeWithScore(node=TextNode(text='a')), NodeWithScore(node=TextNode(text='b'))]
    result = ranker.postprocess_nodes(nodes, query_bundle=QueryBundle(query_str='policy'))
    assert [node.node.text for node in result] == ['b', 'a']
    assert [node.score for node in result] == [.9, .2]
    assert calls == [('policy', ['a', 'b'])]


def test_milvus_filter_quotes_do_not_escape_string_literals():
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore')['MilvusStore']
    store = object.__new__(cls)
    expression = store._build_filter({'doc_type': 'a" || true || "', 'source': 'a\\b'})
    assert expression == 'doc_type == "a\\" || true || \\"" && source like "%a\\\\b%"'


def test_milvus_close_disconnects_only_its_alias():
    disconnected: list[str] = []
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                      connections=SimpleNamespace(disconnect=disconnected.append))['MilvusStore']
    store = object.__new__(cls)
    released = []
    store.collection = SimpleNamespace(release=lambda: released.append(True))
    store._connection_alias = 'owned'
    store._connected = True
    store.close()
    store.close()
    assert disconnected == ['owned'] and released == []


def test_failed_index_build_cleans_all_temporary_markdown(tmp_path):
    def builder(storage):
        def fail(paths, **kwargs):
            assert Path(paths[0]).is_file()
            assert list(kwargs['document_ids'].values()) == ['original-id']
            raise OSError('embedding failed')

        return SimpleNamespace(processor=SimpleNamespace(), build_from_markdown_files=fail)

    cls = load_subject_definitions('app/knowledge/llamaindex_integration.py', 'LlamaIndexIntegration',
                      tempfile=tempfile, HierarchicalIndexBuilder=builder,
                      ChunkConfig=lambda **kwargs: kwargs)['LlamaIndexIntegration']
    integration = object.__new__(cls)
    integration.storage_dir = tmp_path
    doc = SimpleNamespace(id='original-id', title='title', source='source', doc_type='guideline', content='body')
    with pytest.raises(OSError, match='embedding failed'):
        asyncio.run(integration.build_index_from_documents([doc]))
    assert list(tmp_path.iterdir()) == []


def test_mineru_signed_upload_does_not_use_authenticated_api_session(tmp_path):
    import aiofiles
    api_calls = []
    uploaded = []

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self):
            return {'code': 0, 'data': {'batch_id': 'batch', 'file_urls': ['https://signed.invalid/upload']}}

        def raise_for_status(self):
            return None

    class UploadSession(Response):
        def __init__(self, **kwargs):
            assert 'headers' not in kwargs

        def put(self, url, **kwargs):
            uploaded.append((url, kwargs['data']))
            return Response()

    cls = load_subject_definitions('app/knowledge/mineru_adapter.py', 'MinerUAdapter',
                      aiohttp=SimpleNamespace(ClientSession=UploadSession, ClientTimeout=lambda **kwargs: None),
                      aiofiles=aiofiles, os=__import__('os'))['MinerUAdapter']
    agent = object.__new__(cls)
    def post(url, **kwargs):
        api_calls.append(url)
        return Response()

    agent.session = SimpleNamespace(closed=False, post=post)
    agent.base_url = 'https://api.invalid'
    agent.extract_formulas = agent.extract_tables = agent.ocr_enabled = False
    agent.language = 'ch'
    file = tmp_path / 'p.pdf'
    file.write_bytes(b'pdf')
    assert asyncio.run(agent._upload_file_official(str(file), {})) == 'batch'
    assert api_calls == ['https://api.invalid/file-urls/batch']
    assert uploaded == [('https://signed.invalid/upload', b'pdf')]


def test_mineru_local_upload_sends_server_url_for_the_configured_backend(tmp_path):
    import aiofiles

    fields = []

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def json(self):
            return {'results': {'policy': {'markdown': '政策正文'}}}

    def post(url, **kwargs):
        assert url == 'http://mineru.invalid/file_parse'
        return Response()

    async def get_session():
        return SimpleNamespace(post=post)

    cls = load_subject_definitions(
        'app/knowledge/mineru_adapter.py', 'MinerUAdapter', aiofiles=aiofiles, os=os,
        aiohttp=SimpleNamespace(
            FormData=lambda: SimpleNamespace(add_field=lambda name, value, **kwargs: fields.append((name, value))),
            ClientTimeout=lambda **kwargs: None,
        ),
    )['MinerUAdapter']
    adapter = object.__new__(cls)
    adapter.backend, adapter.language, adapter.base_url = 'vlm-http-client', 'ch', 'http://mineru.invalid'
    adapter._get_session = get_session
    path = tmp_path / 'policy.pdf'
    path.write_bytes(b'pdf')

    result = asyncio.run(adapter._extract_local(str(path), {'server_url': 'http://vlm.invalid'}))

    assert result['content'] == '政策正文'
    assert result['metadata']['backend'] == 'vlm-http-client'
    assert dict(fields)['server_url'] == 'http://vlm.invalid'


def test_ocr_pdf_closes_document_and_preserves_error_cause(tmp_path):
    closed = []

    class PDF:
        page_count = 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def __getitem__(self, index):
            raise OSError('page failed')

    ns = load_subject_definitions('app/knowledge/rapid_ocr_processor.py', 'OCRException', 'RapidOCRProcessor',
                     fitz=SimpleNamespace(open=lambda path: PDF()), os=__import__('os'))
    agent = object.__new__(ns['RapidOCRProcessor'])
    file = tmp_path / 'p.pdf'
    file.touch()
    with pytest.raises(ns['OCRException']) as error:
        agent.process_pdf(str(file))
    assert closed == [True] and isinstance(error.value.__cause__, OSError)


def test_hierarchy_child_relationship_keeps_every_section():
    from llama_index.core.schema import TextNode, RelatedNodeInfo, NodeRelationship
    cls = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
                      TextNode=TextNode, RelatedNodeInfo=RelatedNodeInfo,
                      NodeRelationship=NodeRelationship)['HierarchicalMarkdownProcessor']
    config = SimpleNamespace(chunking_strategy='simple', chunk_size=600, chunk_overlap=0, section_summary_size=250)
    processor = cls(config=config, enable_images=False)
    hierarchy = processor.extract_hierarchy('# 文档\n# A\na\n# B\nb', 'd')
    nodes = processor.create_nodes_from_hierarchy(hierarchy)
    children = nodes[0].child_nodes
    assert children is not None
    assert [child.node_id for child in children] == ['sec_d_0', 'sec_d_1']


def test_hierarchy_image_nodes_keep_the_stable_document_id_and_parent_link():
    from llama_index.core.schema import NodeRelationship, RelatedNodeInfo, TextNode

    cls = load_subject_definitions(
        'app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
        TextNode=TextNode, RelatedNodeInfo=RelatedNodeInfo, NodeRelationship=NodeRelationship,
    )['HierarchicalMarkdownProcessor']
    processor = object.__new__(cls)
    image = SimpleNamespace(doc_id='file-stem')
    processor.image_indexer = SimpleNamespace(process_markdown_with_images=lambda *args: (
        [image], [{'id': 'image', 'content': '流程图', 'metadata': {'type': 'image', 'doc_id': 'file-stem'}}],
    ))
    nodes = processor.create_nodes_from_hierarchy(
        {'doc_id': 'stable-policy', 'title': 'Policy', 'sections': []},
        md_path='policy.md', md_content='![流程图](p.png)',
    )

    assert image.doc_id == nodes[1].metadata['doc_id'] == 'stable-policy'
    assert nodes[1].parent_node.node_id == nodes[0].id_
    assert [child.node_id for child in nodes[0].child_nodes] == ['image']


def test_document_images_use_mounted_resources_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    markdown = tmp_path / 'resources' / 'policies' / 'p.md'
    cls = load_subject_definitions('app/knowledge/document_loader.py', 'DocumentLoader')['DocumentLoader']
    assert cls()._extract_images(markdown, '![流程](images/p.png)') == ['/resources/policies/images/p.png']


def test_knowledge_close_failure_still_closes_owned_vector_store():
    closed = []

    async def fail_close():
        raise OSError('hierarchical close failed')

    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService')['KnowledgeService']
    service = object.__new__(cls)
    service.hierarchical_store = SimpleNamespace(close=fail_close)
    service.vector_store = SimpleNamespace(close=lambda: closed.append(True))
    service._owns_vector_store = True
    with pytest.raises(OSError, match='hierarchical close failed'):
        asyncio.run(service.close())
    assert closed == [True]


def test_enhanced_index_search_failure_remains_visible():
    async def fail_search(*args, **kwargs):
        raise OSError('index unavailable')

    cls = load_subject_definitions('app/knowledge/llamaindex_integration.py', 'EnhancedVectorRetrieverAgent')['EnhancedVectorRetrieverAgent']
    agent = object.__new__(cls)
    agent.llamaindex = SimpleNamespace(has_index=True, search=fail_search)
    with pytest.raises(OSError, match='index unavailable'):
        asyncio.run(agent.search('policy'))


@pytest.mark.parametrize('backend', ['dashscope', 'xinference'])
@pytest.mark.parametrize('scores,expected', [({'relevance_score': .9}, .9), ({'score': 0}, 0), ({}, None)])
def test_reranker_scores_follow_provider_contract_and_never_invent_missing_zero(backend, scores, expected):
    closed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            closed.append(True)

        def raise_for_status(self):
            pass

        def json(self):
            items = [{'index': 0, **scores}]
            return {'output': {'results': items}} if backend == 'dashscope' else {'results': items}

    cls = load_subject_definitions('app/knowledge/rerank.py', 'Reranker')['Reranker']
    ranker = object.__new__(cls)
    ranker.settings = SimpleNamespace(return_documents=False, timeout=5)
    ranker.session = SimpleNamespace(post=lambda *args, **kwargs: Response())
    ranker.base_url = ranker.x_url = 'https://offline.invalid'
    ranker.model = 'offline'
    ranker.x_return_docs = False
    call = ranker._call_dashscope if backend == 'dashscope' else ranker._call_xinference
    if expected is None:
        with pytest.raises(ValueError):
            call('q', ['text'], 1)
    else:
        assert call('q', ['text'], 1) == [(0, expected, 'text')]
    assert closed == [True]


@pytest.mark.parametrize('backend', ['dashscope', 'xinference'])
@pytest.mark.parametrize('payload', [{}, {'items': [{}]}, {'items': [{'index': 8, 'score': .9}]}])
def test_reranker_malformed_response_does_not_masquerade_as_no_results(backend, payload):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def json(self):
            if 'items' not in payload:
                return payload
            return {'output': {'results': payload['items']}} if backend == 'dashscope' else {'results': payload['items']}

    cls = load_subject_definitions('app/knowledge/rerank.py', 'Reranker')['Reranker']
    ranker = object.__new__(cls)
    ranker.settings = SimpleNamespace(return_documents=False, timeout=5)
    ranker.session = SimpleNamespace(post=lambda *args, **kwargs: Response())
    ranker.base_url = ranker.x_url = 'https://offline.invalid'
    ranker.model = 'offline'
    ranker.x_return_docs = False
    call = ranker._call_dashscope if backend == 'dashscope' else ranker._call_xinference
    with pytest.raises((KeyError, TypeError, ValueError)):
        call('q', ['text'], 1)


def test_text2sql_pipeline_uses_connection_owned_async_boundary():
    calls = []

    async def run(connection_id, natural_language_query):
        calls.append((connection_id, natural_language_query))
        return SimpleNamespace(sql='SELECT 0', results=[{'value': 0}], error=None)

    namespace = load_subject_definitions(
        'app/agents/pipeline/text2sql_agent.py', 'answer_text2sql_query', '_build_text2sql_answer',
        process_text2sql_query_for_connection_async=run, FinalAnswer=FinalAnswer,
        uuid4=__import__('uuid').uuid4, logger=logging.getLogger(__name__),
    )
    answer = asyncio.run(namespace['answer_text2sql_query']('question', connection_id=3))
    assert calls == [(3, 'question')]
    assert answer.metadata['rows'] == [{'value': 0}]
    assert answer.metadata['connection_id'] == 3


def test_knowledge_service_validates_limits_before_storage():
    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService', time=__import__('time'))['KnowledgeService']
    service = cls(SimpleNamespace(search=lambda **kwargs: pytest.fail('invalid limit reached storage')),
                  use_hierarchical=False)
    with pytest.raises(ValueError, match='top_k'):
        asyncio.run(service.search('query', top_k=-1))
    assert asyncio.run(service.search('query', top_k=0)) == ([], [])


def test_knowledge_service_does_not_modify_borrowed_document():
    from app.models.policy import PolicyDocument, PolicyType
    document = PolicyDocument(title='p', content='body', source='source', doc_type=PolicyType.GUIDELINE,
                              retrieval_origin='original')
    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService', time=__import__('time'))['KnowledgeService']
    service = cls(SimpleNamespace(search=lambda **kwargs: ([document], [.8])), use_hierarchical=False)
    docs, scores = asyncio.run(service.search('q'))
    assert document.retrieval_origin == 'original'
    assert docs[0] is not document and docs[0].retrieval_origin == 'knowledge_base'
    assert scores == [.8]


def test_knowledge_timings_belong_to_the_search_task():
    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService', time=__import__('time'))['KnowledgeService']
    service = cls(SimpleNamespace(search=lambda **kwargs: ([], [])), use_hierarchical=False)

    async def check():
        await asyncio.create_task(service.search('q'))
        assert service.last_timings == {}
        await service.search('q')
        assert service.last_timings['total_ms'] is not None

    asyncio.run(check())


def test_knowledge_close_finishes_in_cancelled_scope_and_preserves_cancellation():
    closed = []

    async def close_hierarchy():
        await anyio.lowlevel.checkpoint()
        closed.append('hierarchy')

    cls = load_subject_definitions('app/knowledge/service.py', 'KnowledgeService')['KnowledgeService']
    service = object.__new__(cls)
    service.hierarchical_store = SimpleNamespace(close=close_hierarchy)
    service.vector_store = SimpleNamespace(close=lambda: closed.append('vector'))
    service._owns_vector_store = True

    async def check():
        with anyio.CancelScope() as scope:
            scope.cancel()
            try:
                await anyio.lowlevel.checkpoint()
            finally:
                await service.close()
        assert scope.cancelled_caught

    anyio.run(check)
    assert closed == ['hierarchy', 'vector']


def test_mineru_signed_download_uses_an_unauthenticated_owned_session():
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('full.md', 'body')
    closed = []

    class Response:
        status = 200

        def raise_for_status(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def read(self):
            return archive.getvalue()

    class DownloadSession(Response):
        def __init__(self, **kwargs):
            assert 'headers' not in kwargs

        async def __aexit__(self, *args):
            closed.append(True)

        def get(self, url, **kwargs):
            assert url == 'https://signed.invalid/result'
            return Response()

    cls = load_subject_definitions('app/knowledge/mineru_adapter.py', 'MinerUAdapter',
                      aiohttp=SimpleNamespace(ClientSession=DownloadSession, ClientTimeout=lambda **kwargs: None),
                      io=io, zipfile=zipfile)['MinerUAdapter']
    adapter = object.__new__(cls)
    adapter.session = SimpleNamespace(closed=False, get=lambda *a, **kw: pytest.fail('authenticated download'))
    result = asyncio.run(adapter._download_and_extract('https://signed.invalid/result'))
    assert result == 'body' and closed == [True]


def test_integration_close_finishes_in_cancelled_scope_once():
    closed = []
    cls = load_subject_definitions('app/knowledge/llamaindex_integration.py', 'LlamaIndexIntegration')['LlamaIndexIntegration']
    integration = object.__new__(cls)
    integration.has_index = True
    integration.retriever = SimpleNamespace(close=lambda: closed.append(True))

    async def check():
        with anyio.CancelScope() as scope:
            scope.cancel()
            try:
                await anyio.lowlevel.checkpoint()
            finally:
                await integration.close()
        assert scope.cancelled_caught
        await integration.close()

    anyio.run(check)
    assert closed == [True] and integration.has_index is False


def test_hierarchical_demo_closes_retriever_after_search_failure():
    closed = []

    def fail(*args, **kwargs):
        raise OSError('search failed')

    ns = load_subject_definitions('app/knowledge/hierarchical_index.py', 'test_retrieval',
                     HierarchicalRetriever=lambda **kwargs: SimpleNamespace(retrieve=fail, close=lambda: closed.append(True)))
    with pytest.raises(OSError, match='search failed'):
        ns['test_retrieval']()
    assert closed == [True]



def test_rewrite_consumes_actual_memory_history():
    memory = runpy.run_path(str(ROOT / 'app/agents/framework/common/autogen_memory_store.py'))
    ns = load_subject_definitions('app/agents/pipeline/rewrite_agent.py', 'ContextHints', 'RewriteAgent',
                     dataclass=dataclass, OrderedDict=OrderedDict,
                     PolicyDomainContextBuilder=lambda: SimpleNamespace(build=lambda text: SimpleNamespace(normalized_query=text, keywords=[])))
    agent = ns['RewriteAgent']()

    async def exchange():
        await memory['add_user_message']('rewrite-context', '家电以旧换新政策')
        await memory['add_assistant_message']('rewrite-context', '请提供商品能效和价格')
        history = memory['get_recent_messages']('rewrite-context')
        assert history == ['用户:家电以旧换新政策', '助手:请提供商品能效和价格']
        return await agent.rewrite('是否符合条件', {'history': history})

    assert '家电以旧换新政策' in asyncio.run(exchange())


@pytest.mark.parametrize('context', [None, {}, {'history': []}])
def test_rewrite_without_history_keeps_current_query(context):
    ns = load_subject_definitions('app/agents/pipeline/rewrite_agent.py', 'ContextHints', 'RewriteAgent',
                     dataclass=dataclass, OrderedDict=OrderedDict,
                     PolicyDomainContextBuilder=lambda: SimpleNamespace(build=lambda text: SimpleNamespace(normalized_query=text, keywords=[])))
    assert asyncio.run(ns['RewriteAgent']().rewrite('你好', context)) == '你好'


def test_graph_summary_rejects_empty_model_answer():
    async def respond(*args):
        return SimpleNamespace(content='  \n ')

    ns = load_subject_definitions('app/agents/pipeline/graph_agent.py', 'GraphAgent',
                     model_client=SimpleNamespace(create=respond), UserMessage=lambda **kwargs: kwargs)
    agent = object.__new__(ns['GraphAgent'])
    with pytest.raises(ValueError, match='empty'):
        asyncio.run(agent._summarize_graph('real graph relations', 'policy'))


@pytest.mark.parametrize('embedding', [[float('nan')], ['1.0'], []])
def test_milvus_embedding_rejects_malformed_vector(embedding):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def json(self):
            return {'output': {'embeddings': [{'embedding': embedding}]}}

    cfg = SimpleNamespace(dashscope_api_key='token', dashscope_base_url='offline',
                          dashscope_dimension=None, dashscope_output_type=None, timeout=1)
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                      settings=SimpleNamespace(embedding=cfg), np=__import__('numpy'),
                      requests=SimpleNamespace(post=lambda *args, **kwargs: Response()))['MilvusStore']
    store = object.__new__(cls)
    store.model_name = 'text-embedding-v3'
    with pytest.raises(ValueError):
        store._embed_dashscope(['query'])


def test_milvus_stats_rejects_closed_collection():
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore')['MilvusStore']
    store = object.__new__(cls)
    store.collection = None
    store.collection_name = 'test'
    store.embedding_dim = 2
    store.embedding_backend = 'openai'
    store.model_name = 'test'
    store.host, store.port, store.backend = 'localhost', 19530, 'openai'
    with pytest.raises(RuntimeError, match='collection|Collection'):
        store.get_stats()


def test_text_decoder_reports_exhausted_supported_encodings(tmp_path):
    cls = load_subject_definitions('app/knowledge/document_processor.py', 'EnhancedDocumentProcessor')['EnhancedDocumentProcessor']
    processor = object.__new__(cls)
    path = tmp_path / 'invalid.txt'
    path.write_bytes(b'\x81')
    with pytest.raises(UnicodeDecodeError):
        asyncio.run(processor._extract_from_text(path))


@pytest.mark.parametrize('extra', [{'tags': 'tag'}, {'source': 42}])
def test_faq_rejects_invalid_external_field_types(tmp_path, extra):
    cls = load_subject_definitions('app/knowledge/faq_responder.py', 'FAQEntry', 'FAQResponder',
                      dataclass=dataclass, SequenceMatcher=SequenceMatcher, os=os, RLock=RLock,
                      logger=logging.getLogger('test'))['FAQResponder']
    path = tmp_path / 'faq.json'
    path.write_text(json.dumps([{'question': ' q ', 'answer': ' a ', **extra}]), encoding='utf-8')
    with pytest.raises(ValueError):
        cls(str(path))


@pytest.mark.parametrize('backend', ['dashscope', 'xinference'])
@pytest.mark.parametrize('score', [float('nan'), float('inf')])
def test_reranker_rejects_nonfinite_external_scores(backend, score):
    cls = load_subject_definitions('app/knowledge/rerank.py', 'Reranker')['Reranker']
    ranker = object.__new__(cls)
    ranker.model = 'test'
    ranker.base_url = 'https://example.invalid'
    ranker.settings = SimpleNamespace(return_documents=False, timeout=1)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def json(self):
            rows = [{'index': 0, 'relevance_score': score}]
            return {'output': {'results': rows}} if backend == 'dashscope' else {'data': rows}

    ranker.session = SimpleNamespace(post=lambda *args, **kwargs: Response())
    with pytest.raises(ValueError):
        getattr(ranker, f'_call_{backend}')('query', ['doc'], 1)


def test_rule_planner_rejects_structured_reasoning():
    cls = load_subject_definitions('app/agents/pipeline/rule_agent.py', 'RuleEngineAgent')['RuleEngineAgent']
    with pytest.raises(ValueError):
        object.__new__(cls)._parse_execution_plan('{"rule_id":null,"inputs":{},"reasoning":{}}')


def test_selected_summary_failure_does_not_return_truncated_success():
    closed = []

    class Client:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            raise OSError('summary unavailable')

        def close(self):
            closed.append(True)

    ns = load_subject_definitions('app/knowledge/hierarchical_index.py', 'HierarchicalMarkdownProcessor',
                     OpenAI=Client, settings=SimpleNamespace(model=SimpleNamespace(
                         llm_api_key='offline', llm_base_url='https://example.invalid', llm_model_name='test')))
    processor = object.__new__(ns['HierarchicalMarkdownProcessor'])
    processor.config = SimpleNamespace(section_summary_size=10)
    with pytest.raises(OSError, match='summary unavailable'):
        processor.generate_section_summary('real text', use_llm=True)
    assert closed == [True]


@pytest.mark.parametrize('strategy', ['vector', 'hybrid'])
def test_simple_hybrid_retriever_rejects_unimplemented_strategies(strategy):
    cls = load_subject_definitions('app/knowledge/hybrid_retrieval.py', 'HybridRetriever')['HybridRetriever']
    with pytest.raises(NotImplementedError):
        cls([], {}).retrieve('query', chunk_strategy=strategy)


@pytest.mark.parametrize("row", [{"data_id": "d", "state": "done", "markdown": 42}, {"data_id": "d", "state": 1}])
def test_mineru_sync_rejects_invalid_external_rows(row):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def json(self):
            return {"code": 0, "data": {"extract_result": [row]}}
    ns = load_subject_definitions("app/knowledge/document_processor.py", "EnhancedDocumentProcessor", requests=SimpleNamespace(get=lambda *a, **kw: Response()), time=__import__("time"))
    processor = object.__new__(ns["EnhancedDocumentProcessor"])
    processor.mineru_poll_timeout, processor.mineru_timeout, processor.mineru_poll_interval = .02, 1, 0
    processor.mineru_base_url, processor.mineru_api_key = "offline", "token"
    with pytest.raises(ValueError):
        processor._mineru_poll_batch_result("batch", "d")


def test_mineru_sync_upload_validates_batch_identifier():
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def json(self):
            return {"code": 0, "data": {"batch_id": 42, "file_urls": ["signed"]}}
    ns = load_subject_definitions("app/knowledge/document_processor.py", "EnhancedDocumentProcessor", requests=SimpleNamespace(post=lambda *a, **kw: Response()), uuid4=lambda: "d")
    processor = object.__new__(ns["EnhancedDocumentProcessor"])
    processor.mineru_model_version, processor.mineru_timeout = "pipeline", 1
    processor.mineru_base_url, processor.mineru_api_key = "offline", "token"
    with pytest.raises(ValueError):
        processor._mineru_request_upload_link("test.pdf")


@pytest.fixture
def make_milvus_store():
    def build(payload, dimension=2, requested_dimension=None):
        requests_sent, responses_closed = [], []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                responses_closed.append(True)

            def raise_for_status(self):
                pass

            def json(self):
                return payload

        def post(url, **kwargs):
            requests_sent.append(kwargs['json'])
            return Response()

        config = SimpleNamespace(dashscope_api_key='token', dashscope_base_url='offline',
                                 dashscope_dimension=requested_dimension,
                                 dashscope_output_type=None, timeout=1)
        cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                          settings=SimpleNamespace(embedding=config), np=__import__('numpy'),
                          requests=SimpleNamespace(post=post))['MilvusStore']
        store = object.__new__(cls)
        store.model_name = 'text-embedding-v3'
        store.embedding_dim = dimension
        return SimpleNamespace(store=store, sent=requests_sent, closed=responses_closed)

    return build


@pytest.mark.parametrize('value', [float('inf'), float('-inf'), False, None])
def test_milvus_embedding_rejects_other_nonfinite_or_nonnumeric_values(make_milvus_store, value):
    case = make_milvus_store({'output': {'embeddings': [{'embedding': [value, 1]}]}})
    with pytest.raises(ValueError):
        case.store._embed_dashscope(['query'])
    assert case.closed == [True]


@pytest.mark.parametrize('embeddings', [[], [{'embedding': [0, 1]}, {'embedding': [1, 0]}]])
def test_milvus_embedding_count_matches_single_text_request(make_milvus_store, embeddings):
    case = make_milvus_store({'output': {'embeddings': embeddings}})
    with pytest.raises(ValueError):
        case.store._embed_dashscope(['query'])
    assert case.closed == [True]


@pytest.mark.parametrize('embedding', [[1], [1, 2, 3]])
def test_milvus_embedding_dimension_matches_collection(make_milvus_store, embedding):
    case = make_milvus_store({'output': {'embeddings': [{'embedding': embedding}]}})
    with pytest.raises(ValueError, match='dimension'):
        case.store._embed_dashscope(['query'])
    assert case.closed == [True]


@pytest.mark.parametrize('embedding,expected', [([0, 0], [0, 0]), ([0, 2], [0, 1])])
def test_milvus_embedding_preserves_zero_and_normalizes_real_numbers(
    make_milvus_store, embedding, expected
):
    payload = {'request_id': 'request', 'usage': {'total_tokens': 2},
               'output': {'embeddings': [{'embedding': embedding, 'text_index': 0}]}}
    case = make_milvus_store(payload)
    result = case.store._embed_dashscope(['query'])
    assert result.shape == (1, 2) and str(result.dtype) == 'float32'
    assert result[0].tolist() == pytest.approx(expected)
    assert case.closed == [True]


def test_milvus_explicit_dimension_zero_is_not_silently_omitted(make_milvus_store):
    case = make_milvus_store({'output': {'embeddings': [{'embedding': [0, 1]}]}},
                               requested_dimension=0)
    case.store._embed_dashscope(['query'])
    assert case.sent[0].get('parameters', {}).get('dimension') == 0


@pytest.mark.parametrize('user,password,expected_user,expected_password', [
    ('', '', '', ''),
    (None, None, 'configured-user', 'configured-password'),
])
def test_milvus_connection_preserves_explicit_empty_credentials(
    user, password, expected_user, expected_password
):
    connected: list[dict[str, object]] = []
    disconnected: list[str] = []
    collection = SimpleNamespace(
        schema=SimpleNamespace(fields=[SimpleNamespace(name='embedding', params={'dim': 1536})]),
        load=lambda: None, release=lambda: None,
    )
    database = SimpleNamespace(milvus_host='offline', milvus_port=19530,
                               milvus_user='configured-user', milvus_password='configured-password',
                               milvus_db_name='default', milvus_collection_name='policies')
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                      settings=SimpleNamespace(database=database),
                      uuid4=lambda: SimpleNamespace(hex='empty-credentials'),
                      connections=SimpleNamespace(connect=lambda **kwargs: connected.append(kwargs),
                                                  disconnect=disconnected.append),
                      utility=SimpleNamespace(has_collection=lambda *args, **kwargs: True),
                      Collection=lambda *args, **kwargs: collection)['MilvusStore']
    store = cls(model_name='text-embedding-3-small', backend='openai', user=user, password=password)
    try:
        assert len(connected) == 1
        assert connected[0]['user'] == expected_user
        assert connected[0]['password'] == expected_password
    finally:
        store.close()
    assert disconnected == ['glyph-empty-credentials']


@pytest.mark.parametrize('backend,dimension,requested_dimension', [
    ('openai', 0, None), ('openai', -2, None),
    ('dashscope', 1536, 0), ('dashscope', 1536, -2),
    ('dashscope', 0, None), ('dashscope', -2, None),
])
def test_milvus_dimension_rejects_nonpositive_configuration(
    backend, dimension, requested_dimension
):
    config = SimpleNamespace(dimension=dimension, dashscope_dimension=requested_dimension)
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                      settings=SimpleNamespace(embedding=config))['MilvusStore']
    store = object.__new__(cls)
    store.backend, store.model_name = backend, 'provider-model'
    with pytest.raises(ValueError, match='positive'):
        store._infer_dim()


@pytest.mark.parametrize('backend,model,dimension,requested_dimension,expected', [
    ('openai', 'text-embedding-3-large', 0, None, 3072),
    ('openai', 'text-embedding-3-small', 0, None, 1536),
    ('openai', 'text-embedding-ada-002', 0, None, 1536),
    ('openai', 'provider-model', 2048, None, 2048),
    ('dashscope', 'text-embedding-v3', 0, 2048, 2048),
    ('dashscope', 'text-embedding-v3', 512, None, 512),
    ('dashscope', 'text-embedding-v3', 1536, None, 1024),
])
def test_milvus_dimension_keeps_model_and_provider_defaults(
    backend, model, dimension, requested_dimension, expected
):
    config = SimpleNamespace(dimension=dimension, dashscope_dimension=requested_dimension)
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore',
                      settings=SimpleNamespace(embedding=config))['MilvusStore']
    store = object.__new__(cls)
    store.backend, store.model_name = backend, model
    assert store._infer_dim() == expected


@pytest.mark.parametrize('method', ['_get_model_name_from_backend', '_infer_dim'])
def test_milvus_unsupported_backend_fails_before_connection(method):
    config = SimpleNamespace(dimension=1536)
    settings = SimpleNamespace(embedding=config)
    cls = load_subject_definitions('app/knowledge/milvus.py', 'MilvusStore', settings=settings)['MilvusStore']
    store = object.__new__(cls)
    store.backend, store.model_name = 'unsupported', 'provider-model'
    arguments = (settings,) if method == '_get_model_name_from_backend' else ()
    with pytest.raises(ValueError, match='Unsupported backend'):
        getattr(store, method)(*arguments)


@pytest.fixture
def make_llamaindex_settings(monkeypatch):
    for name in ('LLM_API_KEY', 'OPENAI_API_KEY', 'DASHSCOPE_API_KEY'):
        monkeypatch.delenv(name, raising=False)

    def build(backend, model_name, api_key='configured-key'):
        calls: list[dict[str, object]] = []

        def llm(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(**kwargs)

        config = SimpleNamespace(
            embedding=SimpleNamespace(backend=backend, dashscope_api_key='embedding-key',
                                          openai_api_key='embedding-key', openai_model='embedding-model',
                                          openai_base_url='https://embedding.invalid'),
            model=SimpleNamespace(llm_api_key=api_key, llm_model_name=model_name,
                                  llm_base_url='https://configured.invalid'),
        )
        sdk_settings = SimpleNamespace(llm=None)
        cls = load_subject_definitions(
            'app/knowledge/llamaindex_hybrid_retrieval.py', 'LlamaIndexHybridRetriever',
            settings=config, Settings=sdk_settings, os=os, OpenAI=llm,
            OpenAIEmbedding=lambda **kwargs: kwargs,
            DashScopeEmbedding=lambda **kwargs: kwargs,
            DashScopeTextEmbeddingModels=SimpleNamespace(TEXT_EMBEDDING_V3='text-embedding-v3'),
            DashScopeTextEmbeddingType=SimpleNamespace(TEXT_TYPE_DOCUMENT='document'),
        )['LlamaIndexHybridRetriever']
        return SimpleNamespace(retriever=object.__new__(cls), calls=calls, settings=sdk_settings)

    return build


@pytest.mark.parametrize('backend', ['dashscope', 'openai'])
@pytest.mark.parametrize('model_name', ['', '  '])
def test_llamaindex_settings_rejects_blank_configured_llm_model(
    make_llamaindex_settings, backend, model_name
):
    case = make_llamaindex_settings(backend, model_name)
    with pytest.raises(ValueError, match='llm_model_name'):
        case.retriever._setup_llama_settings()
    assert case.calls == []


@pytest.mark.parametrize('backend', ['dashscope', 'openai'])
def test_llamaindex_settings_keeps_configured_llm_model(make_llamaindex_settings, backend):
    case = make_llamaindex_settings(backend, 'custom-model')
    case.retriever._setup_llama_settings()
    assert case.calls == [{'model': 'custom-model', 'api_key': 'configured-key',
                           'api_base': 'https://configured.invalid'}]
    assert case.settings.llm.model == 'custom-model'


@pytest.mark.parametrize('backend', ['dashscope', 'openai'])
def test_llamaindex_settings_keeps_llm_optional_without_key(make_llamaindex_settings, backend):
    case = make_llamaindex_settings(backend, '', api_key=None)
    case.retriever._setup_llama_settings()
    assert case.calls == []
    assert case.settings.llm is None
