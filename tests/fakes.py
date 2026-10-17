"""Made-up petitions and a fake model, so the tests need no network or API key."""

import json
from types import SimpleNamespace

from petition_router.petitions import Petition

DEPARTMENTS = {
    "DfE": "Department for Education",
    "DfT": "Department for Transport",
    "DHSC": "Department of Health and Social Care",
    "HO": "Home Office",
}
WORDS = {
    "DfE": ["school", "teachers", "pupils", "exams", "university"],
    "DfT": ["railway", "roads", "buses", "drivers", "trains"],
    "DHSC": ["hospital", "nurses", "NHS", "patients", "GP"],
    "HO": ["police", "immigration", "visa", "crime", "asylum"],
}


def petition(
    i: int, title: str, *departments: str, response: str = "", responded: str = "2025-06-01"
) -> Petition:
    return Petition(i, title, "", "", responded, response or f"response-{i}", list(departments))


def make_petitions(per_department: int = 30, first_id: int = 1) -> list[Petition]:
    petitions = []
    for department, words in WORDS.items():
        for n in range(per_department):
            i = first_id + len(petitions)
            petitions.append(
                Petition(
                    id=i,
                    title=f"Petition {i} about {words[n % 5]}",
                    background=f"We want more {words[(n + 1) % 5]} and fewer {words[(n + 2) % 5]}.",
                    details="",
                    responded=f"{2024 + n % 3}-05-01",
                    response_hash=f"response-{i}",
                    departments=[department],
                )
            )
    return petitions


def reply(content: str):
    """Shaped like a LiteLLM response, as far as the router reads it."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def keyword_model(**call):
    """Answers by spotting a department's words."""
    text = call["messages"][-1]["content"]
    department = next(d for d, words in WORDS.items() if any(w in text for w in words))
    return reply(
        json.dumps({"department": department, "reason": f"It mentions {department} work."})
    )
