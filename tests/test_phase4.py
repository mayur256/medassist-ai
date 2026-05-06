"""Phase 4 tests: LangGraph Orchestrator integration tests with mocked LLM/NER."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.models.request import DiagnoseRequest, PatientInfo
from app.models.response import DISCLAIMER
from app.orchestrator.graph import run_pipeline

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
    """Mock NER that returns predictable results."""
    from app.services.ner_service import NERResult

    return NERResult(
        symptoms=["chest pain", "shortness of breath"],
        duration="2 days",
        severity=None,
    )


# --- Orchestrator Unit Tests ---


class TestOrchestrator:
    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_full_pipeline(self, mock_treat, mock_diag, mock_followup, mock_ner):
        mock_followup.return_value = {
            "questions": ["Is the pain worse with exertion?"],
            "confidence": 0.8,
        }
        mock_diag.return_value = {
            "diagnoses": [
                {"condition": "Angina", "confidence": 0.75, "reasoning": "Chest pain with exertion in 45M with HTN"},
                {"condition": "GERD", "confidence": 0.4, "reasoning": "Can mimic cardiac pain"},
            ]
        }
        mock_treat.return_value = {
            "treatments": ["Antianginal therapy", "Lifestyle modification", "Stress test referral"]
        }

        request = DiagnoseRequest(**VALID_PAYLOAD)
        response = await run_pipeline(request)

        assert response.disclaimer == DISCLAIMER
        assert len(response.differential_diagnosis) == 2
        assert response.differential_diagnosis[0].condition == "Angina"
        assert response.differential_diagnosis[0].confidence == 0.75
        assert len(response.treatment_options) == 3
        assert "Is the pain worse with exertion?" in response.follow_up_questions

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_pipeline_filters_allergies(self, mock_treat, mock_diag, mock_followup, mock_ner):
        mock_followup.return_value = {"questions": [], "confidence": 0.9}
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Infection", "confidence": 0.7, "reasoning": "Symptoms suggest infection"}]
        }
        mock_treat.return_value = {
            "treatments": ["Penicillin antibiotics", "Rest and hydration", "Amoxicillin"]
        }

        request = DiagnoseRequest(**VALID_PAYLOAD)
        response = await run_pipeline(request)

        # Penicillin and Amoxicillin (contains penicillin) should be filtered
        for t in response.treatment_options:
            assert "penicillin" not in t.lower()

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities")
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_pipeline_detects_red_flags(self, mock_treat, mock_diag, mock_followup, mock_ner):
        from app.services.ner_service import NERResult

        mock_ner.return_value = NERResult(symptoms=["chest pain", "difficulty breathing"], duration=None, severity=None)
        mock_followup.return_value = {"questions": [], "confidence": 0.9}
        mock_diag.return_value = {"diagnoses": []}
        mock_treat.return_value = {"treatments": []}

        request = DiagnoseRequest(**VALID_PAYLOAD)
        response = await run_pipeline(request)

        assert "chest pain" in response.red_flags
        assert "difficulty breathing" in response.red_flags

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_pipeline_llm_failure_graceful(self, mock_treat, mock_diag, mock_followup, mock_ner):
        """Pipeline should return valid response even when LLM returns None."""
        mock_followup.return_value = None
        mock_diag.return_value = None
        mock_treat.return_value = None

        request = DiagnoseRequest(**VALID_PAYLOAD)
        response = await run_pipeline(request)

        assert response.disclaimer == DISCLAIMER
        assert response.differential_diagnosis == []
        assert response.treatment_options == []

    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_pipeline_restricted_drugs_filtered(self, mock_treat, mock_diag, mock_followup, mock_ner):
        mock_followup.return_value = {"questions": [], "confidence": 0.9}
        mock_diag.return_value = {"diagnoses": [{"condition": "Pain", "confidence": 0.6, "reasoning": "test"}]}
        mock_treat.return_value = {
            "treatments": ["Nimesulide (pediatric) use", "Paracetamol", "Rest"]
        }

        request = DiagnoseRequest(**VALID_PAYLOAD)
        response = await run_pipeline(request)

        # Nimesulide (pediatric) is restricted in India
        for t in response.treatment_options:
            assert "nimesulide" not in t.lower()


# --- API Integration Tests ---


class TestDiagnoseEndpoint:
    @pytest.mark.asyncio
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_endpoint_returns_full_response(self, mock_treat, mock_diag, mock_followup, mock_ner):
        mock_followup.return_value = {"questions": ["Any fever?"], "confidence": 0.8}
        mock_diag.return_value = {
            "diagnoses": [{"condition": "ACS", "confidence": 0.8, "reasoning": "High risk"}]
        }
        mock_treat.return_value = {"treatments": ["Aspirin", "ECG referral"]}

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["disclaimer"] == DISCLAIMER
        assert len(data["differential_diagnosis"]) == 1
        assert data["differential_diagnosis"][0]["condition"] == "ACS"
        assert "Any fever?" in data["follow_up_questions"]
        assert "Aspirin" in data["treatment_options"]
        assert "chest pain" in data["red_flags"]

    @pytest.mark.asyncio
    async def test_endpoint_rejects_invalid_input(self):
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/diagnose",
                json={"patient": {"age": -5, "gender": "male", "country": "India"}, "symptoms": "x"},
                headers=HEADERS,
            )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_endpoint_requires_auth(self):
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers={"X-API-Key": "wrong"})
        assert r.status_code == 401
