#!/usr/bin/env python3
"""
数据初始化脚本 - 初始化gove系统的知识库
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_base.data_loader import DataLoader


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting data initialization...")

    # 创建数据加载器
    loader = DataLoader(
        raw_data_dir="data/raw",
        processed_data_dir="data/processed",
        vector_store_path="knowledge_base/vector_store"
    )

    try:
        # 加载文档并初始化向量存储
        documents = await loader.load_and_initialize(force_reload=True)

        if documents:
            logger.info(f"Successfully initialized with {len(documents)} documents")

            # 打印文档统计
            doc_types = {}
            for doc in documents:
                doc_type = doc.doc_type.value
                doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

            logger.info("Document types distribution:")
            for doc_type, count in doc_types.items():
                logger.info(f"  {doc_type}: {count}")
        else:
            logger.error("No documents were loaded!")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during initialization: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())