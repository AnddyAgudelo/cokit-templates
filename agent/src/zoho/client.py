"""Zoho CRM read-only HTTP client. ALL Zoho calls flow through this module."""
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

from src.zoho.audit import AuditLogger
from src.zoho.cache import SessionCache


@dataclass(frozen=True)
class ZohoConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    api_domain: str
    accounts_domain: str

    @classmethod
    def from_env(cls) -> "ZohoConfig":
        required = {
            "ZOHO_CLIENT_ID": os.environ.get("ZOHO_CLIENT_ID"),
            "ZOHO_CLIENT_SECRET": os.environ.get("ZOHO_CLIENT_SECRET"),
            "ZOHO_REFRESH_TOKEN": os.environ.get("ZOHO_REFRESH_TOKEN"),
            "ZOHO_API_DOMAIN": os.environ.get("ZOHO_API_DOMAIN"),
            "ZOHO_ACCOUNTS_DOMAIN": os.environ.get("ZOHO_ACCOUNTS_DOMAIN"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required Zoho env vars: {missing}")
        return cls(
            client_id=required["ZOHO_CLIENT_ID"],
            client_secret=required["ZOHO_CLIENT_SECRET"],
            refresh_token=required["ZOHO_REFRESH_TOKEN"],
            api_domain=required["ZOHO_API_DOMAIN"].rstrip("/"),
            accounts_domain=required["ZOHO_ACCOUNTS_DOMAIN"].rstrip("/"),
        )


class RateLimiter:
    """Per-minute token bucket. Blocks until window resets if exhausted."""

    def __init__(self, per_minute: int):
        self._capacity = per_minute
        self._tokens = per_minute
        self._window_start = time.monotonic()
        self._lock = Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                if now - self._window_start >= 60.0:
                    self._tokens = self._capacity
                    self._window_start = now
                if self._tokens > 0:
                    self._tokens -= 1
                    return
                sleep_for = 60.0 - (now - self._window_start)
            time.sleep(max(sleep_for, 0))


class ZohoClient:
    """Read-only Zoho client. NO post/put/delete methods on purpose."""

    def __init__(
        self,
        config: ZohoConfig,
        *,
        audit: AuditLogger,
        cache: SessionCache,
        http: httpx.Client | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        self._config = config
        self._audit = audit
        self._cache = cache
        self._http = http or httpx.Client(timeout=10.0)
        self._rate_limiter = rate_limiter or RateLimiter(per_minute=90)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = Lock()

    def _refresh_token_if_needed(self) -> None:
        with self._token_lock:
            if self._access_token and time.monotonic() < self._token_expires_at - 30:
                return

            resp = self._http.post(
                f"{self._config.accounts_domain}/oauth/v2/token",
                data={
                    "refresh_token": self._config.refresh_token,
                    "client_id": self._config.client_id,
                    "client_secret": self._config.client_secret,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            body = resp.json()

            if "access_token" not in body:
                raise RuntimeError(
                    f"OAuth token refresh failed: response missing 'access_token'. "
                    f"Body: {body}"
                )

            self._access_token = body["access_token"]
            expires_in = body.get("expires_in", 3600)
            self._token_expires_at = time.monotonic() + expires_in

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        cache_key: str | None = None,
        cache_ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        """
        Read-only Zoho GET with caching, rate limiting, and audit logging.
        `cache_key=None` disables caching for this call.
        """
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        self._rate_limiter.acquire()
        self._refresh_token_if_needed()

        url = f"{self._config.api_domain}/crm/v6/{path.lstrip('/')}"
        t0 = time.monotonic()
        try:
            resp = self._http.get(
                url,
                headers={"Authorization": f"Zoho-oauthtoken {self._access_token}"},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self._audit.log_error(path, params, e)
            raise

        latency_ms = (time.monotonic() - t0) * 1000
        self._audit.log_success(path, params, data, latency_ms=latency_ms)

        if cache_key:
            self._cache.set(cache_key, data, ttl_seconds=cache_ttl_seconds)

        return data
