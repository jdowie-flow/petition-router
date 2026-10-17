import httpx
import litellm
import pytest
from conftest import finish_labelling
from fakes import DEPARTMENTS, keyword_model, make_petitions

from petition_router import cli, routers
from petition_router import petitions as data
from petition_router.cli import main
from petition_router.results import Labels, add_answer, load_runs, start_run, summarise
from petition_router.routers import LLM, Answer


@pytest.fixture
def fake_model(monkeypatch):
    calls = []

    def completion(**call):
        calls.append(call)
        return keyword_model(**call)

    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(routers, "cost", lambda response, model: 0.0002)
    return calls


@pytest.fixture
def no_server(monkeypatch):
    """Stands in for the web server, which stops as if Ctrl+C was pressed."""
    opened = []

    def serve(results=False, until_labelled=False):
        opened.append(results)
        return False

    monkeypatch.setattr(cli, "serve", serve)
    return opened


def test_make_labels_first_then_runs_the_models_once(
    project, fake_model, no_server, monkeypatch, capsys
):
    main(["all"])
    assert no_server == [False] and not load_runs()  # labelling only; no model has run
    assert "Stopped with 0 of 100 labelled" in capsys.readouterr().out

    finish_labelling()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    main(["all"])
    runs = [(r["router"], r["reversed"]) for r in load_runs()]
    assert sorted(runs) == sorted(cli.PLAN)
    assert "Run 5 of 5: Routing with anthropic/claude-sonnet-5-5" in capsys.readouterr().out

    calls = len(fake_model)
    main(["all"])
    assert len(fake_model) == calls  # a second make costs nothing

    petitions, departments = data.load()
    summary = summarise(petitions, departments, load_runs(), Labels.load())
    haiku = next(r for r in summary["routers"] if r["name"] == cli.HAIKU)
    assert haiku["accuracy"][0] == 1.0
    assert haiku["cost_per_1000"] == 0.2
    assert summary["consistency"][0]["reversed"] == {"petitions": 120, "changed": 0}


def test_saving_the_last_label_carries_straight_on_to_the_models(project, fake_model, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    opened = []

    def serve(results=False, until_labelled=False):
        opened.append(results)
        if until_labelled:
            finish_labelling()
        return until_labelled

    monkeypatch.setattr(cli, "serve", serve)
    main(["all"])
    assert opened == [False, True]  # the labelling page, then the results
    assert len(load_runs()) == len(cli.PLAN)


def test_make_only_needs_the_key_if_a_model_still_has_to_run(
    project, fake_model, no_server, monkeypatch
):
    finish_labelling()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    main(["all"])
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    main(["all"])  # everything has run, so no key is needed to see the results
    assert no_server == [True, True]


def test_make_asks_for_the_key_after_labelling(project, no_server):
    (project / ".env.example").write_text("ANTHROPIC_API_KEY=\n")
    finish_labelling()
    with pytest.raises(SystemExit, match="put your Anthropic API key"):
        main(["all"])
    assert (project / ".env").exists()


def test_a_stopped_run_carries_on_where_it_left_off(project, fake_model):
    petitions, departments = data.load()
    llm = LLM("test/model", departments)
    path = start_run("test/model", False, llm.version)
    for p in petitions[:50]:
        add_answer(path, Answer(p.id, p.departments[0]))
    with path.open("a") as file:
        file.write('{"petition_id": 99999, "depart')  # the line being written when it stopped

    main(["run", "test/model"])

    assert len(fake_model) == 70
    [run] = load_runs()
    assert sorted(a["petition_id"] for a in run["answers"]) == sorted(p.id for p in petitions)


def test_new_petitions_after_a_download_are_routed_too(project, fake_model):
    main(["run", "test/model"])
    petitions, departments = data.load()
    data.save(petitions + make_petitions(per_department=5, first_id=500), departments)

    main(["run", "test/model"])

    assert len(fake_model) == 120 + 20
    assert len(load_runs()) == 1  # the same run, carried on


def test_an_empty_run_file_is_ignored(project, fake_model):
    (project / "results" / "runs").mkdir(parents=True)
    (project / "results" / "runs" / "2026-01-01-000000-000000-test-model.jsonl").write_text("")
    main(["run", "test/model"])
    assert len(load_runs()) == 1


def test_a_rejected_api_key_gets_a_plain_message(project, monkeypatch):
    def denied(**call):
        raise litellm.AuthenticationError("invalid x-api-key", "anthropic", "test/model")

    monkeypatch.setattr(litellm, "completion", denied)
    with pytest.raises(SystemExit, match="API key was rejected"):
        main(["run", "test/model"])


def test_download_problems_get_a_plain_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def offline():
        raise httpx.ConnectError("Name or service not known")

    monkeypatch.setattr(data, "download", offline)
    with pytest.raises(SystemExit, match="Could not download the petitions"):
        main(["download"])


def test_download_command(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(data, "download", lambda: (make_petitions(), DEPARTMENTS, 3))
    main(["download"])
    assert len(data.load()[0]) == 120
    assert "Skipped 3" in capsys.readouterr().out


def test_no_data_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="No petitions yet"):
        main(["run", "tfidf"])


def test_ctrl_c_stops_with_a_plain_message(project, monkeypatch, capsys):
    def interrupted(petitions):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "tfidf", interrupted)
    with pytest.raises(SystemExit) as stopped:
        main(["run", "tfidf"])
    assert stopped.value.code == 130
    assert "Stopped. Run the same command again" in capsys.readouterr().out
