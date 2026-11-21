# -*- coding: utf-8 -*-

import logging
from typing import Any, List, Optional, Sequence, Tuple

import requests
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, PrivateAttr

from app.config.app_config import settings


class RerankItem(BaseModel):
    """校验重排服务返回的原文档位置和有限相关性分数。"""

    model_config = ConfigDict(strict=True)

    index: int = Field(ge=0)
    relevance_score: float = Field(
        allow_inf_nan=False, validation_alias=AliasChoices("relevance_score", "score")
    )


class DashscopeRerankResponse(BaseModel):
    """适配 DashScope 重排结果所在的响应路径。"""

    results: list[RerankItem] = Field(
        validation_alias=AliasChoices(AliasPath("output", "results"), "data")
    )


class XinferenceRerankResponse(BaseModel):
    """适配 Xinference 的两种重排结果字段名称。"""

    results: list[RerankItem] = Field(validation_alias=AliasChoices("data", "results"))


class Reranker:
    """持有配置选定的重排后端及 HTTP Session；调用方负责 close。"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.settings = settings.reranker
        self.logger = logging.getLogger(__name__) if logger is None else logger
        self.backend = self.settings.backend.lower()

        if self.backend == "dashscope":
            api_key = self.settings.dashscope_api_key
            if api_key is None:
                api_key = self.settings.api_key
            if not api_key:
                raise RuntimeError("DashScope 需要 DASHSCOPE_API_KEY。")
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })
            self.base_url = self.settings.base_url
            self.model = self.settings.model_name
            self.logger.info(f"[Rerank] dashscope model={self.model} url={self.base_url}")

        elif self.backend == "xinference":
            self.base_url = self.settings.base_url
            x_key = self.settings.api_key
            self.model = self.settings.model_name  # 例如 bge-reranker-large / bge-m3
            self.session = requests.Session()
            self.session.headers.update({"Content-Type": "application/json"})
            if x_key:
                self.session.headers.update({"Authorization": f"Bearer {x_key}"})
            self.logger.info(f"[Rerank] xinference model={self.model} url={self.base_url}")

        elif self.backend == "llamaindex":
            # 只用于 Postprocessor 包装
            self.model = self.settings.model_name
            self.logger.info(f"[Rerank] llamaindex(native) model={self.model}")

        else:
            raise ValueError(f"Unknown rerank backend: {self.backend}")


    def rerank(self, query: str, documents: Sequence[str], top_n: Optional[int] = None) -> List[Tuple[int, float, str]]:
        """返回按分数降序的原索引、分数、文本三元组。

        空文档直接返回空列表；非空输入时，零数量返回空列表，负数量抛出 ValueError。
        """
        if not documents:
            return []
        k = int(self.settings.top_n if top_n is None else top_n)
        if k < 0:
            raise ValueError("top_n must not be negative")
        if k == 0:
            return []

        if self.backend == "dashscope":
            return self._call_dashscope(query, documents, k)

        if self.backend == "xinference":
            return self._call_xinference(query, documents, k)

        if self.backend == "llamaindex":
            raise RuntimeError("llamaindex 后端仅用于 LlamaIndex Postprocessor。")

        raise ValueError(f"Unsupported backend: {self.backend}")

    # ------------ DashScope  ------------
    def _call_dashscope(self, query: str, docs: Sequence[str], k: int) -> List[Tuple[int, float, str]]:
        """请求 DashScope 并校验返回索引，再按分数截取；HTTP 响应退出时关闭，错误向上传播。"""
        payload = {
            "model": self.model,  # "gte-rerank-v2"
            "input": {"query": query, "documents": list(docs)},
            "parameters": {"return_documents": self.settings.return_documents, "top_n": k},
        }
        with self.session.post(self.base_url, json=payload, timeout=self.settings.timeout) as resp:
            resp.raise_for_status()
            data = resp.json()

        result = DashscopeRerankResponse.model_validate(data)
        out: List[Tuple[int, float, str]] = []
        for item in result.results:
            idx = item.index
            if idx >= len(docs):
                raise ValueError("DashScope reranker returned an invalid document index")
            out.append((idx, item.relevance_score, docs[idx]))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:k]

    # ------------ Xinference（OpenAI 风格 /v1/rerank） ------------
    def _call_xinference(self, query: str, docs: Sequence[str], k: int) -> List[Tuple[int, float, str]]:
        """请求 Xinference 并校验返回索引，再按分数截取；HTTP 响应退出时关闭，错误向上传播。"""
        payload = {
            "model": self.model,  # 如 bge-reranker-large / bge-m3
            "query": query,
            "documents": list(docs),
            "top_n": k,
            "return_documents": self.settings.return_documents,
        }
        with self.session.post(self.base_url, json=payload, timeout=self.settings.timeout) as resp:
            resp.raise_for_status()
            data = resp.json()

        result = XinferenceRerankResponse.model_validate(data)
        out: List[Tuple[int, float, str]] = []
        for item in result.results:
            idx = item.index
            if idx >= len(docs):
                raise ValueError("Xinference reranker returned an invalid document index")
            out.append((idx, item.relevance_score, docs[idx]))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:k]


    def close(self) -> None:
        """关闭 HTTP 后端持有的 Session；原生 LlamaIndex 模式不创建该 Session。"""
        if self.backend in {"dashscope", "xinference"}:
            self.session.close()


class LlamaIndexReranker(BaseNodePostprocessor):
    """Apply the configured reranker using LlamaIndex's QueryBundle protocol."""

    _settings: Any = PrivateAttr()
    _logger: Any = PrivateAttr()
    _native: Any = PrivateAttr(default=None)
    _service: Any = PrivateAttr(default=None)

    def __init__(self):
        super().__init__()
        self._settings = settings.reranker
        self._logger = logging.getLogger(__name__)
        self._prepare()

    def _prepare(self) -> None:
        """按配置初始化本地后处理器或远程重排服务，初始化失败直接传播。"""
        if self._settings.backend.lower() == "llamaindex":
            model = self._settings.model_name
            if any(key in model.lower() for key in ("bge", "reranker", "flag")):
                from llama_index.postprocessor.flag_embedding_reranker import FlagEmbeddingReranker
                self._native = FlagEmbeddingReranker(
                    model=model, top_n=self._settings.rerank_top_k, use_fp16=True,
                )
            else:
                from llama_index.core.postprocessor import SentenceTransformerRerank
                self._native = SentenceTransformerRerank(
                    model=model, top_n=self._settings.rerank_top_k,
                )
        else:
            self._service = Reranker(self._logger)

    def _postprocess_nodes(
        self, nodes: List[NodeWithScore], query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        """按查询重排节点并生成新的分数包装；空节点返回空列表，非空节点缺少查询时抛错。"""
        if not nodes:
            return []
        if query_bundle is None:
            raise ValueError("Reranking requires a query")
        k = self._settings.rerank_top_k
        if k < 0:
            raise ValueError("rerank_top_k must not be negative")
        if k == 0:
            return []
        if self._native is not None:
            return self._native.postprocess_nodes(nodes, query_bundle=query_bundle)[:k]
        if self._service is None:
            raise RuntimeError("Reranker service has not been initialized")
        ranked = self._service.rerank(
            query_bundle.query_str, [item.node.get_content() for item in nodes],
            top_n=k,
        )
        return [NodeWithScore(node=nodes[index].node, score=score)
                for index, score, _ in ranked]

    def close(self) -> None:
        """关闭包装器创建的远程重排服务；本地后处理器不走此关闭路径。"""
        if self._service is not None:
            self._service.close()


# ---------------- 自测 ----------------
if __name__ == "__main__":
    r = Reranker()
    q = "什么是文本排序模型"
    docs = [
        "文本排序模型广泛用于搜索引擎和推荐系统中，它们根据文本相关性对候选文本进行排序",
        "量子计算是计算科学的一个前沿领域",
        "预训练语言模型的发展给文本排序模型带来了新的进展",
    ]
    try:
        for i, s, t in r.rerank(q, docs, top_n=5):
            print(f"[{i}] {s:.4f}  {t}")
    finally:
        r.close()
