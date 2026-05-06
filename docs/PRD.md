# Product Requirements Document (PRD)
# MedAssist-CDSS v1.0

## 1. Product Overview

MedAssist-CDSS is an AI-powered Clinical Decision Support System that assists healthcare professionals by generating differential diagnoses, asking context-aware follow-up questions, and suggesting guideline-based treatment options.

**Target Users:** Licensed healthcare professionals (doctors, nurses, clinical staff)

**Deployment:** API-first backend service consumed by clinical frontends

---

## 2. Problem Statement

Healthcare professionals face cognitive overload when evaluating complex symptom presentations. MedAssist-CDSS provides AI-assisted second opinions to reduce diagnostic errors and surface treatment options aligned with clinical guidelines.

---

## 3. Goals & Success Metrics

| Goal | Metric | Target |
|------|--------|--------|
| Fast response | End-to-end latency | ≤ 5 seconds |
| Relevant diagnoses | Differential accuracy | Top-3 includes correct condition ≥ 70% of cases |
| Safety compliance | Disclaimer presence | 100% of responses |
| Usability | Structured output | 100% JSON schema conformance |

---

## 4. Functional Requirements

### 4.1 Input Handling (FR-INPUT)

| ID | Requirement |
|----|-------------|
| FR-INPUT-001 | Accept JSON with patient demographics (age, gender, country, known_conditions, allergies) and free-text symptoms |
| FR-INPUT-002 | Validate age as integer, country as India/US/UK |
| FR-INPUT-003 | Gracefully reject malformed input with descriptive errors |

### 4.2 Symptom Extraction — NER (FR-NER)

| ID | Requirement |
|----|-------------|
| FR-NER-001 | Extract symptoms, duration, and severity from free text |
| FR-NER-002 | Use `d4data/biomedical-ner-all` model |
| FR-NER-003 | Output normalized structured data |

### 4.3 Follow-Up Question Engine (FR-FOLLOWUP)

| ID | Requirement |
|----|-------------|
| FR-FOLLOWUP-001 | Generate max 3 follow-up questions per iteration |
| FR-FOLLOWUP-002 | Questions must be medically relevant and non-repetitive |
| FR-FOLLOWUP-003 | Stop when confidence ≥ 0.7 OR max 2 iterations reached |

### 4.4 Diagnosis Engine (FR-DIAG)

| ID | Requirement |
|----|-------------|
| FR-DIAG-001 | Generate differential diagnoses only (never final diagnosis) |
| FR-DIAG-002 | Each diagnosis includes: condition name, confidence score, reasoning |
| FR-DIAG-003 | Consider patient demographics and known conditions |

### 4.5 Treatment Suggestion Engine (FR-TREAT)

| ID | Requirement |
|----|-------------|
| FR-TREAT-001 | Suggest non-prescriptive treatment options |
| FR-TREAT-002 | Respect patient allergies and known conditions |
| FR-TREAT-003 | MUST NOT generate prescriptions or dosage information |

### 4.6 Compliance Engine (FR-COMP)

| ID | Requirement |
|----|-------------|
| FR-COMP-001 | Apply country-specific drug restriction rules (India, US, UK) |
| FR-COMP-002 | Remove restricted/banned substances from suggestions |
| FR-COMP-003 | Always inject disclaimer in output |

### 4.7 Red Flag Detection (FR-RED)

| ID | Requirement |
|----|-------------|
| FR-RED-001 | Detect emergency symptoms (chest pain + SOB, stroke signs, etc.) |
| FR-RED-002 | Flag urgent cases for immediate escalation |

### 4.8 Output Format (FR-OUT)

| ID | Requirement |
|----|-------------|
| FR-OUT-001 | Return structured JSON with: follow_up_questions, differential_diagnosis, suggested_tests, treatment_options, red_flags, disclaimer |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| Performance | Response time ≤ 5 seconds |
| Security | No patient data stored; stateless processing |
| Reliability | Graceful error handling for malformed input and model failures |
| Observability | Structured logging for all operations |
| Scalability | Stateless design allows horizontal scaling |

---

## 6. Constraints & Guardrails

- MUST NOT provide final diagnosis
- MUST NOT generate legally valid prescriptions or dosage
- MUST NOT replace a licensed medical professional
- MUST include disclaimer in every response
- NOT a medical device; NOT clinically validated

---

## 7. API Specification

### POST /diagnose

**Request:**
```json
{
  "patient": {
    "age": 45,
    "gender": "male",
    "country": "India",
    "known_conditions": ["diabetes"],
    "allergies": ["penicillin"]
  },
  "symptoms": "chest pain and shortness of breath for 2 days"
}
```

**Response:**
```json
{
  "follow_up_questions": ["Do you experience pain at rest or during exertion?"],
  "differential_diagnosis": [
    {
      "condition": "Acute Coronary Syndrome",
      "confidence": 0.8,
      "reasoning": "Chest pain with SOB in 45M with diabetes"
    }
  ],
  "suggested_tests": ["ECG", "Troponin levels", "Chest X-ray"],
  "treatment_options": ["Aspirin (if no allergy)", "Oxygen therapy"],
  "red_flags": ["Possible cardiac emergency - immediate evaluation recommended"],
  "disclaimer": "This is AI-assisted output and must be verified by a licensed medical professional."
}
```

---

## 8. AI Models

| Purpose | Model |
|---------|-------|
| LLM (primary) | mistralai/Mistral-7B-Instruct |
| LLM (fallback) | HuggingFaceH4/zephyr-7b-beta |
| NER | d4data/biomedical-ner-all |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |

---

## 9. Out of Scope (MVP)

- Audio/voice input
- EHR/EMR integration
- Real-time clinical deployment
- Regulatory certification (FDA/CE)
- Multi-language support
- Doctor dashboard UI

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| LLM hallucination | Confidence thresholds + disclaimer |
| Harmful suggestions | Compliance engine + guardrails |
| Latency spikes | Model caching + timeout handling |
| Misuse as diagnostic tool | Mandatory disclaimer + legal notice |
