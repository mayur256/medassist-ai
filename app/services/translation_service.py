"""Translation Service — Multi-language symptom input support.

Detects language of patient input and translates to English before NER processing.
Supports Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam,
Punjabi, Urdu, and other languages via LLM-based translation.
"""

import logging
import re

from app.services.llm_service import query_llm_json

logger = logging.getLogger(__name__)

# Common non-English script ranges for detection
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")  # Hindi, Marathi, Sanskrit
_BENGALI = re.compile(r"[\u0980-\u09FF]")
_TAMIL = re.compile(r"[\u0B80-\u0BFF]")
_TELUGU = re.compile(r"[\u0C00-\u0C7F]")
_GUJARATI = re.compile(r"[\u0A80-\u0AFF]")
_KANNADA = re.compile(r"[\u0C80-\u0CFF]")
_MALAYALAM = re.compile(r"[\u0D00-\u0D7F]")
_GURMUKHI = re.compile(r"[\u0A00-\u0A7F]")  # Punjabi
_ARABIC_URDU = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
_CJK = re.compile(r"[\u4E00-\u9FFF\u3400-\u4DBF]")  # Chinese
_HANGUL = re.compile(r"[\uAC00-\uD7AF\u1100-\u11FF]")  # Korean
_CYRILLIC = re.compile(r"[\u0400-\u04FF]")  # Russian etc.
_THAI = re.compile(r"[\u0E00-\u0E7F]")

# Script-to-language mapping
_SCRIPT_MAP = [
    (_DEVANAGARI, "Hindi"),
    (_BENGALI, "Bengali"),
    (_TAMIL, "Tamil"),
    (_TELUGU, "Telugu"),
    (_GUJARATI, "Gujarati"),
    (_KANNADA, "Kannada"),
    (_MALAYALAM, "Malayalam"),
    (_GURMUKHI, "Punjabi"),
    (_ARABIC_URDU, "Urdu"),
    (_CJK, "Chinese"),
    (_HANGUL, "Korean"),
    (_CYRILLIC, "Russian"),
    (_THAI, "Thai"),
]

TRANSLATION_PROMPT = """You are a medical translator. Translate the following patient symptom description from {source_language} to English.

RULES:
- Translate medical symptoms accurately
- Preserve all clinical details (duration, severity, location)
- Keep medical terminology precise
- If some words are already in English, keep them as-is
- Output ONLY the translation, nothing else

Original text ({source_language}):
{text}

Respond with ONLY this JSON:
{{"translated_text": "English translation here", "detected_language": "{source_language}", "confidence": 0.95}}

JSON:"""

# Transliterated Hindi medical terms (common in Indian clinical settings)
_HINDI_TRANSLITERATED_TERMS = {
    "dard": "pain",
    "bukhar": "fever",
    "sir dard": "headache",
    "pet dard": "stomach pain",
    "seene mein dard": "chest pain",
    "khasi": "cough",
    "saans": "breathing",
    "saans lene mein taklif": "difficulty breathing",
    "ulti": "vomiting",
    "dast": "diarrhea",
    "chakkar": "dizziness",
    "kamzori": "weakness",
    "thakan": "fatigue",
    "sujan": "swelling",
    "khujli": "itching",
    "jalan": "burning sensation",
    "tez bukhar": "high fever",
    "kamar dard": "back pain",
    "jodon mein dard": "joint pain",
    "ghabrahat": "anxiety",
    "neend na aana": "insomnia",
    "bhook na lagna": "loss of appetite",
    "wajan kam hona": "weight loss",
    "peshab mein jalan": "burning urination",
    "sar ghoomna": "vertigo",
}


def detect_language(text: str) -> str:
    """Detect the language of the input text using script analysis.

    Returns language name or "English" if no non-Latin scripts detected.
    """
    if not text or not text.strip():
        return "English"

    # Count characters matching each script
    for pattern, language in _SCRIPT_MAP:
        matches = pattern.findall(text)
        if len(matches) >= 2:  # At least 2 characters in that script
            return language

    # Check for transliterated Hindi (common in India)
    text_lower = text.lower()
    hindi_term_count = sum(1 for term in _HINDI_TRANSLITERATED_TERMS if term in text_lower)
    if hindi_term_count >= 2:
        return "Hindi (Transliterated)"

    return "English"


def translate_transliterated_terms(text: str) -> str:
    """Translate common transliterated Hindi medical terms to English.

    Handles cases where patients type Hindi words in Latin script.
    """
    result = text
    text_lower = text.lower()

    for hindi_term, english_term in sorted(
        _HINDI_TRANSLITERATED_TERMS.items(), key=lambda x: len(x[0]), reverse=True
    ):
        if hindi_term in text_lower:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(hindi_term), re.IGNORECASE)
            result = pattern.sub(english_term, result)
            text_lower = result.lower()

    return result


async def translate_to_english(text: str) -> dict:
    """Translate patient input to English if non-English detected.

    Args:
        text: Raw patient symptom input in any language

    Returns:
        Dict with:
            - translated_text: English text (original if already English)
            - original_text: Original input preserved
            - detected_language: Detected language name
            - was_translated: Boolean indicating if translation occurred
    """
    if not text or not text.strip():
        return {
            "translated_text": text,
            "original_text": text,
            "detected_language": "English",
            "was_translated": False,
        }

    detected = detect_language(text)

    # Already English — no translation needed
    if detected == "English":
        return {
            "translated_text": text,
            "original_text": text,
            "detected_language": "English",
            "was_translated": False,
        }

    # Transliterated Hindi — use term replacement (fast, no LLM needed)
    if detected == "Hindi (Transliterated)":
        translated = translate_transliterated_terms(text)
        logger.info("Translated transliterated Hindi: '%s' -> '%s'", text[:50], translated[:50])
        return {
            "translated_text": translated,
            "original_text": text,
            "detected_language": detected,
            "was_translated": True,
        }

    # Non-English script — use LLM for translation
    logger.info("Detected language: %s — translating to English via LLM", detected)

    prompt = TRANSLATION_PROMPT.format(
        source_language=detected,
        text=text,
    )

    result = await query_llm_json(prompt)

    if result and isinstance(result, dict) and result.get("translated_text"):
        translated = result["translated_text"]
        logger.info("LLM translation complete: %s -> English (%d chars)",
                    detected, len(translated))
        return {
            "translated_text": translated,
            "original_text": text,
            "detected_language": result.get("detected_language", detected),
            "was_translated": True,
        }

    # Fallback: return original text if translation fails
    logger.warning("Translation failed for %s text; using original", detected)
    return {
        "translated_text": text,
        "original_text": text,
        "detected_language": detected,
        "was_translated": False,
    }
