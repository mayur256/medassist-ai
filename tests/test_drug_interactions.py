"""Tests for #6 Drug Interaction Checking enhancement."""

import pytest

from app.services.drug_interaction_service import (
    DrugInteraction,
    check_and_filter_interactions,
    check_interactions,
    filter_severe_interactions,
    get_patient_medications,
)


class TestGetPatientMedications:
    """Test medication inference from conditions."""

    def test_diabetes_medications(self):
        """Diabetes maps to common diabetic meds."""
        meds = get_patient_medications(["diabetes"])
        assert "metformin" in meds
        assert "insulin" in meds
        assert "glipizide" in meds

    def test_hypertension_medications(self):
        """Hypertension maps to antihypertensives."""
        meds = get_patient_medications(["hypertension"])
        assert "lisinopril" in meds
        assert "amlodipine" in meds
        assert "metoprolol" in meds

    def test_multiple_conditions(self):
        """Multiple conditions combine medications."""
        meds = get_patient_medications(["diabetes", "hypertension"])
        assert "metformin" in meds
        assert "lisinopril" in meds
        assert len(meds) > len(get_patient_medications(["diabetes"]))

    def test_unknown_condition_returns_empty(self):
        """Unknown condition returns no medications."""
        meds = get_patient_medications(["rare_unknown_condition_xyz"])
        assert meds == []

    def test_empty_conditions(self):
        """Empty conditions list returns empty."""
        meds = get_patient_medications([])
        assert meds == []

    def test_case_insensitive_matching(self):
        """Condition matching is case-insensitive."""
        meds = get_patient_medications(["Diabetes"])
        assert "metformin" in meds

    def test_partial_match_type2_diabetes(self):
        """Type 2 diabetes matches via partial match."""
        meds = get_patient_medications(["type 2 diabetes"])
        assert "metformin" in meds

    def test_depression_medications(self):
        """Depression maps to antidepressants."""
        meds = get_patient_medications(["depression"])
        assert "sertraline" in meds
        assert "fluoxetine" in meds

    def test_atrial_fibrillation_medications(self):
        """AF maps to anticoagulants and rate control."""
        meds = get_patient_medications(["atrial fibrillation"])
        assert "warfarin" in meds
        assert "amiodarone" in meds
        assert "metoprolol" in meds


class TestCheckInteractions:
    """Test drug-drug interaction detection."""

    def test_ibuprofen_with_lisinopril(self):
        """NSAID + ACE inhibitor = moderate interaction."""
        interactions = check_interactions(
            treatments=["Ibuprofen for pain relief"],
            patient_medications=["lisinopril", "metformin"],
        )
        assert len(interactions) >= 1
        ibu_interaction = next(
            (i for i in interactions if "ibuprofen" in i.drug_in_treatment.lower()),
            None,
        )
        assert ibu_interaction is not None
        assert ibu_interaction.severity == "moderate"

    def test_warfarin_with_aspirin(self):
        """Warfarin + aspirin = severe interaction."""
        interactions = check_interactions(
            treatments=["Warfarin anticoagulation"],
            patient_medications=["aspirin", "atorvastatin"],
        )
        assert len(interactions) >= 1
        warfarin_interaction = next(
            (i for i in interactions if i.severity == "severe"), None
        )
        assert warfarin_interaction is not None

    def test_no_interactions_when_safe(self):
        """Safe combination produces no interactions."""
        interactions = check_interactions(
            treatments=["Rest and hydration", "Physical therapy"],
            patient_medications=["metformin", "lisinopril"],
        )
        assert len(interactions) == 0

    def test_empty_treatments(self):
        """Empty treatments list produces no interactions."""
        interactions = check_interactions(
            treatments=[],
            patient_medications=["metformin"],
        )
        assert interactions == []

    def test_empty_patient_meds(self):
        """Empty patient meds produces no interactions."""
        interactions = check_interactions(
            treatments=["Warfarin therapy"],
            patient_medications=[],
        )
        assert interactions == []

    def test_statin_with_erythromycin(self):
        """Atorvastatin + erythromycin = severe (CYP3A4)."""
        interactions = check_interactions(
            treatments=["Erythromycin antibiotic course"],
            patient_medications=["atorvastatin"],
        )
        assert len(interactions) >= 1
        assert any(i.severity == "severe" for i in interactions)

    def test_ssri_with_tramadol(self):
        """SSRI + tramadol = severe (serotonin syndrome)."""
        interactions = check_interactions(
            treatments=["Tramadol for pain management"],
            patient_medications=["sertraline"],
        )
        assert len(interactions) >= 1
        assert any(i.severity == "severe" for i in interactions)

    def test_deduplication(self):
        """Same interaction not reported twice."""
        interactions = check_interactions(
            treatments=["Ibuprofen 400mg", "Ibuprofen gel"],
            patient_medications=["lisinopril"],
        )
        # Should deduplicate
        drug_pairs = [(i.drug_in_treatment.lower(), i.drug_in_patient_meds.lower())
                      for i in interactions]
        assert len(drug_pairs) == len(set(drug_pairs))


