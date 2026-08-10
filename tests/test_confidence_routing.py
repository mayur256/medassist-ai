"""Tests for #3 Confidence-Based Routing enhancement."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings

settings.api_key = "test-key"
HEADERS = {"X-API-Key": "test-key"}

VALID_PAYLOAD = {
    "patient": {
        "age": 45,
        "gender": "male",
        "country": "India",
        "known_conditions": ["hypertension"],
        "allergies": ["penicillin"],
    },
    "symptoms": "chest pain for 2 days with shortness of breath",
}


def _mock_ner(text):
    from app.services.ner_service import NERResult
    return NERResult(symptoms=["chest pain", "shortness of breath"], duration="2 days", severity=None)


class TestConfidenceRouting:
    """Test that confidence >= threshold triggers immediate diagnosis."""

    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_high_confidence_skips_followup(self, mock_treat, mock_diag, mock_followup, mock_ner, mock_diag_rag, mock_treat_rag):
        """When LLM reports confidence >= 0.7, system skips follow-up and diagnoses immediately."""
        mock_followup.return_value = {
            "questions": [],
            "confidence": 0.85,
        }
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "Classic presentation"}]
        }
        mock_treat.return_value = {"treatments": ["Nitroglycerin", "Aspirin"]}

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert data["confidence"] >= settings.confidence_threshold
        assert len(data["differential_diagnosis"]) >= 1
        assert data["session_id"] is None  # No session needed

    @pytest.mark.asyncio
    @patch("app.services.session_store.save_session", new_callable=AsyncMock)
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_low_confidence_returns_followup(self, mock_followup, mock_ner, mock_save):
        """When confidence < 0.7, system returns follow-up questions."""
        mock_followup.return_value = {
            "questions": ["Is the pain worse with exertion?", "Any radiating pain?"],
            "confidence": 0.3,
        }

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "awaiting_followup"
        assert data["confidence"] == 0.3
        assert len(data["follow_up_questions"]) == 2
        assert data["session_id"] is not None

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_confidence_at_threshold_triggers_diagnosis(self, mock_followup, mock_ner):
        """Confidence exactly at 0.7 should trigger diagnosis."""
        mock_followup.return_value = {
            "questions": [],
            "confidence": 0.7,
        }

        from app.main import app
        from app.orchestrator.graph import should_diagnose

        # Test the routing function directly
        state = {
            "confidence": 0.7,
            "iteration": 0,
        }
        assert should_diagnose(state) == "diagnosis"

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_confidence_below_threshold_no_diagnosis(self, mock_followup, mock_ner):
        """Confidence below 0.7 should NOT trigger diagnosis."""
        mock_followup.return_value = {
            "questions": ["Any pain?"],
            "confidence": 0.69,
        }

        from app.orchestrator.graph import should_diagnose

        state = {
            "confidence": 0.69,
            "iteration": 0,
        }
        # Below threshold and below max iterations → END (return follow-up questions)
        from langgraph.graph import END
        assert should_diagnose(state) == END


class TestMaxIterationSafetyCap:
    """Test that max iterations still serves as safety cap."""

    @pytest.mark.asyncio
    async def test_max_iterations_forces_diagnosis(self):
        """Even with low confidence, max iterations triggers diagnosis."""
        from app.orchestrator.graph import should_diagnose

        state = {
            "confidence": 0.2,
            "iteration": settings.max_followup_iterations,  # At max
        }
        assert should_diagnose(state) == "diagnosis"

    @pytest.mark.asyncio
    async def test_below_max_iterations_with_low_confidence(self):
        """Below max iterations with low confidence → still needs follow-up."""
        from langgraph.graph import END
        from app.orchestrator.graph import should_diagnose

        state = {
            "confidence": 0.2,
            "iteration": 0,
        }
        assert should_diagnose(state) == END


class TestFollowupEngineConfidence:
    """Test the followup engine's confidence output."""

    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_returns_confidence_score(self, mock_llm):
        """Follow-up engine must return confidence in its response."""
        mock_llm.return_value = {
            "questions": ["Any fever?"],
            "confidence": 0.55,
        }
        from app.services.followup_engine import generate_followup

        result = await generate_followup(
            symptoms=["headache"],
            patient={"age": 30, "gender": "female", "country": "India", "known_conditions": [], "allergies": []},
            previous_questions=[],
            iteration=0,
        )
        assert result["confidence"] == 0.55
        assert result["should_stop"] is False
        assert result["questions"] == ["Any fever?"]

    @pytest.mark.asyncio
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_high_confidence_sets_should_stop(self, mock_llm):
        """When confidence >= threshold, should_stop is True."""
        mock_llm.return_value = {
            "questions": [],
            "confidence": 0.9,
        }
        from app.services.followup_engine import generate_followup

        result = await generate_followup(
            symptoms=["severe chest pain", "sweating", "nausea"],
            patient={"age": 60, "gender": "male", "country": "US", "known_conditions": ["diabetes"], "allergies": []},
            previous_questions=["Any radiation?"],
            iteration=0,
        )
        assert result["confidence"] == 0.9
        assert result["should_stop"] is True

    @pytest.mark.asyncio
    async def test_max_iteration_returns_full_confidence(self):
        """At max iterations, confidence is forced to 1.0."""
        from app.services.followup_engine import generate_followup

        result = await generate_followup(
            symptoms=["cough"],
            patient={"age": 25, "gender": "female", "country": "UK", "known_conditions": [], "allergies": []},
            previous_questions=[],
            iteration=settings.max_followup_iterations,
        )
        assert result["confidence"] == 1.0
        assert result["should_stop"] is True
        assert result["questions"] == []


