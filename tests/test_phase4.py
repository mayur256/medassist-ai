"""Phase 4 tests: Orchestrator + session-based follow-up flow."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.models.request import DiagnoseRequest, PatientInfo
from app.models.response import DISCLAIMER

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


class TestInitialDiagnose:
    @pytest.mark.asyncio
    @patch("app.services.session_store.save_session", new_callable=AsyncMock)
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    async def test_returns_session_and_questions(self, mock_followup, mock_ner, mock_save):
        mock_followup.return_value = {
            "questions": ["Is the pain worse with exertion?", "Any fever?"],
            "confidence": 0.4,
        }

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "awaiting_followup"
        assert data["session_id"] is not None
        assert len(data["follow_up_questions"]) == 2
        assert data["differential_diagnosis"] == []


class TestFollowup:
    @pytest.mark.asyncio
    @patch("app.services.session_store.delete_session", new_callable=AsyncMock)
    @patch("app.services.session_store.get_session", new_callable=AsyncMock)
    @patch("app.services.session_store.save_session", new_callable=AsyncMock)
    @patch("app.orchestrator.graph.extract_entities", side_effect=_mock_ner)
    @patch("app.services.followup_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.diagnosis_engine.query_llm_json", new_callable=AsyncMock)
    @patch("app.services.treatment_engine.query_llm_json", new_callable=AsyncMock)
    async def test_full_flow(self, mock_treat, mock_diag, mock_followup, mock_ner, mock_save, mock_get, mock_del):
        mock_followup.return_value = {"questions": ["Is pain worse with exertion?"], "confidence": 0.4}
        mock_diag.return_value = {
            "diagnoses": [{"condition": "Angina", "confidence": 0.8, "reasoning": "Chest pain in 45M with HTN"}]
        }
        mock_treat.return_value = {"treatments": ["Antianginal therapy", "Stress test referral"]}

        # Capture the session when saved, return it on get
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
            # Step 1: Initial request
            r1 = await ac.post("/diagnose", json=VALID_PAYLOAD, headers=HEADERS)
            assert r1.status_code == 200
            session_id = r1.json()["session_id"]

            # Step 2: Followup with answers
            followup_payload = {
                "session_id": session_id,
                "answers": [{"question": "Is pain worse with exertion?", "answer": "yes, especially climbing stairs"}],
            }
            r2 = await ac.post("/diagnose/followup", json=followup_payload, headers=HEADERS)

        assert r2.status_code == 200
        data = r2.json()
        assert data["status"] == "complete"
        assert len(data["differential_diagnosis"]) == 1
        assert data["differential_diagnosis"][0]["condition"] == "Angina"
        assert "chest pain" in data["red_flags"]

    @pytest.mark.asyncio
    @patch("app.services.session_store.get_session", new_callable=AsyncMock, return_value=None)
    async def test_invalid_session(self, mock_get):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/diagnose/followup",
                json={"session_id": "nonexistent", "answers": []},
                headers=HEADERS,
            )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_requires_auth(self):
        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/diagnose/followup",
                json={"session_id": "x", "answers": []},
                headers={"X-API-Key": "wrong"},
            )
        assert r.status_code == 401
