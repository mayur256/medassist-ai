"""Follow-up question engine using LLM."""

from app.config import settings
from app.services.llm_service import query_llm_json

FOLLOWUP_PROMPT = """You are a medical assistant. Based on the patient info below, generate follow-up questions.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Symptoms: {symptoms}
Previous questions: {previous_questions}

Respond with ONLY this JSON, nothing else:
{{"questions": ["question1", "question2"], "confidence": 0.5}}

Generate up to {max_questions} questions. Set confidence 0.0-1.0 based on how much info you have.
JSON:"""


async def generate_followup(
    symptoms: list[str],
    patient: dict,
    previous_questions: list[str] | None = None,
    iteration: int = 0,
) -> dict:
    """Generate follow-up questions. Returns {"questions": [...], "confidence": float, "should_stop": bool}."""
    if iteration >= settings.max_followup_iterations:
        return {"questions": [], "confidence": 1.0, "should_stop": True}

    prompt = FOLLOWUP_PROMPT.format(
        age=patient.get("age", "unknown"),
        gender=patient.get("gender", "unknown"),
        country=patient.get("country", "unknown"),
        conditions=", ".join(patient.get("known_conditions", [])) or "none",
        allergies=", ".join(patient.get("allergies", [])) or "none",
        symptoms=", ".join(symptoms) or "none reported",
        previous_questions=", ".join(previous_questions or []) or "none",
        max_questions=settings.max_followup_questions,
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return {"questions": [], "confidence": 0.0, "should_stop": True}

    questions = result.get("questions", [])[:settings.max_followup_questions]
    confidence = float(result.get("confidence", 0.0))
    should_stop = confidence >= settings.confidence_threshold or not questions

    return {"questions": questions, "confidence": confidence, "should_stop": should_stop}
