"""Zoho CRM query tools. All tools are READ-ONLY by design — no write tools exist."""
from typing import Any

from langchain.tools import tool

from src.zoho.client import ZohoClient


# Default fields surfaced to the LLM. Excludes Email/Phone/Address to keep PII out of context.
DEFAULT_QUERY_FIELDS = ["id", "Last_Name", "First_Name", "Account_Name"]


# Chars that need backslash-escaping inside a COQL `equals` value.
# Zoho docs: https://www.zoho.com/crm/developer/docs/api/v6/COQL-Overview.html
# Backslash itself escaped first to avoid double-escaping.
_COQL_VALUE_ESCAPES = ("\\", "(", ")", ",")


def _escape_coql_value(value: str) -> str:
    """Backslash-escape COQL special chars in a filter value."""
    out = value
    for ch in _COQL_VALUE_ESCAPES:
        out = out.replace(ch, "\\" + ch)
    return out


def _build_criteria(filters: dict[str, str]) -> str:
    """Build a Zoho COQL-like criteria string: (k:equals:v)and(k2:equals:v2).

    Values are escaped so picklist labels with parens or commas (e.g.
    'Standard (Standard)') survive transport to Zoho. The colon (`:`) is
    the operator delimiter and has no documented escape — values containing
    it are still rejected explicitly.
    """
    for k, v in filters.items():
        if ":" in v:
            raise ValueError(
                f"filter value for {k!r} contains a colon "
                f"(COQL operator delimiter, no escape supported): {v!r}"
            )
    return "and".join(
        f"({k}:equals:{_escape_coql_value(v)})"
        for k, v in filters.items()
    )


def _fetch_field_api_names(client: ZohoClient, module: str) -> set[str]:
    """Return the set of api_names defined in a Zoho module. Cached 1h."""
    try:
        response = client.get(
            "settings/fields",
            params={"module": module},
            cache_key=f"fields:{module}",
            cache_ttl_seconds=3600,
        )
    except Exception:
        return set()
    return {
        f.get("api_name")
        for f in (response.get("fields") or [])
        if f.get("api_name")
    }


def _suggest_similar(field: str, valid: set[str], n: int = 5) -> list[str]:
    """Find up to n field names similar to `field` (case-insensitive substring match)."""
    field_lower = field.lower()
    matches = [v for v in valid if field_lower in v.lower() or v.lower() in field_lower]
    if matches:
        return sorted(matches)[:n]
    # Fallback: just return some valid fields so the LLM has a hint
    return sorted(valid)[:n]


def _paginated_get(
    client: ZohoClient,
    endpoint: str,
    params: dict[str, Any],
    max_pages: int = 25,
) -> tuple[list[dict], bool]:
    """Fetch all pages from a Zoho list/search endpoint. Returns (records, truncated).

    Loops until info.more_records is false OR max_pages reached. Concatenates
    `data` arrays. Each page is one client.get call (rate-limited + audited).
    """
    all_records: list[dict] = []
    for page in range(1, max_pages + 1):
        page_params = dict(params)
        page_params["page"] = page
        page_params["per_page"] = 200
        response = client.get(endpoint, params=page_params)
        records = response.get("data", []) or []
        all_records.extend(records)
        info = response.get("info", {}) or {}
        if not info.get("more_records"):
            return all_records, False
    # Hit the cap with more pages remaining
    return all_records, True


def _resolve_layout_id(
    client: ZohoClient, module: str, layout_name: str
) -> tuple[str | None, list[str]]:
    """Resolve a layout name to its id for a module. Returns (layout_id_or_None, available_names)."""
    try:
        response = client.get(
            "settings/layouts",
            params={"module": module},
            cache_key=f"layouts:{module}",
            cache_ttl_seconds=3600,
        )
    except Exception:
        return None, []
    layouts = response.get("layouts", []) or []
    available = [L.get("name") for L in layouts if L.get("name")]
    target = layout_name.lower()
    for L in layouts:
        if (L.get("name") or "").lower() == target:
            return L.get("id"), available
    return None, available


