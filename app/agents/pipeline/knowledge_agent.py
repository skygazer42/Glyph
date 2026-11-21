"""Knowledge retrieval + synthesis agent built on KnowledgeService."""

from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import date
import logging
import os
import re
import time
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from autogen_core.models import UserMessage

from app.agents.service.tools import KnowledgeTool, WebSearchTool
from app.agents.service.progress import emit_progress, progress_step, source_references
from app.config.app_config import settings
from app.core.llms import model_client
from app.models.policy import FinalAnswer, PolicyDocument, PolicyType
from app.agents.domain.policy_domain import PolicyDomainContext


class KnowledgeAgent:
    """Wraps KnowledgeTool and LLM summarization to answer policy inquiries."""

    _TOPIC_GROUPS = (
        ("公积金",), ("养老保险", "养老金"),
        ("城乡居民", "居民基本养老保险", "居民养老保险"), ("医保", "医疗保险"),
    )
    _OPERATION_GROUPS = (
        ("购房资助", "住房资助", "资助房源"), ("贷款", "房贷", "商转公"),
        ("贴息", "利息补贴"), ("提取",), ("缴存", "缴交", "缴纳公积金"),
        ("租房", "房租", "租赁住房", "租住"),
        ("缴费档次", "缴费标准", "档次"), ("退休",), ("生育津贴",), ("营养补助",),
    )

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
        """检索政策并按置信度选择摘录或模型总结，必要时使用网页来源，返回带来源与路径元数据的答案。"""
        trace: Dict[str, float] = {}
        t_search = time.perf_counter()
        with progress_step("retrieval", "正在检索相关政策"):
            docs, scores, used_query = await self._domain_aware_search(query, domain_context)
        compatible = [
            (doc, score) for doc, score in zip(docs, scores, strict=True)
            if self._insurance_source_matches(query, doc)
        ]
        docs, scores = [doc for doc, _ in compatible], [score for _, score in compatible]
        trace["search_ms"] = round((time.perf_counter() - t_search) * 1000, 2)
        knowledge_timings = self.tool.last_timings
        focus = emphasis or (intent or {}).get("sub_intent") or "general"

        period = self._requested_period(query)
        if period is not None and (docs or self._is_amount_question(query)):
            current = [
                (doc, score) for doc, score in zip(docs, scores, strict=True)
                if self._temporal_status(doc, period) not in {"expired", "future", "wrong_year"}
            ]
            rate_query = self._is_amount_question(query)
            if rate_query:
                unit = r"(?:%|％|百分之)" if re.search(r"比例|利率|费率|百分", query) else r"(?:万|亿)?元"
                current = [
                    (doc, score) for doc, score in current
                    if (self._temporal_status(doc, period) == "covered" or (
                        self._temporal_status(doc, period) == "undated"
                        and period[0] <= date.today() <= period[1]
                        and "资料类型：official_service_guide" in doc.content.split("\n\n", 1)[0]
                    ))
                    and self._money_matches_period(query, doc, period, unit)
                ]
            if not current:
                label = f"{period[0].year}年度" if period[0].month == 1 and period[1].month == 12 else f"{period[0].isoformat()}至{period[1].isoformat()}"
                return FinalAnswer(
                    query_id=uuid4(),
                    answer=f"现有已核验资料不能确认{label}对应的{'适用金额标准' if rate_query else '适用规定'}。其他年度或已到期的资料不能直接套用；尚未核实该期间的新标准，请向主管部门核定。",
                    sources=docs, confidence=0.2, verification_passed=False,
                    metadata={"route": "knowledge", "reason": "temporal_evidence_gap", "requested_period": [value.isoformat() for value in period], "doc_count": len(docs)},
                    total_processing_time=0.0,
                )
            docs, scores = [doc for doc, _ in current], [score for _, score in current]
            if rate_query:
                docs = [
                    doc.model_copy(update={"metadata": {**doc.metadata, "current_guide_snapshot": True}})
                    if self._temporal_status(doc, period) == "undated" else doc
                    for doc in docs
                ]

        if docs:
            emit_progress("sources", sources=source_references(docs))
            # Dify KB 直返：启用时直接用 Dify 文本，不再调用本地 LLM
            if self._should_direct_return_dify(docs):
                top_doc = docs[0]
                preview_len = int(os.getenv("DIFY_KB_PREVIEW_CHARS", "1500") or "1500")
                preview = top_doc.content[:preview_len].strip()
                answer_text = preview or "暂未从 Dify 知识库获取到有效内容。"
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
            early_stop_threshold = settings.system.early_stop_conf

            financial_query = self._is_amount_question(query) or any(
                term in query for term in ("公积金", "贷款", "贴息", "补贴", "补助", "税", "医保", "保险", "医惠保", "养老金", "资助")
            )
            if initial_confidence >= early_stop_threshold and not financial_query:
                t_extract = time.perf_counter()
                self.logger.info(
                    "早停触发: 置信度 %.2f >= %.2f, 跳过重排和深度分析",
                    initial_confidence,
                    early_stop_threshold,
                )
                # 快速通道：直接生成答案
                # 优先走快速抽取，尽量避免 LLM 调用
                extracted = self._extract_policy_points(docs[0].content)
                if extracted:
                    trace["extract_ms"] = round(
                        (time.perf_counter() - t_extract) * 1000, 2
                    )
                    answer_text = "\n".join(f"- {b}" for b in extracted[:10])
                    answer_text += "\n\n答复依据：" + (docs[0].title or "相关政策")
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
                doc.retrieval_origin for doc in docs
            ]
            if doc_origins and all(origin == doc_origins[0] for origin in doc_origins):
                dominant_origin = doc_origins[0]
            elif "hierarchical_index" in doc_origins:
                dominant_origin = "hierarchical_index"
            else:
                dominant_origin = "knowledge_base"

            t_generate = time.perf_counter()
            extracted_answer = self._extract_preexisting_contract_answer(query, docs)
            if extracted_answer is not None:
                answer_text = extracted_answer
                trace["extract_ms"] = round((time.perf_counter() - t_generate) * 1000, 2)
            else:
                formatted_context = self._format_documents(docs)
                summary_prompt = self._build_summary_prompt(
                    query,
                    focus,
                    formatted_context,
                    context_label="参考资料",
                    domain_context=domain_context,
                )
                answer_text = await self._call_llm(summary_prompt)
                trace["llm_ms"] = round((time.perf_counter() - t_generate) * 1000, 2)
            answer_text = self._remove_unsupported_applicability_labels(answer_text, docs)
            if any(doc.metadata.get("current_guide_snapshot") for doc in docs):
                answer_text += "\n\n该金额仅反映已收录官方办事指南快照的公开受理标准；指南未载明施行期间，特殊群体及个人补缴金额仍须经办机构核定。"
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
                    "extractive": extracted_answer is not None,
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
                            "title": item["title"],
                            "url": item["url"],
                            "score": item["score"],
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
        """检索领域变体，按资料声明的地区优先保留本区依据，避免把市级窗口改称区级窗口。"""
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
            docs, scores = await self._search_knowledge(candidate)
            if docs:
                docs, scores = self._prefer_requested_region(
                    docs, scores, domain_context.region if domain_context else None
                )
                if not docs:
                    continue
                docs, scores = self._prefer_verified_evidence(query, docs, scores)
                if docs:
                    period = self._requested_period(query)
                    priority = {"covered": 0, "partial": 1, "undated": 2, "expired": 3, "future": 3, "wrong_year": 3}
                    ordered = sorted(zip(docs, scores, strict=True), key=lambda pair: (
                        priority[self._temporal_status(pair[0], period)] if period is not None else 0,
                        not pair[0].metadata.get("referenced_basis", False),
                        not pair[0].metadata.get("question_facet", False),
                        not pair[0].metadata.get("annual_product_match", False),
                    ))
                    docs, scores = [doc for doc, _ in ordered], [score for _, score in ordered]
                    return docs[:self.top_k], scores[:self.top_k], candidate
        return [], [], query

    async def _search_knowledge(
        self, query: str, filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """补查问题中完整出现的事项标题，保留真实相似度，避免长指南被短旧记录挤出。"""
        docs, scores = await self.tool.search(query, top_k=self.top_k, filters=filters)
        if len(docs) != len(scores):
            raise ValueError("Knowledge documents and scores must have matching lengths")
        if filters and "title" in filters:
            return docs, scores
        matches = {str(doc.id): (doc, score) for doc, score in zip(docs, scores, strict=True)}
        titles = []
        for doc in docs:
            match = re.search(r"^(?:资料名称|资料)[:：]([^\n]+)", doc.content)
            title = match.group(1).strip() if match else ""
            if len(title) >= 4 and title in query and title not in titles:
                titles.append(title)
        for title in titles[:3]:
            exact_docs, exact_scores = await self.tool.search(
                query, top_k=min(max(self.top_k * 4, 20), 100), threshold=0,
                filters={**(filters or {}), "title": title},
            )
            if len(exact_docs) != len(exact_scores):
                raise ValueError("Knowledge documents and scores must have matching lengths")
            for doc, score in zip(exact_docs, exact_scores, strict=True):
                matches[str(doc.id)] = (doc, score)
        requested_years = set(re.findall(r"(?<!\d)(20\d{2})(?!\d|元|块|万|亿|\.)", query))
        if len(requested_years) == 1:
            annual_filters = {**(filters or {}), "coverage_year": int(next(iter(requested_years)))}
            for doc in docs:
                title = re.sub(r"20\d{2}.*", "", doc.title).strip()
                if len(title) >= 4 and title in query:
                    annual_filters["title"] = title
                    break
            annual_docs, annual_scores = await self.tool.search(
                query, top_k=min(max(self.top_k * 4, 20), 100), threshold=0.45, filters=annual_filters,
            )
            if len(annual_docs) != len(annual_scores):
                raise ValueError("Knowledge documents and scores must have matching lengths")
            for doc, score in zip(annual_docs, annual_scores, strict=True):
                if "title" in annual_filters:
                    doc = doc.model_copy(update={"metadata": {**doc.metadata, "annual_product_match": True}})
                matches[str(doc.id)] = (doc, score)
        for doc, score in await self._recall_preexisting_evidence(query, list(matches.values()), filters):
            matches[str(doc.id)] = (doc, score)
        references: list[tuple[str, str]] = []
        for doc in docs:
            header = doc.content.split("\n\n", 1)[0]
            urls = re.findall(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", header)
            references.extend(("source", url) for url in urls if url != doc.source)
            for value in re.findall(r"[\u4e00-\u9fff]{2,12}〔20\d{2}〕\d+号", header):
                references.append(("content", re.split(r"结合|根据|参照|按照|参见", value)[-1]))
            if not any(url != doc.source for url in urls):
                references.extend(("title", value) for value in re.findall(r"《([^《》\n]{4,60}条例)》", header))
        # References are data observed in source headers. Look them up only in
        # the existing library; no referenced URL is fetched here.
        for kind, value in list(dict.fromkeys(references))[:3]:
            if filters and kind in filters and filters[kind] != value:
                continue
            basis_docs, basis_scores = await self.tool.search(
                query, top_k=min(max(self.top_k * 2, 10), 40), threshold=0,
                filters={**(filters or {}), kind: value},
            )
            if len(basis_docs) != len(basis_scores):
                raise ValueError("Knowledge documents and scores must have matching lengths")
            for doc, score in zip(basis_docs, basis_scores, strict=True):
                if kind == "content" and value not in doc.content.split("\n\n", 1)[-1]:
                    continue
                doc = doc.model_copy(update={"metadata": {**doc.metadata, "referenced_basis": True}})
                matches[str(doc.id)] = (doc, score)
        ordered = sorted(matches.values(), key=lambda pair: pair[1], reverse=True)
        return [doc for doc, _ in ordered], [score for _, score in ordered]

    async def _recall_preexisting_evidence(
        self, query: str, candidates: List[Tuple[PolicyDocument, float]], filters: Optional[Dict[str, Any]]
    ) -> List[Tuple[PolicyDocument, float]]:
        """补齐投保与既往理赔两个问题所需的同产品同年度条款，不扩大到其他保险。"""
        if not re.search(r"既往|带病|病史", query):
            return []
        years = set(re.findall(r"(?<!\d)(20\d{2})(?!\d|元|块|万|亿|\.)", query))
        if len(years) != 1:
            return []
        year = int(next(iter(years)))
        for candidate, _ in candidates:
            header = candidate.content.split("\n\n", 1)[0]
            if "资料类型：commercial_insurance_formal_sales_documents" not in header:
                continue
            product = re.sub(r"20\d{2}.*", "", candidate.title).strip()
            if len(product) < 4 or product not in query or f"保障年度：{year}" not in header:
                continue
            bound = {**(filters or {}), "source": candidate.source, "coverage_year": year}
            if filters and any(key in filters and filters[key] != bound[key] for key in ("source", "coverage_year")):
                continue
            reserved: List[Tuple[PolicyDocument, float]] = []
            anchors = (
                ("既往病史参保人员赔付比例", "preexisting_claims"),
                ("既往病史参保人员待遇约定", "preexisting_definition"),
            )
            for anchor, facet in anchors[:max(1, self.top_k - 1)]:
                if filters and "content" in filters and filters["content"] != anchor:
                    continue
                hits, hit_scores = await self.tool.search(
                    f"{product} {year} {anchor} 保障计划 特别约定",
                    top_k=min(max(self.top_k, 4), 10), threshold=0,
                    filters={**bound, "content": anchor},
                )
                if len(hits) != len(hit_scores):
                    raise ValueError("Knowledge documents and scores must have matching lengths")
                for doc, score in zip(hits, hit_scores, strict=True):
                    if doc.source != candidate.source or anchor not in doc.content.split("\n\n", 1)[-1]:
                        continue
                    doc = doc.model_copy(update={"metadata": {**doc.metadata, "question_facet": facet, "annual_product_match": True}})
                    reserved.append((doc, score))
                    break
            return reserved
        return []

    @classmethod
    def _insurance_source_matches(cls, query: str, doc: PolicyDocument) -> bool:
        """商业补充险的保费、免赔额不能代替居民/职工基本医保标准。"""
        header = doc.content.split("\n\n", 1)[0]
        commercial = (
            "资料类型：commercial_insurance_" in header
            or "说明：商业保险产品平台" in header
            or "资料类型：official_published_product_information" in header
            or bool(re.search(r"惠保|补充医疗保险", doc.title))
        )
        medical_query = any(
            term in query for group in cls._TOPIC_GROUPS if "医保" in group for term in group
        )
        if not commercial or not medical_query:
            return True
        product = re.sub(r"20\d{2}.*", "", doc.title).strip()
        return bool(re.search(r"商业|补充|惠保", query) or (len(product) >= 4 and product in query))

    @staticmethod
    def _extract_preexisting_contract_answer(query: str, docs: List[PolicyDocument]) -> Optional[str]:
        """同源年度条款已补齐时保留责任标题和完整特别约定，避免概括丢失限制条件。"""
        if not re.search(r"既往|带病|病史", query) or re.search(r"材料|申请表|证件|理赔流程|如何理赔|怎么理赔", query):
            return None
        facets = {doc.metadata.get("question_facet"): doc for doc in docs if doc.metadata.get("question_facet")}
        claims, definition = facets.get("preexisting_claims"), facets.get("preexisting_definition")
        if claims is None or definition is None or claims.source != definition.source:
            return None
        conditions = re.search(
            r"既往病史参保人员待遇约定[：:]?\s*(.*?)(?=\n\d+[.．、]|\Z)",
            definition.content.split("\n\n", 1)[-1], re.DOTALL,
        )
        if conditions is None:
            return None
        responsibility = ""
        excerpts = []
        for line in claims.content.split("\n\n", 1)[-1].splitlines():
            if re.match(r"责任[一二三四五六七八九十]+[:：]", line):
                responsibility = line
            if responsibility and "既往病史参保人员赔付比例" in line:
                sentences = re.findall(r"[^。！？]*既往病史参保人员赔付比例[^。！？]*(?:[。！？]|$)", line)
                excerpts.append(responsibility + "\n" + "\n".join(sentences))
        enrollment = None
        for doc in sorted(docs, key=lambda item: item.source != claims.source):
            sentence = re.search(
                r"[^。！？\n]*(?:不设置年龄|不限年龄)[^。！？\n]*(?:[。！？]|$)",
                doc.content.split("\n\n", 1)[-1],
            )
            if sentence is not None:
                enrollment = (doc, sentence.group().strip())
                break
        if not excerpts or enrollment is None:
            return None
        sections = [
            ("参保条件原文", enrollment[0], enrollment[1]),
            ("既往病史待遇及适用范围原文", definition, conditions.group(1).strip()),
            ("各责任赔付差异原文", claims, "\n\n".join(excerpts)),
        ]
        numbered = {doc.id: index for index, doc in enumerate(docs, 1)}
        answer = ["参保条件与赔付约定分别如下。以下均为对应资料原文，个人赔付须结合实际保单核定："]
        for label, doc, text in sections:
            answer.append(f"{label}（资料{numbered[doc.id]}）：\n" + "\n".join(f"> {line}" for line in text.splitlines()))
        return "\n\n".join(answer)

    @staticmethod
    def _remove_unsupported_applicability_labels(answer: str, docs: List[PolicyDocument]) -> str:
        """出版年份不能被模型改写成资料未声明的开放式适用年度。"""
        source_text = "\n".join(doc.content for doc in docs)
        return re.sub(
            r"[（(]?(?:适用年度|适用时间|适用期间)\s*[:：]\s*(20\d{2}年(?:及|和)?(?:以前|以后|之前|之后))\s*[）)]?",
            lambda match: match.group() if match.group(1) in source_text else "",
            answer,
        )

    @staticmethod
    def _is_amount_question(query: str) -> bool:
        return bool(re.search(
            r"多少钱|多少元|金额|(?:缴费|补贴|补助|计发|报销|赔付)标准|费率|利率|比例|"
            r"(?:补助|补贴|费用|缴费).{0,8}是多少|"
            r"(?:交|缴|领|拿|贷|提|赔|付|报销).{0,8}多少(?!天|日|年|月|岁|个?工作日)", query
        ))

    @classmethod
    def _requested_period(cls, query: str) -> Optional[Tuple[date, date]]:
        """只解析用户明确的办理期间；未指定期间时不把出版年当适用年度。"""
        years = set(re.findall(r"(?<!\d)(20\d{2})(?!\d|元|块|万|亿|\.)", query))
        if len(years) == 1:
            year = int(next(iter(years)))
            match = re.search(r"20\d{2}(?:年|[-/])(\d{1,2})(?:月|[-/])(?:(\d{1,2})日?)?", query)
            if match:
                month = int(match.group(1))
                if match.group(2):
                    day = date(year, month, int(match.group(2)))
                    return day, day
                return date(year, month, 1), date(year, month, monthrange(year, month)[1])
            return date(year, 1, 1), date(year, 12, 31)
        if not years and (
            any(word in query for word in ("现在", "当前", "目前", "现行", "今年"))
            or cls._is_amount_question(query)
        ):
            today = date.today()
            return today, today
        return None

    @staticmethod
    def _money_matches_period(
        query: str, doc: PolicyDocument, period: Tuple[date, date], unit: str
    ) -> bool:
        """按金额所在条款的局部期间核对，不因提纲某项旧金额而否定整份资料。"""
        body = doc.content.split("\n\n", 1)[-1]
        date_pattern = r"(20\d{2})(?:年|[-/])(\d{1,2})(?:(?:月|[-/])(\d{1,2})日?)?月?"
        for passage in re.split(r"\n\s*\n|[。；]", body):
            if not re.search(r"\d+(?:\.\d+)?\s*" + unit, passage):
                continue
            if not KnowledgeAgent._business_matches(query, doc.title + passage):
                continue
            # A payment/enrolment window is not the coverage period of its rate.
            if not re.search(r"缴费期|投保期|参保期|缴费截止", passage):
                dates = list(re.finditer(date_pattern, passage))
                lower = upper = None
                if len(dates) >= 2 and re.search(r"至|到|—|~|～", passage[dates[0].end():dates[1].start()]):
                    year, month, day = dates[0].groups()
                    lower = date(int(year), int(month), int(day) if day else 1)
                    year, month, day = dates[1].groups()
                    upper = date(int(year), int(month), int(day) if day else monthrange(int(year), int(month))[1])
                elif dates and re.search(r"截至|截止|适用至|适用到|计发至|标准至", passage[:dates[-1].start()]):
                    year, month, day = dates[-1].groups()
                    upper = date(int(year), int(month), int(day) if day else monthrange(int(year), int(month))[1])
                if (lower is not None and lower > period[0]) or (upper is not None and upper < period[1]):
                    continue
            return True
        return False

    @staticmethod
    def _temporal_status(doc: PolicyDocument, period: Tuple[date, date]) -> str:
        """到期日包含当天。没有施行期间的资料仅作背景，出版日不证明当期金额。"""
        header = doc.content.split("\n\n", 1)[0]
        coverage = re.search(r"^保障年度：(20\d{2})\s*$", header, flags=re.MULTILINE)
        if coverage and int(coverage.group(1)) not in {period[0].year, period[1].year}:
            return "wrong_year"
        start_match = re.search(r"^(?:施行日期|生效日期)：(\d{4}-\d{2}-\d{2})", header, flags=re.MULTILINE)
        end_match = re.search(r"^(?:到期日期|失效日期)：(\d{4}-\d{2}-\d{2})", header, flags=re.MULTILINE)
        start = date.fromisoformat(start_match.group(1)) if start_match else (doc.effective_date.date() if doc.effective_date else None)
        end = date.fromisoformat(end_match.group(1)) if end_match else (doc.expiry_date.date() if doc.expiry_date else None)
        if end is not None and end < period[0]:
            return "expired"
        if start is not None and start > period[1]:
            return "future"
        if (start is not None and start > period[0]) or (end is not None and end < period[1]):
            return "partial"
        if coverage or start is not None or end is not None:
            return "covered"
        return "undated"

    @staticmethod
    def _prefer_requested_region(
        docs: List[PolicyDocument], scores: List[float], region: Optional[str]
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """地区只取来源头部的声明；没有本区依据时不凭正文地址或问题补造地区。"""
        region_key = re.sub(r"江苏省?|常州市?|[市区县]", "", region or "")
        if not region_key:
            return docs, scores
        matching, broader = [], []
        for doc, score in zip(docs, scores, strict=True):
            match = re.search(r"^(适用地区|地区)[:：]([^\n]+)", doc.content, flags=re.MULTILINE)
            scope = match.group(2).strip() if match else ""
            if match and match.group(1) == "地区":
                scope = scope.split("；", 1)[0]
            scope_key = re.sub(r"江苏省?|常州市?|[市区县]", "", scope)
            if region_key in scope_key:
                matching.append((doc, score))
            elif scope_key in {"", "全国", "全省", "全"}:
                broader.append((doc, score))
        ordered = matching + broader
        return [doc for doc, _ in ordered], [score for _, score in ordered]

    @classmethod
    def _business_matches(cls, query: str, title: str) -> bool:
        """明确出现的业务词全部对应时才把某文金额视为本业务金额。"""
        requested = [
            aliases for aliases in cls._TOPIC_GROUPS + cls._OPERATION_GROUPS
            if any(alias in query for alias in aliases)
        ]
        return all(any(alias in title for alias in aliases) for aliases in requested)

    @classmethod
    def _prefer_verified_evidence(
        cls, query: str, docs: List[PolicyDocument], scores: List[float]
    ) -> Tuple[List[PolicyDocument], List[float]]:
        """仅完整事项或明确业务词对应时采用核验资料；未知业务不凭共享主题字丢原包。"""
        topic_groups, operation_groups = cls._TOPIC_GROUPS, cls._OPERATION_GROUPS
        requested_groups = [
            aliases for aliases in topic_groups + operation_groups
            if any(alias in query for alias in aliases)
        ]
        requested_operations = {
            index for index, aliases in enumerate(operation_groups)
            if any(alias in query for alias in aliases)
        }
        compatible, official = [], []
        has_matching_official = False
        for doc, score in zip(docs, scores, strict=True):
            if not cls._insurance_source_matches(query, doc):
                continue
            header = doc.content[:1200]
            if "资料类型：official_form_template" in header and not any(
                term in query for term in ("材料", "表格", "表单", "申请表", "证件", "怎么办理", "如何办理")
            ):
                continue
            title_match = re.search(r"^资料名称[:：]([^\n]+)", header)
            title = title_match.group(1) if title_match else doc.title
            source_operations = {
                index for index, aliases in enumerate(operation_groups)
                if any(alias in title for alias in aliases)
            }
            if requested_operations and source_operations and requested_operations.isdisjoint(source_operations):
                continue
            compatible.append((doc, score))
            if not re.search(r"^说明：官方", header, flags=re.MULTILINE):
                continue
            official.append((doc, score))
            full_title = len(title) >= 4 and title in query
            business_matches = bool(requested_groups) and all(
                any(alias in title for alias in aliases) for aliases in requested_groups
            )
            if full_title or business_matches:
                has_matching_official = True
        retained = official if has_matching_official else compatible
        return [doc for doc, _ in retained], [score for _, score in retained]

    async def _search_web(self, query: str) -> List[Dict[str, Any]]:
        """在线程中调用已启用的网页工具；未配置或未启用时返回空列表。"""
        tool = self.web_tool
        if not tool or not tool.enabled:
            return []
        return await asyncio.to_thread(tool.search, query, tool.max_results)

    async def _call_llm(self, prompt: str) -> str:
        with progress_step("answer_generation", "正在根据政策依据生成答复"):
            response = await model_client.create(
                [UserMessage(content=prompt, source="user")]
            )
            if not isinstance(response.content, str) or not response.content.strip():
                raise ValueError("Knowledge summary model returned no text")
            return response.content.strip()

    def _format_documents(self, docs: List[PolicyDocument]) -> str:
        chunks = []
        max_chars = settings.system.knowledge_max_context_per_doc
        for idx, doc in enumerate(docs[: self.top_k], 1):
            preview = doc.content[:max_chars]
            if doc.metadata.get("current_guide_snapshot"):
                preview = "【指南快照，未载施行期；仅可陈述公开受理标准，个人须核定】\n" + preview
            chunks.append(
                f"[资料{idx}] 标题：{doc.title}\n来源：{doc.source}\n内容摘录：{preview}\n"
            )
        return "\n".join(chunks)

    def _web_results_to_documents(self, results: List[Dict[str, Any]]) -> List[PolicyDocument]:
        """把网页工具的必需字段映射为政策文档，保留 URL 和分数元数据，不抓取网页或校验其权威性。"""
        docs: List[PolicyDocument] = []
        for idx, item in enumerate(results, 1):
            docs.append(
                PolicyDocument(
                    title=item["title"] or f"网络检索结果{idx}",
                    content=item["content"],
                    summary=None,
                    source=item["url"] or "web_search",
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
                        "url": item["url"],
                        "score": item["score"],
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
        scores = [item["score"] for item in results]
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
        calculation_limit = (
            "未匹配到可执行且已核验的计算规则，本次只解释公开条款和主管部门核定边界，"
            "不得生成个人金额，也不能认可尚未核实的乘算公式。"
            if focus == "rule_unmatched" else ""
        )
        return (
            "你是政府政策问答系统的知识专家。"
            "请严格根据【参考资料】回答，禁止臆造未出现的信息，无法确认时写“未明确”。"
            "先直接回答用户所问的能否、在哪里或哪些材料，再列直接依据。"
            "用户问题中的身份、金额和日期不是已经核实的事实。"
            "先区分各份资料的政策、业务和适用年度，只使用直接支持当前问题的条款。"
            "金额和档次的限制人群必须连同括号内的限制一起解释，不得扩展给普通居民。"
            "地区以资料的适用范围和办理机关为准，不能把市级或其他区的地点、电话改称用户所在区。"
            "用户指定区县但资料只说明市级办理窗口时，明确本区窗口尚未核实，保留原地区标签。"
            "发布日期不等于生效日期，明确区分采集日期、施行日期和业务适用年度；"
            "不得把不同位置的年份与月日拼接成新日期，"
            "也不得把发布日期写成受理或生效起点。没有明确起止日就不要补写。"
            "无需覆盖固定栏目，不主动增加用户未问的施行时间、办理期限或金额。"
            "如需说明日期，保留原标签，不将成文或印发时间冒充公开发布日期。"
            "金额必须对应用户所问年度和业务期间，宣传提纲的年度不能证明其中每个金额全年适用。"
            "用户问能否直接按某公式计算时，先核实变量、期间和个人核定事实；不能把问题里的公式当作已经获准的算法。"
            "只回答实际所问事项。原文没有列出申请材料时，不得补写“通常需身份证”等常识性材料。"
            "参保年龄不设门槛仍须保留正常参加基本医保等前提；可带既往症参保不等于所有费用均可赔付。"
            "用户问既往症时，分别说明能否参保和该年度保障计划中的理赔差异、既往人群定义及责任范围，不把普通条款与产品特别约定混为同一口径。"
            "不得将其他提取、缴存、贷款、保险等业务的材料、金额或资格拼接到本事项。"
            "个人资格或金额事实不完整时指出具体缺项，不推定可领取金额；金额试算须补齐事实后按规则执行。"
            "只说明当前问题所问的结论、直接条款和具体缺项。未问材料、金额或施行期，不增加这些栏目。"
            "表单须按真实用途区分；没有明确列为本事项必备的表，不得仅凭名称要求提交。"
            "资料未涉及的项目不用强行列出，只有家电等相应业务才涉及能效或旧机回收。"
            "非申即享事项不得从其他业务搬入申请材料清单；通常办理安排不等于用户申报窗口。"
            "每项关键金额、条件和材料注明对应资料编号，最后说明主要官方依据。\n\n"
            f"用户问题：{query}\n"
            f"关注点/意图：{focus}\n"
            f"计算边界：{calculation_limit}\n"
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

    def _extract_policy_points(self, text: str) -> List[str]:
        """先按政策正则去重摘取片段，无匹配时取最多八条含关键词句子；空文本返回空列表，不执行事实核验。"""
        if not text:
            return []
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
        origin = first.retrieval_origin
        return origin == "dify"

    def _collect_images(self, docs: List[PolicyDocument]) -> List[str]:
        """Collect image URLs from metadata of retrieved documents."""
        images: List[str] = []
        for doc in docs:
            imgs = doc.metadata.get("images", [])
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