class TestChatEngineConfidenceRouting:
    """Test confidence-based routing in the chat engine."""

    @pytest.mark.asyncio
    @patch("app.services.chat_engine.get_patient_history_summary", new_callable=AsyncMock, return_value="")
    @patch("app.services.chat_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.chat_engine.extract_entities")
    async def test_low_confidence_asks_followup(self, mock_ner, mock_llm, mock_history):
        """Chat engine with low confidence should ask follow-up."""
        from app.services.ner_service import NERResult
        mock_ner.return_value = NERResult(symptoms=["headache"], duration=None, severity=None)
        mock_llm.return_value = {"content": "How long have you had the headache?", "confidence": 0.3}

        from app.services.chat_engine import process_chat_message
        from unittest.mock import MagicMock

        patient = MagicMock()
        patient.age = 30
        patient.gender = "female"
        patient.country = "India"
        patient.known_conditions = []
        patient.allergies = []

        msg = MagicMock()
        msg.role = "patient"
        msg.content = "I have a headache"

        result = await process_chat_message(patient, [msg])
        assert result["metadata"]["action"] == "followup"
        assert result["metadata"]["confidence"] == 0.3

    @pytest.mark.asyncio
    @patch("app.services.chat_engine.get_patient_history_summary", new_callable=AsyncMock, return_value="")
    @patch("app.services.chat_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.chat_engine.extract_entities")
    async def test_high_confidence_triggers_diagnosis(self, mock_ner, mock_llm, mock_history):
        """Chat engine with high confidence should proceed to diagnosis."""
        from app.services.ner_service import NERResult
        mock_ner.return_value = NERResult(symptoms=["chest pain"], duration="2 days", severity="severe")

        # First call: followup returns high confidence
        # Second call: diagnosis
        mock_llm.side_effect = [
            {"content": "Any associated symptoms?", "confidence": 0.85},
            {"content": "Assessment complete", "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "test"}], "treatments": ["Rest"], "suggested_tests": ["ECG"]},
        ]

        from app.services.chat_engine import process_chat_message
        from unittest.mock import MagicMock

        patient = MagicMock()
        patient.age = 55
        patient.gender = "male"
        patient.country = "India"
        patient.known_conditions = ["diabetes"]
        patient.allergies = []

        msg = MagicMock()
        msg.role = "patient"
        msg.content = "I have severe chest pain for 2 days"

        result = await process_chat_message(patient, [msg])
        assert result["metadata"]["action"] == "diagnose"
        assert result["metadata"]["confidence"] == 1.0

    @pytest.mark.asyncio
    @patch("app.services.chat_engine.get_patient_history_summary", new_callable=AsyncMock, return_value="")
    @patch("app.services.chat_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.chat_engine.extract_entities")
    async def test_max_questions_forces_diagnosis(self, mock_ner, mock_llm, mock_history):
        """After max questions asked, chat engine forces diagnosis."""
        from app.services.ner_service import NERResult
        mock_ner.return_value = NERResult(symptoms=["cough"], duration=None, severity=None)
        mock_llm.return_value = {"content": "Assessment", "diagnoses": [], "treatments": [], "suggested_tests": []}

        from app.services.chat_engine import process_chat_message
        from unittest.mock import MagicMock

        patient = MagicMock()
        patient.age = 40
        patient.gender = "male"
        patient.country = "UK"
        patient.known_conditions = []
        patient.allergies = []

        # Build messages with enough assistant questions to exceed max
        messages = []
        for i in range(settings.max_followup_iterations + 1):
            pmsg = MagicMock()
            pmsg.role = "patient"
            pmsg.content = f"Answer {i}"
            messages.append(pmsg)

            amsg = MagicMock()
            amsg.role = "assistant"
            amsg.content = f"Question {i}?"
            messages.append(amsg)

        # Final patient message
        last = MagicMock()
        last.role = "patient"
        last.content = "I still have a cough"
        messages.append(last)

        result = await process_chat_message(patient, messages)
        assert result["metadata"]["action"] == "diagnose"


class TestResponseModelConfidence:
    """Test that the response model includes confidence."""

    def test_response_has_confidence_field(self):
        from app.models.response import DiagnoseResponse
        resp = DiagnoseResponse(status="awaiting_followup", confidence=0.5)
        assert resp.confidence == 0.5

    def test_response_default_confidence(self):
        from app.models.response import DiagnoseResponse
        resp = DiagnoseResponse()
        assert resp.confidence == 0.0
