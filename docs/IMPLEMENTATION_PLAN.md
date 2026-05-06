# Implementation Plan
# MedAssist-CDSS v1.0

## Project Structure

```
medassist-ai/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings and configuration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py           # Input Pydantic models
│   │   └── response.py          # Output Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ner_service.py       # Biomedical NER extraction
│   │   ├── llm_service.py       # HuggingFace LLM integration
│   │   ├── followup_engine.py   # Follow-up question generation
│   │   ├── diagnosis_engine.py  # Differential diagnosis
│   │   ├── treatment_engine.py  # Treatment suggestions
│   │   └── compliance_engine.py # Country rules + disclaimer
│   └── orchestrator/
│       ├── __init__.py
│       └── graph.py             # LangGraph workflow
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_ner_service.py
│   ├── test_diagnosis_engine.py
│   └── test_api.py
├── docs/
│   ├── PRD.md
│   └── IMPLEMENTATION_PLAN.md
├── pyproject.toml
├── KIRO.md
└── README.md
```

---

## Phase 1: Foundation (Tasks 3-5)

### Step 3: Project Setup
- Create `pyproject.toml` with pinned dependencies
- Create directory structure
- Create `app/config.py` with environment-based settings

**Dependencies:**
- fastapi
- uvicorn
- pydantic
- transformers
- torch
- langgraph
- langchain-core
- sentence-transformers
- python-dotenv
- structlog (logging)
- httpx (async HTTP)
- pytest (dev)

### Step 4: Core Models
- `app/models/request.py` — PatientInfo, DiagnoseRequest
- `app/models/response.py` — Diagnosis, DiagnoseResponse

### Step 5: FastAPI App
- `app/main.py` — App instance, CORS, health check, POST /diagnose route

---

## Phase 2: AI Services (Tasks 6-8)

### Step 6: NER Service
- Load `d4data/biomedical-ner-all` pipeline
- Extract symptoms, duration, severity from text
- Return normalized structured output

### Step 7: LLM Service
- HuggingFace Inference API integration
- Prompt templates for diagnosis, follow-up, treatment
- Fallback model support (Mistral → Zephyr)
- Response parsing

### Step 8: Follow-up Engine
- Generate max 3 questions per iteration
- Track iteration count (max 2)
- Confidence threshold check (≥ 0.7 → stop)

---

## Phase 3: Clinical Logic (Tasks 9-11)

### Step 9: Diagnosis Engine
- Generate differential diagnoses using LLM
- Structure output: condition, confidence, reasoning
- Consider patient context (age, gender, conditions)

### Step 10: Treatment Engine
- Generate treatment options via LLM
- Filter against patient allergies
- Ensure no dosage/prescription content

### Step 11: Compliance Engine
- Country-specific restricted drug lists
- Red flag symptom detection
- Disclaimer injection
- Output sanitization

---

## Phase 4: Orchestration & Testing (Tasks 12-13)

### Step 12: LangGraph Orchestrator
- Define state schema
- Create nodes: NER → Follow-up → Diagnosis → Treatment → Compliance
- Conditional edges for follow-up loop
- Wire into /diagnose endpoint

### Step 13: Tests
- Unit tests for each service (mocked LLM calls)
- Integration test for full pipeline
- Input validation tests
- Edge case tests (empty symptoms, invalid country)

---

## Implementation Order & Dependencies

```
[3] Project Setup
 └── [4] Core Models
      └── [5] FastAPI App
           ├── [6] NER Service
           ├── [7] LLM Service
           │    ├── [8] Follow-up Engine
           │    ├── [9] Diagnosis Engine
           │    └── [10] Treatment Engine
           └── [11] Compliance Engine
                └── [12] LangGraph Orchestrator
                     └── [13] Tests
```

---

## Key Design Decisions

1. **Stateless API** — No session management; each request is self-contained
2. **HuggingFace Inference API** — Avoids local GPU requirement for MVP
3. **LangGraph over raw chains** — Explicit flow control with conditional branching
4. **Pydantic strict validation** — Catch bad input at the boundary
5. **Structured logging** — Every service call logged with context
