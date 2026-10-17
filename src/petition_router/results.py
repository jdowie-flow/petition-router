"""Save runs and labels, and score them against each petition's department tags."""

import csv
import io
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median

import numpy as np

from .petitions import SAMPLE_SIZE, Petition, write_json
from .routers import Answer

RUNS = Path("results/runs")
LABELS = Path("results/my-labels.json")

# The last month of each model's training data, as Anthropic publishes it:
# https://support.claude.com/en/articles/8114494-how-up-to-date-is-claudes-training-data
# A model may have seen responses published up to the end of that month. To check another
# model for remembered answers, add its name, the part after any "/", and its cutoff.
TRAINING_CUTOFFS = {
    "claude-haiku-5-5": "2026-06",
    "claude-sonnet-5-5": "2026-06",
}


def start_run(router: str, reverse: bool, version: str | None) -> Path:
    """A new run file: a line describing the run, then a line per answer as it arrives."""
    created = datetime.now(UTC).strftime("%Y-%m-%d-%H%M%S-%f")
    slug = re.sub(r"[^a-z0-9.]+", "-", router.lower()) + ("-reversed" if reverse else "")
    path = RUNS / f"{created}-{slug}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    run = {"router": router, "reversed": reverse, "prompt": version, "created": created}
    path.write_text(json.dumps(run) + "\n")
    return path


def add_answer(path: Path, answer: Answer):
    with path.open("a") as file:
        file.write(json.dumps(asdict(answer)) + "\n")


def load_runs() -> list[dict]:
    """Every run, oldest first, with the answers saved so far and the file it's in."""
    runs = []
    for path in RUNS.glob("*.jsonl"):
        lines = []
        for line in path.read_text().splitlines():
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError:  # cut short when a run was stopped, so skip it
                continue
        if lines:
            answers = list({a["petition_id"]: a for a in lines[1:]}.values())  # once each
            runs.append(lines[0] | {"answers": answers, "path": path})
    return sorted(runs, key=lambda run: run["created"])


def complete(run: dict, petitions: list[Petition]) -> bool:
    """Whether the run has an answer for every petition in the current data."""
    answered = {a["petition_id"] for a in run["answers"]}
    return all(p.id in answered for p in petitions)


@dataclass
class Labels:
    """My labels. When the last one is saved, `finished` records the time and they lock."""

    departments: dict[int, str] = field(default_factory=dict)
    seconds: dict[int, float | None] = field(default_factory=dict)  # time taken over each
    finished: str | None = None
    agreed: str | None = None  # when the rules on the first page were agreed to

    @classmethod
    def load(cls) -> "Labels":
        if not LABELS.exists():
            return cls()
        data = json.loads(LABELS.read_text())
        if "labels" not in data:  # the first version saved a plain id-to-department map
            done = "before timings were saved" if len(data) >= SAMPLE_SIZE else None
            return cls({int(i): d for i, d in data.items()}, {}, done)
        entries = {int(i): entry for i, entry in data["labels"].items()}
        return cls(
            {i: entry["department"] for i, entry in entries.items()},
            {i: entry["seconds"] for i, entry in entries.items()},
            data["finished"],
            data.get("agreed"),  # labels saved before there was a first page have none
        )

    def save(self):
        entries = {
            str(i): {"department": department, "seconds": self.seconds.get(i)}
            for i, department in sorted(self.departments.items())
        }
        write_json(LABELS, {"agreed": self.agreed, "finished": self.finished, "labels": entries})


def bootstrap(values, groups=None) -> list[float]:
    """The mean, and a 95% interval from resampling the values 2,000 times.

    Values in the same group are resampled together. Petitions that got the same
    government response aren't independent, so they're grouped.
    """
    values = np.asarray(values, dtype=float)
    labels = np.arange(len(values)) if groups is None else groups
    group = np.unique(labels, return_inverse=True)[1]
    sums, sizes = np.bincount(group, weights=values), np.bincount(group)
    picks = np.random.default_rng(0).integers(0, len(sums), (2000, len(sums)))
    low, high = np.percentile(sums[picks].sum(axis=1) / sizes[picks].sum(axis=1), [2.5, 97.5])
    return [round(float(x), 4) for x in (values.mean(), low, high)]


