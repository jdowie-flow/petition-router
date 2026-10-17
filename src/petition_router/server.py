"""The local web server behind the labelling and results pages."""

import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import petitions as data
from .results import Labels, load_runs, spreadsheet, summarise

app = FastAPI(title="Petition Router")
# Only answer requests addressed to this machine, so a web page can't reach the
# server through a hostname it controls (DNS rebinding)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
app.state.on_finished = None  # `make` sets this to carry on once the last label is saved
saving = threading.Lock()  # requests run in parallel threads; labels are saved one at a time
FIXED = "Your labels are fixed, because you have finished labelling."


class Label(BaseModel):
    department: str
    seconds: float | None = None  # how long the petition was on screen


def load():
    try:
        return data.load()
    except FileNotFoundError:
        raise HTTPException(404, "No petitions yet. Run make first.") from None


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@app.get("/api/labelling")
def labelling():
    """The petitions to label, with nothing that gives away an answer."""
    petitions, departments = load()
    labels = Labels.load()
    return {
        "departments": departments,
        "petitions": [
            {"id": p.id, "title": p.title, "background": p.background, "details": p.details}
            for p in data.sample(petitions, labels.departments)
        ],
        "labels": labels.departments,
        "agreed": labels.agreed,
        "finished": labels.finished,
    }


@app.put("/api/agreement")
def agree():
    """Record when the rules on the first page were agreed to. The first time is kept."""
    with saving:
        labels = Labels.load()
        if labels.finished:
            raise HTTPException(409, FIXED)
        labels.agreed = labels.agreed or now()
        labels.save()
    return {"agreed": labels.agreed}


@app.put("/api/labels/{petition_id}")
def save_label(petition_id: int, label: Label):
    petitions, departments = load()
    with saving:
        labels = Labels.load()
        if labels.finished:
            raise HTTPException(409, FIXED)
        if not labels.agreed:  # e.g. a tab left open from before the first page existed
            raise HTTPException(409, "Reload this page, then agree to the rules to carry on.")
        sample = data.sample(petitions, labels.departments)
        if petition_id not in {p.id for p in sample}:
            raise HTTPException(404, "That petition is not one of the ones to label.")
        if label.department not in departments:
            raise HTTPException(422, f"There is no department called {label.department}.")
        labels.departments[petition_id] = label.department
        labels.seconds.setdefault(petition_id, label.seconds)  # keep the first look's time
        if all(p.id in labels.departments for p in sample):
            labels.finished = now()
        labels.save()
    if labels.finished and app.state.on_finished:
        app.state.on_finished()
    return {"labelled": len(labels.departments), "finished": labels.finished}


def finished_labels(petitions) -> Labels:
    """The labels, once labelling is finished. The results stay closed until then."""
    labels = Labels.load()
    if not labels.finished:
        sample = data.sample(petitions, labels.departments)
        done = sum(p.id in labels.departments for p in sample)
        raise HTTPException(
            409, f"You've labelled {done} of {len(sample)} petitions. Finish labelling first."
        )
    return labels


@app.get("/api/results")
def results():
    petitions, departments = load()
    return summarise(petitions, departments, load_runs(), finished_labels(petitions))


@app.get("/api/results.csv")
def results_spreadsheet():
    """Every answer, one petition to a row, to open in a spreadsheet."""
    petitions, _ = load()
    labels = finished_labels(petitions)
    return Response(
        spreadsheet(petitions, load_runs(), labels),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="petition-router-results.csv"'},
    )


# Serve the built pages as well, so the dashboard needs only one process
if Path("web/dist").is_dir():
    app.mount("/", StaticFiles(directory="web/dist", html=True))
