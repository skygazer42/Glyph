"""
Main entry point for the advanced policy QA system.
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, track
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents.orchestrators.legacy import PolicyQAOrchestrator
from models.base import PolicyDocument, PolicyType, AgentType
from utils.document_loader import DocumentLoader
from utils.config import Config

console = Console()


def print_banner():
    """Print application banner."""
    console.print(Panel.fit(
        "[bold blue]政策智能问答系统 v2.0[/bold blue]\n"
        "[dim]基于AutoGen Core框架的深度政策分析系统[/dim]",
        border_style="blue"
    ))


async def interactive_mode(orchestrator: PolicyQAOrchestrator):
    """Run the system in interactive mode."""
    console.print("\n[green]✅ 系统已就绪，进入交互模式[/green]")
    console.print("[dim]输入 'quit' 或 'exit' 退出，输入 'help' 查看帮助\n")

    session_id = f"interactive_{asyncio.get_event_loop().time()}"

    while True:
        query = console.input("\n[bold cyan]请输入您的问题:[/bold cyan] ").strip()

        if query.lower() in ['quit', 'exit', '退出']:
            console.print("[yellow]👋 再见！[/yellow]")
            break

        if query.lower() == 'help':
            print_help()
            continue

        if not query:
            continue

        # Process query with progress indicator
        with Progress() as progress:
            task = progress.add_task("[cyan]处理中...", total=100)

            # Update progress for different steps
            progress.update(task, advance=20)
            response = await orchestrator.process_query(query, session_id=session_id)
            progress.update(task, advance=80)

        # Display answer
        display_answer(response)

        # Show workflow state if debug mode
        if orchestrator.workflow_state.get(session_id):
            state = orchestrator.workflow_state[session_id]
            console.print(f"\n[dim]处理步骤: {state['step']}/{state['total_steps']} | "
                         f"检索文档: {state['results'].get('retrieval', {}).get('total_searched', 0)} | "
                         f"处理时间: {response.total_processing_time:.2f}s[/dim]")


def display_answer(response):
    """Display the answer in a formatted way."""
    if not response.verification_passed:
        console.print("\n[red]⚠️  答案验证未通过，请谨慎参考[/red]")

    # Display answer
    console.print(f"\n[bold green]回答:[/bold green]")
    console.print(Panel(response.answer, border_style="green"))

    # Display sources
    if response.sources:
        console.print("\n[bold yellow]政策来源:[/bold yellow]")
        for i, source in enumerate(response.sources, 1):
            console.print(f"  {i}. {source.title}")
            console.print(f"     [dim]发布机构: {source.source}[/dim]")

    # Display confidence
    confidence_color = "green" if response.confidence > 0.8 else "yellow" if response.confidence > 0.5 else "red"
    console.print(f"\n置信度: [{confidence_color}]{response.confidence:.1%}[/{confidence_color}]")

    # Display metadata
    if response.metadata:
        console.print("\n[dim]附加信息:")
        for key, value in response.metadata.items():
            console.print(f"  {key}: {value}")


def print_help():
    """Print help information."""
    help_text = """
[bold]使用帮助:[/bold]

1. [cyan]资格查询[/cyan] - "申请汽车补贴需要什么条件？"
2. [cyan]金额计算[/cyan] - "家电以旧换新能补多少钱？"
3. [cyan]流程咨询[/cyan] - "如何申请消费券？"
4. [cyan]时间查询[/cyan] - "政策什么时候截止？"
5. [cyan]政策比较[/cyan] - "济南和山东的补贴政策有什么不同？"

[bold]示例问题:[/bold]
• 2025年家电以旧换新补贴标准
• 新能源汽车补贴申请流程
• 济南市消费券发放时间
• 企业税收优惠政策
    """
    console.print(Panel(help_text, title="帮助", border_style="blue"))


async def batch_mode(orchestrator: PolicyQAOrchestrator, queries: List[str]):
    """Process multiple queries in batch mode."""
    console.print(f"\n[green]批量处理 {len(queries)} 个问题[/green]\n")

    results = []
    for i, query in enumerate(track(queries, description="处理进度")):
        response = await orchestrator.process_query(query)
        results.append({
            "query": query,
            "answer": response.answer[:200] + "...",
            "confidence": response.confidence,
            "sources": len(response.sources)
        })

    # Display results table
    table = Table(title="批量处理结果")
    table.add_column("序号", style="cyan", width=4)
    table.add_column("问题", style="magenta")
    table.add_column("回答预览", style="green")
    table.add_column("置信度", justify="center")
    table.add_column("来源数", justify="center")

    for i, result in enumerate(results, 1):
        confidence_color = "green" if result["confidence"] > 0.8 else "yellow" if result["confidence"] > 0.5 else "red"
        table.add_row(
            str(i),
            result["query"][:30] + "..." if len(result["query"]) > 30 else result["query"],
            result["answer"],
            f"[{confidence_color}]{result['confidence']:.1%}[/{confidence_color}]",
            str(result["sources"])
        )

    console.print(table)


async def load_documents_command(orchestrator: PolicyQAOrchestrator, paths: List[str]):
    """Load documents into the system."""
    console.print(f"[blue]正在加载文档...[/blue]")

    document_loader = DocumentLoader()
    all_documents = []

    for path in paths:
        if os.path.isdir(path):
            console.print(f"扫描目录: {path}")
            docs = document_loader.load_from_directory(path)
            all_documents.extend(docs)
        elif os.path.isfile(path):
            console.print(f"加载文件: {path}")
            doc = document_loader.load_single_file(path)
            if doc:
                all_documents.append(doc)

    if all_documents:
        # Add to vector store
        await orchestrator.agents[AgentType.POLICY_RETRIEVER].add_documents(all_documents)
        console.print(f"[green]✅ 成功加载 {len(all_documents)} 个文档[/green]")
    else:
        console.print("[red]❌ 未找到任何文档[/red]")


async def main():
    """Main function."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    parser = argparse.ArgumentParser(description="政策智能问答系统 v2.0")
    parser.add_argument("--config", type=str, help="配置文件路径")
    parser.add_argument("--load-docs", nargs="+", help="加载文档路径")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument("--batch", type=str, help="批量查询文件")
    parser.add_argument("--query", "-q", type=str, help="单个查询")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Load configuration
    config = Config.from_file(args.config) if args.config else Config.from_env()

    # Initialize orchestrator
    async with PolicyQAOrchestrator(
        model_config=config.model,
        vector_store_config=config.vector_store,
        logging_config=config.logging,
        conversation_config=config.conversation.dict()
    ) as orchestrator:
        # Load documents if specified
        if args.load_docs:
            await load_documents_command(orchestrator, args.load_docs)

        # Show system stats
        if args.debug:
            stats = orchestrator.get_agent_metrics()
            console.print("\n[bold]系统状态:[/bold]")
            for agent, metrics in stats.items():
                console.print(f"  {agent}: {metrics}")

        # Run based on mode
        if args.interactive:
            await interactive_mode(orchestrator)
        elif args.query:
            response = await orchestrator.process_query(args.query)
            display_answer(response)
        elif args.batch:
            # Load queries from file
            with open(args.batch, 'r', encoding='utf-8') as f:
                queries = [line.strip() for line in f if line.strip()]
            await batch_mode(orchestrator, queries)
        else:
            console.print("[yellow]请指定运行模式: --interactive, --query, 或 --batch[/yellow]")
            console.print("使用 --help 查看更多选项")


if __name__ == "__main__":
    # Create necessary directories
    os.makedirs("data/vector_store", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("cache", exist_ok=True)

    # Run main function
    asyncio.run(main())
