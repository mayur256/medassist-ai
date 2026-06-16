"""Patient history service — fetches and summarizes past conversations."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import Conversation, Message, Patient, async_session

MAX_PAST_CONVERSATIONS = 5
MAX_MESSAGES_PER_CONVERSATION = 10


async def get_patient_history_summary(patient_id: str, exclude_conversation_id: str | None = None) -> str:
    """Fetch completed past conversations and produce a compact summary for prompt injection.

    Returns empty string if no history exists.
    """
    async with async_session() as db:
        query = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.patient_id == patient_id, Conversation.status == "completed")
            .order_by(Conversation.created_at.desc())
            .limit(MAX_PAST_CONVERSATIONS)
        )
        if exclude_conversation_id:
            query = query.where(Conversation.id != exclude_conversation_id)

        result = await db.execute(query)
        conversations = result.scalars().all()

    if not conversations:
        return ""

    lines = []
    for conv in reversed(conversations):  # chronological order
        date_str = conv.created_at.strftime("%Y-%m-%d") if conv.created_at else "unknown"
        msgs = sorted(conv.messages, key=lambda m: m.created_at)[:MAX_MESSAGES_PER_CONVERSATION]
        # Extract key info: patient complaints and assistant diagnoses
        symptoms = []
        diagnoses = []
        treatments = []
        for msg in msgs:
            if msg.role == "patient":
                symptoms.append(msg.content[:100])
            elif msg.role == "assistant" and msg.metadata_:
                meta = msg.metadata_ if isinstance(msg.metadata_, dict) else {}
                for d in meta.get("diagnoses", []):
                    if isinstance(d, dict):
                        diagnoses.append(d.get("condition", ""))
                for t in meta.get("treatments", []):
                    treatments.append(t if isinstance(t, str) else "")

        entry = f"[{date_str}] Symptoms: {'; '.join(symptoms[:3])}"
        if diagnoses:
            entry += f" | Dx: {', '.join(diagnoses[:3])}"
        if treatments:
            entry += f" | Tx: {', '.join(treatments[:3])}"
        lines.append(entry)

    return "\n".join(lines)
