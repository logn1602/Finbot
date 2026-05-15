# FinBot — Architecture & Design Decisions

This document explains *why* each technology was chosen and the trade-offs considered. The goal is to preserve the reasoning behind design decisions so future contributors understand not just what was built, but why.

---

## System Overview

FinBot is a voice-first, multi-user financial assistant. Every design decision is shaped by three constraints:

1. **Zero cost** — must run entirely on free tiers
2. **No GPU** — must work in a standard cloud deployment (Streamlit Community Cloud)
3. **Multilingual** — must support 20+ languages end-to-end, not just as a feature flag

---

## Component Decisions

### LLM: Llama 3.3 70B via Groq

**Why Groq over OpenAI or HuggingFace Inference?**

Groq's LPU (Language Processing Unit) hardware delivers ~10× lower latency than OpenAI's API for equivalent model quality. For a voice assistant, latency is UX — a 5-second total response time is acceptable; 15 seconds is not.

- OpenAI GPT-4o: fast but paid; free tier is rate-limited in ways that break demos
- HuggingFace Inference API: free but unpredictable latency (cold starts, queuing)
- Groq free tier: consistent ~0.5–1s LLM inference, no cold starts

**Why Llama 3.3 70B over a smaller model?**

Intent classification needs to handle ambiguous, multilingual, colloquial input ("spent 50 on chai" → food category, INR implied). Smaller models (7B, 13B) misclassify edge cases at a rate that degrades UX visibly. 70B is the minimum size where multilingual entity extraction is reliable enough for production use.

---

### Speech-to-Text: Groq Whisper Large V3

**Why Groq-hosted Whisper over running it locally?**

Running Whisper Large V3 locally requires ~3GB VRAM and ~5s on CPU. Streamlit Community Cloud has no GPU, and CPU inference is too slow for a voice-first app. Groq hosts Whisper on the same LPU infrastructure, so transcription takes ~0.5–1.5s with no local compute.

**Why Large V3 over smaller Whisper models?**

For Indian languages (Tamil, Telugu, Hindi) and accented English, Large V3's accuracy is materially better than Medium or Small. Misrecognised amounts or categories produce silent data corruption — a ₹500 expense logged as ₹50 is worse than no recognition at all.

**Offline fallback:** `SpeechToTextLocal` in `voice/stt.py` uses a local Whisper model for demos without internet access. `medium` is recommended as a balance of speed and accuracy.

---

### Text-to-Speech: Microsoft Edge-TTS

**Why Edge-TTS over ElevenLabs, Google TTS, or OpenAI TTS?**

| Option | Cost | Languages | Latency |
|---|---|---|---|
| ElevenLabs | Paid after ~10k chars/month | Limited non-English | Low |
| Google Cloud TTS | Paid beyond free quota | Excellent | Low |
| OpenAI TTS | Paid | English-focused | Low |
| Edge-TTS | **Free, no API key** | 20+ including Indian | Low |

Edge-TTS uses Microsoft Azure's neural TTS under the hood, the same engine behind Cortana. Audio quality is good enough for a financial assistant. The deciding factor is that it requires zero API key setup — users can clone and run without any TTS credentials.

**Async generation:** `tts.py` uses `asyncio.run()` to generate the MP3 non-blocking and returns the file path to Streamlit, which plays it via `st.audio(autoplay=True)`. This avoids blocking the main thread during audio synthesis.

---

### Database & Auth: Supabase

**Why Supabase over Firebase, PlanetScale, or SQLite?**

SQLite was the original prototype storage layer. It was replaced with Supabase for three reasons:

1. **Multi-user isolation** — Supabase's Row Level Security (RLS) enforces that `SELECT * FROM expenses WHERE user_id = auth.uid()` is the only query a user can run, even if they manipulate the API. This isolation is enforced at the database layer, not the application layer.
2. **Auth included** — email/password authentication, session tokens, and JWT management are built-in. Building this on SQLite would require a separate auth service.
3. **Cloud-native** — Streamlit Community Cloud can't persist a local SQLite file across restarts. Supabase's hosted Postgres persists independently of the app's lifecycle.

**Why not PlanetScale or Neon?**

Both are strong options. Supabase was chosen because its Python SDK handles both auth session tokens and database queries in one client, reducing the number of moving parts.

---

### Frontend: Streamlit

**Why Streamlit over FastAPI + React, Gradio, or Flask?**

For a project with a one-person development team and an academic timeline, Streamlit eliminates the frontend/backend split entirely. Session state (`st.session_state`) provides the persistence layer for conversation history and user tokens without a separate state management system.

The trade-off: Streamlit reruns the entire script on every interaction. This is acceptable here because all expensive operations (LLM, STT, TTS) are external API calls that dominate wall-clock time regardless of rerender cost.

---

## RAG: Retrieval-Augmented Generation

### Why RAG?

LLMs are excellent at conversation but unreliable for domain-specific financial advice. Without grounding, the model may hallucinate rules of thumb, invent tax brackets, or give advice that contradicts established personal-finance best practices. RAG anchors responses in curated, verified content.

