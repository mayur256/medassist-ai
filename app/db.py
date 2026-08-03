"""Database models and async engine setup (PostgreSQL + SQLAlchemy)."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, Index, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    country = Column(String, nullable=False)
    known_conditions = Column(JSON, default=list)
    allergies = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversations = relationship("Conversation", back_populates="patient", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="New consultation")
    status = Column(String, default="active")  # active | completed
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("Patient", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # patient | assistant | system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class GuidelineEmbedding(Base):
    """Vector store for embedded clinical guidelines (RAG)."""
    __tablename__ = "guideline_embeddings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    condition_id = Column(String, nullable=False, index=True)
    condition_name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    countries = Column(ARRAY(String), nullable=False)  # Requires pgvector extension
    content_chunk = Column(Text, nullable=False)
    chunk_index = Column(String, nullable=False)  # diagnostic_criteria, treatment_guidelines, red_flags, etc.
    embedding = Column(ARRAY(Float), nullable=False)  # vector(384) for all-MiniLM-L6-v2
    metadata = Column(JSON, nullable=True)  # source, confidence, severity, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_guideline_embeddings_category', 'category'),
        Index('ix_guideline_embeddings_condition', 'condition_id'),
    )


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with async_session() as session:
        yield session
