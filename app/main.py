from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Patient, async_session, init_db
from app.models.request import DiagnoseRequest, FollowupRequest, PatientInfo
from app.models.response import DiagnoseResponse, Diagnosis, SuggestedTest
from app.routes import conversations, patients
from app.routes import admin as admin_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(conversations.router)
app.include_router(admin_routes.router)


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def _resolve_patient(request: DiagnoseRequest) -> PatientInfo:
    """Resolve patient info from patient_id or inline patient data."""
    if request.patient_id:
        async with async_session() as db:
            patient = await db.get(Patient, request.patient_id)
            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")
            return PatientInfo(
                age=patient.age,
                gender=patient.gender,
                country=patient.country,
                known_conditions=patient.known_conditions or [],
                allergies=patient.allergies or [],
            )
    if request.patient:
        return request.patient
    raise HTTPException(status_code=422, detail="Provide either patient or patient_id")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest, _: str = Depends(verify_api_key)):
    """Initial diagnosis — runs NER + followup with confidence-based routing.

    If confidence >= threshold, returns full diagnosis immediately.
    Otherwise returns session_id and follow-up questions.
    """
    from app.orchestrator.graph import run_initial
    from app.services.session_store import create_session, save_session

    patient_info = await _resolve_patient(request)
    request.patient = patient_info

    result = await run_initial(request)
    confidence = result.get("confidence", 0.0)

    # High confidence — full diagnosis completed in initial call
    if result.get("diagnoses"):
        return DiagnoseResponse(
            status="complete",
            confidence=confidence,
            follow_up_questions=result["follow_up_questions"],
            differential_diagnosis=[
                Diagnosis(**d) for d in result["diagnoses"]
            ],
            suggested_tests=[
                SuggestedTest(**t) for t in result.get("suggested_tests", [])
            ],
            treatment_options=result["treatments"],
            red_flags=result["red_flags"],
            urgency_score=result.get("urgency_score", 1),
            urgency_rationale=result.get("urgency_rationale", ""),
        )

    # Low confidence — need follow-up, persist session
    session = create_session(request)
    session.symptoms = result["symptoms"]
    session.duration = result["duration"]
    session.severity = result["severity"]
    session.follow_up_questions = result["follow_up_questions"]
    session.iteration = result["iteration"]
    session.confidence = confidence
    await save_session(session)

    return DiagnoseResponse(
        session_id=session.id,
        status="awaiting_followup",
        confidence=confidence,
        follow_up_questions=result["follow_up_questions"],
    )


@app.post("/diagnose/followup", response_model=DiagnoseResponse)
async def diagnose_followup(request: FollowupRequest, _: str = Depends(verify_api_key)):
    """Process follow-up answers and return full diagnosis."""
    from app.orchestrator.graph import run_full
    from app.services.session_store import delete_session, get_session

    session = await get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    additional_context = " ".join(
        f"{a.question} Answer: {a.answer}" for a in request.answers
    )

    response = await run_full(session.request, additional_context)
    response.session_id = session.id
    response.follow_up_questions = session.follow_up_questions

    await delete_session(session.id)
    return response
