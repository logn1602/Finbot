"""
Output Validator — Pydantic schemas for LLM output + response cleanup.

Validates the JSON returned by classify_intent() and strips any
markdown artifacts from the natural-language response.
"""

import json
import re
import logging
from typing import Optional, Literal

from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


# ── Pydantic models matching the intent classifier schema ────────

VALID_INTENTS = {"add_expense", "query_balance", "get_advice", "set_budget", "greeting", "goodbye"}
VALID_CATEGORIES = {"food", "transport", "entertainment", "shopping", "bills", "health", "education", "other"}


class IntentEntities(BaseModel):
    """Nested entities block inside the intent classification."""
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    period: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v):
        """Accept stringified numbers like '500' → 500.0."""
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("category", mode="before")
    @classmethod
    def normalise_category(cls, v):
        """Lower-case and map unknown categories to 'other'."""
        if v is None:
            return None
        v = str(v).lower().strip()
        return v if v in VALID_CATEGORIES else "other"


class IntentClassification(BaseModel):
    """Full intent classifier output."""
    intent: str = "greeting"
    entities: IntentEntities = IntentEntities()
    confidence: float = 0.0
    language: str = "en"
    time_scope: Literal["current_month", "historical"] = "current_month"

    @field_validator("intent", mode="before")
    @classmethod
    def validate_intent(cls, v):
        """Map unknown intents to 'get_advice' (safe — no DB writes)."""
        if isinstance(v, str) and v.lower().strip() in VALID_INTENTS:
            return v.lower().strip()
        logger.warning("Unknown intent '%s', falling back to 'get_advice'", v)
        return "get_advice"

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (ValueError, TypeError):
            return 0.0

    @field_validator("time_scope", mode="before")
    @classmethod
    def validate_time_scope(cls, v):
        if v in ("current_month", "historical"):
            return v
        return "current_month"


# ── Regex for extracting JSON from noisy LLM output ─────────────
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_FIRST_BRACE = re.compile(r"\{.*\}", re.DOTALL)

# Markdown artifacts to strip from natural-language responses
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"\*(.+?)\*")
_MD_HEADER = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_BACKTICK = re.compile(r"`(.+?)`")
_MD_BULLET = re.compile(r"^[\-\*]\s+", re.MULTILINE)

_FALLBACK = IntentClassification()   # greeting, no entities


class OutputValidator:
    """Validates and cleans LLM outputs."""

    def parse_intent(self, raw_llm_output: str) -> dict:
        """Parse and validate intent classifier JSON output.

        Attempts to:
          1. Strip markdown fences / surrounding text
          2. json.loads()
          3. Validate with Pydantic
          4. On any failure → safe fallback (greeting, no entities)

        Returns a plain dict matching the original schema so downstream
        code doesn't need to change.
        """
        try:
            json_str = self._extract_json(raw_llm_output)
            raw_dict = json.loads(json_str)
            model = IntentClassification(**raw_dict)
            return self._to_dict(model)

        except Exception as e:
            logger.warning(
                "Intent validation failed — using fallback. error='%s' raw='%.200s'",
                e, raw_llm_output,
            )
            return self._to_dict(_FALLBACK, fallback=True)

    def validate_response(self, response_text: str) -> str:
        """Clean the LLM's natural language response.

        - Strips markdown artifacts (**bold**, # headers, `code`, bullets)
        - Truncates to 500 chars if the LLM went off the rails
        """
        text = response_text

        # Strip markdown formatting
        text = _MD_BOLD.sub(r"\1", text)
        text = _MD_ITALIC.sub(r"\1", text)
        text = _MD_HEADER.sub("", text)
        text = _MD_BACKTICK.sub(r"\1", text)
        text = _MD_BULLET.sub("", text)

        # Collapse multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        # Truncate if excessively long
        if len(text) > 500:
            text = text[:497] + "..."

        return text

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _extract_json(raw: str) -> str:
        """Pull JSON out of a possibly noisy LLM response."""
        raw = raw.strip()

        # Try markdown fenced block first
        m = _JSON_BLOCK.search(raw)
        if m:
            return m.group(1).strip()

        # Try first { … } block
        m = _FIRST_BRACE.search(raw)
        if m:
            return m.group(0)

        # Last resort — return as-is (json.loads will raise)
        return raw

    @staticmethod
    def _to_dict(model: IntentClassification, fallback: bool = False) -> dict:
        """Convert Pydantic model back to the dict format downstream expects."""
        d = {
            "intent": model.intent,
            "entities": model.entities.model_dump(),
            "confidence": model.confidence,
            "language": model.language,
            "time_scope": model.time_scope,
        }
        if fallback:
            d["_fallback"] = True
        return d
