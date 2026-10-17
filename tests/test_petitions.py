import json
from dataclasses import asdict

import httpx
from fakes import make_petitions

from petition_router.petitions import SOURCE, download, sample

HO = {
    "acronym": "HO",
    "name": "Home Office",
    "url": "https://www.gov.uk/government/organisations/home-office",
}
DFE = {"acronym": "DfE", "name": "Department for Education", "url": "https://www.gov.uk/"}


def api_petition(pid: int, departments: list[dict]) -> dict:
    """One petition, shaped like the real API's."""
    return {
        "type": "petition",
        "id": pid,
        "attributes": {
            "action": f"Petition {pid}",
            "background": "Why it matters.",
            "additional_details": None,
            "created_at": "2025-03-01T10:00:00.000Z",
            "government_response_at": "2025-06-12T09:30:00.000Z",
            "creator_name": "A Petitioner",
            "government_response": {"summary": "The Home Office has considered this petition."},
            "departments": departments,
        },
    }


def test_download_keeps_only_the_petitions_own_words():
    pages = {
        SOURCE: {
            "links": {"next": SOURCE + "&page=2"},
            "data": [api_petition(1, [HO]), api_petition(2, [])],
        },
        SOURCE + "&page=2": {"links": {"next": None}, "data": [api_petition(3, [DFE, HO])]},
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=pages[str(request.url)])
    )

    petitions, departments, skipped = download(httpx.Client(transport=transport), pause=0)

    assert [p.id for p in petitions] == [1, 3]
    assert skipped == 1  # petition 2 has no department listed
    assert petitions[1].departments == ["DfE", "HO"]
    assert petitions[1].responded == "2025-06-12"
    assert departments == {"HO": "Home Office", "DfE": "Department for Education"}
    saved = json.dumps([asdict(p) for p in petitions])
    assert "A Petitioner" not in saved
    assert "considered this petition" not in saved  # the response would give the answer away


def test_a_petition_that_turns_up_twice_is_kept_once():
    pages = {
        SOURCE: {"links": {"next": SOURCE + "&page=2"}, "data": [api_petition(1, [HO])]},
        SOURCE + "&page=2": {"links": {"next": None}, "data": [api_petition(1, [HO])]},
    }
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=pages[str(request.url)])
    )
    petitions, _, _ = download(httpx.Client(transport=transport), pause=0)
    assert [p.id for p in petitions] == [1]


def test_sample_ignores_input_order():
    petitions = make_petitions()
    assert len(sample(petitions)) == 100
    assert sample(petitions) == sample(petitions[::-1])


def test_labelled_petitions_stay_in_the_sample():
    older = make_petitions()
    labelled = {p.id for p in sample(older)[:60]}
    newer = older + make_petitions(first_id=1000)

    picked = {p.id for p in sample(newer, labelled)}

    assert len(picked) == 100
    assert labelled <= picked
