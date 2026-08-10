"""Phase 3 tests: Diagnosis Engine, Treatment Engine, Compliance Engine."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.diagnosis_engine import generate_diagnoses
from app.services.treatment_engine import (
    _contains_dosage,
    _filter_allergies,
    generate_treatments,
)
from app.services.compliance_engine import (
    apply_compliance,
    detect_red_flags,
    filter_restricted_drugs,
)


# --- Diagnosis Engine Tests ---

class TestDiagnosisEngine:
    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_returns_diagnoses(self, mock_llm, mock_rag):
        mock_llm.return_value = {
            "diagnoses": [
                {"condition": "Angina", "confidence": 0.8, "reasoning": "Chest pain in 45M"},
                {"condition": "GERD", "confidence": 0.5, "reasoning": "Can mimic chest pain"},
            ]
        }
        result = await generate_diagnoses(
            symptoms=["chest pain"],
            patient={"age": 45, "gender": "male", "country": "India"},
        )
        assert len(result["diagnoses"]) == 2
        assert result["diagnoses"][0]["condition"] == "Angina"
        assert result["diagnoses"][0]["confidence"] == 0.8

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_clamps_confidence(self, mock_llm, mock_rag):
        mock_llm.return_value = {
            "diagnoses": [{"condition": "X", "confidence": 1.5, "reasoning": ""}]
        }
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert result["diagnoses"][0]["confidence"] == 1.0

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_max_5_diagnoses(self, mock_llm, mock_rag):
        mock_llm.return_value = {
            "diagnoses": [{"condition": f"D{i}", "confidence": 0.5, "reasoning": ""} for i in range(8)]
        }
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert len(result["diagnoses"]) <= 5

    @pytest.mark.asyncio
    @patch("app.services.diagnosis_engine.build_diagnosis_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.diagnosis_engine.query_llm_json")
    async def test_handles_llm_failure(self, mock_llm, mock_rag):
        mock_llm.return_value = None
        result = await generate_diagnoses(symptoms=["pain"], patient={"age": 30})
        assert result["diagnoses"] == []
        assert result["suggested_tests"] == []


# --- Treatment Engine Tests ---

class TestTreatmentDosageFilter:
    def test_detects_mg(self):
        assert _contains_dosage("Take 500mg ibuprofen") is True

    def test_detects_times_per_day(self):
        assert _contains_dosage("3 times a day") is True

    def test_detects_bid(self):
        assert _contains_dosage("administer b.i.d") is True

    def test_clean_text_passes(self):
        assert _contains_dosage("Rest and hydration") is False


class TestTreatmentAllergyFilter:
    def test_filters_allergy(self):
        treatments = ["Penicillin antibiotics", "Rest", "Ibuprofen"]
        result = _filter_allergies(treatments, ["penicillin"])
        assert "Penicillin antibiotics" not in result
        assert "Rest" in result

    def test_no_allergies(self):
        treatments = ["Rest", "Hydration"]
        result = _filter_allergies(treatments, [])
        assert len(result) == 2


class TestTreatmentEngine:
    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.treatment_engine.query_llm_json")
    async def test_returns_treatments(self, mock_llm, mock_rag):
        mock_llm.return_value = {"treatments": ["Rest", "Analgesics", "Physical therapy"]}
        result = await generate_treatments(
            diagnoses=[{"condition": "Back pain"}],
            patient={"age": 35, "gender": "male", "country": "US", "allergies": []},
        )
        assert "Rest" in result["treatments"]
        assert len(result["treatments"]) == 3

    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.treatment_engine.query_llm_json")
    async def test_filters_dosage_from_llm(self, mock_llm, mock_rag):
        mock_llm.return_value = {"treatments": ["Rest", "Take 500mg paracetamol twice daily"]}
        result = await generate_treatments(
            diagnoses=[{"condition": "Headache"}],
            patient={"age": 30, "gender": "female", "country": "UK", "allergies": []},
        )
        assert len(result["treatments"]) == 1
        assert "Rest" in result["treatments"]

    @pytest.mark.asyncio
    @patch("app.services.treatment_engine.build_treatment_context", new_callable=AsyncMock, return_value={"guidelines_text": "", "citations": {}})
    @patch("app.services.treatment_engine.query_llm_json")
    async def test_filters_allergies(self, mock_llm, mock_rag):
        mock_llm.return_value = {"treatments": ["Penicillin-based antibiotics", "Rest"]}
        result = await generate_treatments(
            diagnoses=[{"condition": "Infection"}],
            patient={"age": 40, "gender": "male", "country": "India", "allergies": ["penicillin"]},
        )
        assert "Rest" in result["treatments"]
        assert len(result["treatments"]) == 1


# --- Compliance Engine Tests ---

class TestRedFlagDetection:
    def test_detects_chest_pain(self):
        flags = detect_red_flags(["chest pain", "nausea"])
        assert "chest pain" in flags

    def test_detects_from_raw_text(self):
        flags = detect_red_flags([], "patient reports difficulty breathing")
        assert "difficulty breathing" in flags

    def test_no_flags(self):
        flags = detect_red_flags(["mild headache"])
        assert flags == []


class TestRestrictedDrugFilter:
    def test_filters_india_restricted(self):
        treatments = ["Cisapride for motility", "Antacids", "Diet changes"]
        result = filter_restricted_drugs(treatments, "India")
        assert len(result) == 2
        assert "Antacids" in result

    def test_filters_us_restricted(self):
        treatments = ["Rofecoxib", "Ibuprofen"]
        result = filter_restricted_drugs(treatments, "US")
        assert result == ["Ibuprofen"]

    def test_unknown_country_passes_all(self):
        treatments = ["Cisapride", "Anything"]
        result = filter_restricted_drugs(treatments, "Mars")
        assert len(result) == 2


class TestApplyCompliance:
    def test_full_compliance(self):
        result = apply_compliance(
            treatments=["Cisapride", "Rest", "Hydration"],
            symptoms=["chest pain", "mild cough"],
            raw_text="chest pain for 2 days",
            country="India",
        )
        assert "Cisapride" not in result["treatments"]
        assert "Rest" in result["treatments"]
        assert "chest pain" in result["red_flags"]
