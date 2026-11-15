"""
基于 LlamaIndex 的分级索引和切块方案
支持 Markdown 文档的多级索引（文档级 -> 章节级 -> 块级）
"""

import os
import re
import json
import hashlib
from pathlib import Path
from typing import Any, List, Dict, Optional
from dataclasses import dataclass, field
from openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding

from llama_index.core import (
    Document,
    VectorStoreIndex,
    SummaryIndex,
    StorageContext,
    Settings,
    load_index_from_storage
)
from llama_index.core.node_parser import (
    SentenceSplitter
)
from llama_index.core.schema import (
    TextNode,
    NodeWithScore,
    NodeRelationship,
    RelatedNodeInfo
)
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.response_synthesizers.type import ResponseMode

from app.config.app_config import settings

from .image_retrieval import ImageIndexer
from .rerank import Reranker


@dataclass
class ChunkConfig:
    """切块配置"""
    # 切块策略: 'simple', 'sentence', 'keyword_aware'
    chunking_strategy: str = 'sentence'
    # 中文推荐参数
    chunk_size: int = 600  # tokens (对于sentence/keyword策略) 或 字符数 (对于simple策略)
    chunk_overlap: int = 80
    # 章节摘要长度
    section_summary_size: int = 250
    # 是否包含表格和代码块
    include_tables: bool = True
    include_code_blocks: bool = True
    # 关键词感知配置（仅当 chunking_strategy='keyword_aware' 时使用）
    keywords: set[str] = field(default_factory=set)
    min_chunk_size: int = 200
    max_chunk_size: int = 800
    keyword_context_window: int = 80


