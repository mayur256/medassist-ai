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
class SymptomEvent:
    """A single symptom with its temporal context."""

    symptom: str
    onset: str | None = None  # e.g. "3 days ago", "last week"
    progression: str | None = None  # e.g. "worsening", "stable", "improving"


@dataclass
class NERResult:
    symptoms: list[str] = field(default_factory=list)
    duration: str | None = None
    severity: str | None = None
    timeline: list[SymptomEvent] = field(default_factory=list)


# --- Temporal extraction patterns ---

# Common time unit pattern (singular or plural)
_TIME_UNITS = r"(?:days?|weeks?|months?|hours?|years?|minutes?)"

# Matches relative time expressions: "3 days ago", "for 2 weeks", "since last Monday"
# Ordered from most specific to least specific to get best matches
_ONSET_PATTERNS = [
    # "started X days/weeks ago"
    re.compile(
        rf"(started\s+\d+\s*{_TIME_UNITS}\s+ago)",
        re.IGNORECASE,
    ),
    # "started last week/month/yesterday"
    re.compile(
        r"(started\s+(?:last\s+)?(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|this\s+morning))",
        re.IGNORECASE,
    ),
    # "since X days/weeks ago"
    re.compile(
        rf"(since\s+\d+\s*{_TIME_UNITS}\s+ago)",
        re.IGNORECASE,
    ),
    # "since last week/month/Monday/yesterday"
    re.compile(
        r"(since\s+(?:last\s+)?(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday|yesterday|morning|evening|night))",
        re.IGNORECASE,
    ),
    # "over the past X days/weeks"
    re.compile(
        rf"(over\s+the\s+(?:past|last)\s+\d+\s*{_TIME_UNITS})",
        re.IGNORECASE,
    ),
    # "for X days/weeks/months"
    re.compile(
        rf"(for\s+\d+\s*{_TIME_UNITS})",
        re.IGNORECASE,
    ),
    # "X days/weeks/months/hours ago"
    re.compile(
        rf"(\d+\s*{_TIME_UNITS}\s+ago)",
        re.IGNORECASE,
    ),
    # "last X days/weeks" (with optional "the")
    re.compile(
        rf"((?:the\s+)?last\s+\d+\s*{_TIME_UNITS})",
        re.IGNORECASE,
    ),
    # "for a week/month"
    re.compile(
        rf"(for\s+a\s+{_TIME_UNITS})",
        re.IGNORECASE,
    ),
    # "yesterday", "this morning", "last night"
    re.compile(
        r"\b(yesterday|this\s+morning|last\s+night|today|tonight|this\s+evening)\b",
        re.IGNORECASE,
    ),
]

# Progression indicators — ordered from most specific to least specific
_PROGRESSION_PATTERNS = [
    (re.compile(r"\b(intermittent|comes?\s+and\s+goes?|on\s+and\s+off|episodic|fluctuating)\b", re.IGNORECASE), "intermittent"),
    (re.compile(r"\b(sudden(?:ly)?|abrupt(?:ly)?|acute)\b", re.IGNORECASE), "sudden onset"),
    (re.compile(r"\b(gradual(?:ly)?|slowly|progressive(?:ly)?)\b", re.IGNORECASE), "gradual onset"),
    (re.compile(r"\b(worsening|getting\s+worse|deteriorating|intensifying|increasing)\b", re.IGNORECASE), "worsening"),
    (re.compile(r"\b(improving|getting\s+better|subsiding|resolving|decreasing)\b", re.IGNORECASE), "improving"),
    (re.compile(r"\b(constant|persistent|unchanged|stable|steady|continuous)\b", re.IGNORECASE), "stable"),
]

# Pattern to associate symptoms with temporal context in the same clause/sentence
_SENTENCE_SPLIT = re.compile(r"[.;!\n]+|(?:,\s*(?:and|but|then|also|which|that))")


def _extract_onset(text: str) -> str | None:
    """Extract the first temporal onset expression from text."""
    for pattern in _ONSET_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _extract_progression(text: str) -> str | None:
    """Extract progression indicator from text."""
    for pattern, label in _PROGRESSION_PATTERNS:
        if pattern.search(text):
            return label
    return None


def extract_timeline(text: str, symptoms: list[str]) -> list[SymptomEvent]:
    """Extract structured timeline associating symptoms with temporal context.

    Strategy:
    1. Split text into sentence-like segments
    2. For each segment, check if it contains a known symptom
    3. Extract onset and progression from that segment
    4. Fallback: use document-level temporal info for symptoms without local context
    """
    if not text or not symptoms:
        return []

    # Split into sentence-like segments
    segments = _SENTENCE_SPLIT.split(text)
    segments = [s.strip() for s in segments if s.strip()]

    # Track which symptoms have been assigned temporal context
    events: list[SymptomEvent] = []
    matched_symptoms: set[str] = set()
    symptoms_with_temporal: set[str] = set()

    for segment in segments:
        segment_lower = segment.lower()
        # Find symptoms mentioned in this segment
        segment_symptoms = []
        for symptom in symptoms:
            if symptom.lower() in segment_lower:
                segment_symptoms.append(symptom)

        if not segment_symptoms:
            continue

        # Extract temporal info from this segment
        onset = _extract_onset(segment)
        progression = _extract_progression(segment)

        for symptom in segment_symptoms:
            if symptom not in matched_symptoms:
                events.append(SymptomEvent(
                    symptom=symptom,
                    onset=onset,
                    progression=progression,
                ))
                matched_symptoms.add(symptom)
                if onset or progression:
                    symptoms_with_temporal.add(symptom)

    # Document-level fallback: extract global onset/progression for symptoms
    # that were either unmatched or matched without any temporal context
    global_onset = _extract_onset(text)
    global_progression = _extract_progression(text)

    for symptom in symptoms:
        if symptom not in matched_symptoms:
            # Symptom never appeared in any segment
            events.append(SymptomEvent(
                symptom=symptom,
                onset=global_onset,
                progression=global_progression,
            ))
        elif symptom not in symptoms_with_temporal:
            # Symptom was matched but had no local temporal context — apply global
            for event in events:
                if event.symptom == symptom and not event.onset and not event.progression:
                    event.onset = global_onset
                    event.progression = global_progression
                    break

    return events


def format_timeline_for_prompt(timeline: list[SymptomEvent]) -> str:
    """Format structured timeline into a readable string for LLM prompts.

    Returns empty string if no meaningful temporal data exists.
    """
    if not timeline:
        return ""

    # Check if we have any temporal info at all
    has_temporal = any(e.onset or e.progression for e in timeline)
    if not has_temporal:
        return ""

    lines = []
    for event in timeline:
        parts = [f"- {event.symptom}"]
        if event.onset:
            parts.append(f"onset: {event.onset}")
        if event.progression:
            parts.append(f"progression: {event.progression}")
        lines.append(" | ".join(parts))

    return "Symptom Timeline:\n" + "\n".join(lines)


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
    """Extract symptoms, duration, severity, and structured timeline from free text."""
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

    # Extract structured timeline
    timeline = extract_timeline(text, symptoms)

    return NERResult(symptoms=symptoms, duration=duration, severity=severity, timeline=timeline)
