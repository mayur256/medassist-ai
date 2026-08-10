"""RAG Service — Retrieves clinical guidelines and injects into LLM prompts."""

import logging
from typing import Optional
from app.services.embedding_service import retrieve_relevant_guidelines, get_condition_guidelines

logger = logging.getLogger(__name__)


def format_guidelines_for_prompt(guidelines: list[dict]) -> str:
    """
    Format retrieved guidelines into a readable block for LLM injection.
    
    Args:
        guidelines: List of guideline chunks from retrieve_relevant_guidelines()
    
    Returns:
        Formatted string ready for prompt injection
    """
    if not guidelines:
        return ""
    
    lines = ["CLINICAL GUIDELINES CONTEXT:"]
    
    # Group by condition for clarity
    by_condition = {}
    for guideline in guidelines:
        condition_name = guideline.get("condition_name", "Unknown")
        if condition_name not in by_condition:
            by_condition[condition_name] = []
        by_condition[condition_name].append(guideline)
    
    # Format each condition's guidelines
    for condition_name, chunks in by_condition.items():
        lines.append(f"\n### {condition_name}")
        
        for chunk in chunks:
            chunk_type = chunk.get("chunk_type", "info")
            content = chunk.get("content", "")
            source = chunk.get("source", "")
            
            # Format based on chunk type
            if chunk_type == "treatment":
                lines.append(f"**Treatment Guidelines:** {content}")
            elif chunk_type == "tests":
                lines.append(f"**Recommended Tests:** {content}")
            elif chunk_type == "symptoms":
                lines.append(f"**Key Symptoms:** {content}")
            elif chunk_type == "red_flags":
                lines.append(f"**Red Flags:** {content}")
            else:
                lines.append(f"{content}")
            
            if source:
                lines.append(f"[Source: {source}]")
    
    return "\n".join(lines)


def format_citations(guidelines: list[dict]) -> dict:
    """
    Extract citations from guidelines for response metadata.
    
    Returns:
        Dict with citation information for inclusion in response
    """
    citations = {
        "sources": [],
        "conditions_referenced": [],
        "total_guidelines_used": len(guidelines)
    }
    
    seen_sources = set()
    seen_conditions = set()
    
    for guideline in guidelines:
        source = guideline.get("source", "")
        condition = guideline.get("condition_name", "")
        
        if source and source not in seen_sources:
            citations["sources"].append(source)
            seen_sources.add(source)
        
        if condition and condition not in seen_conditions:
            citations["conditions_referenced"].append(condition)
            seen_conditions.add(condition)
    
    return citations


