"""Tests for #7 Severity Triage / Urgency Score enhancement."""

import pytest

from app.services.compliance_engine import calculate_urgency_score, apply_compliance


class TestUrgencyScoreCalculation:
    """Test the urgency scoring formula."""

    def test_baseline_no_risk_factors(self):
        """No red flags, young patient, no comorbidities → score 1."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=30,
            known_conditions=[],
            raw_text="mild headache for 2 days",
        )
        assert score == 1
        assert rationale == "routine presentation"

    def test_single_red_flag(self):
        """One red flag adds 1 point → score 2."""
        score, rationale = calculate_urgency_score(
            red_flags=["chest pain"],
            patient_age=30,
            known_conditions=[],
            raw_text="chest pain",
        )
        assert score == 2
        assert "1 red flag" in rationale

    def test_multiple_red_flags_capped_at_3(self):
        """Multiple red flags add max 3 points."""
        score, rationale = calculate_urgency_score(
            red_flags=["chest pain", "shortness of breath", "loss of consciousness", "seizure"],
            patient_age=30,
            known_conditions=[],
            raw_text="chest pain with breathing issues",
        )
        # base(1) + red_flags(3) = 4
        assert score == 4
        assert "4 red flag" in rationale

    def test_elderly_patient_adds_point(self):
        """Age >= 60 adds 1 point."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=65,
            known_conditions=[],
            raw_text="mild cough",
        )
        assert score == 2
        assert "age 65" in rationale

    def test_pediatric_patient_adds_point(self):
        """Age <= 5 adds 1 point."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=3,
            known_conditions=[],
            raw_text="runny nose",
        )
        assert score == 2
        assert "age 3" in rationale

    def test_comorbidities_add_point(self):
        """2+ comorbidities add 1 point."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=45,
            known_conditions=["diabetes", "hypertension"],
            raw_text="mild fatigue",
        )
        assert score == 2
        assert "2 comorbidities" in rationale

    def test_single_comorbidity_no_extra_point(self):
        """1 comorbidity does NOT add a point."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=45,
            known_conditions=["diabetes"],
            raw_text="mild fatigue",
        )
        assert score == 1

    def test_severity_keywords_add_point(self):
        """Severity keywords in text add 1 point."""
        score, rationale = calculate_urgency_score(
            red_flags=[],
            patient_age=35,
            known_conditions=[],
            raw_text="severe headache, worst pain of my life",
        )
        assert score == 2
        assert "severity indicators" in rationale

    def test_max_score_capped_at_5(self):
        """Score cannot exceed 5."""
        score, rationale = calculate_urgency_score(
            red_flags=["chest pain", "shortness of breath", "loss of consciousness", "seizure"],
            patient_age=70,
            known_conditions=["diabetes", "hypertension", "COPD"],
            raw_text="sudden severe chest pain, worst ever",
        )
        # base(1) + red_flags(3) + age(1) + comorbidities(1) + severity(1) = 8 → capped at 5
        assert score == 5

    def test_combined_moderate_risk(self):
        """Typical moderate case: 1 red flag + elderly."""
        score, rationale = calculate_urgency_score(
            red_flags=["chest pain"],
            patient_age=62,
            known_conditions=["hypertension"],
            raw_text="chest pain for 1 hour",
        )
        # base(1) + red_flag(1) + age(1) = 3
        assert score == 3

    def test_zero_age_no_age_bonus(self):
        """Age 0 (unspecified) should not add age bonus."""
        score, _ = calculate_urgency_score(
            red_flags=[],
            patient_age=0,
            known_conditions=[],
            raw_text="cough",
        )
        assert score == 1


class TestUrgencyInComplianceOutput:
    """Test that apply_compliance returns urgency fields."""

    def test_compliance_includes_urgency(self):
        result = apply_compliance(
            treatments=["rest"],
            symptoms=["chest pain"],
            raw_text="chest pain for 2 days",
            country="India",
            patient_age=55,
            known_conditions=["diabetes", "hypertension"],
        )
        assert "urgency_score" in result
        assert "urgency_rationale" in result
        assert result["urgency_score"] >= 1
        assert result["urgency_score"] <= 5

    def test_compliance_urgency_with_red_flags(self):
        result = apply_compliance(
            treatments=[],
            symptoms=["chest pain", "shortness of breath"],
            raw_text="severe chest pain and shortness of breath",
            country="US",
            patient_age=65,
            known_conditions=["diabetes", "CAD"],
        )
        # Should be high urgency: 2 red flags + elderly + comorbidities + severity
        assert result["urgency_score"] >= 4

    def test_compliance_backward_compatible(self):
        """apply_compliance still works without patient_age/known_conditions."""
        result = apply_compliance(
            treatments=["aspirin"],
            symptoms=["headache"],
            raw_text="mild headache",
            country="UK",
        )
        assert result["urgency_score"] == 1
        assert result["urgency_rationale"] == "routine presentation"


class TestUrgencyInResponse:
    """Test urgency fields in the API response model."""

    def test_response_model_has_urgency(self):
        from app.models.response import DiagnoseResponse
        resp = DiagnoseResponse(urgency_score=4, urgency_rationale="3 red flag(s); age 70")
        assert resp.urgency_score == 4
        assert resp.urgency_rationale == "3 red flag(s); age 70"

    def test_response_model_default_urgency(self):
        from app.models.response import DiagnoseResponse
        resp = DiagnoseResponse()
        assert resp.urgency_score == 1
        assert resp.urgency_rationale == ""

    def test_urgency_score_validation_bounds(self):
        from pydantic import ValidationError
        from app.models.response import DiagnoseResponse

        with pytest.raises(ValidationError):
            DiagnoseResponse(urgency_score=0)

        with pytest.raises(ValidationError):
            DiagnoseResponse(urgency_score=6)
