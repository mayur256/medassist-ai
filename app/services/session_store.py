"""In-memory session store for conversation state."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.models.request import DiagnoseRequest


@dataclass
class Session:
    id: str
    request: DiagnoseRequest
    symptoms: list[str] = field(default_factory=list)
    duration: str | None = None
    severity: str | None = None
    follow_up_questions: list[str] = field(default_factory=list)
    follow_up_answers: list[dict] = field(default_factory=list)
    iteration: int = 0
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


_sessions: dict[str, Session] = {}
_TTL = timedelta(minutes=30)


def create_session(request: DiagnoseRequest) -> Session:
    session_id = str(uuid.uuid4())
    session = Session(id=session_id, request=request)
    _sessions[session_id] = session
    _cleanup_expired()
    return session


def get_session(session_id: str) -> Session | None:
    session = _sessions.get(session_id)
    if session and datetime.utcnow() - session.created_at > _TTL:
        del _sessions[session_id]
        return None
    return session


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _cleanup_expired() -> None:
    now = datetime.utcnow()
    expired = [k for k, v in _sessions.items() if now - v.created_at > _TTL]
    for k in expired:
        del _sessions[k]
