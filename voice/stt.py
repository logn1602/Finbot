"""
Speech-to-Text using Groq's hosted Whisper Large V3
- Supports both local mic (sounddevice) and browser mic (audio bytes)
- Most accurate Whisper model (large-v3)
- Runs on Groq's servers = blazing fast even without GPU
- 100% free on Groq's free tier

Install: pip install groq sounddevice numpy scipy streamlit-mic-recorder
"""

import os
import tempfile
import numpy as np
from scipy.io.wavfile import write
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Language code → friendly name
LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ta": "Tamil", "te": "Telugu",
    "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu",
    "es": "Spanish", "fr": "French", "de": "German", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "ar": "Arabic", "pt": "Portuguese",
    "ru": "Russian", "it": "Italian",
}


class SpeechToText:
    def __init__(self):
        """
        Uses Groq's hosted Whisper large-v3 — the most accurate model.
        No local model download needed, no GPU needed, no ffmpeg needed.
        """
        # Works both locally (.env) and on Streamlit Cloud (secrets)
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GROQ_API_KEY", None)
            except Exception:
                pass
        if not api_key:
            raise ValueError("GROQ_API_KEY not found!")
        self.client = Groq(api_key=api_key)
        self.sample_rate = 16000
        print("STT ready! (using Groq Whisper large-v3)")

    # ============================================================
    # BROWSER MIC: Transcribe raw audio bytes (from streamlit-mic-recorder)
    # ============================================================

    def transcribe_bytes(self, audio_bytes, language=None):
        """
        Transcribe audio from browser mic (raw bytes from streamlit-mic-recorder).
        Returns dict with 'text' and 'language'.
        """
        if not audio_bytes:
            return {"text": "", "language": "en"}

        # Save bytes to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            f.write(audio_bytes)

        try:
            with open(temp_path, "rb") as audio_file:
                params = {
                    "file": ("audio.wav", audio_file),
                    "model": "whisper-large-v3",
                    "response_format": "verbose_json",
                }
                if language:
                    params["language"] = language

                transcription = self.client.audio.transcriptions.create(**params)

            text = transcription.text.strip()
            detected_lang = getattr(transcription, 'language', 'en') or 'en'

            lang_name = LANG_NAMES.get(detected_lang, detected_lang)
            print(f"📝 [{lang_name}] You said: {text}")

            return {"text": text, "language": detected_lang}

        except Exception as e:
            print(f"Transcription error: {e}")
            return {"text": "", "language": "en"}

        finally:
            os.unlink(temp_path)

    # ============================================================
    # LOCAL MIC: Record from system microphone (sounddevice)
    # ============================================================

    def record_audio(self, duration=5):
        """Record audio from microphone for a fixed duration."""
        import sounddevice as sd
        print(f"🎤 Listening for {duration} seconds...")
        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        print("Recording complete!")
        return audio.flatten()

    def record_until_silence(self, silence_threshold=0.01, silence_duration=1.5, max_duration=15):
        """Smart recording: stops when user stops speaking."""
        import sounddevice as sd
        print("🎤 Speak now... (I'll stop when you pause)")
        chunk_size = int(self.sample_rate * 0.1)
        audio_chunks = []
        silent_chunks = 0
        max_silent = int(silence_duration / 0.1)
        max_chunks = int(max_duration / 0.1)

        for i in range(max_chunks):
            chunk = sd.rec(chunk_size, samplerate=self.sample_rate, channels=1, dtype='float32')
            sd.wait()
            audio_chunks.append(chunk.flatten())

            volume = np.abs(chunk).mean()
            if volume < silence_threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0

            if silent_chunks >= max_silent and len(audio_chunks) > max_silent:
                break

        print("Got it!")
        return np.concatenate(audio_chunks)

    def transcribe(self, audio_array, language=None):
        """
        Send audio array to Groq's Whisper large-v3 for transcription.
        Returns dict with 'text' and 'language'.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            audio_int16 = (audio_array * 32767).astype(np.int16)
            write(temp_path, self.sample_rate, audio_int16)

        try:
            with open(temp_path, "rb") as audio_file:
                params = {
                    "file": ("audio.wav", audio_file),
                    "model": "whisper-large-v3",
                    "response_format": "verbose_json",
                }
                if language:
                    params["language"] = language

                transcription = self.client.audio.transcriptions.create(**params)

            text = transcription.text.strip()
            detected_lang = getattr(transcription, 'language', 'en') or 'en'

            return {"text": text, "language": detected_lang}

        except Exception as e:
            print(f"Transcription error: {e}")
            return {"text": "", "language": "en"}

        finally:
            os.unlink(temp_path)

    def listen(self, mode="auto", language=None):
        """
        Full pipeline: record from local mic → transcribe via Groq → return text + language.
        (Used for local testing, not for cloud deployment)
        """
        if mode == "auto":
            audio = self.record_until_silence()
        else:
            audio = self.record_audio(duration=5)

        result = self.transcribe(audio, language=language)

        lang_name = LANG_NAMES.get(result["language"], result["language"])
        print(f"📝 [{lang_name}] You said: {result['text']}")

        return result


# ============================================================
# FALLBACK: Local Whisper (if you want offline capability too)
# ============================================================

class SpeechToTextLocal:
    """
    Use this as a backup if internet is down during demo.
    Uses local Whisper model — needs ffmpeg installed.
    """
    def __init__(self, model_size="medium"):
        import whisper
        print(f"Loading local Whisper '{model_size}' model...")
        self.model = whisper.load_model(model_size)
        print("Local Whisper model loaded!")
        self.sample_rate = 16000

    def record_audio(self, duration=5):
        import sounddevice as sd
        print(f"🎤 Listening for {duration} seconds...")
        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        return audio.flatten()

    def transcribe(self, audio_array, language=None):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            audio_int16 = (audio_array * 32767).astype(np.int16)
            write(temp_path, self.sample_rate, audio_int16)

        try:
            if language:
                result = self.model.transcribe(temp_path, language=language)
            else:
                result = self.model.transcribe(temp_path)

            return {
                "text": result["text"].strip(),
                "language": result.get("language", "en")
            }
        finally:
            os.unlink(temp_path)

    def listen(self, mode="fixed", language=None):
        audio = self.record_audio(duration=5)
        return self.transcribe(audio, language=language)


# === Quick test ===
if __name__ == "__main__":
    print("=" * 50)
    print("Testing Groq Whisper (large-v3, most accurate)")
    print("=" * 50)

    stt = SpeechToText()

    print("\n--- Test 1: Fixed 5 second recording ---")
    result = stt.listen(mode="fixed")
    print(f"Text: {result['text']}")
    print(f"Language: {result['language']}")

    print("\n--- Test 2: Auto-stop on silence ---")
    result = stt.listen(mode="auto")
    print(f"Text: {result['text']}")
    print(f"Language: {result['language']}")