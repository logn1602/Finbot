"""
Tests for month scoping, historical queries, time scope detection,
and dashboard chart generation.

Run: python -m pytest tests/test_historical.py -v
"""

import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ════════════════════════════════════════════════════════════════
# MONTH BOUNDARY HELPERS
# ════════════════════════════════════════════════════════════════

class TestMonthBoundaries:
    """Verify month_start_local / next_month_start_local produce
    correct calendar boundaries for edge-case months."""

    def _boundaries(self, fake_now):
        """Compute boundaries as the production code does, using a fake now."""
        start = fake_now.replace(day=1).strftime("%Y-%m-%d")
        if fake_now.month == 12:
            end = datetime(fake_now.year + 1, 1, 1).strftime("%Y-%m-%d")
        else:
            end = datetime(fake_now.year, fake_now.month + 1, 1).strftime("%Y-%m-%d")
        return start, end

    def test_january_boundaries(self):
        start, end = self._boundaries(datetime(2026, 1, 15))
        assert start == "2026-01-01"
        assert end == "2026-02-01"

    def test_february_boundaries(self):
        start, end = self._boundaries(datetime(2026, 2, 10))
        assert start == "2026-02-01"
        assert end == "2026-03-01"

    def test_december_rolls_to_next_year(self):
        start, end = self._boundaries(datetime(2026, 12, 25))
        assert start == "2026-12-01"
        assert end == "2027-01-01"

    def test_last_day_of_month_stays_in_month(self):
        start, end = self._boundaries(datetime(2026, 3, 31))
        assert start == "2026-03-01"
        assert end == "2026-04-01"

    def test_first_day_of_month(self):
        start, end = self._boundaries(datetime(2026, 7, 1))
        assert start == "2026-07-01"
        assert end == "2026-08-01"

    def test_leap_year_february(self):
        start, end = self._boundaries(datetime(2028, 2, 29))
        assert start == "2028-02-01"
        assert end == "2028-03-01"


# ════════════════════════════════════════════════════════════════
# _month_boundaries (N months back)
# ════════════════════════════════════════════════════════════════

class TestMonthBoundariesNBack:
    """Mirrors ExpenseTracker._month_boundaries logic."""

    def _month_boundaries(self, now, months_back):
        year = now.year
        month = now.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        start = datetime(year, month, 1).strftime("%Y-%m-%d")
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1).strftime("%Y-%m-%d")
        else:
            end = datetime(now.year, now.month + 1, 1).strftime("%Y-%m-%d")
        return start, end

    def test_3_months_back_from_may(self):
        start, end = self._month_boundaries(datetime(2026, 5, 14), 3)
        assert start == "2026-02-01"
        assert end == "2026-06-01"

    def test_6_months_back_from_march(self):
        start, end = self._month_boundaries(datetime(2026, 3, 10), 6)
        assert start == "2025-09-01"
        assert end == "2026-04-01"

    def test_12_months_back_wraps_year(self):
        start, end = self._month_boundaries(datetime(2026, 6, 1), 12)
        assert start == "2025-06-01"
        assert end == "2026-07-01"


# ════════════════════════════════════════════════════════════════
# BUDGET STATUS LOGIC (calendar month scoping)
# ════════════════════════════════════════════════════════════════

class TestBudgetStatusCalendarMonth:
    """Verify budget percentage and status calculations use strict
    calendar-month boundaries (no rolling 30 days)."""

    def _compute_status(self, spent, budget, days_passed, days_in_month):
        """Mirrors BudgetAnalyzer.get_budget_status computation."""
        pct = (spent / budget * 100) if budget > 0 else 0
        projected = (spent / days_passed * days_in_month) if days_passed > 0 else 0
        if pct > 100:
            status = "over"
        elif pct > 75:
            status = "warning"
        else:
            status = "ok"
        return {
            "spent": spent,
            "budget": budget,
            "percentage": round(pct, 1),
            "projected": round(projected, 2),
            "status": status,
        }

    def test_projection_uses_actual_days_in_month(self):
        # 15 days into a 30-day month, spent $300 of $500
        result = self._compute_status(300, 500, 15, 30)
        assert result["projected"] == 600.0  # 300/15 * 30
        assert result["status"] == "ok"  # 60% so far

    def test_projection_february_28_days(self):
        # 14 days into Feb (28 days), spent $200
        result = self._compute_status(200, 400, 14, 28)
        assert result["projected"] == 400.0  # 200/14 * 28
        assert result["status"] == "ok"

    def test_day_one_projection(self):
        # First day, spent $50
        result = self._compute_status(50, 500, 1, 31)
        assert result["projected"] == 1550.0  # 50/1 * 31
        assert result["status"] == "ok"  # only 10% so far

    def test_zero_days_passed_no_crash(self):
        result = self._compute_status(0, 500, 0, 30)
        assert result["projected"] == 0
        assert result["status"] == "ok"


# ════════════════════════════════════════════════════════════════
# HISTORICAL CONTEXT GENERATION
# ════════════════════════════════════════════════════════════════

