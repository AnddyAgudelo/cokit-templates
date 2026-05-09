import json
from datetime import UTC, datetime
from pathlib import Path

from freezegun import freeze_time

from src.zoho.audit import AuditLogger


@freeze_time("2026-05-09 12:00:00", tz_offset=0)
def test_log_success_writes_jsonl_entry(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_success(
        path="Contacts/search",
        params={"criteria": "(Tier:equals:premium)"},
        response={"data": [{"id": "1"}, {"id": "2"}]},
        latency_ms=145.7,
    )

    audit_file = tmp_path / "zoho-audit-2026-05-09.jsonl"
    assert audit_file.exists()
    entry = json.loads(audit_file.read_text().strip())
    assert entry["tool"] == "Contacts/search"
    assert entry["params"] == {"criteria": "(Tier:equals:premium)"}
    assert entry["record_count"] == 2
    assert entry["latency_ms"] == 145.7
    assert entry["status"] == "ok"


@freeze_time("2026-05-09 12:00:00", tz_offset=0)
def test_log_error_records_exception(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_error(
        path="Contacts/search",
        params={"criteria": "broken"},
        error=ValueError("simulated"),
    )

    audit_file = tmp_path / "zoho-audit-2026-05-09.jsonl"
    entry = json.loads(audit_file.read_text().strip())
    assert entry["status"] == "error"
    assert entry["error"] == "simulated"


def test_log_appends_multiple_entries(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    for i in range(3):
        logger.log_success(
            path=f"call-{i}",
            params=None,
            response={"data": []},
            latency_ms=10.0,
        )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    lines = (tmp_path / f"zoho-audit-{today}.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3


def test_log_handles_response_without_data_list(tmp_path: Path) -> None:
    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_success(
        path="settings/fields",
        params={"module": "Contacts"},
        response={"fields": [{"api_name": "x"}]},
        latency_ms=20.0,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    entry = json.loads(
        (tmp_path / f"zoho-audit-{today}.jsonl").read_text().strip()
    )
    assert entry["record_count"] == 0


def test_log_success_with_non_serializable_params(tmp_path: Path) -> None:
    """Non-JSON values in params should be serialized via str() fallback, not crash."""
    from datetime import date

    logger = AuditLogger(audit_dir=tmp_path)
    logger.log_success(
        path="Contacts/search",
        params={"modified_after": date(2026, 1, 1)},
        response={"data": []},
        latency_ms=5.0,
    )

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    entry = json.loads(
        (tmp_path / f"zoho-audit-{today}.jsonl").read_text().strip()
    )
    assert entry["status"] == "ok"
    assert "modified_after" in entry["params"]
    # date object should be stringified by default=str fallback
    assert entry["params"]["modified_after"] == "2026-01-01"
