import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import  StructuredMessage,TextMessage
from autogen_agentchat.ui import  Console
from autogen_core import CancellationToken
from autogen_ext.models.openai import  OpenAIChatCompletionClient
from models.llms import model_client

async  def web_search(city:str)->str:
    """
    搜索星系
    """
    return

async  def main():
    agent=AssistantAgent(
        name="Assistant",
        model_client=model_client,
        description="An agent that provides assistance with ability to use tools.", # name和描述决定智能体干嘛的
        system_message="你是小可，回答一切问题",
        model_client_stream=True

    )
    #流式
    stream=agent.run_stream(task="新疆支持货到付款吗")
    #分解输出内容
    async for msg in stream:
        print(msg)
    # 非流式
    result = await  agent.run(task="新疆支持获得付款吗")
    print(result)


asyncio.run(main())