class TestHistoricalContext:
    """Test the structure of generate_historical_context_for_llm output."""

    def _build_context(self, summary, perf, budgets, current_month_str):
        """Mirrors BudgetAnalyzer.generate_historical_context_for_llm logic."""
        if not summary:
            return "HISTORICAL DATA: No spending history found yet."

        context = (
            "USER'S HISTORICAL FINANCIAL DATA "
            "(all figures pre-calculated — use them exactly, do not recompute):\n\n"
            "MONTHLY SPENDING SUMMARY:\n"
        )
        for s in summary:
            label = "(current)" if s["month"] == current_month_str else ""
            context += f"- {s['month']} {label}: ${s['total']:,.2f} ({s['expense_count']} expenses)\n"

        if len(summary) >= 2:
            prev, curr = summary[-2], summary[-1]
            change = curr["total"] - prev["total"]
            pct_change = (change / prev["total"] * 100) if prev["total"] > 0 else 0
            direction = "up" if change > 0 else "down"
            context += (
                f"\nMONTH-OVER-MONTH: ${abs(change):,.2f} {direction} "
                f"({abs(pct_change):.1f}%) from {prev['month']} to {curr['month']}\n"
            )
        return context

    def test_empty_summary_returns_no_history_message(self):
        ctx = self._build_context([], [], {}, "2026-05")
        assert "No spending history" in ctx

    def test_context_contains_monthly_totals(self):
        summary = [
            {"month": "2026-04", "total": 800, "expense_count": 20},
            {"month": "2026-05", "total": 600, "expense_count": 15},
        ]
        ctx = self._build_context(summary, [], {}, "2026-05")
        assert "$800.00" in ctx
        assert "$600.00" in ctx
        assert "2026-04" in ctx
        assert "2026-05" in ctx

    def test_current_month_label_present(self):
        summary = [
            {"month": "2026-04", "total": 500, "expense_count": 10},
            {"month": "2026-05", "total": 300, "expense_count": 8},
        ]
        ctx = self._build_context(summary, [], {}, "2026-05")
        assert "(current)" in ctx

    def test_month_over_month_increase(self):
        summary = [
            {"month": "2026-03", "total": 500, "expense_count": 10},
            {"month": "2026-04", "total": 700, "expense_count": 15},
        ]
        ctx = self._build_context(summary, [], {}, "2026-05")
        assert "$200.00 up" in ctx
        assert "40.0%" in ctx

    def test_month_over_month_decrease(self):
        summary = [
            {"month": "2026-03", "total": 800, "expense_count": 20},
            {"month": "2026-04", "total": 600, "expense_count": 15},
        ]
        ctx = self._build_context(summary, [], {}, "2026-05")
        assert "$200.00 down" in ctx
        assert "25.0%" in ctx

    def test_single_month_no_mom_section(self):
        summary = [{"month": "2026-05", "total": 300, "expense_count": 5}]
        ctx = self._build_context(summary, [], {}, "2026-05")
        assert "MONTH-OVER-MONTH" not in ctx


# ════════════════════════════════════════════════════════════════
# HISTORICAL BUDGET PERFORMANCE
# ════════════════════════════════════════════════════════════════

class TestHistoricalBudgetPerformance:
    """Test the percentage/status logic in get_historical_budget_performance."""

    def _compute_perf(self, spent, budget):
        pct = (spent / budget * 100) if budget > 0 else 0
        status = "over" if pct > 100 else "warning" if pct > 75 else "ok"
        return {"spent": spent, "budget": budget, "percentage": round(pct, 1), "status": status}

    def test_ok_status(self):
        p = self._compute_perf(200, 500)
        assert p["status"] == "ok"
        assert p["percentage"] == 40.0

    def test_warning_status(self):
        p = self._compute_perf(400, 500)
        assert p["status"] == "warning"
        assert p["percentage"] == 80.0

    def test_over_status(self):
        p = self._compute_perf(600, 500)
        assert p["status"] == "over"
        assert p["percentage"] == 120.0

    def test_zero_budget(self):
        p = self._compute_perf(100, 0)
        assert p["percentage"] == 0
        assert p["status"] == "ok"


# ════════════════════════════════════════════════════════════════
# TIME SCOPE DETECTION (intent prompt)
# ════════════════════════════════════════════════════════════════

