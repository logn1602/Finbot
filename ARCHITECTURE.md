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

## Data Flow Sequence

```
User speaks
  → [stt.py] transcribe_bytes()         # ~0.5–1.5s (Groq Whisper)
  → [database.py] generate_context_for_llm()  # ~50ms (Supabase query)
  → [llm.py] classify_intent()          # ~0.3–0.5s (Groq Llama, low temp)
  → [llm.py] generate_response()        # ~0.5–1.0s (Groq Llama)
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

## What Was Deliberately Not Built

- **Streaming responses** — Streamlit's `st.write_stream()` is available, but streaming conflicts with the TTS step (you can't synthesise audio until the full response is known). A future architecture could stream text first, then generate audio for the complete response.
- **Receipt/image parsing** — vision models (GPT-4V, LLaVA) could parse receipts, but this would require a paid API or a GPU for local inference, violating the zero-cost constraint.
- **Bank integration** — Plaid and similar APIs are paid and require KYC compliance, out of scope for an academic project.
