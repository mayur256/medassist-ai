"""Tests for #12 Session Persistence enhancement."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.request import DiagnoseRequest, PatientInfo
from app.services.session_store import (
    Session,
    DiagnoseSession,
    create_session,
    save_session,
    get_session,
    delete_session,
    cleanup_expired,
    _serialize,
    _deserialize,
    _TTL,
)


def _make_request():
    return DiagnoseRequest(
        patient=PatientInfo(age=45, gender="male", country="India", known_conditions=["hypertension"], allergies=["penicillin"]),
        symptoms="chest pain for 2 days",
    )


class TestSessionCreation:
    """Test session creation (synchronous, no DB)."""

    def test_create_session_returns_session_object(self):
        req = _make_request()
        session = create_session(req)
        assert session.id is not None
        assert session.request == req
        assert session.symptoms == []
        assert session.iteration == 0
        assert session.confidence == 0.0

    def test_create_session_unique_ids(self):
        req = _make_request()
        s1 = create_session(req)
        s2 = create_session(req)
        assert s1.id != s2.id


class TestSessionSerialization:
    """Test serialization and deserialization of session state."""

    def test_serialize_deserialize_roundtrip(self):
        req = _make_request()
        session = create_session(req)
        session.symptoms = ["chest pain", "shortness of breath"]
        session.duration = "2 days"
        session.severity = "severe"
        session.follow_up_questions = ["Is pain worse with exertion?"]
        session.iteration = 1
        session.confidence = 0.6

        serialized = _serialize(session)
        deserialized = _deserialize(session.id, serialized, session.created_at)

        assert deserialized.id == session.id
        assert deserialized.symptoms == session.symptoms
        assert deserialized.duration == session.duration
        assert deserialized.severity == session.severity
        assert deserialized.follow_up_questions == session.follow_up_questions
        assert deserialized.iteration == session.iteration
        assert deserialized.confidence == session.confidence
        assert deserialized.request.symptoms == session.request.symptoms

    def test_serialize_produces_valid_json(self):
        session = create_session(_make_request())
        serialized = _serialize(session)
        parsed = json.loads(serialized)
        assert "request" in parsed
        assert "symptoms" in parsed
        assert "confidence" in parsed


class TestSessionPersistence:
    """Test DB-backed session save/get/delete."""

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_save_session_new(self, mock_session_maker):
        """save_session should insert a new DiagnoseSession row."""
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)  # No existing session
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        session = create_session(_make_request())
        session.symptoms = ["headache"]
        await save_session(session)

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert added.id == session.id
        assert "headache" in added.state_json

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_save_session_update_existing(self, mock_session_maker):
        """save_session should update if session already exists."""
        existing_row = MagicMock()
        existing_row.id = "existing-id"

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=existing_row)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        session = Session(id="existing-id", request=_make_request())
        session.symptoms = ["updated"]
        await save_session(session)

        # Should update, not add
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()
        assert "updated" in existing_row.state_json

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_get_session_found(self, mock_session_maker):
        """get_session returns session when found and not expired."""
        req = _make_request()
        session = create_session(req)
        session.symptoms = ["chest pain"]

        row = MagicMock()
        row.id = session.id
        row.state_json = _serialize(session)
        row.created_at = datetime.now(timezone.utc)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=row)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_session(session.id)
        assert result is not None
        assert result.id == session.id
        assert result.symptoms == ["chest pain"]

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_get_session_not_found(self, mock_session_maker):
        """get_session returns None when session doesn't exist."""
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_get_session_expired(self, mock_session_maker):
        """get_session returns None and deletes expired sessions."""
        row = MagicMock()
        row.id = "expired-session"
        row.state_json = _serialize(create_session(_make_request()))
        row.created_at = datetime.now(timezone.utc) - _TTL - timedelta(minutes=1)

        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=row)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await get_session("expired-session")
        assert result is None
        mock_db.delete.assert_called_once_with(row)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_delete_session(self, mock_session_maker):
        """delete_session removes the row."""
        row = MagicMock()
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=row)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        await delete_session("some-id")
        mock_db.delete.assert_called_once_with(row)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_delete_session_not_found(self, mock_session_maker):
        """delete_session is a no-op if session doesn't exist."""
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        await delete_session("nonexistent")
        mock_db.delete.assert_not_called()


class TestCleanupExpired:
    """Test TTL-based cleanup."""

    @pytest.mark.asyncio
    @patch("app.services.session_store.async_session")
    async def test_cleanup_expired_runs(self, mock_session_maker):
        """cleanup_expired should execute a delete query."""
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)

        await cleanup_expired()
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestDiagnoseSessionModel:
    """Test the SQLAlchemy model."""

    def test_model_has_required_columns(self):
        columns = {c.name for c in DiagnoseSession.__table__.columns}
        assert "id" in columns
        assert "state_json" in columns
        assert "created_at" in columns
