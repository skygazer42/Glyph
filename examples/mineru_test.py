#!/usr/bin/env python3
"""
MinerU 适配器测试脚本
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_base.mineru_adapter import MinerUAdapter


async def test_health_check():
    """测试健康检查"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)

    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        health = await adapter.health_check()

        print(f"\n状态: {health['status']}")
        print(f"消息: {health['message']}")
        print(f"详情: {health['details']}")

        return health["status"] == "healthy"


async def test_single_document():
    """测试单个文档提取"""
    print("\n" + "=" * 60)
    print("测试 2: 单个文档提取")
    print("=" * 60)

    # 查找测试文件
    data_dir = Path("/data/temp33/gov/data/process")
    pdf_files = list(data_dir.glob("**/*.pdf"))

    if not pdf_files:
        print("❌ 未找到测试 PDF 文件")
        return False

    test_file = pdf_files[0]
    print(f"\n测试文件: {test_file.name}")

    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        result = await adapter.extract_document(
            file_path=str(test_file),
            options={
                "is_ocr": True,
                "enable_formula": True,
                "enable_table": True,
                "language": "ch"
            }
        )

        if result["success"]:
            print(f"\n✓ 提取成功!")
            print(f"  - 内容长度: {len(result['content'])} 字符")
            print(f"  - 处理时间: {result['processing_time']:.2f}s")
            print(f"  - 模式: {adapter.mode}")

            # 显示前 200 字符
            preview = result["content"][:200].replace("\n", " ")
            print(f"  - 内容预览: {preview}...")

            # 获取统计信息
            stats = adapter.get_extraction_stats(result)
            print(f"\n统计信息:")
            for key, value in stats.items():
                print(f"  - {key}: {value}")

            return True
        else:
            print(f"\n❌ 提取失败: {result['error']}")
            return False


async def test_batch_processing():
    """测试批量处理"""
    print("\n" + "=" * 60)
    print("测试 3: 批量处理")
    print("=" * 60)

    # 查找测试文件
    data_dir = Path("/data/temp33/gov/data/process")
    pdf_files = list(data_dir.glob("**/*.pdf"))[:3]  # 只测试前 3 个

    if len(pdf_files) < 2:
        print("⚠️  测试文件不足 2 个，跳过批量测试")
        return True

    print(f"\n找到 {len(pdf_files)} 个测试文件")

    adapter = MinerUAdapter(mode="auto")

    async with adapter:
        results = await adapter.batch_extract(
            file_paths=[str(f) for f in pdf_files],
            options={"is_ocr": True},
            max_concurrent=2
        )

        success_count = sum(1 for r in results if r["success"])
        total_chars = sum(len(r.get("content", "")) for r in results if r["success"])

        print(f"\n批量处理结果:")
        print(f"  - 成功: {success_count}/{len(results)}")
        print(f"  - 总字符数: {total_chars:,}")

        for i, result in enumerate(results):
            if result["success"]:
                filename = result["metadata"]["file_name"]
                chars = len(result["content"])
                time = result["processing_time"]
                print(f"  ✓ {i+1}. {filename}: {chars} 字符 ({time:.2f}s)")
            else:
                print(f"  ✗ {i+1}. {result.get('file_path', 'unknown')}: {result['error']}")

        return success_count > 0


async def test_adapter_info():
    """测试适配器信息"""
    print("\n" + "=" * 60)
    print("测试 4: 适配器信息")
    print("=" * 60)

    adapter = MinerUAdapter(mode="auto")

    info = adapter.get_info()

    print(f"\n适配器配置:")
    print(f"  - 模式: {info['mode']}")
    print(f"  - 基础 URL: {info['base_url']}")
    print(f"  - 已启用: {info['enabled']}")
    print(f"  - 有 API Key: {info['has_api_key']}")
    print(f"  - 超时: {info['timeout']}s")
    print(f"  - 支持的扩展名: {', '.join(info['supported_extensions'])}")

    print(f"\n处理选项:")
    for key, value in info['options'].items():
        print(f"  - {key}: {value}")

    return True


async def test_file_type_support():
    """测试文件类型支持"""
    print("\n" + "=" * 60)
    print("测试 5: 文件类型支持")
    print("=" * 60)

    adapter = MinerUAdapter(mode="auto")

    test_extensions = [".pdf", ".doc", ".docx", ".jpg", ".png", ".txt", ".xlsx"]

    print(f"\n文件类型支持测试 (模式: {adapter.mode}):")
    for ext in test_extensions:
        supported = adapter.supports_file_type(ext)
        status = "✓" if supported else "✗"
        print(f"  {status} {ext}: {'支持' if supported else '不支持'}")

    return True


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("MinerU 适配器测试")
    print("=" * 60)

    tests = [
        ("健康检查", test_health_check),
        ("单个文档提取", test_single_document),
        ("批量处理", test_batch_processing),
        ("适配器信息", test_adapter_info),
        ("文件类型支持", test_file_type_support),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            results.append((test_name, False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
