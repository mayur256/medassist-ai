"""Tests for Enhancement #5: Suggested Tests with Reasoning."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.models.response import SuggestedTest
from app.services.diagnosis_engine import generate_diagnoses

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


# --- Unit Tests: SuggestedTest Model ---


class TestSuggestedTestModel:
    def test_valid_suggested_test(self):
        t = SuggestedTest(test="ECG", reasoning="Rule out cardiac ischemia")
        assert t.test == "ECG"
        assert t.reasoning == "Rule out cardiac ischemia"

    def test_empty_reasoning_allowed(self):
        t = SuggestedTest(test="CBC", reasoning="")
        assert t.test == "CBC"
        assert t.reasoning == ""


# --- Unit Tests: Diagnosis Engine returns structured tests ---


class TestDiagnosisEngineTests:
    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_returns_suggested_tests(self, mock_llm, mock_rag):
        mock_llm.return_value = {
            "diagnoses": [
                {"condition": "Angina", "confidence": 0.8, "reasoning": "Chest pain in 45M with HTN"},
            ],
            "suggested_tests": [
                {"test": "ECG", "reasoning": "Detect ST changes indicating ischemia"},
                {"test": "Troponin", "reasoning": "Rule out myocardial infarction"},
                {"test": "Chest X-ray", "reasoning": "Exclude pulmonary causes"},
            ],
        }
        result = await generate_diagnoses(
            symptoms=["chest pain", "shortness of breath"],
            patient={"age": 45, "gender": "male", "country": "India", "known_conditions": ["hypertension"]},
        )
        assert "suggested_tests" in result
        assert len(result["suggested_tests"]) == 3
        assert result["suggested_tests"][0]["test"] == "ECG"
        assert "ischemia" in result["suggested_tests"][0]["reasoning"]

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_max_5_tests(self, mock_llm, mock_rag):
        mock_llm.return_value = {
            "diagnoses": [{"condition": "X", "confidence": 0.5, "reasoning": ""}],
            "suggested_tests": [
                {"test": f"Test{i}", "reasoning": f"Reason {i}"} for i in range(8)
            ],
        }
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert len(result["suggested_tests"]) <= 5

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_handles_missing_tests_key(self, mock_llm, mock_rag):
        """LLM response with no suggested_tests key returns empty list."""
        mock_llm.return_value = {
            "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "Chest pain"}],
        }
        result = await generate_diagnoses(
            symptoms=["chest pain"],
            patient={"age": 45, "gender": "male", "country": "India"},
        )
        assert result["suggested_tests"] == []
        assert len(result["diagnoses"]) == 1

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_handles_malformed_test_entries(self, mock_llm, mock_rag):
        """Invalid test entries (missing 'test' key) are skipped."""
        mock_llm.return_value = {
            "diagnoses": [{"condition": "X", "confidence": 0.5, "reasoning": ""}],
            "suggested_tests": [
                {"test": "ECG", "reasoning": "Check heart"},
                {"reasoning": "Missing test key"},  # invalid - no 'test' key
                "just a string",  # invalid - not a dict
                {"test": "CBC", "reasoning": "Check blood counts"},
            ],
        }
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert len(result["suggested_tests"]) == 2
        assert result["suggested_tests"][0]["test"] == "ECG"
        assert result["suggested_tests"][1]["test"] == "CBC"

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_missing_reasoning_defaults_empty(self, mock_llm, mock_rag):
        """Test entry without reasoning gets empty string."""
        mock_llm.return_value = {
            "diagnoses": [{"condition": "X", "confidence": 0.5, "reasoning": ""}],
            "suggested_tests": [
                {"test": "ECG"},
            ],
        }
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert result["suggested_tests"][0]["reasoning"] == ""


# --- Integration Tests: Full API flow includes structured tests ---


def _mock_ner(text):
    from app.services.ner_service import NERResult

    return NERResult(symptoms=["chest pain", "shortness of breath"], duration="2 days", severity=None)


class TestSuggestedTestsAPI:
    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_high_confidence_includes_tests(self, mock_treat, mock_diag, mock_followup, mock_ner, mock_diag_rag, mock_treat_rag):
        """When diagnosis is returned immediately, suggested_tests are included."""
        mock_followup.return_value = {
            "questions": [],
            "confidence": 0.85,
        }
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "Classic presentation"}],
            "suggested_tests": [
                {"test": "ECG", "reasoning": "Detect ST-segment changes"},
                {"test": "Troponin I", "reasoning": "Rule out acute MI"},
            ],
        }
        mock_treat.return_value = {"treatments": ["Nitroglycerin", "Aspirin"]}

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert len(data["suggested_tests"]) == 2
        assert data["suggested_tests"][0]["test"] == "ECG"
        assert data["suggested_tests"][0]["reasoning"] == "Detect ST-segment changes"
        assert data["suggested_tests"][1]["test"] == "Troponin I"

    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.session_store.delete_session", new_callable=AsyncMock)
    @patch("app.services.session_store.get_session", new_callable=AsyncMock)
    @patch("app.services.session_store.save_session", new_callable=AsyncMock)
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_followup_flow_includes_tests(
        self, mock_treat, mock_diag, mock_followup, mock_ner, mock_save, mock_get, mock_del, mock_diag_rag, mock_treat_rag
    ):
        """Full follow-up flow returns suggested_tests with reasoning."""
        mock_followup.return_value = {"questions": ["Is pain worse with exertion?"], "confidence": 0.4}
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "Chest pain in 45M"}],
            "suggested_tests": [
                {"test": "Stress test", "reasoning": "Evaluate exercise-induced ischemia"},
            ],
        }
        mock_treat.return_value = {"treatments": ["Beta-blockers"]}

        saved_session = None

        async def _save(session):
            nonlocal saved_session
            saved_session = session

        async def _get(session_id):
            if saved_session and saved_session.id == session_id:
                return saved_session
            return None

        mock_save.side_effect = _save
        mock_get.side_effect = _get

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Step 1: Initial request (low confidence → follow-up)
            r1 = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)
            assert r1.status_code == 200
            assert r1.json()["status"] == "awaiting_followup"
            session_id = r1.json()["session_id"]

            # Step 2: Followup → full diagnosis with tests
            followup_payload = {
                "session_id": session_id,
                "answers": [{"question": "Is pain worse with exertion?", "answer": "yes"}],
            }
            r2 = await ac.post("/diagnose/followup", json=followup_payload, headers=HEADERS)

        assert r2.status_code == 200
        data = r2.json()
        assert data["status"] == "complete"
        assert len(data["suggested_tests"]) == 1
        assert data["suggested_tests"][0]["test"] == "Stress test"
        assert "ischemia" in data["suggested_tests"][0]["reasoning"]

    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_empty_tests_when_llm_omits(self, mock_treat, mock_diag, mock_followup, mock_ner, mock_diag_rag, mock_treat_rag):
        """When LLM response has no suggested_tests, API returns empty list."""
        mock_followup.return_value = {"questions": [], "confidence": 0.9}
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Tension headache", "confidence": 0.7, "reasoning": "Bilateral"}],
        }
        mock_treat.return_value = {"treatments": ["Rest", "Analgesics"]}

        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["suggested_tests"] == []
