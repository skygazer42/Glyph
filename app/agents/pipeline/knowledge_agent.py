"""Knowledge retrieval + synthesis agent built on KnowledgeService."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from autogen_core.models import UserMessage

from app.agents.service.tools import KnowledgeTool, WebSearchTool
from app.config import settings
from app.core.llms import model_client
from app.models.base import FinalAnswer, PolicyDocument, PolicyType
from app.agents.domain import PolicyDomainContext


class KnowledgeAgent:
    """Wraps KnowledgeTool and LLM summarization to answer policy inquiries."""

    def __init__(
        self,
        knowledge_tool: KnowledgeTool,
        top_k: int = 5,
        web_search_tool: WebSearchTool | None = None,
    ) -> None:
        self.tool = knowledge_tool
        self.top_k = top_k
        self.web_tool = web_search_tool
        self.logger = logging.getLogger(__name__)

    async def answer(
        self,
        query: str,
        *,
        intent: Optional[Dict[str, Any]] = None,
        emphasis: Optional[str] = None,
        domain_context: Optional[PolicyDomainContext] = None,
    ) -> FinalAnswer:
        trace: Dict[str, float] = {}
        t_search = time.perf_counter()
        docs, scores, used_query = await self._domain_aware_search(query, domain_context)
        trace["search_ms"] = round((time.perf_counter() - t_search) * 1000, 2)
        knowledge_timings = getattr(
            getattr(self.tool, "service", None), "last_timings", {}
        ) or {}
        focus = emphasis or (intent or {}).get("sub_intent") or "general"

        if docs:
            # Dify KB 直返：启用时直接用 Dify 文本，不再调用本地 LLM
            if self._should_direct_return_dify(docs):
                top_doc = docs[0]
                preview_len = int(os.getenv("DIFY_KB_PREVIEW_CHARS", "1500") or "1500")
                preview = (top_doc.content or "")[:preview_len].strip()
                answer_text = preview or "暂未从 Dify 知识库获取到有效内容。"
                answer_text = self._append_citations(answer_text, docs[:1])
                return FinalAnswer(
                    query_id=uuid4(),
                    answer=answer_text,
                    sources=docs,
                    confidence=self._estimate_confidence(scores),
                    verification_passed=True,
                    metadata={
                        "route": "knowledge",
                        "origin": "dify",
                        "doc_count": len(docs),
                        "images": self._collect_images(docs),
                        "early_stopped": True,
                        "dify_direct": True,
                        "search_query": used_query,
                        "domain_context": domain_context.to_metadata() if domain_context else None,
                        "knowledge_trace_ms": trace,
                        "search_timings_ms": knowledge_timings,
                    },
                    total_processing_time=0.0,
                )
            # 早停检查：如果检索置信度足够高，直接生成简化答案，无需重排和深度分析
            initial_confidence = self._estimate_confidence(scores)
            early_stop_threshold = getattr(getattr(settings, 'system', settings), 'early_stop_conf', 0.8)

            if initial_confidence >= early_stop_threshold:
                t_extract = time.perf_counter()
                self.logger.info(
                    "早停触发: 置信度 %.2f >= %.2f, 跳过重排和深度分析",
                    initial_confidence,
                    early_stop_threshold,
                )
                # 快速通道：直接生成答案
                # 优先走快速抽取，尽量避免 LLM 调用
                extracted = self._extract_policy_points((docs[0].content or ""))
                if extracted:
                    trace["extract_ms"] = round(
                        (time.perf_counter() - t_extract) * 1000, 2
                    )
                    answer_text = "\n".join(f"- {b}" for b in extracted[:10])
                    answer_text += "\n\n答复依据：" + (docs[0].title or "相关政策")
                    answer_text = self._append_citations(answer_text, docs[:1])
                else:
                    # 回退到一次性 LLM 总结
                    t_llm = time.perf_counter()
                    formatted_context = self._format_documents(docs)
                    summary_prompt = self._build_summary_prompt(
                        query,
                        focus,
                        formatted_context,
                        context_label="参考资料",
                        domain_context=domain_context,
                    )
                    answer_text = await self._call_llm(summary_prompt)
                    trace["llm_ms"] = round(
                        (time.perf_counter() - t_llm) * 1000, 2
                    )
                    answer_text = self._append_citations(answer_text, docs)

                return FinalAnswer(
                    query_id=uuid4(),
                    answer=answer_text,
                    sources=docs,
                    confidence=initial_confidence,
                    verification_passed=True,  # 高置信度结果
                    metadata={
                        "route": "knowledge",
                        "focus": focus,
                        "doc_count": len(docs),
                        "origin": "knowledge_base",
                        "images": self._collect_images(docs),
                        "early_stopped": True,
                        "early_stop_confidence": initial_confidence,
                        "search_query": used_query,
                        "domain_context": domain_context.to_metadata() if domain_context else None,
                        "knowledge_trace_ms": trace,
                        "search_timings_ms": knowledge_timings,
                    },
                    total_processing_time=0.0,
                )

            # 常规流程：继续重排和深度分析
            doc_origins = [
                getattr(doc, "retrieval_origin", "knowledge_base") for doc in docs
            ]
            if doc_origins and all(origin == doc_origins[0] for origin in doc_origins):
                dominant_origin = doc_origins[0]
            elif "hierarchical_index" in doc_origins:
                dominant_origin = "hierarchical_index"
            else:
                dominant_origin = "knowledge_base"

            t_llm = time.perf_counter()
            formatted_context = self._format_documents(docs)
            summary_prompt = self._build_summary_prompt(
                query,
                focus,
                formatted_context,
                context_label="参考资料",
                domain_context=domain_context,
            )
            answer_text = await self._call_llm(summary_prompt)
            trace["llm_ms"] = round((time.perf_counter() - t_llm) * 1000, 2)
            answer_text = self._append_citations(answer_text, docs)
            confidence = self._estimate_confidence(scores)
            return FinalAnswer(
                query_id=uuid4(),
                answer=answer_text,
                sources=docs,
                confidence=confidence,
                verification_passed=False,
                metadata={
                    "route": "knowledge",
                    "focus": focus,
                    "doc_count": len(docs),
                    "origin": dominant_origin,
                    "doc_origins": doc_origins,
                    "images": self._collect_images(docs),
                    "early_stopped": False,
                    "search_query": used_query,
                    "domain_context": domain_context.to_metadata() if domain_context else None,
                    "knowledge_trace_ms": trace,
                    "search_timings_ms": knowledge_timings,
                },
                total_processing_time=0.0,
            )

        web_results = await self._search_web(query)
        tool = self.web_tool
        if web_results and tool:
            trace["web_search_ms"] = round(
                (time.perf_counter() - t_search) * 1000, 2
            )
            t_llm = time.perf_counter()
            formatted_context = tool.format_results(web_results)
            summary_prompt = self._build_summary_prompt(
                query,
                focus,
                formatted_context,
                context_label="网络搜索结果",
                domain_context=domain_context,
            )
            answer_text = await self._call_llm(summary_prompt)
            trace["llm_ms"] = round((time.perf_counter() - t_llm) * 1000, 2)
            web_docs = self._web_results_to_documents(web_results)
            answer_text = self._append_citations(answer_text, web_docs)
            return FinalAnswer(
                query_id=uuid4(),
                answer=answer_text,
                sources=web_docs,
                confidence=self._estimate_web_confidence(web_results),
                verification_passed=False,
                metadata={
                    "route": "knowledge",
                    "focus": focus,
                    "doc_count": 0,
                    "origin": "web_search",
                    "doc_origins": ["web_search"],
                    "early_stopped": False,
                    "web_results": [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "score": item.get("score", 0.0),
                        }
                        for item in web_results
                    ],
                    "domain_context": domain_context.to_metadata() if domain_context else None,
                    "knowledge_trace_ms": trace,
                    "search_timings_ms": knowledge_timings,
                },
                total_processing_time=0.0,
            )

        return self._build_no_result_answer(
            query,
            reason="知识库暂无匹配文档且网络检索为空",
            trace=trace,
            search_timings=knowledge_timings,
        )

    async def _domain_aware_search(
        self,
        query: str,
        domain_context: Optional[PolicyDomainContext],
    ) -> Tuple[List[PolicyDocument], List[float], str]:
        filters: Dict[str, Any] = {}
        if domain_context and domain_context.region:
            filters["region"] = domain_context.region
        variants = []
        if domain_context:
            variants.extend(domain_context.search_variants)
        variants.append(query)
        seen = set()
        for candidate in variants:
            candidate = candidate.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            docs, scores = await self._safe_search(candidate, filters=filters)
            if docs:
                return docs, scores, candidate
        return [], [], query

    async def _safe_search(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[PolicyDocument], List[float]]:
        try:
            docs, scores = await self.tool.search(query, top_k=self.top_k, filters=filters)
            return docs or [], scores or []
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("知识检索失败: %s", exc)
            return [], []

    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        tool = self.web_tool
        if not tool or not tool.enabled:
            return []
        return await asyncio.to_thread(tool.search, query, tool.max_results)

    async def _call_llm(self, prompt: str) -> str:
        try:
            response = await model_client.create(
                [UserMessage(content=prompt, source="user")]
            )
            return (response.content or "").strip() or "抱歉，目前无法根据知识库生成可靠回答。"
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("知识总结 LLM 调用失败: %s", exc)
            return "抱歉，生成答案时出现问题，请稍后再试。"

    def _format_documents(self, docs: List[PolicyDocument]) -> str:
        chunks = []
        max_chars = getattr(getattr(settings, "system", settings), "knowledge_max_context_per_doc", 6000)
        if max_chars <= 0:
            max_chars = 6000
        for idx, doc in enumerate(docs[: self.top_k], 1):
            preview = (doc.content or "")[:max_chars].replace("\n", " ")
            chunks.append(
                f"[资料{idx}] 标题：{doc.title}\n来源：{doc.source}\n内容摘录：{preview}\n"
            )
        return "\n".join(chunks)

    def _web_results_to_documents(self, results: List[Dict[str, Any]]) -> List[PolicyDocument]:
        docs: List[PolicyDocument] = []
        for idx, item in enumerate(results, 1):
            docs.append(
                PolicyDocument(
                    title=item.get("title") or f"网络检索结果{idx}",
                    content=item.get("content") or "",
                    summary=None,
                    source=item.get("url") or "web_search",
                    doc_type=PolicyType.GUIDELINE,
                    publish_date=None,
                    effective_date=None,
                    expiry_date=None,
                    relevant_departments=[],
                    target_groups=[],
                    regions=[],
                    keywords=[],
                    embedding=None,
                    metadata={
                        "origin": "web_search",
                        "url": item.get("url", ""),
                        "score": item.get("score", 0.0),
                    },
                )
            )
        return docs

    def _estimate_confidence(self, scores: List[float]) -> float:
        if not scores:
            return 0.55
        avg = mean(scores)
        # Milvus score 0-1 (cosine/IP) -> map to 0.5-0.9
        return max(0.45, min(0.9, avg))

    def _estimate_web_confidence(self, results: List[Dict[str, Any]]) -> float:
        if not results:
            return 0.3
        scores = [item.get("score", 0.0) for item in results]
        avg = sum(scores) / len(scores)
        # Tavily score roughly 0-3 -> normalize to 0.35-0.65
        normalized = 0.35 + min(max(avg, 0.0), 3.0) / 3.0 * 0.3
        return round(normalized, 3)

    def _build_summary_prompt(
        self,
        query: str,
        focus: str,
        context: str,
        *,
        context_label: str,
        domain_context: Optional[PolicyDomainContext] = None,
    ) -> str:
        hints = self._format_domain_hints(domain_context)
        return (
            "你是政府政策问答系统的知识专家。"
            "请严格根据【参考资料】回答，禁止臆造未出现的信息，无法确认时写“未明确”。"
            "输出格式使用条列，涵盖以下要素：\n"
            "1) 适用地区/主体；2) 适用品类及能效/档次；3) 补贴标准（档次+封顶）；"
            "4) 申请/核销方式（渠道、发票/旧机回收要求）；5) 时间窗口/截止日期；"
            "6) 其他限制条件；7) 官方渠道或凭证要求。最后用一句话总结主要依据。\n\n"
            f"用户问题：{query}\n"
            f"关注点/意图：{focus}\n"
            f"领域提示：{hints}\n\n"
            f"{context_label}：\n{context}\n\n"
            "请直接给出条列答案，不要重复引用原文。"
        )

    def _format_domain_hints(self, domain_context: Optional[PolicyDomainContext]) -> str:
        if not domain_context:
            return "无"
        lines = []
        if domain_context.region:
            lines.append(f"重点地区：{domain_context.region}")
        if domain_context.time_window and domain_context.time_window.start:
            end = domain_context.time_window.end or domain_context.time_window.start
            lines.append(
                f"关注时间段：{domain_context.time_window.start.isoformat()} 至 {end.isoformat()}"
            )
        if domain_context.keywords:
            lines.append("关键主题：" + "、".join(domain_context.keywords))
        if not lines:
            return "无"
        return "；".join(lines)

    def _append_citations(self, answer: str, docs: List[PolicyDocument]) -> str:
        """Disable inline citation block; AgentService will append统一的【引用】段落。"""
        return answer

    def _extract_policy_points(self, text: str) -> List[str]:
        if not text:
            return []
        import re
        # 规则优先：抓取常用要点段落
        rules = [
            r"补贴范围[:：].{0,200}",
            r"补贴对象[:：].{0,200}",
            r"补贴标准[:：].{0,400}",
            r"(15%|20%|2000元)",
            r"申请流程[:：].{0,300}",
            r"(实名认证|领取资格|核销|支付立减)",
            r"(发票|签收|交旧|资金|有效期|用完即止).{0,100}",
        ]
        found: List[str] = []
        for pat in rules:
            for m in re.findall(pat, text, flags=re.IGNORECASE):
                seg = m.strip()
                if seg and seg not in found:
                    found.append(seg)
        if found:
            return found
        # 回退：取含关键词的前几句
        sentences = re.split(r"[\n。；;]", text)
        for s in sentences:
            s = s.strip()
            if any(k in s for k in ["补贴", "流程", "资格", "发票", "核销", "有效期"]):
                if s and s not in found:
                    found.append(s)
            if len(found) >= 8:
                break
        return found

    def _should_direct_return_dify(self, docs: List[PolicyDocument]) -> bool:
        if not docs:
            return False
        direct = os.getenv("DIFY_KB_DIRECT_ANSWER", "").lower() in {"1", "true", "yes", "on"}
        if not direct:
            return False
        first = docs[0]
        origin = getattr(first, "retrieval_origin", "") or first.metadata.get("origin")
        return origin == "dify"

    def _collect_images(self, docs: List[PolicyDocument]) -> List[str]:
        """Collect image URLs from metadata of retrieved documents."""
        images: List[str] = []
        for doc in docs or []:
            imgs = (getattr(doc, "metadata", {}) or {}).get("images") or []
            for img in imgs:
                if img and img not in images:
                    images.append(img)
        return images

    def _build_no_result_answer(
        self,
        query: str,
        reason: str,
        trace: Optional[Dict[str, float]] = None,
        search_timings: Optional[Dict[str, Any]] = None,
    ) -> FinalAnswer:
        return FinalAnswer(
            query_id=uuid4(),
            answer=f"暂未在知识库或联网检索中找到与“{query}”直接相关的政策条目。建议提供更多背景或确认关键词。",
            sources=[],
            confidence=0.2,
            verification_passed=False,
            metadata={
                "route": "knowledge",
                "reason": reason,
                "doc_origins": [],
                "knowledge_trace_ms": trace or {},
                "search_timings_ms": search_timings or {},
            },
            total_processing_time=0.0,
        )
