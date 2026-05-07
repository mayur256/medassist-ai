from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.request import DiagnoseRequest, FollowupRequest
from app.models.response import DiagnoseResponse

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(request: DiagnoseRequest, _: str = Depends(verify_api_key)):
    """Initial diagnosis — runs NER + followup. Returns session_id and questions."""
    from app.orchestrator.graph import run_initial
    from app.services.session_store import create_session

    session = create_session(request)
    result = await run_initial(request)

    # Save state to session
    session.symptoms = result["symptoms"]
    session.duration = result["duration"]
    session.severity = result["severity"]
    session.follow_up_questions = result["follow_up_questions"]
    session.iteration = result["iteration"]

    return DiagnoseResponse(
        session_id=session.id,
        status="awaiting_followup",
        follow_up_questions=result["follow_up_questions"],
    )


@app.post("/diagnose/followup", response_model=DiagnoseResponse)
async def diagnose_followup(request: FollowupRequest, _: str = Depends(verify_api_key)):
    """Process follow-up answers and return full diagnosis."""
    from app.orchestrator.graph import run_full
    from app.services.session_store import get_session, delete_session

    session = get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Build additional context from answers
    additional_context = " ".join(
        f"{a.question} Answer: {a.answer}" for a in request.answers
    )

    # Run full pipeline with original request + followup context
    response = await run_full(session.request, additional_context)
    response.session_id = session.id
    response.follow_up_questions = session.follow_up_questions

    delete_session(session.id)
    return response
