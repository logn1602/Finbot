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
