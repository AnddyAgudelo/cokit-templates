import time
from pathlib import Path

import httpx
import pytest

from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache
from src.zoho.client import RateLimiter, ZohoClient, ZohoConfig


@pytest.fixture
def config() -> ZohoConfig:
    return ZohoConfig(
        client_id="test-id",
        client_secret="test-secret",
        refresh_token="test-refresh",
        api_domain="https://www.zohoapis.com",
        accounts_domain="https://accounts.zoho.com",
    )


@pytest.fixture
def audit(tmp_path: Path) -> AuditLogger:
    return AuditLogger(audit_dir=tmp_path)


@pytest.fixture
def cache() -> SessionCache:
    return SessionCache()


def test_zoho_config_from_env_missing_var_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_API_DOMAIN", raising=False)
    monkeypatch.delenv("ZOHO_ACCOUNTS_DOMAIN", raising=False)
    with pytest.raises(RuntimeError, match="Missing"):
        ZohoConfig.from_env()


def test_zoho_config_from_env_strips_trailing_slash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZOHO_CLIENT_ID", "id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("ZOHO_API_DOMAIN", "https://www.zohoapis.com/")
    monkeypatch.setenv("ZOHO_ACCOUNTS_DOMAIN", "https://accounts.zoho.com/")
    cfg = ZohoConfig.from_env()
    assert cfg.api_domain == "https://www.zohoapis.com"
    assert cfg.accounts_domain == "https://accounts.zoho.com"


def test_refresh_token_calls_oauth_endpoint(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "new-token", "expires_in": 3600},
    )
    client = ZohoClient(config, audit=audit, cache=cache)
    client._refresh_token_if_needed()
    assert client._access_token == "new-token"


def test_refresh_token_skipped_when_token_fresh(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    client = ZohoClient(config, audit=audit, cache=cache)
    client._access_token = "still-valid"
    client._token_expires_at = time.monotonic() + 3600

    client._refresh_token_if_needed()
    assert len(httpx_mock.get_requests()) == 0
    assert client._access_token == "still-valid"


def test_rate_limiter_allows_under_capacity() -> None:
    limiter = RateLimiter(per_minute=3)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()


def test_rate_limiter_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.client.time.monotonic", lambda: fake_time[0])
    monkeypatch.setattr("src.zoho.client.time.sleep", lambda _: None)

    limiter = RateLimiter(per_minute=2)
    limiter.acquire()
    limiter.acquire()
    fake_time[0] = 1061.0
    limiter.acquire()


def test_refresh_token_raises_on_zoho_200_error(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    """Zoho returns HTTP 200 with {error: ...} for some auth failures (e.g., invalid_code).
    The client must surface this as a clear RuntimeError, not an opaque KeyError."""
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        status_code=200,
        json={"error": "invalid_code"},
    )
    client = ZohoClient(config, audit=audit, cache=cache)
    with pytest.raises(RuntimeError, match="OAuth token refresh failed"):
        client._refresh_token_if_needed()


def test_refresh_token_sets_expires_at(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    """The expiry timestamp drives all future freshness checks; lock down its contract."""
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "x", "expires_in": 3600},
    )
    client = ZohoClient(config, audit=audit, cache=cache)
    before = time.monotonic()
    client._refresh_token_if_needed()
    # Should be ~3600s in the future (allow ±5s of test timing slop)
    assert client._token_expires_at >= before + 3595
    assert client._token_expires_at <= before + 3605


def test_get_returns_response_and_audits(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search?criteria=%28Tier%3Aequals%3Apremium%29",
        method="GET",
        json={"data": [{"id": "1", "Last_Name": "Alice"}]},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    result = client.get("Contacts/search", params={"criteria": "(Tier:equals:premium)"})

    assert result == {"data": [{"id": "1", "Last_Name": "Alice"}]}
    audit_files = list(tmp_path.glob("zoho-audit-*.jsonl"))
    assert len(audit_files) == 1
    assert "Contacts/search" in audit_files[0].read_text()


def test_get_uses_cache_on_second_call(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/settings/fields?module=Contacts",
        method="GET",
        json={"fields": [{"api_name": "City"}]},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    client.get(
        "settings/fields",
        params={"module": "Contacts"},
        cache_key="fields:Contacts",
    )
    client.get(
        "settings/fields",
        params={"module": "Contacts"},
        cache_key="fields:Contacts",
    )

    # Token POST + 1 GET = 2 requests; cache hit means second GET didn't fire
    assert len(httpx_mock.get_requests()) == 2


def test_get_logs_error_on_http_failure(
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
    tmp_path: Path,
) -> None:
    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "test-token", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        status_code=500,
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("Contacts/search")

    audit_files = list(tmp_path.glob("zoho-audit-*.jsonl"))
    assert len(audit_files) == 1
    assert "error" in audit_files[0].read_text()


def test_get_retries_once_on_429(
    monkeypatch: pytest.MonkeyPatch,
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _: None)

    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "t", "expires_in": 3600},
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        status_code=429,
    )
    httpx_mock.add_response(
        url="https://www.zohoapis.com/crm/v6/Contacts/search",
        method="GET",
        json={"data": []},
    )

    client = ZohoClient(config, audit=audit, cache=cache)
    result = client.get("Contacts/search")
    assert result == {"data": []}


def test_get_gives_up_after_3_attempts_on_429(
    monkeypatch: pytest.MonkeyPatch,
    config: ZohoConfig,
    audit: AuditLogger,
    cache: SessionCache,
    httpx_mock,
) -> None:
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _: None)

    httpx_mock.add_response(
        url="https://accounts.zoho.com/oauth/v2/token",
        method="POST",
        json={"access_token": "t", "expires_in": 3600},
    )
    for _ in range(3):
        httpx_mock.add_response(
            url="https://www.zohoapis.com/crm/v6/Contacts/search",
            method="GET",
            status_code=429,
        )

    client = ZohoClient(config, audit=audit, cache=cache)
    with pytest.raises(httpx.HTTPStatusError):
        client.get("Contacts/search")
