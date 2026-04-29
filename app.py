"""
FinBot — AI Voice Financial Assistant
Premium dark UI with warm gold accent, custom chat bubbles, hero stats.
"""

import os
import re
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_mic_recorder import mic_recorder

# ── Page config (must be first Streamlit call) ─────────────────
st.set_page_config(
    page_title="FinBot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth gate ──────────────────────────────────────────────────
from auth.auth import login, logout, seed_default_budgets, signup
from styles.styles import get_global_css
from styles.tokens import (
    ACCENT, BG, BORDER, BORDER_STRONG, DANGER, ON_ACCENT,
    SUCCESS, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, WARNING,
)

DEBUG = os.getenv("FINBOT_DEBUG", "0") == "1"


# ── Helpers ────────────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """Remove markdown syntax that breaks the custom HTML chat UI."""
    text = re.sub(r'`+([^`]*)`+', r'\1', text)          # backticks
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)       # bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)           # italic
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # headers
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)    # bullets
    return text.strip()


# Language pill labels: script character + English name
LANG_LABELS = {
    "hi": "हि Hindi",     "ta": "த Tamil",      "te": "తె Telugu",
    "bn": "বাং Bengali",  "mr": "म Marathi",    "gu": "ગુ Gujarati",
    "kn": "ಕ Kannada",    "ml": "മ Malayalam",  "pa": "ਪੰ Punjabi",
    "ur": "اردو Urdu",    "es": "ES Spanish",   "fr": "FR French",
    "de": "DE German",    "zh": "中 Chinese",   "ja": "日 Japanese",
    "ko": "한 Korean",    "ar": "عر Arabic",    "pt": "PT Portuguese",
    "ru": "РУ Russian",   "it": "IT Italian",
}


def _category_breakdown_html(budget_status: list) -> str:
    """Render the inline budget-breakdown table as an HTML string."""
    active = [b for b in budget_status if b["budget"] > 0]
    if not active:
        return "<p style='color:var(--text-tertiary);font-size:0.82rem'>No budget data yet.</p>"

    rows = []
    for b in active:
        pct = min(b["percentage"], 100)
        if b["status"] == "over":
            badge_cls, bar_color = "fb-badge-danger",  DANGER
        elif b["status"] == "warning":
            badge_cls, bar_color = "fb-badge-warning", WARNING
        else:
            badge_cls, bar_color = "fb-badge-ok",      SUCCESS

        badge_text = {"over": "OVER", "warning": "WARN", "ok": "OK"}[b["status"]]
        rows.append(f"""
        <div class="fb-category-row">
            <span class="fb-cat-name">{b['category']}</span>
            <span class="fb-cat-amounts">${b['spent']:,.0f} / ${b['budget']:,.0f}</span>
            <span class="fb-status-badge {badge_cls}">{badge_text}</span>
            <span class="fb-cat-pct">{b['percentage']:.0f}%</span>
            <div class="fb-cat-bar-wrap">
                <div class="fb-cat-bar-fill" style="width:{pct}%;background:{bar_color}"></div>
            </div>
        </div>""")

    return f"""
    <div class="fb-breakdown-wrap">
        <div class="fb-breakdown-title">Budget breakdown — this month</div>
        {''.join(rows)}
    </div>"""


