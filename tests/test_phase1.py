from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.request import DiagnoseRequest, PatientInfo
from app.models.response import DISCLAIMER, DiagnoseResponse

client = TestClient(app)

# Ensure a test API key is set
settings.api_key = "test-key"
HEADERS = {"X-API-Key": "test-key"}


class TestRequestModels:
    def test_valid_request(self):
        req = DiagnoseRequest(
            patient=PatientInfo(age=45, gender="male", country="India"),
            symptoms="chest pain",
        )
        assert req.patient.age == 45

    def test_invalid_age(self):
        with pytest.raises(Exception):
            PatientInfo(age=0, gender="male", country="India")

    def test_invalid_country(self):
        with pytest.raises(Exception):
            PatientInfo(age=30, gender="female", country="Canada")

    def test_invalid_gender(self):
        with pytest.raises(Exception):
            PatientInfo(age=30, gender="unknown", country="US")

    def test_empty_symptoms(self):
        with pytest.raises(Exception):
            DiagnoseRequest(
                patient=PatientInfo(age=30, gender="male", country="UK"),
                symptoms="",
            )


class TestResponseModels:
    def test_default_response(self):
        resp = DiagnoseResponse()
        assert resp.disclaimer == DISCLAIMER
        assert resp.differential_diagnosis == []


class TestAPI:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_diagnose_no_auth(self):
        r = client.post("/diagnose", json={})
        assert r.status_code == 422

    def test_diagnose_bad_key(self):
        r = client.post(
            "/diagnose",
            json={"patient": {"age": 30, "gender": "male", "country": "India"}, "symptoms": "headache"},
            headers={"X-API-Key": "wrong"},
        )
        assert r.status_code == 401

    @patch("app.services.session_store.save_session", new_callable=AsyncMock)
    @patch("app.orchestrator.graph.run_initial", new_callable=AsyncMock)
    def test_diagnose_valid(self, mock_initial, mock_save):
        mock_initial.return_value = {
            "symptoms": ["headache"], "duration": None, "severity": None,
            "follow_up_questions": [], "iteration": 1, "confidence": 0.3,
        }
        r = client.post(
            "/diagnose",
            json={"patient": {"age": 30, "gender": "male", "country": "India"}, "symptoms": "headache"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["disclaimer"] == DISCLAIMER
        assert data["status"] == "awaiting_followup"

    def test_diagnose_invalid_input(self):
        r = client.post(
            "/diagnose",
            json={"patient": {"age": -1, "gender": "male", "country": "India"}, "symptoms": "x"},
            headers=HEADERS,
        )
        assert r.status_code == 422
