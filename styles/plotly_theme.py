"""
Shared Plotly layout helpers for FinBot charts.
All charts use transparent backgrounds and the warm-gold accent palette.
"""

from styles.tokens import ACCENT, TEXT_SECONDARY, TEXT_TERTIARY, BORDER


def sparkline_layout(height: int = 60) -> dict:
    """Minimal layout for inline sparklines (hero card, sidebar trend)."""
    return dict(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        showlegend=False,
        hovermode=False,
    )


def trend_layout(height: int = 160) -> dict:
    """Layout for the 7-day trend line chart in the sidebar."""
    return dict(
        height=height,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            color=TEXT_TERTIARY,
            tickfont=dict(size=9, color=TEXT_TERTIARY),
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=BORDER,
            color=TEXT_TERTIARY,
            tickfont=dict(size=8, color=TEXT_TERTIARY),
            fixedrange=True,
        ),
        showlegend=False,
    )


def donut_layout(height: int = 200) -> dict:
    """Layout for the category donut chart."""
    return dict(
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            font=dict(size=9, color=TEXT_SECONDARY),
            orientation="h",
            y=-0.15,
            x=0.5,
            xanchor="center",
        ),
        showlegend=True,
    )


# Gold palette for donut slices
DONUT_COLORS = [
    ACCENT,         # gold
    "#b8864a",      # darker gold
    "#c49a5e",      # mid gold
    "#e8be82",      # light gold
    "#7fc99a",      # sage
    "#f0c97a",      # amber
    "#e08a7a",      # coral
    "#94a8c4",      # muted blue
]

# Sparkline trace defaults
def sparkline_trace(x, y) -> dict:
    return dict(
        x=x, y=y,
        mode="lines",
        line=dict(color=ACCENT, width=1.5, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(217,168,100,0.08)",
        hoverinfo="skip",
    )