### Architecture Decisions

**Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`**

| Alternative | Why not |
|---|---|
| OpenAI `text-embedding-3-small` | Paid API, violates zero-cost constraint |
| `all-MiniLM-L6-v2` | English-only — FinBot is multilingual |
| `e5-large-v2` | 1024-dim, ~1.3GB — too heavy for Streamlit Cloud's limited RAM |
| `paraphrase-multilingual-MiniLM-L12-v2` | **384-dim, ~120MB, 50+ languages, CPU-friendly, zero cost** |

The multilingual capability matters because a user asking "mujhe paisa kaise bachana chahiye" (Hindi for "how should I save money") should retrieve the same saving-strategies chunks as the English equivalent. A monolingual embedding model would miss this entirely.

**Vector store: ChromaDB (persistent, local)**

| Alternative | Why not |
|---|---|
| Pinecone / Weaviate | Hosted services — free tiers have limits, adds external dependency |
| FAISS | No built-in persistence, requires manual serialization |
| PostgreSQL pgvector (Supabase) | Would work but adds embedding storage to the user-data DB, mixing concerns |
| ChromaDB | **Local persistent storage, no server, pip-installable, cosine similarity built-in** |

ChromaDB stores its data in `chroma_db/` (gitignored). On a fresh deploy, the app auto-ingests from `knowledge/` on first startup. This means `chroma_db/` is a derived artifact — the source of truth is always the markdown files.

**Knowledge base: curated markdown articles**

The knowledge base is 8 hand-written articles (~800–1500 words each) covering budgeting, saving, debt management, investing fundamentals, tax basics, insurance essentials, financial planning, and common money mistakes.

Why curated content over scraping or using a pre-existing corpus:
- **Quality control** — every claim is verified, no outdated or region-specific advice sneaks in
- **Chunk-friendly** — articles are structured with `##` headings, making section-aware chunking natural
- **Maintainable** — adding or updating a topic means editing one markdown file and re-running `python -m rag.ingest --force`
- **No licensing issues** — original content, no copyright concerns

**Chunking strategy: section-aware with overlap**

Chunks are split hierarchically: first on `##` headings (preserving topic boundaries), then on paragraph breaks, then on sentence boundaries for oversized paragraphs. Each chunk targets ~600 characters with 100 characters of overlap between consecutive chunks.

Why not fixed-size character splitting? A naive 500-char split would cut mid-sentence and mid-topic, producing chunks where the retrieved text lacks enough context to be useful. Section-aware splitting keeps each chunk semantically coherent.

**Intent-gated retrieval**

RAG is only triggered for `get_advice` and `query_balance` intents. Other intents (`add_expense`, `set_budget`, `greeting`, `goodbye`) skip retrieval entirely.

Why gate on intent:
- **Latency** — embedding + vector search adds ~100–300ms. Acceptable for advice, unnecessary for "I spent 500 on food"
- **Relevance** — injecting financial-planning knowledge into a simple expense-logging confirmation would confuse the LLM and produce unnecessarily long responses
- **Token budget** — retrieved chunks consume prompt tokens. Wasting them on non-advice intents reduces the space available for conversation history

### Evaluation

The RAG pipeline is evaluated with 56 test cases across 9 categories (budgeting, saving, debt, investing, tax, insurance, planning, mistakes, cross-topic). Evaluation is retrieval-only — no LLM calls required, making it free and fast to run.

| Metric | Score | Definition |
|---|---|---|
| Hit Rate | 98.2% | At least one chunk from the expected source file was retrieved |
| Topic Coverage | 85.3% | Fraction of expected keywords found in retrieved chunks |
| Mean Relevance | 0.78 | Average cosine similarity of retrieved chunks |
| MRR | 0.88 | Mean reciprocal rank of the first relevant result |

The single miss (1 of 56) is a cross-topic query where the expected sources are spread across multiple files — the retriever finds relevant content from adjacent topics instead.

---

## Data Flow Sequence

```
User speaks
  → [stt.py] transcribe_bytes()         # ~0.5–1.5s (Groq Whisper)
  → [database.py] generate_context_for_llm()  # ~50ms (Supabase query)
  → [llm.py] classify_intent()          # ~0.3–0.5s (Groq Llama, low temp)
  → [retriever.py] query() (advice/query intents only)  # ~100–300ms (ChromaDB)
  → [llm.py] generate_response()        # ~0.5–1.0s (Groq Llama + RAG context)
  → [database.py] add_expense() / set_budget() / save_message()  # ~50ms
  → [tts.py] generate_file()            # ~0.3–0.8s (Edge-TTS async)
  → st.audio(autoplay=True)             # browser plays response
```

