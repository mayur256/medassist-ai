"""Tests for #8 SOAP Export / Conversation Completion enhancement."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.soap_service import (
    _build_soap_from_metadata,
    _build_transcript,
    _empty_soap,
    _extract_diagnoses_from_metadata,
    _extract_treatments_from_metadata,
    _format_soap_plain_text,
    generate_soap_note,
)


def _make_message(role: str, content: str, metadata: dict | None = None):
    """Create a mock Message object."""
    msg = MagicMock()
    msg.role = role
    msg.content = content
    msg.metadata_ = metadata or {}
    msg.created_at = datetime(2026, 8, 10, 12, 0, 0)
    return msg


def _make_patient(
    name="John Doe",
    age=45,
    gender="male",
    country="US",
    conditions=None,
    allergies=None,
):
    """Create a mock Patient object."""
    patient = MagicMock()
    patient.id = "patient-123"
    patient.name = name
    patient.age = age
    patient.gender = gender
    patient.country = country
    patient.known_conditions = conditions or ["diabetes"]
    patient.allergies = allergies or ["penicillin"]
    return patient


class TestBuildTranscript:
    """Test transcript building from messages."""

    def test_basic_conversation(self):
        """Build transcript from patient and assistant messages."""
        messages = [
            _make_message("patient", "I have chest pain"),
            _make_message("assistant", "When did the chest pain start?"),
            _make_message("patient", "About 2 days ago"),
        ]
        transcript = _build_transcript(messages)
        assert "Patient: I have chest pain" in transcript
        assert "Clinician/AI: When did the chest pain start?" in transcript
        assert "Patient: About 2 days ago" in transcript

    def test_system_messages_included(self):
        """System messages included with bracket notation."""
        messages = [
            _make_message("system", "Session started"),
            _make_message("patient", "Hello"),
        ]
        transcript = _build_transcript(messages)
        assert "[System: Session started]" in transcript

    def test_empty_messages(self):
        """Empty message list gives empty transcript."""
        assert _build_transcript([]) == ""


class TestExtractMetadata:
    """Test metadata extraction from messages."""

    def test_extract_diagnoses(self):
        """Extract diagnoses from assistant metadata."""
        messages = [
            _make_message("assistant", "Assessment", {
                "diagnoses": [
                    {"condition": "ACS", "confidence": 0.8, "reasoning": "test"},
                    {"condition": "GERD", "confidence": 0.4, "reasoning": "test"},
                ]
            }),
        ]
        diagnoses = _extract_diagnoses_from_metadata(messages)
        assert len(diagnoses) == 2
        assert diagnoses[0]["condition"] == "ACS"

    def test_extract_treatments(self):
        """Extract treatments from assistant metadata."""
        messages = [
            _make_message("assistant", "Plan", {
                "treatments": ["Aspirin", "Rest", "ECG"]
            }),
        ]
        treatments = _extract_treatments_from_metadata(messages)
        assert "Aspirin" in treatments
        assert "Rest" in treatments

    def test_no_metadata_returns_empty(self):
        """Messages without metadata return empty lists."""
        messages = [_make_message("patient", "hello")]
        assert _extract_diagnoses_from_metadata(messages) == []
        assert _extract_treatments_from_metadata(messages) == []


class TestEmptySoap:
    """Test empty SOAP structure."""

    def test_has_all_sections(self):
        """Empty SOAP has all 4 sections."""
        soap = _empty_soap()
        assert "subjective" in soap
        assert "objective" in soap
        assert "assessment" in soap
        assert "plan" in soap

    def test_subjective_fields(self):
        """Subjective section has required fields."""
        soap = _empty_soap()
        subj = soap["subjective"]
        assert "chief_complaint" in subj
        assert "history_of_present_illness" in subj
        assert "allergies" in subj

    def test_plan_fields(self):
        """Plan section has required fields."""
        soap = _empty_soap()
        plan = soap["plan"]
        assert "diagnostic_workup" in plan
        assert "treatment" in plan
        assert "follow_up" in plan


class TestBuildSoapFromMetadata:
    """Test fallback SOAP generation from metadata."""

    def test_builds_from_messages(self):
        """Builds SOAP from patient messages and metadata."""
        patient = _make_patient()
        messages = [
            _make_message("patient", "Severe chest pain for 2 days"),
            _make_message("assistant", "Assessment complete", {
                "diagnoses": [
                    {"condition": "Acute Coronary Syndrome", "confidence": 0.85,
                     "reasoning": "Chest pain in diabetic male"},
                    {"condition": "GERD", "confidence": 0.3, "reasoning": "Less likely"},
                ],
                "treatments": ["Aspirin", "ECG monitoring"],
            }),
        ]
        soap = _build_soap_from_metadata(patient, messages)

        assert "Severe chest pain" in soap["subjective"]["chief_complaint"]
        assert soap["assessment"]["primary_diagnosis"] == "Acute Coronary Syndrome"
        assert "GERD" in soap["assessment"]["differential_diagnoses"]
        assert "Aspirin" in soap["plan"]["treatment"]

    def test_handles_empty_metadata(self):
        """Handles messages with no diagnosis metadata."""
        patient = _make_patient()
        messages = [_make_message("patient", "I feel unwell")]
        soap = _build_soap_from_metadata(patient, messages)
        assert soap["assessment"]["primary_diagnosis"] == "Undetermined"


class TestFormatSoapPlainText:
    """Test plain text formatting."""

    def test_contains_all_sections(self):
        """Plain text has all SOAP sections."""
        soap = {
            "subjective": {
                "chief_complaint": "Chest pain",
                "history_of_present_illness": "2 day history",
                "review_of_systems": "Positive for SOB",
                "past_medical_history": "Diabetes",
                "allergies": "Penicillin",
                "medications": "Metformin",
            },
            "objective": {
                "vitals": "Not documented",
                "physical_exam": "Not documented",
                "labs_imaging": "Pending ECG",
            },
            "assessment": {
                "primary_diagnosis": "ACS",
                "differential_diagnoses": ["GERD"],
                "severity": "Severe",
                "clinical_reasoning": "Classic presentation",
            },
            "plan": {
                "diagnostic_workup": ["ECG", "Troponin"],
                "treatment": ["Aspirin", "Oxygen"],
                "patient_education": "Go to ER if worsens",
                "follow_up": "24 hours",
                "referrals": "Cardiology",
                "red_flags_discussed": "Worsening pain",
            },
        }
        patient = _make_patient()
        text = _format_soap_plain_text(soap, patient)

        assert "SUBJECTIVE:" in text
        assert "OBJECTIVE:" in text
        assert "ASSESSMENT:" in text
        assert "PLAN:" in text
        assert "Chest pain" in text
        assert "ACS" in text
        assert "DISCLAIMER" in text

    def test_includes_patient_info(self):
        """Plain text includes patient demographics."""
        soap = _empty_soap()
        patient = _make_patient(name="Jane Smith", age=55, gender="female")
        text = _format_soap_plain_text(soap, patient)
        assert "Jane Smith" in text
        assert "55y" in text
        assert "female" in text


class TestGenerateSoapNote:
    """Test async SOAP generation."""

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self):
        """Empty messages gives empty SOAP."""
        patient = _make_patient()
        result = await generate_soap_note(patient, [], "conv-123")
        assert result["plain_text"] == "No consultation data available."
        assert result["soap_note"] == _empty_soap()

    @pytest.mark.asyncio
    @patch("app.services.soap_service.query_llm_json")
    async def test_llm_success(self, mock_llm):
        """Successful LLM call returns structured SOAP."""
        mock_llm.return_value = {
            "subjective": {
                "chief_complaint": "Chest pain",
                "history_of_present_illness": "2 days of chest pain",
                "review_of_systems": "SOB present",
                "past_medical_history": "Diabetes",
                "allergies": "Penicillin",
                "medications": "Metformin",
            },
            "objective": {
                "vitals": "Not documented",
                "physical_exam": "Not documented",
                "labs_imaging": "Pending",
            },
            "assessment": {
                "primary_diagnosis": "ACS",
                "differential_diagnoses": ["GERD", "Costochondritis"],
                "severity": "High",
                "clinical_reasoning": "Classic ACS presentation",
            },
            "plan": {
                "diagnostic_workup": ["ECG", "Troponin"],
                "treatment": ["Aspirin"],
                "patient_education": "ER if worsens",
                "follow_up": "24h",
                "referrals": "Cardiology",
                "red_flags_discussed": "Worsening pain",
            },
        }

        patient = _make_patient()
        messages = [_make_message("patient", "Chest pain for 2 days")]
        result = await generate_soap_note(patient, messages, "conv-123")

        assert result["soap_note"]["assessment"]["primary_diagnosis"] == "ACS"
        assert "SOAP NOTE" in result["plain_text"]
        assert result["conversation_id"] == "conv-123"
        assert result["patient_id"] == "patient-123"

    @pytest.mark.asyncio
    @patch("app.services.soap_service.query_llm_json")
    async def test_llm_failure_falls_back(self, mock_llm):
        """LLM failure falls back to metadata-based SOAP."""
        mock_llm.return_value = None

        patient = _make_patient()
        messages = [
            _make_message("patient", "Headache and fever"),
            _make_message("assistant", "Assessment", {
                "diagnoses": [{"condition": "Viral illness", "confidence": 0.7, "reasoning": "test"}],
                "treatments": ["Rest", "Acetaminophen"],
            }),
        ]
        result = await generate_soap_note(patient, messages, "conv-456")

        assert result["soap_note"]["assessment"]["primary_diagnosis"] == "Viral illness"
        assert "Headache and fever" in result["soap_note"]["subjective"]["chief_complaint"]
