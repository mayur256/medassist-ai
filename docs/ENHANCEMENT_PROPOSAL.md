# MedAssist-CDSS Enhancement Proposal

**Version:** 1.0  
**Date:** 2026-05-19  
**Status:** Proposed  

---

## Overview

This document captures proposed enhancements to the MedAssist-CDSS system beyond the current MVP. Each enhancement includes a description, rationale, implementation notes, and an audit section to be filled during/after implementation.

---

## Enhancement Index

| # | Enhancement | Priority | Effort | Status |
|---|-------------|----------|--------|--------|
| 1 | Conversation Memory & Patient History | High | Medium | ⬜ Proposed |
| 2 | RAG with Clinical Guidelines | High | High | ⬜ Proposed |
| 3 | Confidence-Based Routing | High | Low | ⬜ Proposed |
| 4 | Structured Symptom Timeline | High | Medium | ⬜ Proposed |
| 5 | Suggested Tests with Reasoning | Medium | Low | ⬜ Proposed |
| 6 | Drug Interaction Checking | Medium | Medium | ⬜ Proposed |
| 7 | Severity Triage / Urgency Score | Medium | Low | ⬜ Proposed |
| 8 | Conversation Export / SOAP Summary | Medium | Medium | ⬜ Proposed |
| 9 | Streaming Responses | Medium | Medium | ⬜ Proposed |
| 10 | Multi-language Symptom Input | Medium | Medium | ⬜ Proposed |
| 11 | Audit Trail / Explainability | Medium | Low | ⬜ Proposed |
| 12 | Session Persistence | Low | Low | ⬜ Proposed |

**Status Legend:** ⬜ Proposed → 🔄 In Progress → ✅ Implemented → 🔍 Audited

---

## 1. Conversation Memory & Patient History Awareness

**Priority:** High  
**Effort:** Medium  
**Affected Components:** `chat_engine.py`, `conversations.py`, `db.py`

### Description

Enable the system to reference past consultations for the same patient when generating follow-up questions and diagnoses. The assistant should be aware of previously reported symptoms, diagnoses, and treatments.

### Rationale

- Reduces redundant questioning across visits
- Improves diagnostic accuracy with longitudinal context
- Enables tracking of chronic condition progression

### Implementation Notes

- Query last N completed conversations for the patient before building the prompt
- Summarize past conversations into a compact context block
- Add a `patient_history_summary` field to the prompt templates
- Respect a token budget to avoid context overflow

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 2. RAG with Clinical Guidelines

**Priority:** High  
**Effort:** High  
**Affected Components:** New `rag_service.py`, `diagnosis_engine.py`, `treatment_engine.py`

### Description

Embed clinical guidelines (WHO, NICE, ICMR) into a vector store and retrieve relevant passages during diagnosis and treatment generation to ground LLM output in evidence-based medicine.

### Rationale

- Reduces hallucination risk in clinical recommendations
- Provides traceable, citation-backed suggestions
- Enables country-specific guideline adherence (NICE for UK, ICMR for India)

### Implementation Notes

- Use `sentence-transformers/all-MiniLM-L6-v2` (already in config) for embeddings
- Store vectors in PostgreSQL with pgvector extension, or use ChromaDB
- Chunk guidelines into ~500 token passages with metadata (source, country, condition)
- Inject top-K retrieved passages into diagnosis/treatment prompts
- Add source citations to the response output

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 3. Confidence-Based Routing

**Priority:** High  
**Effort:** Low  
**Affected Components:** `chat_engine.py`, `graph.py`

### Description

Replace the hard-coded `MAX_FOLLOWUP_QUESTIONS = 2` cutoff with dynamic confidence scoring. The LLM should output a confidence score after each exchange, and the system should proceed to diagnosis only when confidence ≥ 0.7 or max iterations reached.

### Rationale

- Aligns with SRS requirement FR-FOLLOWUP-003 (confidence ≥ 0.7 threshold)
- Simple cases resolve faster (fewer unnecessary questions)
- Complex cases get adequate information gathering

### Implementation Notes

- Add `confidence` field to the follow-up prompt's expected JSON output
- Route to diagnosis when `confidence >= settings.confidence_threshold`
- Keep max iterations as a safety cap (currently 2)
- Log confidence progression for observability

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 4. Structured Symptom Timeline

**Priority:** High  
**Effort:** Medium  
**Affected Components:** `ner_service.py`, `GraphState`, prompt templates

### Description

Enhance NER output to capture temporal relationships between symptoms — onset, progression, and ordering — rather than a single flat duration string.

### Rationale

- Temporal patterns are critical for differential diagnosis (e.g., migraine vs. stroke)
- Enables "symptom started X days ago, worsened Y days ago" reasoning
- Improves LLM diagnostic accuracy with structured temporal data

### Implementation Notes

- Extend `NERResult` to include a list of `SymptomEvent(symptom, onset, progression)`
- Use regex + NER to extract relative time expressions
- Pass structured timeline to diagnosis prompt instead of flat `duration` string
- Fallback to current behavior if timeline extraction fails

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 5. Suggested Tests with Reasoning

**Priority:** Medium  
**Effort:** Low  
**Affected Components:** `diagnosis_engine.py`, response models

### Description

Enhance test recommendations to include reasoning for each suggested test, explaining what it would confirm or rule out.

### Rationale

- Makes output actionable for clinicians
- Supports clinical decision-making transparency
- Aligns with explainability goals

### Implementation Notes

- Update diagnosis prompt to request `{"test": "name", "reasoning": "why"}` format
- Update `DiagnoseResponse` model to include structured test objects
- Surface in frontend as expandable test cards

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 6. Drug Interaction Checking

