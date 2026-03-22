# 💰 FinBot — AI Financial Advisor Voice Assistant

A voice-powered AI chatbot that helps users manage personal finances through natural conversation — in 20+ languages. Say "I spent 500 on food" and FinBot logs it, tracks your budget, and gives you personalized financial advice — all through voice or text.

🔗 **[Try the Live App](https://finbot-ubucudqttyqsz37bbxqjan.streamlit.app)**

---

## ✨ Features

- **🎤 Voice In / Voice Out** — Speak naturally, get spoken responses back via browser mic
- **💬 Text Chat** — Type messages for the same full experience
- **📊 Smart Expense Tracking** — Say "I spent 50 on lunch" and it auto-classifies and logs it
- **🎯 Budget Monitoring** — Real-time budget vs. spending with visual progress bars and alerts
- **💡 Personalized Advice** — Context-aware financial guidance based on your actual spending data
- **🌍 20+ Languages** — Auto-detects English, Hindi, Tamil, Spanish, French, and more — responds in the same language
- **📈 Live Dashboard** — Spending trends, category breakdowns, donut charts, and smart insights
- **🔊 Multilingual TTS** — Speaks responses back in the detected language with natural-sounding neural voices

---

## 🏗️ Tech Stack

| Layer | Technology | Purpose | Cost |
|-------|-----------|---------|------|
| 🎙️ Speech-to-Text | Groq Whisper large-v3 | Transcription + auto language detection (90+ languages) | Free |
| 🧠 LLM / Brain | Groq + Llama 3.3 70B | Intent classification + multilingual response generation | Free |
| 🔊 Text-to-Speech | Microsoft Edge-TTS | Neural voice synthesis with 20+ language-matched voices | Free |
| 🗄️ Database | SQLite | Expense tracking, budget management, income storage | Free |
| 🖥️ Frontend | Streamlit | Chat UI + real-time financial dashboard + cloud deployment | Free |
| 🎤 Voice Recording | streamlit-mic-recorder | Browser-based mic capture for cloud compatibility | Free |

> **Total cost to run: $0** — Every layer runs on free tiers with no GPU required.

---

## 📁 Project Structure

```
finbot/
├── brain/
│   ├── __init__.py
│   └── llm.py                # Intent classification + multilingual response generation
├── finance/
│   ├── __init__.py
│   └── database.py            # SQLite DB, expense tracker, budget analyzer
├── voice/
│   ├── __init__.py
│   ├── stt.py                 # Speech-to-text (Groq Whisper + browser mic)
│   └── tts.py                 # Text-to-speech (Edge-TTS, 20+ language voices)
├── app.py                     # Main Streamlit application
├── requirements.txt           # Python dependencies
├── .env                       # API key (local only, not committed)
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- A free Groq API key from [console.groq.com](https://console.groq.com)
- Git
- A modern browser (Chrome, Firefox, Edge)

### Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/logn1602/Finbot.git
cd Finbot

# 2. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
echo GROQ_API_KEY=your_key_here > .env

# 5. Run the app
streamlit run app.py

# Opens at http://localhost:8501
```

### Cloud Deployment (Streamlit Community Cloud)

1. Fork this repo to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select the repo → set main file to `app.py`
4. Under **Advanced settings**, add your secret: `GROQ_API_KEY = "your_key_here"`
5. Click **Deploy** — live in 2-3 minutes

---

## 🧪 Testing Individual Modules

```bash
# Test database & finance engine
python finance/database.py

# Test LLM brain (requires GROQ_API_KEY in .env)
python brain/llm.py

# Test speech-to-text (requires microphone, local only)
python voice/stt.py

# Test text-to-speech (requires speakers)
python voice/tts.py
```

---

## ⚙️ How It Works

```
User speaks → Browser Mic Recording
  → Groq Whisper large-v3 (transcribe + detect language)
  → Llama 3.3 70B (classify intent + extract entities)
  → Finance Engine (database operations)
  → Llama 3.3 70B (generate response in user's language)
  → Edge-TTS (convert to speech with matched voice)
  → Audio plays in browser + text in chat
```

**End-to-end latency: ~5 seconds**

---

## 🌐 Supported Languages

English · Hindi · Tamil · Telugu · Bengali · Marathi · Gujarati · Kannada · Malayalam · Punjabi · Urdu · Spanish · French · German · Chinese · Japanese · Korean · Arabic · Portuguese · Russian · Italian

Language is auto-detected — no manual selection needed.

---

## 📊 Dashboard Features

- **Monthly/Daily spending totals** with real-time updates
- **Budget progress bars** with ON TRACK / WARNING / OVER badges
- **Category breakdown** donut chart
- **7-day spending trend** line chart
- **Smart insights** — overspending alerts, spending spikes, top categories

---

## 🔮 Future Roadmap

- 🔐 User authentication & multi-user support
- ⚡ Streaming LLM responses
- 📸 Receipt/SMS parsing with vision models
- 🔄 Recurring expense detection
- 📋 Smart budget recommendations (50-30-20 rule)
- 📄 Exportable PDF financial reports
- 🏦 Bank & payment app integration (Venmo, Zelle, Plaid)


## 📄 License

This project was developed as an academic assignment for EAI 6010 at Northeastern University.