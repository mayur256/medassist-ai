from pydantic import BaseModel, Field

DISCLAIMER = (
    "This is AI-assisted output and must be verified by a licensed medical professional."
)


class Diagnosis(BaseModel):
    condition: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class DiagnoseResponse(BaseModel):
    follow_up_questions: list[str] = []
    differential_diagnosis: list[Diagnosis] = []
    suggested_tests: list[str] = []
    treatment_options: list[str] = []
    red_flags: list[str] = []
    disclaimer: str = DISCLAIMER
