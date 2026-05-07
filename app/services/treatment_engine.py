"""Treatment engine: suggests non-prescriptive treatment options via LLM."""

import re

from app.services.llm_service import query_llm_json

TREATMENT_PROMPT = """You are a clinical decision support system. Suggest general treatment approaches.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Diagnoses: {diagnoses}

Respond with ONLY this JSON, nothing else:
{{"treatments": ["treatment 1", "treatment 2", "treatment 3"]}}

Rules: suggest general approaches only (e.g. "analgesics", "rest", "physical therapy"). NO specific drug dosages. Avoid anything the patient is allergic to.
JSON:"""

# Patterns that indicate prescription/dosage content
DOSAGE_PATTERNS = [
    r"\d+\s*mg",
    r"\d+\s*ml",
    r"\d+\s*tablet",
    r"\d+\s*capsule",
    r"twice\s+daily",
    r"once\s+daily",
    r"\d+\s*times?\s*(a|per)\s*day",
    r"every\s+\d+\s*hours?",
    r"b\.?i\.?d",
    r"t\.?i\.?d",
    r"q\.?i\.?d",
]


def _contains_dosage(text: str) -> bool:
    """Check if text contains prescription/dosage language."""
    for pattern in DOSAGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _filter_allergies(treatments: list[str], allergies: list[str]) -> list[str]:
    """Remove treatments that mention patient allergies."""
    if not allergies:
        return treatments
    allergy_lower = [a.lower() for a in allergies]
    return [t for t in treatments if not any(a in t.lower() for a in allergy_lower)]


async def generate_treatments(
    diagnoses: list[dict],
    patient: dict,
) -> list[str]:
    """Generate treatment suggestions. Returns list of treatment option strings."""
    prompt = TREATMENT_PROMPT.format(
        age=patient.get("age", "unknown"),
        gender=patient.get("gender", "unknown"),
        country=patient.get("country", "unknown"),
        conditions=", ".join(patient.get("known_conditions", [])) or "none",
        allergies=", ".join(patient.get("allergies", [])) or "none",
        diagnoses=", ".join(d.get("condition", "") for d in diagnoses) or "none",
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return []

    treatments = result.get("treatments", [])
    # Post-processing: remove dosage content and allergy matches
    treatments = [str(t) for t in treatments if isinstance(t, str)]
    treatments = [t for t in treatments if not _contains_dosage(t)]
    treatments = _filter_allergies(treatments, patient.get("allergies", []))
    return treatments
