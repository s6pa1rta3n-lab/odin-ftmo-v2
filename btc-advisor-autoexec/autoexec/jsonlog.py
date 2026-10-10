"""Structured JSON-lines logging with secret redaction.

Every request, decision, guard value, order payload, and broker response goes
through :func:`JsonLogger.emit`. Keys that look like secrets are redacted
recursively before the line is written, so a token can never reach the log
even if a caller passes a raw header dict by mistake.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SECRET_KEY_FRAGMENTS = ("token", "auth", "secret", "password", "api_key", "apikey", "api-key")
REDACTED = "[REDACTED]"


def redact(value: Any, _key: str = "") -> Any:
    """Return a copy of ``value`` with secret-looking keys replaced."""

    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k)
            if any(frag in ks.lower() for frag in SECRET_KEY_FRAGMENTS):
                out[ks] = REDACTED
            else:
                out[ks] = redact(v, ks)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


def _default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return redact(vars(obj))
    return str(obj)


class JsonLogger:
    """Append-only JSONL writer that also mirrors to stdout."""

    def __init__(self, path: Optional[str], *, stdout: bool = True, token: Optional[str] = None) -> None:
        self.path = Path(path) if path else None
        self.stdout = stdout
        self._lock = threading.Lock()
        self._token = token or ""
        self.records: List[Dict[str, Any]] = []  # in-memory tail for tests and /status
        self._max_records = 500

    def emit(self, event: str, **data: Any) -> Dict[str, Any]:
        record: Dict[str, Any] = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
        record.update(redact(data))
        line = json.dumps(record, default=_default, separators=(",", ":"))
        if self._token and self._token in line:
            # Defence in depth: a token that slipped through a non-secret key.
            line = line.replace(self._token, REDACTED)
        with self._lock:
            self.records.append(record)
            if len(self.records) > self._max_records:
                del self.records[: len(self.records) - self._max_records]
            if self.stdout:
                sys.stdout.write(line + "\n")
                sys.stdout.flush()
            if self.path is not None:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a", encoding="utf-8") as fh:
                        fh.write(line + "\n")
                except OSError as exc:
                    sys.stderr.write(f"autoexec: cannot write log {self.path}: {exc}\n")
        return record
