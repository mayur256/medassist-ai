"""Tests for #9 Streaming Responses enhancement."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.streaming_service import (
    _format_sse_event,
    stream_diagnosis,
)
from app.models.request import DiagnoseRequest, PatientInfo


def _make_request(
    symptoms="chest pain for 2 days",
    age=45,
    gender="male",
    country="US",
    conditions=None,
    allergies=None,
):
    """Create a DiagnoseRequest for testing."""
    return DiagnoseRequest(
        symptoms=symptoms,
        patient=PatientInfo(
            age=age,
            gender=gender,
            country=country,
            known_conditions=conditions or ["diabetes"],
            allergies=allergies or ["penicillin"],
        ),
    )


class TestSSEFormatting:
    """Test SSE event formatting."""

    def test_basic_event(self):
        """Format basic SSE event."""
        result = _format_sse_event("stage_start", {"stage": "ner", "message": "Starting"})
        assert result.startswith("event: stage_start\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_event_data_is_json(self):
        """Event data is valid JSON."""
        result = _format_sse_event("test", {"key": "value", "num": 42})
        lines = result.strip().split("\n")
        data_line = next(l for l in lines if l.startswith("data: "))
        json_str = data_line[6:]
        parsed = json.loads(json_str)
        assert parsed == {"key": "value", "num": 42}

    def test_event_types(self):
        """All expected event types format correctly."""
        events = ["stage_start", "stage_complete", "token", "result", "error"]
        for event_type in events:
            result = _format_sse_event(event_type, {"msg": "test"})
            assert f"event: {event_type}" in result


class TestStreamDiagnosis:
    """Test the streaming diagnosis pipeline."""

    @pytest.mark.asyncio
    @patch("app.services.streaming_service.translate_to_english")
    @patch("app.services.streaming_service._stream_groq_tokens")
    async def test_emits_stage_events(self, mock_stream, mock_translate):
        """Stream emits stage_start and stage_complete events."""
        mock_translate.return_value = {
            "translated_text": "chest pain for 2 days",
            "original_text": "chest pain for 2 days",
            "detected_language": "English",
            "was_translated": False,
        }

        # Mock LLM streaming to return a valid JSON response
        async def mock_token_generator(prompt):
            tokens = ['{"diagnoses": [{"condition": "ACS", "confidence": 0.8, ',
                      '"reasoning": "chest pain"}], "suggested_tests": ',
                      '[{"test": "ECG", "reasoning": "check"}], ',
                      '"treatments": ["Aspirin"]}']
            for t in tokens:
                yield t

        mock_stream.side_effect = mock_token_generator

        request = _make_request()
        events = []
        async for event_str in stream_diagnosis(request):
            events.append(event_str)

        # Parse events
        parsed_events = []
        for ev in events:
            lines = ev.strip().split("\n")
            event_type = None
            event_data = None
            for line in lines:
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    event_data = json.loads(line[6:])
            if event_type:
                parsed_events.append((event_type, event_data))

        # Check required events
        event_types = [e[0] for e in parsed_events]
        assert "stage_start" in event_types
        assert "stage_complete" in event_types
        assert "result" in event_types

    @pytest.mark.asyncio
    @patch("app.services.streaming_service.translate_to_english")
    @patch("app.services.streaming_service._stream_groq_tokens")
    async def test_emits_tokens(self, mock_stream, mock_translate):
        """Stream emits individual tokens."""
        mock_translate.return_value = {
            "translated_text": "headache",
            "original_text": "headache",
            "detected_language": "English",
            "was_translated": False,
        }

        async def mock_token_generator(prompt):
            yield '{"diagnoses": []'
            yield ', "suggested_tests": []'
            yield ', "treatments": []}'

        mock_stream.side_effect = mock_token_generator

        request = _make_request(symptoms="headache")
        token_events = []
        async for event_str in stream_diagnosis(request):
            if "event: token" in event_str:
                token_events.append(event_str)

        assert len(token_events) >= 1

    @pytest.mark.asyncio
    @patch("app.services.streaming_service.translate_to_english")
    @patch("app.services.streaming_service._stream_groq_tokens")
    async def test_final_result_has_required_fields(self, mock_stream, mock_translate):
        """Final result event contains all required fields."""
        mock_translate.return_value = {
            "translated_text": "chest pain",
            "original_text": "chest pain",
            "detected_language": "English",
            "was_translated": False,
        }

        async def mock_token_generator(prompt):
            yield '{"diagnoses": [{"condition": "ACS", "confidence": 0.8, "reasoning": "test"}], '
            yield '"suggested_tests": [{"test": "ECG", "reasoning": "check"}], '
            yield '"treatments": ["Rest"]}'

        mock_stream.side_effect = mock_token_generator

        request = _make_request()
        result_event = None
        async for event_str in stream_diagnosis(request):
            if "event: result" in event_str:
                lines = event_str.strip().split("\n")
                for line in lines:
                    if line.startswith("data: "):
                        result_event = json.loads(line[6:])

        assert result_event is not None
        response = result_event["response"]
        assert "status" in response
        assert "differential_diagnosis" in response
        assert "treatment_options" in response
        assert "red_flags" in response
        assert "urgency_score" in response
        assert "drug_interactions" in response
        assert "disclaimer" in response
        assert response["status"] == "complete"

    @pytest.mark.asyncio
    @patch("app.services.streaming_service.translate_to_english")
    @patch("app.services.streaming_service._stream_groq_tokens")
    async def test_handles_llm_error(self, mock_stream, mock_translate):
        """Stream handles LLM errors gracefully."""
        mock_translate.return_value = {
            "translated_text": "pain",
            "original_text": "pain",
            "detected_language": "English",
            "was_translated": False,
        }

        async def mock_error_generator(prompt):
            yield ""  # Empty response

        mock_stream.side_effect = mock_error_generator

        request = _make_request(symptoms="pain")
        events = []
        async for event_str in stream_diagnosis(request):
            events.append(event_str)

        # Should still emit a result (with empty diagnoses)
        all_text = "".join(events)
        assert "event: result" in all_text

    @pytest.mark.asyncio
    @patch("app.services.streaming_service.translate_to_english")
    @patch("app.services.streaming_service._stream_groq_tokens")
    async def test_includes_elapsed_time(self, mock_stream, mock_translate):
        """Final result includes elapsed_ms."""
        mock_translate.return_value = {
            "translated_text": "cough",
            "original_text": "cough",
            "detected_language": "English",
            "was_translated": False,
        }

        async def mock_token_generator(prompt):
            yield '{"diagnoses": [], "suggested_tests": [], "treatments": []}'

        mock_stream.side_effect = mock_token_generator

        request = _make_request(symptoms="cough")
        async for event_str in stream_diagnosis(request):
            if "event: result" in event_str:
                lines = event_str.strip().split("\n")
                for line in lines:
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        assert "elapsed_ms" in data["response"]
                        assert data["response"]["elapsed_ms"] >= 0