**Total: ~2–4 seconds end-to-end** (Groq's speed advantage over OpenAI is most visible here)

---

## Prompt Engineering Decisions

### Two-pass LLM architecture

FinBot makes two separate LLM calls per user message:

1. `classify_intent()` — temperature 0.1, max_tokens 200, JSON output only
2. `generate_response()` — temperature 0.7, max_tokens 300, natural language

**Why not one call?**

Combining both tasks into one prompt reliably produces either good intent classification *or* good conversational responses, not both simultaneously. Keeping them separate allows each call to be tuned independently (low temperature for deterministic JSON, higher temperature for natural language).

### Language handling

Language detection flows from Whisper (most reliable source, since it's trained on audio features) to the intent classifier (fallback for text input). The detected language code is threaded through the entire pipeline and injected into the advisor system prompt as `{detected_language}`. This ensures TTS voice selection, LLM response language, and Whisper transcription all operate on the same language signal.

---

## Calendar Month Scoping

### The problem

The original codebase used rolling 30-day windows for all "this month" queries (`get_total_spent(days=30)`). This caused April expenses to bleed into May totals and vice versa, producing incorrect budget tracking near month boundaries.

### The fix

All current-month queries now use strict calendar month boundaries:

```python
month_start_local()       # e.g., "2026-05-01"
next_month_start_local()  # e.g., "2026-06-01"
# Query: date >= month_start AND date < next_month_start
```

This ensures that expenses logged on April 30th never appear in May's totals, regardless of timezone. The boundary functions use the user's browser timezone (detected via `streamlit-js-eval`) so "today" and "this month" match the user's local calendar.

Budget projections now use `calendar.monthrange()` to get the actual number of days in the current month (28, 29, 30, or 31) instead of assuming 30.

### Backward compatibility

`get_total_spent(days=None)` still accepts an optional `days` parameter for rolling-window queries. When called without arguments, it returns the calendar-month total. Existing callers that passed `days=30` were updated to use the new `get_total_spent_this_month()` method.

---

## Time Scope Detection

### Why two scopes?

A user asking "how much did I spend this month?" needs current-month data. A user asking "how has my spending changed over the last 3 months?" needs historical multi-month data. Feeding current-month-only context to historical questions produces unhelpful responses; feeding multi-month data to simple expense logging wastes tokens and confuses the LLM.

### How it works

The intent classifier outputs a `time_scope` field alongside the intent:

- `current_month` (default) — "how much did I spend?", "I spent 500 on food", "set my budget to 600"
- `historical` — "compare last 3 months", "how has my spending changed?", "what did I spend in January?"

`process_message()` reads the scope and routes to the correct context generator:

| Scope | Context source | Content |
|---|---|---|
| `current_month` | `generate_context_for_llm()` | This month's totals, budget status, today's spending |
| `historical` | `generate_historical_context_for_llm()` | Multi-month summaries, month-over-month changes, category trends |

`add_expense` and `set_budget` intents always use `current_month` regardless of the classifier's output, since they are write operations against the current period.

---

## Historical Dashboard

### Architecture

The historical dashboard is a collapsible panel in the sidebar, built as a separate module (`dashboard/`) to keep `app.py` focused on the chat interface.

```
dashboard/
├── charts.py    # 5 Plotly chart functions (pure data → figure)
└── ui.py        # Streamlit layout (tabs, selectors, rendering)
```

**Data layer** reuses the historical query methods added to `ExpenseTracker` and `BudgetAnalyzer` — no new database queries were needed for the UI.

### Chart functions

| Function | Chart type | Data source |
|---|---|---|
| `monthly_spending_bar()` | Bar | `get_monthly_summary()` |
| `category_breakdown_stacked()` | Stacked bar | `get_monthly_breakdown_by_category()` |
| `spending_trend_line()` | Line + 7-day MA | `get_spending_trend()` |
| `budget_performance_heatmap()` | Heatmap | `get_historical_budget_performance()` |
| `category_trend_line()` | Line + budget ref | `get_category_trend()` |

All chart functions return `None` on empty data, allowing the UI to skip rendering gracefully. All use the shared dark theme tokens from `styles/tokens.py`.

### UI layout

Three tabs inside an `st.expander`:
1. **Overview** — monthly bar chart with month-over-month stats, 90-day daily trend with moving average
2. **Categories** — stacked breakdown + single-category drilldown with budget reference line
3. **Budget** — heatmap of budget usage percentage (category x month), color-coded green/gold/coral

A period slider (3/6/9/12 months) controls all tabs from a single control.

---

## What Was Deliberately Not Built

- **Streaming responses** — Streamlit's `st.write_stream()` is available, but streaming conflicts with the TTS step (you can't synthesise audio until the full response is known). A future architecture could stream text first, then generate audio for the complete response.
- **Receipt/image parsing** — vision models (GPT-4V, LLaVA) could parse receipts, but this would require a paid API or a GPU for local inference, violating the zero-cost constraint.
- **Bank integration** — Plaid and similar APIs are paid and require KYC compliance, out of scope for an academic project.
- **User-specific RAG** — the knowledge base is shared across all users (general financial advice). A future extension could embed each user's transaction history for personalised retrieval, but this raises privacy and storage scaling concerns.
- **LLM-as-judge evaluation** — the eval pipeline measures retrieval quality only. Adding LLM-based answer scoring (e.g., "was the generated advice accurate?") would require paid API calls or a local judge model, conflicting with the zero-cost constraint.
