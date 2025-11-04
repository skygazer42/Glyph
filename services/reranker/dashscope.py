"""
DashScope reranker service integration.

Environment:
- DASHSCOPE_API_KEY: required
- RERANKER_MODEL: default 'gte-rerank-v2'
- RERANKER_ENDPOINT: default 'https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank'
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import requests


def rerank(
    query: str,
    documents: List[str],
    top_n: Optional[int] = None,
    return_documents: bool = True,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Call DashScope reranker and return JSON response.

    Returns the raw JSON; caller can parse to reorder documents.
    """
    api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not configured")

    model = model or os.getenv("RERANKER_MODEL", "gte-rerank-v2")
    endpoint = endpoint or os.getenv(
        "RERANKER_ENDPOINT",
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    )
    top_n = top_n or int(os.getenv("RERANKER_TOP_N", "5"))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": {
            "query": query,
            "documents": documents,
        },
        "parameters": {
            "return_documents": return_documents,
            "top_n": top_n,
        },
    }
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def reorder_by_rerank(
    query: str,
    doc_texts: List[str],
    top_n: Optional[int] = None,
    model: Optional[str] = None,
) -> List[Tuple[int, float]]:
    """Return list of (original_index, score) sorted by rerank score desc."""
    data = rerank(query, doc_texts, top_n=top_n, return_documents=False, model=model)
    # DashScope returns rankings under output? adjust according to actual response schema
    items = []
    # Try to parse generic structures
    for i, item in enumerate(data.get("output", {}).get("results", [])):
        idx = item.get("index", i)
        score = float(item.get("score", 0.0))
        items.append((idx, score))
    if not items and isinstance(data.get("results"), list):
        for i, item in enumerate(data["results"]):
            idx = item.get("index", i)
            score = float(item.get("score", 0.0))
            items.append((idx, score))
    # fallback: identity
    if not items:
        items = list(zip(range(len(doc_texts)), [0.0] * len(doc_texts)))
    items.sort(key=lambda x: x[1], reverse=True)
    return items

