"""
LLM Brain - Intent Classification + Multilingual Response Generation
Uses Groq API (free tier) with Llama 3
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# INTENT CLASSIFIER (always works in English internally)
# ============================================================

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a voice-based financial assistant.
The user may speak in ANY language. Regardless of their language, classify the intent in English.
Extract entities (amounts, categories) from whatever language they use.
Also detect what language the user is writing/speaking in.

Given the user's message, classify into EXACTLY ONE intent and extract entities.

INTENTS:
- add_expense: User wants to log spending (e.g., "I spent 500 on food", "maine 500 khane pe kharch kiye", "நான் 500 செலவு செய்தேன்")
- query_balance: User asks about spending/budget (e.g., "how much did I spend", "mera budget kya hai", "என் செலவு எவ்வளவு")
- get_advice: User wants financial advice (e.g., "can I afford this", "kya main ye le sakta hoon")
- set_budget: User wants to set/change budget (e.g., "set food budget to 6000")
- greeting: Saying hi in any language
- goodbye: Ending conversation in any language

CATEGORIES: food, transport, entertainment, shopping, bills, health, education, other

LANGUAGE DETECTION:
- Detect the language the user is writing in
- Use ISO 639-1 codes: en, hi, ta, te, bn, mr, gu, kn, ml, pa, ur, es, fr, de, zh, ja, ko, ar, pt, ru, it
- If the user mixes languages (like Hinglish), pick the dominant one

Respond ONLY with valid JSON, no markdown, no backticks:
{
    "intent": "the_intent",
    "entities": {
        "amount": null or number,
        "category": null or "category_name",
        "description": null or "brief description in English",
        "period": null or "today/week/month"
    },
    "confidence": 0.0 to 1.0,
    "language": "detected language code (e.g., en, hi, ta, es)"
}"""

# ============================================================
# MULTILINGUAL FINANCIAL ADVISOR PERSONA
# ============================================================

ADVISOR_SYSTEM_PROMPT = """You are FinBot, a friendly AI financial advisor voice assistant.

CRITICAL LANGUAGE RULE:
The user is speaking in: {detected_language}
You MUST respond in the SAME language the user is speaking in.
If they speak Hindi, reply in Hindi. If Tamil, reply in Tamil. If English, reply in English.
If they mix languages (like Hinglish), match their style.

PERSONALITY:
- Speak naturally, like a knowledgeable friend
- Keep responses SHORT (2-4 sentences max) — you're a VOICE assistant
- Use casual language appropriate for the detected language
- Be encouraging but honest about bad spending habits
- Add humor when appropriate

RULES:
- Always reference the user's ACTUAL financial data when giving advice
- If they're overspending, be direct but kind
- Suggest specific, actionable tips
- When they log an expense, confirm it and give a quick status update
- Use ₹ for Indian languages, $ for English (unless user specifies)
- NEVER say "as an AI" — stay in character
- NEVER respond in English if the user spoke in another language

{financial_context}
"""

# Language code → friendly name for the prompt
LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu",
    "es": "Spanish", "fr": "French", "de": "German",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "ar": "Arabic", "pt": "Portuguese", "ru": "Russian", "it": "Italian",
}


class FinanceBrain:
    def __init__(self):
        # Works both locally (.env) and on Streamlit Cloud (secrets)
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GROQ_API_KEY", None)
            except Exception:
                pass
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found! Get one free at https://console.groq.com"
            )
        self.client = Groq(api_key=api_key)
        self.conversation_history = []
        self.model = "llama-3.3-70b-versatile"

    def classify_intent(self, user_message: str) -> dict:
        """Classify intent + detect language — works regardless of input language."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=200
            )
            result_text = response.choices[0].message.content.strip()
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            return json.loads(result_text)

        except (json.JSONDecodeError, Exception) as e:
            print(f"Intent classification error: {e}")
            return {"intent": "get_advice", "entities": {}, "confidence": 0.3, "language": "en"}

    def generate_response(self, user_message: str, financial_context: str = "", language: str = "en") -> str:
        """
        Generate response in the SAME language the user spoke in.
        
        Args:
            user_message: what the user said
            financial_context: budget/spending data
            language: detected language code from Whisper or intent classifier (e.g., 'hi', 'ta', 'en')
        """
        lang_name = LANG_NAMES.get(language, language)

        system_prompt = ADVISOR_SYSTEM_PROMPT.format(
            detected_language=lang_name,
            financial_context=financial_context
        )

        self.conversation_history.append({"role": "user", "content": user_message})
        recent_history = self.conversation_history[-20:]
        messages = [{"role": "system", "content": system_prompt}] + recent_history

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            assistant_reply = response.choices[0].message.content.strip()
            self.conversation_history.append({"role": "assistant", "content": assistant_reply})
            return assistant_reply

        except Exception as e:
            print(f"LLM generation error: {e}")
            error_msgs = {
                "en": "Sorry, I had a hiccup there. Could you say that again?",
                "hi": "माफ़ करें, कुछ गड़बड़ हो गई। क्या आप दोबारा कह सकते हैं?",
                "ta": "மன்னிக்கவும், ஒரு சிக்கல் ஏற்பட்டது. மீண்டும் சொல்ல முடியுமா?",
                "te": "క్షమించండి, ఒక సమస్య వచ్చింది. మళ్ళీ చెప్పగలరా?",
                "es": "Lo siento, tuve un problema. ¿Puedes repetirlo?",
                "fr": "Désolé, j'ai eu un souci. Pouvez-vous répéter?",
            }
            return error_msgs.get(language, error_msgs["en"])

    def process_message(self, user_message: str, financial_context: str = "", language: str = None) -> dict:
        """
        Full pipeline: classify intent (+ detect language) → generate response in user's language.
        
        Args:
            language: if provided (e.g., from Whisper), use it directly.
                      if None (e.g., typed input), use the language detected by intent classifier.
        """
        intent_data = self.classify_intent(user_message)
        print(f"  Intent: {intent_data['intent']} (confidence: {intent_data.get('confidence', 'N/A')})")

        # Use Whisper's language if available, otherwise use LLM-detected language
        detected_language = language or intent_data.get("language", "en")
        print(f"  Language: {detected_language}")

        response = self.generate_response(user_message, financial_context, detected_language)

        return {
            "intent": intent_data,
            "response": response,
            "language": detected_language
        }

    def reset_conversation(self):
        self.conversation_history = []


# === Quick test ===
if __name__ == "__main__":
    brain = FinanceBrain()

    test_messages = [
        # English
        ("Hey there!", None),
        ("I spent 350 on lunch today", None),
        # Hindi (no language hint — LLM should detect)
        ("Namaste! Mera budget kya hai?", None),
        ("Maine aaj 500 rupaye khane pe kharch kiye", None),
        # Tamil (no language hint)
        ("வணக்கம்! இன்று எவ்வளவு செலவு செய்தேன்?", None),
        # Spanish (no language hint)
        ("Hola! ¿Cuánto gasté hoy?", None),
        # Whisper-detected language (simulating voice input)
        ("I spent 200 on coffee", "en"),
    ]

    context = "Total spent this month: 15000. Food: 4500/5000 (90%)"

    for msg, lang in test_messages:
        print(f"\n👤 User: {msg}  (hint: {lang or 'auto-detect'})")
        result = brain.process_message(msg, financial_context=context, language=lang)
        print(f"🤖 FinBot: {result['response']}")
        print(f"   [Intent: {result['intent']['intent']}, Lang: {result['language']}]")