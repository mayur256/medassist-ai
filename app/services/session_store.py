"""Database-backed session store for /diagnose conversation state."""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, String, Text, select, delete

from app.db import Base, async_session
from app.models.request import DiagnoseRequest

_TTL = timedelta(minutes=30)


class DiagnoseSession(Base):
    __tablename__ = "diagnose_sessions"

    id = Column(String, primary_key=True)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


@dataclass
class Session:
    """Session object — same interface as before."""
    id: str
    request: DiagnoseRequest
    symptoms: list[str] = field(default_factory=list)
    duration: str | None = None
    severity: str | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    follow_up_answers: list[dict] = field(default_factory=list)
    iteration: int = 0
    confidence: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _serialize(session: Session) -> str:
    return json.dumps({
        "request": session.request.model_dump(),
        "symptoms": session.symptoms,
        "duration": session.duration,
        "severity": session.severity,
        "follow_up_questions": session.follow_up_questions,
        "follow_up_answers": session.follow_up_answers,
        "iteration": session.iteration,
        "confidence": session.confidence,
    })


def _deserialize(session_id: str, data: str, created_at: datetime) -> Session:
    d = json.loads(data)
    return Session(
        id=session_id,
        request=DiagnoseRequest(**d["request"]),
        symptoms=d.get("symptoms", []),
        duration=d.get("duration"),
        severity=d.get("severity"),
        follow_up_questions=d.get("follow_up_questions", []),
        follow_up_answers=d.get("follow_up_answers", []),
        iteration=d.get("iteration", 0),
        confidence=d.get("confidence", 0.0),
        created_at=created_at,
    )


def create_session(request: DiagnoseRequest) -> Session:
    """Create a new session (synchronous — writes on save)."""
    session_id = str(uuid.uuid4())
    return Session(id=session_id, request=request)


async def save_session(session: Session) -> None:
    """Persist session state to database."""
    async with async_session() as db:
        existing = await db.get(DiagnoseSession, session.id)
        if existing:
            existing.state_json = _serialize(session)
        else:
            db.add(DiagnoseSession(
                id=session.id,
                state_json=_serialize(session),
                created_at=session.created_at,
            ))
        await db.commit()


async def get_session(session_id: str) -> Session | None:
    """Retrieve session from database. Returns None if expired or missing."""
    async with async_session() as db:
        row = await db.get(DiagnoseSession, session_id)
        if not row:
            return None
        # TTL check
        now = datetime.now(timezone.utc)
        created = row.created_at.replace(tzinfo=timezone.utc) if row.created_at.tzinfo is None else row.created_at
        if now - created > _TTL:
            await db.delete(row)
            await db.commit()
            return None
        return _deserialize(session_id, row.state_json, row.created_at)


async def delete_session(session_id: str) -> None:
    """Remove session from database."""
    async with async_session() as db:
        row = await db.get(DiagnoseSession, session_id)
        if row:
            await db.delete(row)
            await db.commit()


async def cleanup_expired() -> None:
    """Remove all expired sessions."""
    cutoff = datetime.now(timezone.utc) - _TTL
    async with async_session() as db:
        await db.execute(
            delete(DiagnoseSession).where(DiagnoseSession.created_at < cutoff)
        )
        await db.commit()
