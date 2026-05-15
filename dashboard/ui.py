"""
Historical Dashboard — Streamlit UI

Renders a multi-tab historical spending dashboard inside the sidebar.
Uses chart functions from dashboard.charts and data from
ExpenseTracker / BudgetAnalyzer historical methods.
"""

import streamlit as st

from dashboard.charts import (
    budget_performance_heatmap,
    category_breakdown_stacked,
    category_trend_line,
    monthly_spending_bar,
    spending_trend_line,
)
from styles.tokens import ACCENT, TEXT_SECONDARY, TEXT_TERTIARY


def render_historical_dashboard(tracker, analyzer) -> None:
    """Render the historical spending dashboard inside an expander.

    Args:
        tracker:  ExpenseTracker instance (has get_monthly_summary, etc.)
        analyzer: BudgetAnalyzer instance (has get_historical_budget_performance, etc.)
    """
    with st.expander("Historical Dashboard", expanded=False):
        # Month range selector
        months_back = st.select_slider(
            "Period",
            options=[3, 6, 9, 12],
            value=6,
            format_func=lambda x: f"{x} months",
            key="hist_months_back",
        )

        # Tabs for different views
        tab_overview, tab_categories, tab_budget = st.tabs([
            "Overview", "Categories", "Budget"
        ])

        # ── Tab 1: Overview ───────────────────────────────────
        with tab_overview:
            _render_overview(tracker, months_back)

        # ── Tab 2: Categories ─────────────────────────────────
        with tab_categories:
            _render_categories(tracker, analyzer, months_back)

        # ── Tab 3: Budget Performance ─────────────────────────
        with tab_budget:
            _render_budget(analyzer, months_back)


def _section_header(text: str) -> None:
    """Small uppercase section label matching FinBot's style."""
    st.markdown(
        f'<div style="font-size:0.68rem;text-transform:uppercase;letter-spacing:0.8px;'
        f'color:{TEXT_TERTIARY};margin:12px 0 6px;font-family:Inter,sans-serif">'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


def _no_data_msg() -> None:
    """Show a subtle message when there's no data to display."""
    st.markdown(
        f'<p style="color:{TEXT_TERTIARY};font-size:0.82rem;padding:16px 0">'
        f'No spending data for this period yet.</p>',
        unsafe_allow_html=True,
    )


# ── Tab renderers ─────────────────────────────────────────────

def _render_overview(tracker, months_back: int) -> None:
    """Monthly spending bar chart + daily trend line."""

    # Monthly totals bar chart
    _section_header("Monthly spending")
    summary = tracker.get_monthly_summary(months_back)
    fig_bar = monthly_spending_bar(summary)
    if fig_bar:
        st.plotly_chart(fig_bar, width="stretch", config={"displayModeBar": False})

        # Summary stats row
        if len(summary) >= 2:
            prev, curr = summary[-2], summary[-1]
            change = curr["total"] - prev["total"]
            pct = (change / prev["total"] * 100) if prev["total"] > 0 else 0
            arrow = "+" if change >= 0 else ""
            color = "#e08a7a" if change > 0 else "#7fc99a"
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;font-size:0.78rem;'
                f'color:{TEXT_SECONDARY};padding:4px 0">'
                f'<span>Avg: ${sum(s["total"] for s in summary)/len(summary):,.0f}/mo</span>'
                f'<span style="color:{color}">{arrow}${abs(change):,.0f} ({arrow}{pct:.1f}%)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        _no_data_msg()

    # Daily spending trend (90 days)
    _section_header("Daily spending trend")
    daily = tracker.get_spending_trend(days=min(months_back * 30, 90))
    fig_trend = spending_trend_line(daily)
    if fig_trend:
        st.plotly_chart(fig_trend, width="stretch", config={"displayModeBar": False})
    else:
        _no_data_msg()


def _render_categories(tracker, analyzer, months_back: int) -> None:
    """Stacked category breakdown + single-category drilldown."""

    # Stacked bar
    _section_header("Category breakdown by month")
    breakdown = tracker.get_monthly_breakdown_by_category(months_back)
    fig_stacked = category_breakdown_stacked(breakdown)
    if fig_stacked:
        st.plotly_chart(fig_stacked, width="stretch", config={"displayModeBar": False})
    else:
        _no_data_msg()
        return

    # Category drilldown selector
    categories = sorted(set(row["category"] for row in breakdown))
    if categories:
        _section_header("Category drilldown")
        selected = st.selectbox(
            "Select category",
            options=categories,
            format_func=lambda x: x.capitalize(),
            key="hist_cat_select",
            label_visibility="collapsed",
        )
        if selected:
            trend = tracker.get_category_trend(selected, months_back)
            budgets = analyzer.get_budgets()
            limit = budgets.get(selected)
            fig_cat = category_trend_line(selected, trend, budget_limit=limit)
            if fig_cat:
                st.plotly_chart(fig_cat, width="stretch", config={"displayModeBar": False})


def _render_budget(analyzer, months_back: int) -> None:
    """Budget performance heatmap across months."""

    _section_header("Budget vs actual by month")
    perf = analyzer.get_historical_budget_performance(months_back)
    fig_heat = budget_performance_heatmap(perf)
    if fig_heat:
        st.plotly_chart(fig_heat, width="stretch", config={"displayModeBar": False})

        # Count overspend months
        over_count = sum(1 for p in perf if p["status"] == "over")
        warn_count = sum(1 for p in perf if p["status"] == "warning")
        ok_count = sum(1 for p in perf if p["status"] == "ok")
        total = over_count + warn_count + ok_count

        if total > 0:
            st.markdown(
                f'<div style="font-size:0.78rem;color:{TEXT_SECONDARY};padding:4px 0">'
                f'<span style="color:#7fc99a">{ok_count} on track</span> · '
                f'<span style="color:#f0c97a">{warn_count} warning</span> · '
                f'<span style="color:#e08a7a">{over_count} over budget</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        _no_data_msg()
