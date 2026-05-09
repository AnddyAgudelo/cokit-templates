"""Entry point for the LangGraph agent. Finalized in Task 16."""
from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

agent = create_agent(
    model=ChatOpenAI(model="gpt-5.2-mini"),
    tools=[],
    middleware=[CopilotKitMiddleware()],
    system_prompt="You are a stub agent for the bootstrap phase.",
)

graph = agent
