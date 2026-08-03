"""Tests for structured symptom timeline extraction (Enhancement #4)."""

import pytest

from app.services.ner_service import (
    SymptomEvent,
    _extract_onset,
    _extract_progression,
    extract_timeline,
    format_timeline_for_prompt,
)


# --- Tests for _extract_onset ---

class TestExtractOnset:
    def test_days_ago(self):
        assert _extract_onset("headache started 3 days ago") == "started 3 days ago"

    def test_weeks_ago(self):
        assert _extract_onset("pain for about 2 weeks ago") == "2 weeks ago"

    def test_for_duration(self):
        assert _extract_onset("cough for 5 days now") == "for 5 days"

    def test_since_last_week(self):
        assert _extract_onset("fever since last week") == "since last week"

    def test_since_yesterday(self):
        assert _extract_onset("nausea since yesterday") == "since yesterday"

    def test_started_days_ago(self):
        assert _extract_onset("it started 2 days ago") == "started 2 days ago"

    def test_started_last_monday(self):
        assert _extract_onset("symptoms started last Monday") == "started last Monday"

    def test_over_the_past_days(self):
        assert _extract_onset("getting worse over the past 3 days") == "over the past 3 days"

    def test_last_n_hours(self):
        assert _extract_onset("pain in the last 6 hours") == "the last 6 hours"

    def test_yesterday(self):
        assert _extract_onset("it happened yesterday around noon") == "yesterday"

    def test_this_morning(self):
        assert _extract_onset("woke up this morning with pain") == "this morning"

    def test_last_night(self):
        assert _extract_onset("started having chills last night") == "last night"

    def test_no_onset(self):
        assert _extract_onset("I have a headache and nausea") is None

    def test_months_ago(self):
        assert _extract_onset("back pain 6 months ago") == "6 months ago"

    def test_since_days_ago(self):
        assert _extract_onset("coughing since 4 days ago") == "since 4 days ago"


# --- Tests for _extract_progression ---

class TestExtractProgression:
    def test_worsening(self):
        assert _extract_progression("the pain is worsening") == "worsening"

    def test_getting_worse(self):
        assert _extract_progression("it's getting worse each day") == "worsening"

    def test_improving(self):
        assert _extract_progression("symptoms are improving") == "improving"

    def test_getting_better(self):
        assert _extract_progression("feeling is getting better") == "improving"

    def test_constant(self):
        assert _extract_progression("constant pain throughout the day") == "stable"

    def test_persistent(self):
        assert _extract_progression("persistent headache") == "stable"

    def test_intermittent(self):
        assert _extract_progression("intermittent chest pain") == "intermittent"

    def test_comes_and_goes(self):
        assert _extract_progression("the pain comes and goes") == "intermittent"

    def test_sudden(self):
        assert _extract_progression("sudden onset of severe pain") == "sudden onset"

    def test_gradual(self):
        assert _extract_progression("gradually developing weakness") == "gradual onset"

    def test_no_progression(self):
        assert _extract_progression("I have a headache") is None

    def test_on_and_off(self):
        assert _extract_progression("it's been on and off") == "intermittent"


# --- Tests for extract_timeline ---

