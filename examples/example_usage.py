"""
Example usage of the Policy QA System.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.policy_service import PolicyQAService


async def example_basic_usage():
    """Basic usage example."""
    print("=== 基本使用示例 ===\n")

    # Initialize the service
    service = PolicyQAService()
    service.initialize()

    # Load documents
    print("加载政策文档...")
    doc_count = service.load_documents("/data/temp33/市级消费活动政策")
    doc_count += service.load_documents("/data/temp33/2025年家电和数码以旧换新政策文件")
    print(f"已加载 {doc_count} 个文档\n")

    # Ask questions
    questions = [
        "2025年家电以旧换新的补贴标准是多少？",
        "济南市消费券如何申请？",
        "汽车消费补贴的申请条件是什么？",
        "以旧换新政策适用于哪些产品？"
    ]

    for question in questions:
        print(f"\n问题: {question}")
        print("-" * 50)

        response = await service.ask(question)

        if response.get("success"):
            answer_data = response.get("answer", {})
            print(f"回答: {answer_data.get('answer', '')}")

            sources = answer_data.get("sources", [])
            if sources:
                print(f"\n来源: {', '.join(sources)}")

            confidence = answer_data.get("confidence", 0)
            print(f"置信度: {confidence:.2%}")
        else:
            print(f"错误: {response.get('error')}")

        print("-" * 50)


async def example_detailed_workflow():
    """Show detailed workflow example."""
    print("\n\n=== 详细工作流程示例 ===\n")

    service = PolicyQAService()
    service.initialize()

    # Load documents
    service.load_documents("/data/temp33/市级消费活动政策")

    # Process a single question with detailed output
    question = "我想申请汽车消费补贴，需要什么条件？"
    print(f"处理问题: {question}\n")

    # Step-by-step processing
    print("1. 理解问题...")
    question_understander = service.agent_factory.get_agent(
        service.agent_factory.AgentTypes.QUESTION_UNDERSTANDER
    )
    analysis = await question_understander.process_message(question)
    print(f"   意图: {analysis['data']['intent']}")
    print(f"   关键词: {', '.join(analysis['data']['keywords'])}")

    print("\n2. 检索相关政策...")
    retriever = service.agent_factory.get_agent(
        service.agent_factory.AgentTypes.POLICY_RETRIEVER
    )
    retrieval = await retriever.process_message(question)
    print(f"   找到 {len(retrieval['data'].documents)} 个相关文档")

    print("\n3. 分析政策...")
    analyzer = service.agent_factory.get_agent(
        service.agent_factory.AgentTypes.POLICY_ANALYZER
    )
    analysis_request = {
        "query": question,
        "documents": [doc.__dict__ for doc in retrieval['data'].documents]
    }
    analysis_report = await analyzer.process_message(analysis_request)
    synthesis = analysis_report['data']['synthesis']
    print(f"   最相关政策: {synthesis.get('most_relevant', 'N/A')}")

    print("\n4. 生成回答...")
    generator = service.agent_factory.get_agent(
        service.agent_factory.AgentTypes.ANSWER_GENERATOR
    )
    generation_request = {
        "query": question,
        "analysis": analysis['data'],
        "document_analyses": analysis_report['data']['document_analyses']
    }
    answer = await generator.process_message(generation_request)
    print(f"   回答生成完成，置信度: {answer['data'].get('confidence', 0):.2%}")

    print("\n5. 验证回答...")
    verifier = service.agent_factory.get_agent(
        service.agent_factory.AgentTypes.ANSWER_VERIFIER
    )
    verification_request = {
        "query": question,
        "answer": answer['data'].get('answer', ''),
        "sources": answer['data'].get('sources', []),
        "document_analyses": analysis_report['data']['document_analyses']
    }
    verification = await verifier.process_message(verification_request)
    print(f"   验证结果: {'通过' if verification['data'].get('is_accurate') else '需要改进'}")

    # Final answer
    print("\n最终回答:")
    print("=" * 50)
    print(answer['data'].get('answer', ''))
    print("=" * 50)


async def example_batch_questions():
    """Batch processing example."""
    print("\n\n=== 批量问答示例 ===\n")

    service = PolicyQAService()
    service.initialize()

    # Load documents
    service.load_documents("/data/temp33/市级消费活动政策")
    service.load_documents("/data/temp33/2025年家电和数码以旧换新政策文件")

    # Batch of questions
    questions = [
        "以旧换新的补贴金额是多少？",
        "消费券的使用范围是什么？",
        "如何申请购车补贴？",
        "政策的截止日期是什么时候？",
        "哪些人可以申请这些补贴？"
    ]

    results = []

    print("批量处理问题...\n")
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] 处理: {question}")
        response = await service.ask(question)
        results.append({
            "question": question,
            "answer": response.get("answer", {}).get("answer", ""),
            "confidence": response.get("answer", {}).get("confidence", 0),
            "success": response.get("success", False)
        })

    # Summary
    print("\n\n处理结果汇总:")
    print("-" * 50)
    for i, result in enumerate(results, 1):
        status = "✅" if result["success"] else "❌"
        print(f"{status} {result['question']}")
        print(f"   置信度: {result['confidence']:.2%}")
        if result["answer"]:
            answer_preview = result["answer"][:100] + "..." if len(result["answer"]) > 100 else result["answer"]
            print(f"   回答预览: {answer_preview}")
        print()


if __name__ == "__main__":
    # Run examples
    asyncio.run(example_basic_usage())
    asyncio.run(example_detailed_workflow())
    asyncio.run(example_batch_questions())