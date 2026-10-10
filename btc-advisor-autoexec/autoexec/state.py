"""On-disk state that must survive restarts.

* ``HALT`` file  — equity-halt latch (mechanic #6). Created when equity is at
  or below the threshold; while it exists every entry is blocked, whatever the
  equity is now. Re-enable is manual: delete the file (``rm``) or
  ``python3 -m autoexec halt-clear --yes``.
* ``state.json`` — daily-cap latch (``daily_cap_hit_day``), the last place
  attempt (post-place cooldown), and the last known guard snapshot.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class HaltLatch:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    @property
    def active(self) -> bool:
        return self.path.exists()

    def read(self) -> Optional[Dict[str, Any]]:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, ValueError):
            return {"note": "halt file present but unreadable"}

    def latch(self, *, equity: float, threshold: float, reason: str) -> Dict[str, Any]:
        if self.path.exists():
            existing = self.read() or {}
            return existing
        record = {"latched_at": _now_iso(), "equity": equity, "threshold": threshold, "reason": reason}
        _atomic_write(self.path, json.dumps(record, indent=2) + "\n")
        return record

    def clear(self) -> bool:
        """Manual re-enable. Returns True if a latch was removed."""

        if self.path.exists():
            self.path.unlink()
            return True
        return False


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
            except (OSError, ValueError):
                self._data = {}
        if not isinstance(self._data, dict):
            self._data = {}

    def _save(self) -> None:
        _atomic_write(self.path, json.dumps(self._data, indent=2, default=str) + "\n")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._data)

    # daily cap latch ---------------------------------------------------------

    def daily_cap_hit_day(self) -> Optional[str]:
        return self._data.get("daily_cap_hit_day")

    def latch_daily_cap(self, day_iso: str, pnl: float) -> None:
        self._data["daily_cap_hit_day"] = day_iso
        self._data["daily_cap_hit_at"] = _now_iso()
        self._data["daily_cap_hit_pnl"] = pnl
        self._save()

    # post-place cooldown -----------------------------------------------------

    def note_place_attempt(self, *, at_epoch: float, request_id: Optional[str], outcome: str) -> None:
        self._data["last_place_attempt"] = {"at_epoch": at_epoch, "request_id": request_id, "outcome": outcome}
        self._save()

    def last_place_attempt(self) -> Optional[Dict[str, Any]]:
        v = self._data.get("last_place_attempt")
        return v if isinstance(v, dict) else None

    def clear_place_attempt(self) -> None:
        if "last_place_attempt" in self._data:
            del self._data["last_place_attempt"]
            self._save()
