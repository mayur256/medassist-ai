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


def apply_compliance(
    treatments: list[str],
    symptoms: list[str],
    raw_text: str,
    country: str,
) -> dict:
    """Apply compliance rules. Returns {treatments, red_flags}."""
    filtered_treatments = filter_restricted_drugs(treatments, country)
    red_flags = detect_red_flags(symptoms, raw_text)
    return {"treatments": filtered_treatments, "red_flags": red_flags}
