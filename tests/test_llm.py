"""
Tests for FinanceBrain — intent classification and language detection.
These tests call the real Groq API, so GROQ_API_KEY must be set.
Run: pytest tests/test_llm.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.llm import FinanceBrain


@pytest.fixture(scope="module")
def brain():
    return FinanceBrain()


# ── Intent classification ──────────────────────────────────────

class TestIntentClassification:

    def test_add_expense_english(self, brain):
        result = brain.classify_intent("I spent 300 on groceries")
        assert result["intent"] == "add_expense"
        assert float(result["entities"]["amount"]) == 300
        assert result["entities"]["category"] == "food"

    def test_add_expense_with_transport(self, brain):
        result = brain.classify_intent("Paid 150 for an Uber ride")
        assert result["intent"] == "add_expense"
        assert result["entities"]["category"] == "transport"

    def test_query_balance(self, brain):
        result = brain.classify_intent("How much have I spent this month?")
        assert result["intent"] == "query_balance"

    def test_get_advice(self, brain):
        result = brain.classify_intent("Can I afford to go out this weekend?")
        assert result["intent"] == "get_advice"

    def test_set_budget(self, brain):
        result = brain.classify_intent("Set my food budget to 500")
        assert result["intent"] == "set_budget"
        assert float(result["entities"]["amount"]) == 500
        assert result["entities"]["category"] == "food"

    def test_greeting(self, brain):
        result = brain.classify_intent("Hey there!")
        assert result["intent"] == "greeting"

    def test_confidence_field_present(self, brain):
        result = brain.classify_intent("I spent 50 on coffee")
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0


# ── Language detection ─────────────────────────────────────────

class TestLanguageDetection:

    def test_detects_english(self, brain):
        result = brain.classify_intent("I spent 200 on lunch")
        assert result["language"] == "en"

    def test_detects_hindi(self, brain):
        result = brain.classify_intent("Maine aaj 500 rupaye khane pe kharch kiye")
        assert result["language"] == "hi"

    def test_detects_spanish(self, brain):
        result = brain.classify_intent("Hola, cuánto gasté hoy?")
        assert result["language"] == "es"

    def test_detects_french(self, brain):
        result = brain.classify_intent("Combien ai-je dépensé ce mois-ci?")
        assert result["language"] == "fr"


# ── Response generation ────────────────────────────────────────

class TestResponseGeneration:

    def test_response_is_string(self, brain):
        context = "Total spent this month: 200. Food: 200/500 (40%)"
        response = brain.generate_response("How am I doing?", context, language="en")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_response_not_empty_on_hindi(self, brain):
        context = "Total spent this month: 500."
        response = brain.generate_response(
            "Mera budget kaisa chal raha hai?", context, language="hi"
        )
        assert isinstance(response, str)
        assert len(response) > 0

    def test_conversation_history_grows(self, brain):
        brain.reset_conversation()
        assert len(brain.conversation_history) == 0
        brain.generate_response("Hello!", language="en")
        assert len(brain.conversation_history) == 2  # user + assistant

    def test_reset_clears_history(self, brain):
        brain.generate_response("Test", language="en")
        brain.reset_conversation()
        assert len(brain.conversation_history) == 0


# ── Full pipeline ──────────────────────────────────────────────

class TestProcessMessage:

    def test_full_pipeline_returns_required_keys(self, brain):
        result = brain.process_message("I spent 100 on food", financial_context="")
        assert "intent" in result
        assert "response" in result
        assert "language" in result

    def test_whisper_language_takes_precedence(self, brain):
        # If Whisper already detected the language, it should override LLM detection
        result = brain.process_message(
            "I spent 200 on food", financial_context="", language="ta"
        )
        assert result["language"] == "ta"
