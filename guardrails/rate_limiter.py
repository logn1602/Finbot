"""
Rate Limiter — per-session sliding-window throttle.

Limits:
  - 15 messages per minute   (prevents rapid-fire spamming)
  - 100 messages per hour    (prevents sustained abuse)

Uses in-memory timestamp lists.  State is expected to live in
Streamlit's st.session_state so it survives reruns but resets on
redeploy (which is acceptable).

The RateLimiter class itself is stateless — callers pass in and
receive back the timestamps dict, making it easy to test without
Streamlit.
"""

import time
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate-limit check."""
    allowed: bool = True
    canned_response: Optional[str] = None
    retry_after_seconds: Optional[int] = None


# ── Canned responses ─────────────────────────────────────────────

_MINUTE_RESPONSE = (
    "You're sending messages quite fast — give me a moment to "
    "catch up! Try again in a few seconds."
)

_HOUR_RESPONSE = (
    "You've been very active this session! Take a short break "
    "and come back — I'll be here."
)

# ── Default limits ───────────────────────────────────────────────

_PER_MINUTE = 15
_PER_HOUR = 100
_MINUTE_WINDOW = 60        # seconds
_HOUR_WINDOW = 3600        # seconds


class RateLimiter:
    """Sliding-window rate limiter keyed by session ID.

    Internally stores ``{session_id: [timestamp, ...]}`` in a plain dict.
    The dict should be persisted across Streamlit reruns by storing it in
    ``st.session_state``.
    """

    def __init__(self, per_minute: int = _PER_MINUTE, per_hour: int = _PER_HOUR):
        self.per_minute = per_minute
        self.per_hour = per_hour
        # session_id → list of Unix timestamps
        self._store: dict[str, list[float]] = {}

    def check_rate(self, session_id: str) -> RateLimitResult:
        """Check whether *session_id* is within rate limits.

        Does NOT record a new request — call ``record_request()``
        separately after the message is actually processed.
        """
        now = time.time()
        timestamps = self._store.get(session_id, [])

        # Prune timestamps older than the hour window
        cutoff = now - _HOUR_WINDOW
        timestamps = [t for t in timestamps if t > cutoff]
        self._store[session_id] = timestamps

        # Check per-minute limit
        minute_cutoff = now - _MINUTE_WINDOW
        recent = sum(1 for t in timestamps if t > minute_cutoff)
        if recent >= self.per_minute:
            wait = int(timestamps[-self.per_minute] + _MINUTE_WINDOW - now) + 1
            logger.warning(
                "Rate limit hit (per-minute): session=%s count=%d",
                session_id, recent,
            )
            return RateLimitResult(
                allowed=False,
                canned_response=_MINUTE_RESPONSE,
                retry_after_seconds=max(1, wait),
            )

        # Check per-hour limit
        if len(timestamps) >= self.per_hour:
            wait = int(timestamps[-self.per_hour] + _HOUR_WINDOW - now) + 1
            logger.warning(
                "Rate limit hit (per-hour): session=%s count=%d",
                session_id, len(timestamps),
            )
            return RateLimitResult(
                allowed=False,
                canned_response=_HOUR_RESPONSE,
                retry_after_seconds=max(1, wait),
            )

        return RateLimitResult(allowed=True)

    def record_request(self, session_id: str) -> None:
        """Record a new request timestamp for *session_id*."""
        if session_id not in self._store:
            self._store[session_id] = []
        self._store[session_id].append(time.time())

    def reset(self, session_id: str) -> None:
        """Clear counters for *session_id* (used in tests)."""
        self._store.pop(session_id, None)

    def get_store(self) -> dict[str, list[float]]:
        """Return the internal store (for persisting to session_state)."""
        return self._store

    def set_store(self, store: dict[str, list[float]]) -> None:
        """Restore the store (from session_state on Streamlit rerun)."""
        self._store = store
