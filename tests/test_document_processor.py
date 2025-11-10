#!/usr/bin/env python3
"""
测试增强文档处理器
"""

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.knowledge.doc_enhanced import EnhancedDocumentProcessor
from app.knowledge.mineru_adapter import MinerUAdapter
from app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_processor():
    """测试文档处理器"""
    print("\n=== 测试增强文档处理器 ===\n")

    # 初始化处理器
    config = {
        "mineru_enabled": True,
        "mineru_base_url": settings.model.mineru_base_url,
        "mineru_api_key": settings.model.mineru_api_key,
        "docling_enabled": True,
        "llamaindex_enabled": True,
        "ocr_enabled": True,
        "table_extraction": True,
        "image_extraction": True
    }

    processor = EnhancedDocumentProcessor(config)

    # 测试引擎
    print("\n1. 测试引擎可用性:")
    engines = processor.test_engines()
    for engine, available in engines.items():
        status = "✓ 可用" if available else "✗ 不可用"
        print(f"   - {engine}: {status}")

    # 测试MinerU适配器
    print("\n2. 测试MinerU连接:")
    async with MinerUAdapter() as mineru:
        is_healthy = await mineru.health_check()
        print(f"   - MinerU服务: {'✓ 正常' if is_healthy else '✗ 无法连接'}")

    # 测试支持的格式
    print("\n3. 支持的文件格式:")
    formats = processor.get_supported_formats()
    print(f"   - 支持格式: {', '.join(formats)}")

    # 测试文档提取（如果有测试文件）
    test_dir = Path("resources/data/test")
    if test_dir.exists():
        print("\n4. 测试文档提取:")
        for file_path in test_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in formats:
                print(f"\n   测试文件: {file_path.name}")
                try:
                    # 提取文本
                    text = await processor.extract_text(file_path)
                    print(f"   - 提取方法: {processor._get_extraction_method(file_path.suffix.lower())}")
                    print(f"   - 文本长度: {len(text) if text else 0}")

                    # 提取元数据
                    metadata = await processor.extract_with_metadata(file_path)
                    print(f"   - 文件大小: {metadata.get('file_size', 0)} bytes")
                    print(f"   - 提取时间: {metadata.get('extracted_at', 'N/A')}")

                    # 显示文本预览
                    if text:
                        preview = text[:200].replace('\n', ' ')
                        print(f"   - 文本预览: {preview}...")

                except Exception as e:
                    print(f"   ✗ 错误: {e}")

    print("\n✅ 测试完成!\n")


async def test_mineru_batch():
    """测试MinerU批量处理"""
    print("\n=== 测试MinerU批量处理 ===\n")

    test_dir = Path("resources/data/test")
    pdf_files = list(test_dir.rglob("*.pdf"))

    if not pdf_files:
        print("没有找到测试PDF文件")
        return

    # 只处理前3个文件
    pdf_files = pdf_files[:3]

    async with MinerUAdapter() as mineru:
        print(f"\n批量处理 {len(pdf_files)} 个PDF文件...")

        # 配置选项
        options = {
            "ocr_all_images": True,
            "extract_tables": True,
            "extract_images": True,
            "output_format": "markdown",
            "include_raw_ocr": True
        }

        # 批量提取
        results = await mineru.batch_extract(
            [str(f) for f in pdf_files],
            options=options,
            max_concurrent=2
        )

        # 显示结果
        for i, result in enumerate(results):
            file_name = pdf_files[i].name
            if result.get("success"):
                stats = mineru.get_extraction_stats(result)
                print(f"\n✓ {file_name}:")
                print(f"  - 文本长度: {stats['text_length']}")
                print(f"  - 页数: {stats['pages_processed']}")
                print(f"  - 包含表格: {'是' if stats['has_tables'] else '否'}")
                print(f"  - 包含图片: {'是' if stats['has_images'] else '否'}")
                print(f"  - OCR执行: {'是' if stats['ocr_performed'] else '否'}")
            else:
                print(f"\n✗ {file_name}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    # 创建测试目录
    test_dir = Path("resources/data/test")
    test_dir.mkdir(parents=True, exist_ok=True)

    print("请将测试文件放在 data/test/ 目录下")
    print("支持格式: PDF, DOCX, TXT, MD")

    # 运行测试
    asyncio.run(test_processor())
    asyncio.run(test_mineru_batch())