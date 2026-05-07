from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


class PatientInfo(BaseModel):
    age: int = Field(..., gt=0, lt=150)
    gender: Gender
    country: Literal["India", "US", "UK"]
    known_conditions: list[str] = []
    allergies: list[str] = []


class DiagnoseRequest(BaseModel):
    patient: PatientInfo | None = None
    patient_id: str | None = None
    symptoms: str = Field(..., min_length=1)


class FollowupAnswer(BaseModel):
    question: str
    answer: str


class FollowupRequest(BaseModel):
    session_id: str
    answers: list[FollowupAnswer]
