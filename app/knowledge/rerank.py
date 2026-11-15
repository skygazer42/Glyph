# -*- coding: utf-8 -*-

import logging
from typing import Any, List, Optional, Sequence, Tuple

import requests
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, PrivateAttr
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from app.config.app_config import settings


class RerankItem(BaseModel):
    model_config = ConfigDict(strict=True)

    index: int = Field(ge=0)
    relevance_score: float = Field(
        allow_inf_nan=False, validation_alias=AliasChoices("relevance_score", "score")
    )


class DashscopeRerankResponse(BaseModel):
    results: list[RerankItem] = Field(
        validation_alias=AliasChoices(AliasPath("output", "results"), "data")
    )


class XinferenceRerankResponse(BaseModel):
    results: list[RerankItem] = Field(validation_alias=AliasChoices("data", "results"))


def _log() -> logging.Logger:
    logger = logging.getLogger("rerank")
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s"))
        logger.addHandler(h)
        logger.setLevel(logging.INFO)
    return logger


class Reranker:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.s = settings.reranker
        self.logger = _log() if logger is None else logger
        self.backend = self.s.backend.lower()

        if self.backend == "dashscope":
            api_key = self.s.dashscope_api_key
            if api_key is None:
                api_key = self.s.api_key
            if not api_key:
                raise RuntimeError("DashScope 需要 DASHSCOPE_API_KEY。")
            self.session = requests.Session()
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })
            self.base_url = self.s.base_url
            self.model = self.s.model_name
            self.logger.info(f"[Rerank] dashscope model={self.model} url={self.base_url}")

        elif self.backend == "xinference":
            self.base_url = self.s.base_url
            x_key = self.s.api_key
            self.model = self.s.model_name  # 例如 bge-reranker-large / bge-m3
            self.session = requests.Session()
            self.session.headers.update({"Content-Type": "application/json"})
            if x_key:
                self.session.headers.update({"Authorization": f"Bearer {x_key}"})
            self.logger.info(f"[Rerank] xinference model={self.model} url={self.base_url}")

        elif self.backend == "llamaindex":
            # 只用于 Postprocessor 包装
            self.model = self.s.model_name
            self.logger.info(f"[Rerank] llamaindex(native) model={self.model}")

        else:
            raise ValueError(f"Unknown rerank backend: {self.backend}")


    def rerank(self, query: str, documents: Sequence[str], top_n: Optional[int] = None,
               normalize: Optional[bool] = None) -> List[Tuple[int, float, str]]:
        if not documents:
            return []
        k = int(self.s.top_n if top_n is None else top_n)
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
        payload = {
            "model": self.model,  # "gte-rerank-v2"
            "input": {"query": query, "documents": list(docs)},
            "parameters": {"return_documents": bool(self.s.return_documents), "top_n": k},
        }
        with self.session.post(self.base_url, json=payload, timeout=self.s.timeout) as resp:
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
        payload = {
            "model": self.model,  # 如 bge-reranker-large / bge-m3
            "query": query,
            "documents": list(docs),
            "top_n": k,
            "return_documents": self.s.return_documents,
        }
        with self.session.post(self.base_url, json=payload, timeout=self.s.timeout) as resp:
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
        self._logger = _log()
        self._prepare()

    def _prepare(self) -> None:
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
            top_n=k, normalize=self._settings.normalize_scores,
        )
        return [NodeWithScore(node=nodes[index].node, score=score)
                for index, score, _ in ranked]

    def close(self) -> None:
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
        for i, s, t in r.rerank(q, docs, top_n=5, normalize=True):
            print(f"[{i}] {s:.4f}  {t}")
    finally:
        r.close()
