"""Chat engine — processes patient messages using full conversation history."""

from app.db import Message, Patient
from app.services.compliance_engine import apply_compliance
from app.services.llm_service import query_llm_json
from app.services.ner_service import extract_entities


CHAT_PROMPT = """You are a clinical decision support assistant having a conversation with a healthcare professional about their patient.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}

Conversation so far:
{history}

Based on the conversation, decide what to do next:
- If you need more information, ask follow-up questions (max 3)
- If you have enough information, provide differential diagnoses and treatment suggestions

Respond with ONLY this JSON:
{{
  "action": "followup" or "diagnose",
  "content": "your natural language response to the patient",
  "follow_up_questions": ["q1", "q2"],
  "diagnoses": [{{"condition": "name", "confidence": 0.7, "reasoning": "why"}}],
  "treatments": ["treatment1", "treatment2"],
  "suggested_tests": ["test1"]
}}

If action is "followup", include questions in content. If action is "diagnose", include diagnoses and treatments.
JSON:"""


async def process_chat_message(patient: Patient, messages: list[Message]) -> dict:
    """Process chat using full history. Returns dict with content and metadata."""
    # Build history string
    history_lines = []
    for msg in messages:
        role_label = "Doctor" if msg.role == "patient" else "Assistant"
        history_lines.append(f"{role_label}: {msg.content}")
    history = "\n".join(history_lines)

    # Extract entities from latest patient message for red flags
    latest_patient_msg = next((m for m in reversed(messages) if m.role == "patient"), None)
    raw_text = latest_patient_msg.content if latest_patient_msg else ""
    ner_result = extract_entities(raw_text)

    # Query LLM with full context
    prompt = CHAT_PROMPT.format(
        age=patient.age,
        gender=patient.gender,
        country=patient.country,
        conditions=", ".join(patient.known_conditions or []) or "none",
        allergies=", ".join(patient.allergies or []) or "none",
        history=history or "No messages yet",
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        return {
            "content": "I need more information. Could you describe your symptoms in more detail?",
            "metadata": {},
        }

    # Apply compliance
    treatments = result.get("treatments", [])
    compliance = apply_compliance(
        treatments=treatments,
        symptoms=ner_result.symptoms,
        raw_text=raw_text,
        country=patient.country,
    )

    content = result.get("content", "")
    metadata = {
        "action": result.get("action", "followup"),
        "follow_up_questions": result.get("follow_up_questions", []),
        "diagnoses": result.get("diagnoses", []),
        "treatments": compliance["treatments"],
        "suggested_tests": result.get("suggested_tests", []),
        "red_flags": compliance["red_flags"],
    }

    return {"content": content, "metadata": metadata}
