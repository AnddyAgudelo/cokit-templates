"""Generative-UI tools. The agent calls render_chart after fetching real data."""
import uuid
from typing import Annotated, Any

from langchain.messages import ToolMessage
from langchain.tools import tool
from langchain_core.tools.base import InjectedToolArg
from langgraph.types import Command

ALLOWED_CHART_TYPES = {"pie", "bar", "metric"}


@tool
def render_chart(
    type: str,
    title: str,
    data: list[dict[str, Any]],
    source_query: str,
    runtime: Annotated[Any, InjectedToolArg] = None,
    x_label: str | None = None,
    y_label: str | None = None,
) -> Command:
    """
    Render a chart of the given type (pie | bar | metric).

    `data` must be a list of {label, value} pairs. Items with non-numeric
    values or missing keys are silently skipped.

    Call AFTER getting real data from a query tool. NEVER invent data.

    `source_query` is a brief human-readable description of what was queried
    (e.g., "Premium customers grouped by city"); shown as the chart subtitle.
    """
    if type not in ALLOWED_CHART_TYPES:
        raise ValueError(
            f"Unsupported chart type: {type}. Use one of {sorted(ALLOWED_CHART_TYPES)}."
        )

    cleaned: list[dict[str, Any]] = []
    for d in data:
        if not isinstance(d, dict) or "label" not in d or "value" not in d:
            continue
        try:
            cleaned.append({"label": str(d["label"]), "value": float(d["value"])})
        except (TypeError, ValueError):
            continue

    if not cleaned:
        raise ValueError(
            "data must contain at least one {label, value} pair with a numeric value"
        )

    chart = {
        "id": str(uuid.uuid4()),
        "type": type,
        "title": title,
        "data": cleaned,
        "x_label": x_label,
        "y_label": y_label,
        "source_query": source_query,
    }

    existing = (runtime.state.get("charts", []) if runtime is not None else []) or []

    return Command(update={
        "charts": existing + [chart],
        "messages": [ToolMessage(
            content=f"Rendered {type} chart: {title}",
            tool_call_id=runtime.tool_call_id if runtime is not None else None,
        )],
    })