class HierarchicalMarkdownProcessor:
    """分级 Markdown 处理器"""

    def __init__(self, config: Optional[ChunkConfig] = None, enable_images: bool = True):
        self.config = ChunkConfig() if config is None else config
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.*)$', re.MULTILINE)
        self.enable_images = enable_images

        if self.enable_images:
            self.image_indexer: Optional[ImageIndexer] = ImageIndexer()
        else:
            self.image_indexer = None

    def extract_hierarchy(self, text: str, doc_id: str) -> Dict:
        """提取文档的层级结构"""
        lines = text.split('\n')
        hierarchy: Dict[str, Any] = {
            'doc_id': doc_id,
            'title': '',
            'sections': [],
            'full_text': text
        }

        current_section: Optional[Dict[str, Any]] = None
        current_subsection: Optional[Dict[str, Any]] = None
        current_content: List[str] = []

        for line in lines:
            match = self.heading_pattern.match(line)
            if match:
                # 保存之前的内容
                if current_content:
                    content_text = '\n'.join(current_content)
                    if current_subsection:
                        current_subsection['content'] = content_text
                    elif current_section:
                        current_section['content'] = content_text
                    else:
                        hierarchy['sections'].append({'level': 1, 'title': '文档内容', 'content': content_text, 'path': '文档内容', 'subsections': []})
                    current_content = []

                level = len(match.group(1))
                title = match.group(2).strip()

                if level == 1:
                    # 文档标题或一级章节
                    if not hierarchy['title']:
                        hierarchy['title'] = title
                    else:
                        if current_section:
                            if current_subsection:
                                current_section['subsections'].append(current_subsection)
                            hierarchy['sections'].append(current_section)
                        current_section = {
                            'level': 1,
                            'title': title,
                            'subsections': [],
                            'content': '',
                            'path': title
                        }
                        current_subsection = None

                elif level == 2:
                    # 二级章节
                    if current_section:
                        if current_subsection:
                            current_section['subsections'].append(current_subsection)
                        current_subsection = {
                            'level': 2,
                            'title': title,
                            'content': '',
                            'path': f"{current_section['title']} > {title}"
                        }
                    else:
                        # 如果没有一级章节，创建默认的
                        current_section = {
                            'level': 1,
                            'title': '文档内容',
                            'subsections': [],
                            'content': '',
                            'path': '文档内容'
                        }
                        current_subsection = {
                            'level': 2,
                            'title': title,
                            'content': '',
                            'path': f"文档内容 > {title}"
                        }

                elif level >= 3:
                    # 三级及更深的内容作为普通文本
                    current_content.append(line)
            else:
                current_content.append(line)

        # 保存最后的内容
        if current_content:
            content_text = '\n'.join(current_content)
            if current_subsection:
                current_subsection['content'] = content_text
            elif current_section:
                current_section['content'] = content_text
            else:
                hierarchy['sections'].append({'level': 1, 'title': '文档内容', 'content': content_text, 'path': '文档内容', 'subsections': []})

        if current_subsection and current_section:
            current_section['subsections'].append(current_subsection)
        if current_section:
            hierarchy['sections'].append(current_section)

        return hierarchy

    def generate_section_summary(self, section_text: str, use_llm: bool = False) -> str:
        """生成章节摘要

        Args:
            section_text: 章节文本
            use_llm: 是否使用 LLM 生成摘要
        """
        # 去除多余空白
        text = re.sub(r'\s+', ' ', section_text).strip()

        if use_llm:
            # 使用 LLM 生成摘要（直接导入 OpenAI，出现导入错误会向上抛出）
            client = OpenAI(
                api_key=settings.model.llm_api_key,
                base_url=settings.model.llm_base_url
            )

            prompt = f"""请为以下政策文档章节生成一个简洁的摘要（不超过200字）：

{text[:2000]}

摘要："""

            try:
                response = client.chat.completions.create(
                    model=settings.model.llm_model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=300
                )

                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Summary model returned no text")
                summary = content.strip()
                if not summary:
                    raise ValueError("Summary model returned empty text")
                return summary[:self.config.section_summary_size]
            finally:
                client.close()

        # 默认：截取前 N 个字符作为摘要
        if len(text) > self.config.section_summary_size:
            text = text[:self.config.section_summary_size] + '...'
        return text

    def create_nodes_from_hierarchy(self, hierarchy: Dict, use_llm: bool = False,
                                   md_path: Optional[str] = None, md_content: Optional[str] = None) -> List[TextNode]:
        """从层级结构创建 LlamaIndex 节点

        Args:
            hierarchy: 文档层级结构
            use_llm: 是否使用 LLM 生成摘要
            md_path: Markdown 文件路径（用于提取图片）
            md_content: Markdown 内容（用于提取图片）
        """
        nodes = []

        # 文档级节点
        doc_node = TextNode(
            text=hierarchy['title'] or '政策文档',
            id_=f"doc_{hierarchy['doc_id']}",
            metadata={
                'type': 'document',
                'level': 0,
                'doc_id': hierarchy['doc_id'],
                'title': hierarchy['title']
            }
        )
        nodes.append(doc_node)
        doc_children = []

        # 处理图片（如果启用）
        if self.image_indexer is not None and md_path and md_content:
            images, img_nodes = self.image_indexer.process_markdown_with_images(md_path, md_content)
            # 将图片节点转换为 TextNode
            for img_node in img_nodes:
                image_text_node = TextNode(
                    text=img_node['content'],
                    id_=img_node['id'],
                    metadata=img_node['metadata']
                )
                # 建立父子关系
                image_text_node.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(
                    node_id=doc_node.id_,
                    metadata={'title': hierarchy['title']}
                )
                nodes.append(image_text_node)

        # 处理章节
        for section_idx, section in enumerate(hierarchy['sections']):
            # 章节级节点
            section_id = f"sec_{hierarchy['doc_id']}_{section_idx}"
            section_text = section['content']

            # 如果有子章节，合并内容
            if section['subsections']:
                for subsec in section['subsections']:
                    section_text += '\n' + subsec['content']

            # 生成摘要（可选 LLM）
            section_summary = self.generate_section_summary(section_text, use_llm=use_llm)

            section_node = TextNode(
                text=section_summary,
                id_=section_id,
                metadata={
                    'type': 'section',
                    'level': 1,
                    'doc_id': hierarchy['doc_id'],
                    'title': section['title'],
                    'path': section['path'],
                    'full_text': section_text[:1000]  # 保留部分全文用于检索
                }
            )

            # 建立父子关系
            section_node.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(
                node_id=doc_node.id_,
                metadata={'title': hierarchy['title']}
            )
            doc_children.append(RelatedNodeInfo(
                node_id=section_node.id_,
                metadata={'title': section['title']}
            ))

            nodes.append(section_node)

            # 创建细粒度块
            chunks = self._split_into_chunks(section_text, section_id, section['path'])
            for chunk_idx, chunk_text in enumerate(chunks):
                chunk_node = TextNode(
                    text=chunk_text,
                    id_=f"chunk_{section_id}_{chunk_idx}",
                    metadata={
                        'type': 'chunk',
                        'level': 2,
                        'doc_id': hierarchy['doc_id'],
                        'section_id': section_id,
                        'path': section['path'],
                        'chunk_idx': chunk_idx,
                        'title': section['title']
                    }
                )

                # 建立父子关系
                chunk_node.relationships[NodeRelationship.PARENT] = RelatedNodeInfo(
                    node_id=section_node.id_,
                    metadata={'title': section['title']}
                )

                nodes.append(chunk_node)

        doc_node.relationships[NodeRelationship.CHILD] = doc_children
        return nodes

    def _split_into_chunks(self, text: str, section_id: str, path: str) -> List[str]:
        """
        将文本切分为块

        支持三种策略:
        1. 'simple': 简单的字符级滑动窗口（保留旧逻辑）
        2. 'sentence': 使用 LlamaIndex SentenceSplitter（推荐）
        3. 'keyword_aware': 关键词感知切分（需要配置keywords）
        """
        if not text:
            return []

        strategy = self.config.chunking_strategy

        # 策略1: 简单字符级滑动窗口
        if strategy == 'simple':
            return self._split_simple(text)

        # 策略2: 句子级滑动窗口（推荐）
        elif strategy == 'sentence':
            return self._split_sentence(text)

        # 策略3: 关键词感知切分
        elif strategy == 'keyword_aware':
            if not self.config.keywords:
                print("  ⚠ 警告: 未配置关键词，回退到 sentence 策略")
                return self._split_sentence(text)
            return self._split_keyword_aware(text)

        else:
            raise ValueError(f"未知的切块策略: {strategy}")

    def _split_simple(self, text: str) -> List[str]:
        """简单的字符级滑动窗口切分（原有逻辑）"""
        chunks = []
        text_len = len(text)
        start = 0

        while start < text_len:
            # 计算块的结束位置
            end = min(start + self.config.chunk_size, text_len)

            # 尝试在句子边界切分
            if end < text_len:
                # 查找最近的句号、问号或感叹号
                for sep in ['。', '！', '？', '\n\n', '\n']:
                    sep_pos = text.rfind(sep, start, end)
                    if sep_pos > start + self.config.chunk_size // 2:
                        end = sep_pos + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # 滑动窗口 - 确保窗口向前移动
            new_start = end - self.config.chunk_overlap
            if new_start <= start:
                # 如果新起点没有向前移动，直接从end开始
                start = end
            else:
                start = new_start

        return chunks

    def _split_sentence(self, text: str) -> List[str]:
        """
        使用 LlamaIndex SentenceSplitter 进行句子级切分

        优势:
        - 尊重句子边界
        - 基于 token 数量切分（更准确）
        - 自动处理重叠
        """
        # 创建切分器
        splitter = SentenceSplitter(
            chunk_size=self.config.chunk_size,      # tokens
            chunk_overlap=self.config.chunk_overlap  # tokens
        )

        # 创建临时文档
        doc = Document(text=text)

        # 执行切分
        nodes = splitter.get_nodes_from_documents([doc])

        # 提取文本
        chunks = [node.get_content() for node in nodes]

        return chunks

    def _split_keyword_aware(self, text: str) -> List[str]:
        """
        关键词感知切分

        工作流程:
        1. 第一阶段: 使用 SentenceSplitter 初步切分
        2. 第二阶段: 在关键词边界进行智能切分
        """
        # 第一阶段: 初步切分
        splitter = SentenceSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap
        )

        doc = Document(text=text)
        initial_nodes = splitter.get_nodes_from_documents([doc])

        # 第二阶段: 关键词感知处理
        final_chunks = []

        for node in initial_nodes:
            content = node.get_content()

            # 检查是否包含关键词
            has_keywords = any(kw in content for kw in self.config.keywords)

            # 检查大小
            content_len = len(content)

            if not has_keywords or content_len <= self.config.max_chunk_size:
                # 直接使用
                final_chunks.append(content)
            else:
                # 需要基于关键词二次切分
                sub_chunks = self._split_by_keywords(content)
                final_chunks.extend(sub_chunks)

        return final_chunks

    def _split_by_keywords(self, text: str) -> List[str]:
        """
        根据关键词边界切分文本

        策略:
        1. 找到所有关键词位置
        2. 在关键词之间寻找合适的切分点
        3. 保证每个chunk包含完整的关键词上下文
        """
        keyword_positions = []
        for keyword in self.config.keywords:
            for match in re.finditer(re.escape(keyword), text):
                keyword_positions.append((keyword, match.start(), match.end()))

        # 按位置排序
        keyword_positions.sort(key=lambda x: x[1])

        if not keyword_positions:
            return [text]

        chunks = []
        current_start = 0
        text_len = len(text)

        i = 0
        while i < len(keyword_positions):
            keyword, kw_start, kw_end = keyword_positions[i]

            # 计算包含当前关键词的chunk范围
            chunk_start = max(current_start, kw_start - self.config.keyword_context_window)

            # 尝试向前延伸到句子边界
            if chunk_start > current_start:
                for sep in ['。', '\n', '！', '？', '. ', '! ', '? ']:
                    sep_pos = text.rfind(sep, current_start, chunk_start)
                    if sep_pos != -1:
                        chunk_start = sep_pos + len(sep)
                        break

            # 尝试包含后续的关键词（如果它们很近）
            chunk_end = kw_end + self.config.keyword_context_window
            j = i + 1
            while j < len(keyword_positions):
                next_kw, next_start, next_end = keyword_positions[j]
                if next_start - chunk_end < self.config.keyword_context_window:
                    chunk_end = next_end + self.config.keyword_context_window
                    j += 1
                else:
                    break

            # 确保chunk不会太大
            if chunk_end - chunk_start > self.config.max_chunk_size:
                chunk_end = chunk_start + self.config.max_chunk_size

            # 尝试在句子边界结束
            if chunk_end < text_len:
                for sep in ['。', '\n', '！', '？', '. ', '! ', '? ']:
                    sep_pos = text.find(sep, chunk_end, min(chunk_end + 50, text_len))
                    if sep_pos != -1:
                        chunk_end = sep_pos + len(sep)
                        break

            chunk_end = min(chunk_end, text_len)

            # 提取chunk
            chunk_text = text[chunk_start:chunk_end].strip()
            if len(chunk_text) >= self.config.min_chunk_size:
                chunks.append(chunk_text)

            # 更新位置
            current_start = chunk_end
            i = j

        # 处理剩余文本
        if current_start < text_len:
            remaining = text[current_start:].strip()
            if len(remaining) >= self.config.min_chunk_size:
                chunks.append(remaining)
            elif chunks:
                # 如果剩余文本太短，合并到最后一个chunk
                chunks[-1] += " " + remaining

        return chunks