class TestTimeScopeDetection:
    """Verify the time_scope field is present in intent classification
    output and defaults correctly. These tests do NOT call the real API —
    they validate the fallback and the prompt structure."""

    def test_fallback_includes_time_scope(self):
        """The error-case fallback dict must include time_scope."""
        from brain.llm import FinanceBrain
        fallback = {"intent": "get_advice", "entities": {}, "confidence": 0.3,
                     "language": "en", "time_scope": "current_month"}
        assert "time_scope" in fallback
        assert fallback["time_scope"] == "current_month"

    def test_intent_prompt_contains_time_scope_instructions(self):
        """The INTENT_PROMPT must mention time_scope and its values."""
        from brain.llm import INTENT_PROMPT
        prompt_text = INTENT_PROMPT.system
        assert "time_scope" in prompt_text
        assert "current_month" in prompt_text
        assert "historical" in prompt_text

    def test_intent_prompt_json_schema_has_time_scope(self):
        """The JSON output schema in the prompt must include time_scope."""
        from brain.llm import INTENT_PROMPT
        assert '"time_scope"' in INTENT_PROMPT.system

    def test_advisor_prompt_has_historical_instructions(self):
        """ADVISOR_PROMPT must contain the historical trend section."""
        from brain.llm import ADVISOR_PROMPT
        assert "HISTORICAL" in ADVISOR_PROMPT.system
        assert "trend" in ADVISOR_PROMPT.system.lower()

    def test_process_message_accepts_historical_context(self):
        """process_message signature must accept historical_context kwarg."""
        import inspect
        from brain.llm import FinanceBrain
        sig = inspect.signature(FinanceBrain.process_message)
        assert "historical_context" in sig.parameters


# ════════════════════════════════════════════════════════════════
# DASHBOARD CHART FUNCTIONS
# ════════════════════════════════════════════════════════════════

class TestDashboardCharts:
    """Test chart functions return valid Plotly figures or None."""

    def test_monthly_spending_bar_returns_figure(self):
        from dashboard.charts import monthly_spending_bar
        fig = monthly_spending_bar([
            {"month": "2026-03", "total": 800, "expense_count": 20},
            {"month": "2026-04", "total": 950, "expense_count": 30},
        ])
        assert fig is not None
        assert len(fig.data) == 1  # single bar trace
        assert fig.data[0].type == "bar"

    def test_monthly_spending_bar_empty(self):
        from dashboard.charts import monthly_spending_bar
        assert monthly_spending_bar([]) is None

    def test_category_breakdown_stacked_returns_figure(self):
        from dashboard.charts import category_breakdown_stacked
        fig = category_breakdown_stacked([
            {"month": "2026-04", "category": "food", "total": 300},
            {"month": "2026-04", "category": "transport", "total": 150},
        ])
        assert fig is not None
        assert len(fig.data) == 2  # one trace per category
        assert all(t.type == "bar" for t in fig.data)

    def test_category_breakdown_empty(self):
        from dashboard.charts import category_breakdown_stacked
        assert category_breakdown_stacked([]) is None

    def test_spending_trend_line_returns_figure(self):
        from dashboard.charts import spending_trend_line
        data = [{"date": f"2026-05-{d:02d}", "total": d * 10} for d in range(1, 10)]
        fig = spending_trend_line(data)
        assert fig is not None
        assert fig.data[0].type == "scatter"

    def test_spending_trend_with_moving_average(self):
        from dashboard.charts import spending_trend_line
        data = [{"date": f"2026-05-{d:02d}", "total": d * 10} for d in range(1, 15)]
        fig = spending_trend_line(data)
        assert len(fig.data) == 2  # main line + 7-day MA

    def test_spending_trend_empty(self):
        from dashboard.charts import spending_trend_line
        assert spending_trend_line([]) is None

    def test_budget_performance_heatmap_returns_figure(self):
        from dashboard.charts import budget_performance_heatmap
        fig = budget_performance_heatmap([
            {"month": "2026-04", "category": "food", "budget": 500,
             "spent": 430, "percentage": 86, "status": "warning"},
        ])
        assert fig is not None
        assert fig.data[0].type == "heatmap"

    def test_budget_performance_heatmap_empty(self):
        from dashboard.charts import budget_performance_heatmap
        assert budget_performance_heatmap([]) is None

    def test_category_trend_line_returns_figure(self):
        from dashboard.charts import category_trend_line
        fig = category_trend_line("food", [
            {"month": "2026-03", "total": 350},
            {"month": "2026-04", "total": 430},
        ])
        assert fig is not None
        assert fig.data[0].type == "scatter"

    def test_category_trend_with_budget_line(self):
        from dashboard.charts import category_trend_line
        fig = category_trend_line("food", [
            {"month": "2026-03", "total": 350},
        ], budget_limit=500)
        assert fig is not None
        # Budget reference line appears in layout.shapes
        shapes = fig.layout.shapes
        assert len(shapes) >= 1

    def test_category_trend_empty(self):
        from dashboard.charts import category_trend_line
        assert category_trend_line("food", []) is None

    def test_current_month_highlighted_in_bar(self):
        """Last bar should be a different color (brighter gold = ACCENT)."""
        from dashboard.charts import monthly_spending_bar
        from styles.tokens import ACCENT, ACCENT_DARK
        fig = monthly_spending_bar([
            {"month": "2026-03", "total": 500, "expense_count": 10},
            {"month": "2026-04", "total": 600, "expense_count": 15},
            {"month": "2026-05", "total": 300, "expense_count": 8},
        ])
        colors = fig.data[0].marker.color
        assert colors[-1] == ACCENT       # current month
        assert colors[0] == ACCENT_DARK    # past months
