"""Drug Interaction Checking Service.

Checks suggested treatments against patient's existing medications (inferred from
known_conditions) for potential drug-drug interactions. Flags interactions with
severity levels: minor, moderate, severe.

Severe interactions → removed from suggestions with warning.
Moderate interactions → kept but warned.
Minor interactions → noted for reference.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Load interaction database
_DATA_PATH = Path(__file__).parent.parent / "data" / "drug_interactions.json"
_interaction_data: dict | None = None


@dataclass
class DrugInteraction:
    """Represents a detected drug interaction."""
    drug_in_treatment: str
    drug_in_patient_meds: str
    severity: str  # minor, moderate, severe
    description: str
    recommendation: str


def _load_interaction_data() -> dict:
    """Load the drug interaction database (lazy-loaded, cached)."""
    global _interaction_data
    if _interaction_data is not None:
        return _interaction_data
    try:
        with open(_DATA_PATH) as f:
            _interaction_data = json.load(f)
        logger.info("Drug interaction database loaded: %d interactions, %d conditions",
                    len(_interaction_data.get("interactions", [])),
                    len(_interaction_data.get("condition_medications", {})))
    except Exception as e:
        logger.error("Failed to load drug interaction database: %s", e)
        _interaction_data = {"condition_medications": {}, "interactions": []}
    return _interaction_data


def get_patient_medications(known_conditions: list[str]) -> list[str]:
    """Infer likely medications from patient's known conditions.

    Maps conditions to common medications used to treat them.
    Returns deduplicated list of medication names (lowercase).
    """
    data = _load_interaction_data()
    condition_meds = data.get("condition_medications", {})

    medications = set()
    for condition in known_conditions:
        condition_lower = condition.lower().strip()
        # Try exact match first, then partial match
        if condition_lower in condition_meds:
            medications.update(condition_meds[condition_lower])
        else:
            # Partial match: condition contains the key or key contains condition
            for key, meds in condition_meds.items():
                if condition_lower in key or key in condition_lower:
                    medications.update(meds)
                    break

    return sorted(medications)


def check_interactions(
    treatments: list[str],
    patient_medications: list[str],
) -> list[DrugInteraction]:
    """Check proposed treatments against patient's medications for interactions.

    Args:
        treatments: List of treatment option strings from the treatment engine
        patient_medications: List of drugs the patient is likely taking

    Returns:
        List of DrugInteraction objects for detected interactions
    """
    data = _load_interaction_data()
    interactions_db = data.get("interactions", [])

    if not treatments or not patient_medications:
        return []

    detected: list[DrugInteraction] = []
    patient_meds_lower = [m.lower() for m in patient_medications]

    for treatment in treatments:
        treatment_lower = treatment.lower()
        for interaction in interactions_db:
            drug_a = interaction["drug_a"].lower()
            drug_b = interaction["drug_b"].lower()

            # Check if treatment mentions drug_a and patient takes drug_b, or vice versa
            match_a_in_treatment = drug_a in treatment_lower
            match_b_in_treatment = drug_b in treatment_lower

            if match_a_in_treatment:
                # Check if drug_b is in patient meds
                if any(drug_b in med for med in patient_meds_lower):
                    detected.append(DrugInteraction(
                        drug_in_treatment=interaction["drug_a"],
                        drug_in_patient_meds=interaction["drug_b"],
                        severity=interaction["severity"],
                        description=interaction["description"],
                        recommendation=interaction["recommendation"],
                    ))
            elif match_b_in_treatment:
                # Check if drug_a is in patient meds
                if any(drug_a in med for med in patient_meds_lower):
                    detected.append(DrugInteraction(
                        drug_in_treatment=interaction["drug_b"],
                        drug_in_patient_meds=interaction["drug_a"],
                        severity=interaction["severity"],
                        description=interaction["description"],
                        recommendation=interaction["recommendation"],
                    ))

    # Deduplicate by (drug_in_treatment, drug_in_patient_meds)
    seen = set()
    unique = []
    for interaction in detected:
        key = (interaction.drug_in_treatment.lower(), interaction.drug_in_patient_meds.lower())
        if key not in seen:
            seen.add(key)
            unique.append(interaction)

    return unique


def filter_severe_interactions(
    treatments: list[str],
    interactions: list[DrugInteraction],
) -> tuple[list[str], list[str]]:
    """Remove treatments with severe interactions; return filtered list and warnings.

    Args:
        treatments: Original treatment list
        interactions: Detected interactions

    Returns:
        Tuple of (filtered_treatments, warning_messages)
    """
    severe_drugs = set()
    warnings = []

    for interaction in interactions:
        if interaction.severity == "severe":
            severe_drugs.add(interaction.drug_in_treatment.lower())
            warnings.append(
                f"SEVERE INTERACTION: {interaction.drug_in_treatment} conflicts with "
                f"patient's {interaction.drug_in_patient_meds} — {interaction.description}. "
                f"Recommendation: {interaction.recommendation}"
            )
        elif interaction.severity == "moderate":
            warnings.append(
                f"MODERATE INTERACTION: {interaction.drug_in_treatment} with "
                f"patient's {interaction.drug_in_patient_meds} — {interaction.description}. "
                f"Recommendation: {interaction.recommendation}"
            )
        else:
            warnings.append(
                f"MINOR INTERACTION: {interaction.drug_in_treatment} with "
                f"patient's {interaction.drug_in_patient_meds} — {interaction.description}."
            )

    # Remove treatments that contain severe interaction drugs
    if severe_drugs:
        filtered = []
        for t in treatments:
            t_lower = t.lower()
            if not any(drug in t_lower for drug in severe_drugs):
                filtered.append(t)
        return filtered, warnings

    return treatments, warnings


def check_and_filter_interactions(
    treatments: list[str],
    known_conditions: list[str],
) -> dict:
    """Full pipeline: infer medications, check interactions, filter severe ones.

    Args:
        treatments: Treatment suggestions from the treatment engine
        known_conditions: Patient's known medical conditions

    Returns:
        Dict with:
            - treatments: filtered treatment list (severe interactions removed)
            - interactions: list of all detected interactions as dicts
            - warnings: human-readable warning strings
            - patient_medications: inferred medication list
    """
    if not known_conditions:
        return {
            "treatments": treatments,
            "interactions": [],
            "warnings": [],
            "patient_medications": [],
        }

    # Infer patient medications from conditions
    patient_medications = get_patient_medications(known_conditions)

    if not patient_medications:
        return {
            "treatments": treatments,
            "interactions": [],
            "warnings": [],
            "patient_medications": [],
        }

    # Check for interactions
    interactions = check_interactions(treatments, patient_medications)

    # Filter severe interactions and generate warnings
    filtered_treatments, warnings = filter_severe_interactions(treatments, interactions)

    # Convert interactions to serializable dicts
    interaction_dicts = [
        {
            "drug_in_treatment": i.drug_in_treatment,
            "drug_in_patient_meds": i.drug_in_patient_meds,
            "severity": i.severity,
            "description": i.description,
            "recommendation": i.recommendation,
        }
        for i in interactions
    ]

    logger.info(
        "Drug interaction check: %d treatments checked, %d interactions found (%d severe)",
        len(treatments),
        len(interactions),
        sum(1 for i in interactions if i.severity == "severe"),
    )

    return {
        "treatments": filtered_treatments,
        "interactions": interaction_dicts,
        "warnings": warnings,
        "patient_medications": patient_medications,
    }
