import csv
import io

import numpy as np
from fakes import petition

from petition_router.results import Labels, bootstrap, spreadsheet, summarise

NO_LABELS = Labels()


def run(router, answers, reverse=False, created="2026-10-01-120000", cost=0.001, prompt="v1"):
    rows = [
        {"petition_id": i, "department": d, "reason": "", "seconds": 0.5, "cost": cost, "reply": ""}
        for i, d in answers.items()
    ]
    return {
        "router": router,
        "reversed": reverse,
        "prompt": prompt,
        "created": created,
        "answers": rows,
    }


def test_bootstrap_interval():
    estimate, low, high = bootstrap([1] * 30 + [0] * 10)
    assert estimate == 0.75
    assert 0.6 < low < estimate < high < 0.9


def test_the_interval_covers_the_truth_about_95_percent_of_the_time():
    rng = np.random.default_rng(1)
    covered = 0
    for _ in range(200):
        _, low, high = bootstrap(rng.random(300) < 0.8)
        covered += low <= 0.8 <= high
    assert 0.9 <= covered / 200 <= 0.99


def test_grouped_values_are_resampled_together():
    values = [1] * 30 + [0] * 10
    groups = [i // 10 for i in range(40)]  # four groups of ten identical values
    _, low, high = bootstrap(values)
    _, grouped_low, grouped_high = bootstrap(values, groups)
    assert grouped_high - grouped_low > high - low


def test_any_tagged_department_counts():
    petitions = [petition(1, "Joint", "HO", "MoJ"), petition(2, "Schools", "DfE")]
    summary = summarise(petitions, {}, [run("m", {1: "MoJ", 2: "HO"})], NO_LABELS)
    assert summary["routers"][0]["accuracy"][0] == 0.5


def test_paired_comparisons():
    petitions = [petition(i, "Police", "HO") for i in range(1, 11)]
    runs = [
        run("tfidf", {i: "HO" if i <= 5 else "DfE" for i in range(1, 11)}),
        run("test/model", dict.fromkeys(range(1, 11), "HO")),
    ]
    labels = Labels({1: "HO", 2: "DfE"}, {1: 10.0, 2: 20.0})
    summary = summarise(petitions, {}, runs, labels)

    model = summary["routers"][0]
    assert model["name"] == "test/model"
    assert model["vs_tfidf"][0] == 0.5
    assert model["vs_tfidf"][1] > 0  # right on five more petitions out of ten is a real gap

    me = summary["me"]
    assert me["petitions"] == 2
    assert me["accuracy"][0] == 0.5
    assert me["median_seconds"] == 15.0
    against_me = next(r for r in me["routers"] if r["name"] == "test/model")
    assert against_me["accuracy"][0] == 1.0
    assert against_me["vs_me"][0] == 0.5
    assert against_me["agrees_with_me"] == 0.5


def test_consistency():
    petitions = [petition(i, "Police", "HO") for i in range(1, 5)]
    runs = [
        run("m", {1: "HO", 2: "HO", 3: "HO", 4: "DfE"}, created="2026-01-01-000000"),
        run("m", dict.fromkeys(range(1, 5), "HO"), created="2026-02-01-000000"),
        run("m", {1: "HO", 2: "DfE", 3: "DfE", 4: "HO"}, reverse=True),
    ]
    check = summarise(petitions, {}, runs, NO_LABELS)["consistency"][0]

    assert check["repeated"] == {"petitions": 4, "changed": 1}
    assert check["reversed"] == {"petitions": 4, "changed": 2}
    assert check["reversed_accuracy"] == 0.5
    # Only petition 1 got the same answer all three times
    assert (check["petitions"], check["stable"]) == (4, 1)
    assert check["right_when_stable"] == 1.0
    assert check["right_otherwise"] == 1.0


def test_runs_with_another_prompt_or_unfinished_are_left_out():
    petitions = [petition(i, "Police", "HO") for i in range(1, 5)]
    unfinished = run("m", {1: "DfE"}, created="2026-03-01-000000")
    runs = [
        run("m", dict.fromkeys(range(1, 5), "DfE"), created="2026-01-01-000000", prompt="v1"),
        run("m", dict.fromkeys(range(1, 5), "HO"), created="2026-02-01-000000", prompt="v2"),
        unfinished,
    ]
    summary = summarise(petitions, {}, runs, NO_LABELS)
    assert summary["routers"][0]["accuracy"][0] == 1.0
    assert summary["consistency"] == []


def test_labels_saved_by_the_first_version_still_load(project):
    (project / "results").mkdir()
    (project / "results" / "my-labels.json").write_text('{"7": "HO", "8": "DfE"}')
    labels = Labels.load()
    assert labels.departments == {7: "HO", 8: "DfE"}
    assert labels.finished is labels.agreed is None  # two labels is not a finished set


def test_labels_saved_before_the_first_page_existed_still_load(project):
    (project / "results").mkdir()
    (project / "results" / "my-labels.json").write_text(
        '{"finished": null, "labels": {"7": {"department": "HO", "seconds": 4.5}}}'
    )
    labels = Labels.load()
    assert (labels.departments, labels.seconds, labels.agreed) == ({7: "HO"}, {7: 4.5}, None)

    labels.agreed = "2026-10-14T09:00:00+00:00"
    labels.save()
    assert Labels.load() == labels


def test_runs_on_petitions_no_longer_in_the_data_are_skipped_without_errors():
    petitions = [petition(1, "Police", "HO")]
    runs = [run("tfidf", {99: "HO"}), run("new", {1: "HO"}), run("other", {1: "HO"})]
    summary = summarise(petitions, {}, runs, NO_LABELS)
    assert [r["name"] for r in summary["routers"]] == ["new", "other"]
    assert "vs_tfidf" not in summary["routers"][0]


def test_mistakes_are_grouped():
    petitions = [
        petition(1, "a", "HO"),
        petition(2, "b", "HO"),
        petition(3, "c", "DfE"),
        petition(4, "d", "HO"),
    ]
    model = run("test/model", {1: "MoJ", 2: "MoJ", 3: "DfE", 4: None}, cost=None)
    summary = summarise(petitions, {}, [model], Labels({2: "MoJ"}))

    pairs = summary["mixups"]["pairs"]
    assert [(p["tagged"], p["chose"], len(p["petitions"])) for p in pairs] == [
        ("HO", "MoJ", 2),
        ("HO", None, 1),
    ]
    assert pairs[0]["petitions"][1]["mine"] == "MoJ"
    assert summary["routers"][0]["unusable"] == 1
    assert summary["routers"][0]["cost_per_1000"] is None  # one answer had no known price


def test_the_spreadsheet_has_every_answer_and_no_formulas():
    petitions = [
        petition(1, "Fund more nurses", "DHSC"),
        petition(2, '=HYPERLINK("x")', "HO", "MoJ"),
    ]
    runs = [
        run("tfidf", {1: "DHSC", 2: "DfE"}),
        run("anthropic/claude-haiku-5-5", {1: "DHSC", 2: None}),
    ]
    text = spreadsheet(petitions, runs, Labels({1: "DfE"}, {1: 12.5}))

    assert text.startswith("\ufeff")  # so Excel reads it as UTF-8
    header, nurses, formula = csv.reader(io.StringIO(text[1:]))
    assert header[4:] == [
        "Tagged",
        "Human",
        "Human right",
        "Human seconds",
        "TF-IDF answer",
        "TF-IDF right",
        "claude-haiku-5-5 answer",
        "claude-haiku-5-5 right",
        "claude-haiku-5-5 reason",
    ]
    assert nurses[4:11] == ["DHSC", "DfE", "no", "12.5", "DHSC", "yes", "DHSC"]
    assert formula[1] == '\'=HYPERLINK("x")'
    assert formula[4:] == ["HO; MoJ", "", "", "", "DfE", "no", "", "no", ""]
