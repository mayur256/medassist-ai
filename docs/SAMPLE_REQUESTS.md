# MedAssist-CDSS — Sample Request Bodies

**Updated:** 2026-08-03  
**Features:** Now includes suggested tests, urgency scoring, and patient history awareness

## Endpoint: `POST /diagnose`
## Header: `X-API-Key: <your-api-key>`

---

## Sample Response (Updated 2026-08-03)

Shows new features: suggested_tests, urgency_score, urgency_rationale

```json
{
  "status": "complete",
  "confidence": 0.85,
  "urgency_score": 4,
  "urgency_rationale": "Severe chest pain with cardiac risk factors (age 52, diabetes, hypertension) and aspirin allergy requires urgent evaluation",
  "differential_diagnosis": [
    {
      "condition": "Acute Coronary Syndrome (ACS)",
      "confidence": 0.8,
      "reasoning": "Classic presentation: severe substernal chest pain radiating to left arm with diaphoresis in a 52-year-old male with hypertension and diabetes"
    },
    {
      "condition": "Myocardial Infarction (MI)",
      "confidence": 0.75,
      "reasoning": "Similar presentation; urgency of presentation and risk profile suggest need for immediate cardiac workup"
    }
  ],
  "suggested_tests": [
    {
      "test": "ECG (12-lead)",
      "reasoning": "First-line test to identify ST-segment elevation or T-wave changes indicating acute MI"
    },
    {
      "test": "Troponin I/T",
      "reasoning": "Specific cardiac biomarker for myocardial necrosis; elevated levels confirm MI"
    },
    {
      "test": "Complete Blood Count (CBC)",
      "reasoning": "Rule out infectious causes; assess for leukocytosis"
    }
  ],
  "treatment_options": [
    "Immediate cardiology consultation",
    "Oxygen therapy if hypoxic",
    "Nitroglycerin (sublingual)",
    "Aspirin contraindicated (patient allergic) — consider clopidogrel or ticagrelor",
    "IV access for emergency intervention if needed"
  ],
  "red_flags": ["chest pain", "difficulty breathing"],
  "follow_up_questions": [],
  "disclaimer": "This is AI-assisted output and must be verified by a licensed medical professional."
}
```

---

## Input Examples

```json
{
  "patient": {
    "age": 52,
    "gender": "male",
    "country": "India",
    "known_conditions": ["hypertension", "type 2 diabetes"],
    "allergies": ["aspirin"]
  },
  "symptoms": "Severe chest pain radiating to left arm for the past 3 hours, accompanied by sweating and nausea"
}
```

---

## 2. Respiratory Symptoms (Female, 34, UK)

```json
{
  "patient": {
    "age": 34,
    "gender": "female",
    "country": "UK",
    "known_conditions": ["asthma"],
    "allergies": ["sulfa drugs", "ibuprofen"]
  },
  "symptoms": "Persistent dry cough for 2 weeks with mild fever, fatigue, and occasional shortness of breath at night"
}
```

---

## 3. Neurological Symptoms (Male, 67, US)

```json
{
  "patient": {
    "age": 67,
    "gender": "male",
    "country": "US",
    "known_conditions": ["atrial fibrillation", "hyperlipidemia"],
    "allergies": ["penicillin"]
  },
  "symptoms": "Sudden onset severe headache with blurred vision and slurred speech lasting 20 minutes"
}
```

---

## 4. Gastrointestinal Symptoms (Female, 28, India)

```json
{
  "patient": {
    "age": 28,
    "gender": "female",
    "country": "India",
    "known_conditions": [],
    "allergies": ["metronidazole"]
  },
  "symptoms": "Burning stomach pain after meals for 1 week, acid reflux, and occasional nausea in the morning"
}
```

---

## 5. Pediatric Case (Male, 6, US)

```json
{
  "patient": {
    "age": 6,
    "gender": "male",
    "country": "US",
    "known_conditions": [],
    "allergies": ["amoxicillin"]
  },
  "symptoms": "High fever for 3 days with sore throat, difficulty swallowing, and swollen neck glands"
}
```

---

## 6. Musculoskeletal Symptoms (Female, 45, UK)

```json
{
  "patient": {
    "age": 45,
    "gender": "female",
    "country": "UK",
    "known_conditions": ["rheumatoid arthritis"],
    "allergies": []
  },
  "symptoms": "Worsening joint pain and stiffness in both hands for 2 months, worse in the morning, with occasional swelling"
}
```

---

## 7. Mental Health + Physical (Male, 38, India)

```json
{
  "patient": {
    "age": 38,
    "gender": "male",
    "country": "India",
    "known_conditions": ["generalized anxiety disorder"],
    "allergies": []
  },
  "symptoms": "Palpitations, dizziness, and tingling in hands for 1 hour, feels like something terrible is about to happen"
}
```

---

## 8. Elderly Multi-Morbid (Female, 78, US)

```json
{
  "patient": {
    "age": 78,
    "gender": "female",
    "country": "US",
    "known_conditions": ["congestive heart failure", "chronic kidney disease", "osteoporosis"],
    "allergies": ["ACE inhibitors", "NSAIDs"]
  },
  "symptoms": "Increasing leg swelling for 5 days, shortness of breath when lying flat, and reduced urine output"
}
```
