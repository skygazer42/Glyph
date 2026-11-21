"""Offline HTTP regressions for real GraphML exploration; no application clients start."""

import importlib.util
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
NS = "http://graphml.graphdrawing.org/xmlns"


def write_graph(path, nodes, links, *, directed=False):
    root = ET.Element("graphml", xmlns=NS)
    fields = {
        "label": "entity_name", "type": "entity_type", "description": "description",
        "source_id": "source_id", "weight": "weight", "keywords": "keywords",
    }
    for key, name in fields.items():
        ET.SubElement(root, "key", {"id": key, "attr.name": name})
    graph = ET.SubElement(root, "graph", edgedefault="directed" if directed else "undirected")
    for values in nodes:
        element = ET.SubElement(graph, "node", id=values["id"])
        for key in ("label", "type", "description", "source_id"):
            if key in values:
                ET.SubElement(element, "data", key=key).text = values[key]
    for values in links:
        attrs = {key: values[key] for key in ("id", "source", "target", "directed") if key in values}
        element = ET.SubElement(graph, "edge", attrs)
        for key in ("weight", "keywords", "description"):
            if key in values:
                ET.SubElement(element, "data", key=key).text = str(values[key])
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIGHTRAG_WORKDIR", "resources/data/lightrag")
    name = "_graph_exploration_api"
    spec = importlib.util.spec_from_file_location(name, ROOT / "app/api/endpoints/knowledge_graph.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    application = FastAPI()
    application.include_router(module.router, prefix="/api/knowledge-graph")
    graph_file = tmp_path / "resources/data/lightrag/graph_chunk_entity_relation.graphml"
    with TestClient(application) as client:
        yield SimpleNamespace(module=module, client=client, graph_file=graph_file)


def test_all_graph_endpoints_use_the_configured_regional_directory(api, monkeypatch, tmp_path):
    write_graph(api.graph_file, [{"id": "旧地区"}], [])
    regional = tmp_path / "changzhou_graph"
    write_graph(regional / "graph_chunk_entity_relation.graphml", [{"id": "常州市"}], [])
    monkeypatch.setenv("LIGHTRAG_WORKDIR", str(regional))
    graph = api.client.get('/api/knowledge-graph/graph')
    assert graph.status_code == 200
    assert {row['id'] for row in graph.json()['nodes']} == {'常州市'}
    stats = api.client.get('/api/knowledge-graph/graph/stats')
    assert stats.status_code == 200 and stats.json()['nodes'] == 1
    subset = api.client.get('/api/knowledge-graph/subgraph')
    assert subset.status_code == 200
    assert {row['id'] for row in subset.json()['nodes']} == {'常州市'}


def get_subgraph(api, **params):
    response = api.client.get("/api/knowledge-graph/subgraph", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_overview_starts_with_connected_policy_and_obeys_both_caps(api):
    nodes = [{"id": f"n{i}", "type": '"POLICY"' if i == 27 else "organization"} for i in range(40)]
    nodes.append({"id": "isolated-policy", "type": "policy"})
    links = [{"source": f"n{i}", "target": f"n{i + 1}", "weight": i + 1} for i in range(39)]
    write_graph(api.graph_file, nodes, links)

    overview = get_subgraph(api)
    assert len(overview["nodes"]) == 24
    assert overview["nodes"][0]["id"] == "n27"
    assert overview["nodes"][0]["type"] == '"POLICY"'
    assert "isolated-policy" not in {node["id"] for node in overview["nodes"]}
    assert len(overview["links"]) == 23
    assert overview["total_nodes"] == 41 and overview["total_links"] == 39
    assert overview["center_id"] is None and overview["truncated"] is True
    assert len(get_subgraph(api, limit=3)["nodes"]) == 3


@pytest.mark.parametrize("depth,expected", [(1, {"a", "b"}), (2, {"a", "b", "c"}), (3, {"a", "b", "c", "d"})])
def test_center_bfs_depth_is_bounded_and_keeps_all_induced_edges(api, depth, expected):
    write_graph(api.graph_file, [{"id": node_id} for node_id in "abcde"], [
        {"source": "a", "target": "b", "weight": 0},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "d"},
        {"source": "d", "target": "e"},
        {"source": "a", "target": "b", "id": "edge:0", "directed": "true"},
        {"source": "b", "target": "b"},
    ])
    data = get_subgraph(api, node_id="a", depth=depth)
    assert {node["id"] for node in data["nodes"]} == expected
    assert data["center_id"] == "a" and data["truncated"] is False
    assert data["total_nodes"] == 5 and data["total_links"] == 6
    assert len([link for link in data["links"] if link["source"] == "a" and link["target"] == "b"]) == 2
    assert len([link for link in data["links"] if link["source"] == link["target"]]) == 1
    assert {node["id"]: node["neighbor_count"] for node in data["nodes"]}["b"] == 2
    by_id = {link["id"]: link for link in data["links"]}
    assert by_id["edge:0"]["weight"] == 0 and by_id["edge:0"]["directed"] is False
    assert by_id["graphml:edge:0"]["directed"] is True
    overview_edges = {link["id"]: link for link in get_subgraph(api)["links"]}
    assert all(overview_edges[edge_id] == edge for edge_id, edge in by_id.items())


def test_limit_truncation_detects_more_nodes_only_within_requested_depth(api):
    write_graph(api.graph_file, [{"id": node_id} for node_id in "abc"], [
        {"source": "a", "target": "b"}, {"source": "b", "target": "c"},
    ])
    assert get_subgraph(api, node_id="a", depth=1, limit=2)["truncated"] is False
    assert get_subgraph(api, node_id="a", depth=2, limit=2)["truncated"] is True
    limited = get_subgraph(api, node_id="b", depth=3, limit=1)
    assert [node["id"] for node in limited["nodes"]] == ["b"]
    assert limited["truncated"] is True and limited["links"] == []


def test_cycles_disconnected_components_and_self_only_nodes_are_not_duplicated(api):
    write_graph(api.graph_file, [{"id": node_id} for node_id in "abcdef"], [
        {"source": "a", "target": "b"}, {"source": "b", "target": "c"},
        {"source": "c", "target": "a"}, {"source": "d", "target": "e"},
        {"source": "f", "target": "f"},
    ])
    overview = get_subgraph(api)
    assert len(overview["nodes"]) == 6 and len(overview["links"]) == 5
    assert overview["truncated"] is False
    assert {node["id"] for node in get_subgraph(api, node_id="a", depth=3)["nodes"]} == {"a", "b", "c"}
    single = get_subgraph(api, node_id="f", depth=3, limit=1)
    assert single["nodes"][0]["neighbor_count"] == 0
    assert len(single["links"]) == 1 and single["truncated"] is False


def test_directed_default_and_per_edge_overrides_do_not_restrict_neighbor_discovery(api):
    write_graph(api.graph_file, [{"id": node_id} for node_id in "abc"], [
        {"source": "a", "target": "b"}, {"source": "b", "target": "c", "directed": "false"},
    ], directed=True)
    data = get_subgraph(api, node_id="b", depth=1)
    assert {node["id"] for node in data["nodes"]} == {"a", "b", "c"}
    assert [link["directed"] for link in data["links"]] == [True, False]


def test_search_uses_all_nodes_and_preserves_raw_types_and_sources(api):
    source = "file:///真实资料.pdf<SEP>chunk-id<SEP>unknown_source"
    nodes = [{"id": f"node-{i}", "type": "organization"} for i in range(28)]
    nodes.extend([
        {"id": "hidden-needle-a", "label": "远处的政策 Needle", "type": '"UNLISTED_TYPE"', "source_id": source},
        {"id": "hidden-needle-b", "label": "其他 Needle", "type": '"UNLISTED_TYPE"'},
    ])
    links = [{"source": f"node-{i}", "target": f"node-{i + 1}"} for i in range(27)]
    write_graph(api.graph_file, nodes, links)
    overview = get_subgraph(api)
    assert not any(node["id"].startswith("hidden") for node in overview["nodes"])

    response = api.client.get("/api/knowledge-graph/search", params={"q": " NEEDLE ", "limit": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2 and len(data["nodes"]) == 1
    assert data["nodes"][0]["source_id"] == source
    assert data["nodes"][0]["type"] == '"UNLISTED_TYPE"'
    assert data["revision"] == overview["revision"]
    assert api.client.get("/api/knowledge-graph/search", params={"q": "unlisted_type"}).json()["total"] == 2
    assert api.client.get("/api/knowledge-graph/search", params={"q": "hidden-needle-b"}).json()["total"] == 1
    assert api.client.get("/api/knowledge-graph/search", params={"q": "no-such-node"}).json()["nodes"] == []


def test_cache_is_shared_bounded_invalidated_by_mtime_and_does_not_hide_file_deletion(api, monkeypatch):
    write_graph(api.graph_file, [{"id": "a", "label": "A"}], [])
    calls = []
    parse = api.module._parse_exploration_graphml

    def counted(path):
        calls.append(path)
        return parse(path)

    monkeypatch.setattr(api.module, "_parse_exploration_graphml", counted)
    before = get_subgraph(api)
    assert api.client.get("/api/knowledge-graph/search", params={"q": "a"}).status_code == 200
    assert len(calls) == 1
    stat = api.graph_file.stat()
    write_graph(api.graph_file, [{"id": "a", "label": "B"}], [])
    assert api.graph_file.stat().st_size == stat.st_size
    os.utime(api.graph_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    after = get_subgraph(api)
    assert after["nodes"][0]["label"] == "B" and after["revision"] != before["revision"]
    assert len(calls) == 2 and api.module._cached_graph.cache_info().currsize == 1
    api.graph_file.unlink()
    assert api.client.get("/api/knowledge-graph/subgraph").status_code == 404


def test_cache_invalidates_on_size_when_mtime_is_unchanged(api):
    write_graph(api.graph_file, [{"id": "a"}], [])
    before = get_subgraph(api)
    stat = api.graph_file.stat()
    write_graph(api.graph_file, [{"id": "a"}, {"id": "b"}], [])
    os.utime(api.graph_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = get_subgraph(api)
    assert after["total_nodes"] == 2 and after["revision"] != before["revision"]


def test_cache_key_includes_resolved_file_path(api, monkeypatch, tmp_path):
    write_graph(api.graph_file, [{"id": "a", "label": "A"}], [])
    assert get_subgraph(api)["nodes"][0]["label"] == "A"
    stat = api.graph_file.stat()
    other_root = tmp_path / "other-workspace"
    other_file = other_root / "resources/data/lightrag/graph_chunk_entity_relation.graphml"
    write_graph(other_file, [{"id": "a", "label": "B"}], [])
    assert other_file.stat().st_size == stat.st_size
    os.utime(other_file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    monkeypatch.chdir(other_root)
    assert get_subgraph(api)["nodes"][0]["label"] == "B"
    assert api.module._cached_graph.cache_info().currsize == 1


def test_file_change_during_loading_does_not_return_a_mislabeled_revision(api, monkeypatch):
    write_graph(api.graph_file, [{"id": "a"}], [])
    parse = api.module._parse_exploration_graphml

    def changing_file(path):
        result = parse(path)
        write_graph(path, [{"id": "a"}, {"id": "b"}], [])
        return result

    monkeypatch.setattr(api.module, "_parse_exploration_graphml", changing_file)
    response = api.client.get("/api/knowledge-graph/subgraph")
    assert response.status_code == 409
    monkeypatch.setattr(api.module, "_parse_exploration_graphml", parse)
    assert get_subgraph(api)["total_nodes"] == 2


@pytest.mark.parametrize("route,params", [
    ("subgraph", {"depth": 0}), ("subgraph", {"depth": 4}),
    ("subgraph", {"limit": 0}), ("subgraph", {"limit": 601}),
    ("subgraph", {"node_id": ""}), ("search", {}),
    ("search", {"q": ""}), ("search", {"q": "   "}),
    ("search", {"q": "a" * 201}), ("search", {"q": "a", "limit": 0}),
    ("search", {"q": "a", "limit": 51}),
])
def test_query_boundaries_are_validated_before_file_loading(api, route, params):
    response = api.client.get(f"/api/knowledge-graph/{route}", params=params)
    assert response.status_code == 422


def test_empty_missing_malformed_and_unknown_center_have_distinct_results(api):
    assert api.client.get("/api/knowledge-graph/subgraph").status_code == 404
    assert api.client.get("/api/knowledge-graph/search", params={"q": "a"}).status_code == 404
    write_graph(api.graph_file, [], [])
    data = get_subgraph(api)
    assert data["nodes"] == [] and data["links"] == [] and data["truncated"] is False
    assert api.client.get("/api/knowledge-graph/subgraph", params={"node_id": "unknown"}).status_code == 404
    api.graph_file.write_text("<invalid", encoding="utf-8")
    response = api.client.get("/api/knowledge-graph/subgraph")
    assert response.status_code == 500
    assert response.json()["detail"] == "加载知识图谱失败，请检查 GraphML 文件"


@pytest.mark.parametrize("links", [
    [{"source": "a", "target": "b", "weight": "invalid"}],
    [{"source": "a", "target": "b", "weight": "nan"}],
    [{"source": "a", "target": "missing"}],
    [{"source": "a", "target": "b", "directed": "invalid"}],
])
def test_invalid_graph_data_fails_visibly(api, links):
    write_graph(api.graph_file, [{"id": "a"}, {"id": "b"}], links)
    assert api.client.get("/api/knowledge-graph/subgraph").status_code == 500


def test_legacy_graph_wire_shape_and_parser_tuple_are_preserved(api):
    write_graph(api.graph_file, [{"id": "a"}, {"id": "b"}], [{"source": "a", "target": "b", "weight": 0}])
    parsed = api.module.parse_graphml(api.graph_file)
    assert isinstance(parsed, tuple) and len(parsed) == 2
    assert isinstance(parsed[0][0], api.module.GraphNode) and isinstance(parsed[1][0], api.module.GraphLink)
    response = api.client.get("/api/knowledge-graph/graph")
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"nodes", "links"}
    assert set(data["nodes"][0]) == {"id", "label", "type", "description", "source_id"}
    assert set(data["links"][0]) == {"source", "target", "weight", "keywords", "description"}
    assert data["links"][0]["weight"] == 0
