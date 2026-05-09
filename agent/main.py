"""Entry point for the LangGraph Segmentation Explorer agent."""
import os
from datetime import date

from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from src.state import AgentState
from src.system_prompt import SYSTEM_PROMPT
from src.tools.chart_renderers import render_chart
from src.tools.zoho_queries import make_zoho_tools
from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache
from src.zoho.client import ZohoClient, ZohoConfig


def _build_agent():
    zoho_config = ZohoConfig.from_env()
    zoho_client = ZohoClient(
        zoho_config,
        audit=AuditLogger(audit_dir="audit"),
        cache=SessionCache(),
    )

    model = ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        model_kwargs={"parallel_tool_calls": False},
    )

    tools = [*make_zoho_tools(zoho_client), render_chart]

    today = date.today().isoformat()
    system_prompt = SYSTEM_PROMPT.replace("{TODAY}", today)

    return create_agent(
        model=model,
        tools=tools,
        middleware=[CopilotKitMiddleware()],
        state_schema=AgentState,
        system_prompt=system_prompt,
    )


agent = _build_agent()
graph = agent
