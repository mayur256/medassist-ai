# FR Audit & Tracking Document
# MedAssist-CDSS v1.0

**Last Updated:** 2026-05-06  
**Current Phase:** Phase 1 (Foundation) ✅  
**Overall Progress:** 5 / 22 FRs implemented

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented & verified |
| 🔧 | In progress |
| ⏳ | Pending |
| ❌ | Blocked |

---

## FR Implementation Status

### 4.1 Input Handling (FR-INPUT)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-INPUT-001 | Accept JSON with patient demographics and free-text symptoms | ✅ | `DiagnoseRequest` model + `POST /diagnose` |
| FR-INPUT-002 | Validate age as integer, country as India/US/UK | ✅ | Pydantic `Field(gt=0, lt=150)` + `Literal["India","US","UK"]` |
| FR-INPUT-003 | Gracefully reject malformed input with descriptive errors | ✅ | FastAPI returns 422 with validation details |

### 4.2 Symptom Extraction — NER (FR-NER)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-NER-001 | Extract symptoms, duration, severity from free text | ⏳ | Needs NER service |
| FR-NER-002 | Use `d4data/biomedical-ner-all` model | ⏳ | Model configured in settings |
| FR-NER-003 | Output normalized structured data | ⏳ | Needs response schema |

### 4.3 Follow-Up Question Engine (FR-FOLLOWUP)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-FOLLOWUP-001 | Generate max 3 follow-up questions per iteration | ⏳ | Threshold in config |
| FR-FOLLOWUP-002 | Questions must be medically relevant and non-repetitive | ⏳ | Needs LLM prompt design |
| FR-FOLLOWUP-003 | Stop when confidence ≥ 0.7 OR max 2 iterations | ⏳ | Thresholds in config |

### 4.4 Diagnosis Engine (FR-DIAG)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-DIAG-001 | Generate differential diagnoses only (never final) | ⏳ | Needs diagnosis service |
| FR-DIAG-002 | Each diagnosis: condition, confidence, reasoning | ⏳ | Needs response model |
| FR-DIAG-003 | Consider patient demographics and known conditions | ⏳ | Needs prompt context |

### 4.5 Treatment Suggestion Engine (FR-TREAT)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-TREAT-001 | Suggest non-prescriptive treatment options | ⏳ | Needs treatment service |
| FR-TREAT-002 | Respect patient allergies and known conditions | ⏳ | Needs allergy filtering |
| FR-TREAT-003 | MUST NOT generate prescriptions or dosage | ⏳ | Guardrail in prompt + post-processing |

### 4.6 Compliance Engine (FR-COMP)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-COMP-001 | Apply country-specific drug restriction rules | ⏳ | Needs compliance service |
| FR-COMP-002 | Remove restricted/banned substances | ⏳ | Needs drug restriction data |
| FR-COMP-003 | Always inject disclaimer in output | ✅ | Default value in `DiagnoseResponse.disclaimer` |

### 4.7 Red Flag Detection (FR-RED)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-RED-001 | Detect emergency symptoms | ⏳ | Needs red flag rules |
| FR-RED-002 | Flag urgent cases for immediate escalation | ⏳ | Needs escalation logic |

### 4.8 Output Format (FR-OUT)

| FR ID | Requirement | Status | Notes |
|-------|-------------|--------|-------|
| FR-OUT-001 | Return structured JSON (follow_up_questions, differential_diagnosis, suggested_tests, treatment_options, red_flags, disclaimer) | ✅ | `DiagnoseResponse` model with all fields |

---

## Phase Progress

| Phase | Description | Status | Steps |
|-------|-------------|--------|-------|
| Phase 1 | Foundation | ✅ | Steps 3-5 complete |
| Phase 2 | AI Services | ⏳ | Steps 6-8 |
| Phase 3 | Clinical Logic | ⏳ | Steps 9-11 |
| Phase 4 | Orchestration & Testing | ⏳ | Steps 12-13 |

---

## Implementation Log

| Date | Action | FRs Affected |
|------|--------|--------------|
| 2026-05-05 | Project scaffolding: pyproject.toml, config, directory structure | — (infrastructure only) |
| 2026-05-06 | Core models (request.py, response.py), FastAPI app (main.py), API key auth, tests passing | FR-INPUT-001, FR-INPUT-002, FR-INPUT-003, FR-COMP-003, FR-OUT-001 |

---

## Next Up

**Phase 2, Step 6: NER Service**
- `app/services/ner_service.py` → FR-NER-001, FR-NER-002, FR-NER-003

**Phase 2, Step 7: LLM Service**
- `app/services/llm_service.py` → Foundation for FR-FOLLOWUP, FR-DIAG, FR-TREAT

**Phase 2, Step 8: Follow-up Engine**
- `app/services/followup_engine.py` → FR-FOLLOWUP-001, FR-FOLLOWUP-002, FR-FOLLOWUP-003
