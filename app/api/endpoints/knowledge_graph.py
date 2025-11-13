"""
知识图谱相关端点
提供 LightRAG GraphML 数据的访问接口
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.get("/graph", response_model=GraphData)
async def get_knowledge_graph():
    """
    获取知识图谱数据

    从 LightRAG 的 GraphML 文件中解析并返回节点和边的数据
    """
    try:
        # 获取 GraphML 文件路径
        graph_file = Path("resources/data/lightrag/graph_chunk_entity_relation.graphml")

        if not graph_file.exists():
            raise HTTPException(
                status_code=404,
                detail="知识图谱文件不存在，请先导入数据"
            )

        # 解析 GraphML 文件
        nodes, links = parse_graphml(graph_file)

        logger.info(f"成功加载知识图谱: {len(nodes)} 个节点, {len(links)} 条边")

        return GraphData(nodes=nodes, links=links)

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"加载知识图谱失败: {str(e)}"
        )


def parse_graphml(file_path: Path) -> tuple[List[GraphNode], List[GraphLink]]:
    """
    解析 GraphML 文件

    Args:
        file_path: GraphML 文件路径

    Returns:
        (节点列表, 边列表)
    """
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
    links = []

    # 解析节点
    for node in root.findall('.//graphml:node', ns):
        node_id = node.get('id')
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

    # 解析边
    for edge in root.findall('.//graphml:edge', ns):
        source = edge.get('source')
        target = edge.get('target')
        edge_data = {}

        for data in edge.findall('graphml:data', ns):
            key_id = data.get('key')
            key_name = key_map.get(key_id, key_id)
            edge_data[key_name] = data.text or ""

        # 解析权重
        weight = 1.0
        try:
            weight = float(edge_data.get('weight', 1.0))
        except (ValueError, TypeError):
            pass

        links.append(GraphLink(
            source=source,
            target=target,
            weight=weight,
            keywords=edge_data.get('keywords', ''),
            description=edge_data.get('description', '')[:100]  # 限制长度
        ))

    return nodes, links


@router.get("/graph/stats")
async def get_graph_stats():
    """
    获取知识图谱统计信息
    """
    try:
        graph_file = Path("resources/data/lightrag/graph_chunk_entity_relation.graphml")

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
        type_distribution = {}
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
        logger.error(f"获取图谱统计信息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )


__all__ = ["router"]
