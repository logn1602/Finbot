"""
Historical Dashboard — Plotly Chart Functions

Five chart builders that consume data from ExpenseTracker / BudgetAnalyzer
historical methods and return ready-to-render Plotly figures.

All charts follow the FinBot dark theme (transparent background, warm gold
accent) via shared tokens from styles.tokens.
"""

import plotly.graph_objects as go
from styles.tokens import (
    ACCENT, ACCENT_DARK, TEXT_SECONDARY, TEXT_TERTIARY,
    BORDER, SUCCESS, WARNING, DANGER, SURFACE,
)
from styles.plotly_theme import DONUT_COLORS


# ── Shared layout base ────────────────────────────────────────

def _base_layout(height: int = 300, **overrides) -> dict:
    """Dark-themed layout shared by all historical charts."""
    layout = dict(
        height=height,
        margin=dict(l=40, r=16, t=32, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=11),
        xaxis=dict(
            showgrid=False,
            color=TEXT_TERTIARY,
            tickfont=dict(size=10, color=TEXT_TERTIARY),
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=BORDER,
            color=TEXT_TERTIARY,
            tickfont=dict(size=10, color=TEXT_TERTIARY),
            tickprefix="$",
            fixedrange=True,
        ),
        showlegend=False,
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=SURFACE,
            font_size=11,
            font_color=TEXT_SECONDARY,
        ),
    )
    layout.update(overrides)
    return layout


# ── 1. Monthly Spending Bar Chart ─────────────────────────────

def monthly_spending_bar(monthly_summary: list[dict]) -> go.Figure | None:
    """Bar chart of total spending per month.

    Args:
        monthly_summary: from ExpenseTracker.get_monthly_summary()
            [{"month": "2026-01", "total": 1200.00, "expense_count": 45}, ...]

    Returns:
        Plotly Figure or None if no data.
    """
    if not monthly_summary:
        return None

    months = [row["month"] for row in monthly_summary]
    totals = [row["total"] for row in monthly_summary]
    counts = [row["expense_count"] for row in monthly_summary]

    # Highlight the current month differently
    colors = [ACCENT if i == len(months) - 1 else ACCENT_DARK for i in range(len(months))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months,
        y=totals,
        marker_color=colors,
        marker_line=dict(width=0),
        text=[f"${t:,.0f}" for t in totals],
        textposition="outside",
        textfont=dict(size=10, color=TEXT_SECONDARY),
        customdata=counts,
        hovertemplate="%{x}<br>$%{y:,.2f}<br>%{customdata} expenses<extra></extra>",
    ))

    layout = _base_layout(height=300)
    layout["xaxis"]["title"] = None
    layout["yaxis"]["title"] = None
    fig.update_layout(**layout)

    return fig


# ── 2. Category Breakdown Stacked Bar ─────────────────────────

def category_breakdown_stacked(breakdown: list[dict]) -> go.Figure | None:
    """Stacked bar chart showing category distribution per month.

    Args:
        breakdown: from ExpenseTracker.get_monthly_breakdown_by_category()
            [{"month": "2026-01", "category": "food", "total": 300}, ...]

    Returns:
        Plotly Figure or None if no data.
    """
    if not breakdown:
        return None

    # Pivot: get unique months and categories
    months: list[str] = sorted(set(row["month"] for row in breakdown))
    categories: list[str] = sorted(set(row["category"] for row in breakdown))

    # Build lookup
    lookup: dict[tuple[str, str], float] = {}
    for row in breakdown:
        lookup[(row["month"], row["category"])] = row["total"]

    fig = go.Figure()
    for i, cat in enumerate(categories):
        values = [lookup.get((m, cat), 0) for m in months]
        color = DONUT_COLORS[i % len(DONUT_COLORS)]
        fig.add_trace(go.Bar(
            name=cat.capitalize(),
            x=months,
            y=values,
            marker_color=color,
            hovertemplate=f"{cat.capitalize()}: $%{{y:,.2f}}<extra></extra>",
        ))

    layout = _base_layout(height=350)
    layout["barmode"] = "stack"
    layout["showlegend"] = True
    layout["legend"] = dict(
        font=dict(size=10, color=TEXT_SECONDARY),
        orientation="h",
        y=-0.18,
        x=0.5,
        xanchor="center",
    )
    fig.update_layout(**layout)

    return fig


# ── 3. Spending Trend Line (daily, multi-month) ──────────────

