"""Audit trail — logs all LLM prompts and responses for explainability."""

import time
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy import select

from app.db import Base, async_session


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, nullable=True, index=True)
    step = Column(String, nullable=False)  # e.g. "followup", "diagnosis", "treatment"
    prompt = Column(Text, nullable=False)
    raw_response = Column(Text, nullable=False, default="")
    parsed_response = Column(Text, nullable=True)  # JSON string of parsed result
    latency_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


async def log_llm_call(
    step: str,
    prompt: str,
    raw_response: str,
    parsed_response: str | None = None,
    latency_ms: float = 0.0,
    conversation_id: str | None = None,
) -> str:
    """Persist an audit log entry. Returns the log id."""
    log_id = str(uuid.uuid4())
    entry = AuditLog(
        id=log_id,
        conversation_id=conversation_id,
        step=step,
        prompt=prompt,
        raw_response=raw_response,
        parsed_response=parsed_response,
        latency_ms=latency_ms,
    )
    async with async_session() as session:
        session.add(entry)
        await session.commit()
    return log_id


async def get_audit_logs(
    conversation_id: str | None = None,
    step: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve audit logs with optional filtering."""
    async with async_session() as session:
        query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if conversation_id:
            query = query.where(AuditLog.conversation_id == conversation_id)
        if step:
            query = query.where(AuditLog.step == step)
        result = await session.execute(query)
        return [
            {
                "id": log.id,
                "conversation_id": log.conversation_id,
                "step": log.step,
                "prompt": log.prompt,
                "raw_response": log.raw_response,
                "parsed_response": log.parsed_response,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in result.scalars().all()
        ]
