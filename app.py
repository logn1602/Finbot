"""
FinBot - AI Financial Advisor Voice Assistant
Main application with Supabase auth + persistent storage.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import os
from streamlit_mic_recorder import mic_recorder

# ============================================================
# PAGE CONFIG (must be first)
# ============================================================
st.set_page_config(
    page_title="FinBot - AI Financial Advisor",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# AUTH GATE — must happen before any other imports that need DB
# ============================================================
from auth.auth import login, signup, logout, seed_default_budgets

def show_auth_page():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { font-family: 'Inter', sans-serif; }
        #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div style='text-align:center; padding: 3rem 0 2rem'>
                <span style='font-size: 4rem'>💰</span>
                <h1 style='background: linear-gradient(135deg, #6366f1, #a78bfa, #f472b6);
                            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                            font-size: 2.5rem; margin: 0.5rem 0 0'>FinBot</h1>
                <p style='color: #94a3b8; font-size: 1rem; margin-top: 0.3rem'>
                    Your AI Financial Advisor
                </p>
            </div>
        """, unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔑 Login", "✨ Sign Up"])

        with tab1:
            email = st.text_input("Email", key="login_email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
            if st.button("Login", use_container_width=True, type="primary", key="login_btn"):
                if email and password:
                    with st.spinner("Logging in..."):
                        session, err = login(email, password)
                    if err:
                        st.error(err)
                    else:
                        st.session_state.user = session.user.email
                        st.session_state.user_id = session.user.id
                        st.session_state.access_token = session.access_token
                        from finance.database import ChatHistory
                        ch = ChatHistory()
                        history = ch.load_history()
                        st.session_state.messages = history if history else [
                            {"role": "assistant", "content": "Hey! I'm FinBot, your AI financial advisor. You can talk to me or type — tell me about your expenses, ask about your budget, or get some money advice! 🚀"}
                        ]
                        st.session_state.pending_audio = None
                        st.rerun()
                else:
                    st.warning("Please enter your email and password.")

        with tab2:
            new_email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
            new_pass = st.text_input("Password (min 6 chars)", type="password", key="signup_pass", placeholder="••••••••")
            new_pass2 = st.text_input("Confirm Password", type="password", key="signup_pass2", placeholder="••••••••")
            if st.button("Create Account", use_container_width=True, type="primary", key="signup_btn"):
                if not new_email or not new_pass:
                    st.warning("Please fill in all fields.")
                elif new_pass != new_pass2:
                    st.error("Passwords don't match.")
                elif len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating your account..."):
                        user, err = signup(new_email, new_pass)
                    if err:
                        st.error(err)
                    else:
                        # Need a temp session to seed budgets
                        temp_session, _ = login(new_email, new_pass)
                        if temp_session:
                            seed_default_budgets(temp_session.user.id, temp_session.access_token)
                            st.session_state.user = temp_session.user.email
                            st.session_state.user_id = temp_session.user.id
                            st.session_state.access_token = temp_session.access_token
                            st.session_state.messages = [
                                {"role": "assistant", "content": "Hey! I'm FinBot, your AI financial advisor. You can talk to me or type — tell me about your expenses, ask about your budget, or get some money advice! 🚀"}
                            ]
                            st.session_state.pending_audio = None
                            st.rerun()
                        else:
                            st.success("Account created! Please check your email to confirm, then log in.")


# Show auth page if not logged in
if "user" not in st.session_state or not st.session_state.get("user"):
    show_auth_page()
    st.stop()

# ── Browser timezone detection ───────────────────────────────
from streamlit_js_eval import streamlit_js_eval
if "user_timezone" not in st.session_state:
    tz = streamlit_js_eval(
        js_expressions="Intl.DateTimeFormat().resolvedOptions().timeZone",
        key="get_timezone"
    )
    st.session_state.user_timezone = tz if tz else "America/New_York"

# ============================================================
# IMPORTS (only runs if logged in)
# ============================================================
from voice.stt import SpeechToText
from voice.tts import TextToSpeech
from finance.database import ExpenseTracker, BudgetAnalyzer, ChatHistory
from brain.llm import FinanceBrain

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
        border-right: 1px solid rgba(255,255,255,0.05);
        min-width: 200px !important;
    }
    section[data-testid="stSidebar"] button[kind="header"] { display: none !important; }

    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1));
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 12px;
        padding: 12px 16px;
    }
    div[data-testid="stMetric"] label {
        color: #a5b4fc !important; font-size: 0.8rem !important;
        font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.5px;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #e0e7ff !important; font-size: 1.6rem !important; font-weight: 700 !important;
    }

    div[data-testid="stChatMessage"] {
        border-radius: 16px !important; margin-bottom: 8px;
        border: 1px solid rgba(255,255,255,0.04);
    }
    div[data-testid="stChatInput"] textarea {
        border-radius: 16px !important;
        border: 1px solid rgba(99,102,241,0.3) !important; font-size: 0.95rem !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: rgba(99,102,241,0.6) !important;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.15) !important;
    }

    .stButton > button {
        border-radius: 12px !important; font-weight: 500 !important;
        font-size: 0.85rem !important; transition: all 0.2s ease !important;
        border: 1px solid rgba(99,102,241,0.3) !important;
    }
    .stButton > button:hover {
        border-color: rgba(99,102,241,0.6) !important;
        box-shadow: 0 4px 12px rgba(99,102,241,0.2) !important;
        transform: translateY(-1px);
    }

    .main-title { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
    .main-title h1 {
        font-size: 2.2rem; font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #a78bfa, #f472b6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0;
    }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }

    .sidebar-header {
        color: #a5b4fc; font-size: 0.75rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 1px;
        margin-top: 24px; margin-bottom: 8px; padding-bottom: 6px;
        border-bottom: 1px solid rgba(165,180,252,0.15);
    }

    .insight-card {
        background: rgba(99,102,241,0.06); border-left: 3px solid #6366f1;
        border-radius: 0 8px 8px 0; padding: 10px 14px; margin-bottom: 8px;
        font-size: 0.82rem; color: #cbd5e1; line-height: 1.5;
    }
    .insight-card.warning { border-left-color: #f59e0b; background: rgba(245,158,11,0.06); }
    .insight-card.danger  { border-left-color: #ef4444; background: rgba(239,68,68,0.06); }
    .insight-card.success { border-left-color: #22c55e; background: rgba(34,197,94,0.06); }

    .status-badge {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .badge-ok      { background: rgba(34,197,94,0.15); color: #4ade80; }
    .badge-warning { background: rgba(245,158,11,0.15); color: #fbbf24; }
    .badge-over    { background: rgba(239,68,68,0.15);  color: #f87171; }

    .mic-area { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
    .mic-label { color: #94a3b8; font-size: 0.82rem; }
    .user-pill {
        background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.2);
        border-radius: 20px; padding: 6px 14px; font-size: 0.8rem; color: #a5b4fc;
        display: inline-block; margin-bottom: 8px;
    }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# INITIALIZE COMPONENTS
# ============================================================

@st.cache_resource
def init_stt():
    return SpeechToText()

@st.cache_resource
def init_tts():
    return TextToSpeech(default_lang="en", gender="male")

@st.cache_resource
def init_brain():
    return FinanceBrain()

brain = init_brain()

# Per-user instances (not cached — each user needs their own)
tracker = ExpenseTracker()
analyzer = BudgetAnalyzer()
chat_history = ChatHistory()

# Session state defaults
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hey! I'm FinBot, your AI financial advisor. You can talk to me or type — tell me about your expenses, ask about your budget, or get some money advice! 🚀"}
    ]
if "pending_audio" not in st.session_state:
    st.session_state.pending_audio = None

# ============================================================
# CORE LOGIC
# ============================================================

def process_user_input(user_text: str, language: str = None) -> dict:
    financial_context = analyzer.generate_context_for_llm()
    result = brain.process_message(user_text, financial_context, language=language)
    intent = result["intent"]
    intent_type = intent.get("intent", "get_advice")
    entities = intent.get("entities", {})
    detected_lang = result["language"]

    if intent_type == "add_expense":
        amount = entities.get("amount")
        category = entities.get("category", "other")
        description = entities.get("description", "")
        if amount and float(amount) > 0:
            tracker.add_expense(float(amount), category, description)
            updated_context = analyzer.generate_context_for_llm()
            response = brain.generate_response(
                f"I just logged an expense of {amount} in {category}. Give me a quick update.",
                updated_context, language=detected_lang
            )
            # Save to DB
            chat_history.save_message("user", user_text)
            chat_history.save_message("assistant", response)
            return {"response": response, "language": detected_lang}

    elif intent_type == "set_budget":
        amount = entities.get("amount")
        category = entities.get("category")
        if amount and category:
            analyzer.set_budget(category, float(amount))
            updated_context = analyzer.generate_context_for_llm()
            response = brain.generate_response(
                f"I just set the {category} budget to {amount}. Confirm this to the user.",
                updated_context, language=detected_lang
            )
            chat_history.save_message("user", user_text)
            chat_history.save_message("assistant", response)
            return {"response": response, "language": detected_lang}

    # Save for all other intents
    chat_history.save_message("user", user_text)
    chat_history.save_message("assistant", result["response"])
    return {"response": result["response"], "language": detected_lang}


def generate_audio(response_text: str, language: str = "en") -> str:
    tts = init_tts()
    return tts.generate_file(response_text, language=language, output_path="response.mp3")


# ============================================================
# SIDEBAR — FINANCIAL DASHBOARD
# ============================================================
with st.sidebar:
    st.markdown("""
        <div style="text-align: center; padding: 8px 0 16px 0;">
            <span style="font-size: 2.5rem;">💰</span>
            <h2 style="margin: 4px 0 0 0; font-size: 1.3rem; font-weight: 700;
                        background: linear-gradient(135deg, #6366f1, #a78bfa);
                        -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                Financial Dashboard
            </h2>
        </div>
    """, unsafe_allow_html=True)

    # User info + logout
    st.markdown(f'<div class="user-pill">👤 {st.session_state.user}</div>', unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        logout()
        st.rerun()

    # --- Overview Metrics ---
    total_month = tracker.get_total_spent(days=30)
    total_today_expenses = tracker.get_today_expenses()
    total_today = sum(e["amount"] for e in total_today_expenses)

    st.markdown('<div class="sidebar-header">📊 Overview</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    col1.metric("This Month", f"${total_month:,.0f}")
    col2.metric("Today", f"${total_today:,.0f}")

    # --- Budget Status ---
    st.markdown('<div class="sidebar-header">🎯 Budget Status</div>', unsafe_allow_html=True)
    budget_status = analyzer.get_budget_status()
    active_budgets = [b for b in budget_status if b["spent"] > 0]

    if active_budgets:
        for b in active_budgets:
            pct = min(b["percentage"], 100)
            if b["status"] == "over":
                bar_color, badge_class, badge_text = "#ef4444", "badge-over", "OVER"
            elif b["status"] == "warning":
                bar_color, badge_class, badge_text = "#f59e0b", "badge-warning", "WARNING"
            else:
                bar_color, badge_class, badge_text = "#22c55e", "badge-ok", "ON TRACK"

            st.markdown(f"""
                <div style="margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <span style="font-size: 0.82rem; font-weight: 600; color: #e2e8f0; text-transform: capitalize;">
                            {b['category']}
                        </span>
                        <span class="status-badge {badge_class}">{badge_text}</span>
                    </div>
                    <div style="background: rgba(255,255,255,0.06); border-radius: 8px; height: 8px; overflow: hidden;">
                        <div style="width: {min(b['percentage'], 100)}%; height: 100%;
                                    background: {bar_color}; border-radius: 8px;
                                    transition: width 0.5s ease;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 3px;">
                        <span style="font-size: 0.7rem; color: #64748b;">${b['spent']:,.0f} spent</span>
                        <span style="font-size: 0.7rem; color: #64748b;">${b['budget']:,.0f} limit</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # Category donut chart
        st.markdown('<div class="sidebar-header">📈 Category Breakdown</div>', unsafe_allow_html=True)
        cats = [b["category"].title() for b in active_budgets]
        spent_vals = [b["spent"] for b in active_budgets]
        colors = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd",
                  "#e879f9", "#f472b6", "#fb7185", "#f87171"]

        fig_donut = go.Figure(data=[go.Pie(
            labels=cats, values=spent_vals, hole=0.6,
            marker=dict(colors=colors[:len(cats)]),
            textinfo="percent", textfont_size=11,
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>"
        )])
        fig_donut.update_layout(
            height=220, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(font=dict(size=10, color="#94a3b8"), orientation="h",
                       y=-0.15, x=0.5, xanchor="center"),
            showlegend=True
        )
        st.plotly_chart(fig_donut, width="stretch")
    else:
        st.markdown("""
            <div style="text-align: center; padding: 30px 20px; color: #64748b;">
                <span style="font-size: 2rem;">📝</span>
                <p style="margin-top: 8px; font-size: 0.85rem;">No expenses logged yet.<br>Start chatting to track spending!</p>
            </div>
        """, unsafe_allow_html=True)

    # --- 7-Day Trend ---
    st.markdown('<div class="sidebar-header">📉 7-Day Trend</div>', unsafe_allow_html=True)
    daily = tracker.get_daily_totals(days=7)
    if daily:
        df = pd.DataFrame(daily)
        df["date"] = pd.to_datetime(df["date"])
        df["day"] = df["date"].dt.strftime("%a")

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=df["day"], y=df["total"],
            mode="lines+markers+text",
            line=dict(color="#6366f1", width=2.5, shape="spline"),
            marker=dict(size=8, color="#6366f1", line=dict(width=2, color="#1a1a2e")),
            text=[f"${v:,.0f}" for v in df["total"]],
            textposition="top center",
            textfont=dict(size=9, color="#a5b4fc"),
            fill="tozeroy", fillcolor="rgba(99,102,241,0.08)"
        ))
        fig_trend.update_layout(
            height=180, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#64748b", tickfont=dict(size=10)),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)",
                      color="#64748b", tickfont=dict(size=9)),
            showlegend=False
        )
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.caption("No data for the past 7 days yet.")

    # --- Insights ---
    st.markdown('<div class="sidebar-header">💡 Smart Insights</div>', unsafe_allow_html=True)
    insights = analyzer.get_spending_insights()
    for insight in insights:
        if "exceeded" in insight.lower() or "over" in insight.lower():
            card_class = "danger"
        elif "heads up" in insight.lower() or "warning" in insight.lower() or "above" in insight.lower():
            card_class = "warning"
        elif "looking good" in insight.lower() or "within" in insight.lower():
            card_class = "success"
        else:
            card_class = ""
        st.markdown(f'<div class="insight-card {card_class}">{insight}</div>', unsafe_allow_html=True)


# ============================================================
# MAIN CHAT AREA
# ============================================================
st.markdown("""
    <div class="main-title">
        <span style="font-size: 2.5rem;">💰</span>
        <h1>FinBot</h1>
    </div>
    <p class="subtitle">Your AI Financial Advisor — Talk or Type in any language!</p>
""", unsafe_allow_html=True)

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Play pending audio after chat renders
if st.session_state.pending_audio and os.path.exists(st.session_state.pending_audio):
    st.audio(st.session_state.pending_audio, autoplay=True)
    st.session_state.pending_audio = None

# --- Voice Input ---
st.markdown('<div class="mic-area">', unsafe_allow_html=True)
col_mic, col_mic_label = st.columns([1, 4])
with col_mic:
    audio_data = mic_recorder(
        start_prompt="🎤 Speak", stop_prompt="⏹️ Stop",
        just_once=True, use_container_width=True, key="mic_recorder"
    )
with col_mic_label:
    st.markdown('<span class="mic-label">Click 🎤 to record, then ⏹️ to stop</span>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

if audio_data and audio_data.get("bytes"):
    with st.spinner("🧠 Transcribing & thinking..."):
        stt = init_stt()
        stt_result = stt.transcribe_bytes(audio_data["bytes"])
        if stt_result["text"]:
            user_text = stt_result["text"]
            detected_lang = stt_result["language"]
            st.session_state.messages.append({"role": "user", "content": user_text})
            result = process_user_input(user_text, language=detected_lang)
            st.session_state.messages.append({"role": "assistant", "content": result["response"]})
            audio_path = generate_audio(result["response"], language=result["language"])
            st.session_state.pending_audio = audio_path
            st.rerun()
        else:
            st.warning("Couldn't catch that. Try speaking louder or closer to your mic.")

# --- Text Input ---
if user_text := st.chat_input("💬 Type a message... (e.g., 'I spent 300 on lunch')"):
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.write(user_text)
    with st.chat_message("assistant"):
        with st.spinner("🧠 Thinking..."):
            result = process_user_input(user_text)
            st.write(result["response"])
    st.session_state.messages.append({"role": "assistant", "content": result["response"]})
    audio_path = generate_audio(result["response"], language=result["language"])
    st.session_state.pending_audio = audio_path
    st.rerun()

# --- Quick Actions ---
st.divider()
st.markdown('<div class="quick-actions">', unsafe_allow_html=True)
quick_cols = st.columns(4)
quick_prompts = [
    ("📊", "How much did I spend today?"),
    ("🎯", "Am I within my budget?"),
    ("💡", "Give me a savings tip"),
    ("📈", "Show my spending patterns")
]
for i, col in enumerate(quick_cols):
    icon, text = quick_prompts[i]
    if col.button(f"{icon} {text}", width="stretch"):
        full_prompt = f"{icon} {text}"
        st.session_state.messages.append({"role": "user", "content": full_prompt})
        with st.spinner("🧠 Thinking..."):
            result = process_user_input(full_prompt)
        st.session_state.messages.append({"role": "assistant", "content": result["response"]})
        audio_path = generate_audio(result["response"], language=result["language"])
        st.session_state.pending_audio = audio_path
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)