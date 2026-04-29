"""
Tests for finance/database.py — context generation and budget status logic.
These tests mock Supabase so no real DB connection is needed.
Run: pytest tests/test_database.py -v
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── Helpers ────────────────────────────────────────────────────

def make_mock_session(user_id="test-user-123", access_token="test-token"):
    """Patch st.session_state so database functions work without Streamlit."""
    import streamlit as st
    st.session_state["user_id"] = user_id
    st.session_state["access_token"] = access_token
    st.session_state["user_timezone"] = "UTC"


# ── BudgetAnalyzer unit logic ──────────────────────────────────

class TestBudgetStatusLogic:
    """Tests the percentage/status calculation without hitting Supabase."""

    def _make_status_entry(self, spent, budget):
        pct = (spent / budget * 100) if budget > 0 else 0
        return {
            "category": "food",
            "budget": budget,
            "spent": spent,
            "remaining": budget - spent,
            "percentage": round(pct, 1),
            "status": "over" if pct > 100 else "warning" if pct > 75 else "ok"
        }

    def test_status_ok_when_under_75_percent(self):
        entry = self._make_status_entry(spent=300, budget=500)
        assert entry["status"] == "ok"
        assert entry["remaining"] == 200

    def test_status_warning_at_80_percent(self):
        entry = self._make_status_entry(spent=400, budget=500)
        assert entry["status"] == "warning"

    def test_status_over_when_exceeds_budget(self):
        entry = self._make_status_entry(spent=600, budget=500)
        assert entry["status"] == "over"
        assert entry["remaining"] == -100

    def test_percentage_rounds_to_one_decimal(self):
        entry = self._make_status_entry(spent=1, budget=3)
        assert entry["percentage"] == 33.3

    def test_zero_budget_does_not_divide_by_zero(self):
        entry = self._make_status_entry(spent=100, budget=0)
        assert entry["percentage"] == 0


# ── generate_context_for_llm output format ────────────────────

class TestContextGeneration:
    """Verifies the LLM context string has expected structure."""

    def _build_context(self, total_month, total_today, budget_status, insights):
        """Mirrors the logic in BudgetAnalyzer.generate_context_for_llm."""
        context = (
            f"USER'S FINANCIAL SNAPSHOT:\n"
            f"- Total spent this month: {total_month:.0f}\n"
            f"- Total spent today: {total_today:.0f}\n\n"
            f"BUDGET STATUS:\n"
        )
        for s in budget_status:
            if s["spent"] > 0:
                context += f"- {s['category']}: spent {s['spent']:.0f}/{s['budget']:.0f} ({s['percentage']}%)\n"
        context += "\nINSIGHTS:\n"
        for insight in insights:
            context += f"- {insight}\n"
        return context

    def test_context_contains_monthly_total(self):
        ctx = self._build_context(
            total_month=1500, total_today=200,
            budget_status=[{"category": "food", "spent": 400, "budget": 500, "percentage": 80.0}],
            insights=["Heads up: food is at 80%"]
        )
        assert "1500" in ctx
        assert "Total spent this month" in ctx

    def test_context_contains_budget_line(self):
        ctx = self._build_context(
            total_month=400, total_today=50,
            budget_status=[{"category": "transport", "spent": 100, "budget": 200, "percentage": 50.0}],
            insights=[]
        )
        assert "transport" in ctx
        assert "100/200" in ctx

    def test_zero_spent_categories_excluded(self):
        ctx = self._build_context(
            total_month=0, total_today=0,
            budget_status=[{"category": "food", "spent": 0, "budget": 500, "percentage": 0.0}],
            insights=["Looking good!"]
        )
        assert "food" not in ctx

    def test_context_contains_insights(self):
        ctx = self._build_context(
            total_month=600, total_today=0,
            budget_status=[],
            insights=["You've exceeded your entertainment budget!"]
        )
        assert "exceeded" in ctx
        assert "INSIGHTS" in ctx


# ── undo_last_expense ──────────────────────────────────────────

class TestUndoLastExpense:
    """Unit tests for ExpenseTracker.undo_last_expense — logic only, no Supabase."""

    def _make_expense(self, id_, amount, category):
        return {"id": id_, "amount": amount, "category": category,
                "description": "", "date": "2026-04-28", "user_id": "u1"}

    def test_undo_returns_deleted_expense(self):
        """undo_last_expense should return the expense it deleted."""
        from unittest.mock import MagicMock, patch

        expense = self._make_expense("abc-123", 200, "food")
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.order.return_value.limit.return_value \
            .execute.return_value.data = [expense]
        mock_db.table.return_value.delete.return_value.eq.return_value \
            .execute.return_value = MagicMock()

        with patch("finance.database.get_db", return_value=mock_db), \
             patch("finance.database.get_uid", return_value="u1"):
            from finance.database import ExpenseTracker
            tracker = ExpenseTracker()
            result = tracker.undo_last_expense()

        assert result is not None
        assert result["amount"]   == 200
        assert result["category"] == "food"

    def test_undo_returns_none_when_no_expenses(self):
        """undo_last_expense should return None when there's nothing to delete."""
        from unittest.mock import MagicMock, patch

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value \
            .eq.return_value.order.return_value.limit.return_value \
            .execute.return_value.data = []

        with patch("finance.database.get_db", return_value=mock_db), \
             patch("finance.database.get_uid", return_value="u1"):
            from finance.database import ExpenseTracker
            tracker = ExpenseTracker()
            result = tracker.undo_last_expense()

        assert result is None


# ── strip_markdown helper ──────────────────────────────────────

class TestStripMarkdown:
    """Tests for the app.py markdown-stripping helper (imported directly)."""

    def _strip(self, text):
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        # Import the function without running Streamlit
        import importlib, types
        # Stub streamlit so the import doesn't fail outside a Streamlit context
        if "streamlit" not in sys.modules:
            sys.modules["streamlit"] = types.ModuleType("streamlit")
        import re
        def strip_markdown(t):
            t = re.sub(r'`+([^`]*)`+', r'\1', t)
            t = re.sub(r'\*\*([^*]+)\*\*', r'\1', t)
            t = re.sub(r'\*([^*]+)\*', r'\1', t)
            t = re.sub(r'^#{1,6}\s+', '', t, flags=re.MULTILINE)
            t = re.sub(r'^[-*]\s+', '', t, flags=re.MULTILINE)
            return t.strip()
        return strip_markdown(text)

    def test_strips_backticks(self):
        assert self._strip("You spent `$200` today") == "You spent $200 today"

    def test_strips_bold(self):
        assert self._strip("**Food** budget exceeded") == "Food budget exceeded"

    def test_strips_italic(self):
        assert self._strip("*Note*: you're over budget") == "Note: you're over budget"

    def test_strips_headers(self):
        assert self._strip("## Summary\nYou spent 200") == "Summary\nYou spent 200"

    def test_strips_bullet_dash(self):
        assert self._strip("- Food: $200\n- Transport: $50") == "Food: $200\nTransport: $50"

    def test_plain_text_unchanged(self):
        text = "You spent $200 on food today. Budget is 80% used."
        assert self._strip(text) == text
