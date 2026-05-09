from unittest.mock import MagicMock, call

from src.tools.zoho_queries import make_zoho_tools


def _client_returning(payload: dict) -> MagicMock:
    """Mock client that returns the given payload for every .get() call.
    Ensures info.more_records=False so pagination terminates on first page."""
    if "info" not in payload:
        payload = {**payload, "info": {**payload.get("info", {}), "more_records": False}}
    elif "more_records" not in payload["info"]:
        payload["info"] = {**payload["info"], "more_records": False}
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
        # Distribution call — pagination: first page has data, no more_records
        return {
            "data": [{"City": "Bogota"}, {"City": "Medellin"}, {"City": "Bogota"}],
            "info": {"more_records": False},
        }

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


# ---------------------------------------------------------------------------
# New tests: pagination
# ---------------------------------------------------------------------------

def test_paginated_get_accumulates_multiple_pages() -> None:
    """_paginated_get fetches pages until more_records=False."""
    from src.tools.zoho_queries import _paginated_get

    page_responses = [
        {"data": [{"id": "1"}, {"id": "2"}], "info": {"more_records": True}},
        {"data": [{"id": "3"}, {"id": "4"}], "info": {"more_records": True}},
        {"data": [{"id": "5"}], "info": {"more_records": False}},
    ]
    client = MagicMock()
    client.get.side_effect = page_responses

    records, truncated = _paginated_get(client, "Contacts", {"fields": "id"})

    assert len(records) == 5
    assert [r["id"] for r in records] == ["1", "2", "3", "4", "5"]
    assert truncated is False
    assert client.get.call_count == 3


def test_paginated_get_truncates_at_max_pages() -> None:
    """_paginated_get returns truncated=True when max_pages is hit."""
    from src.tools.zoho_queries import _paginated_get

    # Always returns more_records=True — simulates an enormous dataset
    client = MagicMock()
    client.get.return_value = {
        "data": [{"id": "x"}],
        "info": {"more_records": True},
    }

    records, truncated = _paginated_get(client, "Contacts", {"fields": "id"}, max_pages=3)

    assert truncated is True
    assert len(records) == 3  # 1 record per page × 3 pages
    assert client.get.call_count == 3


# ---------------------------------------------------------------------------
# New tests: layout filter
# ---------------------------------------------------------------------------

def test_query_customers_resolves_layout_name_to_id() -> None:
    """layout='Empresas' is resolved to its id and appended to criteria."""
    client = MagicMock()

    def fake_get(path, params=None, **kwargs):
        if path == "settings/layouts":
            return {
                "layouts": [
                    {"id": "4823391000299562269", "name": "Empresas"},
                    {"id": "4823391000000091023", "name": "Standard"},
                ]
            }
        # Data fetch — pagination terminates immediately
        return {"data": [], "info": {"more_records": False}}

    client.get.side_effect = fake_get
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({
        "layout": "Empresas",
        "module": "Deals",
    })

    # Find the data fetch call and verify criteria contains layout id
    data_calls = [
        c for c in client.get.call_args_list
        if c.args[0] == "Deals/search"
    ]
    assert len(data_calls) == 1
    criteria = data_calls[0].kwargs["params"]["criteria"]
    assert "4823391000299562269" in criteria
    assert "Layout:equals" in criteria


def test_query_customers_returns_error_for_unknown_layout() -> None:
    """An unrecognised layout name returns an error with available names."""
    client = MagicMock()

    def fake_get(path, params=None, **kwargs):
        if path == "settings/layouts":
            return {
                "layouts": [
                    {"id": "111", "name": "Empresas"},
                    {"id": "222", "name": "Standard"},
                    {"id": "333", "name": "Técnicos"},
                ]
            }
        return {"data": [], "info": {"more_records": False}}

    client.get.side_effect = fake_get
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({
        "layout": "Desconocido",
        "module": "Deals",
    })

    assert result["count"] == 0
    assert "error" in result
    assert "Desconocido" in result["error"]
    assert "suggestions" in result
    assert set(result["suggestions"]) == {"Empresas", "Standard", "Técnicos"}


# ---------------------------------------------------------------------------
# New tests: Created_Time date range filter
# ---------------------------------------------------------------------------

