"""SOAP Note Generation Service.

Generates structured clinical summaries in SOAP (Subjective, Objective, Assessment, Plan)
format from conversation history. Designed for EHR handoff and clinical documentation.
"""

import logging
from datetime import datetime

from app.db import Message, Patient
from app.services.llm_service import query_llm_json, set_audit_context

logger = logging.getLogger(__name__)

SOAP_PROMPT = """You are a clinical documentation specialist. Generate a SOAP note from the following consultation.

Patient: {name}, {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Consultation date: {date}

Full consultation transcript:
{transcript}

Generate a SOAP note following this exact JSON structure:
{{
  "subjective": {{
    "chief_complaint": "brief 1-line chief complaint",
    "history_of_present_illness": "detailed HPI from patient's own words",
    "review_of_systems": "relevant positive and negative findings mentioned",
    "past_medical_history": "relevant PMH from known conditions and conversation",
    "allergies": "documented allergies",
    "medications": "any medications mentioned or inferred"
  }},
  "objective": {{
    "vitals": "any vitals mentioned (or 'Not documented')",
    "physical_exam": "any exam findings mentioned (or 'Not documented - telehealth consultation')",
    "labs_imaging": "any test results mentioned (or 'Pending/Not yet ordered')"
  }},
  "assessment": {{
    "primary_diagnosis": "most likely diagnosis with reasoning",
    "differential_diagnoses": ["differential 1", "differential 2"],
    "severity": "mild/moderate/severe assessment",
    "clinical_reasoning": "brief reasoning connecting symptoms to assessment"
  }},
  "plan": {{
    "diagnostic_workup": ["ordered tests or recommended tests"],
    "treatment": ["treatment recommendations made"],
    "patient_education": "education/counseling provided",
    "follow_up": "follow-up plan",
    "referrals": "any referrals recommended (or 'None at this time')",
    "red_flags_discussed": "warning signs discussed with patient"
  }}
}}

Respond with ONLY the JSON, nothing else:"""


def _build_transcript(messages: list[Message]) -> str:
    """Build a readable transcript from messages."""
    lines = []
    for msg in messages:
        if msg.role == "patient":
            lines.append(f"Patient: {msg.content}")
        elif msg.role == "assistant":
            lines.append(f"Clinician/AI: {msg.content}")
        elif msg.role == "system":
            lines.append(f"[System: {msg.content}]")
    return "\n".join(lines)


def _extract_diagnoses_from_metadata(messages: list[Message]) -> list[dict]:
    """Extract diagnoses from assistant message metadata."""
    diagnoses = []
    for msg in messages:
        if msg.role == "assistant" and msg.metadata_:
            meta = msg.metadata_
            if isinstance(meta, dict) and meta.get("diagnoses"):
                diagnoses.extend(meta["diagnoses"])
    return diagnoses


def _extract_treatments_from_metadata(messages: list[Message]) -> list[str]:
    """Extract treatments from assistant message metadata."""
    treatments = []
    for msg in messages:
        if msg.role == "assistant" and msg.metadata_:
            meta = msg.metadata_
            if isinstance(meta, dict) and meta.get("treatments"):
                treatments.extend(meta["treatments"])
    return treatments


async def generate_soap_note(
    patient: Patient,
    messages: list[Message],
    conversation_id: str,
) -> dict:
    """Generate a SOAP note from a conversation.

    Args:
        patient: Patient model instance
        messages: Ordered list of messages in the conversation
        conversation_id: ID for audit logging

    Returns:
        Dict with structured SOAP note fields and a plain-text version
    """
    if not messages:
        return {
            "soap_note": _empty_soap(),
            "plain_text": "No consultation data available.",
            "generated_at": datetime.utcnow().isoformat(),
        }

    set_audit_context(conversation_id=conversation_id, step="soap_generation")

    transcript = _build_transcript(messages)

    prompt = SOAP_PROMPT.format(
        name=patient.name or "Unknown",
        age=patient.age,
        gender=patient.gender,
        country=patient.country,
        conditions=", ".join(patient.known_conditions or []) or "None documented",
        allergies=", ".join(patient.allergies or []) or "NKDA",
        date=datetime.utcnow().strftime("%Y-%m-%d"),
        transcript=transcript,
    )

    result = await query_llm_json(prompt)

    if not result or not isinstance(result, dict):
        # Fallback: build basic SOAP from metadata
        logger.warning("LLM SOAP generation failed; building from metadata")
        result = _build_soap_from_metadata(patient, messages)

    # Generate plain-text version
    plain_text = _format_soap_plain_text(result, patient)

    return {
        "soap_note": result,
        "plain_text": plain_text,
        "generated_at": datetime.utcnow().isoformat(),
        "conversation_id": conversation_id,
        "patient_id": patient.id,
    }


