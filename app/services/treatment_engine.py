"""Treatment engine: suggests non-prescriptive treatment options via LLM."""

import re

from app.services.llm_service import query_llm_json
from app.services.rag_service import build_treatment_context

TREATMENT_PROMPT = """You are a clinical decision support system. Suggest general treatment approaches.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Diagnoses: {diagnoses}

{guidelines_context}

Rules:
- Suggest general approaches only (e.g. "analgesics", "rest", "physical therapy")
- NO specific drug dosages or prescription details
- Avoid anything the patient is allergic to
- Ground treatment suggestions in the clinical guidelines provided above
- Prioritize evidence-based approaches from the guidelines
- Consider patient's known conditions and contraindications

Respond with ONLY this JSON, nothing else:
{{"treatments": ["treatment 1", "treatment 2", "treatment 3"]}}

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
) -> dict:
    """
    Generate treatment suggestions. 
    
    Returns dict with:
        - treatments: list of treatment option strings
        - guideline_citations: citations from guidelines used
    """
    country = patient.get("country")
    allergies = patient.get("allergies", [])
    
    # Fetch treatment guidelines using RAG
    treatment_context = await build_treatment_context(
        diagnoses=diagnoses,
        country=country,
        patient_allergies=allergies,
    )
    
    guidelines_text = treatment_context.get("guidelines_text", "")
    citations = treatment_context.get("citations", {})
    
    prompt = TREATMENT_PROMPT.format(
        age=patient.get("age", "unknown"),
        gender=patient.get("gender", "unknown"),
        country=country or "unknown",
        conditions=", ".join(patient.get("known_conditions", [])) or "none",
        allergies=", ".join(allergies) or "none",
        diagnoses=", ".join(d.get("condition", "") for d in diagnoses) or "none",
        guidelines_context=guidelines_text,
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return {
            "treatments": [],
            "guideline_citations": citations,
        }

    treatments = result.get("treatments", [])
    # Post-processing: remove dosage content and allergy matches
    treatments = [str(t) for t in treatments if isinstance(t, str)]
    treatments = [t for t in treatments if not _contains_dosage(t)]
    treatments = _filter_allergies(treatments, allergies)
    
    return {
        "treatments": treatments,
        "guideline_citations": citations,
    }
