"""Entry point for the LangGraph Segmentation Explorer agent."""
import os

from copilotkit import CopilotKitMiddleware
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

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

    model = ChatGoogleGenerativeAI(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
    )

    tools = [*make_zoho_tools(zoho_client), render_chart]

    return create_agent(
        model=model,
        tools=tools,
        middleware=[CopilotKitMiddleware()],
        state_schema=AgentState,
        system_prompt=SYSTEM_PROMPT,
    )


agent = _build_agent()
graph = agent
