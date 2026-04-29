# Migration Notes — Premium Dark Reskin

## What changed

### New files
| File | Purpose |
|---|---|
| `styles/__init__.py` | Package marker |
| `styles/tokens.py` | Design token constants (colours, imported by app and styles.py) |
| `styles/styles.py` | `get_global_css()` — full CSS block injected at app start |
| `styles/plotly_theme.py` | Shared Plotly layout helpers (sparkline, trend, donut) |
| `.streamlit/config.toml` | Streamlit theme config (dark base, gold primary) |
| `MIGRATION.md` | This file |

### Modified files

#### `app.py` (major rewrite)
- CSS now loaded from `styles/styles.py` via `get_global_css()` instead of inline
- Expense confirmation flow **removed**. Expenses log immediately (optimistic write). An undo toast with a 1-click "Undo" button appears instead.
- `pending_expense` session state key **removed**. Replaced with `undo_expense`.
- Chat messages rendered as custom HTML bubbles (`.fb-bubble-bot` / `.fb-bubble-user`) instead of `st.chat_message`. User messages show a language pill when non-English.
- Hero stats area: three columns — monthly total with 30-day sparkline, today total, budget-left indicator with colour coding.
- Category breakdown table injected as a bot message on first render (and on demand via "📋 Show breakdown" chip). Removed from sidebar.
- Sidebar simplified to: logo, email, month total, today total, 7-day sparkline, sign-out button.
- Suggestion chips styled as pill buttons using `data-testid="fb-chip"` wrapper.
- Mic recorder wrapped in `data-testid="fb-mic-recorder"` for CSS targeting; start button styled gold, stop button styled coral with pulse animation.
- `_dispatch()` helper centralises message appending + audio queuing + rerun.
- Latency display hidden behind `FINBOT_DEBUG=1` env variable.

#### `brain/llm.py`
- `ADVISOR_PROMPT` updated: added rule prohibiting markdown formatting (no `**`, backticks, `#` headers, bullet points). LLM must write plain sentences only.

#### `finance/database.py`
- `ExpenseTracker.undo_last_expense()` added: deletes the most recently inserted expense for the current user, returns the deleted record (or `None` if nothing to undo).

#### `tests/test_database.py`
- `TestUndoLastExpense` — two tests covering the happy path and the empty case, both using mocked Supabase.
- `TestStripMarkdown` — six tests covering all markdown stripping cases.

---

## How to run after pulling

```bash
cd "C:\Finance Voice Assistant"
venv\Scripts\activate
pip install -r requirements.txt   # no new packages added
streamlit run app.py
```

To see latency metrics in the UI:

```bash
set FINBOT_DEBUG=1 && streamlit run app.py     # Windows
FINBOT_DEBUG=1 streamlit run app.py            # macOS/Linux
```

## Breaking changes
- `st.session_state.pending_expense` no longer exists. Any external code referencing it must switch to `undo_expense`.
- The "Shall I log that? ✅/❌" confirmation message will no longer appear for users who have it in their chat history (loaded from Supabase). It will render as a plain bot bubble — harmless, but visually slightly off-theme.
