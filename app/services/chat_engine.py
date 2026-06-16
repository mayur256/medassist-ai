"""Chat engine — processes patient messages using full conversation history."""

from app.config import settings
from app.db import Message, Patient
from app.services.compliance_engine import apply_compliance
from app.services.llm_service import query_llm_json
from app.services.ner_service import extract_entities

FOLLOWUP_PROMPT = """You are a clinical decision support assistant. Be concise and decisive.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}

Conversation so far:
{history}

Questions already asked (DO NOT repeat or rephrase any of these):
{asked_questions}

RULES:
- Ask exactly ONE short, medically relevant follow-up question
- NEVER repeat, rephrase, or ask a semantically similar question to one already asked above
- If the patient says "no" to a question, accept it and move on
- Only ask if critical information is truly missing to differentiate conditions
- Set confidence 0.0-1.0 based on how sufficient the gathered info is for diagnosis

Respond with ONLY this JSON:
{{
  "content": "your single follow-up question",
  "confidence": 0.5
}}
JSON:"""

DIAGNOSE_PROMPT = """You are a clinical decision support assistant. Be concise and decisive.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}

Conversation so far:
{history}

RULES:
- Provide a differential diagnosis based on ALL information gathered
- Include confidence levels and reasoning for each condition
- Suggest relevant treatments (respecting allergies and known conditions)
- Suggest relevant diagnostic tests
- Must NOT generate prescriptions or dosage
- Must NOT provide a final diagnosis

Respond with ONLY this JSON:
{{
  "content": "brief summary of findings and clinical assessment",
  "diagnoses": [{{"condition": "name", "confidence": 0.7, "reasoning": "why"}}],
  "treatments": ["treatment1"],
  "suggested_tests": ["test1"]
}}
JSON:"""


def _extract_asked_questions(messages: list[Message]) -> list[str]:
    """Extract all questions the assistant has already asked."""
    questions = []
    for msg in messages:
        if msg.role == "assistant":
            for line in msg.content.replace("?", "?\n").split("\n"):
                line = line.strip().strip('"')
                if line.endswith("?"):
                    questions.append(line)
    return questions


async def process_chat_message(patient: Patient, messages: list[Message]) -> dict:
    """Process chat using full history with confidence-based routing."""
    history_lines = []
    for msg in messages:
        role_label = "Doctor" if msg.role == "patient" else "Assistant"
        history_lines.append(f"{role_label}: {msg.content}")
    history = "\n".join(history_lines)

    asked_questions = _extract_asked_questions(messages)

    # Extract entities from latest patient message
    latest_patient_msg = next((m for m in reversed(messages) if m.role == "patient"), None)
    raw_text = latest_patient_msg.content if latest_patient_msg else ""
    ner_result = extract_entities(raw_text)

    fmt_kwargs = dict(
        age=patient.age,
        gender=patient.gender,
        country=patient.country,
        conditions=", ".join(patient.known_conditions or []) or "none",
        allergies=", ".join(patient.allergies or []) or "none",
        history=history or "No messages yet",
    )

    # Safety cap: max iterations reached → diagnose
    should_diagnose = len(asked_questions) >= settings.max_followup_iterations

    if not should_diagnose:
        # Ask LLM for follow-up with confidence score
        prompt = FOLLOWUP_PROMPT.format(
            **fmt_kwargs,
            asked_questions="\n".join(f"- {q}" for q in asked_questions) or "None yet",
        )
        result = await query_llm_json(prompt)

        confidence = 0.0
        content = ""
        if result and isinstance(result, dict):
            content = result.get("content", "")
            confidence = float(result.get("confidence", 0.0))

        # Confidence-based routing: high confidence → proceed to diagnosis
        if confidence >= settings.confidence_threshold:
            should_diagnose = True
        elif content:
            return {
                "content": content,
                "metadata": {
                    "action": "followup",
                    "confidence": confidence,
                    "diagnoses": [],
                    "treatments": [],
                    "suggested_tests": [],
                    "red_flags": [],
                    "follow_up_questions": [],
                },
            }
        else:
            # Fallback if LLM returns empty
            return {
                "content": "Could you tell me more about your symptoms?",
                "metadata": {
                    "action": "followup",
                    "confidence": confidence,
                    "diagnoses": [],
                    "treatments": [],
                    "suggested_tests": [],
                    "red_flags": [],
                    "follow_up_questions": [],
                },
            }

    # Diagnose path
    prompt = DIAGNOSE_PROMPT.format(**fmt_kwargs)
    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        result = {"content": "Based on the information provided, here is my assessment.", "diagnoses": [], "treatments": [], "suggested_tests": []}

    treatments = result.get("treatments", [])
    compliance = apply_compliance(
        treatments=treatments,
        symptoms=ner_result.symptoms,
        raw_text=raw_text,
        country=patient.country,
        patient_age=patient.age,
        known_conditions=patient.known_conditions,
    )

    return {
        "content": result.get("content", ""),
        "metadata": {
            "action": "diagnose",
            "confidence": 1.0,
            "diagnoses": result.get("diagnoses", []),
            "treatments": compliance["treatments"],
            "suggested_tests": result.get("suggested_tests", []),
            "red_flags": compliance["red_flags"],
            "urgency_score": compliance["urgency_score"],
            "urgency_rationale": compliance["urgency_rationale"],
            "follow_up_questions": [],
        },
    }
