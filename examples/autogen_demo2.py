import asyncio
import anyio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.tools import AgentTool
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient


async def main() -> None:
    model_client = OpenAIChatCompletionClient(model="gpt-4.1")
    try:

        math_agent = AssistantAgent(
            "math_expert",
            model_client=model_client,
            system_message="You are a math expert.",
            description="A math expert assistant.",
            model_client_stream=True,
        )
        math_agent_tool = AgentTool(math_agent, return_value_as_last_message=True)

        chemistry_agent = AssistantAgent(
            "chemistry_expert",
            model_client=model_client,
            system_message="You are a chemistry expert.",
            description="A chemistry expert assistant.",
            model_client_stream=True,
        )
        chemistry_agent_tool = AgentTool(chemistry_agent, return_value_as_last_message=True)

        agent = AssistantAgent(
            "assistant",
            system_message="You are a general assistant. Use expert tools when needed.",
            model_client=model_client,
            model_client_stream=True,
            tools=[math_agent_tool, chemistry_agent_tool],
            max_tool_iterations=10,
        )
        await Console(agent.run_stream(task="What is the integral of x^2?"))
        await Console(agent.run_stream(task="What is the molecular weight of water?"))

    finally:
        with anyio.fail_after(5, shield=True):
            await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
