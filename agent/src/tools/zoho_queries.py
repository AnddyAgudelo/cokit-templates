"""Zoho CRM query tools. All tools are READ-ONLY by design — no write tools exist."""
from typing import Any

from langchain.tools import tool

from src.zoho.client import ZohoClient


# Default fields surfaced to the LLM. Excludes Email/Phone/Address to keep PII out of context.
DEFAULT_QUERY_FIELDS = ["id", "Last_Name", "First_Name", "Account_Name"]


def _build_criteria(filters: dict[str, str]) -> str:
    """Build a Zoho COQL-like criteria string: (k:equals:v)and(k2:equals:v2)."""
    return "and".join(f"({k}:equals:{v})" for k, v in filters.items())


def make_zoho_tools(client: ZohoClient) -> list:
    """Bind tools to a ZohoClient instance via closure."""

    @tool
    def query_customers(
        filters: dict[str, str],
        limit: int = 50,
        fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Query Zoho contacts matching `filters`.
        `filters` example: {"Tier": "premium", "City": "Bogota"}.
        Returns aggregate count and a list of records.
        Default `fields` exclude PII (email, phone, address) — pass explicit
        `fields` ONLY when the user explicitly drills down on individual contacts.
        """
        if not filters:
            return {
                "count": 0,
                "records": [],
                "error": "filters is required (e.g., {'Tier': 'premium'})",
            }

        capped_limit = min(limit, 200)
        criteria = _build_criteria(filters)
        select = ",".join(fields or DEFAULT_QUERY_FIELDS)

        try:
            response = client.get(
                "Contacts/search",
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
        return {
            "count": info.get("count", len(records)),
            "records": records[:capped_limit],
        }

    @tool
    def get_field_distribution(
        field: str,
        filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate distribution of `field` over the (filtered) Contacts set.
        Returns: {"field": str, "buckets": [{"label": str, "count": int}, ...], "total": int}.
        Prefer this over query_customers + manual aggregation.
        """
        params: dict[str, Any] = {"fields": f"id,{field}", "per_page": 200}
        if filters:
            params["criteria"] = _build_criteria(filters)
            endpoint = "Contacts/search"
        else:
            endpoint = "Contacts"

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
        return {"field": field, "buckets": buckets, "total": len(records)}

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
