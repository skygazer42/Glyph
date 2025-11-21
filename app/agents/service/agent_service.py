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
from app.agents.framework.common import autogen_memory_store
from app.agents.service.agentchat_router import AgentChatRouter, agentchat_enabled
from app.agents.service.agentchat_team import AgentChatTeam, agentchat_team_enabled
from .tools import (
    IntentDetectionTool,
    KnowledgeTool,
    VisionTool,
    WebSearchTool,
    UserProfileTool,
)
from app.agents.domain import PolicyDomainContextBuilder
from app.core import logging_manager
from app.config import settings, Config
from app.knowledge.service import KnowledgeService
from app.knowledge.faq_responder import FAQResponder
from app.knowledge import DocumentLoader
from app.models.base import Attachment, UserQuery
from app.persistence.db.session import SessionLocal
from app.persistence import crud

import logging
from app.core.llms import model_client
from app.core.logging_manager import UTF8JsonFormatter

_LOGGING_CONFIGURED = False


def _configure_logging_once() -> None:
    """Ensure logging configuration only runs a single time per process."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging_manager.configure(
        log_dir=str(settings.system.log_dir),
        filename="agent.log",
        max_bytes=settings.system.log_max_bytes,
        backup_count=settings.system.log_backup_count,
    )

    autogen_logger = logging.getLogger("autogen_core.events")
    autogen_logger.handlers.clear()
    autogen_logger.setLevel(logging.INFO)
    autogen_logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        UTF8JsonFormatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    )
    autogen_logger.addHandler(console_handler)
    _LOGGING_CONFIGURED = True


class _PerfTrace:
    """Lightweight stage-level timing recorder."""

    def __init__(self, enabled: bool, slow_log_ms: int) -> None:
        self.enabled = enabled
        self._start = time.perf_counter()
        self._slow_log_ms = slow_log_ms
        self._marks: List[Dict[str, float]] = []

    def mark(self, stage: str) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        total_ms = (now - self._start) * 1000
        prev_total = self._marks[-1]["total_ms"] if self._marks else 0.0
        self._marks.append(
            {
                "stage": stage,
                "total_ms": round(total_ms, 2),
                "delta_ms": round(total_ms - prev_total, 2),
            }
        )

    def summary(self) -> Dict[str, Any]:
        if not self.enabled:
            return {}
        total_ms = (
            self._marks[-1]["total_ms"]
            if self._marks
            else round((time.perf_counter() - self._start) * 1000, 2)
        )
        return {"total_ms": total_ms, "stages": self._marks}

    @property
    def slow_threshold_ms(self) -> int:
        return self._slow_log_ms


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
    ROUTE_LABELS = {
        "dialogue": "DialogueAgent · 闲聊问候",
        "faq_cache": "FAQResponder · 快速命中",
        "clarify": "ClarifierAgent · 条件澄清",
        "knowledge": "KnowledgeAgent · 知识检索",
        "graph": "GraphAgent · LightRAG 关系推理",
        "rule_engine": "RuleEngineAgent · DSL 补贴计算",
        "text2sql": "Text2SQLAgent · 结构化查询",
        "workflow": "WorkflowAgent · 多模态协作",
        "agentchat": "AgentChat Router",
        "agentchat_stream": "AgentChat Router · 流式",
        "agentchat_team": "AgentChat Team",
        "agentchat_team_stream": "AgentChat Team · 流式",
        "agentchat_router_error": "AgentChat Router · 异常",
        "agentchat_team_error": "AgentChat Team · 异常",
    }

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        knowledge_service: Optional[KnowledgeService] = None,
    ) -> None:
        _configure_logging_once()
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
        self._default_connection_id: Optional[int] = None

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
        self._trace_latency = bool(getattr(self.config.performance, "trace_latency", True))
        self._slow_log_ms = int(getattr(self.config.performance, "slow_threshold_ms", 4000))
        self._log_timing_breakdown = bool(
            getattr(self.config.performance, "log_timing_breakdown", False)
        )
        self._agentchat_enabled = agentchat_enabled()
        self._agentchat_router: Optional[AgentChatRouter] = None
        self._agentchat_team_enabled = agentchat_team_enabled()
        self._agentchat_team: Optional[AgentChatTeam] = None
        self._agentchat_no_fallback = os.getenv("AGENTCHAT_NO_FALLBACK", "").lower() in {"1", "true", "yes", "on"}
        self._initialized = False
        self._init_lock = asyncio.Lock()
        # AgentChat 辅助状态：最近一次工具调用的文档与当前/历史附件
        self._last_agentchat_sources: List[PolicyDocument] = []
        self._tool_metrics: List[Dict[str, Any]] = []
        self._agentchat_attachments: List[Attachment] = []
        # 会话级附件缓存，用于“根据上传的发票…”这类后续追问重用上一轮附件
        self._session_attachments_store: Dict[str, List[Attachment]] = {}

        if self._agentchat_enabled:
            self._agentchat_router = AgentChatRouter(
                model_client=model_client,
                knowledge_tool=self._tool_agentchat_knowledge,
                graph_tool=self._tool_agentchat_graph,
                rule_tool=self._tool_agentchat_rule,
                text2sql_tool=self._tool_agentchat_text2sql,
                workflow_tool=self._tool_agentchat_workflow,
                memory_buffer_size=int(os.getenv("LLM_CTX_BUFFER_SIZE", "10")),
        )
        if self._agentchat_team_enabled:
            self._agentchat_team = AgentChatTeam(
                model_client=model_client,
                knowledge_tool=self._tool_agentchat_knowledge,
                graph_tool=self._tool_agentchat_graph,
                rule_tool=self._tool_agentchat_rule,
                text2sql_tool=self._tool_agentchat_text2sql,
                workflow_tool=self._tool_agentchat_workflow,
                memory_buffer_size=int(os.getenv("LLM_CTX_BUFFER_SIZE", "10")),
            )

    def _resolve_connection_id(self, connection_id: Optional[int]) -> Optional[int]:
        """
        Resolve an effective connection_id.

        - If explicit connection_id is provided, use it.
        - Otherwise, try to reuse/calculate a default MySQL connection:
          currently we look for a DBConnection named 'Policy Demo MySQL'
          (created by scripts/7_sync_text2sql_schema.py).
        """
        if connection_id is not None:
            return connection_id

        if self._default_connection_id is not None:
            return self._default_connection_id

        db = SessionLocal()
        try:
            default = crud.db_connection.get_by_name(db, name="Policy Demo MySQL")
            if default:
                self._default_connection_id = default.id
                return default.id
        finally:
            db.close()

        return None

    def _resolve_session_attachments(
        self,
        session_id: Optional[str],
        query: str,
        attachments: Optional[List[Attachment]],
    ) -> List[Attachment]:
        """
        根据当前请求与会话缓存解析附件：
        - 本次请求显式携带附件：写入会话缓存并直接返回；
        - 本次请求未携带附件，但用户语义上引用“上传的发票/图片/附件”等，
          且该会话下已有缓存附件：复用上一轮附件；
        - 其他情况：返回原始 attachments（通常为空）。
        """
        current = attachments or []

        # 没有会话标识时，不做任何缓存逻辑
        if not session_id:
            return current

        # 本轮有新附件：覆盖会话缓存
        if current:
            self._session_attachments_store[session_id] = list(current)
            return current

        # 本轮没有附件，但用户显式提到“上传的发票/图片/附件”等，尝试复用
        text = (query or "").strip()
        if not text:
            return current

        reuse_triggers = [
            "上传的发票",
            "这张发票",
            "刚才的发票",
            "上一张发票",
            "上传的小票",
            "上传的票据",
            "上传的凭证",
            "上传的图片",
            "上传的截图",
            "上传的照片",
            "上传的附件",
            "刚才上传的发票",
            "根据发票",
            "根据小票",
            "根据票据",
            "根据凭证",
        ]
        if any(term in text for term in reuse_triggers):
            cached = self._session_attachments_store.get(session_id) or []
            return list(cached)

        return current

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
        force_text2sql: bool = False,
    ) -> Any:
        start = time.perf_counter()
        trace = _PerfTrace(self._trace_latency, self._slow_log_ms)
        # 初始化工具耗时记录（agentchat 工具使用）
        self._tool_metrics = []
        await self.initialize()
        trace.mark("initialize")
        attachments = attachments or []

        # 尝试解析默认 connection_id（例如 Policy Demo MySQL）
        connection_id = self._resolve_connection_id(connection_id)

        (
            session_id,
            effective_query,
            conversation_context,
            history_used,
        ) = await self._prepare_conversation_context(session_id, user_id, query)
        trace.mark("conversation_context")

        # 基于会话缓存解析附件：支持“根据上传的发票/图片”这类后续追问自动复用上一轮附件
        attachments = self._resolve_session_attachments(session_id, query, attachments)
        # 记录当前请求的附件，供 AgentChat 工具（尤其 workflow_tool）使用
        self._agentchat_attachments = attachments

        conversation_meta = {
            "history_used": history_used,
            "history_turns": len(conversation_context.get("history", [])),
            "is_new_session": conversation_context.get("is_new_session", True),
        }

        # 0) 问候/闲聊快速检测：避免短句被 FAQ 模糊命中
        logging_manager.info("[AgentService] 接收到用户提问: %s", query)

        if self._looks_like_greeting(query):
            logging_manager.info("[AgentService] 命中问候检测，直接走 dialogue route")
            final = self.dialogue_agent.respond("greeting")
            trace.mark("agent:dialogue")
            return await self._finalize_answer(
                final=final,
                route="dialogue",
                intent_result={"intent": "greeting"},
                rewritten_query=query,
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id,
                conversation_context=conversation_meta,
                domain_context=None,
                attachments=attachments,
                trace=trace,
                start_time=start,
            )

        # 1) FAQ 短路：优先用原始问题命中即可返回
        faq_final = self.faq_responder.maybe_answer(query)
        trace.mark("faq_check")
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
            trace.mark("agent:faq_cache")
            return await self._finalize_answer(
                final=final,
                route=route,
                intent_result=intent_result,
                rewritten_query=query,
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id,
                conversation_context=conversation_meta,
                domain_context=None,
                attachments=attachments,
                trace=trace,
                start_time=start,
            )

        # AgentChat 主路径：启用且非强制 text2sql 时直接交给 AgentChat（绕过改写/意图）
        agentchat_primary = (self._agentchat_team_enabled or self._agentchat_enabled) and not force_text2sql
        if agentchat_primary:
            agentchat_meta: Dict[str, Any] = {}
            agentchat_used = False
            agentchat_error: Optional[str] = None
            if self._agentchat_team_enabled:
                try:
                    team_final, team_meta = await self._agentchat_team.run(session_id or "default", effective_query)
                except Exception as exc:  # 防御性：AgentChat Team 失败时允许回退
                    logging_manager.warning("AgentChat Team 调用失败，将尝试回退: %s", exc, exc_info=True)
                    team_final, team_meta = None, {"error": str(exc)}

                if team_final:
                    final = team_final
                    route = "agentchat_team"
                    agentchat_used = True
                    agentchat_meta = team_meta
                elif self._agentchat_no_fallback:
                    final = FinalAnswer(
                        query_id=uuid4(),
                        answer="抱歉，当前智能路由不可用，请稍后再试。",
                        sources=[],
                        confidence=0.2,
                        verification_passed=False,
                        metadata={"route": "agentchat_team_error", "agentchat_meta": team_meta},
                    )
                    agentchat_used = True
                    agentchat_meta = team_meta
                else:
                    agentchat_error = (team_meta or {}).get("error")

            if (not agentchat_used) and self._agentchat_enabled:
                try:
                    agentchat_final, ac_meta = await self._agentchat_router.run(session_id or "default", effective_query)
                except Exception as exc:  # 防御性：Router 失败时允许回退
                    logging_manager.warning("AgentChat Router 调用失败，将尝试回退: %s", exc, exc_info=True)
                    agentchat_final, ac_meta = None, {"error": str(exc)}

                if agentchat_final:
                    final = agentchat_final
                    route = "agentchat"
                    agentchat_used = True
                    agentchat_meta = ac_meta
                elif self._agentchat_no_fallback:
                    final = FinalAnswer(
                        query_id=uuid4(),
                        answer="抱歉，当前智能路由不可用，请稍后再试。",
                        sources=[],
                        confidence=0.2,
                        verification_passed=False,
                        metadata={"route": "agentchat_router_error", "agentchat_meta": ac_meta},
                    )
                    agentchat_used = True
                    agentchat_meta = ac_meta
                else:
                    agentchat_error = agentchat_error or (ac_meta or {}).get("error")

            if agentchat_used:
                return await self._finalize_answer(
                    final=final,
                    route=route,
                    intent_result={"intent": "agentchat"},
                    rewritten_query=effective_query,
                    session_id=session_id,
                    user_id=user_id,
                    connection_id=connection_id,
                    conversation_context=conversation_meta,
                    domain_context=None,
                    attachments=attachments,
                    trace=trace,
                    start_time=start,
                    agentchat_meta=agentchat_meta,
                )
            # AgentChat 未能产生结果且允许回退：直接走知识库主路径，避免 final 未定义错误
            if not self._agentchat_no_fallback:
                logging_manager.warning(
                    "AgentChat 未产生结果，回退到知识库 pipeline，error=%s",
                    agentchat_error,
                )
                route = "knowledge"
                intent_result = {"intent": "knowledge_fallback", "from_agentchat": True}
                rewritten_for_metadata = effective_query
                domain_context = None
                final = await self.knowledge_agent.answer(
                    effective_query,
                    intent=intent_result,
                    domain_context=domain_context,
                )
                trace.mark("agent:knowledge_fallback")
                return await self._finalize_answer(
                    final=final,
                    route=route,
                    intent_result=intent_result,
                    rewritten_query=rewritten_for_metadata,
                    session_id=session_id,
                    user_id=user_id,
                    connection_id=connection_id,
                    conversation_context=conversation_meta,
                    domain_context=domain_context,
                    attachments=attachments,
                    trace=trace,
                    start_time=start,
                )
        else:
            rewritten_query = await self.rewrite_agent.rewrite(
                effective_query,
                context=conversation_context,
                domain_hint=None,
            )
            trace.mark("rewrite")
            logging_manager.info(
                "[AgentService] 改写结果: %s -> %s",
                query,
                rewritten_query,
            )
            domain_context = self._domain_context_builder.build(rewritten_query)
            # FAQ 仅针对原始问题；改写后不再重复匹配
            # 如果未命中 FAQ，继续走后续流程

            # 如果显式开启 Text2SQL 模式且有可用 connection_id，则优先走 text2sql
            if force_text2sql and connection_id:
                logging_manager.info("[AgentService] Text2SQL 模式开启，强制路由到 text2sql")
                intent_result = {
                    "intent": "forced_text2sql",
                    "raw_query": query,
                    "domain_context": domain_context.to_metadata(),
                }
                route = "text2sql"
            else:
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
                    trace.mark("routing:fast_path")
                    intent_result = {
                        "intent": "fast_path",
                        "raw_query": query,
                        "domain_context": domain_context.to_metadata(),
                    }
                    route = fast_route
                else:
                    logging_manager.info("[AgentService] FastPath 未命中，调用意图检测")
                    intent_result = await self.intent_tool.detect(rewritten_query)
                    trace.mark("intent_detection")
                    # 保存原始查询供路由逻辑使用
                    intent_result["raw_query"] = query
                    intent_result["domain_context"] = domain_context.to_metadata()
                    route = self._resolve_route(
                        intent_result, rewritten_query, connection_id, attachments
                    )

            logging_manager.info(
                "[AgentService] 最终路由 route=%s intent=%s", route, (intent_result or {}).get("intent")
            )

            rewritten_for_metadata = rewritten_query

            # AgentChat Team 优先，其次 AgentChat Router，最后回退原逻辑
            agentchat_meta: Dict[str, Any] = {}
            agentchat_used = False
            # 多模态 / workflow 场景直接由 WorkflowAgent 处理，避免再包一层 AgentChat
            if self._agentchat_team_enabled and route in {"knowledge", "rule_engine", "text2sql"}:
                team_final, team_meta = await self._agentchat_team.run(session_id or "default", rewritten_query)
                if team_final:
                    logging_manager.info("[AgentService] AgentChat Team 命中")
                    final = team_final
                    route = f"{route}+agentchat_team"
                    rewritten_for_metadata = rewritten_query
                    agentchat_used = True
                    agentchat_meta = team_meta
                elif self._agentchat_no_fallback:
                    # 直接失败返回
                    final = FinalAnswer(
                        query_id=uuid4(),
                        answer="抱歉，当前智能路由不可用，请稍后再试。",
                        sources=[],
                        confidence=0.2,
                        verification_passed=False,
                        metadata={"route": "agentchat_team_error", "agentchat_meta": team_meta},
                    )
                    agentchat_used = True
                    agentchat_meta = team_meta
            if (not agentchat_used) and self._agentchat_enabled and route in {"knowledge", "rule_engine", "text2sql"}:
                agentchat_final, ac_meta = await self._agentchat_router.run(
                    session_id or "default", rewritten_query
                )
                if agentchat_final:
                    logging_manager.info("[AgentService] AgentChat Router 命中，使用 agentchat 结果")
                    final = agentchat_final
                    route = f"{route}+agentchat"
                    rewritten_for_metadata = rewritten_query
                    agentchat_used = True
                    agentchat_meta = ac_meta
                elif self._agentchat_no_fallback:
                    final = FinalAnswer(
                        query_id=uuid4(),
                        answer="抱歉，当前智能路由不可用，请稍后再试。",
                        sources=[],
                        confidence=0.2,
                        verification_passed=False,
                        metadata={"route": "agentchat_router_error", "agentchat_meta": ac_meta},
                    )
                    agentchat_used = True
                    agentchat_meta = ac_meta

            if agentchat_used:
                pass  # 已得到 final
            elif route == "dialogue":
                final = self.dialogue_agent.respond(intent_result.get("intent", "chit_chat"))
                trace.mark("agent:dialogue")
            elif route == "clarify":
                # 追问场景下根据原始问题 + 领域元数据，按缺失槽位选择固定模板，不再回显内部拼接的历史上下文
                final = self.clarifier_agent.ask(query, domain_context.to_metadata())
                trace.mark("agent:clarify")
            elif route == "rule_engine":
                # 规则计算场景下，优先保留改写后的业务表述，同时附加本轮用户补充信息，避免丢失价格/能效等槽位
                combined_query = rewritten_query
                if query and query not in combined_query:
                    combined_query = f"{rewritten_query}\n\n用户补充信息：{query}"
                final = await self.rule_agent.compute(combined_query, intent=intent_result)
                trace.mark("agent:rule_engine")
            elif route == "text2sql":
                final = await self.text2sql_agent.answer(query, connection_id=connection_id)
                rewritten_for_metadata = query
                trace.mark("agent:text2sql")
            elif route == "graph":
                final = await self.graph_agent.answer(rewritten_query, intent=intent_result)
                trace.mark("agent:graph")
            elif route == "workflow":
                final = await self.workflow_agent.answer(
                    rewritten_query,
                    attachments=attachments,
                    intent=intent_result,
                )
                trace.mark("agent:workflow")
            else:  # knowledge 默认
                final = await self.knowledge_agent.answer(
                    rewritten_query,
                    intent=intent_result,
                    domain_context=domain_context,
                )
                trace.mark("agent:knowledge")

        return await self._finalize_answer(
            final=final,
            route=route,
            intent_result=intent_result,
            rewritten_query=rewritten_for_metadata,
            session_id=session_id,
            user_id=user_id,
            connection_id=connection_id,
            conversation_context=conversation_meta,
            domain_context=domain_context,
            attachments=attachments,
            trace=trace,
            start_time=start,
        )

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

    async def _prepare_conversation_context(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        query: str,
    ) -> Tuple[str, str, Dict[str, Any], bool]:
        """Ensure session presence, record用户查询，并用 AgentChat memory 构造上下文。"""

        default_context: Dict[str, Any] = {"history": [], "is_new_session": True}
        try:
            sid, new_or_existing = session_store.create_or_update_session(session_id, user_id)
            context_payload = {"history": [], "is_new_session": new_or_existing.get("query_count", 0) == 0}
            # 记录用户消息到 AutoGen Memory
            await autogen_memory_store.add_user_message(sid, query)
            # 以 AutoGen memory 为唯一来源构造历史
            augmented, history_used = self._augment_query_with_history(query, {}, session_id=sid)
            return sid, augmented, context_payload, history_used
        except Exception as exc:  # pragma: no cover - defensive fallback
            logging_manager.warning("会话上下文处理失败：%s", exc)
            return session_id or "", query, default_context, False

    def _augment_query_with_history(
        self,
        query: str,
        context_payload: Dict[str, Any],
        max_snippets: int = 10,
        session_id: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """Append recent multi-turn history to the query using AutoGen memory as source."""

        try:
            from app.config import settings as _settings
            window = int(getattr(getattr(_settings, 'system', _settings), 'conversation_history_window', 5))
        except Exception:
            window = 5

        autogen_history: List[str] = []
        if session_id:
            try:
                autogen_history = autogen_memory_store.get_recent_messages(
                    session_id, limit=max_snippets
                )
            except Exception:
                autogen_history = []

        if (not autogen_history) or window <= 0:
            return query, False

        snippets: List[str] = []
        max_snippets = max(1, window * 2)
        for item in autogen_history[-max_snippets:]:
            text = (item or "").strip()
            if not text:
                continue
            snippets.append(text)

        if not snippets:
            return query, False

        history_text = "\n".join(snippets)
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

    def _looks_like_calculation(self, query: str) -> bool:
        """Rudimentary check whether the query asks for numeric subsidy calculation."""
        q = (query or "").lower()
        money_keywords = [
            "多少钱",
            "补贴多少",
            "补贴金额",
            "能补贴",
            "返现",
            "金额",
            "单价",
            "售价",
            "价格",
            "费用",
            "元",
            "rmb",
            "price",
            "cost",
        ]
        has_number = bool(re.search(r"[0-9]+", q))
        return has_number or any(kw in q for kw in money_keywords)

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
        process_keywords = [
            "流程",
            "环节",
            "节点",
            "链路",
            "步骤",
            "分工",
            "材料",
            "怎么操作",
            "如何操作",
            "怎么办理",
            "如何办理",
        ]
        q_lower = query.lower()
        if any(kw in query or kw in q_lower for kw in graph_keywords):
            return True
        # 带明显流程/材料关键词的问题，也优先尝试用 Graph/流程视角来回答
        if any(kw in query or kw in q_lower for kw in process_keywords):
            return True
        if sub_intent in {"process", "documents"} and any(
            kw in query or kw in q_lower for kw in process_keywords
        ):
            return True
        return False

    def _looks_like_policy_content_question(
        self,
        query: str,
        domain_meta: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Detect standard “policy content” questions that可以直接走知识库，
        用于 FastPath 跳过意图识别 LLM 调用。
        """
        text = (query or "").strip()
        if not text:
            return False

        # 需要同时具备“政策语境” + “内容类提问”两个要素
        policy_terms = ["政策", "实施细则", "实施方案", "补贴政策"]
        has_policy = any(term in text for term in policy_terms)
        if not has_policy:
            keywords = (domain_meta or {}).get("keywords") or []
            has_policy = any("政策" in str(kw) or "补贴" in str(kw) for kw in keywords)
            if not has_policy:
                return False

        content_triggers = [
            "具体内容",
            "主要内容",
            "详细内容",
            "包括哪些",
            "具体有哪些",
            "内容是什么",
            "怎么规定",
            "如何规定",
        ]
        if any(term in text for term in content_triggers):
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
        # Attachments（尤其是发票/票据/图片等）优先走 workflow，多模态/档案协作统一由 WorkflowAgent 处理
        if self._looks_like_multimodal_invoice_question(
            original_query=original_query,
            rewritten_query=rewritten_query,
            attachments=attachments,
        ):
            return "workflow"
        # SQL keywords → text2sql
        if self._looks_like_sql_question(rewritten_query) and connection_id:
            return "text2sql"
        # Need clarification?
        if self._needs_clarification(original_query, rewritten_query, domain_meta):
            return "clarify"
        # Subsidy computation?
        if self._looks_like_subsidy_calculation(original_query, domain_meta):
            return "rule_engine"
        # Temporal subsidy eligibility (“去年…今年还能享受补贴吗”) → Graph
        if self._looks_like_temporal_subsidy_eligibility(rewritten_query):
            return "graph"
        # Graph-like?
        if self._looks_like_graph_question(rewritten_query):
            return "graph"
        # Standard “政策具体内容”问答 → 直接走知识库
        if self._looks_like_policy_content_question(rewritten_query, domain_meta):
            return "knowledge"
        return None

    def _looks_like_multimodal_invoice_question(
        self,
        *,
        original_query: str,
        rewritten_query: str,
        attachments: List[Attachment],
    ) -> bool:
        """
        判断是否属于“发票/票据/附件/图片”驱动的多模态问题：
        - 明确上传了附件；
        - 且问题或附件元数据中出现发票/票据/图片/截图/照片/附件等关键词。
        这类问题应优先路由到 WorkflowAgent，由其串联视觉解析 + 规则计算。
        """
        if not attachments:
            return False

        text = f"{original_query} {rewritten_query}".strip()
        trigger_terms = ["发票", "票据", "票根", "小票", "凭证", "图片", "照片", "截图", "附件"]
        if any(term in text for term in trigger_terms):
            return True

        for att in attachments:
            meta_label = ""
            if att.metadata:
                meta_label = str(
                    att.metadata.get("label")
                    or att.metadata.get("name")
                    or ""
                )
            combined = f"{meta_label} {att.path or ''} {att.url or ''}"
            if any(term in combined for term in trigger_terms):
                return True
        return False

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
        """
        仅根据「本轮问题」判断是否属于补贴金额计算：
        - 需要在补贴/补助语境下；
        - 且当前问题里同时出现金额、具体产品和能效等级。
        上下文中的历史价格/产品不会触发计算路由，避免后续追问被误判为“再次计算”。
        """
        text = (query or "").strip()
        if not text:
            return False

        # 补贴/补助语境：问题本身或领域关键词中包含“补贴/补助”
        if "补贴" not in text and "补助" not in text:
            keywords = (domain_meta or {}).get("keywords") or []
            has_subsidy_kw = any("补贴" in str(kw) or "补助" in str(kw) for kw in keywords)
            if not has_subsidy_kw:
                return False

        has_price = bool(re.search(r"\d+(\.\d+)?\s*元", text))
        if not has_price:
            return False

        keywords = (domain_meta or {}).get("keywords") or []
        has_product = any(kw in text for kw in self.PRODUCT_KEYWORDS) or any(
            kw in keywords for kw in self.PRODUCT_KEYWORDS
        )
        if not has_product:
            return False

        has_energy = any(tag in text for tag in ["1级", "一级", "2级", "二级", "能效", "水效"])
        return has_energy

    def _looks_like_temporal_subsidy_eligibility(self, query: str) -> bool:
        """
        检测像“去年已享受，今年还能享受补贴吗？”这类带时间对比的资格问题，
        优先路由到 Graph（需要结合条款做推理）。
        """
        text = (query or "").strip()
        if not text:
            return False
        if "补贴" not in text and "补助" not in text:
            return False
        temporal_terms = ["去年", "上一年", "上一次", "2024", "今年", "2025"]
        if not any(t in text for t in temporal_terms):
            return False
        eligibility_terms = ["还能", "再次", "还可以", "还能享受", "还能领", "还能不能", "还可以享受"]
        return any(t in text for t in eligibility_terms)

    def _ensure_route_and_citations(self, final) -> None:
        citation_line = self._format_citation_block(final)

        blocks = []
        answer_text = final.answer or ""
        # 可选：将 Markdown 友好的内容转为纯文本，便于前端不做 markdown 渲染时展示
        if getattr(self.config, "answer_plain_output", False):
            answer_text = self._to_plain_text(answer_text)

        if citation_line:
            blocks.append(citation_line)
        if not blocks:
            return
        suffix = "\n" + "\n".join(blocks)
        if answer_text and not answer_text.endswith("\n"):
            final.answer = answer_text + "\n" + suffix.lstrip("\n")
        else:
            final.answer = answer_text + suffix

        # 末尾块也做一次 plain 化，保证引用/路由不带 markdown 列表符号
        if getattr(self.config, "answer_plain_output", False):
            final.answer = self._to_plain_text(final.answer)

    def _format_citation_block(self, final) -> Optional[str]:
        meta = final.metadata or {}
        meta_sources = meta.get("sources")
        # 如果元数据中已经提供了结构化引用（供前端展示），这里就不再追加文本版引用，避免重复
        if isinstance(meta_sources, list) and meta_sources:
            return None

        sources = getattr(final, "sources", None) or []
        if not sources and isinstance(meta_sources, list):
            sources = meta_sources
        lines: List[str] = []
        for doc in sources[:3]:
            title = getattr(doc, "title", None) or (doc.get("title") if isinstance(doc, dict) else None) or "未知来源"
            source = getattr(doc, "source", None) or (doc.get("origin") if isinstance(doc, dict) else None) or ""
            path = None
            if hasattr(doc, "metadata") and getattr(doc, "metadata", None):
                path = doc.metadata.get("path") or doc.metadata.get("origin")
            elif isinstance(doc, dict):
                path = doc.get("path") or doc.get("origin")
            ref = path or source or "内部知识库"
            lines.append(f"- {title}（{ref}）")
        if not lines:
            meta = final.metadata or {}
            if meta.get("rule_id"):
                # rule_engine 结果优先展示规则关联的政策标题
                engine_result = meta.get("engine_result") or {}
                policy_source = engine_result.get("policy_source") or {}
                policy_title = policy_source.get("title")
                if policy_title:
                    lines.append(f"- {policy_title}")
                else:
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

    def _to_plain_text(self, text: str) -> str:
        """Best-effort Markdown → plain-text转换，保持换行与要点顺序。"""
        if not text:
            return ""
        cleaned = text
        # 去掉代码块
        cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
        # 去掉行首标题符号
        cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
        # 列表符替换为中点
        cleaned = re.sub(r"^\s*[-*]\s+", "· ", cleaned, flags=re.MULTILINE)
        # 粗体/斜体/行内代码标记去壳
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
        cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
        # 多余空行压缩为单个空行
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    # ========== AgentChat 工具封装 ==========

    async def _tool_agentchat_knowledge(self, query: str) -> str:
        import time
        t0 = time.perf_counter()
        try:
            final = await self.knowledge_agent.answer(query)
            # 记录最近一次 AgentChat 调用中使用的文档，供 _finalize_answer 回收
            self._last_agentchat_sources = getattr(final, "sources", []) or []
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "knowledge_tool", "duration_ms": elapsed})
            return final.answer or ""
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "knowledge_tool", "duration_ms": elapsed, "error": str(exc)})
            logging_manager.warning("AgentChat knowledge tool failed: %s", exc)
            return "知识检索失败，请稍后重试。"

    async def _tool_agentchat_graph(self, query: str) -> str:
        import time
        t0 = time.perf_counter()
        try:
            final = await self.graph_agent.answer(query)
            self._last_agentchat_sources = getattr(final, "sources", []) or []
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "graph_tool", "duration_ms": elapsed})
            return final.answer or ""
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "graph_tool", "duration_ms": elapsed, "error": str(exc)})
            logging_manager.warning("AgentChat graph tool failed: %s", exc)
            return "图谱/关系推理失败，请稍后再试或提供更具体的比较问题。"

    async def _tool_agentchat_rule(self, query: str) -> str:
        import time
        t0 = time.perf_counter()
        try:
            if not self._looks_like_calculation(query):
                # 缺少金额/数字类关键词，直接改走知识库回答
                self._tool_metrics.append(
                    {"tool": "rule_tool", "duration_ms": 0.0, "note": "fallback_to_knowledge"}
                )
                kb_final = await self.knowledge_agent.answer(query)
                self._last_agentchat_sources = getattr(kb_final, "sources", []) or []
                return kb_final.answer or "为保证准确性，请提供补贴计算所需的价格/能效信息。"
            final = await self.rule_agent.compute(query, intent={"intent": "calculation"})
            self._last_agentchat_sources = getattr(final, "sources", []) or []
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "rule_tool", "duration_ms": elapsed})
            return final.answer or ""
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "rule_tool", "duration_ms": elapsed, "error": str(exc)})
            logging_manager.warning("AgentChat rule tool failed: %s", exc)
            return "规则计算失败，请提供更清晰的金额/能效信息。"

    async def _tool_agentchat_text2sql(self, query: str) -> str:
        import time
        t0 = time.perf_counter()
        try:
            conn_id = self._resolve_connection_id(None)
            final = await self.text2sql_agent.answer(query, connection_id=conn_id)
            self._last_agentchat_sources = getattr(final, "sources", []) or []
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "text2sql_tool", "duration_ms": elapsed})
            return final.answer or ""
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "text2sql_tool", "duration_ms": elapsed, "error": str(exc)})
            logging_manager.warning("AgentChat text2sql tool failed: %s", exc)
            return "数据库查询失败，请检查连接配置或问题是否包含表字段。"

    async def _tool_agentchat_workflow(self, query: str) -> str:
        import time
        t0 = time.perf_counter()
        try:
            final = await self.workflow_agent.answer(
                query,
                # AgentChat 工具目前只能接受文本参数，这里复用当前请求挂载的附件，
                # 以便在“上传发票/图片”场景下，workflow_tool 能够真正看到附件内容。
                attachments=getattr(self, "_agentchat_attachments", []) or [],
                intent={"intent": "workflow"},
            )
            self._last_agentchat_sources = getattr(final, "sources", []) or []
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "workflow_tool", "duration_ms": elapsed})
            return final.answer or ""
        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            self._tool_metrics.append({"tool": "workflow_tool", "duration_ms": elapsed, "error": str(exc)})
            logging_manager.warning("AgentChat workflow tool failed: %s", exc)
            return "多模态/协作流程执行失败，请重试。"

    async def _finalize_answer(
        self,
        *,
        final,
        route: str,
        intent_result: Dict[str, Any],
        rewritten_query: str,
        session_id: str,
        user_id: Optional[str],
        connection_id: Optional[int],
        conversation_context: Dict[str, Any],
        domain_context,
        attachments: List[Attachment],
        trace: _PerfTrace,
        start_time: float,
        agentchat_meta: Optional[Dict[str, Any]] = None,
    ):
        session_store.add_answer(session_id, final)
        # 同步写入 AutoGen Memory
        if session_id:
            try:
                await autogen_memory_store.add_assistant_message(session_id, final.answer)
            except Exception:
                logging_manager.warning("AutoGen memory 记录助手回答失败", exc_info=True)

        metadata = final.metadata or {}
        base_route = (route or "").split("+")[0] if route else None
        metadata.update(
            {
                "route": route,
                "route_chain": [
                    {"key": seg, "label": self.ROUTE_LABELS.get(seg, seg)}
                    for seg in (route.split("+") if route else [])
                ],
                "intent": intent_result,
                "routing_debug": getattr(self, "_routing_debug", []),
                "agentchat_meta": agentchat_meta if agentchat_meta else None,
                "agentchat_flags": {
                    "team_enabled": self._agentchat_team_enabled,
                    "router_enabled": self._agentchat_enabled,
                    "memory_key": session_id,
                },
                "rewritten_query": rewritten_query,
                "session_id": session_id,
                "user_id": user_id,
                "connection_id": connection_id,
                "conversation_context": conversation_context,
                "domain_context": domain_context.to_metadata()
                if hasattr(domain_context, "to_metadata")
                else None,
            }
        )
        if agentchat_meta:
            # 附加工具级耗时
            if getattr(self, "_tool_metrics", None):
                agentchat_meta["tool_metrics"] = getattr(self, "_tool_metrics")
            metadata["agentchat_meta"] = agentchat_meta
        if attachments:
            metadata.setdefault("attachments", [att.model_dump() for att in attachments])

        # 轻量化引用源，供前端展示参考文件
        sources = []
        for doc in (getattr(final, "sources", None) or [])[:5]:
            meta = getattr(doc, "metadata", {}) or {}
            sources.append(
                {
                    "title": getattr(doc, "title", None) or meta.get("title") or "未命名来源",
                    "path": meta.get("path") or meta.get("origin") or "",
                    "origin": getattr(doc, "source", None) or meta.get("source") or "",
                    "chunk_idx": meta.get("chunk_idx"),
                }
            )
        # 如果 AgentChat 最终结果没有自带 sources，尝试回收最近一次工具调用中的文档
        if not sources:
            fallback_sources = getattr(self, "_last_agentchat_sources", []) or []
            for doc in fallback_sources[:5]:
                meta = getattr(doc, "metadata", {}) or {}
                sources.append(
                    {
                        "title": getattr(doc, "title", None) or meta.get("title") or "未命名来源",
                        "path": meta.get("path") or meta.get("origin") or "",
                        "origin": getattr(doc, "source", None) or meta.get("source") or "",
                        "chunk_idx": meta.get("chunk_idx"),
                    }
                )
        if sources:
            # 去重：按 (title, origin, path) 维度
            unique = []
            seen = set()
            for s in sources:
                key = (
                    s.get("title") or "",
                    s.get("origin") or "",
                    s.get("path") or "",
                )
                if key in seen:
                    continue
                seen.add(key)
                unique.append(s)
            metadata["sources"] = unique[:5]

        # 轻量化工具轨迹（高层能力说明）
        tools_used: list[str] = []
        meta_block = metadata.get("agentchat_meta") or {}

        def _add(label: str) -> None:
            if label and label not in tools_used:
                tools_used.append(label)

        # 1) 优先根据 AgentChat 选择的 primary_tool 判断
        primary_tool = (
            metadata.get("agentchat_tool")
            or metadata.get("primary_tool")
            or (meta_block.get("primary_tool") if isinstance(meta_block, dict) else None)
        )
        if isinstance(primary_tool, str):
            key = primary_tool.lower()
            if "knowledge" in key:
                _add("知识库检索")
            elif "graph" in key:
                _add("知识图谱推理")
            elif "rule" in key:
                _add("规则计算")
            elif "text2sql" in key or "sql" in key:
                _add("Text2SQL 查询")
            elif "workflow" in key:
                _add("多模态工作流")

        # 1.5) 结合工具耗时记录（tool_metrics）进一步还原能力类型
        tool_metrics = meta_block.get("tool_metrics") if isinstance(meta_block, dict) else None
        if isinstance(tool_metrics, list):
            for item in tool_metrics:
                tool_key = (item or {}).get("tool", "")
                key = str(tool_key).lower()
                if "knowledge_tool" in key:
                    _add("知识库检索")
                elif "graph_tool" in key:
                    _add("知识图谱推理")
                elif "rule_tool" in key:
                    _add("规则计算")
                elif "text2sql_tool" in key:
                    _add("Text2SQL 查询")
                elif "workflow_tool" in key:
                    _add("多模态工作流")

        # 2) 结合路由链补全（非 AgentChat 主路径时更明确）
        route_text = route or ""
        if "knowledge" in route_text:
            _add("知识库检索")
        if "graph" in route_text:
            _add("知识图谱推理")
        if "rule_engine" in route_text:
            _add("规则计算")
        if "text2sql" in route_text:
            _add("Text2SQL 查询")
        if "workflow" in route_text:
            _add("多模态工作流")

        # 3) 若只看到 AgentChat，而没有具体能力，标明协作式推理
        if (self._agentchat_team_enabled or self._agentchat_enabled) and "agentchat" in route_text and not tools_used:
            _add("AgentChat 协作")

        # 4) 兜底：至少说明是对话生成
        if not tools_used:
            _add("对话生成")

        metadata["tools_used"] = tools_used
        # 基于工具推导人类可读的主路由标签
        if tools_used:
            metadata["route_display"] = " + ".join(tools_used)
        else:
            metadata["route_display"] = self.ROUTE_LABELS.get(base_route or route, base_route or route)

        timing = trace.summary() if trace else {}
        if timing:
            metadata["timings_ms"] = timing

        final.metadata = metadata
        final.total_processing_time = time.perf_counter() - start_time
        self._ensure_route_and_citations(final)

        if timing and timing.get("total_ms", 0) >= trace.slow_threshold_ms:
            logging_manager.info(
                "[AgentService] 慢请求 %.1f ms route=%s stages=%s",
                timing["total_ms"],
                route,
                timing.get("stages"),
            )
        elif timing and getattr(self, "_log_timing_breakdown", False):
            logging_manager.info(
                "[AgentService] 请求耗时 %.1f ms route=%s stages=%s",
                timing["total_ms"],
                route,
                timing.get("stages"),
            )

        return final

    async def process_query_stream(
        self,
        query: str,
        *,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        connection_id: Optional[int] = None,
        attachments: Optional[List[Attachment]] = None,
        force_text2sql: bool = False,
    ):
        """
        Streamed processing via AgentChat Team/Router when enabled.
        Yields dicts: {"type": "chunk", "content": "..."} or {"type": "final", "answer": FinalAnswer, "meta": {...}}.
        """
        attachments = attachments or []
        # 结合会话级缓存解析附件：支持“根据上传的发票/截图/附件”等后续追问重用上一轮附件
        attachments = self._resolve_session_attachments(session_id, query, attachments)
        # 记录当前请求的附件，供 AgentChat workflow_tool 等内部工具使用
        self._agentchat_attachments = attachments
        # 有明显“发票/票据/图片/附件”且需要解析的多模态问题，直接复用非流式主流程，
        # 由 WorkflowAgent 统一处理（包括视觉解析 + 规则计算），再通过 SSE 一次性推送，
        # 前端仍然会用吐字效果渲染整段内容。
        if self._looks_like_multimodal_invoice_question(
            original_query=query,
            rewritten_query=query,
            attachments=attachments,
        ):
            final = await self.process_query(
                query,
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id,
                attachments=attachments,
                force_text2sql=force_text2sql,
            )
            yield {"type": "final", "answer": final, "meta": final.metadata or {}}
            return

        # 如果未开启 AgentChat 流式，直接走普通处理
        if not (getattr(self, "_agentchat_team_enabled", False) or getattr(self, "_agentchat_enabled", False)):
            final = await self.process_query(
                query,
                session_id=session_id,
                user_id=user_id,
                connection_id=connection_id,
                attachments=attachments,
                force_text2sql=force_text2sql,
            )
            yield {"type": "final", "answer": final, "meta": final.metadata or {}}
            return

        sid = session_id or "stream_default"
        # 记录用户消息到 memory，保持与常规路径一致
        await autogen_memory_store.add_user_message(sid, query)

        async def _enrich_and_yield(stream):
            async for evt in stream:
                if evt.get("type") == "final":
                    final = evt.get("answer")
                    meta = evt.get("meta") or {}
                    if final is not None:
                        # 合并 agentchat 元信息
                        if isinstance(final.metadata, dict):
                            merged = dict(final.metadata)
                            if isinstance(meta, dict):
                                merged.setdefault("agentchat_meta", meta)
                            final.metadata = merged
                        else:
                            final.metadata = meta if isinstance(meta, dict) else {}

                        # 复用 _finalize_answer 中的轻量元数据填充逻辑（sources / tools_used / route_display）
                        # 这里不重复写入会话与耗时，只做展示相关的信息补全
                        metadata = final.metadata or {}
                        route = metadata.get("route") or meta.get("route")
                        base_route = (route or "").split("+")[0] if route else None

                        # 引用文档回收（包括 AgentChat 工具调用中的文档）
                        sources = []
                        for doc in (getattr(final, "sources", None) or [])[:5]:
                            doc_meta = getattr(doc, "metadata", {}) or {}
                            sources.append(
                                {
                                    "title": getattr(doc, "title", None) or doc_meta.get("title") or "未命名来源",
                                    "path": doc_meta.get("path") or doc_meta.get("origin") or "",
                                    "origin": getattr(doc, "source", None) or doc_meta.get("source") or "",
                                    "chunk_idx": doc_meta.get("chunk_idx"),
                                }
                            )
                        if not sources:
                            fallback_sources = getattr(self, "_last_agentchat_sources", []) or []
                            for doc in fallback_sources[:5]:
                                doc_meta = getattr(doc, "metadata", {}) or {}
                                sources.append(
                                    {
                                        "title": getattr(doc, "title", None) or doc_meta.get("title") or "未命名来源",
                                        "path": doc_meta.get("path") or doc_meta.get("origin") or "",
                                        "origin": getattr(doc, "source", None) or doc_meta.get("source") or "",
                                        "chunk_idx": doc_meta.get("chunk_idx"),
                                    }
                                )
                        if sources:
                            unique = []
                            seen = set()
                            for s in sources:
                                key = (
                                    s.get("title") or "",
                                    s.get("origin") or "",
                                    s.get("path") or "",
                                )
                                if key in seen:
                                    continue
                                seen.add(key)
                                unique.append(s)
                            metadata["sources"] = unique[:5]

                        # 高层工具说明
                        tools_used: list[str] = []
                        meta_block = metadata.get("agentchat_meta") or {}

                        def _add(label: str) -> None:
                            if label and label not in tools_used:
                                tools_used.append(label)

                        primary_tool = (
                            metadata.get("agentchat_tool")
                            or metadata.get("primary_tool")
                            or (meta_block.get("primary_tool") if isinstance(meta_block, dict) else None)
                        )
                        if isinstance(primary_tool, str):
                            key = primary_tool.lower()
                            if "knowledge" in key:
                                _add("知识库检索")
                            elif "graph" in key:
                                _add("知识图谱推理")
                            elif "rule" in key:
                                _add("规则计算")
                            elif "text2sql" in key or "sql" in key:
                                _add("Text2SQL 查询")
                            elif "workflow" in key:
                                _add("多模态工作流")

                        route_text = route or ""
                        if "knowledge" in route_text:
                            _add("知识库检索")
                        if "graph" in route_text:
                            _add("知识图谱推理")
                        if "rule_engine" in route_text:
                            _add("规则计算")
                        if "text2sql" in route_text:
                            _add("Text2SQL 查询")
                        if "workflow" in route_text:
                            _add("多模态工作流")

                        if (self._agentchat_team_enabled or self._agentchat_enabled) and "agentchat" in route_text and not tools_used:
                            _add("AgentChat 协作")
                        if not tools_used:
                            _add("对话生成")

                        metadata["tools_used"] = tools_used
                        # 使用工具信息推导友好路由标签，供前端展示
                        metadata["route_display"] = " + ".join(tools_used) if tools_used else self.ROUTE_LABELS.get(
                            base_route or route, base_route or route
                        )

                        final.metadata = metadata
                        evt["answer"] = final
                        evt["meta"] = metadata

                yield evt

        if getattr(self, "_agentchat_team_enabled", False):
            async for evt in _enrich_and_yield(self._agentchat_team.run_stream(sid, query)):
                yield evt
            return

        if getattr(self, "_agentchat_enabled", False):
            async for evt in _enrich_and_yield(self._agentchat_router.run_stream(sid, query)):
                yield evt
            return


__all__ = ["AgentService"]
