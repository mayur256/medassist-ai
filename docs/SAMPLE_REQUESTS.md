# MedAssist-CDSS — Sample Request Bodies

## Endpoint: `POST /diagnose`
## Header: `X-API-Key: <your-api-key>`

---

## 1. Cardiac Symptoms (Male, 52, India)

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
