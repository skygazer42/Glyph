"""
知识图谱相关端点
提供 LightRAG GraphML 数据的访问接口
"""

import logging
import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
logger = logging.getLogger(__name__)


def _graph_file_path() -> Path:
    """与图检索使用相同地区工作目录，避免页面继续展示已归档的旧图谱。"""
    return Path(os.getenv("LIGHTRAG_WORKDIR", "resources/data/lightrag_changzhou_20261121")) / "graph_chunk_entity_relation.graphml"


class GraphNode(BaseModel):
    """图节点模型"""
    id: str
    label: str
    type: str = "unknown"
    description: str = ""
    source_id: str = ""


class GraphLink(BaseModel):
    """图边模型"""
    source: str
    target: str
    weight: float = 1.0
    keywords: str = ""
    description: str = ""


class GraphData(BaseModel):
    """图数据模型"""
    nodes: List[GraphNode]
    links: List[GraphLink]


class GraphStats(BaseModel):
    """描述图谱文件是否存在及节点、边和文件大小统计。"""

    exists: bool
    nodes: int
    edges: int
    file_size: int
    type_distribution: Optional[Dict[str, int]] = None


class ExplorationNode(GraphNode):
    """为图谱浏览节点补充去重邻居数量。"""

    neighbor_count: int


class ExplorationLink(GraphLink):
    """保留边的稳定版本内标识与方向，供子图展示使用。"""

    id: str
    directed: bool


class SubgraphData(BaseModel):
    """返回有限子图及全图总量、截断标记和文件修订信息。"""

    nodes: list[ExplorationNode]
    links: list[ExplorationLink]
    total_nodes: int
    total_links: int
    truncated: bool
    center_id: str | None
    revision: str


class GraphSearchData(BaseModel):
    """返回排序后的图谱搜索命中及截取前总数。"""

    nodes: list[ExplorationNode]
    total: int
    revision: str


class SubgraphQuery(BaseModel):
    """限制中心邻域查询深度和节点预算；无中心时查询概览。"""

    node_id: str | None = Field(default=None, min_length=1)
    depth: int = Field(default=1, ge=1, le=3)
    limit: int = Field(default=120, ge=1, le=600)


class GraphSearchQuery(BaseModel):
    """限制全图实体搜索词长度和返回数量。"""

    q: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=12, ge=1, le=50)

    @field_validator("q")
    @classmethod
    def strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("搜索词不能为空")
        return value


@dataclass
class GraphIndex:
    """缓存一个文件修订内的节点、边、无向邻接及确定性排名。"""

    nodes: dict[str, ExplorationNode]
    links: tuple[ExplorationLink, ...]
    neighbors: dict[str, set[str]]
    ranked_ids: tuple[str, ...]
    rank: dict[str, int]
    revision: str


@router.get("/graph", response_model=GraphData)
def get_knowledge_graph():
    """
    获取知识图谱数据

    从 LightRAG 的 GraphML 文件中解析并返回节点和边的数据
    """
    try:
        # 获取 GraphML 文件路径
        graph_file = _graph_file_path()

        if not graph_file.exists():
            raise HTTPException(
                status_code=404,
                detail="知识图谱文件不存在，请先导入数据"
            )

        # 解析 GraphML 文件
        nodes, links = parse_graphml(graph_file)

        logger.info(f"成功加载知识图谱: {len(nodes)} 个节点, {len(links)} 条边")

        return GraphData(nodes=nodes, links=links)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"加载知识图谱失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"加载知识图谱失败: {str(e)}"
        ) from e


def parse_graphml(file_path: Path) -> tuple[List[GraphNode], List[GraphLink]]:
    """
    解析 GraphML 文件

    Args:
        file_path: GraphML 文件路径

    Returns:
        (节点列表, 边列表)
    """
    nodes, links = _parse_exploration_graphml(file_path)
    return nodes, [GraphLink(**link.model_dump()) for link in links]


def _parse_exploration_graphml(file_path: Path) -> tuple[list[GraphNode], list[ExplorationLink]]:
    """解析节点和边并保留方向；无原生边 ID 时以全图序号构造版本内标识。"""
    tree = ET.parse(file_path)
    root = tree.getroot()

    # GraphML 命名空间
    ns = {'graphml': 'http://graphml.graphdrawing.org/xmlns'}

    # 解析 key 定义，建立 id 到属性名的映射
    key_map = {}
    for key in root.findall('.//graphml:key', ns):
        key_id = key.get('id')
        key_name = key.get('attr.name')
        key_map[key_id] = key_name

    nodes = []
    links: list[ExplorationLink] = []

    # 解析节点
    for node in root.findall('.//graphml:node', ns):
        node_id = node.attrib['id']
        node_data = {}

        for data in node.findall('graphml:data', ns):
            key_id = data.get('key')
            key_name = key_map.get(key_id, key_id)
            node_data[key_name] = data.text or ""

        nodes.append(GraphNode(
            id=node_id,
            label=node_data.get('entity_name', node_id),
            type=node_data.get('entity_type', 'unknown'),
            description=node_data.get('description', '')[:200],  # 限制长度
            source_id=node_data.get('source_id', '')
        ))

    # 无原生边 ID 时使用全图序号，保证同一文件版本内不同子图的 ID 一致。
    for graph in root.findall('.//graphml:graph', ns):
        default_directed = graph.get('edgedefault', 'undirected') == 'directed'
        for edge in graph.findall('graphml:edge', ns):
            edge_data = {}
            for data in edge.findall('graphml:data', ns):
                key_id = data.get('key')
                key_name = key_map.get(key_id, key_id)
                edge_data[key_name] = data.text or ""

            weight = float(edge_data.get('weight', 1.0))
            if not math.isfinite(weight):
                raise ValueError("图谱边权重必须为有限数值")
            directed = edge.get('directed')
            if directed is not None and directed not in {'true', 'false', '1', '0'}:
                raise ValueError("图谱边 directed 属性无效")
            edge_id = edge.get('id')
            links.append(ExplorationLink(
                id=f"edge:{len(links)}" if edge_id is None else f"graphml:{edge_id}",
                source=edge.attrib['source'],
                target=edge.attrib['target'],
                weight=weight,
                keywords=edge_data.get('keywords', ''),
                description=edge_data.get('description', '')[:100],
                directed=default_directed if directed is None else directed in {'true', '1'},
            ))

    return nodes, links


@lru_cache(maxsize=1)
def _cached_graph(file_path: str, mtime_ns: int, size: int) -> GraphIndex:
    """按路径、mtime 和大小缓存图索引；拒绝重复标识、悬空边并计算无向邻居及排名。"""
    nodes, links = _parse_exploration_graphml(Path(file_path))
    node_map = {node.id: node for node in nodes}
    if len(node_map) != len(nodes):
        raise ValueError("图谱节点 ID 重复")
    if len({link.id for link in links}) != len(links):
        raise ValueError("图谱边 ID 重复")
    neighbors: dict[str, set[str]] = {node.id: set() for node in nodes}
    weighted_degree = {node.id: 0.0 for node in nodes}
    for link in links:
        if link.source not in node_map or link.target not in node_map:
            raise ValueError("图谱边引用了不存在的节点")
        weighted_degree[link.source] += link.weight
        if link.source != link.target:
            neighbors[link.source].add(link.target)
            neighbors[link.target].add(link.source)
            weighted_degree[link.target] += link.weight
    exploration_nodes = {
        node.id: ExplorationNode(**node.model_dump(), neighbor_count=len(neighbors[node.id]))
        for node in nodes
    }
    ranked_ids = tuple(sorted(node_map, key=lambda node_id: (
        node_map[node_id].type.strip().strip("\"'").casefold() not in {'policy', '政策'},
        -weighted_degree[node_id],
        -len(neighbors[node_id]),
        node_id,
    )))
    return GraphIndex(
        nodes=exploration_nodes,
        links=tuple(links),
        neighbors=neighbors,
        ranked_ids=ranked_ids,
        rank={node_id: index for index, node_id in enumerate(ranked_ids)},
        revision=f"{mtime_ns}:{size}",
    )


def _load_graph_index() -> GraphIndex:
    """加载当前图索引并复核文件元数据；缺失返回 404，读取或格式错误转换为 500。"""
    graph_file = _graph_file_path().resolve()
    try:
        stat = graph_file.stat()
        # shortcut: 版本由 mtime 和大小识别，导入若保留两者时改用内容摘要。
        graph = _cached_graph(str(graph_file), stat.st_mtime_ns, stat.st_size)
        latest_stat = graph_file.stat()
        if (latest_stat.st_mtime_ns, latest_stat.st_size) != (stat.st_mtime_ns, stat.st_size):
            raise HTTPException(status_code=409, detail="图谱数据已更新，请重新查询")
        return graph
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="知识图谱文件不存在，请先导入数据") from exc
    except (OSError, ET.ParseError, ValueError, KeyError) as exc:
        logger.exception("加载知识图谱失败")
        raise HTTPException(status_code=500, detail="加载知识图谱失败，请检查 GraphML 文件") from exc


def _overview_ids(graph: GraphIndex, limit: int) -> list[str]:
    """按排名从多个连通区域选概览节点，最多取预算与 24 的较小值。"""
    remaining = set(graph.nodes)
    selected: list[str] = []
    frontier: set[str] = set()
    seeds = iter(sorted(graph.ranked_ids, key=lambda node_id: (
        not graph.neighbors[node_id], graph.rank[node_id],
    )))
    while remaining and len(selected) < min(limit, 24):
        if not frontier:
            seed = next(node_id for node_id in seeds if node_id in remaining)
            frontier.add(seed)
        node_id = min(frontier, key=graph.rank.__getitem__)
        frontier.remove(node_id)
        remaining.remove(node_id)
        selected.append(node_id)
        frontier.update(graph.neighbors[node_id] & remaining)
    return selected


def _center_ids(graph: GraphIndex, node_id: str, depth: int, limit: int) -> tuple[list[str], bool]:
    """按无向邻接逐层选择中心邻域，返回节点 ID 和是否因预算截断的标记。"""
    selected = [node_id]
    seen = {node_id}
    frontier = [node_id]
    for _ in range(depth):
        candidates = set()
        for current in frontier:
            candidates.update(graph.neighbors[current])
        candidates.difference_update(seen)
        ordered = sorted(candidates, key=graph.rank.__getitem__)
        remaining = limit - len(selected)
        if len(ordered) > remaining:
            selected.extend(ordered[:remaining])
            return selected, True
        selected.extend(ordered)
        seen.update(ordered)
        frontier = ordered
        if not frontier:
            break
    return selected, False


@router.get("/subgraph", response_model=SubgraphData)
def get_subgraph(query: Annotated[SubgraphQuery, Query()]) -> SubgraphData:
    """返回核心概览或中心节点的有限深度邻域；只包含真实节点和诱导边。"""
    graph = _load_graph_index()
    if query.node_id is None:
        selected = _overview_ids(graph, query.limit)
        truncated = len(selected) < len(graph.nodes)
    else:
        if query.node_id not in graph.nodes:
            raise HTTPException(status_code=404, detail="图谱节点不存在")
        selected, truncated = _center_ids(graph, query.node_id, query.depth, query.limit)
    selected_ids = set(selected)
    return SubgraphData(
        nodes=[graph.nodes[node_id] for node_id in selected],
        links=[link for link in graph.links if link.source in selected_ids and link.target in selected_ids],
        total_nodes=len(graph.nodes),
        total_links=len(graph.links),
        truncated=truncated,
        center_id=query.node_id,
        revision=graph.revision,
    )


@router.get("/search", response_model=GraphSearchData)
def search_graph(query: Annotated[GraphSearchQuery, Query()]) -> GraphSearchData:
    """搜索全图，不受当前已加载子图限制。"""
    graph = _load_graph_index()
    term = query.q.casefold()
    matches = [
        graph.nodes[node_id] for node_id in graph.ranked_ids
        if any(term in value.casefold() for value in (
            graph.nodes[node_id].label, graph.nodes[node_id].type, node_id,
        ))
    ]
    return GraphSearchData(nodes=matches[:query.limit], total=len(matches), revision=graph.revision)


@router.get("/graph/stats", response_model=GraphStats, response_model_exclude_none=True)
def get_graph_stats():
    """
    获取知识图谱统计信息
    """
    try:
        graph_file = _graph_file_path()

        if not graph_file.exists():
            return {
                "exists": False,
                "nodes": 0,
                "edges": 0,
                "file_size": 0
            }

        nodes, links = parse_graphml(graph_file)
        file_size = graph_file.stat().st_size

        # 统计节点类型分布
        type_distribution: Dict[str, int] = {}
        for node in nodes:
            node_type = node.type
            type_distribution[node_type] = type_distribution.get(node_type, 0) + 1

        return {
            "exists": True,
            "nodes": len(nodes),
            "edges": len(links),
            "file_size": file_size,
            "type_distribution": type_distribution
        }

    except Exception as e:
        logger.exception(f"获取图谱统计信息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        ) from e


__all__ = ["router"]
