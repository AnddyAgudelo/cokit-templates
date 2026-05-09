import pytest

from src.zoho.cache import SessionCache


def test_set_and_get_returns_stored_value() -> None:
    cache = SessionCache()
    cache.set("k", {"hello": "world"})
    assert cache.get("k") == {"hello": "world"}


def test_get_missing_key_returns_none() -> None:
    cache = SessionCache()
    assert cache.get("missing") is None


def test_expired_entry_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SessionCache(default_ttl_seconds=10)

    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.cache.time.monotonic", lambda: fake_time[0])

    cache.set("k", "v")
    fake_time[0] = 1011.0
    assert cache.get("k") is None


def test_explicit_ttl_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = SessionCache(default_ttl_seconds=10)

    fake_time = [1000.0]
    monkeypatch.setattr("src.zoho.cache.time.monotonic", lambda: fake_time[0])

    cache.set("k", "v", ttl_seconds=100)
    fake_time[0] = 1050.0
    assert cache.get("k") == "v"


def test_clear_removes_all_entries() -> None:
    cache = SessionCache()
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
