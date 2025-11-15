"""High-level service that wires together the agent pipeline."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.agents.framework.base.types import PolicyDocument
from app.agents.pipeline import (
    ClarifierAgent,
    DialogueAgent,
    GraphAgent,
    KnowledgeAgent,
    RewriteAgent,
    RuleEngineAgent,
    Text2SQLAgent,
    WorkflowAgent,
)
from app.agents.framework.common import session_store
from .tools import (
    IntentDetectionTool,
    KnowledgeTool,
    VisionTool,
    WebSearchTool,
    UserProfileTool,
)
from app.agents.domain import PolicyDomainContextBuilder
from app.core import logging_manager
from app.config import settings
from app.knowledge.service import KnowledgeService
from app.knowledge.faq_responder import FAQResponder
from app.utils.config import Config
from app.utils.document_loader import DocumentLoader
from app.models.base import Attachment, UserQuery

# 配置主日志管理器
logging_manager.configure(
    log_dir=str(settings.system.log_dir),
    filename="agent.log",
    max_bytes=settings.system.log_max_bytes,
    backup_count=settings.system.log_backup_count,
)

# 确保autogen logger只有UTF-8 handler,无重复
import logging
from app.core.logging_manager import UTF8JsonFormatter

autogen_logger = logging.getLogger("autogen_core.events")
autogen_logger.handlers.clear()
autogen_logger.setLevel(logging.INFO)
autogen_logger.propagate = False

# 添加UTF-8格式化的console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(UTF8JsonFormatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
))
autogen_logger.addHandler(console_handler)


class AgentService:
    """Single entrypoint that orchestrates the streamlined agent pipeline."""

    SQL_KEYWORDS = ["sql", "数据库", "数据表", "字段", "列名", "select", "查询语句"]
    PRODUCT_KEYWORDS = [
        "空调",
        "冰箱",
        "洗衣机",
        "电视",
        "家电",
        "净水器",
        "洗碗机",
        "电脑",
        "热水器",
        "油烟机",
    ]

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> None:
        self.config = config or Config.from_env()
        self.intent_tool = IntentDetectionTool()
        self.knowledge_tool = KnowledgeTool(knowledge_service)
        search_cfg = self.config.web_search
        self.web_search_tool = WebSearchTool(
            api_key=(search_cfg.tavily_api_key or None),
            max_results=search_cfg.max_results,
            search_depth=search_cfg.search_depth,
            enabled=search_cfg.enabled,
            site_filter=search_cfg.site_filter,
        )
        vision_cfg = self.config.vision
        self.vision_tool = VisionTool(
            enabled=vision_cfg.enabled,
            model=vision_cfg.model,
            api_key=(vision_cfg.api_key or None),
            base_url=vision_cfg.base_url or None,
            prompt_template=vision_cfg.prompt_template,
            max_images=vision_cfg.max_images,
            max_output_tokens=vision_cfg.max_output_tokens,
        )
        profile_db_path = self.config.user_profile_db_path
        self.user_profile_tool = UserProfileTool(db_path=profile_db_path)
        self._loader = DocumentLoader()

        # Pipeline agents
        self.rewrite_agent = RewriteAgent()
        self.knowledge_agent = KnowledgeAgent(
            self.knowledge_tool, web_search_tool=self.web_search_tool
        )
        self.graph_agent = GraphAgent(self.knowledge_agent)
        self.rule_agent = RuleEngineAgent()
        self.text2sql_agent = Text2SQLAgent()
        self.dialogue_agent = DialogueAgent()
        self.clarifier_agent = ClarifierAgent()
        self.workflow_agent = WorkflowAgent(
            vision_tool=self.vision_tool,
            knowledge_agent=self.knowledge_agent,
            rule_agent=self.rule_agent,
            user_profile_tool=self.user_profile_tool,
        )
        self.faq_responder = FAQResponder()
        self._domain_context_builder = PolicyDomainContextBuilder()
        self._ingest_batch_size = max(1, getattr(self.config.performance, "batch_size", 10))
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await self._maybe_seed_lightrag()
            self._initialized = True

    async def _maybe_seed_lightrag(self) -> None:
        seed_dir = getattr(self.config, "lightrag_seed_data_dir", None)
        if not seed_dir:
            return
        if not getattr(self.graph_agent, "_graph_agent", None):
            logging_manager.info("LightRAG 未启用，跳过自动导入。")
            return

        seed_path = Path(seed_dir)
        if not seed_path.exists():
            logging_manager.warning("LightRAG 种子目录不存在：%s", seed_dir)
            return

        current_manifest = self._collect_seed_manifest(seed_path)
        if not current_manifest:
            logging_manager.warning("LightRAG 种子目录中没有可解析的文档：%s", seed_dir)
            return

        workdir = self._get_lightrag_workdir()
        manifest_path = workdir / "seed_manifest.json"
        existing_manifest = self._load_seed_manifest(manifest_path)
        workdir_has_data = self._workdir_has_data(workdir, manifest_path)

        same_seed = (
            existing_manifest is not None
            and existing_manifest.get("seed_dir") == str(seed_path.resolve())
            and existing_manifest.get("files") == current_manifest
        )

        if workdir_has_data and same_seed:
            logging_manager.info("LightRAG 种子目录未变化，且工作目录已有数据，跳过自动导入。")
            return

        if not workdir_has_data and not manifest_path.exists():
            logging_manager.info("LightRAG 工作目录为空，开始自动导入种子数据。")
        elif not same_seed:
            logging_manager.info("检测到 LightRAG 种子目录内容发生变化，触发重新导入。")

        try:
            batch: List[PolicyDocument] = []
            total_ingested = 0
            for doc in self._loader.iter_documents_from_directory(seed_dir):
                batch.append(doc)
                if len(batch) >= self._ingest_batch_size:
                    await self.graph_agent.ingest(batch)
                    total_ingested += len(batch)
                    batch = []
            if batch:
                await self.graph_agent.ingest(batch)
                total_ingested += len(batch)

            if not total_ingested:
                logging_manager.warning("LightRAG 种子目录未加载到任何有效文档：%s", seed_dir)
                return

            self._write_seed_manifest(manifest_path, seed_path, current_manifest)
            logging_manager.info(
                "已自动将 %s 篇文档导入 LightRAG（目录：%s）。", total_ingested, seed_dir
            )
        except Exception as exc:
            logging_manager.warning("LightRAG 自动导入失败：%s", exc)

    def _get_lightrag_workdir(self) -> Path:
        configured = os.getenv("LIGHTRAG_WORKDIR")
        if configured:
            return Path(configured)
        return Path("resources/data/lightrag")

    def _collect_seed_manifest(self, seed_path: Path) -> Dict[str, Dict[str, int]]:
        manifest: Dict[str, Dict[str, int]] = {}
        try:
            for file in seed_path.rglob("*"):
                if file.is_file() and file.suffix.lower() in self._loader.supported_extensions:
                    try:
                        stat = file.stat()
                        rel_path = str(file.relative_to(seed_path))
                        manifest[rel_path] = {
                            "size": int(stat.st_size),
                            "mtime": int(stat.st_mtime),
                        }
                    except OSError:
                        continue
        except Exception:
            return {}
        return manifest

    def _load_seed_manifest(self, manifest_path: Path) -> Optional[Dict[str, Any]]:
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_seed_manifest(
        self,
        manifest_path: Path,
        seed_path: Path,
        manifest_data: Dict[str, Dict[str, int]],
    ) -> None:
        payload = {
            "seed_dir": str(seed_path.resolve()),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "files": manifest_data,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def _workdir_has_data(self, workdir: Path, manifest_path: Path) -> bool:
        if not workdir.exists():
            return False
        try:
            manifest_real = manifest_path.resolve() if manifest_path.exists() else None
            for item in workdir.iterdir():
                try:
                    if manifest_real and item.resolve() == manifest_real:
                        continue
                except FileNotFoundError:
                    continue
                return True
        except Exception:
            return False
        return False

    async def process_query(
        self,
        query: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
        attachments: Optional[List[Attachment]] = None,
    ) -> Any:
        start = time.perf_counter()
        await self.initialize()
        attachments = attachments or []

        (
            session_id,
            effective_query,
            conversation_context,
            history_used,
        ) = self._prepare_conversation_context(session_id, user_id, query)

        # 0) 问候/闲聊快速检测：避免短句被 FAQ 模糊命中
        logging_manager.info("[AgentService] 接收到用户提问: %s", query)

        if self._looks_like_greeting(query):
            logging_manager.info("[AgentService] 命中问候检测，直接走 dialogue route")
            final = self.dialogue_agent.respond("greeting")
            session_store.add_answer(session_id, final)
            metadata = final.metadata or {}
            metadata.update(
                {
                    "route": "dialogue",
                    "rewritten_query": query,
                    "session_id": session_id,
                    "user_id": user_id,
                    "connection_id": connection_id,
                    "conversation_context": {
                        "history_used": history_used,
                        "history_turns": len(conversation_context.get("history", [])),
                        "is_new_session": conversation_context.get("is_new_session", True),
                    },
                }
            )
            final.metadata = metadata
            final.total_processing_time = time.perf_counter() - start
            self._ensure_route_and_citations(final)
            return final

        # 1) FAQ 短路：优先用原始问题命中即可返回
        faq_final = self.faq_responder.maybe_answer(query)
        if faq_final:
            logging_manager.info(
                "[AgentService] FAQ 命中 question=%s similarity=%.3f",
                faq_final.metadata.get("faq_question"),
                faq_final.metadata.get("similarity"),
            )
            intent_result = {
                "intent": "faq_cache",
                "confidence": faq_final.confidence,
                "processing_chain": ["faq_cache"],
            }
            route = "faq_cache"
            final = faq_final
            # 立刻封装并返回，避免进入改写/意图等后续环节
            session_store.add_answer(session_id, final)
            metadata = final.metadata or {}
            metadata.update(
                {
                    "route": route,
                    "intent": intent_result,
                    "rewritten_query": query,  # FAQ 命中时未改写
                    "session_id": session_id,
                    "user_id": user_id,
                    "connection_id": connection_id,
                    "conversation_context": {
                        "history_used": history_used,
                        "history_turns": len(conversation_context.get("history", [])),
                        "is_new_session": conversation_context.get("is_new_session", True),
                    },
                }
            )
            final.metadata = metadata
            final.total_processing_time = time.perf_counter() - start
            self._ensure_route_and_citations(final)
            return final
        else:
            rewritten_query = await self.rewrite_agent.rewrite(
                effective_query,
                context=conversation_context,
                domain_hint=None,
            )
            logging_manager.info(
                "[AgentService] 改写结果: %s -> %s",
                query,
                rewritten_query,
            )
            domain_context = self._domain_context_builder.build(rewritten_query)
            # FAQ 仅针对原始问题；改写后不再重复匹配
            # 如果未命中 FAQ，继续走后续流程
            rewritten_query = rewritten_query
            domain_context = domain_context
            
            # Fast-path routing to reduce LLM calls
            fast_route = self._fast_route(
                original_query=query,
                rewritten_query=rewritten_query,
                connection_id=connection_id,
                attachments=attachments,
                domain_meta=domain_context.to_metadata(),
            )
            if fast_route:
                logging_manager.info("[AgentService] FastPath 命中 route=%s", fast_route)
                intent_result = {"intent": "fast_path", "raw_query": query, "domain_context": domain_context.to_metadata()}
                route = fast_route
            else:
                logging_manager.info("[AgentService] FastPath 未命中，调用意图检测")
                intent_result = await self.intent_tool.detect(rewritten_query)
            # 保存原始查询供路由逻辑使用
            intent_result["raw_query"] = query
            intent_result["domain_context"] = domain_context.to_metadata()
            if not fast_route:
                route = self._resolve_route(intent_result, rewritten_query, connection_id, attachments)

            logging_manager.info(
                "[AgentService] 最终路由 route=%s intent=%s", route, (intent_result or {}).get("intent")
            )

            if route == "dialogue":
                final = self.dialogue_agent.respond(intent_result.get("intent", "chit_chat"))
            elif route == "clarify":
                # 追问场景下根据原始问题 + 领域元数据，按缺失槽位选择固定模板，不再回显内部拼接的历史上下文
                final = self.clarifier_agent.ask(query, domain_context.to_metadata())
            elif route == "rule_engine":
                final = await self.rule_agent.compute(rewritten_query, intent=intent_result)
            elif route == "text2sql":
                final = await self.text2sql_agent.answer(
                    rewritten_query, connection_id=connection_id
                )
            elif route == "graph":
                final = await self.graph_agent.answer(rewritten_query, intent=intent_result)
            elif route == "workflow":
                final = await self.workflow_agent.answer(
                    rewritten_query,
                    attachments=attachments,
                    intent=intent_result,
                )
            else:  # knowledge 默认
                final = await self.knowledge_agent.answer(
                    rewritten_query,
                    intent=intent_result,
                    domain_context=domain_context,
                )

        session_store.add_answer(session_id, final)

        metadata = final.metadata or {}
        metadata.update(
            {
                "route": route,
                "intent": intent_result,
                "routing_debug": getattr(self, "_routing_debug", []),
                "rewritten_query": rewritten_query,
                "session_id": session_id,
                "user_id": user_id,
                "connection_id": connection_id,
                "conversation_context": {
                    "history_used": history_used,
                    "history_turns": len(conversation_context.get("history", [])),
                    "is_new_session": conversation_context.get("is_new_session", True),
                },
                "domain_context": domain_context.to_metadata(),
            }
        )
        if attachments:
            metadata.setdefault("attachments", [att.model_dump() for att in attachments])
        final.metadata = metadata
        final.total_processing_time = time.perf_counter() - start
        self._ensure_route_and_citations(final)
        return final

    async def ingest_paths(self, paths: List[str]) -> Dict[str, int]:
        batch: List[PolicyDocument] = []
        total_loaded = 0
        total_indexed = 0
        total_rag_indexed = 0

        async def _flush_batch():
            nonlocal batch, total_loaded, total_indexed, total_rag_indexed
            if not batch:
                return
            indexed = await self.knowledge_tool.ingest(batch)
            rag_indexed = await self.graph_agent.ingest(batch)
            total_indexed += indexed
            total_rag_indexed += rag_indexed
            total_loaded += len(batch)
            batch = []

        for path in paths:
            if os.path.isdir(path):
                try:
                    iterator = self._loader.iter_documents_from_directory(path)
                except FileNotFoundError:
                    logging_manager.warning("未找到目录：%s", path)
                    continue
            else:
                try:
                    doc = self._loader.load_single_file(path)
                except Exception as exc:
                    logging_manager.warning("加载文件失败 %s：%s", path, exc)
                    doc = None
                iterator = (doc,) if doc else tuple()

            for doc in iterator:
                batch.append(doc)
                if len(batch) >= self._ingest_batch_size:
                    await _flush_batch()

        if not total_loaded and not batch:
            return {"loaded_docs": 0, "kb_indexed": 0, "rag_indexed": 0}

        await _flush_batch()
        logging_manager.info("Ingested %s documents into vector store", total_loaded)
        return {"loaded_docs": total_loaded, "kb_indexed": total_indexed, "rag_indexed": total_rag_indexed}

    async def detect_intent(self, query: str) -> Dict[str, Any]:
        return await self.intent_tool.detect(query)

    async def search_knowledge(
        self,
        query: str,
        *,
        top_k: int = 5,
        threshold: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[PolicyDocument], List[float]]:
        return await self.knowledge_tool.search(
            query, top_k=top_k, threshold=threshold, filters=filters
        )

    def _resolve_route(
        self,
        intent_result: Dict[str, Any],
        rewritten_query: str,
        connection_id: Optional[int],
        attachments: List[Attachment],
    ) -> str:
        self._routing_debug = []  # collect reasons for the final metadata
        intent = (intent_result or {}).get("intent", "policy_inquiry")
        sub_intent = (intent_result or {}).get("sub_intent")
        original_query = (
            (intent_result or {}).get("raw_query")
            or (intent_result or {}).get("original_query")
            or ""
        )
        domain_meta = (intent_result or {}).get("domain_context") or {}
        def looks_like_graph() -> bool:
            return self._looks_like_graph_question(rewritten_query, sub_intent) or (
                original_query and self._looks_like_graph_question(original_query, sub_intent)
            )
        if attachments and any(att.is_image() for att in attachments):
            if self.vision_tool.enabled:
                self._routing_debug.append("has_image_attachment=>workflow")
                return "workflow"
        if intent in {"user_history", "user_profile"}:
            self._routing_debug.append(f"intent={intent}=>workflow")
            return "workflow"
        if intent in {"greeting", "farewell", "chit_chat"}:
            self._routing_debug.append(f"intent={intent}=>dialogue")
            return "dialogue"
        if intent == "clarification":
            self._routing_debug.append("intent=clarification=>clarify")
            return "clarify"
        if intent == "calculation":
            self._routing_debug.append("intent=calculation=>rule_engine")
            return "rule_engine"
        if intent == "summary":
            self._routing_debug.append("intent=summary=>graph")
            return "graph"
        if intent == "comparison":
            if looks_like_graph():
                self._routing_debug.append("intent=comparison + graph_keywords=>graph")
                return "graph"
            self._routing_debug.append("intent=comparison=>knowledge")
            return "knowledge"

        if self._looks_like_sql_question(rewritten_query) and connection_id:
            self._routing_debug.append("sql_keywords + has_connection_id=>text2sql")
            return "text2sql"

        if self._needs_clarification(original_query, rewritten_query, domain_meta):
            self._routing_debug.append("needs_clarification_heuristic=>clarify")
            return "clarify"

        if self._looks_like_subsidy_calculation(rewritten_query, domain_meta):
            self._routing_debug.append("looks_like_subsidy_calculation=>rule_engine")
            return "rule_engine"

        chains = (intent_result or {}).get("chains") or []
        if "vision_chain" in chains and self.vision_tool.enabled:
            self._routing_debug.append("chains:vision/user_history=>workflow")
            return "workflow"
        if "user_history_chain" in chains:
            return "workflow"
        graph_chain_requested = "graph_chain" in chains
        kb_chain_requested = "kb_chain" in chains

        if graph_chain_requested and self._looks_like_graph_question(
            rewritten_query, sub_intent
        ):
            # 只有在明确的关系/比较用例下才切到 Graph；否则继续走知识库降低成本
            if not kb_chain_requested or connection_id is None:
                self._routing_debug.append("chains:graph_chain + graph_keywords=>graph")
                return "graph"
        if "calculation_chain" in chains:
            self._routing_debug.append("chains:calculation_chain=>rule_engine")
            return "rule_engine"

        if intent == "policy_inquiry" and looks_like_graph():
            if connection_id is None:
                self._routing_debug.append("policy_inquiry + graph_keywords=>graph")
                return "graph"

        if self._looks_like_user_history(rewritten_query):
            self._routing_debug.append("looks_like_user_history=>workflow")
            return "workflow"

        self._routing_debug.append("fallback=>knowledge")
        return "knowledge"

    def _prepare_conversation_context(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        query: str,
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Ensure session presence, record用户查询并返回上下文/增强后的查询。"""

        default_context: Dict[str, Any] = {"history": [], "is_new_session": True}
        try:
            sid, _ = session_store.create_or_update_session(session_id, user_id)
            context_payload = session_store.get_context(sid, current_query=query)
            user_query = UserQuery(
                text=query,
                session_id=sid,
                user_id=user_id,
                context=context_payload,
            )
            session_store.add_query(sid, user_query)
            augmented_query, history_used = self._augment_query_with_history(query, context_payload)
            return sid, augmented_query, context_payload, history_used
        except Exception as exc:  # pragma: no cover - defensive fallback
            logging_manager.warning("会话上下文处理失败：%s", exc)
            return session_id or "", query, default_context, False

    def _augment_query_with_history(
        self,
        query: str,
        context_payload: Dict[str, Any],
        max_snippets: int = 10,
    ) -> Tuple[str, bool]:
        """Append recent multi-turn history to the query when available."""

        # 读取 .env 配置窗口（0 表示关闭记忆）
        try:
            from app.config import settings as _settings
            window = int(getattr(getattr(_settings, 'system', _settings), 'conversation_history_window', 5))
        except Exception:
            window = 5

        history = context_payload.get("history") or []
        if not history or window <= 0:
            return query, False

        snippets: List[str] = []
        max_snippets = max(1, window * 2)
        for item in history[-max_snippets:]:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            role = "用户" if item.get("type") == "query" else "助手"
            snippets.append(f"{role}:{text}")

        if not snippets:
            return query, False

        history_text = "\n".join(snippets)
        # 简短问题直接改写成“历史+当前问题”结构，长问题则附加参考段落
        if len(query) <= 200:
            augmented = (
                "请结合以下对话历史回答用户最新问题。\n"
                f"历史：\n{history_text}\n\n用户最新问题：{query}"
            )
        else:
            augmented = f"{query}\n\n【最近对话参考】\n{history_text}"
        return augmented, True

    def _looks_like_sql_question(self, query: str) -> bool:
        q = query.lower()
        return any(keyword in q for keyword in self.SQL_KEYWORDS)

    def _looks_like_user_history(self, query: str) -> bool:
        keywords = [
            "历史查询",
            "用户历史",
            "个人历史",
            "个人资料",
            "用户信息",
            "user history",
            "user profile",
        ]
        q_lower = query.lower()
        return any(kw in query or kw in q_lower for kw in keywords)

    def _looks_like_greeting(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q:
            return False
        # 常见问候/寒暄/在吗/打招呼
        patterns = [
            r"^(你好|您好|hi|hello|哈喽|在吗|早上好|中午好|下午好|晚上好)[!！。.?]*$",
            r"^(hey|yo)[!！。.?]*$",
        ]
        for pat in patterns:
            if re.match(pat, q):
                return True
        # 极短消息且无关键词，视为闲聊
        if len(q) <= 3 and not any(ch.isdigit() for ch in q):
            return True
        return False

    def _looks_like_graph_question(self, query: str, sub_intent: Optional[str] = None) -> bool:
        """
        Detect questions that ask for relationships, responsible parties, or process linkage,
        which are better answered by LightRAG.
        """
        graph_keywords = [
            "关系",
            "关联",
            "联系",
            "梳理",
            "脉络",
            "负责",
        ]
        process_keywords = ["流程", "环节", "节点", "链路", "步骤", "分工"]
        q_lower = query.lower()
        if any(kw in query or kw in q_lower for kw in graph_keywords):
            return True
        if sub_intent in {"process", "documents"} and any(
            kw in query or kw in q_lower for kw in process_keywords
        ):
            return True
        return False

    def _fast_route(
        self,
        *,
        original_query: str,
        rewritten_query: str,
        connection_id: Optional[int],
        attachments: List[Attachment],
        domain_meta: Dict[str, Any],
    ) -> Optional[str]:
        # Attachments → workflow
        if attachments and any(att.is_image() for att in attachments) and self.vision_tool.enabled:
            return "workflow"
        # SQL keywords → text2sql
        if self._looks_like_sql_question(rewritten_query) and connection_id:
            return "text2sql"
        # Need clarification?
        if self._needs_clarification(original_query, rewritten_query, domain_meta):
            return "clarify"
        # Subsidy computation?
        if self._looks_like_subsidy_calculation(rewritten_query, domain_meta):
            return "rule_engine"
        # Graph-like?
        if self._looks_like_graph_question(rewritten_query):
            return "graph"
        return None

    def _needs_clarification(
        self,
        original_query: str,
        rewritten_query: str,
        domain_meta: Dict[str, Any],
    ) -> bool:
        text = f"{original_query} {rewritten_query}"
        triggers = [
            "是否符合",
            "是否满足",
            "能否享受",
            "是否可以享受",
            "有没有资格",
            "是否有资格",
            "是否符合条件",
            "能不能补贴",
            "是否可以补贴",
        ]
        if not any(term in text for term in triggers):
            return False
        has_number = bool(re.search(r"\d", text))
        has_price = bool(re.search(r"\d+(\.\d+)?\s*元", text))
        keywords = (domain_meta or {}).get("keywords") or []
        has_product = any(kw in text for kw in self.PRODUCT_KEYWORDS) or any(
            kw in keywords for kw in self.PRODUCT_KEYWORDS
        )
        has_energy = any(tag in text for tag in ["1级", "一级", "2级", "二级", "能效", "水效"])
        if has_product and has_price and has_energy:
            return False
        if not has_product or not has_energy or (not has_price and not has_number):
            return True
        return False

    def _looks_like_subsidy_calculation(
        self,
        query: str,
        domain_meta: Dict[str, Any],
    ) -> bool:
        if "补贴" not in query and "补助" not in query:
            return False
        has_price = bool(re.search(r"\d+(\.\d+)?\s*元", query))
        if not has_price:
            return False
        keywords = (domain_meta or {}).get("keywords") or []
        has_product = any(kw in query for kw in self.PRODUCT_KEYWORDS) or any(
            kw in keywords for kw in self.PRODUCT_KEYWORDS
        )
        if not has_product:
            return False
        has_energy = any(tag in query for tag in ["1级", "一级", "2级", "二级", "能效", "水效"])
        return has_energy

    def _ensure_route_and_citations(self, final) -> None:
        route = (final.metadata or {}).get("route") if hasattr(final, "metadata") else None
        route_line = f"【路由】{route}" if route else None
        citation_line = self._format_citation_block(final)

        blocks = []
        answer_text = final.answer or ""
        if route_line:
            blocks.append(route_line)
        if citation_line:
            blocks.append(citation_line)
        if not blocks:
            return
        suffix = "\n" + "\n".join(blocks)
        if answer_text and not answer_text.endswith("\n"):
            final.answer = answer_text + "\n" + suffix.lstrip("\n")
        else:
            final.answer = answer_text + suffix

    def _format_citation_block(self, final) -> Optional[str]:
        sources = getattr(final, "sources", None) or []
        lines: List[str] = []
        for doc in sources[:3]:
            title = getattr(doc, "title", None) or "未知来源"
            source = getattr(doc, "source", None) or ""
            if not source and hasattr(doc, "metadata") and doc.metadata:
                source = doc.metadata.get("path") or doc.metadata.get("origin") or ""
            lines.append(f"- {title}（{source or '内部知识库'}）")
        if not lines:
            meta = final.metadata or {}
            if meta.get("rule_id"):
                lines.append(f"- DSL 规则：{meta['rule_id']}")
            elif meta.get("origin"):
                lines.append(f"- 知识来源：{meta['origin']}")
            elif meta.get("workflow"):
                lines.append("- Workflow 协作结果")
            elif meta.get("sql"):
                lines.append("- 数据库查询 (Text2SQL)")
        if not lines:
            return None
        return "【引用】\n" + "\n".join(lines)


__all__ = ["AgentService"]