**Priority:** Medium  
**Effort:** Medium  
**Affected Components:** `compliance_engine.py`, new interaction database

### Description

Check suggested treatments against the patient's existing medications (inferred from `known_conditions`) for potential drug interactions.

### Rationale

- Critical patient safety enhancement
- Complements existing allergy filtering and restricted drug checks
- Reduces risk of harmful treatment suggestions

### Implementation Notes

- Source a basic interaction dataset (e.g., DrugBank open data, or curated JSON)
- Map common conditions to typical medications
- Add `check_interactions(treatments, known_conditions)` to compliance pipeline
- Flag interactions with severity level (minor/moderate/severe)
- Severe interactions → remove from suggestions; moderate → warn

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 7. Severity Triage / Urgency Score

**Priority:** Medium  
**Effort:** Low  
**Affected Components:** `compliance_engine.py`, response models

### Description

Add a 1-5 urgency score to the output based on symptom severity, patient risk factors, and red flag presence. Goes beyond binary red flag detection.

### Rationale

- Helps clinicians prioritize cases
- "Chest pain + diabetes + age 60" should score higher than "mild headache for 1 day"
- Enables future queue/triage features

### Implementation Notes

- Score based on: red flag count, patient age, comorbidity count, symptom severity
- Simple weighted formula (no LLM needed)
- Add `urgency_score: int` to response model
- Include brief justification string

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 8. Conversation Export / SOAP Summary

**Priority:** Medium  
**Effort:** Medium  
**Affected Components:** New endpoint, `llm_service.py`

### Description

Add a `POST /conversations/{id}/complete` endpoint that generates a structured clinical summary in SOAP note format (Subjective, Objective, Assessment, Plan) from the full conversation.

### Rationale

- Provides a portable, EHR-compatible output
- Useful for documentation and handoff between clinicians
- Prepares for future EHR integration

### Implementation Notes

- Gather full message history for the conversation
- Send to LLM with SOAP formatting prompt
- Mark conversation status as "completed"
- Store summary in a new `summary` column or related table
- Return as structured JSON and optionally as plain text

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 9. Streaming Responses

**Priority:** Medium  
**Effort:** Medium  
**Affected Components:** `llm_service.py`, `conversations.py`, frontend

### Description

Add Server-Sent Events (SSE) or WebSocket support for streaming LLM responses token-by-token to the frontend.

### Rationale

- Diagnosis step involves multiple LLM calls; total latency can exceed 5s
- Streaming provides immediate feedback and perceived performance improvement
- Better UX for longer clinical assessments

### Implementation Notes

- Add `StreamingResponse` endpoint using FastAPI's SSE support
- Modify Groq API call to use `stream=True`
- Frontend: consume SSE stream and render tokens incrementally
- Fallback to non-streaming for structured JSON responses (diagnosis step)

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 10. Multi-language Symptom Input

**Priority:** Medium  
**Effort:** Medium  
**Affected Components:** New `translation_service.py`, `ner_service.py`

### Description

Support symptom input in Hindi and other regional languages by adding a translation layer before NER processing.

### Rationale

- Many Indian patients describe symptoms in local languages
- Broadens system usability without changing core pipeline
- Country field already available for routing

### Implementation Notes

- Use Groq/LLM for translation (cheapest approach) or a dedicated model
- Detect language before NER; translate to English if non-English
- Store original language input alongside translated version
- Add `detected_language` to message metadata

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 11. Audit Trail / Explainability

**Priority:** Medium  
**Effort:** Low  
**Affected Components:** `llm_service.py`, `db.py`

### Description

Log the full prompt sent to the LLM and the raw response for every inference call. Support debugging, quality review, and future regulatory needs.

### Rationale

- SRS requires observability ("Log everything")
- Enables post-hoc review of AI decisions
- Required for any future clinical validation or certification

### Implementation Notes

- Create an `audit_logs` table: `id, conversation_id, step, prompt, raw_response, parsed_response, latency_ms, created_at`
- Wrap `query_llm` / `query_llm_json` to log automatically
- Add admin endpoint `GET /admin/audit-logs` with filtering
- Retention policy: keep for 90 days minimum

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## 12. Session Persistence

**Priority:** Low  
**Effort:** Low  
**Affected Components:** `session_store.py`, `db.py`

### Description

Replace the in-memory session store (used by `/diagnose` flow) with database-backed persistence so sessions survive server restarts.

### Rationale

- Current in-memory store loses all sessions on restart
- The chat-based flow already uses PostgreSQL; the `/diagnose` flow should too
- Enables horizontal scaling (multiple server instances)

### Implementation Notes

- Create a `sessions` table or reuse conversation model
- Serialize session state as JSON
- Add TTL-based cleanup (expire after 30 minutes)
- Minimal change: swap dict operations for DB queries in `session_store.py`

### Audit

| Field | Value |
|-------|-------|
| Implemented By | |
| Date Implemented | |
| Tests Added | |
| Reviewed By | |
| Notes | |

---

## Implementation Order (Recommended)

1. **Phase 1 — Quick Wins:** #3 (Confidence Routing), #7 (Urgency Score), #11 (Audit Trail), #12 (Session Persistence)
2. **Phase 2 — Clinical Quality:** #1 (Patient History), #4 (Symptom Timeline), #5 (Test Reasoning)
3. **Phase 3 — Safety:** #6 (Drug Interactions), #2 (RAG Guidelines)
4. **Phase 4 — UX:** #9 (Streaming), #10 (Multi-language), #8 (SOAP Export)

---

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-05-19 | 1.0 | System Design | Initial proposal |
