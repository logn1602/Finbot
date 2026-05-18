"""
GuardrailPipeline — orchestrates all input and output safety checks.

Input side (runs before LLM):
  1. Rate limiting
  2. Prompt injection detection
  3. Profanity / abuse detection
  4. Scope enforcement
  5. PII redaction

Output side (runs after LLM):
  1. Intent JSON validation (Pydantic)
  2. Response text cleanup
"""

from dataclasses import dataclass, field
from typing import Optional

from guardrails.pii import PIIRedactor
from guardrails.input_validator import InputValidator
from guardrails.output_validator import OutputValidator
from guardrails.scope import ScopeEnforcer
from guardrails.rate_limiter import RateLimiter


@dataclass
class GuardrailResult:
    """Unified result returned by every guardrail check."""
    passed: bool = True
    sanitized_message: Optional[str] = None
    blocked_reason: Optional[str] = None
    canned_response: Optional[str] = None
    validated_output: Optional[dict] = None
    fallback_used: bool = False
    details: dict = field(default_factory=dict)


class GuardrailPipeline:
    """Runs all guardrails in the correct order."""

    def __init__(self):
        self.pii = PIIRedactor()
        self.input_validator = InputValidator()
        self.output_validator = OutputValidator()
        self.scope = ScopeEnforcer()
        self.rate_limiter = RateLimiter()

    def check_input(self, user_message: str, session_id: str = "default") -> GuardrailResult:
        """
        Run all input-side guardrails in sequence.

        Returns a GuardrailResult with:
          - passed: True if the message is safe to forward to the LLM
          - sanitized_message: PII-redacted version of the input
          - blocked_reason / canned_response: set when the message is blocked
        """
        # Placeholder — passes everything through unchanged
        return GuardrailResult(passed=True, sanitized_message=user_message)

    def validate_output(self, llm_output: str, expected_schema: str = "intent") -> GuardrailResult:
        """
        Run all output-side guardrails.

        Returns a GuardrailResult with:
          - passed: True if validation succeeded
          - validated_output: parsed dict (or fallback)
          - fallback_used: True if the raw output was malformed
        """
        # Placeholder — passes everything through unchanged
        return GuardrailResult(passed=True, validated_output=llm_output)
