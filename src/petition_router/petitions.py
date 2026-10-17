"""Petitions to Parliament that got a government response.

Source: https://petition.parliament.uk, under the Open Parliament Licence v3.0.
"""

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

SOURCE = "https://petition.parliament.uk/petitions.json?state=with_response"
DATA_FILE = Path("data/petitions.json")
SAMPLE_SIZE = 100


@dataclass
class Petition:
    id: int
    title: str
    background: str
    details: str
    responded: str  # date of the government response
    response_hash: str  # identifies the response text, which is shared by near-duplicates
    departments: list[str]  # acronyms, as tagged by the petitions team

    @property
    def text(self) -> str:
        return "\n\n".join(part for part in (self.title, self.background, self.details) if part)


def download(client: httpx.Client | None = None, pause: float = 0.5):
    """Fetch every page of petitions with a government response.

    Only the petition's own words are kept. The petitioner's name is dropped, and so
    is the government's response, which would give the department away.
    """
    client = client or httpx.Client(timeout=30)
    petitions: dict[int, Petition] = {}  # by id: a petition can turn up twice if pages shift
    departments: dict[str, str] = {}
    skipped = 0
    url = SOURCE
    while url:
        page = client.get(url).raise_for_status().json()
        for item in page["data"]:
            fields = item["attributes"]
            if not fields["departments"]:
                skipped += 1
                continue
            departments.update((d["acronym"], d["name"]) for d in fields["departments"])
            response = fields["government_response"]["summary"].strip()
            petitions[item["id"]] = Petition(
                id=item["id"],
                title=fields["action"],
                background=fields["background"] or "",
                details=fields["additional_details"] or "",
                responded=fields["government_response_at"][:10],
                response_hash=hashlib.sha256(response.encode()).hexdigest()[:12],
                departments=[d["acronym"] for d in fields["departments"]],
            )
        url = page["links"]["next"]
        time.sleep(pause)
    return list(petitions.values()), departments, skipped


def save(petitions: list[Petition], departments: dict[str, str], path: Path = DATA_FILE):
    data = {
        # A to Z, ignoring case: the order the model sees them in, and the labelling page
        "departments": dict(sorted(departments.items(), key=lambda d: d[0].lower())),
        "petitions": [asdict(p) for p in petitions],
    }
    write_json(path, data)


def write_json(path: Path, data):
    """Write to a temporary file, then swap it in, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    temporary.replace(path)


def load(path: Path = DATA_FILE) -> tuple[list[Petition], dict[str, str]]:
    data = json.loads(path.read_text())
    return [Petition(**p) for p in data["petitions"]], data["departments"]


def sample(petitions: list[Petition], labelled=()) -> list[Petition]:
    """The 100 petitions to label by hand, picked at random.

    Each petition's place in the shuffle comes from a random number seeded with its
    id, so the pick is the same every time. Petitions already labelled keep their
    places, even if newer petitions are downloaded later.
    """

    def place(petition):
        return random.Random(petition.id).random()

    shuffled = sorted(petitions, key=place)
    kept = [p for p in shuffled if p.id in labelled][:SAMPLE_SIZE]
    rest = [p for p in shuffled if p.id not in labelled][: SAMPLE_SIZE - len(kept)]
    return sorted(kept + rest, key=place)
