"""
Text-to-Speech Module using Edge-TTS
NOW WITH: Automatic voice selection based on detected language
"""

import edge_tts
import asyncio
import tempfile
import os

try:
    import pygame
    pygame.mixer.init()
    AUDIO_BACKEND = "pygame"
except ImportError:
    AUDIO_BACKEND = "system"


class TextToSpeech:

    # Voice map: language_code → best Edge-TTS voice
    # Each language has a default male + female option
    LANG_VOICES = {
        # English
        "en": {"male": "en-US-GuyNeural",       "female": "en-US-JennyNeural"},
        # Indian Languages
        "hi": {"male": "hi-IN-MadhurNeural",     "female": "hi-IN-SwaraNeural"},
        "ta": {"male": "ta-IN-ValluvarNeural",    "female": "ta-IN-PallaviNeural"},
        "te": {"male": "te-IN-MohanNeural",       "female": "te-IN-ShrutiNeural"},
        "bn": {"male": "bn-IN-BashkarNeural",     "female": "bn-IN-TanishaaNeural"},
        "mr": {"male": "mr-IN-ManoharNeural",     "female": "mr-IN-AarohiNeural"},
        "gu": {"male": "gu-IN-NiranjanNeural",    "female": "gu-IN-DhwaniNeural"},
        "kn": {"male": "kn-IN-GaganNeural",       "female": "kn-IN-SapnaNeural"},
        "ml": {"male": "ml-IN-MidhunNeural",      "female": "ml-IN-SobhanaNeural"},
        # European
        "es": {"male": "es-ES-AlvaroNeural",      "female": "es-ES-ElviraNeural"},
        "fr": {"male": "fr-FR-HenriNeural",       "female": "fr-FR-DeniseNeural"},
        "de": {"male": "de-DE-ConradNeural",      "female": "de-DE-KatjaNeural"},
        "it": {"male": "it-IT-DiegoNeural",       "female": "it-IT-ElsaNeural"},
        "pt": {"male": "pt-BR-AntonioNeural",     "female": "pt-BR-FranciscaNeural"},
        "ru": {"male": "ru-RU-DmitryNeural",      "female": "ru-RU-SvetlanaNeural"},
        # Asian
        "zh": {"male": "zh-CN-YunxiNeural",       "female": "zh-CN-XiaoxiaoNeural"},
        "ja": {"male": "ja-JP-KeitaNeural",       "female": "ja-JP-NanamiNeural"},
        "ko": {"male": "ko-KR-InJoonNeural",      "female": "ko-KR-SunHiNeural"},
        # Middle Eastern
        "ar": {"male": "ar-SA-HamedNeural",       "female": "ar-SA-ZariyahNeural"},
        "ur": {"male": "ur-PK-AsadNeural",        "female": "ur-PK-UzmaNeural"},
    }

    def __init__(self, default_lang="en", gender="male", rate="+0%", pitch="+0Hz"):
        """
        default_lang: fallback language code (e.g., 'en', 'hi', 'ta')
        gender: 'male' or 'female'
        """
        self.default_lang = default_lang
        self.gender = gender
        self.rate = rate
        self.pitch = pitch
        print(f"TTS initialized (default: {default_lang}, {gender})")

    def get_voice_for_language(self, lang_code):
        """Pick the right voice for the detected language."""
        lang_code = lang_code.lower()[:2]  # Normalize: 'en-US' → 'en'

        if lang_code in self.LANG_VOICES:
            voice = self.LANG_VOICES[lang_code][self.gender]
            return voice
        else:
            # Fallback to default language
            print(f"  No voice for '{lang_code}', falling back to {self.default_lang}")
            return self.LANG_VOICES[self.default_lang][self.gender]

    async def _generate_audio(self, text, output_path, voice):
        """Generate speech audio file from text."""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=self.rate,
            pitch=self.pitch
        )
        await communicate.save(output_path)

    def _play_audio(self, filepath):
        """Play an audio file."""
        if AUDIO_BACKEND == "pygame":
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
        else:
            import platform
            system = platform.system()
            if system == "Darwin":
                os.system(f"afplay {filepath}")
            elif system == "Linux":
                os.system(f"aplay {filepath} 2>/dev/null || mpv {filepath} 2>/dev/null")
            elif system == "Windows":
                os.system(f'start /wait "" "{filepath}"')

    def speak(self, text, language=None):
        """
        Convert text to speech and play it.
        
        Args:
            text: what to say
            language: language code (e.g., 'hi', 'en', 'ta')
                      if None, uses default language
        """
        if not text or not text.strip():
            return

        lang = language or self.default_lang
        voice = self.get_voice_for_language(lang)
        print(f"🔊 Speaking [{lang}] with {voice}: {text[:60]}{'...' if len(text) > 60 else ''}")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_path = f.name

        try:
            asyncio.run(self._generate_audio(text, temp_path, voice))
            self._play_audio(temp_path)
        finally:
            # Release the file before deleting (Windows needs this)
            if AUDIO_BACKEND == "pygame":
                pygame.mixer.music.unload()
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except PermissionError:
                pass  # Windows may still hold it briefly, that's okay

    def generate_file(self, text, language=None, output_path="response.mp3"):
        """Generate audio file without playing (useful for Streamlit/Gradio)."""
        lang = language or self.default_lang
        voice = self.get_voice_for_language(lang)
        asyncio.run(self._generate_audio(text, output_path, voice))
        return output_path

    @classmethod
    def list_supported_languages(cls):
        """Print all supported languages."""
        print("Supported languages:")
        for code, voices in cls.LANG_VOICES.items():
            print(f"  {code}: male={voices['male']}, female={voices['female']}")


# === Quick test ===
if __name__ == "__main__":
    tts = TextToSpeech(default_lang="en", gender="male")

    # Test English
    tts.speak("Hey! I'm your AI financial advisor.", language="en")

    # Test Hindi
    tts.speak("नमस्ते! मैं आपका AI वित्तीय सलाहकार हूं।", language="hi")

    # Test Tamil
    tts.speak("வணக்கம்! நான் உங்கள் நிதி ஆலோசகர்.", language="ta")

    # Show all supported
    TextToSpeech.list_supported_languages()