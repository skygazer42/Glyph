#!/usr/bin/env python3
"""
快速演示图片检索功能
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base.hierarchical_index import HierarchicalRetriever


def demo_image_search():
    """演示图片搜索"""

    # 存储目录（假设已构建索引）
    storage_dir = "/data/temp33/gov/storage/hierarchical"

    # 检查索引是否存在
    if not Path(storage_dir).exists():
        print("❌ 索引不存在，请先构建索引：")
        print("python scripts/batch_process.py build --data-dir /data/temp33/gov/data/process")
        return

    print("="*60)
    print("   图片检索演示")
    print("="*60)

    try:
        # 初始化检索器
        print("\n初始化检索器...")
        retriever = HierarchicalRetriever(
            storage_dir=storage_dir,
            use_rerank="simple",
            enable_images=True
        )
        print("✅ 检索器就绪")

        # 演示查询
        demos = [
            {
                "title": "查找二维码",
                "query": "二维码 扫码 申请",
                "image_only": True
            },
            {
                "title": "查找补贴流程图",
                "query": "补贴 流程 步骤 图",
                "image_only": False
            },
            {
                "title": "查找所有图片",
                "query": "图片 图像 附图",
                "image_only": True
            }
        ]

        for demo in demos:
            print(f"\n{'='*60}")
            print(f"演示: {demo['title']}")
            print(f"查询: {demo['query']}")
            print(f"模式: {'仅图片' if demo['image_only'] else '图文混合'}")
            print("-"*60)

            # 执行检索
            results = retriever.retrieve_with_images(
                query=demo['query'],
                top_k=5,
                image_only=demo['image_only']
            )

            # 显示结果
            if results['image_results']:
                print(f"\n找到 {len(results['image_results'])} 个相关图片：")
                for i, img in enumerate(results['image_results'][:3], 1):
                    print(f"\n  [{i}] {img['path']}")
                    if img.get('caption'):
                        print(f"      说明: {img['caption']}")
                    if img.get('is_qrcode'):
                        print(f"      类型: 二维码")
                        if img.get('qr_content'):
                            print(f"      内容: {img['qr_content'][:50]}...")
                    if img.get('alt_text'):
                        print(f"      Alt: {img['alt_text']}")
            else:
                print("\n未找到相关图片")

            if not demo['image_only'] and results['text_nodes']:
                print(f"\n另有 {len(results['text_nodes'])} 个文本结果")

        # 交互模式
        print(f"\n{'='*60}")
        print("进入交互模式（输入 'quit' 退出）")
        print("-"*60)

        while True:
            query = input("\n请输入查询（例如：二维码）> ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("退出演示")
                break

            if not query:
                continue

            # 询问模式
            mode = input("仅搜索图片？(y/n，默认n) > ").strip().lower()
            image_only = mode in ['y', 'yes']

            # 执行搜索
            print("\n搜索中...")
            results = retriever.retrieve_with_images(
                query=query,
                top_k=5,
                image_only=image_only
            )

            # 显示结果
            if results['image_results']:
                print(f"\n找到 {results['total_images']} 个相关图片：")
                for i, img in enumerate(results['image_results'], 1):
                    print(f"\n  [{i}] {img['path']}")
                    if img.get('caption'):
                        print(f"      {img['caption']}")
                    if img.get('is_qrcode'):
                        print(f"      [二维码]")
            else:
                print("\n未找到相关图片")

            if not image_only and results['text_nodes']:
                print(f"\n另有 {len(results['text_nodes'])} 个文本结果")

    except Exception as e:
        print(f"\n❌ 出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    demo_image_search()