class TestExtractTimeline:
    def test_single_symptom_with_onset(self):
        text = "I've had a headache for 3 days"
        symptoms = ["headache"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].symptom == "headache"
        assert timeline[0].onset == "for 3 days"

    def test_single_symptom_with_progression(self):
        text = "my headache is getting worse"
        symptoms = ["headache"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].symptom == "headache"
        assert timeline[0].progression == "worsening"

    def test_multiple_symptoms_same_sentence(self):
        text = "headache and nausea started 2 days ago"
        symptoms = ["headache", "nausea"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 2
        for event in timeline:
            assert event.onset == "started 2 days ago"

    def test_multiple_symptoms_different_temporal_context(self):
        text = "headache started 3 days ago. nausea began yesterday and is worsening"
        symptoms = ["headache", "nausea"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 2
        headache = next(e for e in timeline if e.symptom == "headache")
        nausea = next(e for e in timeline if e.symptom == "nausea")

        assert headache.onset == "started 3 days ago"
        assert nausea.onset == "yesterday"
        assert nausea.progression == "worsening"

    def test_symptom_with_both_onset_and_progression(self):
        text = "chest pain started 2 hours ago and is getting worse"
        symptoms = ["chest pain"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].symptom == "chest pain"
        assert timeline[0].onset == "started 2 hours ago"
        assert timeline[0].progression == "worsening"

    def test_no_temporal_info(self):
        text = "I have a headache and feel nauseous"
        symptoms = ["headache"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].onset is None
        assert timeline[0].progression is None

    def test_empty_text(self):
        timeline = extract_timeline("", ["headache"])
        assert timeline == []

    def test_empty_symptoms(self):
        timeline = extract_timeline("headache for 3 days", [])
        assert timeline == []

    def test_global_fallback_for_unmatched_symptoms(self):
        # Symptom not directly in any segment but text has global temporal info
        text = "I've been feeling unwell for 2 weeks. I have fatigue and dizziness"
        symptoms = ["fatigue", "dizziness"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 2
        # Both should get the global onset as fallback
        for event in timeline:
            assert event.onset == "for 2 weeks"

    def test_intermittent_pattern(self):
        text = "chest pain that comes and goes for 1 week"
        symptoms = ["chest pain"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].progression == "intermittent"
        assert timeline[0].onset == "for 1 week"

    def test_sudden_onset(self):
        text = "sudden severe headache started 1 hour ago"
        symptoms = ["headache"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].progression == "sudden onset"
        assert "1 hour" in (timeline[0].onset or "")

    def test_gradual_progression(self):
        text = "gradually worsening back pain over the past 2 months"
        symptoms = ["back pain"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].progression == "gradual onset"
        assert timeline[0].onset == "over the past 2 months"


# --- Tests for format_timeline_for_prompt ---

class TestFormatTimelineForPrompt:
    def test_empty_timeline(self):
        assert format_timeline_for_prompt([]) == ""

    def test_no_temporal_data(self):
        timeline = [SymptomEvent(symptom="headache", onset=None, progression=None)]
        assert format_timeline_for_prompt(timeline) == ""

    def test_single_event_with_onset(self):
        timeline = [SymptomEvent(symptom="headache", onset="3 days ago", progression=None)]
        result = format_timeline_for_prompt(timeline)

        assert "Symptom Timeline:" in result
        assert "headache" in result
        assert "onset: 3 days ago" in result

    def test_single_event_with_progression(self):
        timeline = [SymptomEvent(symptom="chest pain", onset=None, progression="worsening")]
        result = format_timeline_for_prompt(timeline)

        assert "chest pain" in result
        assert "progression: worsening" in result

    def test_full_event(self):
        timeline = [
            SymptomEvent(symptom="headache", onset="2 days ago", progression="worsening"),
        ]
        result = format_timeline_for_prompt(timeline)

        assert "headache" in result
        assert "onset: 2 days ago" in result
        assert "progression: worsening" in result

    def test_multiple_events(self):
        timeline = [
            SymptomEvent(symptom="headache", onset="3 days ago", progression="stable"),
            SymptomEvent(symptom="nausea", onset="yesterday", progression="worsening"),
        ]
        result = format_timeline_for_prompt(timeline)

        assert "headache" in result
        assert "nausea" in result
        assert "3 days ago" in result
        assert "yesterday" in result

    def test_mixed_events_some_without_temporal(self):
        timeline = [
            SymptomEvent(symptom="headache", onset="2 days ago", progression=None),
            SymptomEvent(symptom="nausea", onset=None, progression=None),
        ]
        # Should still produce output because at least one event has temporal data
        result = format_timeline_for_prompt(timeline)
        assert "Symptom Timeline:" in result
        assert "headache" in result


# --- Integration-style tests ---

class TestTimelineIntegration:
    """Tests that exercise the full flow from text to formatted output."""

    def test_complex_patient_narrative(self):
        text = (
            "I started having chest pain 3 days ago. "
            "It's been getting worse since yesterday. "
            "I also have shortness of breath that comes and goes."
        )
        symptoms = ["chest pain", "shortness of breath"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 2

        chest_pain = next(e for e in timeline if e.symptom == "chest pain")
        sob = next(e for e in timeline if e.symptom == "shortness of breath")

        assert chest_pain.onset is not None
        assert sob.progression == "intermittent"

        # Format should produce meaningful output
        formatted = format_timeline_for_prompt(timeline)
        assert "Symptom Timeline:" in formatted
        assert "chest pain" in formatted
        assert "shortness of breath" in formatted

    def test_migraine_vs_stroke_scenario(self):
        """Timeline patterns that help differentiate migraine from stroke."""
        text = "sudden severe headache started 30 minutes ago with no warning"
        symptoms = ["headache"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].progression == "sudden onset"
        assert "30 minutes" in (timeline[0].onset or "")

    def test_chronic_condition_scenario(self):
        text = "persistent back pain for 6 months, gradually getting worse"
        symptoms = ["back pain"]
        timeline = extract_timeline(text, symptoms)

        assert len(timeline) == 1
        assert timeline[0].onset == "for 6 months"
        assert timeline[0].progression == "gradual onset"

    def test_no_symptoms_provided(self):
        """Edge case: symptoms list is empty."""
        text = "headache for 3 days and getting worse"
        timeline = extract_timeline(text, [])
        assert timeline == []

    def test_symptoms_not_in_text(self):
        """Edge case: symptoms are from NER but not matching text exactly."""
        text = "I've been feeling sick for a week"
        # NER might extract a symptom not literally in the sentence segments
        symptoms = ["malaise"]
        timeline = extract_timeline(text, symptoms)

        # Should still produce a timeline entry with global fallback
        assert len(timeline) == 1
        assert timeline[0].symptom == "malaise"
        assert timeline[0].onset == "for a week" or timeline[0].onset is None
