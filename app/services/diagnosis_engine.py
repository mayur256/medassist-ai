"""Diagnosis engine: generates differential diagnoses via LLM."""

from app.services.llm_service import query_llm_json

DIAGNOSIS_PROMPT = """You are a clinical decision support system. Generate differential diagnoses for this patient.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Symptoms: {symptoms}
Duration: {duration}
Severity: {severity}

Respond with ONLY this JSON, nothing else:
{{"diagnoses": [{{"condition": "name", "confidence": 0.7, "reasoning": "brief reason"}}]}}

List up to 5 possible conditions ranked by likelihood.
JSON:"""


async def generate_diagnoses(
    symptoms: list[str],
    patient: dict,
    duration: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    """Generate differential diagnoses. Returns list of {condition, confidence, reasoning}."""
    prompt = DIAGNOSIS_PROMPT.format(
        age=patient.get("age", "unknown"),
        gender=patient.get("gender", "unknown"),
        country=patient.get("country", "unknown"),
        conditions=", ".join(patient.get("known_conditions", [])) or "none",
        allergies=", ".join(patient.get("allergies", [])) or "none",
        symptoms=", ".join(symptoms) or "none reported",
        duration=duration or "not specified",
        severity=severity or "not specified",
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return []

    diagnoses = result.get("diagnoses", [])
    # Validate and clamp confidence values
    validated = []
    for d in diagnoses[:5]:
        if isinstance(d, dict) and "condition" in d:
            validated.append({
                "condition": str(d["condition"]),
                "confidence": max(0.0, min(1.0, float(d.get("confidence", 0.5)))),
                "reasoning": str(d.get("reasoning", "")),
            })
    return validated
