#!/usr/bin/env python3
"""
提示词管理系统使用示例
"""

import asyncio
import json
from datetime import datetime

# 添加项目路径
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.prompts import PromptManager, get_prompt, get_prompt_manager


async def example_basic_usage():
    """基本使用示例"""
    print("\n=== 基本使用示例 ===\n")

    # 获取全局提示词管理器
    pm = get_prompt_manager()

    # 1. 获取意图分类提示词
    print("1. 获取意图分类提示词:")
    intent_prompt = pm.get_prompt(
        "intent.classification",
        query="我想申请汽车补贴需要什么条件？"
    )
    print(f"   提示词长度: {len(intent_prompt)} 字符")
    print(f"   提示词预览: {intent_prompt[:200]}...\n")

    # 2. 获取聊天提示词
    print("2. 获取聊天提示词:")
    greeting_prompt = pm.get_prompt(
        "chat.greeting",
        user_input="你好",
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    print(f"   {greeting_prompt}\n")

    # 3. 获取政策分析提示词
    print("3. 获取政策分析提示词:")
    analysis_prompt = pm.get_prompt(
        "policy.analysis",
        policy_content="济南市2025年汽车以旧换新补贴实施细则...",
        user_query="补贴标准是多少？"
    )
    print(f"   提示词已生成，长度: {len(analysis_prompt)} 字符\n")


async def example_prompt_management():
    """提示词管理示例"""
    print("\n=== 提示词管理示例 ===\n")

    pm = get_prompt_manager()

    # 1. 列出所有提示词
    print("1. 列出所有意图相关的提示词:")
    intent_prompts = pm.list_prompts(category="intent")
    for name in intent_prompts:
        print(f"   - {name}")
    print()

    # 2. 按标签筛选
    print("2. 列出所有带'policy'标签的提示词:")
    policy_prompts = pm.list_prompts(tags=["policy"])
    for name, config in policy_prompts.items():
        print(f"   - {name}: {config.description}")
    print()

    # 3. 添加自定义提示词
    print("3. 添加自定义提示词:")
    from app.prompts.prompt_manager import PromptConfig
    custom_prompt = PromptConfig(
        name="custom.greeting",
        content="你好！我是政策助手，很高兴为您服务。{time}",
        description="自定义问候语",
        tags=["custom", "greeting"]
    )
    success = pm.add_prompt(custom_prompt)
    print(f"   添加成功: {success}\n")

    # 4. 更新提示词
    print("4. 更新提示词:")
    success = pm.update_prompt(
        "custom.greeting",
        "您好！我是智能政策助手，{name}。今天{time}，有什么可以帮助您的吗？"
    )
    print(f"   更新成功: {success}\n")

    # 5. 获取提示词配置
    print("5. 获取提示词配置:")
    config = pm.get_prompt_config("custom.greeting")
    if config:
        print(f"   名称: {config.name}")
        print(f"   描述: {config.description}")
        print(f"   标签: {config.tags}")
        print(f"   版本: {config.version}")
        print(f"   更新时间: {config.updated_at}\n")


async def example_agent_integration():
    """智能体集成示例"""
    print("\n=== 智能体集成示例 ===\n")

    # 模拟意图识别
    print("1. 模拟意图识别过程:")
    pm = get_prompt_manager()

    user_query = "我想买新能源汽车，能补贴多少钱？"

    # 步骤1：意图分类
    classification_prompt = pm.get_prompt(
        "intent.classification",
        query=user_query
    )
    print("   [意图分类] 已生成分类提示词")

    # 模拟LLM响应
    mock_response = json.dumps({
        "intent_type": "benefit_calculation",
        "confidence": 0.95,
        "keywords": ["新能源汽车", "补贴", "多少钱"],
        "entities": {
            "policy_type": ["新能源汽车补贴"],
            "target_group": ["购车者"],
            "amount": ["多少钱"]
        },
        "reasoning": "用户询问补贴金额，属于计算类查询"
    })
    print(f"   [意图分类] 模拟响应: {mock_response}\n")

    # 步骤2：选择处理链
    chain_prompt = pm.get_prompt(
        "intent.chain_selection",
        intent_type="benefit_calculation",
        confidence=0.95,
        entity_count=3,
        complexity="simple"
    )
    print("   [链选择] 已生成处理链选择提示词")

    # 步骤3：政策检索
    retrieval_prompt = pm.get_prompt(
        "policy.retrieval",
        query=user_query,
        entities=json.dumps({
            "policy_type": ["新能源汽车补贴"],
            "target_group": ["购车者"]
        })
    )
    print("   [政策检索] 已生成检索查询提示词\n")


async def example_export_import():
    """导入导出示例"""
    print("\n=== 导入导出示例 ===\n")

    pm = get_prompt_manager()

    # 1. 导出提示词
    print("1. 导出所有policy相关提示词:")
    export_file = "../resources/gove/data/exported_prompts.json"
    pm.export_prompts(export_file, category="policy")
    print(f"   已导出到: {export_file}\n")

    # 2. 获取统计信息
    print("2. 提示词统计信息:")
    stats = pm.get_stats()
    print(f"   总提示词数: {stats['total_prompts']}")
    print(f"   分类统计: {stats['categories']}")
    print(f"   标签统计: {stats['tags']}")
    print(f"   最近更新:")
    for update in stats['recent_updates']:
        print(f"     - {update['name']}: {update['updated_at']}")
    print()


async def example_dynamic_prompts():
    """动态提示词示例"""
    print("\n=== 动态提示词示例 ===\n")

    pm = get_prompt_manager()

    # 1. 带参数的提示词
    print("1. 使用动态参数:")
    response = pm.get_prompt(
        "generation.step_by_step",
        process_info="申请补贴需要提交身份证、户口本、购车发票等材料"
    )
    print(f"   生成的步骤说明预览: {response[:200]}...\n")

    # 2. 复杂场景组合
    print("2. 复杂场景组合:")
    scenario = {
        "user_type": "高校毕业生",
        "policy_type": "创业补贴",
        "amount": "10万元",
        "duration": "3年"
    }

    personalized_prompt = pm.get_prompt(
        "generation.answer_generation",
        retrieved_policies="高校毕业生创业补贴政策...",
        analysis_results="符合申请条件...",
        user_query=f"我是{scenario['user_type']}，能申请多少{scenario['policy_type']}？"
    )
    print(f"   个性化答案生成提示词已创建，长度: {len(personalized_prompt)} 字符\n")


async def main():
    """主函数"""
    print("提示词管理系统使用示例")
    print("=" * 50)

    # 运行所有示例
    await example_basic_usage()
    await example_prompt_management()
    await example_agent_integration()
    await example_export_import()
    await example_dynamic_prompts()

    print("\n" + "=" * 50)
    print("✅ 所有示例运行完成！")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())