from unittest.mock import MagicMock

import pytest

from src.tools.chart_renderers import render_chart


def _runtime(state: dict | None = None) -> MagicMock:
    runtime = MagicMock()
    runtime.state = state if state is not None else {}
    runtime.tool_call_id = "tc-123"
    return runtime


def test_render_chart_appends_chart_to_state() -> None:
    runtime = _runtime(state={"charts": []})
    cmd = render_chart.invoke({
        "type": "pie",
        "title": "Customers by city",
        "data": [
            {"label": "Bogota", "value": 120},
            {"label": "Medellin", "value": 80},
        ],
        "source_query": "Premium customers grouped by city",
    }, runtime=runtime)

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
    runtime = _runtime(state={"charts": existing})

    cmd = render_chart.invoke({
        "type": "metric",
        "title": "Total",
        "data": [{"label": "Total", "value": 500}],
        "source_query": "Sum of customers",
    }, runtime=runtime)

    assert len(cmd.update["charts"]) == 2
    assert cmd.update["charts"][0]["id"] == "old"


def test_render_chart_rejects_invalid_type() -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="Unsupported chart type"):
        render_chart.invoke({
            "type": "scatter",
            "title": "x",
            "data": [{"label": "a", "value": 1}],
            "source_query": "y",
        }, runtime=runtime)


def test_render_chart_rejects_empty_data() -> None:
    runtime = _runtime()
    with pytest.raises(ValueError, match="at least one"):
        render_chart.invoke({
            "type": "pie",
            "title": "x",
            "data": [],
            "source_query": "y",
        }, runtime=runtime)


def test_render_chart_skips_invalid_data_points() -> None:
    runtime = _runtime(state={"charts": []})
    cmd = render_chart.invoke({
        "type": "bar",
        "title": "x",
        "data": [
            {"label": "a", "value": 1},
            {"label": "b", "value": "not-a-number"},  # skipped
            {"value": 2},  # missing label, skipped
            {"label": "c", "value": 3},
        ],
        "source_query": "y",
    }, runtime=runtime)
    assert cmd.update["charts"][0]["data"] == [
        {"label": "a", "value": 1.0},
        {"label": "c", "value": 3.0},
    ]
