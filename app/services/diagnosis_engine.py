"""Diagnosis engine: generates differential diagnoses via LLM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.llm_service import query_llm_json
from app.services.ner_service import format_timeline_for_prompt

if TYPE_CHECKING:
    from app.services.ner_service import SymptomEvent

DIAGNOSIS_PROMPT = """You are a clinical decision support system. Generate differential diagnoses and recommended diagnostic tests for this patient.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Symptoms: {symptoms}
Duration: {duration}
Severity: {severity}
{timeline_block}

RULES:
- Use the symptom timeline (onset, progression) to differentiate between conditions
- A sudden onset suggests acute conditions; gradual onset suggests chronic
- Worsening symptoms increase urgency; improving symptoms lower likelihood of serious pathology
- Temporal ordering of symptoms helps narrow the differential
- For suggested tests, explain what each test would confirm or rule out

Respond with ONLY this JSON, nothing else:
{{"diagnoses": [{{"condition": "name", "confidence": 0.7, "reasoning": "brief reason"}}], "suggested_tests": [{{"test": "test name", "reasoning": "what this test would confirm or rule out"}}]}}

List up to 5 possible conditions ranked by likelihood.
Suggest up to 5 relevant diagnostic tests with clinical reasoning for each.
JSON:"""


async def generate_diagnoses(
    symptoms: list[str],
    patient: dict,
    duration: str | None = None,
    severity: str | None = None,
    timeline: list[SymptomEvent] | None = None,
) -> dict:
    """Generate differential diagnoses and suggested tests.

    Returns dict with:
        - diagnoses: list of {condition, confidence, reasoning}
        - suggested_tests: list of {test, reasoning}
    """
    timeline_block = format_timeline_for_prompt(timeline or [])

    prompt = DIAGNOSIS_PROMPT.format(
        age=patient.get("age", "unknown"),
        gender=patient.get("gender", "unknown"),
        country=patient.get("country", "unknown"),
        conditions=", ".join(patient.get("known_conditions", [])) or "none",
        allergies=", ".join(patient.get("allergies", [])) or "none",
        symptoms=", ".join(symptoms) or "none reported",
        duration=duration or "not specified",
        severity=severity or "not specified",
        timeline_block=timeline_block,
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return {"diagnoses": [], "suggested_tests": []}

    # Validate diagnoses
    diagnoses = result.get("diagnoses", [])
    validated_diagnoses = []
    for d in diagnoses[:5]:
        if isinstance(d, dict) and "condition" in d:
            validated_diagnoses.append({
                "condition": str(d["condition"]),
                "confidence": max(0.0, min(1.0, float(d.get("confidence", 0.5)))),
                "reasoning": str(d.get("reasoning", "")),
            })

    # Validate suggested tests
    raw_tests = result.get("suggested_tests", [])
    validated_tests = []
    for t in raw_tests[:5]:
        if isinstance(t, dict) and "test" in t:
            validated_tests.append({
                "test": str(t["test"]),
                "reasoning": str(t.get("reasoning", "")),
            })

    return {"diagnoses": validated_diagnoses, "suggested_tests": validated_tests}