def _empty_soap() -> dict:
    """Return an empty SOAP structure."""
    return {
        "subjective": {
            "chief_complaint": "",
            "history_of_present_illness": "",
            "review_of_systems": "",
            "past_medical_history": "",
            "allergies": "",
            "medications": "",
        },
        "objective": {
            "vitals": "Not documented",
            "physical_exam": "Not documented",
            "labs_imaging": "Not documented",
        },
        "assessment": {
            "primary_diagnosis": "",
            "differential_diagnoses": [],
            "severity": "",
            "clinical_reasoning": "",
        },
        "plan": {
            "diagnostic_workup": [],
            "treatment": [],
            "patient_education": "",
            "follow_up": "",
            "referrals": "None at this time",
            "red_flags_discussed": "",
        },
    }


def _build_soap_from_metadata(patient: Patient, messages: list[Message]) -> dict:
    """Build a basic SOAP note from message metadata when LLM fails."""
    # Extract from patient messages
    patient_texts = [m.content for m in messages if m.role == "patient"]
    chief_complaint = patient_texts[0] if patient_texts else "Not documented"

    # Extract from metadata
    diagnoses = _extract_diagnoses_from_metadata(messages)
    treatments = _extract_treatments_from_metadata(messages)

    primary_dx = diagnoses[0].get("condition", "Undetermined") if diagnoses else "Undetermined"
    differential = [d.get("condition", "") for d in diagnoses[1:4]]

    return {
        "subjective": {
            "chief_complaint": chief_complaint[:200],
            "history_of_present_illness": " ".join(patient_texts),
            "review_of_systems": "As documented in consultation",
            "past_medical_history": ", ".join(patient.known_conditions or []) or "None",
            "allergies": ", ".join(patient.allergies or []) or "NKDA",
            "medications": "See known conditions",
        },
        "objective": {
            "vitals": "Not documented - telehealth consultation",
            "physical_exam": "Not documented - telehealth consultation",
            "labs_imaging": "Pending",
        },
        "assessment": {
            "primary_diagnosis": primary_dx,
            "differential_diagnoses": differential,
            "severity": "To be determined",
            "clinical_reasoning": diagnoses[0].get("reasoning", "") if diagnoses else "",
        },
        "plan": {
            "diagnostic_workup": [],
            "treatment": treatments[:5],
            "patient_education": "Standard precautions discussed",
            "follow_up": "As clinically indicated",
            "referrals": "None at this time",
            "red_flags_discussed": "Return if symptoms worsen",
        },
    }


def _format_soap_plain_text(soap: dict, patient: Patient) -> str:
    """Format SOAP note as plain text for easy reading/export."""
    lines = []
    lines.append("=" * 60)
    lines.append("CLINICAL SOAP NOTE")
    lines.append("=" * 60)
    lines.append(f"Patient: {patient.name or 'N/A'}, {patient.age}y {patient.gender}")
    lines.append(f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("-" * 60)

    # Subjective
    subj = soap.get("subjective", {})
    lines.append("\nSUBJECTIVE:")
    lines.append(f"  Chief Complaint: {subj.get('chief_complaint', 'N/A')}")
    lines.append(f"  HPI: {subj.get('history_of_present_illness', 'N/A')}")
    lines.append(f"  ROS: {subj.get('review_of_systems', 'N/A')}")
    lines.append(f"  PMH: {subj.get('past_medical_history', 'N/A')}")
    lines.append(f"  Allergies: {subj.get('allergies', 'NKDA')}")
    lines.append(f"  Medications: {subj.get('medications', 'N/A')}")

    # Objective
    obj = soap.get("objective", {})
    lines.append("\nOBJECTIVE:")
    lines.append(f"  Vitals: {obj.get('vitals', 'Not documented')}")
    lines.append(f"  Physical Exam: {obj.get('physical_exam', 'Not documented')}")
    lines.append(f"  Labs/Imaging: {obj.get('labs_imaging', 'Not documented')}")

    # Assessment
    assess = soap.get("assessment", {})
    lines.append("\nASSESSMENT:")
    lines.append(f"  Primary Diagnosis: {assess.get('primary_diagnosis', 'N/A')}")
    differentials = assess.get("differential_diagnoses", [])
    if differentials:
        lines.append(f"  Differential: {', '.join(differentials)}")
    lines.append(f"  Severity: {assess.get('severity', 'N/A')}")
    lines.append(f"  Reasoning: {assess.get('clinical_reasoning', 'N/A')}")

    # Plan
    plan = soap.get("plan", {})
    lines.append("\nPLAN:")
    workup = plan.get("diagnostic_workup", [])
    if workup:
        lines.append(f"  Workup: {', '.join(workup)}")
    treatments = plan.get("treatment", [])
    if treatments:
        lines.append(f"  Treatment: {', '.join(treatments)}")
    lines.append(f"  Education: {plan.get('patient_education', 'N/A')}")
    lines.append(f"  Follow-up: {plan.get('follow_up', 'N/A')}")
    lines.append(f"  Referrals: {plan.get('referrals', 'None')}")
    lines.append(f"  Red Flags: {plan.get('red_flags_discussed', 'N/A')}")

    lines.append("\n" + "-" * 60)
    lines.append("DISCLAIMER: AI-assisted documentation. Must be reviewed")
    lines.append("and co-signed by a licensed healthcare professional.")
    lines.append("=" * 60)

    return "\n".join(lines)
