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

import logging
from dataclasses import dataclass, field
from typing import Optional

from guardrails.pii import PIIRedactor
from guardrails.input_validator import InputValidator
from guardrails.output_validator import OutputValidator
from guardrails.scope import ScopeEnforcer
from guardrails.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


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

        Order: rate limit → injection → abuse → scope → PII redaction.
        Short-circuits on the first block.

        Returns a GuardrailResult with:
          - passed: True if the message is safe to forward to the LLM
          - sanitized_message: PII-redacted version of the input
          - blocked_reason / canned_response: set when the message is blocked
        """
        details: dict = {}

        # 1. Rate limiting
        rate_result = self.rate_limiter.check_rate(session_id)
        if not rate_result.allowed:
            return GuardrailResult(
                passed=False,
                sanitized_message=user_message,
                blocked_reason="rate_limit",
                canned_response=rate_result.canned_response,
                details={"retry_after": rate_result.retry_after_seconds},
            )

        # 2. Prompt injection detection
        injection_result = self.input_validator.check_injection(user_message)
        details["injection_score"] = injection_result.risk_score
        if injection_result.is_injection:
            # Record the request so it counts toward rate limits
            self.rate_limiter.record_request(session_id)
            return GuardrailResult(
                passed=False,
                sanitized_message=user_message,
                blocked_reason="prompt_injection",
                canned_response=(
                    "I can only help with financial topics like tracking expenses, "
                    "budgets, and money advice. What would you like help with?"
                ),
                details=details,
            )

        # 3. Profanity / abuse detection
        abuse_result = self.input_validator.check_abuse(user_message)
        details["abuse_severity"] = abuse_result.severity
        if abuse_result.is_abusive:
            self.rate_limiter.record_request(session_id)
            return GuardrailResult(
                passed=False,
                sanitized_message=user_message,
                blocked_reason="abuse",
                canned_response=abuse_result.canned_response,
                details=details,
            )

        # 4. Scope enforcement
        scope_result = self.scope.is_in_scope(user_message)
        if not scope_result.in_scope:
            self.rate_limiter.record_request(session_id)
            return GuardrailResult(
                passed=False,
                sanitized_message=user_message,
                blocked_reason="out_of_scope",
                canned_response=scope_result.canned_response,
                details=details,
            )

        # 5. PII redaction (message passes all checks — sanitize it)
        pii_result = self.pii.redact(user_message)
        details["pii_found"] = pii_result.pii_found
        if pii_result.pii_found:
            details["pii_types"] = pii_result.detections
            logger.info("PII redacted: types=%s", pii_result.detections)

        # Record the request (it passed all checks and will be processed)
        self.rate_limiter.record_request(session_id)

        return GuardrailResult(
            passed=True,
            sanitized_message=pii_result.redacted_text,
            details=details,
        )

    def validate_output(self, llm_output: str, expected_schema: str = "intent") -> GuardrailResult:
        """
        Run all output-side guardrails.

        Returns a GuardrailResult with:
          - passed: True if validation succeeded
          - validated_output: parsed dict (or fallback)
          - fallback_used: True if the raw output was malformed
        """
        if expected_schema == "intent":
            parsed = self.output_validator.parse_intent(llm_output)
            fallback = parsed.get("_fallback", False)
            # Remove the internal marker before returning
            parsed.pop("_fallback", None)
            return GuardrailResult(
                passed=not fallback,
                validated_output=parsed,
                fallback_used=fallback,
            )

        elif expected_schema == "response":
            cleaned = self.output_validator.validate_response(llm_output)
            return GuardrailResult(
                passed=True,
                validated_output=cleaned,
            )

        # Unknown schema — pass through
        return GuardrailResult(passed=True, validated_output=llm_output)