def gap(values, groups, before) -> list[float]:
    """The mean of the values marked `before`, minus the mean of the rest, with a 95% interval.

    Resampled like `bootstrap`, so values in the same group stay together, even a group
    with some values before and some after.
    """
    values = np.asarray(values, dtype=float)
    before = np.asarray(before, dtype=bool)
    group = np.unique(groups, return_inverse=True)[1]
    count = group.max() + 1
    picks = np.random.default_rng(0).integers(0, count, (2000, count))
    means = []
    for side in (before, ~before):
        sums = np.bincount(group, weights=values * side, minlength=count)
        sizes = np.bincount(group, weights=side.astype(float), minlength=count)
        with np.errstate(divide="ignore", invalid="ignore"):  # a resample can miss a side
            means.append(sums[picks].sum(axis=1) / sizes[picks].sum(axis=1))
    low, high = np.nanpercentile(means[0] - means[1], [2.5, 97.5])
    estimate = values[before].mean() - values[~before].mean()
    return [round(float(x), 4) for x in (estimate, low, high)]


def latest(runs: list[dict], petitions: list[Petition]) -> tuple[dict, dict]:
    """Complete runs by (router, reversed), oldest first, and each router's newest one."""
    history = defaultdict(list)
    for run in runs:
        if complete(run, petitions):
            history[run["router"], run["reversed"]].append(run)
    newest = {name: kept[-1] for (name, reverse), kept in history.items() if not reverse}
    return history, newest


def summarise(petitions: list[Petition], departments: dict, runs: list[dict], labels) -> dict:
    gold = {p.id: p.departments for p in petitions}
    response = {p.id: p.response_hash for p in petitions}

    history, newest = latest(runs, petitions)
    answers = {name: by_id(run) for name, run in newest.items()}

    # router -> petition id -> was the answer one of the petition's tagged departments?
    right = {
        name: {i: a["department"] in gold[i] for i, a in run.items() if i in gold}
        for name, run in answers.items()
    }
    right = {name: hits for name, hits in right.items() if hits}  # skip runs on old data
    routers = sorted(
        (score(name, answers[name], right, petitions, response) for name in right),
        key=lambda row: row["accuracy"][0],
        reverse=True,
    )
    best_model = next((row["name"] for row in routers if row["name"] != "tfidf"), None)

    checks = []
    for name in right:
        version = newest[name]["prompt"]
        forward = [by_id(r) for r in history[name, False] if r["prompt"] == version]
        backward = [by_id(r) for r in history[name, True] if r["prompt"] == version]
        if name != "tfidf" and (len(forward) > 1 or backward):
            checks.append(consistency(name, forward, backward, gold, right[name]))

    return {
        "petitions": len(petitions),
        "departments": departments,
        "most_common": most_common(petitions),
        "routers": routers,
        "me": compare_with_me(labels, gold, answers, right, response),
        "consistency": checks,
        "by_department": by_department(petitions, right),
        "training_cutoffs": training_cutoffs(
            petitions, [row["name"] for row in routers], right, response
        ),
        "mixups": mixups(best_model, answers, right, petitions, labels.departments)
        if best_model
        else None,
    }


def by_id(run: dict) -> dict:
    return {a["petition_id"]: a for a in run["answers"]}