class HierarchicalIndexBuilder:
    """分级索引构建器"""

    def __init__(self,
                 storage_dir: str = "./storage/hierarchical",
                 embed_model_name: Optional[str] = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 配置嵌入模型
        if embed_model_name is not None:
            Settings.embed_model = OpenAIEmbedding(
                model=embed_model_name,
                api_key=settings.embedding.openai_api_key,
                api_base=settings.embedding.openai_base_url
            )

        self.processor = HierarchicalMarkdownProcessor()
        self.doc_store = SimpleDocumentStore()

    def build_from_markdown_files(self, file_paths: List[str], use_llm: bool = False, enable_images: bool = True, *, document_ids: Optional[Dict[str, str]] = None) -> Dict:
        """从 Markdown 文件构建分级索引

        Args:
            file_paths: Markdown 文件路径列表
            use_llm: 是否使用 LLM 生成章节摘要
            enable_images: 是否提取和索引图片
        """
        all_nodes = []
        doc_nodes = []
        section_nodes = []
        chunk_nodes = []
        image_nodes = []

        # 处理每个文档
        for file_path in file_paths:
            print(f"处理文档: {file_path}")

            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            # 生成文档 ID
            doc_id = (document_ids[file_path] if document_ids is not None else
                      hashlib.md5(file_path.encode(), usedforsecurity=False).hexdigest()[:16])

            # 提取层级结构
            hierarchy = self.processor.extract_hierarchy(text, doc_id)

            # 创建节点（传递文件路径和内容以支持图片提取）
            nodes = self.processor.create_nodes_from_hierarchy(
                hierarchy,
                use_llm=use_llm,
                md_path=file_path if enable_images else None,
                md_content=text if enable_images else None
            )
            all_nodes.extend(nodes)

            # 按类型分类
            for node in nodes:
                node_type = node.metadata.get('type', '')
                if node_type == 'document':
                    doc_nodes.append(node)
                elif node_type == 'section':
                    section_nodes.append(node)
                elif node_type == 'chunk':
                    chunk_nodes.append(node)
                elif node.metadata.get('content_type') == 'image':
                    image_nodes.append(node)

        # 构建分级索引
        print(f"构建索引: {len(doc_nodes)} 文档, {len(section_nodes)} 章节, {len(chunk_nodes)} 块, {len(image_nodes)} 图片")
        if use_llm:
            print("使用 LLM 生成章节摘要")
        if enable_images and image_nodes:
            print(f"包含 {len(image_nodes)} 个图片节点")

        # 1. 文档级索引（用于快速定位文档）
        doc_index = VectorStoreIndex(
            nodes=doc_nodes,
            show_progress=True
        )

        # 2. 章节级索引（用于定位相关章节）
        section_index = VectorStoreIndex(
            nodes=section_nodes,
            show_progress=True
        )

        # 3. 块级索引（用于精确检索）
        chunk_index = VectorStoreIndex(
            nodes=chunk_nodes,
            show_progress=True
        )

        # 4. 摘要索引（用于全局理解）
        summary_index = SummaryIndex(
            nodes=section_nodes,
            show_progress=True
        )

        # 保存索引
        self._save_indices({
            'doc_index': doc_index,
            'section_index': section_index,
            'chunk_index': chunk_index,
            'summary_index': summary_index
        })

        # 保存节点到文档存储
        for node in all_nodes:
            self.doc_store.add_documents([node])

        # 保存文档存储
        self.doc_store.persist(str(self.storage_dir / 'docstore.json'))

        # 保存图片索引（如果有）
        if enable_images and image_nodes and self.processor.image_indexer:
            image_index_path = self.storage_dir / 'image_index.json'
            self.processor.image_indexer.save_index(str(image_index_path))
            print(f"图片索引已保存到 {image_index_path}")

        return {
            'total_docs': len(doc_nodes),
            'total_sections': len(section_nodes),
            'total_chunks': len(chunk_nodes),
            'total_images': len(image_nodes),
            'storage_dir': str(self.storage_dir)
        }

    def _save_indices(self, indices: Dict):
        """保存索引到磁盘"""
        for name, index in indices.items():
            index_dir = self.storage_dir / name
            index_dir.mkdir(exist_ok=True)
            index.storage_context.persist(str(index_dir))
            print(f"索引 {name} 已保存到 {index_dir}")


class HierarchicalRetriever:
    """分级检索器 - 实现三段式检索"""

    def __init__(self,
                 storage_dir: str = "./storage/hierarchical",
                 use_rerank: str = "dashscope",  # "dashscope", "simple", "none"
                 enable_images: bool = True):
        self.storage_dir = Path(storage_dir)
        self.use_rerank = use_rerank
        self.enable_images = enable_images

        # 加载索引
        self.indices = self._load_indices()

        # 加载文档存储
        self.doc_store = SimpleDocumentStore.from_persist_path(
            str(self.storage_dir / 'docstore.json')
        )

        # 初始化重排器
        self.reranker: Optional[Reranker] = None
        # 初始化图片索引器
        if self.enable_images:
            self.image_indexer = ImageIndexer()
            # 尝试加载已保存的图片索引
            image_index_path = self.storage_dir / 'image_index.json'
            if image_index_path.exists():
                self.image_indexer.load_index(str(image_index_path))

        if use_rerank == "dashscope":
            self.reranker = Reranker()
            print("使用 DashScope 重排器")

    def _rank_by_retrieval_score(self, nodes: List, top_k: int) -> List:
        """简单的基于分数的重排"""
        def weighted_score(node) -> float:
            score = node.metadata["retrieval_score"]
            weight = 1.2 if node.metadata.get("type") == "section" else .8 if node.metadata.get("type") == "document" else 1.0
            return float(score) * weight

        return sorted(nodes, key=weighted_score, reverse=True)[:top_k]

    def _dashscope_rerank(self, nodes: List, query: str, top_k: int) -> List:
        """使用 DashScope 重排"""
        if self.reranker is None:
            raise RuntimeError("Configured reranker is not initialized")
        texts = [node.text for node in nodes]
        ranking = self.reranker.rerank(query=query, documents=texts, top_n=top_k)
        reranked_nodes = []
        for index, score, _ in ranking:
            node = nodes[index]
            node.metadata["retrieval_score"] = float(score)
            reranked_nodes.append(node)
        return reranked_nodes[:top_k]

    def _load_indices(self) -> Dict:
        """加载保存的索引"""
        indices = {}

        # 尝试加载各级索引
        for index_name in ['doc_index', 'section_index', 'chunk_index', 'summary_index']:
            index_dir = self.storage_dir / index_name
            if index_dir.exists():
                storage_context = StorageContext.from_defaults(
                    persist_dir=str(index_dir)
                )
                index = load_index_from_storage(storage_context)
                indices[index_name] = index
                print(f"已加载索引: {index_name}")

        return indices

    def retrieve(self,
                 query: str,
                 top_k: int = 10,
                 use_rerank: bool = True,
                 retrieval_mode: str = "hybrid") -> List[TextNode]:
        """
        分级检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            use_rerank: 是否使用重排
            retrieval_mode: 检索模式
                - "hybrid": 混合检索（推荐）
                - "hierarchical": 层级检索
                - "direct": 直接检索
        """

        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if retrieval_mode == "hybrid":
            nodes = self._hybrid_retrieve(query, top_k * 2)  # 多召回一些用于重排
        elif retrieval_mode == "hierarchical":
            nodes = self._hierarchical_retrieve(query, top_k * 2)
        else:
            nodes = self._direct_retrieve(query, top_k * 2)

        # 重排
        if use_rerank and self.use_rerank != "none" and len(nodes) > 0:
            if self.use_rerank == "dashscope" and self.reranker is not None:
                nodes = self._dashscope_rerank(nodes, query, top_k)
            else:
                nodes = self._rank_by_retrieval_score(nodes, top_k)
        else:
            nodes = nodes[:top_k]

        return nodes

    def _hybrid_retrieve(self, query: str, top_k: int) -> List[TextNode]:
        """混合检索：同时从多个层级检索，然后融合结果"""

        all_nodes = []

        # 1. 从章节索引检索（获取相关章节）
        if 'section_index' in self.indices:
            section_retriever = self.indices['section_index'].as_retriever(
                similarity_top_k=top_k * 2
            )
            section_nodes = section_retriever.retrieve(query)
            all_nodes.extend([self._scored_node(n) for n in section_nodes])

        # 2. 从块索引直接检索（获取精确匹配）
        if 'chunk_index' in self.indices:
            chunk_retriever = self.indices['chunk_index'].as_retriever(
                similarity_top_k=top_k * 3
            )
            chunk_nodes = chunk_retriever.retrieve(query)
            all_nodes.extend([self._scored_node(n) for n in chunk_nodes])

        # 3. 从摘要索引检索（获取全局相关）
        if 'summary_index' in self.indices:
            summary_retriever = self.indices['summary_index'].as_retriever(
                similarity_top_k=top_k
            )
            summary_nodes = summary_retriever.retrieve(query)
            all_nodes.extend([self._scored_node(n) for n in summary_nodes])

        # 去重（基于节点 ID）
        unique_nodes = {}
        for node in all_nodes:
            if node.id_ not in unique_nodes:
                unique_nodes[node.id_] = node

        result_nodes = list(unique_nodes.values())
        return result_nodes

    def _hierarchical_retrieve(self, query: str, top_k: int) -> List[TextNode]:
        """层级检索：先检索章节，再检索该章节下的块"""

        result_nodes = []

        # 1. 先从章节索引检索
        if 'section_index' not in self.indices:
            return []

        section_retriever = self.indices['section_index'].as_retriever(
            similarity_top_k=5  # 获取最相关的5个章节
        )
        section_results = section_retriever.retrieve(query)

        if not section_results:
            return []

        # 2. 获取相关章节的 ID
        section_ids = [n.node.id_ for n in section_results]

        # 3. 在块索引中检索这些章节下的块
        if 'chunk_index' in self.indices:
            chunk_retriever = self.indices['chunk_index'].as_retriever(
                similarity_top_k=top_k * 2
            )
            chunk_results = chunk_retriever.retrieve(query)

            # 过滤：只保留属于相关章节的块
            for chunk_result in chunk_results:
                chunk_node = self._scored_node(chunk_result)
                if chunk_node.metadata.get('section_id') in section_ids:
                    result_nodes.append(chunk_node)

        # 4. 添加章节节点本身（提供上下文）
        for section_result in section_results[:2]:  # 只添加前2个最相关的章节
            result_nodes.append(self._scored_node(section_result))

        return result_nodes

    def _direct_retrieve(self, query: str, top_k: int) -> List[TextNode]:
        """直接检索：只从块索引检索"""

        if 'chunk_index' not in self.indices:
            return []

        retriever = self.indices['chunk_index'].as_retriever(
            similarity_top_k=top_k
        )
        results = retriever.retrieve(query)

        nodes = [self._scored_node(r) for r in results]
        return nodes

    @staticmethod
    def _scored_node(result) -> TextNode:
        node = result.node.model_copy(deep=True)
        if result.score is None:
            raise ValueError("Retrieval result is missing its relevance score")
        node.metadata["retrieval_score"] = float(result.score)
        return node

    def close(self) -> None:
        reranker, self.reranker = self.reranker, None
        if reranker is not None:
            reranker.close()

    def retrieve_with_images(self,
                            query: str,
                            top_k: int = 10,
                            image_only: bool = False) -> Dict:
        """检索并返回图片结果

        Args:
            query: 查询文本
            top_k: 返回结果数量
            image_only: 是否只返回图片

        Returns:
            包含文本节点和图片节点的字典
        """
        # 执行常规检索
        nodes = self.retrieve(query, top_k=top_k * 2 if not image_only else top_k)

        # 分离图片和文本节点
        image_nodes = []
        text_nodes = []

        for node in nodes:
            if node.metadata.get('content_type') == 'image':
                image_nodes.append(node)
            elif not image_only:
                text_nodes.append(node)

        # 如果有图片索引器，格式化图片结果
        image_results = []
        if self.enable_images and self.image_indexer:
            image_infos = self.image_indexer.get_images_for_nodes(image_nodes)
            for img_info in image_infos:
                image_results.append({
                    'image_id': img_info.image_id,
                    'path': img_info.relative_path,
                    'caption': img_info.caption,
                    'is_qrcode': img_info.is_qrcode,
                    'qr_content': img_info.qr_content,
                    'alt_text': img_info.alt_text,
                    'width': img_info.width,
                    'height': img_info.height
                })

        return {
            'text_nodes': text_nodes[:top_k] if not image_only else [],
            'image_results': image_results[:top_k],
            'total_images': len(image_results)
        }

    def get_query_engine(self, retrieval_mode: str = "hybrid", response_mode: str = "compact"):
        """获取查询引擎"""

        # 创建自定义检索器
        class CustomRetriever(BaseRetriever):
            def __init__(self, parent_retriever, mode):
                super().__init__()
                self.parent_retriever = parent_retriever
                self.mode = mode

            def _retrieve(self, query_bundle):
                nodes = self.parent_retriever.retrieve(
                    query_bundle.query_str,
                    top_k=10,
                    use_rerank=True,
                    retrieval_mode=self.mode
                )
                return [NodeWithScore(node=n, score=n.metadata["retrieval_score"]) for n in nodes]

        retriever = CustomRetriever(self, retrieval_mode)

        # 创建响应合成器
        response_synthesizer = get_response_synthesizer(
            response_mode=ResponseMode(response_mode)
        )

        # 创建查询引擎
        query_engine = RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synthesizer
        )

        return query_engine


