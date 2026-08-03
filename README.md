---

## 📚 Documentation Guide

**New to the project?** Start here:
- 👉 **[docs/CURRENT_STATUS.md](docs/CURRENT_STATUS.md)** — What the system is NOW (architecture, APIs, features, tests)

**Want historical context?**
- 📋 **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** — [HISTORICAL] What was planned in May 2026 vs. what was built
- 📊 **[docs/FR_AUDIT.md](docs/FR_AUDIT.md)** — Technical audit of all 22 core requirements + 7 enhancements
- 🚀 **[docs/ENHANCEMENT_PROPOSAL.md](docs/ENHANCEMENT_PROPOSAL.md)** — Feature roadmap with 7/12 enhancements complete

**For API examples:**
- 🔌 **[docs/SAMPLE_REQUESTS.md](docs/SAMPLE_REQUESTS.md)** — Request/response examples with suggested tests

---

# 🧠 MedAssist-CDSS --- Software Requirements Specification (SRS)

## Version: 1.0

## Date: 2026-05-01

## Author: System Design

------------------------------------------------------------------------

# 1. 🎯 Purpose

MedAssist-CDSS is an AI-powered **Clinical Decision Support System
(CDSS)** designed to assist healthcare professionals by:

-   Generating **differential diagnoses**
-   Asking **context-aware follow-up questions**
-   Suggesting **guideline-based treatment options**

------------------------------------------------------------------------

## 🚫 Critical Constraints

The system MUST NOT: - Provide final diagnosis - Generate legally valid
prescriptions - Replace a licensed medical professional

The system MUST ALWAYS include: \> "This is AI-assisted output and must
be verified by a licensed medical professional."

------------------------------------------------------------------------

# 2. 🧩 Scope

## ✅ Included (MVP)

-   Text-based symptom input
-   Patient demographic awareness
-   Follow-up questioning loop
-   Differential diagnosis generation
-   Treatment suggestions (non-prescriptive)
-   Country-aware compliance filtering (India, US, UK)
-   Structured JSON API output

## ❌ Excluded (MVP)

-   Audio input
-   EHR integration
-   Real-time clinical deployment
-   Regulatory certification

------------------------------------------------------------------------

# 3. 🏗️ System Architecture

## 3.1 Components

FastAPI Backend ├── LangGraph Orchestrator ├── LLM Service (HuggingFace)
├── NER Service ├── RAG Service └── Compliance Engine

------------------------------------------------------------------------

# 4. 📦 Functional Requirements

## 4.1 Input Handling

### FR-INPUT-001

The system SHALL accept the following JSON input:

``` json
{
  "patient": {
    "age": 45,
    "gender": "male",
    "country": "India | US | UK",
    "known_conditions": ["string"],
    "allergies": ["string"]
  },
  "symptoms": "string"
}
```

## 4.2 Symptom Extraction (NER)

### FR-NER-001

The system SHALL extract: - Symptoms - Duration (if present) - Severity
(if present)

### FR-NER-002

The system SHALL normalize output:

``` json
{
  "symptoms": ["chest pain", "shortness of breath"],
  "duration": "2 days"
}
```

## 4.3 Follow-Up Question Engine

### FR-FOLLOWUP-001

Generate max 3 follow-up questions per iteration

### FR-FOLLOWUP-002

Ask only medically relevant questions and avoid repetition

### FR-FOLLOWUP-003

Stop when: - Confidence ≥ 0.7 OR - Max 2 iterations

## 4.4 Diagnosis Engine

### FR-DIAG-001

Generate differential diagnosis only

### FR-DIAG-002

Each diagnosis includes: - Condition - Confidence - Reasoning

## 4.5 Treatment Suggestion Engine

### FR-TREAT-001

Suggest treatment options only

### FR-TREAT-002

Respect allergies and known conditions

### FR-TREAT-003

Must NOT generate prescriptions or dosage

## 4.6 Compliance Engine

Apply country rules and remove restricted drugs. Add disclaimer always.

## 4.7 Red Flag Detection

Detect emergency symptoms and escalate

## 4.8 Output Formatting

Return structured JSON response with: - follow_up_questions -
differential_diagnosis - suggested_tests - treatment_options -
red_flags - disclaimer

------------------------------------------------------------------------

# 5. 🔁 LangGraph Flow

Input → NER → Follow-up Loop → Diagnosis → Treatment → Compliance →
Output

------------------------------------------------------------------------

# 6. 🤖 AI Model Requirements

LLM: - mistralai/Mistral-7B-Instruct - HuggingFaceH4/zephyr-7b-beta

NER: - d4data/biomedical-ner-all

Embeddings: - sentence-transformers/all-MiniLM-L6-v2

------------------------------------------------------------------------

# 7. 🔐 Non-Functional Requirements

-   Performance: ≤ 5 sec
-   Security: No data storage
-   Reliability: Handle malformed input
-   Observability: Log everything

------------------------------------------------------------------------

# 8. 🧪 Validation Rules

-   Age must be integer
-   Country must be India, US, UK
-   Output must follow JSON schema

------------------------------------------------------------------------

# 9. 🚫 Guardrails

Must NOT: - Provide diagnosis - Provide dosage - Replace doctors

------------------------------------------------------------------------

# 10. 🚀 API Specification

POST /diagnose

------------------------------------------------------------------------

# 11. 📅 MVP Milestones

Phase 1 → Setup\
Phase 2 → Orchestration\
Phase 3 → Diagnosis\
Phase 4 → Compliance + RAG

------------------------------------------------------------------------

# 12. ⚠️ Legal Notice

NOT a medical device\
NOT clinically validated

------------------------------------------------------------------------

# 13. 🔮 Future Enhancements

-   Audio input
-   EHR integration
-   Doctor dashboard
