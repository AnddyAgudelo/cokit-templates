from unittest.mock import MagicMock

import pytest

from src.tools.chart_renderers import render_chart


def _runtime_mock(state: dict | None = None) -> MagicMock:
    """Build a MagicMock that quacks like ToolRuntime for our tool's needs:
    .state.get() and .tool_call_id."""
    runtime = MagicMock()
    runtime.state = state if state is not None else {}
    runtime.tool_call_id = "tc-123"
    return runtime


def _invoke(args: dict, runtime: MagicMock):
    """Helper: invoke render_chart by injecting runtime into the input dict.
    LangChain's @tool decorator unpacks input keys to function parameters."""
    return render_chart.invoke({**args, "runtime": runtime})


def test_render_chart_appends_chart_to_state() -> None:
    runtime = _runtime_mock(state={"charts": []})
    cmd = _invoke({
        "type": "pie",
        "title": "Customers by city",
        "data": [
            {"label": "Bogota", "value": 120},
            {"label": "Medellin", "value": 80},
        ],
        "source_query": "Premium customers grouped by city",
    }, runtime)

    update = cmd.update
    assert "charts" in update
    assert len(update["charts"]) == 1
    chart = update["charts"][0]
    assert chart["type"] == "pie"
    assert chart["title"] == "Customers by city"
    assert chart["data"] == [
        {"label": "Bogota", "value": 120.0},
        {"label": "Medellin", "value": 80.0},
    ]
    assert chart["source_query"] == "Premium customers grouped by city"
    assert chart["id"]


def test_render_chart_preserves_existing_charts() -> None:
    existing = [{"id": "old", "type": "bar", "title": "x", "data": [{"label": "a", "value": 1}], "x_label": None, "y_label": None, "source_query": "y"}]
    runtime = _runtime_mock(state={"charts": existing})

    cmd = _invoke({
        "type": "metric",
        "title": "Total",
        "data": [{"label": "Total", "value": 500}],
        "source_query": "Sum of customers",
    }, runtime)

    assert len(cmd.update["charts"]) == 2
    assert cmd.update["charts"][0]["id"] == "old"


def test_render_chart_rejects_invalid_type() -> None:
    runtime = _runtime_mock()
    with pytest.raises(ValueError, match="Unsupported chart type"):
        _invoke({
            "type": "scatter",
            "title": "x",
            "data": [{"label": "a", "value": 1}],
            "source_query": "y",
        }, runtime)


def test_render_chart_rejects_empty_data() -> None:
    runtime = _runtime_mock()
    with pytest.raises(ValueError, match="at least one"):
        _invoke({
            "type": "pie",
            "title": "x",
            "data": [],
            "source_query": "y",
        }, runtime)


def test_render_chart_skips_invalid_data_points() -> None:
    runtime = _runtime_mock(state={"charts": []})
    cmd = _invoke({
        "type": "bar",
        "title": "x",
        "data": [
            {"label": "a", "value": 1},
            {"label": "b", "value": "not-a-number"},  # skipped
            {"value": 2},  # missing label, skipped
            {"label": "c", "value": 3},
        ],
        "source_query": "y",
    }, runtime)
    assert cmd.update["charts"][0]["data"] == [
        {"label": "a", "value": 1.0},
        {"label": "c", "value": 3.0},
    ]
