from pydantic import BaseModel, Field

DISCLAIMER = (
    "This is AI-assisted output and must be verified by a licensed medical professional."
)


class Diagnosis(BaseModel):
    condition: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class SuggestedTest(BaseModel):
    """A recommended diagnostic test with clinical reasoning."""

    test: str
    reasoning: str


class SourceCitation(BaseModel):
    """Citation source for clinical guidelines."""
    
    name: str  # e.g., "WHO 2021"
    full_name: str  # e.g., "World Health Organization Clinical Guidelines 2021"
    url: str | None = None  # Link to the guideline source
    publication_date: str | None = None
    doi: str | None = None
    version: str | None = None


class DiagnoseResponse(BaseModel):
    session_id: str | None = None
    status: str = "complete"  # "awaiting_followup" or "complete"
    confidence: float = 0.0
    urgency_score: int = Field(default=1, ge=1, le=5)
    urgency_rationale: str = ""
    follow_up_questions: list[str] = []
    differential_diagnosis: list[Diagnosis] = []
    suggested_tests: list[SuggestedTest] = []
    treatment_options: list[str] = []
    red_flags: list[str] = []
    
    # Citation tracking
    guideline_sources: list[SourceCitation] = []  # Clinical guidelines used
    formatted_citations: list[str] = []  # APA-formatted citations for academic use
    
    disclaimer: str = DISCLAIMER