def test_query_customers_created_after_clause_in_criteria() -> None:
    """created_after produces a Created_Time:greater_equal clause in criteria.

    Date-only inputs (YYYY-MM-DD) are auto-padded to a full ISO datetime
    because Zoho /search rejects bare dates with HTTP 400.
    """
    client = _client_returning({"data": [], "info": {"more_records": False}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({
        "created_after": "2026-01-01",
        "module": "Deals",
    })

    call_args = client.get.call_args
    criteria = call_args.kwargs["params"]["criteria"]
    # Date-only input is normalized to full ISO datetime with UTC offset
    assert "(Created_Time:greater_equal:2026-01-01T00:00:00+00:00)" in criteria


def test_created_after_iso_datetime_passes_through_unchanged() -> None:
    """If created_after already includes a 'T' time, it is not re-padded."""
    client = _client_returning({"data": [], "info": {"more_records": False}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({
        "created_after": "2026-01-01T15:30:00+00:00",
        "module": "Deals",
    })

    criteria = client.get.call_args.kwargs["params"]["criteria"]
    assert "(Created_Time:greater_equal:2026-01-01T15:30:00+00:00)" in criteria


def test_created_before_date_only_normalized_to_end_of_day() -> None:
    """A date-only created_before maps to T23:59:59+00:00 (end of day in UTC)."""
    client = _client_returning({"data": [], "info": {"more_records": False}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({
        "created_before": "2026-05-09",
        "module": "Deals",
    })

    criteria = client.get.call_args.kwargs["params"]["criteria"]
    assert "(Created_Time:less_equal:2026-05-09T23:59:59+00:00)" in criteria


def test_query_customers_created_before_clause_in_criteria() -> None:
    """created_before produces a Created_Time:less_equal clause in criteria."""
    client = _client_returning({"data": [], "info": {"more_records": False}})
    [query_customers, *_] = make_zoho_tools(client)

    query_customers.invoke({
        "created_before": "2026-05-01T00:00:00+00:00",
        "module": "Deals",
    })

    call_args = client.get.call_args
    criteria = call_args.kwargs["params"]["criteria"]
    assert "(Created_Time:less_equal:2026-05-01T00:00:00+00:00)" in criteria


# ---------------------------------------------------------------------------
# Bug fix 3: _paginated_get graceful error handling after first page
# ---------------------------------------------------------------------------

def test_paginated_get_graceful_error_after_first_page() -> None:
    """If page 1 succeeds but page 2 raises, return page-1 records with truncated=True."""
    from src.tools.zoho_queries import _paginated_get

    client = MagicMock()
    client.get.side_effect = [
        {"data": [{"id": "1"}, {"id": "2"}], "info": {"more_records": True}},
        RuntimeError("HTTP 400 — page limit exceeded"),
    ]

    records, truncated = _paginated_get(client, "Deals/search", {"criteria": "(Layout:equals:123)"})

    assert records == [{"id": "1"}, {"id": "2"}]
    assert truncated is True
    assert client.get.call_count == 2


def test_paginated_get_propagates_page1_error() -> None:
    """If page 1 itself raises, the exception propagates (no records to salvage)."""
    from src.tools.zoho_queries import _paginated_get

    client = MagicMock()
    client.get.side_effect = RuntimeError("zoho down")

    import pytest
    with pytest.raises(RuntimeError, match="zoho down"):
        _paginated_get(client, "Deals/search", {"criteria": "(Layout:equals:123)"})


def test_query_customers_no_filters_but_layout_is_valid() -> None:
    """query_customers succeeds with only layout= and no filters dict."""
    client = MagicMock()

    def fake_get(path, params=None, **kwargs):
        if path == "settings/layouts":
            return {
                "layouts": [{"id": "4823391000299562269", "name": "Empresas"}]
            }
        return {"data": [{"id": "42", "Last_Name": "Test"}], "info": {"more_records": False}}

    client.get.side_effect = fake_get
    [query_customers, *_] = make_zoho_tools(client)

    result = query_customers.invoke({
        "layout": "Empresas",
        "module": "Deals",
    })

    assert "error" not in result
    assert result["count"] == 1
    assert result["records"][0]["id"] == "42"
