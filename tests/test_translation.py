"""Tests for #10 Multi-language Input enhancement."""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.translation_service import (
    detect_language,
    translate_to_english,
    translate_transliterated_terms,
)


class TestDetectLanguage:
    """Test language detection from text input."""

    def test_english_text(self):
        """English text detected correctly."""
        assert detect_language("chest pain for 2 days") == "English"
        assert detect_language("I have a headache and fever") == "English"
        assert detect_language("shortness of breath since yesterday") == "English"

    def test_hindi_devanagari(self):
        """Hindi Devanagari script detected."""
        assert detect_language("मुझे सीने में दर्द हो रहा है") == "Hindi"
        assert detect_language("मेरा सिर दर्द कर रहा है") == "Hindi"

    def test_bengali_script(self):
        """Bengali script detected."""
        assert detect_language("আমার বুকে ব্যথা হচ্ছে") == "Bengali"

    def test_tamil_script(self):
        """Tamil script detected."""
        assert detect_language("எனக்கு மார்பு வலி") == "Tamil"

    def test_telugu_script(self):
        """Telugu script detected."""
        assert detect_language("నాకు ఛాతీ నొప్పి ఉంది") == "Telugu"

    def test_gujarati_script(self):
        """Gujarati script detected."""
        assert detect_language("મને છાતીમાં દુખાવો થાય છે") == "Gujarati"

    def test_kannada_script(self):
        """Kannada script detected."""
        assert detect_language("ನನಗೆ ಎದೆ ನೋವು ಇದೆ") == "Kannada"

    def test_malayalam_script(self):
        """Malayalam script detected."""
        assert detect_language("എനിക്ക് നെഞ്ചുവേദന") == "Malayalam"

    def test_urdu_arabic_script(self):
        """Urdu/Arabic script detected."""
        assert detect_language("مجھے سینے میں درد ہو رہا ہے") == "Urdu"

    def test_transliterated_hindi(self):
        """Romanized Hindi medical terms detected."""
        assert detect_language("mujhe pet dard aur bukhar hai") == "Hindi (Transliterated)"
        assert detect_language("seene mein dard aur saans lene mein taklif") == "Hindi (Transliterated)"

    def test_empty_text(self):
        """Empty text returns English."""
        assert detect_language("") == "English"
        assert detect_language("   ") == "English"

    def test_mixed_english_numbers(self):
        """English with numbers stays English."""
        assert detect_language("pain score 7 out of 10 for 3 days") == "English"

    def test_single_hindi_character_not_enough(self):
        """Single script character not enough to trigger detection."""
        # Less than 2 characters shouldn't trigger
        assert detect_language("a") == "English"


class TestTranslateTransliteratedTerms:
    """Test transliteration of Hindi medical terms in Latin script."""

    def test_single_term(self):
        """Single Hindi term translated."""
        assert "fever" in translate_transliterated_terms("bukhar hai").lower()

    def test_multiple_terms(self):
        """Multiple Hindi terms translated."""
        result = translate_transliterated_terms("pet dard aur ulti")
        assert "stomach pain" in result.lower()
        assert "vomiting" in result.lower()

    def test_compound_terms(self):
        """Multi-word Hindi terms translated."""
        result = translate_transliterated_terms("seene mein dard")
        assert "chest pain" in result.lower()

    def test_preserves_english(self):
        """English words preserved unchanged."""
        result = translate_transliterated_terms("bukhar for 2 days")
        assert "fever" in result.lower()
        assert "2 days" in result

    def test_severity_terms(self):
        """Severity-related terms translated."""
        result = translate_transliterated_terms("tez bukhar aur kamzori")
        assert "high fever" in result.lower()
        assert "weakness" in result.lower()

    def test_no_hindi_terms_unchanged(self):
        """Text without Hindi terms returns unchanged."""
        text = "chest pain and shortness of breath"
        assert translate_transliterated_terms(text) == text

    def test_headache_term(self):
        """'sir dard' translates to headache."""
        result = translate_transliterated_terms("sir dard bahut tez hai")
        assert "headache" in result.lower()

    def test_breathing_difficulty(self):
        """Breathing difficulty term translated."""
        result = translate_transliterated_terms("saans lene mein taklif")
        assert "difficulty breathing" in result.lower()

    def test_urinary_symptom(self):
        """Urinary symptom translated."""
        result = translate_transliterated_terms("peshab mein jalan")
        assert "burning urination" in result.lower()


class TestTranslateToEnglish:
    """Test the async translation pipeline."""

    @pytest.mark.asyncio
    async def test_english_not_translated(self):
        """English text passes through unchanged."""
        result = await translate_to_english("I have chest pain for 2 days")
        assert result["translated_text"] == "I have chest pain for 2 days"
        assert result["detected_language"] == "English"
        assert result["was_translated"] is False

    @pytest.mark.asyncio
    async def test_transliterated_hindi_uses_terms(self):
        """Transliterated Hindi uses term replacement (no LLM)."""
        result = await translate_to_english("mujhe pet dard aur bukhar hai")
        assert result["was_translated"] is True
        assert result["detected_language"] == "Hindi (Transliterated)"
        assert "stomach pain" in result["translated_text"].lower()
        assert "fever" in result["translated_text"].lower()
        assert result["original_text"] == "mujhe pet dard aur bukhar hai"

    @pytest.mark.asyncio
    async def test_empty_text(self):
        """Empty text passes through."""
        result = await translate_to_english("")
        assert result["translated_text"] == ""
        assert result["was_translated"] is False

    @pytest.mark.asyncio
    @patch("app.services.translation_service.query_llm_json")
    async def test_hindi_script_uses_llm(self, mock_llm):
        """Hindi Devanagari uses LLM translation."""
        mock_llm.return_value = {
            "translated_text": "I have chest pain",
            "detected_language": "Hindi",
            "confidence": 0.95,
        }

        result = await translate_to_english("मुझे सीने में दर्द है")
        assert result["translated_text"] == "I have chest pain"
        assert result["detected_language"] == "Hindi"
        assert result["was_translated"] is True
        mock_llm.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.translation_service.query_llm_json")
    async def test_bengali_uses_llm(self, mock_llm):
        """Bengali uses LLM translation."""
        mock_llm.return_value = {
            "translated_text": "I have stomach pain",
            "detected_language": "Bengali",
            "confidence": 0.9,
        }

        result = await translate_to_english("আমার পেটে ব্যথা")
        assert result["translated_text"] == "I have stomach pain"
        assert result["detected_language"] == "Bengali"
        assert result["was_translated"] is True

    @pytest.mark.asyncio
    @patch("app.services.translation_service.query_llm_json")
    async def test_llm_failure_returns_original(self, mock_llm):
        """LLM failure returns original text."""
        mock_llm.return_value = None

        result = await translate_to_english("मुझे दर्द है")
        assert result["translated_text"] == "मुझे दर्द है"
        assert result["was_translated"] is False
        assert result["detected_language"] == "Hindi"

    @pytest.mark.asyncio
    async def test_preserves_original_text(self):
        """Original text always preserved."""
        original = "pet dard aur chakkar aa rahe hain"
        result = await translate_to_english(original)
        assert result["original_text"] == original