async def retrieve_guidelines_for_condition(
    condition: str,
    country: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    """
    Retrieve guidelines for a specific condition.
    
    Args:
        condition: Condition name or ID (e.g., "hypertension", "acute_coronary_syndrome")
        country: Filter by country (India, US, UK)
        k: Number of results to return
    
    Returns:
        List of relevant guideline chunks
    """
    query = f"Treatment and diagnosis guidelines for {condition}"
    guidelines = await retrieve_relevant_guidelines(
        query=query,
        country=country,
        k=k,
    )
    return guidelines


async def retrieve_guidelines_for_symptoms(
    symptoms: list[str],
    country: Optional[str] = None,
    category: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    """
    Retrieve guidelines based on patient symptoms.
    
    Args:
        symptoms: List of symptoms extracted from patient input
        country: Filter by country
        category: Filter by category (cardiovascular, respiratory, etc.)
        k: Number of results to return
    
    Returns:
        List of relevant guideline chunks
    """
    # Create a comprehensive query from symptoms
    query = "Clinical management and diagnosis for: " + ", ".join(symptoms)
    
    guidelines = await retrieve_relevant_guidelines(
        query=query,
        country=country,
        category=category,
        k=k,
    )
    
    return guidelines


async def retrieve_guidelines_for_treatment(
    diagnoses: list[dict],
    country: Optional[str] = None,
    k: int = 5,
) -> list[dict]:
    """
    Retrieve treatment guidelines for diagnosed conditions.
    
    Args:
        diagnoses: List of diagnoses [{"condition": "...", "confidence": 0.8, ...}]
        country: Filter by country
        k: Number of results to return
    
    Returns:
        List of relevant treatment guideline chunks
    """
    # Build query from diagnoses, prioritizing by confidence
    sorted_diagnoses = sorted(
        diagnoses,
        key=lambda x: x.get("confidence", 0.0),
        reverse=True
    )
    
    # Use top diagnoses in query
    top_conditions = [d.get("condition", "") for d in sorted_diagnoses[:3]]
    query = "Treatment guidelines for: " + ", ".join(top_conditions)
    
    guidelines = await retrieve_relevant_guidelines(
        query=query,
        country=country,
        k=k,
    )
    
    return guidelines


async def retrieve_guidelines_for_red_flags(
    symptoms: list[str],
    k: int = 3,
) -> list[dict]:
    """
    Retrieve guidelines for red flag symptoms (emergency indicators).
    
    Args:
        symptoms: Symptoms that might indicate emergency
        k: Number of results to return
    
    Returns:
        List of guideline chunks for red flag conditions
    """
    query = "Emergency management and red flags for: " + ", ".join(symptoms)
    
    guidelines = await retrieve_relevant_guidelines(
        query=query,
        k=k,
    )
    
    return guidelines


async def build_diagnosis_context(
    symptoms: list[str],
    patient_conditions: list[str],
    country: Optional[str] = None,
) -> dict:
    """
    Build comprehensive guideline context for diagnosis generation.
    
    Args:
        symptoms: Extracted symptoms
        patient_conditions: Known patient conditions
        country: Patient's country
    
    Returns:
        Dict with formatted guidelines and citations
    """
    logger.info(f"Building diagnosis context for symptoms: {symptoms}")
    
    try:
        # Retrieve guidelines based on symptoms
        symptom_guidelines = await retrieve_guidelines_for_symptoms(
            symptoms=symptoms,
            country=country,
            k=10,
        )
        
        # Also retrieve based on known conditions (for context)
        condition_guidelines = []
        for condition in patient_conditions:
            cond_guidelines = await retrieve_guidelines_for_condition(
                condition=condition,
                country=country,
                k=2,
            )
            condition_guidelines.extend(cond_guidelines)
        
        # Combine and deduplicate
        all_guidelines = []
        seen_content = set()
        
        for guideline in symptom_guidelines + condition_guidelines:
            content = guideline.get("content", "")
            if content not in seen_content:
                all_guidelines.append(guideline)
                seen_content.add(content)
        
        return {
            "guidelines_text": format_guidelines_for_prompt(all_guidelines),
            "citations": format_citations(all_guidelines),
            "guideline_count": len(all_guidelines),
        }
    except Exception as e:
        logger.warning(f"RAG retrieval failed (degrading gracefully): {e}")
        return {
            "guidelines_text": "",
            "citations": {},
            "guideline_count": 0,
        }


async def build_treatment_context(
    diagnoses: list[dict],
    country: Optional[str] = None,
    patient_allergies: list[str] = None,
) -> dict:
    """
    Build comprehensive guideline context for treatment generation.
    
    Args:
        diagnoses: List of differential diagnoses
        country: Patient's country
        patient_allergies: Patient's allergies (for filtering)
    
    Returns:
        Dict with formatted guidelines and citations
    """
    logger.info(f"Building treatment context for diagnoses: {[d.get('condition') for d in diagnoses]}")
    
    try:
        # Retrieve treatment guidelines
        guidelines = await retrieve_guidelines_for_treatment(
            diagnoses=diagnoses,
            country=country,
            k=10,
        )
        
        # Filter out any guidelines mentioning patient allergies
        if patient_allergies:
            filtered_guidelines = []
            for guideline in guidelines:
                content = guideline.get("content", "").lower()
                allergy_mentioned = any(
                    allergy.lower() in content for allergy in patient_allergies
                )
                if not allergy_mentioned:
                    filtered_guidelines.append(guideline)
            guidelines = filtered_guidelines
        
        return {
            "guidelines_text": format_guidelines_for_prompt(guidelines),
            "citations": format_citations(guidelines),
            "guideline_count": len(guidelines),
        }
    except Exception as e:
        logger.warning(f"RAG retrieval failed (degrading gracefully): {e}")
        return {
            "guidelines_text": "",
            "citations": {},
            "guideline_count": 0,
        }


async def build_red_flag_context(
    symptoms: list[str],
) -> dict:
    """
    Build guideline context for red flag evaluation.
    
    Args:
        symptoms: Symptoms to check for red flags
    
    Returns:
        Dict with formatted guidelines and citations
    """
    logger.info(f"Building red flag context for symptoms: {symptoms}")
    
    guidelines = await retrieve_guidelines_for_red_flags(symptoms)
    
    return {
        "guidelines_text": format_guidelines_for_prompt(guidelines),
        "citations": format_citations(guidelines),
        "guideline_count": len(guidelines),
    }
