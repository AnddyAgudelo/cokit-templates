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


# ---------------------------------------------------------------------------
# Task 12: get_field_distribution tests
# ---------------------------------------------------------------------------

def test_get_field_distribution_buckets_records_by_field() -> None:
    client = _client_returning({
        "data": [
            {"id": "1", "City": "Bogota"},
            {"id": "2", "City": "Medellin"},
            {"id": "3", "City": "Bogota"},
            {"id": "4", "City": None},
        ],
    })
    [_, get_field_distribution, _] = make_zoho_tools(client)

    result = get_field_distribution.invoke({"field": "City"})

    assert result["field"] == "City"
    assert result["total"] == 4
    labels = {b["label"]: b["count"] for b in result["buckets"]}
    assert labels == {"Bogota": 2, "Medellin": 1, "(unknown)": 1}


def test_get_field_distribution_orders_by_count_desc() -> None:
    client = _client_returning({
        "data": [
            {"City": "A"}, {"City": "B"}, {"City": "B"}, {"City": "C"},
            {"City": "C"}, {"City": "C"},
        ],
    })
    [_, get_field_distribution, _] = make_zoho_tools(client)
    result = get_field_distribution.invoke({"field": "City"})
    counts = [b["count"] for b in result["buckets"]]
    assert counts == sorted(counts, reverse=True)


def test_get_field_distribution_with_filters_uses_search_endpoint() -> None:
    client = _client_returning({"data": []})
    [_, get_field_distribution, _] = make_zoho_tools(client)

    get_field_distribution.invoke({
        "field": "City",
        "filters": {"Tier": "premium"},
    })

    call_args = client.get.call_args
    assert call_args.args[0] == "Contacts/search"
    assert "(Tier:equals:premium)" in call_args.kwargs["params"]["criteria"]


def test_get_field_distribution_returns_error_on_failure() -> None:
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get.side_effect = RuntimeError("zoho down")
    [_, get_field_distribution, _] = make_zoho_tools(client)
    result = get_field_distribution.invoke({"field": "City"})
    assert result["buckets"] == []
    assert "zoho down" in result["error"]


# ---------------------------------------------------------------------------
# Task 13: list_custom_fields tests
# ---------------------------------------------------------------------------

def test_list_custom_fields_normalizes_response() -> None:
    client = _client_returning({
        "fields": [
            {
                "api_name": "Tier",
                "display_label": "Tier",
                "data_type": "picklist",
                "pick_list_values": [
                    {"display_value": "free"},
                    {"display_value": "premium"},
                ],
            },
            {
                "api_name": "City",
                "display_label": "City",
                "data_type": "text",
                "pick_list_values": [],
            },
        ],
    })
    [_, _, list_custom_fields] = make_zoho_tools(client)

    fields = list_custom_fields.invoke({"module": "Contacts"})
    assert fields[0]["api_name"] == "Tier"
    assert fields[0]["picklist_values"] == ["free", "premium"]
    assert fields[1]["api_name"] == "City"
    assert fields[1]["picklist_values"] is None


def test_list_custom_fields_passes_cache_key_to_client() -> None:
    client = _client_returning({"fields": []})
    [_, _, list_custom_fields] = make_zoho_tools(client)

    list_custom_fields.invoke({"module": "Deals"})
    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs["cache_key"] == "fields:Deals"
    assert call_kwargs["cache_ttl_seconds"] == 3600


def test_list_custom_fields_returns_empty_on_failure() -> None:
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get.side_effect = RuntimeError("boom")
    [_, _, list_custom_fields] = make_zoho_tools(client)
    assert list_custom_fields.invoke({}) == []
