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


# ---------------------------------------------------------------------------
# Bug fix: module parameter routes to correct Zoho module
# ---------------------------------------------------------------------------

def test_query_customers_uses_module_parameter() -> None:
    client = _client_returning({"data": [], "info": {"count": 0}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({
        "filters": {"Industry": "Software"},
        "limit": 10,
        "module": "Accounts",
    })

    call_args = client.get.call_args
    assert call_args.args[0] == "Accounts/search", f"expected Accounts/search, got {call_args.args[0]}"


def test_get_field_distribution_uses_module_parameter() -> None:
    client = _client_returning({"data": []})
    [_, get_field_distribution, _] = make_zoho_tools(client)

    get_field_distribution.invoke({
        "field": "Industry",
        "module": "Accounts",
    })

    call_args = client.get.call_args
    assert call_args.args[0] == "Accounts", f"expected Accounts, got {call_args.args[0]}"


def test_get_field_distribution_uses_module_with_filters() -> None:
    client = _client_returning({"data": []})
    [_, get_field_distribution, _] = make_zoho_tools(client)

    get_field_distribution.invoke({
        "field": "Industry",
        "filters": {"Country": "Colombia"},
        "module": "Accounts",
    })

    call_args = client.get.call_args
    assert call_args.args[0] == "Accounts/search", f"expected Accounts/search, got {call_args.args[0]}"


# ---------------------------------------------------------------------------
# Field validation: deterministic enforcement against LLM hallucinations
# ---------------------------------------------------------------------------

def test_get_field_distribution_validates_field_exists() -> None:
    """If the field doesn't exist in the module, return error with suggestions."""
    from unittest.mock import MagicMock
    client = MagicMock()
    # First call: settings/fields returns the schema
    # Second call would be the actual distribution — but should never happen because validation fails
    client.get.return_value = {
        "fields": [
            {"api_name": "Estado_de_gestion"},
            {"api_name": "Sector_economico"},
            {"api_name": "Industry"},
        ],
    }
    [_, get_field_distribution, _] = make_zoho_tools(client)

    result = get_field_distribution.invoke({
        "field": "Fase",
        "module": "Accounts",
    })

    assert result["buckets"] == []
    assert "error" in result
    assert "Fase" in result["error"]
    assert "Accounts" in result["error"]
    assert "suggestions" in result
    # Settings/fields was called exactly once (the validation), not twice
    assert client.get.call_count == 1


def test_get_field_distribution_returns_render_hint_on_success() -> None:
    """Successful distributions include a render_hint to guide the LLM."""
    from unittest.mock import MagicMock
    client = MagicMock()

    def fake_get(path, params=None, **kwargs):
        if path == "settings/fields":
            return {"fields": [{"api_name": "City"}, {"api_name": "Industry"}]}
        # Distribution call
        return {"data": [{"City": "Bogota"}, {"City": "Medellin"}, {"City": "Bogota"}]}

    client.get.side_effect = fake_get
    [_, get_field_distribution, _] = make_zoho_tools(client)

    result = get_field_distribution.invoke({"field": "City"})

    assert "buckets" in result
    assert "render_hint" in result
    assert result["render_hint"]["type"] == "bar"
    assert result["render_hint"]["data"] == result["buckets"]
    assert "title" in result["render_hint"]


def test_query_customers_validates_filter_keys() -> None:
    """If a filter key doesn't exist in the module, return error with suggestions."""
    from unittest.mock import MagicMock
    client = MagicMock()
    client.get.return_value = {
        "fields": [{"api_name": "Tier"}, {"api_name": "City"}],
    }
    [query_customers, _, _] = make_zoho_tools(client)

    result = query_customers.invoke({
        "filters": {"NonExistent": "value"},
        "limit": 50,
    })

    assert result["count"] == 0
    assert result["records"] == []
    assert "error" in result
    assert "NonExistent" in result["error"]
    assert "suggestions" in result