# 使用示例函数
def build_index_from_directory(data_dir: str, storage_dir: str = "./storage/hierarchical"):
    """从目录构建索引"""

    # 查找所有 Markdown 文件
    md_files = []
    for root, _dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.md'):
                md_files.append(os.path.join(root, file))

    print(f"找到 {len(md_files)} 个 Markdown 文件")

    # 构建索引
    builder = HierarchicalIndexBuilder(storage_dir=storage_dir)
    stats = builder.build_from_markdown_files(md_files)

    print("索引构建完成:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    return stats


def test_retrieval(storage_dir: str = "./storage/hierarchical"):
    """测试检索功能"""

    retriever = HierarchicalRetriever(storage_dir=storage_dir)

    try:
        # 测试查询
        test_queries = [
            "家电以旧换新补贴标准是什么？",
            "手机购新补贴的申请条件",
            "补贴金额如何计算？"
        ]

        for query in test_queries:
            print(f"\n查询: {query}")
            print("-" * 50)

            # 混合检索
            nodes = retriever.retrieve(
                query,
                top_k=5,
                use_rerank=True,
                retrieval_mode="hybrid"
            )

            for i, node in enumerate(nodes, 1):
                print(f"\n结果 {i}:")
                print(f"  类型: {node.metadata.get('type', 'unknown')}")
                print(f"  路径: {node.metadata.get('path', 'N/A')}")
                print(f"  内容: {node.text[:200]}...")

        # 测试查询引擎
        engine = retriever.get_query_engine()
        response = engine.query("家电以旧换新的具体流程是什么？")
        print(f"\n查询引擎响应:\n{response}")
    finally:
        retriever.close()


if __name__ == "__main__":
    # 构建索引
    project_root = Path(__file__).resolve().parents[2]
    data_dir = str(project_root / "resources/data/process")
    storage_dir = str(project_root / "storage/hierarchical")

    print("开始构建分级索引...")
    build_index_from_directory(data_dir, storage_dir)

    print("\n测试检索...")
    test_retrieval(storage_dir)
