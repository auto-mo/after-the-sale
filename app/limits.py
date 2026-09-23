"""Per-visitor rate limiting and the daily spend budget ledger.

Both are process-local (in-memory rate limiter, file-backed budget ledger). That is
sufficient for a single-process Flask deployment behind nginx, which is how this
service is meant to run.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # POSIX file locking (stdlib); not available on Windows.
    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - dev machines here are POSIX
    _HAS_FCNTL = False


class RateLimiter:
    """Sliding-window rate limiter, keyed by visitor identifier.

    Thread-safe in-memory implementation. Good enough for a single gunicorn/Flask
    worker; if the service is ever scaled to multiple processes this would need to
    move to a shared store, which is out of scope here.
    """

    def __init__(self, per_hour: int, window_seconds: int = 3600):
        self.per_hour = per_hour
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key` and return whether it is within the limit."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits.setdefault(key, [])
            # Prune expired hits.
            i = 0
            while i < len(hits) and hits[i] < cutoff:
                i += 1
            if i:
                del hits[:i]
            if len(hits) >= self.per_hour:
                return False
            hits.append(now)
            return True

    def remaining(self, key: str) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits.get(key, [])
            active = [h for h in hits if h >= cutoff]
            return max(0, self.per_hour - len(active))


def client_ip(headers: dict, remote_addr: str | None) -> str:
    """Resolve the visitor's IP per the spec's precedence order."""
    cf = headers.get("CF-Connecting-IP")
    if cf:
        return cf.strip()
    xff = headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return remote_addr or "unknown"


@dataclass
class CostBreakdown:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    def usd(self, price_in_per_mtok: float, price_out_per_mtok: float) -> float:
        cost = self.input_tokens * price_in_per_mtok / 1_000_000
        cost += self.output_tokens * price_out_per_mtok / 1_000_000
        cost += self.cache_read_tokens * (price_in_per_mtok * 0.10) / 1_000_000
        cost += self.cache_creation_tokens * (price_in_per_mtok * 1.25) / 1_000_000
        return cost


class BudgetLedger:
    """Tracks today's (UTC) spend in a small JSON file, guarded by a file lock.

    File shape: {"date": "YYYY-MM-DD", "spent_usd": <float>}
    """

    def __init__(self, path: Path, daily_budget_usd: float):
        self.path = Path(path)
        self.daily_budget_usd = daily_budget_usd
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _read_locked(self, fh) -> dict:
        fh.seek(0)
        raw = fh.read()
        if not raw.strip():
            return {"date": self._today(), "spent_usd": 0.0}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"date": self._today(), "spent_usd": 0.0}
        if data.get("date") != self._today():
            data = {"date": self._today(), "spent_usd": 0.0}
        return data

    def _write_locked(self, fh, data: dict) -> None:
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(data))
        fh.flush()
        os.fsync(fh.fileno())

    def _with_lock(self, fn):
        # Open for read+write, creating the file if needed.
        if not self.path.exists():
            self.path.touch()
        with open(self.path, "r+", encoding="utf-8") as fh:
            if _HAS_FCNTL:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                return fn(fh)
            finally:
                if _HAS_FCNTL:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def spent_today(self) -> float:
        def _op(fh):
            data = self._read_locked(fh)
            return float(data.get("spent_usd", 0.0))

        return self._with_lock(_op)

    def budget_left(self) -> float:
        return max(0.0, self.daily_budget_usd - self.spent_today())

    def is_paused(self) -> bool:
        return self.spent_today() >= self.daily_budget_usd

    def add_cost(self, usd: float) -> float:
        """Add `usd` to today's spend and return the new total."""

        def _op(fh):
            data = self._read_locked(fh)
            data["spent_usd"] = float(data.get("spent_usd", 0.0)) + usd
            self._write_locked(fh, data)
            return data["spent_usd"]

        return self._with_lock(_op)
