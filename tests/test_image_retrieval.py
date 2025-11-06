#!/usr/bin/env python3
"""
测试图片检索功能
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base.hierarchical_index import (
    HierarchicalIndexBuilder,
    HierarchicalRetriever
)
from knowledge_base.image_retrieval import ImageExtractor


def test_image_extraction():
    """测试图片提取功能"""
    print("="*60)
    print("测试图片提取")
    print("="*60)

    # 创建测试 Markdown
    test_md = """
# 济南市消费补贴政策

## 申请方式

消费者可以通过以下方式申请：

![申请二维码](images/apply_qr.jpg)
扫描上方二维码进入申请页面

## 补贴流程

![补贴流程图](images/process.png "补贴申请流程")
图1：补贴申请流程说明，包括以下步骤：

1. 登录平台
2. 填写信息
3. 提交申请
4. 等待审核

## 联系方式

![客服二维码](images/service_qr.jpg)
图：扫码添加客服微信，获取帮助

更多信息请访问官网。
    """

    # 提取图片
    extractor = ImageExtractor()
    images = extractor.extract_images_from_markdown("test.md", test_md)

    print(f"找到 {len(images)} 个图片：\n")
    for i, img in enumerate(images, 1):
        print(f"{i}. {img.relative_path}")
        if img.caption:
            print(f"   说明: {img.caption}")
        if img.context_after:
            print(f"   上下文: {img.context_after[:50]}...")
        print()

    return True


def test_build_index_with_images():
    """测试构建包含图片的索引"""
    print("="*60)
    print("构建包含图片的索引")
    print("="*60)

    data_dir = "/data/temp33/gov/data/process"
    storage_dir = "/data/temp33/gov/storage/test_images"

    # 查找几个测试文件
    import glob
    md_files = glob.glob(f"{data_dir}/**/*.md", recursive=True)[:3]

    if not md_files:
        print("未找到 Markdown 文件")
        return False

    print(f"使用 {len(md_files)} 个文件构建索引：")
    for f in md_files:
        print(f"  - {Path(f).name}")
    print()

    try:
        # 构建索引
        builder = HierarchicalIndexBuilder(storage_dir=storage_dir)
        stats = builder.build_from_markdown_files(
            md_files,
            use_llm=False,
            enable_images=True  # 启用图片提取
        )

        print("\n索引统计：")
        print(f"  文档数: {stats['total_docs']}")
        print(f"  章节数: {stats['total_sections']}")
        print(f"  块数: {stats['total_chunks']}")
        print(f"  图片数: {stats['total_images']}")

        return True
    except Exception as e:
        print(f"构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_retrieval():
    """测试图片检索"""
    print("="*60)
    print("测试图片检索")
    print("="*60)

    storage_dir = "/data/temp33/gov/storage/test_images"

    # 检查索引是否存在
    if not Path(storage_dir).exists():
        print("索引不存在，请先运行构建测试")
        return False

    try:
        # 初始化检索器
        retriever = HierarchicalRetriever(
            storage_dir=storage_dir,
            use_rerank="simple",
            enable_images=True
        )

        # 测试查询
        test_queries = [
            "二维码",
            "申请流程图",
            "扫码",
            "图片",
            "补贴申请方式"
        ]

        for query in test_queries:
            print(f"\n查询: '{query}'")
            print("-" * 40)

            # 检索包含图片的结果
            results = retriever.retrieve_with_images(
                query=query,
                top_k=5,
                image_only=False
            )

            print(f"找到 {results['total_images']} 个相关图片：")
            for i, img in enumerate(results['image_results'][:3], 1):
                print(f"\n  {i}. {img['path']}")
                if img['caption']:
                    print(f"     说明: {img['caption']}")
                if img['is_qrcode']:
                    print(f"     类型: 二维码")
                    if img['qr_content']:
                        print(f"     内容: {img['qr_content']}")

            if not results['image_results']:
                print("  （无图片结果）")

        return True
    except Exception as e:
        print(f"检索失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_only_search():
    """测试只搜索图片"""
    print("="*60)
    print("只搜索图片")
    print("="*60)

    storage_dir = "/data/temp33/gov/storage/test_images"

    try:
        retriever = HierarchicalRetriever(
            storage_dir=storage_dir,
            use_rerank="simple",
            enable_images=True
        )

        # 只搜索图片
        results = retriever.retrieve_with_images(
            query="二维码 扫描 申请",
            top_k=10,
            image_only=True  # 只返回图片
        )

        print(f"找到 {len(results['image_results'])} 个图片")
        print(f"文本节点: {len(results['text_nodes'])} 个（应该为0）")

        for img in results['image_results']:
            print(f"\n- {img['path']}")
            if img['is_qrcode']:
                print("  [二维码]")

        return True
    except Exception as e:
        print(f"搜索失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("   LlamaIndex 图片检索测试")
    print("="*60)

    tests = [
        ("图片提取", test_image_extraction),
        ("构建索引", test_build_index_with_images),
        ("图片检索", test_image_retrieval),
        ("纯图片搜索", test_image_only_search)
    ]

    results = []
    for name, test_func in tests:
        print(f"\n运行测试: {name}")
        try:
            success = test_func()
            results.append((name, success))
            print(f"\n✅ {name} {'成功' if success else '失败'}")
        except Exception as e:
            print(f"\n❌ {name} 出错: {e}")
            results.append((name, False))

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name}: {status}")

    all_passed = all(success for _, success in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())