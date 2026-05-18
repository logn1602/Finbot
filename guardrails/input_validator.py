"""
Input Validator — prompt injection detection and profanity/abuse handling.

Injection detection uses regex pattern matching with a cumulative risk score.
Abuse handling uses severity levels so casual swearing isn't over-blocked.
"""

from dataclasses import dataclass


@dataclass
class InjectionResult:
    """Result of a prompt injection scan."""
    is_injection: bool = False
    risk_score: int = 0
    matched_patterns: list = None

    def __post_init__(self):
        if self.matched_patterns is None:
            self.matched_patterns = []


@dataclass
class AbuseResult:
    """Result of a profanity/abuse scan."""
    is_abusive: bool = False
    severity: str = "none"          # none | mild | moderate | severe
    canned_response: str | None = None


class InputValidator:
    """Checks user messages for prompt injection attempts and abusive content."""

    def check_injection(self, message: str) -> InjectionResult:
        """Scan for prompt injection patterns."""
        # Placeholder — allows everything
        return InjectionResult()

    def check_abuse(self, message: str) -> AbuseResult:
        """Scan for profanity and directed abuse."""
        # Placeholder — allows everything
        return AbuseResult()
