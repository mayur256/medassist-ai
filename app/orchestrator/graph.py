"""LangGraph orchestrator: NER → Follow-up → Diagnosis → Treatment → Compliance."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import settings
from app.models.request import DiagnoseRequest
from app.models.response import DiagnoseResponse, Diagnosis, SuggestedTest, DrugInteractionWarning
from app.services.compliance_engine import apply_compliance
from app.services.diagnosis_engine import generate_diagnoses
from app.services.drug_interaction_service import check_and_filter_interactions
from app.services.followup_engine import generate_followup
from app.services.ner_service import SymptomEvent, extract_entities, format_timeline_for_prompt
from app.services.translation_service import translate_to_english
from app.services.treatment_engine import generate_treatments


class GraphState(TypedDict):
    request: DiagnoseRequest
    symptoms: list[str]
    duration: str | None
    severity: str | None
    timeline: list[SymptomEvent]
    follow_up_questions: list[str]
    diagnoses: list[dict]
    suggested_tests: list[dict]
    treatments: list[str]
    red_flags: list[str]
    urgency_score: int
    urgency_rationale: str
    drug_interactions: list[dict]
    interaction_warnings: list[str]
    iteration: int
    confidence: float
    additional_context: str


async def ner_node(state: GraphState) -> dict:
    """Translate (if needed) and extract entities from symptom text."""
    raw_text = state["request"].symptoms + " " + state.get("additional_context", "")

    # Translate non-English input to English before NER
    translation = await translate_to_english(raw_text)
    text = translation["translated_text"]

    result = extract_entities(text)
    return {
        "symptoms": result.symptoms,
        "duration": result.duration,
        "severity": result.severity,
        "timeline": result.timeline,
    }


async def followup_node(state: GraphState) -> dict:
    """Generate follow-up questions with confidence scoring."""
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
        "confidence": result["confidence"],
    }


def should_diagnose(state: GraphState) -> str:
    """Route to diagnosis if confidence is high enough or max iterations reached."""
    if state["confidence"] >= settings.confidence_threshold:
        return "diagnosis"
    if state["iteration"] >= settings.max_followup_iterations:
        return "diagnosis"
    return END


async def diagnosis_node(state: GraphState) -> dict:
    """Generate differential diagnoses with timeline context."""
    patient = state["request"].patient.model_dump()
    timeline = state.get("timeline", [])
    result = await generate_diagnoses(
        symptoms=state["symptoms"],
        patient=patient,
        duration=state["duration"],
        severity=state["severity"],
        timeline=timeline,
    )
    return {
        "diagnoses": result["diagnoses"],
        "suggested_tests": result["suggested_tests"],
    }


async def treatment_node(state: GraphState) -> dict:
    """Generate treatment suggestions."""
    patient = state["request"].patient.model_dump()
    result = await generate_treatments(
        diagnoses=state["diagnoses"],
        patient=patient,
    )
    return {
        "treatments": result.get("treatments", []),
        # Note: guideline_citations from treatment_engine are available
        # but not stored in state; they'll be included in final response
    }


def compliance_node(state: GraphState) -> dict:
    """Apply compliance rules, detect red flags, and check drug interactions."""
    patient = state["request"].patient
    result = apply_compliance(
        treatments=state["treatments"],
        symptoms=state["symptoms"],
        raw_text=state["request"].symptoms,
        country=patient.country,
        patient_age=patient.age,
        known_conditions=patient.known_conditions,
    )

    # Drug interaction checking
    interaction_result = check_and_filter_interactions(
        treatments=result["treatments"],
        known_conditions=patient.known_conditions,
    )

    return {
        "treatments": interaction_result["treatments"],
        "red_flags": result["red_flags"],
        "urgency_score": result["urgency_score"],
        "urgency_rationale": result["urgency_rationale"],
        "drug_interactions": interaction_result["interactions"],
        "interaction_warnings": interaction_result["warnings"],
    }


# --- Initial pipeline: NER → Followup with confidence-based routing ---

def _build_initial_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("ner", ner_node)
    graph.add_node("followup", followup_node)
    graph.add_node("diagnosis", diagnosis_node)
    graph.add_node("treatment", treatment_node)
    graph.add_node("compliance", compliance_node)
    graph.set_entry_point("ner")
    graph.add_edge("ner", "followup")
    graph.add_conditional_edges("followup", should_diagnose, {"diagnosis": "diagnosis", END: END})
    graph.add_edge("diagnosis", "treatment")
    graph.add_edge("treatment", "compliance")
    graph.add_edge("compliance", END)
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
        "timeline": [],
        "follow_up_questions": [],
        "diagnoses": [],
        "suggested_tests": [],
        "treatments": [],
        "red_flags": [],
        "urgency_score": 1,
        "urgency_rationale": "",
        "drug_interactions": [],
        "interaction_warnings": [],
        "iteration": 0,
        "confidence": 0.0,
        "additional_context": additional_context,
    }


async def run_initial(request: DiagnoseRequest) -> dict:
    """Run NER + followup with confidence-based routing.

    If confidence >= threshold, proceeds to full diagnosis automatically.
    Otherwise returns state with follow-up questions.
    """
    state = _make_initial_state(request)
    return await initial_pipeline.ainvoke(state)


async def run_full(request: DiagnoseRequest, additional_context: str = "") -> DiagnoseResponse:
    """Run full pipeline (NER → Diagnosis → Treatment → Compliance)."""
    from app.services.citation_service import get_citations_with_urls, format_citations
    from app.models.response import SourceCitation
    
    # Inject patient history if patient_id is available
    if request.patient_id:
        from app.services.history_service import get_patient_history_summary
        history = await get_patient_history_summary(request.patient_id)
        if history:
            additional_context = f"Past consultations:\n{history}\n\n{additional_context}"

    state = _make_initial_state(request, additional_context)
    result = await full_pipeline.ainvoke(state)
    
    # Extract unique sources from diagnosis and treatment citations
    all_sources = set()
    
    # Collect diagnosis sources
    if result.get("diagnoses"):
        for diagnosis in result["diagnoses"]:
            if isinstance(diagnosis, dict) and diagnosis.get("reasoning"):
                # Extract source references from reasoning
                reasoning = diagnosis.get("reasoning", "")
                for key in ["WHO", "NICE", "ICMR", "ACC/AHA", "ESC", "ADA", "GINA", "BTS", "IDSA"]:
                    if key in reasoning:
                        all_sources.add(key)
    
    # Get formatted citations
    source_names = sorted(list(all_sources))
    guideline_sources_dicts = get_citations_with_urls(source_names)
    formatted_citations = format_citations(source_names, format_style="apa")
    
    # Convert dicts to SourceCitation models
    guideline_sources = [SourceCitation(**s) for s in guideline_sources_dicts]
    
    # Build response with citations
    return DiagnoseResponse(
        status="complete",
        differential_diagnosis=[Diagnosis(**d) for d in result["diagnoses"]],
        suggested_tests=[SuggestedTest(**t) for t in result.get("suggested_tests", [])],
        treatment_options=result["treatments"],
        red_flags=result["red_flags"],
        urgency_score=result.get("urgency_score", 1),
        urgency_rationale=result.get("urgency_rationale", ""),
        confidence=result.get("confidence", 0.0),
        drug_interactions=[
            DrugInteractionWarning(**i) for i in result.get("drug_interactions", [])
        ],
        interaction_warnings=result.get("interaction_warnings", []),
        guideline_sources=guideline_sources,
        formatted_citations=formatted_citations,
    )
