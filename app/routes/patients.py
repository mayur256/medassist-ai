"""Patient CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Patient, get_db

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientCreate(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., gt=0, lt=150)
    gender: str
    country: str
    known_conditions: list[str] = []
    allergies: list[str] = []


class PatientResponse(BaseModel):
    id: str
    name: str
    age: int
    gender: str
    country: str
    known_conditions: list[str]
    allergies: list[str]
    created_at: str


@router.post("", response_model=PatientResponse, status_code=201)
async def create_patient(data: PatientCreate, db: AsyncSession = Depends(get_db)):
    patient = Patient(**data.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return _to_resp(patient)


@router.get("", response_model=list[PatientResponse])
async def list_patients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Patient).order_by(Patient.created_at.desc()))
    return [_to_resp(p) for p in result.scalars().all()]


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return _to_resp(patient)


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: str, data: PatientCreate, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for key, value in data.model_dump().items():
        setattr(patient, key, value)
    await db.commit()
    await db.refresh(patient)
    return _to_resp(patient)


@router.delete("/{patient_id}", status_code=204)
async def delete_patient(patient_id: str, db: AsyncSession = Depends(get_db)):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    await db.delete(patient)
    await db.commit()


def _to_resp(p: Patient) -> PatientResponse:
    return PatientResponse(
        id=p.id, name=p.name, age=p.age, gender=p.gender, country=p.country,
        known_conditions=p.known_conditions or [], allergies=p.allergies or [],
        created_at=p.created_at.isoformat() if p.created_at else "",
    )
