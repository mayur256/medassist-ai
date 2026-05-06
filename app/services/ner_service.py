"""Biomedical NER service using d4data/biomedical-ner-all."""

import re
from dataclasses import dataclass, field

from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

from app.config import settings

# Lazy-loaded pipeline
_ner_pipeline = None

# Entity labels that map to symptoms
SYMPTOM_LABELS = {"Sign_symptom", "Detailed_description", "Disease_disorder"}
DURATION_LABELS = {"Duration", "Date", "Time"}
SEVERITY_LABELS = {"Severity", "Qualitative_concept"}


@dataclass
class NERResult:
    symptoms: list[str] = field(default_factory=list)
    duration: str | None = None
    severity: str | None = None


def _get_pipeline():
    global _ner_pipeline
    if _ner_pipeline is None:
        tokenizer = AutoTokenizer.from_pretrained(settings.ner_model)
        model = AutoModelForTokenClassification.from_pretrained(settings.ner_model)
        _ner_pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
        )
    return _ner_pipeline


def _extract_duration_from_text(text: str) -> str | None:
    """Regex fallback for duration extraction."""
    pattern = r"\b(\d+\s*(?:day|days|week|weeks|month|months|hour|hours|year|years|minute|minutes))\b"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_entities(text: str) -> NERResult:
    """Extract symptoms, duration, and severity from free text."""
    pipe = _get_pipeline()
    entities = pipe(text)

    symptoms: list[str] = []
    duration: str | None = None
    severity: str | None = None

    for ent in entities:
        label = ent["entity_group"]
        word = ent["word"].strip()
        if not word:
            continue

        if label in SYMPTOM_LABELS:
            normalized = word.lower().strip(".,;")
            if normalized and normalized not in symptoms:
                symptoms.append(normalized)
        elif label in DURATION_LABELS and duration is None:
            duration = word
        elif label in SEVERITY_LABELS and severity is None:
            severity = word

    # Fallback: try regex for duration if NER missed it
    if duration is None:
        duration = _extract_duration_from_text(text)

    return NERResult(symptoms=symptoms, duration=duration, severity=severity)
