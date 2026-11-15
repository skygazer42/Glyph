import asyncio

from autogen_agentchat.agents import AssistantAgent
from app.core.llms import model_client

async def web_search(city: str) -> str:
    """
    搜索星系
    """
    raise NotImplementedError("Configure a real search provider before using this demo tool")

async  def main():
    agent=AssistantAgent(
        name="Assistant",
        model_client=model_client,
        description="An agent that provides assistance with ability to use tools.", # name和描述决定智能体干嘛的
        system_message="你是小可，回答一切问题",
        model_client_stream=True,
        tools=[web_search]


    )
    #流式
    stream=agent.run_stream(task="新疆支持货到付款吗")
    #分解输出内容
    async for msg in stream:
        print(msg)
    # 非流式
    result = await  agent.run(task="新疆支持获得付款吗")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
