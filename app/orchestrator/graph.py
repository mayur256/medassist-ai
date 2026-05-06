"""LangGraph orchestrator: NER → Follow-up → Diagnosis → Treatment → Compliance."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.models.request import DiagnoseRequest
from app.models.response import DiagnoseResponse, Diagnosis
from app.services.compliance_engine import apply_compliance
from app.services.diagnosis_engine import generate_diagnoses
from app.services.followup_engine import generate_followup
from app.services.ner_service import extract_entities
from app.services.treatment_engine import generate_treatments


class GraphState(TypedDict):
    request: DiagnoseRequest
    symptoms: list[str]
    duration: str | None
    severity: str | None
    follow_up_questions: list[str]
    diagnoses: list[dict]
    treatments: list[str]
    red_flags: list[str]
    iteration: int


def ner_node(state: GraphState) -> dict:
    """Extract entities from symptom text."""
    result = extract_entities(state["request"].symptoms)
    return {
        "symptoms": result.symptoms,
        "duration": result.duration,
        "severity": result.severity,
    }


async def followup_node(state: GraphState) -> dict:
    """Generate follow-up questions."""
    patient = state["request"].patient.model_dump()
    result = await generate_followup(
        symptoms=state["symptoms"],
        patient=patient,
        previous_questions=state["follow_up_questions"],
        iteration=state["iteration"],
    )
    return {
        "follow_up_questions": state["follow_up_questions"] + result["questions"],
        "iteration": state["iteration"] + 1,
    }


def should_continue_followup(state: GraphState) -> str:
    """Decide whether to continue follow-up or proceed to diagnosis."""
    from app.config import settings

    if state["iteration"] >= settings.max_followup_iterations:
        return "diagnose"
    return "diagnose"


async def diagnosis_node(state: GraphState) -> dict:
    """Generate differential diagnoses."""
    patient = state["request"].patient.model_dump()
    diagnoses = await generate_diagnoses(
        symptoms=state["symptoms"],
        patient=patient,
        duration=state["duration"],
        severity=state["severity"],
    )
    return {"diagnoses": diagnoses}


async def treatment_node(state: GraphState) -> dict:
    """Generate treatment suggestions."""
    patient = state["request"].patient.model_dump()
    treatments = await generate_treatments(
        diagnoses=state["diagnoses"],
        patient=patient,
    )
    return {"treatments": treatments}


def compliance_node(state: GraphState) -> dict:
    """Apply compliance rules and detect red flags."""
    result = apply_compliance(
        treatments=state["treatments"],
        symptoms=state["symptoms"],
        raw_text=state["request"].symptoms,
        country=state["request"].patient.country,
    )
    return {
        "treatments": result["treatments"],
        "red_flags": result["red_flags"],
    }


def build_graph() -> StateGraph:
    """Build the LangGraph pipeline."""
    graph = StateGraph(GraphState)

    graph.add_node("ner", ner_node)
    graph.add_node("followup", followup_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("treatment", treatment_node)
    graph.add_node("compliance", compliance_node)

    graph.set_entry_point("ner")
    graph.add_edge("ner", "followup")
    graph.add_conditional_edges("followup", should_continue_followup, {"diagnose": "diagnosis"})
    graph.add_edge("diagnosis", "treatment")
    graph.add_edge("treatment", "compliance")
    graph.add_edge("compliance", END)

    return graph.compile()


# Compiled graph singleton
pipeline = build_graph()


async def run_pipeline(request: DiagnoseRequest) -> DiagnoseResponse:
    """Execute the full orchestration pipeline and return a DiagnoseResponse."""
    initial_state: GraphState = {
        "request": request,
        "symptoms": [],
        "duration": None,
        "severity": None,
        "follow_up_questions": [],
        "diagnoses": [],
        "treatments": [],
        "red_flags": [],
        "iteration": 0,
    }

    result = await pipeline.ainvoke(initial_state)

    return DiagnoseResponse(
        follow_up_questions=result["follow_up_questions"],
        differential_diagnosis=[
            Diagnosis(**d) for d in result["diagnoses"]
        ],
        treatment_options=result["treatments"],
        red_flags=result["red_flags"],
    )
