"""Tests for #11 Audit Trail / Explainability enhancement."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings

settings.api_key = "test-key"
HEADERS = {"X-API-Key": "test-key"}


class TestAuditLogModel:
    """Test the AuditLog model and log_llm_call function."""

    @pytest.mark.asyncio
    @patch("app.services.audit.async_session")
    async def test_log_llm_call_creates_entry(self, mock_session_maker):
        """log_llm_call should create an audit log entry."""
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.services.audit import log_llm_call

        log_id = await log_llm_call(
            step="diagnosis",
            prompt="Test prompt",
            raw_response="Test response",
            parsed_response='{"key": "value"}',
            latency_ms=150.5,
            conversation_id="conv-123",
        )

        assert log_id is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

        # Verify the AuditLog object passed to add
        entry = mock_session.add.call_args[0][0]
        assert entry.step == "diagnosis"
        assert entry.prompt == "Test prompt"
        assert entry.raw_response == "Test response"
        assert entry.parsed_response == '{"key": "value"}'
        assert entry.latency_ms == 150.5
        assert entry.conversation_id == "conv-123"

    @pytest.mark.asyncio
    @patch("app.services.audit.async_session")
    async def test_log_llm_call_no_conversation_id(self, mock_session_maker):
        """log_llm_call works without conversation_id."""
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.services.audit import log_llm_call

        log_id = await log_llm_call(
            step="followup",
            prompt="Some prompt",
            raw_response="Some response",
            latency_ms=50.0,
        )

        assert log_id is not None
        entry = mock_session.add.call_args[0][0]
        assert entry.conversation_id is None


class TestAuditContext:
    """Test the audit context setting in LLM service."""

    def test_set_audit_context(self):
        from app.services.llm_service import set_audit_context, _audit_context

        set_audit_context(conversation_id="test-conv", step="diagnosis")
        assert _audit_context["conversation_id"] == "test-conv"
        assert _audit_context["step"] == "diagnosis"

    def test_set_audit_context_defaults(self):
        from app.services.llm_service import set_audit_context, _audit_context

        set_audit_context()
        assert _audit_context["conversation_id"] is None
        assert _audit_context["step"] == "unknown"


class TestLLMServiceAuditIntegration:
    """Test that LLM calls trigger audit logging."""

    @pytest.mark.asyncio
    @patch("app.services.llm_service._query_groq", new_callable=AsyncMock)
    @patch("app.services.audit.async_session")
    async def test_query_llm_logs_audit(self, mock_session_maker, mock_groq):
        """query_llm should log the call to audit."""
        mock_groq.return_value = "test response"
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.services.llm_service import query_llm, set_audit_context

        set_audit_context(conversation_id="conv-456", step="treatment")
        result = await query_llm("test prompt")

        assert result == "test response"
        # Verify audit log was created
        mock_session.add.assert_called_once()
        entry = mock_session.add.call_args[0][0]
        assert entry.step == "treatment"
        assert entry.prompt == "test prompt"
        assert entry.raw_response == "test response"
        assert entry.conversation_id == "conv-456"
        assert entry.latency_ms >= 0

    @pytest.mark.asyncio
    @patch("app.services.llm_service._query_groq", new_callable=AsyncMock)
    @patch("app.services.audit.async_session")
    async def test_query_llm_json_logs_audit(self, mock_session_maker, mock_groq):
        """query_llm_json should also log via query_llm."""
        mock_groq.return_value = '{"result": "ok"}'
        mock_session = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.services.llm_service import query_llm_json, set_audit_context

        set_audit_context(step="followup")
        result = await query_llm_json("json prompt")

        assert result == {"result": "ok"}
        mock_session.add.assert_called_once()
        entry = mock_session.add.call_args[0][0]
        assert entry.prompt == "json prompt"
        assert entry.raw_response == '{"result": "ok"}'

    @pytest.mark.asyncio
    @patch("app.services.llm_service._query_groq", new_callable=AsyncMock)
    @patch("app.services.audit.async_session")
    async def test_audit_failure_does_not_break_llm_call(self, mock_session_maker, mock_groq):
        """If audit logging fails, the LLM call should still succeed."""
        mock_groq.return_value = "valid response"
        mock_session_maker.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB down"))

        from app.services.llm_service import query_llm

        result = await query_llm("prompt")
        assert result == "valid response"  # Should NOT raise


class TestAdminAuditEndpoint:
    """Test the /admin/audit-logs endpoint."""

    @pytest.mark.asyncio
    @patch("app.services.audit.async_session")
    async def test_get_audit_logs_endpoint(self, mock_session_maker):
        """GET /admin/audit-logs returns logs."""
        from app.services.audit import AuditLog
        from datetime import datetime

        mock_log = MagicMock()
        mock_log.id = "log-1"
        mock_log.conversation_id = "conv-1"
        mock_log.step = "diagnosis"
        mock_log.prompt = "test"
        mock_log.raw_response = "response"
        mock_log.parsed_response = None
        mock_log.latency_ms = 100.0
        mock_log.created_at = datetime(2026, 1, 1)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/admin/audit-logs")

        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["logs"][0]["step"] == "diagnosis"

    @pytest.mark.asyncio
    @patch("app.services.audit.async_session")
    async def test_audit_logs_filter_by_step(self, mock_session_maker):
        """GET /admin/audit-logs?step=followup filters correctly."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/admin/audit-logs?step=followup&limit=10")

        assert r.status_code == 200
        assert r.json()["count"] == 0


class TestAuditLogSchema:
    """Test AuditLog table schema."""

    def test_audit_log_has_required_columns(self):
        from app.services.audit import AuditLog

        columns = {c.name for c in AuditLog.__table__.columns}
        assert "id" in columns
        assert "conversation_id" in columns
        assert "step" in columns
        assert "prompt" in columns
        assert "raw_response" in columns
        assert "parsed_response" in columns
        assert "latency_ms" in columns
        assert "created_at" in columns
