"""
Global CSS for FinBot — premium dark theme with warm gold accent.
Call get_global_css() and inject via st.markdown(f"<style>{css}</style>", unsafe_allow_html=True).
"""


def get_global_css() -> str:
    return """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── CSS variables ───────────────────────────────────────────── */
:root {
    --bg:            #0a0a0b;
    --surface:       #16161a;
    --surface-2:     rgba(255,255,255,0.025);
    --text-primary:  #e8e6e1;
    --text-secondary:rgba(232,230,225,0.6);
    --text-tertiary: rgba(232,230,225,0.4);
    --accent:        #d9a864;
    --accent-dark:   #b8864a;
    --on-accent:     #1a1208;
    --success:       #7fc99a;
    --warning:       #f0c97a;
    --danger:        #e08a7a;
    --border:        rgba(255,255,255,0.06);
    --border-strong: rgba(255,255,255,0.10);
}

/* ── Global resets ───────────────────────────────────────────── */
.stApp {
    background: var(--bg) !important;
    font-family: 'Inter', system-ui, sans-serif;
    color: var(--text-primary);
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }

/* ── Sidebar ─────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
section[data-testid="stSidebar"] > div { padding-top: 0 !important; }

.fb-sidebar-top {
    padding: 20px 16px 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 4px;
}
.fb-sidebar-logo {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 1.3rem;
    color: var(--accent);
    letter-spacing: -0.3px;
    margin-bottom: 4px;
}
.fb-sidebar-email {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.68rem;
    color: var(--text-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 180px;
}
.fb-sidebar-stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
}
.fb-sidebar-stat-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-tertiary);
    font-family: 'Inter', system-ui;
}
.fb-sidebar-stat-value {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.95rem;
    color: var(--text-primary);
}
.fb-trend-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-tertiary);
    padding: 12px 16px 4px;
}

/* ── Main header ─────────────────────────────────────────────── */
.fb-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 2px;
    padding-top: 8px;
}
.fb-header-title {
    font-family: 'Fraunces', Georgia, serif;
    font-size: 2rem;
    font-weight: 500;
    color: var(--accent);
    margin: 0;
    line-height: 1;
    letter-spacing: -0.5px;
}
.fb-header-sub {
    font-size: 0.82rem;
    color: var(--text-tertiary);
    font-family: 'Inter', system-ui;
}

/* ── Hero stat cards ─────────────────────────────────────────── */
.fb-hero-card {
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: 18px;
    padding: 20px 22px 12px;
    position: relative;
    overflow: hidden;
    height: 100%;
}
.fb-hero-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent) 0%, transparent 70%);
    border-radius: 18px 18px 0 0;
}
.fb-stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 18px 20px;
    height: 100%;
}
.fb-stat-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-tertiary);
    font-family: 'Inter', system-ui;
    margin-bottom: 8px;
}
.fb-stat-value {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 1.9rem;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: -1px;
}
.fb-stat-value-sm {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 1.5rem;
    color: var(--text-primary);
    line-height: 1;
    letter-spacing: -0.5px;
}
.fb-stat-sub {
    font-size: 0.72rem;
    color: var(--text-secondary);
    margin-top: 5px;
    font-family: 'Inter', system-ui;
}
.fb-stat-value-success { color: var(--success) !important; }
.fb-stat-value-warning { color: var(--warning) !important; }
.fb-stat-value-danger  { color: var(--danger)  !important; }

/* ── Chat messages ───────────────────────────────────────────── */
/* Override the default st.chat_message styling */
div[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

.fb-chat-wrap {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin: 12px 0;
}
.fb-msg-row {
    display: flex;
    flex-direction: column;
    margin-bottom: 6px;
}
.fb-msg-row-user {
    align-items: flex-end;
}
.fb-msg-row-bot {
    align-items: flex-start;
}
.fb-bubble-bot {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 4px 18px 18px 18px;
    padding: 13px 17px;
    color: var(--text-primary);
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.88rem;
    line-height: 1.65;
    max-width: 82%;
    word-wrap: break-word;
}
.fb-bubble-user {
    background: var(--accent);
    border-radius: 18px 4px 18px 18px;
    padding: 11px 16px;
    color: var(--on-accent);
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 0.88rem;
    line-height: 1.6;
    max-width: 72%;
    word-wrap: break-word;
}
.fb-lang-pill {
    display: inline-block;
    background: rgba(217,168,100,0.12);
    border: 1px solid rgba(217,168,100,0.25);
    color: var(--accent);
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 20px;
    margin-bottom: 5px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    letter-spacing: 0.3px;
}

/* ── Inline category breakdown table ────────────────────────── */
.fb-breakdown-wrap {
    margin-top: 6px;
}
.fb-breakdown-title {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--text-tertiary);
    margin-bottom: 10px;
    font-family: 'Inter', system-ui;
}
.fb-category-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
}
.fb-category-row:last-child { border-bottom: none; }
.fb-cat-name {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    color: var(--accent);
    font-size: 0.78rem;
    width: 100px;
    flex-shrink: 0;
}
.fb-cat-amounts {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.75rem;
    color: var(--text-secondary);
    flex: 1;
}
.fb-status-badge {
    font-size: 0.6rem;
    font-family: 'Inter', system-ui;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 20px;
    flex-shrink: 0;
    white-space: nowrap;
}
.fb-badge-ok      { background: rgba(127,201,154,0.15); color: var(--success); }
.fb-badge-warning { background: rgba(240,201,122,0.15); color: var(--warning); }
.fb-badge-danger  { background: rgba(224,138,122,0.15); color: var(--danger);  }
.fb-cat-pct {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 0.72rem;
    color: var(--text-tertiary);
    width: 38px;
    text-align: right;
    flex-shrink: 0;
}
.fb-cat-bar-wrap {
    width: 60px;
    height: 4px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    flex-shrink: 0;
}
.fb-cat-bar-fill {
    height: 100%;
    border-radius: 4px;
}

/* ── Undo toast ──────────────────────────────────────────────── */
.fb-undo-toast {
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    padding: 10px 16px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-family: 'Inter', system-ui;
    margin: 6px 0 12px;
}

/* ── Suggestion chips ────────────────────────────────────────── */
.fb-chips-row {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    padding: 4px 0 12px;
}

/* Style the chip buttons */
div[data-testid="fb-chip"] .stButton > button {
    background: var(--surface-2) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 20px !important;
    color: var(--text-secondary) !important;
    font-size: 0.76rem !important;
    padding: 5px 14px !important;
    height: auto !important;
    min-height: 30px !important;
    white-space: nowrap;
    font-weight: 400 !important;
    transition: all 0.15s ease !important;
}
div[data-testid="fb-chip"] .stButton > button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: rgba(217,168,100,0.06) !important;
}

/* ── Mic button ──────────────────────────────────────────────── */
div[data-testid="fb-mic"] .stButton > button {
    width: 40px !important;
    height: 40px !important;
    border-radius: 50% !important;
    background: var(--accent) !important;
    color: var(--on-accent) !important;
    border: none !important;
    font-size: 1rem !important;
    padding: 0 !important;
    min-height: unset !important;
    box-shadow: 0 2px 12px rgba(217,168,100,0.25);
    transition: all 0.2s ease !important;
}
div[data-testid="fb-mic"] .stButton > button:hover {
    background: var(--accent-dark) !important;
    transform: scale(1.06);
    box-shadow: 0 4px 16px rgba(217,168,100,0.35) !important;
    border: none !important;
    color: var(--on-accent) !important;
}

/* Mic recorder custom styling */
div[data-testid="fb-mic-recorder"] button {
    width: 40px !important;
    height: 40px !important;
    border-radius: 50% !important;
    padding: 0 !important;
    font-size: 1rem !important;
    min-height: unset !important;
}

/* Start recording = gold */
div[data-testid="fb-mic-recorder"] button:first-child {
    background: var(--accent) !important;
    color: var(--on-accent) !important;
    border: none !important;
    box-shadow: 0 2px 12px rgba(217,168,100,0.25) !important;
}
/* Stop recording = coral with pulse */
div[data-testid="fb-mic-recorder"] button:last-child {
    background: var(--danger) !important;
    color: #fff !important;
    border: none !important;
    animation: mic-pulse 1.4s ease infinite;
}
@keyframes mic-pulse {
    0%   { box-shadow: 0 0 0 0   rgba(224,138,122,0.5); }
    70%  { box-shadow: 0 0 0 10px rgba(224,138,122,0);   }
    100% { box-shadow: 0 0 0 0   rgba(224,138,122,0);   }
}

/* ── Input bar ───────────────────────────────────────────────── */
.fb-input-bar {
    position: sticky;
    bottom: 0;
    background: var(--bg);
    padding: 10px 0 16px;
    border-top: 1px solid var(--border);
    margin-top: 8px;
    z-index: 50;
}
div[data-testid="stChatInput"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 24px !important;
}
div[data-testid="stChatInput"] textarea {
    background: transparent !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', system-ui !important;
    font-size: 0.88rem !important;
    caret-color: var(--accent) !important;
}
div[data-testid="stChatInput"] textarea::placeholder {
    color: var(--text-tertiary) !important;
}
div[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(217,168,100,0.1) !important;
}

/* ── General button overrides ────────────────────────────────── */
.stButton > button {
    border-radius: 10px !important;
    font-family: 'Inter', system-ui !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    transition: all 0.18s ease !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-secondary) !important;
    background: var(--surface-2) !important;
}
.stButton > button:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    background: rgba(217,168,100,0.05) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: var(--on-accent) !important;
    border-color: var(--accent) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--accent-dark) !important;
    border-color: var(--accent-dark) !important;
    color: var(--on-accent) !important;
}

/* ── Tabs (auth page) ────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: var(--text-secondary) !important;
    font-family: 'Inter', system-ui !important;
    font-size: 0.85rem !important;
}
.stTabs [aria-selected="true"] {
    background: var(--surface-2) !important;
    color: var(--text-primary) !important;
}

/* ── Text inputs (auth page) ─────────────────────────────────── */
div[data-testid="stTextInput"] input {
    background: var(--surface) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: 'Inter', system-ui !important;
    font-size: 0.88rem !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(217,168,100,0.12) !important;
}

/* ── Plotly charts ───────────────────────────────────────────── */
.js-plotly-plot .plotly { background: transparent !important; }

/* ── Spinner ─────────────────────────────────────────────────── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }

/* ── Mobile ──────────────────────────────────────────────────── */
@media (max-width: 640px) {
    .fb-stats-grid { grid-template-columns: 1fr !important; }

    .fb-hero-card, .fb-stat-card { border-radius: 14px; padding: 16px 18px 10px; }

    .fb-stat-value    { font-size: 1.6rem !important; }
    .fb-stat-value-sm { font-size: 1.3rem !important; }

    .stButton > button { min-height: 44px; }

    .fb-chips-row {
        flex-wrap: nowrap;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        -ms-overflow-style: none;
        padding-bottom: 6px;
    }
    .fb-chips-row::-webkit-scrollbar { display: none; }

    div[data-testid="fb-chip"] .stButton > button {
        min-height: 36px !important;
        white-space: nowrap;
    }

    div[data-testid="fb-mic-recorder"] button,
    div[data-testid="fb-mic"] .stButton > button {
        width: 44px !important;
        height: 44px !important;
        min-height: 44px !important;
    }

    .fb-input-bar {
        position: sticky;
        bottom: 0;
        padding: 8px 0 14px;
    }

    .fb-bubble-bot, .fb-bubble-user { max-width: 95%; font-size: 0.85rem; }

    .fb-header-title { font-size: 1.6rem; }
}
"""
