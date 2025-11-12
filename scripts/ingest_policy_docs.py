#!/usr/bin/env python3
"""
导入政策文档到向量数据库和LightRAG
"""

import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.agents.service.agent_service import AgentService


async def ingest_documents():
    """导入文档"""
    print("开始导入政策文档...")

    service = AgentService()
    await service.initialize()

    # 导入的目录
    paths = [
        "resources/data/process/md2025年家电和数码以旧换新政策文件",
        "resources/data/process/md市级消费活动政策"
    ]

    for path in paths:
        print(f"\n导入目录: {path}")
        result = await service.ingest_paths([path])
        print(f"结果: {result}")

    print("\n✅ 文档导入完成！")


if __name__ == "__main__":
    asyncio.run(ingest_documents())