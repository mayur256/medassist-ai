"""Streaming Service — SSE streaming for diagnosis pipeline.

Provides Server-Sent Events (SSE) streaming for the diagnosis flow,
sending progress updates and partial results as each pipeline stage completes.
Supports token-by-token streaming from the LLM for the diagnosis step.
"""

import json
import logging
import time
from typing import AsyncGenerator

import httpx

from app.config import settings
from app.models.request import DiagnoseRequest, PatientInfo
from app.services.compliance_engine import apply_compliance
from app.services.drug_interaction_service import check_and_filter_interactions
from app.services.ner_service import extract_entities, format_timeline_for_prompt
from app.services.translation_service import translate_to_english

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Diagnosis prompt for streaming (same as diagnosis_engine but self-contained)
STREAM_DIAGNOSIS_PROMPT = """You are a clinical decision support system generating differential diagnoses.

Patient: {age} year old {gender} from {country}
Known conditions: {conditions}
Allergies: {allergies}
Symptoms: {symptoms}
Duration: {duration}
Severity: {severity}

{timeline_block}

Rules:
- Generate differential diagnoses only (NEVER a final diagnosis)
- Each diagnosis needs: condition name, confidence (0.0-1.0), reasoning
- Consider patient demographics, known conditions, symptom timeline
- Suggest relevant diagnostic tests with reasoning
- Suggest general treatment approaches (NO dosages or prescriptions)

Respond with ONLY this JSON:
{{"diagnoses": [{{"condition": "name", "confidence": 0.7, "reasoning": "why"}}], "suggested_tests": [{{"test": "name", "reasoning": "why"}}], "treatments": ["treatment option 1", "treatment option 2"]}}

JSON:"""


async def _stream_groq_tokens(prompt: str) -> AsyncGenerator[str, None]:
    """Stream tokens from Groq API using SSE."""
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.3,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", GROQ_URL, json=payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        logger.error("Groq streaming failed: %s", e)
        yield ""


def _format_sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    json_data = json.dumps(data)
    return f"event: {event}\ndata: {json_data}\n\n"


async def stream_diagnosis(request: DiagnoseRequest) -> AsyncGenerator[str, None]:
    """Stream the full diagnosis pipeline as SSE events.

    Events emitted:
    - stage_start: {stage: "ner"|"diagnosis"|"compliance", message: "..."}
    - stage_complete: {stage: "...", result: {...}}
    - token: {content: "..."} — individual LLM tokens during diagnosis
    - result: {response: {...}} — final complete response
    - error: {message: "..."} — if something fails
    """
    patient = request.patient
    start_time = time.time()

    try:
        # === Stage 1: NER ===
        yield _format_sse_event("stage_start", {
            "stage": "ner",
            "message": "Extracting symptoms and clinical entities...",
        })

        # Translate if non-English
        translation = await translate_to_english(request.symptoms)
        text_for_ner = translation["translated_text"]

        if translation["was_translated"]:
            yield _format_sse_event("stage_complete", {
                "stage": "translation",
                "result": {
                    "detected_language": translation["detected_language"],
                    "original_text": translation["original_text"][:100],
                },
            })

        ner_result = extract_entities(text_for_ner)
        timeline_block = format_timeline_for_prompt(ner_result.timeline)

        yield _format_sse_event("stage_complete", {
            "stage": "ner",
            "result": {
                "symptoms": ner_result.symptoms,
                "duration": ner_result.duration,
                "severity": ner_result.severity,
                "timeline_events": len(ner_result.timeline),
            },
        })

        # === Stage 2: Diagnosis (with token streaming) ===
        yield _format_sse_event("stage_start", {
            "stage": "diagnosis",
            "message": "Generating differential diagnosis...",
        })

        prompt = STREAM_DIAGNOSIS_PROMPT.format(
            age=patient.age,
            gender=patient.gender,
            country=patient.country,
            conditions=", ".join(patient.known_conditions) or "none",
            allergies=", ".join(patient.allergies) or "none",
            symptoms=", ".join(ner_result.symptoms) or request.symptoms,
            duration=ner_result.duration or "not specified",
            severity=ner_result.severity or "not specified",
            timeline_block=timeline_block,
        )

        # Stream tokens
        full_response = ""
        async for token in _stream_groq_tokens(prompt):
            full_response += token
            yield _format_sse_event("token", {"content": token})

        # Parse the accumulated response
        diagnoses = []
        suggested_tests = []
        treatments = []

        try:
            # Try to extract JSON from accumulated response
            from app.services.llm_service import _extract_json
            parsed = _extract_json(full_response)
            if parsed and isinstance(parsed, dict):
                diagnoses = parsed.get("diagnoses", [])
                suggested_tests = parsed.get("suggested_tests", [])
                treatments = parsed.get("treatments", [])
        except Exception as e:
            logger.warning("Failed to parse streamed diagnosis response: %s", e)

        yield _format_sse_event("stage_complete", {
            "stage": "diagnosis",
            "result": {
                "diagnosis_count": len(diagnoses),
                "test_count": len(suggested_tests),
            },
        })

        # === Stage 3: Compliance + Drug Interactions ===
        yield _format_sse_event("stage_start", {
            "stage": "compliance",
            "message": "Applying safety checks and drug interaction screening...",
        })

        compliance = apply_compliance(
            treatments=treatments,
            symptoms=ner_result.symptoms,
            raw_text=request.symptoms,
            country=patient.country,
            patient_age=patient.age,
            known_conditions=patient.known_conditions,
        )

        interaction_result = check_and_filter_interactions(
            treatments=compliance["treatments"],
            known_conditions=patient.known_conditions,
        )

        yield _format_sse_event("stage_complete", {
            "stage": "compliance",
            "result": {
                "red_flags": compliance["red_flags"],
                "urgency_score": compliance["urgency_score"],
                "interactions_found": len(interaction_result["interactions"]),
            },
        })

        # === Final Result ===
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Clamp confidences
        for d in diagnoses:
            if isinstance(d, dict) and "confidence" in d:
                d["confidence"] = max(0.0, min(1.0, float(d.get("confidence", 0.5))))

        final_response = {
            "status": "complete",
            "confidence": diagnoses[0]["confidence"] if diagnoses else 0.0,
            "differential_diagnosis": diagnoses,
            "suggested_tests": suggested_tests,
            "treatment_options": interaction_result["treatments"],
            "red_flags": compliance["red_flags"],
            "urgency_score": compliance["urgency_score"],
            "urgency_rationale": compliance["urgency_rationale"],
            "drug_interactions": interaction_result["interactions"],
            "interaction_warnings": interaction_result["warnings"],
            "disclaimer": "This is AI-assisted output and must be verified by a licensed medical professional.",
            "elapsed_ms": elapsed_ms,
        }

        yield _format_sse_event("result", {"response": final_response})

    except Exception as e:
        logger.error("Streaming diagnosis failed: %s", e, exc_info=True)
        yield _format_sse_event("error", {"message": f"Pipeline error: {str(e)}"})