def _safe_text(text: str) -> str:
    """Escape only angle brackets so they don't break HTML structure.
    Apostrophes and quotes are intentionally left unescaped — html.escape()
    converts them to &#x27; which Streamlit's markdown renderer shows literally."""
    return (strip_markdown(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>"))


def _render_chat(messages: list) -> None:
    """Render each chat message as its own st.markdown call.
    One-big-block rendering caused Streamlit's markdown parser to strip
    opening div tags (with classes) while leaving closing tags as raw text.
    Per-message calls with inline flex styles sidestep the parser entirely."""
    for msg in messages:
        role = msg["role"]

        if role == "assistant":
            if msg.get("type") == "breakdown":
                # Breakdown HTML is already safe — wrap in a left-aligned bot bubble
                st.markdown(
                    f'<div style="display:flex;justify-content:flex-start;margin:2px 0 6px">'
                    f'<div class="fb-bubble-bot">{msg["content"]}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                text = _safe_text(msg["content"])
                st.markdown(
                    f'<div style="display:flex;justify-content:flex-start;margin:2px 0 6px">'
                    f'<div class="fb-bubble-bot">{text}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            text = _safe_text(msg["content"])
            lang = msg.get("language", "en")
            pill = ""
            if lang and lang != "en" and lang in LANG_LABELS:
                pill = (f'<div style="text-align:right;margin-bottom:3px">'
                        f'<span class="fb-lang-pill">{LANG_LABELS[lang]}</span></div>')
            st.markdown(
                f'{pill}'
                f'<div style="display:flex;justify-content:flex-end;margin:2px 0 6px">'
                f'<div class="fb-bubble-user">{text}</div></div>',
                unsafe_allow_html=True,
            )


def _latency_caption(stt_ms: float, llm_ms: float, tts_ms: float) -> str:
    total = stt_ms + llm_ms + tts_ms
    parts = []
    if stt_ms > 0:
        parts.append(f"STT {stt_ms/1000:.1f}s")
    parts.append(f"LLM {llm_ms/1000:.1f}s")
    parts.append(f"TTS {tts_ms/1000:.1f}s")
    parts.append(f"total {total/1000:.1f}s")
    return "⚡ " + " · ".join(parts)


# ── Auth page ──────────────────────────────────────────────────

def show_auth_page() -> None:
    st.markdown(f"<style>{get_global_css()}</style>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown(f"""
        <div style='text-align:center;padding:3rem 0 2rem'>
            <div style='font-size:3rem'>💰</div>
            <h1 style='font-family:Fraunces,Georgia,serif;font-size:2.2rem;
                        font-weight:500;color:{ACCENT};margin:8px 0 4px;letter-spacing:-0.5px'>
                FinBot
            </h1>
            <p style='color:{TEXT_TERTIARY};font-size:0.88rem;margin:0'>
                Your AI financial advisor — in any language
            </p>
        </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Sign in", "Create account"])

        with tab1:
            email    = st.text_input("Email",    key="login_email",    placeholder="you@example.com")
            password = st.text_input("Password", key="login_pass",     placeholder="••••••••", type="password")
            if st.button("Sign in", use_container_width=True, type="primary", key="login_btn"):
                if email and password:
                    with st.spinner("Signing in…"):
                        session, err = login(email, password)
                    if err:
                        st.error(err)
                    else:
                        _init_session(session)
                        st.rerun()
                else:
                    st.warning("Please enter your email and password.")

        with tab2:
            new_email  = st.text_input("Email",            key="signup_email",  placeholder="you@example.com")
            new_pass   = st.text_input("Password (6+ chars)", key="signup_pass",
                                       placeholder="••••••••", type="password")
            new_pass2  = st.text_input("Confirm password", key="signup_pass2",  placeholder="••••••••", type="password")
            if st.button("Create account", use_container_width=True, type="primary", key="signup_btn"):
                if not new_email or not new_pass:
                    st.warning("Please fill in all fields.")
                elif new_pass != new_pass2:
                    st.error("Passwords don't match.")
                elif len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account…"):
                        _, err = signup(new_email, new_pass)
                    if err:
                        st.error(err)
                    else:
                        temp_session, _ = login(new_email, new_pass)
                        if temp_session:
                            _init_session(temp_session)
                            st.rerun()
                        else:
                            st.success("Account created! Check your email to confirm, then sign in.")


def _init_session(session) -> None:
    """Populate session state after a successful login."""
    st.session_state.user         = session.user.email
    st.session_state.user_id      = session.user.id
    st.session_state.access_token = session.access_token
    seed_default_budgets(session.user.id, session.access_token)
    from finance.database import ChatHistory
    history = ChatHistory().load_history()
    st.session_state.messages     = history if history else _welcome_messages()
    st.session_state.pending_audio = None
    st.session_state.last_latency  = None
    st.session_state.undo_expense  = None


def _welcome_messages() -> list:
    return [{"role": "assistant",
             "content": "Hey! I'm FinBot — your AI financial advisor. "
                        "Tell me what you spent, ask about your budget, or just say hi. "
                        "I understand 20+ languages, so speak freely. 🎙️"}]


# ── Check auth ─────────────────────────────────────────────────
if "user" not in st.session_state or not st.session_state.get("user"):
    show_auth_page()
    st.stop()

# ── Browser timezone ───────────────────────────────────────────
from streamlit_js_eval import streamlit_js_eval
if "user_timezone" not in st.session_state:
    tz = streamlit_js_eval(
        js_expressions="Intl.DateTimeFormat().resolvedOptions().timeZone",
        key="get_timezone",
    )
    st.session_state.user_timezone = tz or "America/New_York"

# ── Module imports (post-auth) ─────────────────────────────────
from brain.llm import FinanceBrain
from finance.database import BudgetAnalyzer, ChatHistory, ExpenseTracker
from styles.plotly_theme import (
    DONUT_COLORS, donut_layout, sparkline_layout, sparkline_trace, trend_layout,
)
from voice.stt import SpeechToText
from voice.tts import TextToSpeech

# ── Inject global CSS ──────────────────────────────────────────
st.markdown(f"<style>{get_global_css()}</style>", unsafe_allow_html=True)

# ── Cached resource init ───────────────────────────────────────
@st.cache_resource
def init_stt():   return SpeechToText()

@st.cache_resource
def init_tts():   return TextToSpeech(default_lang="en", gender="male")

@st.cache_resource
def init_brain(): return FinanceBrain()

brain        = init_brain()
tracker      = ExpenseTracker()
analyzer     = BudgetAnalyzer()
chat_history = ChatHistory()

# ── Session state defaults ─────────────────────────────────────
if "messages"      not in st.session_state: st.session_state.messages      = _welcome_messages()
if "pending_audio" not in st.session_state: st.session_state.pending_audio = None
if "last_latency"  not in st.session_state: st.session_state.last_latency  = None
if "undo_expense"  not in st.session_state: st.session_state.undo_expense  = None


# ── Core pipeline ──────────────────────────────────────────────

def process_user_input(user_text: str, language: str = None, stt_ms: float = 0.0) -> dict:
    t0 = time.perf_counter()
    financial_context = analyzer.generate_context_for_llm()
    result            = brain.process_message(user_text, financial_context, language=language)
    llm_ms            = (time.perf_counter() - t0) * 1000

    intent_type   = result["intent"].get("intent", "get_advice")
    entities      = result["intent"].get("entities", {})
    detected_lang = result["language"]

    if intent_type == "add_expense":
        amount   = entities.get("amount")
        category = entities.get("category", "other")
        desc     = entities.get("description", "")
        if amount and float(amount) > 0:
            # Log immediately (optimistic)
            exp = tracker.add_expense(float(amount), category, desc)
            # Store for undo
            st.session_state.undo_expense = {
                "label":    f"${float(amount):,.0f} · {category}",
                "logged":   True,
            }
            updated_context = analyzer.generate_context_for_llm()
            response = brain.generate_response(
                f"I just logged ${float(amount):,.0f} in {category}. Give a brief confirmation and budget status.",
                updated_context, language=detected_lang,
            )
            chat_history.save_message("user",      user_text)
            chat_history.save_message("assistant", response)
            return {"response": response, "language": detected_lang,
                    "stt_ms": stt_ms, "llm_ms": llm_ms}

    elif intent_type == "set_budget":
        amount   = entities.get("amount")
        category = entities.get("category")
        if amount and category:
            analyzer.set_budget(category, float(amount))
            updated_context = analyzer.generate_context_for_llm()
            response = brain.generate_response(
                f"I just set the {category} budget to {amount}. Confirm this.",
                updated_context, language=detected_lang,
            )
            chat_history.save_message("user",      user_text)
            chat_history.save_message("assistant", response)
            return {"response": response, "language": detected_lang,
                    "stt_ms": stt_ms, "llm_ms": llm_ms}

    chat_history.save_message("user",      user_text)
    chat_history.save_message("assistant", result["response"])
    return {"response": result["response"], "language": detected_lang,
            "stt_ms": stt_ms, "llm_ms": llm_ms}


def generate_audio(text: str, language: str = "en") -> tuple[str, float]:
    tts = init_tts()
    t0  = time.perf_counter()
    path = tts.generate_file(text, language=language, output_path="response.mp3")
    return path, (time.perf_counter() - t0) * 1000


def _dispatch(user_text: str, language: str = None, stt_ms: float = 0.0) -> None:
    """Process input, append messages, queue audio, rerun."""
    result     = process_user_input(user_text, language=language, stt_ms=stt_ms)
    audio_path, tts_ms = generate_audio(result["response"], language=result["language"])

    st.session_state.messages.append({"role": "user",      "content": user_text,
                                       "language": result["language"]})
    st.session_state.messages.append({"role": "assistant", "content": result["response"]})
    st.session_state.pending_audio = audio_path
    if DEBUG:
        st.session_state.last_latency = _latency_caption(stt_ms, result["llm_ms"], tts_ms)
    st.rerun()


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    total_month = tracker.get_total_spent(days=30)
    total_today = sum(e["amount"] for e in tracker.get_today_expenses())

    st.markdown(f"""
    <div class="fb-sidebar-top">
        <div class="fb-sidebar-logo">💰 FinBot</div>
        <div class="fb-sidebar-email">{st.session_state.user}</div>
    </div>
    <div class="fb-sidebar-stat-row">
        <span class="fb-sidebar-stat-label">This month</span>
        <span class="fb-sidebar-stat-value">${total_month:,.0f}</span>
    </div>
    <div class="fb-sidebar-stat-row">
        <span class="fb-sidebar-stat-label">Today</span>
        <span class="fb-sidebar-stat-value">${total_today:,.0f}</span>
    </div>
    """, unsafe_allow_html=True)

    # 7-day sparkline
    daily = tracker.get_daily_totals(days=7)
    if daily:
        df = pd.DataFrame(daily)
        df["date"] = pd.to_datetime(df["date"])
        df["day"]  = df["date"].dt.strftime("%a")
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=df["day"], y=df["total"],
            mode="lines+markers+text",
            line=dict(color=ACCENT, width=2, shape="spline"),
            marker=dict(size=6, color=ACCENT, line=dict(width=1.5, color=SURFACE)),
            text=[f"${v:,.0f}" for v in df["total"]],
            textposition="top center",
            textfont=dict(size=8, color=TEXT_TERTIARY),
            fill="tozeroy",
            fillcolor="rgba(217,168,100,0.07)",
        ))
        fig_trend.update_layout(**trend_layout(height=150))
        st.markdown('<div class="fb-trend-label">7-day trend</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sign out", use_container_width=True):
        logout()
        st.rerun()


# ── Main area ──────────────────────────────────────────────────

# Header
st.markdown(f"""
<div class="fb-header">
    <span class="fb-header-title">FinBot</span>
    <span class="fb-header-sub">your AI financial advisor</span>
</div>
""", unsafe_allow_html=True)

# ── Hero stats ─────────────────────────────────────────────────
total_month       = tracker.get_total_spent(days=30)
today_expenses    = tracker.get_today_expenses()
total_today       = sum(e["amount"] for e in today_expenses)
today_count       = len(today_expenses)
budget_status     = analyzer.get_budget_status()
active_budgets    = [b for b in budget_status if b["budget"] > 0]

# Budget-left aggregate
total_budget  = sum(b["budget"]  for b in active_budgets)
total_spent_b = sum(b["spent"]   for b in active_budgets)
budget_left   = total_budget - total_spent_b
budget_pct    = (total_spent_b / total_budget * 100) if total_budget > 0 else 0

if budget_pct >= 90:
    bval_cls = "fb-stat-value-danger"
elif budget_pct >= 70:
    bval_cls = "fb-stat-value-warning"
else:
    bval_cls = "fb-stat-value-success"

# 30-day sparkline data
daily_30 = tracker.get_daily_totals(days=30)

col_hero, col_today, col_budget = st.columns([1.7, 1, 1])

with col_hero:
    st.markdown(f"""
    <div class="fb-hero-card">
        <div class="fb-stat-label">Spent this month</div>
        <div class="fb-stat-value">${total_month:,.0f}</div>
        <div class="fb-stat-sub">30-day total</div>
    </div>
    """, unsafe_allow_html=True)
    if daily_30:
        df30 = pd.DataFrame(daily_30)
        fig_spark = go.Figure()
        fig_spark.add_trace(go.Scatter(**sparkline_trace(
            list(range(len(df30))), df30["total"].tolist()
        )))
        fig_spark.update_layout(**sparkline_layout(height=56))
        st.plotly_chart(fig_spark, use_container_width=True,
                        config={"displayModeBar": False, "staticPlot": True})

with col_today:
    st.markdown(f"""
    <div class="fb-stat-card">
        <div class="fb-stat-label">Today</div>
        <div class="fb-stat-value-sm">${total_today:,.0f}</div>
        <div class="fb-stat-sub">{today_count} expense{'s' if today_count != 1 else ''}</div>
    </div>
    """, unsafe_allow_html=True)

with col_budget:
    st.markdown(f"""
    <div class="fb-stat-card">
        <div class="fb-stat-label">Budget left</div>
        <div class="fb-stat-value-sm {bval_cls}">${budget_left:,.0f}</div>
        <div class="fb-stat-sub">{100 - budget_pct:.0f}% remaining</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ── Inject breakdown as first bot message if data exists & not yet injected ──
if active_budgets and not any(m.get("type") == "breakdown" for m in st.session_state.messages):
    breakdown_html = _category_breakdown_html(budget_status)
    st.session_state.messages.append({
        "role":    "assistant",
        "content": breakdown_html,
        "type":    "breakdown",
    })

# ── Chat messages ──────────────────────────────────────────────
_render_chat(st.session_state.messages)

# ── Pending audio ──────────────────────────────────────────────
if st.session_state.pending_audio and os.path.exists(st.session_state.pending_audio):
    st.audio(st.session_state.pending_audio, autoplay=True)
    if DEBUG and st.session_state.last_latency:
        st.caption(st.session_state.last_latency)
    st.session_state.last_latency  = None
    st.session_state.pending_audio = None

# ── Undo toast ─────────────────────────────────────────────────
if st.session_state.undo_expense:
    undo = st.session_state.undo_expense
    col_msg, col_btn = st.columns([5, 1])
    with col_msg:
        st.markdown(
            f'<div class="fb-undo-toast">✓ Logged {undo["label"]}</div>',
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("Undo", key="undo_btn"):
            deleted = tracker.undo_last_expense()
            st.session_state.undo_expense = None
            if deleted:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Done — removed ${deleted['amount']:,.0f} from {deleted['category']}.",
                })
            st.rerun()

# ── Suggestion chips ───────────────────────────────────────────
CHIPS = [
    ("📊", "How much did I spend today?"),
    ("🎯", "Am I within my budget?"),
    ("💡", "Give me a savings tip"),
    ("📋", "Show breakdown"),
]

st.markdown('<div class="fb-chips-row">', unsafe_allow_html=True)
chip_cols = st.columns(len(CHIPS))
for i, (icon, label) in enumerate(CHIPS):
    with chip_cols[i]:
        st.markdown('<div data-testid="fb-chip">', unsafe_allow_html=True)
        if st.button(f"{icon} {label}", key=f"chip_{i}"):
            if label == "Show breakdown":
                # Re-inject fresh breakdown into chat
                breakdown_html = _category_breakdown_html(analyzer.get_budget_status())
                st.session_state.messages.append({
                    "role": "assistant", "content": breakdown_html, "type": "breakdown"
                })
                st.rerun()
            else:
                _dispatch(f"{icon} {label}")
        st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ── Input area ─────────────────────────────────────────────────
st.markdown('<div class="fb-input-bar">', unsafe_allow_html=True)
col_input, col_mic = st.columns([11, 1])

with col_input:
    if user_text := st.chat_input("Speak or type — I understand 20+ languages…"):
        st.session_state.undo_expense = None  # clear stale undo on new input
        _dispatch(user_text)

with col_mic:
    st.markdown('<div data-testid="fb-mic-recorder">', unsafe_allow_html=True)
    audio_data = mic_recorder(
        start_prompt="🎤",
        stop_prompt="⏹",
        just_once=True,
        use_container_width=True,
        key="mic_recorder",
    )
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# ── Voice input handler ────────────────────────────────────────
if audio_data and audio_data.get("bytes"):
    with st.spinner("Transcribing…"):
        stt         = init_stt()
        t_stt       = time.perf_counter()
        stt_result  = stt.transcribe_bytes(audio_data["bytes"])
        stt_ms      = (time.perf_counter() - t_stt) * 1000
    if stt_result["text"]:
        st.session_state.undo_expense = None
        _dispatch(stt_result["text"],
                  language=stt_result["language"],
                  stt_ms=stt_ms)
    else:
        st.warning("Couldn't catch that — try speaking a little louder.")