def spreadsheet(petitions: list[Petition], runs: list[dict], labels) -> str:
    """Every petition with its tags, the human label and each router's answer, as CSV."""
    answers = {name: by_id(run) for name, run in latest(runs, petitions)[1].items()}
    names = sorted(answers, key=lambda name: (name != "tfidf", name))  # the baseline first
    header = ["Petition", "Title", "Link", "Response date", "Tagged"]
    header += ["Human", "Human right", "Human seconds"]
    for name in names:
        short = "TF-IDF" if name == "tfidf" else name.split("/")[-1]
        header += [f"{short} answer", f"{short} right"]
        if name != "tfidf":
            header.append(f"{short} reason")

    rows = [header]
    for p in petitions:
        link = f"https://petition.parliament.uk/petitions/{p.id}"
        row = [p.id, p.title, link, p.responded, "; ".join(p.departments)]
        if mine := labels.departments.get(p.id):
            seconds = labels.seconds.get(p.id)
            row += [mine, judge(mine, p), "" if seconds is None else seconds]
        else:
            row += ["", "", ""]
        for name in names:
            answer = answers[name][p.id]  # complete runs answer every petition
            row += [answer["department"] or "", judge(answer["department"], p)]
            if name != "tfidf":
                row.append(answer["reason"] or answer["reply"] or "")
        rows.append(row)

    out = io.StringIO()
    csv.writer(out).writerows([[cell(value) for value in row] for row in rows])
    return "\ufeff" + out.getvalue()  # the mark tells Excel the file is UTF-8


def judge(department: str | None, petition: Petition) -> str:
    return "yes" if department in petition.departments else "no"


def cell(value):
    """Text for a spreadsheet cell, so a petition title can never run as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def score(name: str, answers: dict, right: dict, petitions: list[Petition], response: dict) -> dict:
    hits = right[name]
    costs = [a["cost"] for a in answers.values()]
    times = [a["seconds"] for a in answers.values() if a["seconds"] is not None]
    row = {
        "name": name,
        "petitions": len(hits),
        "accuracy": bootstrap(list(hits.values()), [response[i] for i in hits]),
        "unusable": sum(a["department"] is None for a in answers.values()),
        "cost_per_1000": None if None in costs else round(1000 * mean(costs), 4),
        "median_seconds": median(times) if times else None,
    }
    shared = [i for i in hits if i in right.get("tfidf", {})]
    if name != "tfidf" and shared:
        differences = [hits[i] - right["tfidf"][i] for i in shared]
        row["vs_tfidf"] = bootstrap(differences, [response[i] for i in shared])
    return row


def most_common(petitions: list[Petition]) -> dict | None:
    counts = Counter(d for p in petitions for d in p.departments)
    if not counts:
        return None
    department = counts.most_common(1)[0][0]
    return {
        "department": department,
        "share": round(mean(department in p.departments for p in petitions), 4),
    }


def compare_with_me(labels, gold: dict, answers: dict, right: dict, response: dict) -> dict | None:
    """My labels and each router's answers, compared on the petitions I labelled."""
    labelled = {i: d for i, d in labels.departments.items() if i in gold}
    if not labelled:
        return None
    mine = {i: d in gold[i] for i, d in labelled.items()}
    routers = []
    for name, hits in right.items():
        shared = [i for i in mine if i in hits]
        if shared:
            groups = [response[i] for i in shared]
            agree = mean(answers[name][i]["department"] == labelled[i] for i in shared)
            routers.append(
                {
                    "name": name,
                    "petitions": len(shared),
                    "accuracy": bootstrap([hits[i] for i in shared], groups),
                    "vs_me": bootstrap([hits[i] - mine[i] for i in shared], groups),
                    "agrees_with_me": round(agree, 4),
                }
            )
    routers.sort(key=lambda row: row["accuracy"][0], reverse=True)
    times = [labels.seconds[i] for i in labelled if labels.seconds.get(i) is not None]
    return {
        "petitions": len(mine),
        "accuracy": bootstrap(list(mine.values()), [response[i] for i in mine]),
        "median_seconds": median(times) if times else None,
        "routers": routers,
    }


