import csv
import io

import pytest
from conftest import finish_labelling
from fastapi.testclient import TestClient

from petition_router import petitions as data
from petition_router.results import Labels
from petition_router.server import app


@pytest.fixture
def client(project):
    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def agreed(client):
    """Agree to the rules on the first page, which comes before any labelling."""
    client.put("/api/agreement")


def test_labelling_page_is_blind(client):
    page = client.get("/api/labelling").json()
    assert len(page["petitions"]) == 100
    assert all(set(p) == {"id", "title", "background", "details"} for p in page["petitions"])
    assert page["labels"] == {}
    assert page["agreed"] is page["finished"] is None


def test_agreeing_to_the_rules_is_recorded_once(client):
    agreed = client.put("/api/agreement").json()["agreed"]
    assert client.get("/api/labelling").json()["agreed"] == agreed

    labels = Labels.load()
    labels.agreed = "2026-10-01T09:00:00+00:00"
    labels.save()
    assert client.put("/api/agreement").json()["agreed"] == "2026-10-01T09:00:00+00:00"


def test_labels_are_only_saved_after_agreeing_to_the_rules(client):
    first = client.get("/api/labelling").json()["petitions"][0]["id"]
    refused = client.put(f"/api/labels/{first}", json={"department": "HO", "seconds": 8.5})
    assert refused.status_code == 409
    assert "agree to the rules" in refused.json()["detail"]
    assert Labels.load().departments == {}


@pytest.mark.usefixtures("agreed")
def test_save_label_with_its_time(client):
    first = client.get("/api/labelling").json()["petitions"][0]["id"]
    saved = client.put(f"/api/labels/{first}", json={"department": "HO", "seconds": 8.5}).json()
    assert saved == {"labelled": 1, "finished": None}
    page = client.get("/api/labelling").json()
    assert page["labels"] == {str(first): "HO"}
    assert Labels.load().seconds == {first: 8.5}
    assert page["agreed"]  # saving a label keeps the agreement


@pytest.mark.usefixtures("agreed")
def test_a_relabelled_petition_keeps_its_first_time(client):
    first = client.get("/api/labelling").json()["petitions"][0]["id"]
    client.put(f"/api/labels/{first}", json={"department": "HO", "seconds": 30.0})
    client.put(f"/api/labels/{first}", json={"department": "DfE", "seconds": 2.0})
    labels = Labels.load()
    assert (labels.departments[first], labels.seconds[first]) == ("DfE", 30.0)


@pytest.mark.usefixtures("agreed")
def test_label_validation(client):
    sampled = {p["id"] for p in client.get("/api/labelling").json()["petitions"]}
    outside = next(i for i in range(1, 121) if i not in sampled)
    assert client.put(f"/api/labels/{outside}", json={"department": "HO"}).status_code == 404
    assert client.put(f"/api/labels/{min(sampled)}", json={"department": "XYZ"}).status_code == 422


@pytest.mark.usefixtures("agreed")
def test_the_last_label_finishes_and_locks_labelling(client, monkeypatch):
    finished = []
    monkeypatch.setattr(app.state, "on_finished", lambda: finished.append(True))
    ids = [p["id"] for p in client.get("/api/labelling").json()["petitions"]]
    for petition_id in ids[:-1]:
        client.put(f"/api/labels/{petition_id}", json={"department": "HO"})
    assert client.get("/api/results").status_code == 409
    assert not finished

    last = client.put(f"/api/labels/{ids[-1]}", json={"department": "HO"}).json()
    assert last["finished"]
    assert finished == [True]  # so make can carry on to the models
    assert client.get("/api/results").status_code == 200
    assert client.put(f"/api/labels/{ids[0]}", json={"department": "DfE"}).status_code == 409
    assert client.put("/api/agreement").status_code == 409


def test_labels_stay_locked_after_a_new_download(client):
    finish_labelling()
    petitions, departments = data.load()
    data.save(petitions[1:], departments)
    unlabelled = client.get("/api/labelling").json()["petitions"][0]["id"]
    assert client.put(f"/api/labels/{unlabelled}", json={"department": "HO"}).status_code == 409


def test_results_download_as_a_spreadsheet_once_labelling_is_finished(client):
    assert client.get("/api/results.csv").status_code == 409
    finish_labelling()
    response = client.get("/api/results.csv")
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text.lstrip("\ufeff"))))
    assert len(rows) == 1 + 120  # a header, then every petition


def test_only_answers_requests_addressed_to_this_machine(project):
    elsewhere = TestClient(app, base_url="http://rebinding.example")
    assert elsewhere.get("/api/labelling").status_code == 400


def test_no_data_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = TestClient(app, base_url="http://127.0.0.1").get("/api/results")
    assert response.status_code == 404
    assert "No petitions yet" in response.json()["detail"]