def make_zoho_tools(client: ZohoClient) -> list:
    """Bind tools to a ZohoClient instance via closure."""

    @tool
    def query_customers(
        filters: dict[str, str] | None = None,
        limit: int = 50,
        fields: list[str] | None = None,
        module: str = "Contacts",
        layout: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> dict[str, Any]:
        """
        Query Zoho records matching `filters` in the specified `module`.
        `filters` example: {"Tier": "premium", "City": "Bogota"}.
        Returns aggregate count and a list of records.
        Validates filter keys against the module schema; returns suggestions
        if any key is unknown.
        Default `fields` exclude PII (email, phone, address) — pass explicit
        `fields` ONLY when the user explicitly drills down on individual contacts.
        `module` defaults to "Contacts". Common values: "Contacts", "Accounts",
        "Deals", "Leads". Use "Accounts" for companies/empresas.
        `layout` filters by Zoho Layout name (Diseño), e.g. layout="Empresas".
        `created_after` and `created_before` are ISO 8601 strings for Created_Time
        filtering, e.g. created_after="2026-01-01".
        """
        # Require at least one filter dimension
        if not filters and not layout and not created_after and not created_before:
            return {
                "count": 0,
                "records": [],
                "error": (
                    "At least one of filters, layout, created_after, or "
                    "created_before is required."
                ),
            }

        # Validate filter keys exist in module schema
        if filters:
            valid_fields = _fetch_field_api_names(client, module)
            if valid_fields:
                invalid_keys = [k for k in filters if k not in valid_fields]
                if invalid_keys:
                    suggestions = {k: _suggest_similar(k, valid_fields) for k in invalid_keys}
                    return {
                        "count": 0,
                        "records": [],
                        "error": (
                            f"Filter keys not in module {module!r}: {invalid_keys}. "
                            f"Suggestions: {suggestions}"
                        ),
                        "suggestions": suggestions,
                    }

        # Resolve layout name to id if provided
        layout_id: str | None = None
        if layout:
            layout_id, available_layouts = _resolve_layout_id(client, module, layout)
            if layout_id is None:
                return {
                    "count": 0,
                    "records": [],
                    "error": (
                        f"Layout {layout!r} not found in module {module!r}. "
                        f"Available layouts: {available_layouts}"
                    ),
                    "suggestions": available_layouts,
                }

        # Build criteria parts
        criteria_parts: list[str] = []
        if filters:
            criteria_parts.append(_build_criteria(filters))
        if created_after:
            criteria_parts.append(f"(Created_Time:greater_equal:{created_after})")
        if created_before:
            criteria_parts.append(f"(Created_Time:less_equal:{created_before})")
        if layout_id:
            criteria_parts.append(f"(Layout:equals:{layout_id})")

        final_criteria = "and".join(criteria_parts) if criteria_parts else None
        select = ",".join(fields or DEFAULT_QUERY_FIELDS)

        # Choose endpoint: use /search when we have criteria, bare module otherwise
        if final_criteria:
            endpoint = f"{module}/search"
            params: dict[str, Any] = {"criteria": final_criteria, "fields": select}
        else:
            endpoint = module
            params = {"fields": select}

        try:
            all_records, truncated = _paginated_get(client, endpoint, params)
        except Exception as e:
            return {"count": 0, "records": [], "error": str(e)}

        capped_limit = min(limit, 200)
        result_records = all_records[:capped_limit]
        return {
            "count": len(all_records),
            "records": result_records,
            "truncated": truncated or len(all_records) > capped_limit,
        }

    @tool
    def get_field_distribution(
        field: str,
        filters: dict[str, str] | None = None,
        module: str = "Contacts",
        layout: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate distribution of `field` over the (filtered) records in `module`.
        Returns: {"field": str, "buckets": [...], "total": int}.
        Validates `field` exists in the module schema; if not, returns an error
        with suggested field names. Prefer this over query_customers + manual aggregation.
        `module` defaults to "Contacts". Common values: "Contacts", "Accounts",
        "Deals", "Leads". Use "Accounts" for companies/empresas.
        `layout` filters by Zoho Layout name (Diseño), e.g. layout="Empresas".
        `created_after` and `created_before` are ISO 8601 strings for Created_Time
        filtering, e.g. created_after="2026-01-01".
        """
        # Deterministic validation — prevents LLM field hallucinations
        valid_fields = _fetch_field_api_names(client, module)
        if valid_fields and field not in valid_fields:
            suggestions = _suggest_similar(field, valid_fields)
            return {
                "field": field,
                "buckets": [],
                "total": 0,
                "error": (
                    f"Field {field!r} does not exist in module {module!r}. "
                    f"Did you mean one of: {suggestions}? "
                    f"Call list_custom_fields(module={module!r}) for the full list."
                ),
                "suggestions": suggestions,
            }

        if filters:
            # Also validate filter keys
            invalid_keys = [k for k in filters if k not in valid_fields and valid_fields]
            if invalid_keys:
                suggestions = {k: _suggest_similar(k, valid_fields) for k in invalid_keys}
                return {
                    "field": field,
                    "buckets": [],
                    "total": 0,
                    "error": (
                        f"Filter keys not in module {module!r}: {invalid_keys}. "
                        f"Suggestions: {suggestions}"
                    ),
                    "suggestions": suggestions,
                }

        # Resolve layout name to id if provided
        layout_id: str | None = None
        if layout:
            layout_id, available_layouts = _resolve_layout_id(client, module, layout)
            if layout_id is None:
                return {
                    "field": field,
                    "buckets": [],
                    "total": 0,
                    "error": (
                        f"Layout {layout!r} not found in module {module!r}. "
                        f"Available layouts: {available_layouts}"
                    ),
                    "suggestions": available_layouts,
                }

        # Build criteria parts
        criteria_parts: list[str] = []
        if filters:
            criteria_parts.append(_build_criteria(filters))
        if created_after:
            criteria_parts.append(f"(Created_Time:greater_equal:{created_after})")
        if created_before:
            criteria_parts.append(f"(Created_Time:less_equal:{created_before})")
        if layout_id:
            criteria_parts.append(f"(Layout:equals:{layout_id})")

        final_criteria = "and".join(criteria_parts) if criteria_parts else None

        base_params: dict[str, Any] = {"fields": f"id,{field}"}
        if final_criteria:
            base_params["criteria"] = final_criteria
            endpoint = f"{module}/search"
        else:
            endpoint = module

        try:
            all_records, truncated = _paginated_get(client, endpoint, base_params)
        except Exception as e:
            return {"field": field, "buckets": [], "total": 0, "error": str(e)}

        counts: dict[str, int] = {}
        for rec in all_records:
            value = rec.get(field)
            label = str(value) if value is not None else "(unknown)"
            counts[label] = counts.get(label, 0) + 1

        buckets = [
            {"label": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda kv: -kv[1])
        ]
        return {
            "field": field,
            "buckets": buckets,
            "total": len(all_records),
            "truncated": truncated,
            "render_hint": {
                "type": "bar" if len(buckets) > 1 else "metric",
                "title": f"{field} distribution in {module}",
                "data": buckets,
                "source_query": (
                    f"{field} grouped over {module}"
                    + (f" filtered by {filters}" if filters else "")
                ),
            },
        }

    @tool
    def list_custom_fields(module: str = "Contacts") -> list[dict[str, Any]]:
        """
        Returns metadata of all fields in a Zoho module (default: Contacts).
        Cached for 1 hour. Use BEFORE proposing segments based on custom fields
        so you don't hallucinate field names.
        """
        try:
            response = client.get(
                "settings/fields",
                params={"module": module},
                cache_key=f"fields:{module}",
                cache_ttl_seconds=3600,
            )
        except Exception:
            return []

        fields = response.get("fields", []) or []
        return [
            {
                "api_name": f.get("api_name"),
                "display_name": f.get("display_label") or f.get("field_label"),
                "type": f.get("data_type"),
                "picklist_values": [
                    pv.get("display_value")
                    for pv in (f.get("pick_list_values") or [])
                ] or None,
            }
            for f in fields
        ]

    return [query_customers, get_field_distribution, list_custom_fields]
