"""Phase 2 tests: NER Service, LLM Service, Follow-up Engine."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ner_service import NERResult, _extract_duration_from_text, extract_entities
from app.services.llm_service import query_llm, query_llm_json
from app.services.followup_engine import generate_followup


# --- NER Service Tests ---

class TestNERDurationRegex:
    def test_extracts_days(self):
        assert _extract_duration_from_text("pain for 3 days") == "3 days"

    def test_extracts_weeks(self):
        assert _extract_duration_from_text("cough lasting 2 weeks") == "2 weeks"

    def test_extracts_hours(self):
        assert _extract_duration_from_text("started 6 hours ago") == "6 hours"

    def test_no_duration(self):
        assert _extract_duration_from_text("I have a headache") is None


class TestNERService:
    @patch("app.services.ner_service._get_pipeline")
    def test_extract_symptoms(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(return_value=[
            {"entity_group": "Sign_symptom", "word": "chest pain", "score": 0.95},
            {"entity_group": "Sign_symptom", "word": "shortness of breath", "score": 0.90},
            {"entity_group": "Duration", "word": "2 days", "score": 0.85},
        ])
        result = extract_entities("chest pain and shortness of breath for 2 days")
        assert "chest pain" in result.symptoms
        assert "shortness of breath" in result.symptoms
        assert result.duration == "2 days"

    @patch("app.services.ner_service._get_pipeline")
    def test_extract_severity(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(return_value=[
            {"entity_group": "Sign_symptom", "word": "headache", "score": 0.9},
            {"entity_group": "Severity", "word": "severe", "score": 0.8},
        ])
        result = extract_entities("severe headache")
        assert result.severity == "severe"
        assert "headache" in result.symptoms

    @patch("app.services.ner_service._get_pipeline")
    def test_deduplicates_symptoms(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(return_value=[
            {"entity_group": "Sign_symptom", "word": "headache", "score": 0.9},
            {"entity_group": "Sign_symptom", "word": "Headache", "score": 0.8},
        ])
        result = extract_entities("headache headache")
        assert len(result.symptoms) == 1

    @patch("app.services.ner_service._get_pipeline")
    def test_duration_regex_fallback(self, mock_pipeline):
        mock_pipeline.return_value = MagicMock(return_value=[
            {"entity_group": "Sign_symptom", "word": "fever", "score": 0.9},
        ])
        result = extract_entities("fever for 5 days")
        assert result.duration == "5 days"


# --- LLM Service Tests ---

class TestLLMService:
    @pytest.mark.asyncio
    @patch("app.services.llm_service._query_groq", new_callable=AsyncMock)
    async def test_query_llm_success(self, mock_groq):
        mock_groq.return_value = "Hello world"

        result = await query_llm("test prompt")
        assert result == "Hello world"

    @pytest.mark.asyncio
    @patch("app.services.llm_service._query_groq", new_callable=AsyncMock)
    async def test_query_llm_handles_exception(self, mock_groq):
        mock_groq.return_value = ""

        result = await query_llm("test prompt")
        assert result == ""
        assert result == ""

    @pytest.mark.asyncio
    @patch("app.services.llm_service.query_llm")
    async def test_query_llm_json_parses(self, mock_query):
        mock_query.return_value = '```json\n{"key": "value"}\n```'
        result = await query_llm_json("test")
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    @patch("app.services.llm_service.query_llm")
    async def test_query_llm_json_handles_invalid(self, mock_query):
        mock_query.return_value = "not json at all"
        result = await query_llm_json("test")
        assert result is None


# --- Follow-up Engine Tests ---

class TestFollowupEngine:
    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json")
    async def test_generates_questions(self, mock_llm):
        mock_llm.return_value = {
            "questions": ["When did it start?", "Is it constant?"],
            "confidence": 0.4,
        }
        result = await generate_followup(
            symptoms=["chest pain"],
            patient={"age": 45, "gender": "male", "country": "India"},
        )
        assert len(result["questions"]) == 2
        assert result["confidence"] == 0.4
        assert result["should_stop"] is False

    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json")
    async def test_stops_at_high_confidence(self, mock_llm):
        mock_llm.return_value = {"questions": ["Any more?"], "confidence": 0.8}
        result = await generate_followup(
            symptoms=["headache", "fever"],
            patient={"age": 30, "gender": "female", "country": "UK"},
        )
        assert result["should_stop"] is True

    @pytest.mark.asyncio
    async def test_stops_at_max_iterations(self):
        result = await generate_followup(
            symptoms=["cough"],
            patient={"age": 60, "gender": "male", "country": "US"},
            iteration=2,
        )
        assert result["should_stop"] is True
        assert result["questions"] == []

    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json")
    async def test_limits_to_max_questions(self, mock_llm):
        mock_llm.return_value = {
            "questions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"],
            "confidence": 0.3,
        }
        result = await generate_followup(
            symptoms=["pain"],
            patient={"age": 25, "gender": "other", "country": "India"},
        )
        assert len(result["questions"]) <= 3

    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json")
    async def test_handles_llm_failure(self, mock_llm):
        mock_llm.return_value = None
        result = await generate_followup(
            symptoms=["dizziness"],
            patient={"age": 70, "gender": "female", "country": "US"},
        )
        assert result["should_stop"] is True
        assert result["questions"] == []
