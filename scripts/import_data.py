#!/usr/bin/env python3
"""Prepare synthetic policy fixtures and index them with configured embeddings.

Run as python -m scripts.import_data. MySQL schema initialization and LightRAG
seed-file preparation are separate from importing SQL rows or building a graph.
"""

import asyncio
import json
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
        self.project_root = Path(__file__).resolve().parents[1] if project_root is None else Path(project_root)
        self.data_dir = self.project_root / "resources" / "data"

    async def _run_command(
        self, command: list[str], *, input: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Own the subprocess until completion, timeout, or cancelled cleanup."""
        process = await asyncio.create_subprocess_exec(
            *command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            cwd=self.project_root,
        )
        try:
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(None if input is None else input.encode('utf-8')), timeout=120,
                )
            except asyncio.TimeoutError as exc:
                raise subprocess.TimeoutExpired(command, 120) from exc
            output, errors = stdout.decode('utf-8'), stderr.decode('utf-8')
            returncode = process.returncode
            if returncode is None:
                raise RuntimeError('Subprocess completed without an exit status')
            if returncode != 0:
                raise subprocess.CalledProcessError(returncode, command, output=output, stderr=errors)
            return subprocess.CompletedProcess(command, returncode, output, errors)
        finally:
            if process.returncode is None:
                process.kill()
                with anyio.fail_after(5, shield=True):
                    await process.communicate()

    @staticmethod
    def _mysql_command(*args: str) -> list[str]:
        return [
            "docker", "exec", "-i", "-e", "MYSQL_PWD",
            os.getenv("MYSQL_CONTAINER", "glyph_mysql_1"), "mysql", "-uroot",
            "--default-character-set=utf8mb4", *args,
        ]

    async def init_mysql(self) -> None:
        """Initialize schema without claiming that sample SQL rows were imported."""
        from scripts.seed_mysql_text2sql import mysql_schema_statements

        mysql_env = {**os.environ, "MYSQL_PWD": os.environ["MYSQL_ROOT_PASSWORD"]}
        await self._run_command(self._mysql_command(
            "-e", "CREATE DATABASE IF NOT EXISTS policy_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        ), env=mysql_env)
        schema_file = self.project_root / "resources/database/schema/policy_qa_schema.sql"
        statements = await anyio.to_thread.run_sync(mysql_schema_statements, schema_file)
        await self._run_command(
            self._mysql_command("policy_db"), input=";\n".join(statements) + ";", env=mysql_env,
        )
        logger.info("MySQL policy_db schema initialized")

    @staticmethod
    def _milvus_stats() -> dict[str, Any]:
        from app.knowledge.milvus import MilvusStore

        store = MilvusStore()
        try:
            return store.get_stats()
        finally:
            store.close()

    async def init_milvus(self) -> None:
        """Ensure the configured collection exists; preserve its current records."""
        stats = await anyio.to_thread.run_sync(self._milvus_stats)
        logger.info("Milvus collection %s ready: %s records, dimension %s",
                    stats["collection_name"], stats["total_documents"], stats["dim"])

    async def write_sample_policies(self) -> None:
        """Write explicitly synthetic sample policies to the local fixture file."""
        logger.info("写入合成政策样例文件...")

        # 创建示例数据
        sample_policies = [
            {
                "doc_id": "policy_001",
                "title": "深圳市小微企业创业补贴政策",
                "category": "创业扶持",
                "content": """
深圳市为支持小微企业发展，推出以下创业补贴政策：

一、创业场地补贴
- 对符合条件的初创企业，给予每月500-2000元的场地租金补贴
- 补贴期限最长3年

二、创业带动就业补贴
- 每招用1名员工并缴纳社保6个月以上，补贴2000元
- 最高补贴不超过10万元

三、创业孵化补贴
- 入驻政府认定的创业孵化基地，享受首年免租金
- 第二年租金减半

申请条件：
1. 深圳户籍人员或毕业5年内的大学生
2. 企业成立时间不超过3年
3. 正常经营并缴纳社保
                """,
                "region": "深圳市",
                "effective_date": "2024-01-01",
                "expiry_date": "2026-12-31"
            },
            {
                "doc_id": "policy_002",
                "title": "高新技术企业税收优惠政策",
                "category": "税收优惠",
                "content": """
国家高新技术企业所得税优惠政策：

一、税率优惠
- 企业所得税减按15%税率征收
（一般企业所得税税率为25%）

二、研发费用加计扣除
- 研发费用按100%加计扣除
- 形成无形资产的按200%摊销

三、技术转让所得减免
- 年度技术转让所得不超过500万元的部分，免征企业所得税
- 超过500万元的部分，减半征收企业所得税

申请条件：
1. 拥有核心自主知识产权
2. 产品属于《国家重点支持的高新技术领域》
3. 研发费用占比符合要求
4. 高新技术产品收入占总收入60%以上
                """,
                "region": "全国",
                "effective_date": "2024-01-01",
                "expiry_date": "2025-12-31"
            },
            {
                "doc_id": "policy_003",
                "title": "软件产品增值税即征即退政策",
                "category": "税收优惠",
                "content": """
软件产品增值税即征即退政策：

一、政策内容
- 对销售自行开发生产的软件产品，按17%税率征收增值税后
- 对实际税负超过3%的部分实行即征即退

二、享受条件
1. 取得软件产品登记证书
2. 软件产品拥有自主知识产权
3. 销售自行开发的软件产品

三、计算方法
- 即征即退税额 = 当期软件产品增值税应纳税额 - 软件产品销售额×3%
- 实际税负 = 当期软件产品增值税应纳税额÷当期软件产品销售额×100%

四、申请流程
1. 在电子税务局提出申请
2. 提交软件产品证书等材料
3. 税务机关审核批准
                """,
                "region": "全国",
                "effective_date": "2024-01-01",
                "expiry_date": "2025-12-31"
            }
        ]

        # 保存示例数据
        for policy in sample_policies:
            policy["title"] = "【合成示例】" + policy["title"]
        sample_data_file = self.data_dir / "sample_policies.json"
        await asyncio.to_thread(sample_data_file.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(sample_data_file.write_text, json.dumps(sample_policies, ensure_ascii=False, indent=2), encoding='utf-8')

        logger.info(f"✅ 示例数据已保存到: {sample_data_file}")

    async def prepare_lightrag_documents(self) -> None:
        """Prepare Markdown seed files; graph indexing is a separate command."""
        logger.info("🔗 准备LightRAG数据...")

        lightrag_dir = self.data_dir / "lightrag"
        await asyncio.to_thread(lightrag_dir.mkdir, parents=True, exist_ok=True)

        # 创建示例文档
        sample_docs = [
            {
                "filename": "shenzhen_startup_subsidy.md",
                "content": """# 深圳市小微企业创业补贴政策

## 政策概述
深圳市为支持小微企业发展，推出创业补贴政策。

## 补贴内容
1. 创业场地补贴：每月500-2000元
2. 创业带动就业补贴：每招用1名员工补贴2000元
3. 创业孵化补贴：首年免租金

## 申请条件
- 深圳户籍或毕业5年内大学生
- 企业成立不超过3年
- 正常经营并缴纳社保

## 申请流程
1. 在线申请
2. 提交材料
3. 审核
4. 公示
5. 发放补贴
"""
            },
            {
                "filename": "high_tech_tax_policy.md",
                "content": """# 高新技术企业税收优惠政策

## 税率优惠
企业所得税减按15%征收（原税率25%）。

## 研发费用加计扣除
- 未形成无形资产：按100%加计扣除
- 形成无形资产：按200%摊销

## 技术转让所得优惠
- 500万元以内：免征
- 超过500万元：减半征收

## 申请条件
1. 拥有核心自主知识产权
2. 属于高新技术领域
3. 研发费用占比达标
4. 高新产品收入占比60%以上
"""
            }
        ]

        # 保存文档
        for doc in sample_docs:
            file_path = lightrag_dir / doc["filename"]
            content = "> 合成政策示例，仅供功能演示，不代表现行政策。\n\n" + doc["content"]
            await asyncio.to_thread(file_path.write_text, content, encoding='utf-8')

        logger.info(f"✅ 已保存 {len(sample_docs)} 个文档到LightRAG目录")

    @staticmethod
    def _index_sample_policies(sample_file: Path) -> int:
        from uuid import NAMESPACE_URL, uuid5

        from app.knowledge.milvus import MilvusStore
        from app.models.policy import PolicyDocument, PolicyType

        policies = json.loads(sample_file.read_text(encoding="utf-8"))
        if not isinstance(policies, list):
            raise ValueError("Sample policies must be a list")
        documents = [
            PolicyDocument(
                id=uuid5(NAMESPACE_URL, f"glyph:sample-policy:{policy['doc_id']}"),
                title=policy["title"], content=policy["content"],
                source="合成政策样例", doc_type=PolicyType.GUIDELINE,
                effective_date=policy["effective_date"], expiry_date=policy["expiry_date"],
                metadata={"synthetic": True, "sample_doc_id": policy["doc_id"],
                          "category": policy["category"], "region": policy["region"]},
            )
            for policy in policies
        ]
        store = MilvusStore()
        try:
            store.add_documents(documents, upsert=True)
        finally:
            store.close()
        return len(documents)

    async def import_embeddings(self) -> None:
        """Use the configured real embedding backend and stable sample IDs."""
        count = await anyio.to_thread.run_sync(
            self._index_sample_policies, self.data_dir / "sample_policies.json",
        )
        logger.info("Indexed %s synthetic sample policies with configured embeddings", count)

    async def verify_import(self) -> None:
        """Report actual connectivity, collection count, and prepared seed files."""
        mysql_env = {**os.environ, "MYSQL_PWD": os.environ["MYSQL_ROOT_PASSWORD"]}
        result = await self._run_command(
            self._mysql_command("-e", "USE policy_db; SHOW TABLES;"), env=mysql_env,
        )
        logger.info("MySQL tables: %s", result.stdout.splitlines()[1:])
        stats = await anyio.to_thread.run_sync(self._milvus_stats)
        logger.info("Milvus collection %s contains %s records",
                    stats["collection_name"], stats["total_documents"])
        lightrag_dir = self.data_dir / "lightrag"
        doc_count = await anyio.to_thread.run_sync(lambda: len(list(lightrag_dir.glob("*.md"))))
        logger.info("Prepared LightRAG seed documents: %s", doc_count)

    async def run(self) -> None:
        logger.info("Starting sample data setup at %s", datetime.now().isoformat())
        await self.init_mysql()
        await self.init_milvus()
        await self.write_sample_policies()
        await self.prepare_lightrag_documents()
        await self.import_embeddings()
        await self.verify_import()
        logger.info("MySQL schema, synthetic fixtures, and Milvus ingestion completed")
        logger.info("LightRAG graph indexing remains separate: python -m scripts.seed_lightrag --input-dir %s",
                    self.data_dir / "lightrag")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(DataImporter().run())