def spending_trend_line(daily_data: list[dict]) -> go.Figure | None:
    """Smooth line chart of daily spending over 90 days.

    Args:
        daily_data: from ExpenseTracker.get_spending_trend(days=90)
            [{"date": "2026-03-01", "total": 45.00}, ...]

    Returns:
        Plotly Figure or None if no data.
    """
    if not daily_data:
        return None

    dates = [row["date"] for row in daily_data]
    totals = [row["total"] for row in daily_data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=totals,
        mode="lines",
        line=dict(color=ACCENT, width=2, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(217,168,100,0.08)",
        hovertemplate="%{x}<br>$%{y:,.2f}<extra></extra>",
    ))

    # 7-day moving average overlay
    if len(totals) >= 7:
        ma7 = []
        for i in range(len(totals)):
            window = totals[max(0, i - 6):i + 1]
            ma7.append(sum(window) / len(window))
        fig.add_trace(go.Scatter(
            x=dates,
            y=ma7,
            mode="lines",
            line=dict(color=WARNING, width=1.5, dash="dot"),
            hovertemplate="7-day avg: $%{y:,.2f}<extra></extra>",
            name="7-day avg",
        ))

    layout = _base_layout(height=280)
    layout["showlegend"] = len(totals) >= 7
    if len(totals) >= 7:
        layout["legend"] = dict(
            font=dict(size=10, color=TEXT_SECONDARY),
            orientation="h",
            y=1.05,
            x=0.5,
            xanchor="center",
        )
    fig.update_layout(**layout)

    return fig


# ── 4. Budget Performance Heatmap ─────────────────────────────

def budget_performance_heatmap(performance: list[dict]) -> go.Figure | None:
    """Heatmap of budget usage percentage by category x month.

    Args:
        performance: from BudgetAnalyzer.get_historical_budget_performance()
            [{"month": "2026-01", "category": "food", "budget": 500,
              "spent": 430, "percentage": 86.0, "status": "warning"}, ...]

    Returns:
        Plotly Figure or None if no data.
    """
    if not performance:
        return None

    months = sorted(set(row["month"] for row in performance))
    categories = sorted(set(row["category"] for row in performance))

    # Build percentage matrix (categories as rows, months as columns)
    z: list[list[float]] = []
    text: list[list[str]] = []
    for cat in categories:
        row_z: list[float] = []
        row_text: list[str] = []
        for m in months:
            match = [r for r in performance if r["month"] == m and r["category"] == cat]
            if match:
                pct = match[0]["percentage"]
                spent = match[0]["spent"]
                budget = match[0]["budget"]
                row_z.append(pct)
                row_text.append(f"${spent:,.0f}/${budget:,.0f} ({pct:.0f}%)")
            else:
                row_z.append(0)
                row_text.append("No data")
        z.append(row_z)
        text.append(row_text)

    # Custom colorscale: green (0%) → gold (75%) → coral (100%+)
    colorscale = [
        [0.0, SUCCESS],
        [0.5, WARNING],
        [0.75, DANGER],
        [1.0, "#c0392b"],
    ]

    fig = go.Figure()
    fig.add_trace(go.Heatmap(
        z=z,
        x=months,
        y=[c.capitalize() for c in categories],
        text=text,
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorscale=colorscale,
        zmin=0,
        zmax=150,
        colorbar=dict(
            title=dict(text="% of budget", font=dict(size=10, color=TEXT_SECONDARY)),
            tickfont=dict(size=9, color=TEXT_TERTIARY),
            ticksuffix="%",
            len=0.8,
        ),
        hovertemplate="%{y} — %{x}<br>%{text}<extra></extra>",
    ))

    layout = _base_layout(
        height=max(200, 50 * len(categories) + 80),
    )
    layout["yaxis"]["showgrid"] = False
    layout["yaxis"]["tickprefix"] = ""
    layout["xaxis"]["side"] = "top"
    fig.update_layout(**layout)

    return fig


# ── 5. Category Trend Line (single category over time) ───────

def category_trend_line(
    category: str,
    trend_data: list[dict],
    budget_limit: float | None = None,
) -> go.Figure | None:
    """Line chart for one category's monthly spending with optional budget line.

    Args:
        category:     category name (e.g. "food")
        trend_data:   from ExpenseTracker.get_category_trend(category)
            [{"month": "2026-01", "total": 350.00}, ...]
        budget_limit: optional monthly budget for this category

    Returns:
        Plotly Figure or None if no data.
    """
    if not trend_data:
        return None

    months = [row["month"] for row in trend_data]
    totals = [row["total"] for row in trend_data]

    fig = go.Figure()

    # Budget reference line
    if budget_limit and budget_limit > 0:
        fig.add_hline(
            y=budget_limit,
            line_dash="dash",
            line_color=DANGER,
            line_width=1,
            annotation_text=f"Budget ${budget_limit:,.0f}",
            annotation_font=dict(size=9, color=DANGER),
            annotation_position="top right",
        )

    fig.add_trace(go.Scatter(
        x=months,
        y=totals,
        mode="lines+markers",
        line=dict(color=ACCENT, width=2.5),
        marker=dict(size=8, color=ACCENT, line=dict(width=2, color=SURFACE)),
        text=[f"${t:,.0f}" for t in totals],
        textposition="top center",
        textfont=dict(size=10, color=TEXT_SECONDARY),
        hovertemplate=f"{category.capitalize()}<br>%{{x}}: $%{{y:,.2f}}<extra></extra>",
    ))

    layout = _base_layout(height=260)
    fig.update_layout(**layout)

    return fig
