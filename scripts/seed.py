"""Seed database with sample patients."""

import asyncio

from app.db import Patient, async_session, init_db, engine

SAMPLE_PATIENTS = [
    {
        "name": "Rajesh Kumar",
        "age": 52,
        "gender": "male",
        "country": "India",
        "known_conditions": ["hypertension", "type 2 diabetes"],
        "allergies": ["aspirin"],
    },
    {
        "name": "Sarah Thompson",
        "age": 34,
        "gender": "female",
        "country": "UK",
        "known_conditions": ["asthma"],
        "allergies": ["sulfa drugs", "ibuprofen"],
    },
    {
        "name": "James Wilson",
        "age": 67,
        "gender": "male",
        "country": "US",
        "known_conditions": ["atrial fibrillation", "hyperlipidemia"],
        "allergies": ["penicillin"],
    },
    {
        "name": "Priya Sharma",
        "age": 28,
        "gender": "female",
        "country": "India",
        "known_conditions": [],
        "allergies": ["metronidazole"],
    },
    {
        "name": "Emily Carter",
        "age": 45,
        "gender": "female",
        "country": "US",
        "known_conditions": ["rheumatoid arthritis", "hypothyroidism"],
        "allergies": ["NSAIDs"],
    },
]


async def seed():
    await init_db()
    async with async_session() as db:
        for data in SAMPLE_PATIENTS:
            patient = Patient(**data)
            db.add(patient)
        await db.commit()
        print(f"✅ Seeded {len(SAMPLE_PATIENTS)} patients")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
