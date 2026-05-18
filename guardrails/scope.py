"""
Scope Enforcement — detects off-topic queries and redirects to finance.

Uses a keyword allowlist and off-topic patterns.  When unsure, errs on
the side of letting the message through (false positives are worse than
false negatives for user experience).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScopeResult:
    """Result of a scope check."""
    in_scope: bool = True
    canned_response: Optional[str] = None


class ScopeEnforcer:
    """Determines whether a user message is finance-related."""

    def is_in_scope(self, message: str) -> ScopeResult:
        """Check if *message* is within FinBot's financial scope."""
        # Placeholder — considers everything in scope
        return ScopeResult(in_scope=True)
