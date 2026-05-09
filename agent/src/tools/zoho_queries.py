"""Zoho CRM query tools. All tools are READ-ONLY by design — no write tools exist."""
from typing import Any

from langchain.tools import tool

from src.zoho.client import ZohoClient


# Default fields surfaced to the LLM. Excludes Email/Phone/Address to keep PII out of context.
DEFAULT_QUERY_FIELDS = ["id", "Last_Name", "First_Name", "Account_Name"]


_COQL_RESERVED = (":", "(", ")")


def _build_criteria(filters: dict[str, str]) -> str:
    """Build a Zoho COQL-like criteria string: (k:equals:v)and(k2:equals:v2).

    Raises ValueError if any value contains COQL-reserved chars; Zoho's
    documented escape rules for `equals` are unreliable, so we refuse rather
    than silently producing a malformed query.
    """
    for k, v in filters.items():
        if any(ch in v for ch in _COQL_RESERVED):
            raise ValueError(
                f"filter value for {k!r} contains COQL-reserved char "
                f"(one of {_COQL_RESERVED}): {v!r}"
            )
    return "and".join(f"({k}:equals:{v})" for k, v in filters.items())


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


def make_zoho_tools(client: ZohoClient) -> list:
    """Bind tools to a ZohoClient instance via closure."""

    @tool
    def query_customers(
        filters: dict[str, str],
        limit: int = 50,
        fields: list[str] | None = None,
        module: str = "Contacts",
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
        """
        if not filters:
            return {
                "count": 0,
                "records": [],
                "error": "filters is required (e.g., {'Tier': 'premium'})",
            }

        # Validate filter keys exist in module schema
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

        capped_limit = min(limit, 200)
        criteria = _build_criteria(filters)
        select = ",".join(fields or DEFAULT_QUERY_FIELDS)

        try:
            response = client.get(
                f"{module}/search",
                params={
                    "criteria": criteria,
                    "fields": select,
                    "per_page": capped_limit,
                },
            )
        except Exception as e:
            return {"count": 0, "records": [], "error": str(e)}

        records = response.get("data", []) or []
        info = response.get("info", {}) or {}
        total = info.get("count", len(records))
        return {
            "count": total,
            "records": records[:capped_limit],
            "truncated": len(records) >= capped_limit and total > capped_limit,
        }

    @tool
    def get_field_distribution(
        field: str,
        filters: dict[str, str] | None = None,
        module: str = "Contacts",
    ) -> dict[str, Any]:
        """
        Aggregate distribution of `field` over the (filtered) records in `module`.
        Returns: {"field": str, "buckets": [...], "total": int}.
        Validates `field` exists in the module schema; if not, returns an error
        with suggested field names. Prefer this over query_customers + manual aggregation.
        `module` defaults to "Contacts". Common values: "Contacts", "Accounts",
        "Deals", "Leads". Use "Accounts" for companies/empresas.
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

        params: dict[str, Any] = {"fields": f"id,{field}", "per_page": 200}
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
            params["criteria"] = _build_criteria(filters)
            endpoint = f"{module}/search"
        else:
            endpoint = module

        try:
            response = client.get(endpoint, params=params)
        except Exception as e:
            return {"field": field, "buckets": [], "total": 0, "error": str(e)}

        records = response.get("data", []) or []
        counts: dict[str, int] = {}
        for rec in records:
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
            "total": len(records),
            "truncated": len(records) >= 200,
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
