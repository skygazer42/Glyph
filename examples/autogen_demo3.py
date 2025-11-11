from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import SourceMatchTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.tools import TeamTool
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient


async def main() -> None:
    # Disable parallel tool calls when using TeamTool
    model_client = OpenAIChatCompletionClient(model="gpt-4.1")

    writer = AssistantAgent(name="writer", model_client=model_client, system_message="You are a helpful assistant.")
    reviewer = AssistantAgent(
        name="reviewer", model_client=model_client, system_message="You are a critical reviewer."
    )
    summarizer = AssistantAgent(
        name="summarizer",
        model_client=model_client,
        system_message="You combine the review and produce a revised response.",
    )
    team = RoundRobinGroupChat(
        [writer, reviewer, summarizer], termination_condition=SourceMatchTermination(sources=["summarizer"])
    )

    # Create a TeamTool that uses the team to run tasks, returning the last message as the result.
    tool = TeamTool(
        team=team,
        name="writing_team",
        description="A tool for writing tasks.",
        return_value_as_last_message=True,
    )

    # Create model client with parallel tool calls disabled for the main agent
    main_model_client = OpenAIChatCompletionClient(model="gpt-4.1", parallel_tool_calls=False)
    main_agent = AssistantAgent(
        name="main_agent",
        model_client=main_model_client,
        system_message="You are a helpful assistant that can use the writing tool.",
        tools=[tool],
    )
    # For handling each events manually.
    # async for message in main_agent.run_stream(
    #     task="Write a short story about a robot learning to love.",
    # ):
    #     print(message)
    # Use Console to display the messages in a more readable format.
    await Console(
        main_agent.run_stream(
            task="Write a short story about a robot learning to love.",
        )
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
