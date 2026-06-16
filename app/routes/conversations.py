"""Conversation and message endpoints — chat-style interface."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Conversation, Message, Patient, get_db

router = APIRouter(tags=["conversations"])


class ConversationResponse(BaseModel):
    id: str
    patient_id: str
    title: str
    status: str
    created_at: str


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: dict
    created_at: str


@router.post("/patients/{patient_id}/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    conv = Conversation(patient_id=patient_id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return _conv_resp(conv)


@router.get("/patients/{patient_id}/conversations", response_model=list[ConversationResponse])
async def list_conversations(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    result = await db.execute(
        select(Conversation).where(Conversation.patient_id == patient_id).order_by(Conversation.created_at.desc())
    )
    return [_conv_resp(c) for c in result.scalars().all()]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    return [_msg_resp(m) for m in result.scalars().all()]


@router.post("/conversations/{conversation_id}/messages", response_model=list[MessageResponse], status_code=201)
async def send_message(conversation_id: str, data: MessageCreate, db: AsyncSession = Depends(get_db)):
    """Send a patient message and get AI response."""
    conv = await db.execute(
        select(Conversation).options(selectinload(Conversation.patient)).where(Conversation.id == conversation_id)
    )
    conv = conv.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.status == "completed":
        raise HTTPException(status_code=400, detail="Conversation is completed")

    # Save patient message
    patient_msg = Message(conversation_id=conversation_id, role="patient", content=data.content)
    db.add(patient_msg)

    # Update title from first message
    existing = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).limit(1)
    )
    if not existing.scalar_one_or_none():
        conv.title = data.content[:50]

    await db.commit()
    await db.refresh(patient_msg)

    # Get full history for context
    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    history = result.scalars().all()

    # Run AI pipeline
    from app.services.chat_engine import process_chat_message
    ai_response = await process_chat_message(conv.patient, history, conversation_id=conversation_id)

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response["content"],
        metadata_=ai_response.get("metadata", {}),
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return [_msg_resp(patient_msg), _msg_resp(assistant_msg)]


def _conv_resp(c: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=c.id, patient_id=c.patient_id, title=c.title or "",
        status=c.status or "active", created_at=c.created_at.isoformat() if c.created_at else "",
    )


def _msg_resp(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id, conversation_id=m.conversation_id, role=m.role,
        content=m.content, metadata=m.metadata_ or {},
        created_at=m.created_at.isoformat() if m.created_at else "",
    )
