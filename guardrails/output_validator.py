"""
Output Validator — Pydantic schemas for LLM output + response cleanup.

Validates the JSON returned by classify_intent() and strips any
markdown artifacts from the natural-language response.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OutputValidationResult:
    """Result of output validation."""
    valid: bool = True
    parsed: Optional[dict] = None
    fallback_used: bool = False
    error: Optional[str] = None


class OutputValidator:
    """Validates and cleans LLM outputs."""

    def parse_intent(self, raw_llm_output: str) -> dict:
        """Parse and validate intent classifier JSON output."""
        # Placeholder — returns raw output as-is
        return {"raw": raw_llm_output}

    def validate_response(self, response_text: str) -> str:
        """Clean the LLM's natural language response."""
        # Placeholder — returns text unchanged
        return response_text
