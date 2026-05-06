# Project: MedAssist-CDSS

## Overview
AI-powered Clinical Decision Support System (CDSS) that assists healthcare professionals with differential diagnoses, follow-up questions, and guideline-based treatment suggestions.

## Tech Stack
- Language: Python
- Framework: FastAPI
- Orchestration: LangGraph
- LLM: HuggingFace (Mistral-7B-Instruct / Zephyr-7b-beta)
- NER: d4data/biomedical-ner-all
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- RAG: vector-based retrieval for clinical guidelines

## Architecture
```
FastAPI Backend
├── LangGraph Orchestrator
├── LLM Service (HuggingFace)
├── NER Service
├── RAG Service
└── Compliance Engine
```

Flow: Input → NER → Follow-up Loop → Diagnosis → Treatment → Compliance → Output

## API
- Single endpoint: `POST /diagnose`
- Input: patient demographics + symptoms (text)
- Output: structured JSON (follow_up_questions, differential_diagnosis, suggested_tests, treatment_options, red_flags, disclaimer)

## Critical Rules
- NEVER provide final diagnosis, legally valid prescriptions, or dosage
- ALWAYS include disclaimer: "This is AI-assisted output and must be verified by a licensed medical professional."
- NOT a medical device, NOT clinically validated
- No patient data storage
- Country-aware compliance filtering (India, US, UK)

## Coding Conventions
- Python with type hints
- FastAPI for API layer
- Pydantic models for request/response validation
- Structured JSON responses
- Performance target: ≤ 5 sec response time
- Log all operations for observability
- Handle malformed input gracefully

## Project Status
- Greenfield project (Phase 1 - Setup)
- Only README, .gitignore, LICENSE exist so far
- No source code written yet

## Key Functional Requirements
- NER extracts symptoms, duration, severity
- Max 3 follow-up questions per iteration, max 2 iterations
- Stop follow-up when confidence ≥ 0.7
- Differential diagnosis with condition, confidence, reasoning
- Treatment suggestions respect allergies and known conditions
- Red flag detection for emergency symptoms
- Country-specific compliance rules filter restricted drugs
