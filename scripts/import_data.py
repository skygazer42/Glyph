#!/usr/bin/env python3
"""Import accepted official Changzhou policies with configured embeddings.

Run as python -m scripts.import_data. MySQL schema initialization and LightRAG
seed-file preparation are separate from importing SQL rows or building a graph.
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio

logger = logging.getLogger(__name__)


class DataImporter:
    """Own sample-file paths, MySQL setup, and configured Milvus ingestion."""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = (
            Path(__file__).resolve().parents[1]
            if project_root is None
            else Path(project_root)
        )
        self.data_dir = self.project_root / "resources" / "data"

    async def _run_command(
        self,
        command: list[str],
        *,
        input: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Own the subprocess until completion, timeout, or cancelled cleanup."""
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.project_root,
        )
        try:
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(
                        None if input is None else input.encode("utf-8")
                    ),
                    timeout=120,
                )
            except asyncio.TimeoutError as exc:
                raise subprocess.TimeoutExpired(command, 120) from exc
            output, errors = stdout.decode("utf-8"), stderr.decode("utf-8")
            returncode = process.returncode
            if returncode is None:
                raise RuntimeError("Subprocess completed without an exit status")
            if returncode != 0:
                raise subprocess.CalledProcessError(
                    returncode, command, output=output, stderr=errors
                )
            return subprocess.CompletedProcess(command, returncode, output, errors)
        finally:
            if process.returncode is None:
                process.kill()
                with anyio.fail_after(5, shield=True):
                    await process.communicate()

    @staticmethod
    def _mysql_command(*args: str) -> list[str]:
        """构造容器内 MySQL 命令；密码通过子进程环境传入，不拼入命令参数。"""
        return [
            "docker",
            "exec",
            "-i",
            "-e",
            "MYSQL_PWD",
            os.getenv("MYSQL_CONTAINER", "glyph_mysql_1"),
            "mysql",
            "-uroot",
            "--default-character-set=utf8mb4",
            *args,
        ]

    async def init_mysql(self) -> None:
        """Initialize schema without claiming that sample SQL rows were imported."""
        from scripts.seed_mysql_text2sql import mysql_schema_statements

        mysql_env = {**os.environ, "MYSQL_PWD": os.environ["MYSQL_ROOT_PASSWORD"]}
        await self._run_command(
            self._mysql_command(
                "-e",
                "CREATE DATABASE IF NOT EXISTS policy_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            ),
            env=mysql_env,
        )
        schema_file = (
            self.project_root / "resources/database/schema/policy_qa_schema.sql"
        )
        statements = await anyio.to_thread.run_sync(
            mysql_schema_statements, schema_file
        )
        await self._run_command(
            self._mysql_command("policy_db"),
            input=";\n".join(statements) + ";",
            env=mysql_env,
        )
        logger.info("MySQL policy_db schema initialized")

    @staticmethod
    def _milvus_stats() -> dict[str, Any]:
        """读取真实集合统计，并在返回或失败前关闭本次创建的存储客户端。"""
        from app.knowledge.milvus import MilvusStore

        store = MilvusStore()
        try:
            return store.get_stats()
        finally:
            store.close()

    async def init_milvus(self) -> None:
        """Ensure the configured collection exists; preserve its current records."""
        stats = await anyio.to_thread.run_sync(self._milvus_stats)
        logger.info(
            "Milvus collection %s ready: %s records, dimension %s",
            stats["collection_name"],
            stats["total_documents"],
            stats["dim"],
        )

    async def import_embeddings(self) -> None:
        """校验官方目录并导入真实正文、向量和可追溯问答，不再生成合成政策。"""
        from scripts.import_changzhou_policies import main as import_official_policies

        await asyncio.to_thread(import_official_policies, self.project_root)

    async def verify_import(self) -> None:
        """Report actual connectivity, collection count, and prepared seed files."""
        mysql_env = {**os.environ, "MYSQL_PWD": os.environ["MYSQL_ROOT_PASSWORD"]}
        result = await self._run_command(
            self._mysql_command("-e", "USE policy_db; SHOW TABLES;"),
            env=mysql_env,
        )
        logger.info("MySQL tables: %s", result.stdout.splitlines()[1:])
        stats = await anyio.to_thread.run_sync(self._milvus_stats)
        logger.info(
            "Milvus collection %s contains %s records",
            stats["collection_name"],
            stats["total_documents"],
        )
        lightrag_dir = self.data_dir / "lightrag"
        doc_count = await anyio.to_thread.run_sync(
            lambda: len(list(lightrag_dir.glob("*.md")))
        )
        logger.info("Prepared LightRAG seed documents: %s", doc_count)

    async def run(self) -> None:
        """导入已核验官方资料；SQL表结构和图谱构建使用各自显式命令。"""
        logger.info("Starting official policy import at %s", datetime.now().isoformat())
        await self.import_embeddings()
        logger.info("Official source/vector/FAQ import verified")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(DataImporter().run())
