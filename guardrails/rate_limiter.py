"""
Rate Limiter — per-session sliding-window throttle.

Limits:
  - 15 messages per minute
  - 100 messages per hour

Uses in-memory timestamp lists.  State is expected to live in
Streamlit's st.session_state so it survives reruns but resets on
redeploy (which is acceptable).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RateLimitResult:
    """Result of a rate-limit check."""
    allowed: bool = True
    canned_response: Optional[str] = None
    retry_after_seconds: Optional[int] = None


class RateLimiter:
    """Sliding-window rate limiter keyed by session ID."""

    def check_rate(self, session_id: str) -> RateLimitResult:
        """Check whether *session_id* is within rate limits."""
        # Placeholder — allows everything
        return RateLimitResult(allowed=True)

    def record_request(self, session_id: str) -> None:
        """Record a new request timestamp for *session_id*."""
        pass

    def reset(self, session_id: str) -> None:
        """Clear counters for *session_id* (used in tests)."""
        pass