def consistency(name: str, forward: list, backward: list, gold: dict, hits: dict) -> dict:
    """How many answers change when the model is asked again, or with the list reversed.

    Asking again in the same order shows the background noise, and reversing the list
    adds any effect of the order. Petitions that get the same answer every time are the
    ones a model might route without a person checking, so accuracy is split that way.
    """
    latest, others = forward[-1], forward[-2:-1] + backward[-1:]

    def changed(other: dict) -> dict | None:
        shared = [i for i in latest if i in other]
        if not shared:
            return None
        return {
            "petitions": len(shared),
            "changed": sum(latest[i]["department"] != other[i]["department"] for i in shared),
        }

    shared = [i for i in hits if all(i in other for other in others)]
    stable = {
        i for i in shared if all(o[i]["department"] == latest[i]["department"] for o in others)
    }
    flipped = (
        [backward[-1][i]["department"] in gold[i] for i in backward[-1] if i in gold]
        if backward
        else []
    )
    return {
        "name": name,
        "repeated": changed(forward[-2]) if len(forward) > 1 else None,
        "reversed": changed(backward[-1]) if backward else None,
        "reversed_accuracy": round(mean(flipped), 4) if flipped else None,
        "runs": 1 + len(others),
        "petitions": len(shared),
        "stable": len(stable),
        "right_when_stable": round(mean(hits[i] for i in stable), 4) if stable else None,
        "right_otherwise": round(mean(hits[i] for i in shared if i not in stable), 4)
        if len(stable) < len(shared)
        else None,
    }


def training_cutoffs(petitions: list[Petition], names: list[str], right: dict, response: dict):
    """Each model's accuracy on petitions answered before and after its training cutoff.

    A model may have seen the responses published before its cutoff, so if it's remembering
    answers, it does better on those. Word matching can't have seen any of them, so it shows
    how much of a difference comes from the petitions themselves.
    """
    models, unknown = defaultdict(list), []  # models by cutoff, and those with none known
    for name in names:
        cutoff = TRAINING_CUTOFFS.get(name.split("/")[-1])
        if cutoff:
            models[cutoff].append(name)
        elif name != "tfidf":
            unknown.append(name)

    groups = []
    for cutoff, named in sorted(models.items()):
        before = {p.id: p.responded[:7] <= cutoff for p in petitions}
        groups.append(
            {
                "cutoff": cutoff,
                "before": sum(before.values()),
                "after": len(before) - sum(before.values()),
                "routers": [
                    before_and_after(name, before, right, response)
                    for name in [*named, "tfidf"]
                    if name in right
                ],
            }
        )
    return {"groups": groups, "unknown": unknown}


def before_and_after(name: str, before: dict, right: dict, response: dict) -> dict:
    hits, baseline = right[name], right.get("tfidf")
    row = {"name": name}
    for side, wanted in (("before", True), ("after", False)):
        ids = [i for i in hits if i in before and before[i] == wanted]
        row[side] = bootstrap([hits[i] for i in ids], [response[i] for i in ids]) if ids else None
    if name != "tfidf" and baseline and row["before"] and row["after"]:
        # How much further ahead of word matching the model is before its cutoff than after
        shared = [i for i in hits if i in baseline and i in before]
        row["extra_lead"] = gap(
            [hits[i] - baseline[i] for i in shared],
            [response[i] for i in shared],
            [before[i] for i in shared],
        )
    return row


def by_department(petitions: list[Petition], right: dict) -> list[dict]:
    """Accuracy by department. A petition tagged with two departments counts under the first."""
    groups = defaultdict(list)
    for p in petitions:
        groups[p.departments[0]].append(p.id)
    rows = []
    for department, ids in sorted(groups.items(), key=lambda g: -len(g[1])):
        accuracy = {}
        for name, hits in right.items():
            scored = [hits[i] for i in ids if i in hits]
            if scored:
                accuracy[name] = round(mean(scored), 4)
        rows.append({"department": department, "petitions": len(ids), "accuracy": accuracy})
    return rows


def mixups(name: str, answers: dict, right: dict, petitions: list[Petition], labels: dict) -> dict:
    """The model's wrong answers, grouped by the department tagged and the one it chose."""
    groups = defaultdict(list)
    for p in petitions:
        if p.id in right[name] and not right[name][p.id]:
            answer = answers[name][p.id]
            groups[p.departments[0], answer["department"]].append(
                {
                    "id": p.id,
                    "title": p.title,
                    "departments": p.departments,
                    "reason": answer["reason"] or answer["reply"],
                    "mine": labels.get(p.id),
                }
            )
    pairs = sorted(groups.items(), key=lambda g: -len(g[1]))
    return {
        "router": name,
        "pairs": [
            {"tagged": tagged, "chose": chose, "petitions": examples}
            for (tagged, chose), examples in pairs
        ],
    }