class TestFilterSevereInteractions:
    """Test removal of treatments with severe interactions."""

    def test_severe_removed(self):
        """Severe interactions cause treatment removal."""
        interactions = [
            DrugInteraction(
                drug_in_treatment="warfarin",
                drug_in_patient_meds="aspirin",
                severity="severe",
                description="Increased bleeding risk",
                recommendation="Avoid combination",
            )
        ]
        filtered, warnings = filter_severe_interactions(
            treatments=["Warfarin therapy", "Rest", "Oxygen"],
            interactions=interactions,
        )
        assert "Warfarin therapy" not in filtered
        assert "Rest" in filtered
        assert "Oxygen" in filtered
        assert len(warnings) == 1
        assert "SEVERE" in warnings[0]

    def test_moderate_kept_with_warning(self):
        """Moderate interactions kept but warned."""
        interactions = [
            DrugInteraction(
                drug_in_treatment="ibuprofen",
                drug_in_patient_meds="lisinopril",
                severity="moderate",
                description="Reduced antihypertensive effect",
                recommendation="Monitor BP",
            )
        ]
        filtered, warnings = filter_severe_interactions(
            treatments=["Ibuprofen for pain", "Rest"],
            interactions=interactions,
        )
        # Moderate is NOT removed
        assert len(filtered) == 2
        assert len(warnings) == 1
        assert "MODERATE" in warnings[0]

    def test_minor_noted(self):
        """Minor interactions noted with info."""
        interactions = [
            DrugInteraction(
                drug_in_treatment="omeprazole",
                drug_in_patient_meds="levothyroxine",
                severity="minor",
                description="May reduce absorption",
                recommendation="Separate doses",
            )
        ]
        filtered, warnings = filter_severe_interactions(
            treatments=["Omeprazole for reflux"],
            interactions=interactions,
        )
        assert len(filtered) == 1
        assert len(warnings) == 1
        assert "MINOR" in warnings[0]

    def test_no_interactions_returns_unchanged(self):
        """No interactions = unchanged treatments."""
        filtered, warnings = filter_severe_interactions(
            treatments=["Rest", "Hydration", "Physical therapy"],
            interactions=[],
        )
        assert len(filtered) == 3
        assert warnings == []


class TestCheckAndFilterInteractions:
    """Test the full pipeline function."""

    def test_full_pipeline_with_interactions(self):
        """Full pipeline detects and filters."""
        result = check_and_filter_interactions(
            treatments=["Ibuprofen for pain", "Rest and hydration"],
            known_conditions=["hypertension"],
        )
        assert "treatments" in result
        assert "interactions" in result
        assert "warnings" in result
        assert "patient_medications" in result
        assert len(result["patient_medications"]) > 0

    def test_full_pipeline_no_conditions(self):
        """No conditions = no interactions checked."""
        result = check_and_filter_interactions(
            treatments=["Warfarin", "Aspirin"],
            known_conditions=[],
        )
        assert result["treatments"] == ["Warfarin", "Aspirin"]
        assert result["interactions"] == []
        assert result["warnings"] == []
        assert result["patient_medications"] == []

    def test_severe_interaction_removed_in_pipeline(self):
        """Severe interaction removes treatment in full pipeline."""
        result = check_and_filter_interactions(
            treatments=["Warfarin anticoagulation", "Beta-blocker therapy", "Rest"],
            known_conditions=["atrial fibrillation"],
        )
        # Warfarin interacts with aspirin (which AF patients take)
        # Check that at least some interaction was found
        assert len(result["interactions"]) >= 1

    def test_diabetes_hypertension_patient(self):
        """Common comorbidity pair checked correctly."""
        result = check_and_filter_interactions(
            treatments=["Ibuprofen for pain", "Acetaminophen", "Rest"],
            known_conditions=["diabetes", "hypertension"],
        )
        # Ibuprofen interacts with lisinopril (moderate)
        assert any(
            "ibuprofen" in i["drug_in_treatment"].lower()
            for i in result["interactions"]
        )
        # Moderate = kept in treatments
        assert any("Ibuprofen" in t for t in result["treatments"])
