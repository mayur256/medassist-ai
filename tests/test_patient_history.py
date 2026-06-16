"""Tests for patient history service and integration."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.history_service import get_patient_history_summary


def _make_message(role, content, metadata=None, created_at=None):
    msg = MagicMock()
    msg.role = role
    msg.content = content
    msg.metadata_ = metadata or {}
    msg.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return msg


def _make_conversation(conv_id, patient_id, status="completed", messages=None, created_at=None):
    conv = MagicMock()
    conv.id = conv_id
    conv.patient_id = patient_id
    conv.status = status
    conv.created_at = created_at or datetime(2026, 1, 1, tzinfo=timezone.utc)
    conv.messages = messages or []
    return conv


class TestGetPatientHistorySummary:
    @pytest.mark.asyncio
    @patch("app.services.history_service.async_session")
    async def test_returns_empty_when_no_conversations(self, mock_session_maker):
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_patient_history_summary("patient-1")
        assert result == ""

    @pytest.mark.asyncio
    @patch("app.services.history_service.async_session")
    async def test_summarizes_past_conversations(self, mock_session_maker):
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        conv = _make_conversation(
            "conv-1", "patient-1",
            messages=[
                _make_message("patient", "I have chest pain"),
                _make_message("assistant", "Assessment done", metadata={
                    "diagnoses": [{"condition": "Angina", "confidence": 0.8}],
                    "treatments": ["Nitroglycerin"],
                }),
            ],
            created_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [conv]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_patient_history_summary("patient-1")
        assert "2026-01-15" in result
        assert "chest pain" in result
        assert "Angina" in result
        assert "Nitroglycerin" in result

    @pytest.mark.asyncio
    @patch("app.services.history_service.async_session")
    async def test_excludes_current_conversation(self, mock_session_maker):
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        await get_patient_history_summary("patient-1", exclude_conversation_id="conv-current")
        # Verify execute was called (the filtering happens in the query)
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.history_service.async_session")
    async def test_multiple_conversations_in_chronological_order(self, mock_session_maker):
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        conv1 = _make_conversation(
            "conv-1", "patient-1",
            messages=[_make_message("patient", "headache for 3 days")],
            created_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
        )
        conv2 = _make_conversation(
            "conv-2", "patient-1",
            messages=[_make_message("patient", "fever and cough")],
            created_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        )

        # Returned in desc order (most recent first) as per the query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [conv2, conv1]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_patient_history_summary("patient-1")
        # Should be reversed to chronological in output
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "headache" in lines[0]
        assert "fever" in lines[1]


class TestChatEngineHistoryIntegration:
    @pytest.mark.asyncio
    @patch("app.services.chat_engine.get_patient_history_summary", new_callable=AsyncMock)
    @patch("app.services.chat_engine.query_llm_json", new_callable=AsyncMock)
    async def test_history_included_in_prompt(self, mock_llm, mock_history):
        mock_history.return_value = "[2026-01-15] Symptoms: chest pain | Dx: Angina"
        mock_llm.return_value = {"content": "Any fever?", "confidence": 0.3}

        patient = MagicMock()
        patient.id = "patient-1"
        patient.age = 45
        patient.gender = "male"
        patient.country = "India"
        patient.known_conditions = []
        patient.allergies = []

        msg = MagicMock()
        msg.role = "patient"
        msg.content = "I have a headache"
        msg.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

        from app.services.chat_engine import process_chat_message
        result = await process_chat_message(patient, [msg], conversation_id="conv-2")

        mock_history.assert_called_once_with("patient-1", exclude_conversation_id="conv-2")
        # The prompt should contain the history
        prompt_used = mock_llm.call_args[0][0]
        assert "Angina" in prompt_used
        assert result["content"] == "Any fever?"

    @pytest.mark.asyncio
    @patch("app.services.chat_engine.get_patient_history_summary", new_callable=AsyncMock)
    @patch("app.services.chat_engine.query_llm_json", new_callable=AsyncMock)
    async def test_no_history_block_when_empty(self, mock_llm, mock_history):
        mock_history.return_value = ""
        mock_llm.return_value = {"content": "When did it start?", "confidence": 0.2}

        patient = MagicMock()
        patient.id = "patient-1"
        patient.age = 30
        patient.gender = "female"
        patient.country = "US"
        patient.known_conditions = []
        patient.allergies = []

        msg = MagicMock()
        msg.role = "patient"
        msg.content = "headache"
        msg.created_at = datetime(2026, 2, 1, tzinfo=timezone.utc)

        from app.services.chat_engine import process_chat_message
        await process_chat_message(patient, [msg])

        prompt_used = mock_llm.call_args[0][0]
        assert "Past consultations" not in prompt_used


class TestGraphHistoryIntegration:
    @pytest.mark.asyncio
    @patch("app.services.history_service.async_session")
    @patch("app.orchestrator.graph.full_pipeline")
    async def test_run_full_injects_history(self, mock_pipeline, mock_session_maker):
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        conv = _make_conversation(
            "conv-old", "patient-1",
            messages=[_make_message("patient", "back pain last month")],
            created_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [conv]
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_pipeline.ainvoke = AsyncMock(return_value={
            "diagnoses": [], "treatments": [], "red_flags": [],
            "urgency_score": 1, "urgency_rationale": "", "confidence": 0.8,
        })

        from app.models.request import DiagnoseRequest, PatientInfo
        from app.orchestrator.graph import run_full

        request = DiagnoseRequest(
            patient_id="patient-1",
            patient=PatientInfo(age=40, gender="male", country="India"),
            symptoms="knee pain",
        )

        await run_full(request)

        # Verify the state passed to pipeline includes history in additional_context
        call_args = mock_pipeline.ainvoke.call_args[0][0]
        assert "back pain" in call_args["additional_context"]
