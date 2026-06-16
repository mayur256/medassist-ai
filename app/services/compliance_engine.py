"""Compliance engine: country-specific drug restrictions and red flag detection."""

# Country-specific restricted/banned substances
RESTRICTED_DRUGS: dict[str, set[str]] = {
    "India": {
        "nimesulide (pediatric)", "cisapride", "phenylpropanolamine",
        "rosiglitazone", "sibutramine", "gatifloxacin",
    },
    "US": {
        "thalidomide (OTC)", "phenacetin", "methaqualone",
        "cisapride", "rofecoxib", "valdecoxib",
    },
    "UK": {
        "co-proxamol", "rosiglitazone", "cisapride",
        "sibutramine", "rimonabant", "phenylpropanolamine",
    },
}

# Emergency symptoms that require immediate escalation
RED_FLAG_SYMPTOMS = [
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "sudden severe headache",
    "loss of consciousness",
    "seizure",
    "stroke symptoms",
    "slurred speech",
    "facial drooping",
    "sudden numbness",
    "coughing blood",
    "vomiting blood",
    "suicidal ideation",
    "self-harm",
    "anaphylaxis",
    "severe allergic reaction",
    "sudden vision loss",
    "severe abdominal pain",
    "high fever with rash",
    "uncontrolled bleeding",
]


def detect_red_flags(symptoms: list[str], raw_text: str = "") -> list[str]:
    """Detect emergency symptoms that require escalation."""
    flags = []
    combined = " ".join(symptoms).lower() + " " + raw_text.lower()
    for flag in RED_FLAG_SYMPTOMS:
        if flag in combined:
            flags.append(flag)
    return flags


def filter_restricted_drugs(treatments: list[str], country: str) -> list[str]:
    """Remove treatments that mention country-restricted substances."""
    restricted = RESTRICTED_DRUGS.get(country, set())
    if not restricted:
        return treatments
    filtered = []
    for t in treatments:
        t_lower = t.lower()
        if not any(drug.lower() in t_lower for drug in restricted):
            filtered.append(t)
    return filtered


# Severity keywords in patient text
SEVERITY_KEYWORDS = ["severe", "worst", "unbearable", "excruciating", "sudden", "acute", "emergency"]


def calculate_urgency_score(
    red_flags: list[str],
    patient_age: int = 0,
    known_conditions: list[str] | None = None,
    raw_text: str = "",
) -> tuple[int, str]:
    """Calculate 1-5 urgency score based on clinical factors.

    Scoring:
    - Red flags: +1 per flag (max +3)
    - Age risk (>60 or <5): +1
    - Comorbidities (>=2): +1
    - Severity keywords: +1
    - Base: 1
    Returns (score clamped 1-5, rationale string).
    """
    conditions = known_conditions or []
    score = 1
    reasons = []

    # Red flags (biggest signal)
    if red_flags:
        points = min(len(red_flags), 3)
        score += points
        reasons.append(f"{len(red_flags)} red flag(s)")

    # Age risk
    if patient_age >= 60 or (0 < patient_age <= 5):
        score += 1
        reasons.append(f"age {patient_age} (high-risk group)")

    # Comorbidities
    if len(conditions) >= 2:
        score += 1
        reasons.append(f"{len(conditions)} comorbidities")

    # Severity keywords
    text_lower = raw_text.lower()
    if any(kw in text_lower for kw in SEVERITY_KEYWORDS):
        score += 1
        reasons.append("severity indicators in description")

    score = max(1, min(5, score))
    rationale = "; ".join(reasons) if reasons else "routine presentation"
    return score, rationale


def apply_compliance(
    treatments: list[str],
    symptoms: list[str],
    raw_text: str,
    country: str,
    patient_age: int = 0,
    known_conditions: list[str] | None = None,
) -> dict:
    """Apply compliance rules. Returns {treatments, red_flags, urgency_score, urgency_rationale}."""
    filtered_treatments = filter_restricted_drugs(treatments, country)
    red_flags = detect_red_flags(symptoms, raw_text)
    urgency_score, urgency_rationale = calculate_urgency_score(
        red_flags=red_flags,
        patient_age=patient_age,
        known_conditions=known_conditions or [],
        raw_text=raw_text,
    )
    return {
        "treatments": filtered_treatments,
        "red_flags": red_flags,
        "urgency_score": urgency_score,
        "urgency_rationale": urgency_rationale,
    }
