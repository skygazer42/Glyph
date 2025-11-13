"""High-level service that wires together the agent pipeline."""

from __future__ import annotations

import asyncio
import json
import os
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

        rewritten_query = await self.rewrite_agent.rewrite(effective_query)
        faq_final = self.faq_responder.maybe_answer(rewritten_query)
        if faq_final:
            intent_result = {
                "intent": "faq_cache",
                "confidence": faq_final.confidence,
                "processing_chain": ["faq_cache"],
            }
            route = "faq_cache"
            final = faq_final
        else:
            intent_result = await self.intent_tool.detect(rewritten_query)
            # 保存原始查询供路由逻辑使用
            intent_result["raw_query"] = query
            route = self._resolve_route(intent_result, rewritten_query, connection_id, attachments)

            if route == "dialogue":
                final = self.dialogue_agent.respond(intent_result.get("intent", "chit_chat"))
            elif route == "clarify":
                final = self.clarifier_agent.ask(rewritten_query)
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
                final = await self.knowledge_agent.answer(rewritten_query, intent=intent_result)

        session_store.add_answer(session_id, final)

        metadata = final.metadata or {}
        metadata.update(
            {
                "route": route,
                "intent": intent_result,
                "rewritten_query": rewritten_query,
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
        if attachments:
            metadata.setdefault("attachments", [att.model_dump() for att in attachments])
        final.metadata = metadata
        final.total_processing_time = time.perf_counter() - start
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
        intent = (intent_result or {}).get("intent", "policy_inquiry")
        sub_intent = (intent_result or {}).get("sub_intent")
        original_query = (
            (intent_result or {}).get("raw_query")
            or (intent_result or {}).get("original_query")
            or ""
        )
        def looks_like_graph() -> bool:
            return self._looks_like_graph_question(rewritten_query, sub_intent) or (
                original_query and self._looks_like_graph_question(original_query, sub_intent)
            )
        if attachments and any(att.is_image() for att in attachments):
            if self.vision_tool.enabled:
                return "workflow"
        if intent in {"user_history", "user_profile"}:
            return "workflow"
        if intent in {"greeting", "farewell", "chit_chat"}:
            return "dialogue"
        if intent == "clarification":
            return "clarify"
        if intent == "calculation":
            return "rule_engine"
        if intent == "summary":
            return "graph"
        if intent == "comparison":
            if looks_like_graph():
                return "graph"
            return "knowledge"

        if self._looks_like_sql_question(rewritten_query) and connection_id:
            return "text2sql"

        chains = (intent_result or {}).get("chains") or []
        if "vision_chain" in chains and self.vision_tool.enabled:
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
                return "graph"
        if "calculation_chain" in chains:
            return "rule_engine"

        if intent == "policy_inquiry" and looks_like_graph():
            if connection_id is None:
                return "graph"

        if self._looks_like_user_history(rewritten_query):
            return "workflow"

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
        max_snippets: int = 6,
    ) -> Tuple[str, bool]:
        """Append recent multi-turn history to the query when available."""

        history = context_payload.get("history") or []
        if not history:
            return query, False

        snippets: List[str] = []
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


__all__ = ["AgentService"]
