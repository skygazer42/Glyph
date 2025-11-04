# -*- coding: utf-8 -*-

import logging
from typing import Any, List, Optional, Sequence, Tuple

import requests
from config.settings import settings

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
        self.logger = logger or _log()
        self.session = requests.Session()
        self.backend = (self.s.backend or "dashscope").lower()

        self.local_model = None
        self.local_type = None  # "flag" | "cross"

        if self.backend == "dashscope":
            if not (self.s.dashscope_api_key or  self.s.api_key):
                raise RuntimeError("DashScope 需要 DASHSCOPE_API_KEY。")
            self.session.headers.update({
                "Authorization": f"Bearer {self.s.dashscope_api_key or self.s.api_key}",
                "Content-Type": "application/json",
            })
            self.base_url = self.s.base_url
            self.model = self.s.dashscope_model or self.s.model_name
            self.logger.info(f"[Rerank] dashscope model={self.model} url={self.base_url}")

        elif self.backend == "xinference":
            x_base = getattr(self.s, "xinference_base_url", "http://10.168.2.250:9997/v1")
            x_path = getattr(self.s, "xinference_rerank_path", "/v1/rerank")
            x_key  = getattr(self.s, "xinference_api_key", None)
            self.x_url = x_base.rstrip("/") + x_path
            self.model = self.s.model_name  # 例如 bge-reranker-large / bge-m3
            self.session.headers.update({"Content-Type": "application/json"})
            if x_key:
                self.session.headers.update({"Authorization": f"Bearer {x_key}"})
            self.x_return_docs = bool(getattr(self.s, "xinference_return_documents", True))
            self.logger.info(f"[Rerank] xinference model={self.model} url={self.x_url}")

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
        k = int(top_n or self.s.top_n)
        norm = bool(self.s.normalize_scores if normalize is None else normalize)

        if self.backend in ("local", "flagembedding", "sentence-transformers"):
            pairs = [(query, t) for t in documents]
            if self.local_type == "flag":
                scores = self.local_model.compute_score(pairs, normalize=norm)
            else:
                scores = self.local_model.predict(pairs)
                scores = scores.tolist() if hasattr(scores, "tolist") else list(scores)
                if norm and len(scores) > 1:
                    mn, mx = min(scores), max(scores)
                    if mx > mn:
                        scores = [(s - mn) / (mx - mn) for s in scores]
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:k]
            return [(i, float(s), documents[i]) for i, s in ranked]

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
        resp = self.session.post(self.base_url, json=payload, timeout=self.s.timeout)
        resp.raise_for_status()
        data = resp.json()

        items = (data.get("output") or {}).get("results") or data.get("data") or []
        out: List[Tuple[int, float, str]] = []
        for it in items:
            idx = it.get("index")
            score = float(it.get("score", 0.0))
            doc = it.get("document")
            text = doc.get("text", "") if isinstance(doc, dict) else (doc if isinstance(doc, str) else None)
            if idx is None and text and text in docs:
                idx = docs.index(text)
            if isinstance(idx, int) and 0 <= idx < len(docs):
                out.append((idx, score, docs[idx]))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:k]

    # ------------ Xinference（OpenAI 风格 /v1/rerank） ------------
    def _call_xinference(self, query: str, docs: Sequence[str], k: int) -> List[Tuple[int, float, str]]:
        payload = {
            "model": self.model,  # 如 bge-reranker-large / bge-m3
            "query": query,
            "documents": list(docs),
            "top_n": k,
            "return_documents": self.x_return_docs,
        }
        resp = self.session.post(self.x_url, json=payload, timeout=self.s.timeout)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data") or data.get("results") or []
        out: List[Tuple[int, float, str]] = []
        for it in items:
            idx = it.get("index")
            score = it.get("relevance_score", it.get("score", 0.0))
            try: score = float(score)
            except Exception: score = 0.0
            doc = it.get("document")
            text = doc.get("text", "") if isinstance(doc, dict) else (doc if isinstance(doc, str) else None)
            if idx is None and text and text in docs:
                idx = docs.index(text)
            if isinstance(idx, int) and 0 <= idx < len(docs):
                out.append((idx, score, docs[idx]))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:k]


# ---------------- LlamaIndex Postprocessor（按 settings 使用） ----------------
try:
    from llama_index.core.schema import NodeWithScore
    from llama_index.core.postprocessor.types import BaseNodePostprocessor
except Exception:
    NodeWithScore = Any
    class BaseNodePostprocessor:  # 允许未安装 LlamaIndex 也能 import
        def __init__(self, **kwargs): ...
        def _postprocess_nodes(self, nodes: List[Any], query_str: Optional[str] = None) -> List[Any]: return nodes

class LlamaIndexReranker(BaseNodePostprocessor):
    def __init__(self):
        super().__init__()
        self.rerank = settings.reranker
        self.logger = _log()
        self.native = None
        self.service = None
        self._prepare()

    def _prepare(self):
        if self.s.backend.lower() == "llamaindex":
            mn = (self.s.model_name or "").lower()
            try:
                if any(k in mn for k in ("bge", "reranker", "flag")):
                    from llama_index.core.postprocessor import FlagEmbeddingReranker
                    self.native = FlagEmbeddingReranker(model=self.s.model_name,
                                                        top_n=self.s.rerank_top_k,
                                                        use_fp16=True,
                                                        normalize=self.s.normalize_scores)
                else:
                    from llama_index.core.postprocessor import SentenceTransformerRerank
                    self.native = SentenceTransformerRerank(model=self.s.model_name,
                                                            top_n=self.s.rerank_top_k)
            except Exception as e:
                self.logger.warning(f"LlamaIndex 内置不可用，回退通用 Service: {e}")
        if self.native is None:
            self.service = Reranker(self.logger)

    def _postprocess_nodes(self, nodes: List[NodeWithScore], query_str: Optional[str] = None) -> List[NodeWithScore]:
        if not nodes: return nodes
        k = self.s.rerank_top_k or self.s.top_n
        if self.native is not None:
            out = self.native._postprocess_nodes(nodes, query_str=query_str)  # type: ignore
            return out[:k]

        texts = [getattr(n.node, "get_content", None)() if hasattr(n.node, "get_content")
                 else getattr(n.node, "text", "") for n in nodes]
        ranked = self.service.rerank(query_str or "", texts, top_n=k, normalize=self.s.normalize_scores)
        keep = {i: sc for i, sc, _ in ranked}
        filtered: List[NodeWithScore] = []
        for i, n in enumerate(nodes):
            if i in keep:
                try:
                    n = NodeWithScore(node=n.node, score=float(keep[i]))
                except Exception:
                    pass
                filtered.append(n)
        filtered.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)
        return filtered[:k]


# ---------------- 自测 ----------------
if __name__ == "__main__":
    r = Reranker()
    q = "什么是文本排序模型"
    docs = [
        "文本排序模型广泛用于搜索引擎和推荐系统中，它们根据文本相关性对候选文本进行排序",
        "量子计算是计算科学的一个前沿领域",
        "预训练语言模型的发展给文本排序模型带来了新的进展",
    ]
    for i, s, t in r.rerank(q, docs, top_n=5, normalize=True):
        print(f"[{i}] {s:.4f}  {t}")
