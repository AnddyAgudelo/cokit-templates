from unittest.mock import MagicMock

from src.tools.zoho_queries import make_zoho_tools


def _client_returning(payload: dict) -> MagicMock:
    client = MagicMock()
    client.get.return_value = payload
    return client


def test_query_customers_returns_records_and_count() -> None:
    client = _client_returning({
        "data": [
            {"id": "1", "Last_Name": "Alice"},
            {"id": "2", "Last_Name": "Bob"},
        ],
        "info": {"count": 2, "more_records": False},
    })
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({
        "filters": {"Tier": "premium"},
        "limit": 50,
    })

    assert result["count"] == 2
    assert len(result["records"]) == 2
    assert result["records"][0]["id"] == "1"


def test_query_customers_requires_filters() -> None:
    client = _client_returning({"data": []})
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({"filters": {}, "limit": 10})
    assert result["count"] == 0
    assert "error" in result


def test_query_customers_caps_limit_at_200() -> None:
    client = _client_returning({"data": [], "info": {"count": 0}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({"filters": {"Tier": "premium"}, "limit": 9999})

    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs["params"]["per_page"] == 200


def test_query_customers_returns_error_on_client_failure() -> None:
    client = MagicMock()
    client.get.side_effect = RuntimeError("zoho down")
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({"filters": {"Tier": "premium"}, "limit": 50})
    assert result["count"] == 0
    assert result["records"] == []
    assert "zoho down" in result["error"]
