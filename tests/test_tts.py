"""
Tests for TextToSpeech — voice selection and language mapping.
These tests do NOT call external APIs (no audio generated).
Run: pytest tests/test_tts.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from voice.tts import TextToSpeech


@pytest.fixture
def tts_male():
    return TextToSpeech(default_lang="en", gender="male")


@pytest.fixture
def tts_female():
    return TextToSpeech(default_lang="en", gender="female")


class TestVoiceSelection:

    def test_english_male_voice(self, tts_male):
        voice = tts_male.get_voice_for_language("en")
        assert "en" in voice.lower()
        assert "neural" in voice.lower()

    def test_english_female_voice(self, tts_female):
        voice = tts_female.get_voice_for_language("en")
        assert "en" in voice.lower()
        assert voice != tts_male.get_voice_for_language("en")

    def test_hindi_voice_returned(self, tts_male):
        voice = tts_male.get_voice_for_language("hi")
        assert "hi" in voice.lower()

    def test_tamil_voice_returned(self, tts_male):
        voice = tts_male.get_voice_for_language("ta")
        assert "ta" in voice.lower()

    def test_spanish_voice_returned(self, tts_male):
        voice = tts_male.get_voice_for_language("es")
        assert "es" in voice.lower()

    def test_unknown_language_falls_back_to_default(self, tts_male):
        # 'xx' is not a known language — should fall back to 'en'
        voice = tts_male.get_voice_for_language("xx")
        assert "en" in voice.lower()

    def test_locale_code_normalised(self, tts_male):
        # 'en-US' should normalise to 'en' and still return a valid voice
        voice = tts_male.get_voice_for_language("en-US")
        assert voice is not None
        assert "neural" in voice.lower()

    def test_all_declared_languages_have_voices(self, tts_male):
        for lang_code in TextToSpeech.LANG_VOICES:
            voice = tts_male.get_voice_for_language(lang_code)
            assert voice is not None and len(voice) > 0, f"No voice for {lang_code}"

    def test_male_and_female_voices_differ(self):
        male = TextToSpeech(default_lang="en", gender="male")
        female = TextToSpeech(default_lang="en", gender="female")
        for lang_code in ["en", "hi", "ta", "es", "fr"]:
            assert male.get_voice_for_language(lang_code) != female.get_voice_for_language(lang_code), \
                f"Male and female voices are identical for {lang_code}"
