"""Consultation history endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Consultation, Patient, get_db

router = APIRouter(tags=["history"])


class ConsultationResponse(BaseModel):
    id: str
    patient_id: str
    symptoms: str
    follow_up_questions: list[str]
    follow_up_answers: list[dict]
    differential_diagnosis: list[dict]
    treatment_options: list[str]
    red_flags: list[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("/patients/{patient_id}/history", response_model=list[ConsultationResponse])
async def get_patient_history(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    result = await db.execute(
        select(Consultation).where(Consultation.patient_id == patient_id).order_by(Consultation.created_at.desc())
    )
    return [_to_dict(c) for c in result.scalars().all()]


@router.get("/history/{session_id}", response_model=ConsultationResponse)
async def get_consultation(session_id: str, db: AsyncSession = Depends(get_db)):
    consultation = await db.get(Consultation, session_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return _to_dict(consultation)


def _to_dict(c: Consultation) -> dict:
    return {
        "id": c.id,
        "patient_id": c.patient_id,
        "symptoms": c.symptoms,
        "follow_up_questions": c.follow_up_questions or [],
        "follow_up_answers": c.follow_up_answers or [],
        "differential_diagnosis": c.differential_diagnosis or [],
        "treatment_options": c.treatment_options or [],
        "red_flags": c.red_flags or [],
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }
