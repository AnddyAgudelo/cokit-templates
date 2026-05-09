"""Append-only JSONL logger for Zoho API calls. Files rotate daily."""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, audit_dir: str | Path = "audit"):
        self._audit_dir = Path(audit_dir)
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_today(self) -> Path:
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        return self._audit_dir / f"zoho-audit-{date}.jsonl"

    def log_success(
        self,
        path: str,
        params: dict[str, Any] | None,
        response: dict[str, Any],
        *,
        latency_ms: float,
    ) -> None:
        self._write({
            "ts": datetime.now(UTC).isoformat(),
            "tool": path,
            "params": params or {},
            "record_count": self._count_records(response),
            "latency_ms": round(latency_ms, 1),
            "status": "ok",
        })

    def log_error(
        self,
        path: str,
        params: dict[str, Any] | None,
        error: Exception,
    ) -> None:
        self._write({
            "ts": datetime.now(UTC).isoformat(),
            "tool": path,
            "params": params or {},
            "status": "error",
            "error": str(error),
        })

    def _count_records(self, response: dict[str, Any]) -> int:
        if not isinstance(response, dict):
            return 0
        data = response.get("data")
        return len(data) if isinstance(data, list) else 0

    def _write(self, entry: dict[str, Any]) -> None:
        with self._path_for_today().open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
