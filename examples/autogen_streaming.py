"""Compare streaming and non-streaming AssistantAgent output."""

import asyncio
from contextlib import aclosing

from autogen_agentchat.agents import AssistantAgent

from app.core.llms import model_client
from app.utils.lifecycle import close_with_timeout


async def web_search(query: str) -> str:
    """Search tool placeholder; configure a provider before running it."""
    raise NotImplementedError("Configure a real search provider before using this demo tool")


async def main() -> None:
    """演示流式及完整响应并清理模型客户端；搜索工具需先配置真实实现。"""
    try:
        agent = AssistantAgent(
            name="Assistant",
            model_client=model_client,
            description="An assistant with access to a search tool.",
            system_message="你是小可，回答一切问题",
            model_client_stream=True,
            tools=[web_search],
        )
        async with aclosing(agent.run_stream(task="新疆支持货到付款吗")) as stream:
            async for message in stream:
                print(message)
        result = await agent.run(task="新疆支持货到付款吗")
        print(result)
    finally:
        await close_with_timeout(model_client.close)


if __name__ == "__main__":
    asyncio.run(main())
