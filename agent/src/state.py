"""TypedDicts that define what the agent knows about. Mirrored in Zod on the frontend."""
from typing import Literal, TypedDict

from langchain.agents import AgentState as BaseAgentState

ChartType = Literal["pie", "bar", "metric"]


class ChartDataPoint(TypedDict):
    label: str
    value: float


class ChartSpec(TypedDict):
    id: str
    type: ChartType
    title: str
    data: list[ChartDataPoint]
    x_label: str | None
    y_label: str | None
    source_query: str


class AgentState(BaseAgentState):
    charts: list[ChartSpec]
    last_segment_filter: dict | None
