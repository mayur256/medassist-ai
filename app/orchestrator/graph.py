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
    additional_context: str


def ner_node(state: GraphState) -> dict:
    """Extract entities from symptom text."""
    text = state["request"].symptoms + " " + state.get("additional_context", "")
    result = extract_entities(text)
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


# --- Initial pipeline: NER → Followup only ---

def _build_initial_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("ner", ner_node)
    graph.add_node("followup", followup_node)
    graph.set_entry_point("ner")
    graph.add_edge("ner", "followup")
    graph.add_edge("followup", END)
    return graph.compile()


# --- Full pipeline: NER → Diagnosis → Treatment → Compliance ---

def _build_full_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("ner", ner_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("treatment", treatment_node)
    graph.add_node("compliance", compliance_node)
    graph.set_entry_point("ner")
    graph.add_edge("ner", "diagnosis")
    graph.add_edge("diagnosis", "treatment")
    graph.add_edge("treatment", "compliance")
    graph.add_edge("compliance", END)
    return graph.compile()


initial_pipeline = _build_initial_graph()
full_pipeline = _build_full_graph()


def _make_initial_state(request: DiagnoseRequest, additional_context: str = "") -> GraphState:
    return {
        "request": request,
        "symptoms": [],
        "duration": None,
        "severity": None,
        "follow_up_questions": [],
        "diagnoses": [],
        "treatments": [],
        "red_flags": [],
        "iteration": 0,
        "additional_context": additional_context,
    }


async def run_initial(request: DiagnoseRequest) -> dict:
    """Run NER + followup only. Returns state with symptoms and questions."""
    state = _make_initial_state(request)
    return await initial_pipeline.ainvoke(state)


async def run_full(request: DiagnoseRequest, additional_context: str = "") -> DiagnoseResponse:
    """Run full pipeline (NER → Diagnosis → Treatment → Compliance)."""
    state = _make_initial_state(request, additional_context)
    result = await full_pipeline.ainvoke(state)
    return DiagnoseResponse(
        status="complete",
        differential_diagnosis=[Diagnosis(**d) for d in result["diagnoses"]],
        treatment_options=result["treatments"],
        red_flags=result["red_flags"],
    )
