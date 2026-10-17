import pytest
from fakes import DEPARTMENTS, make_petitions

from petition_router import petitions as data
from petition_router.results import Labels


@pytest.fixture
def project(tmp_path, monkeypatch):
    """An empty project folder with 120 made-up petitions downloaded into it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    data.save(make_petitions(), DEPARTMENTS)
    return tmp_path


def finish_labelling(department=None):
    """Label every sampled petition, with its first tag unless a department is given."""
    petitions, _ = data.load()
    sample = data.sample(petitions)
    chosen = {p.id: department or p.departments[0] for p in sample}
    Labels(chosen, dict.fromkeys(chosen, 12.0), "2026-10-14T09:00:00+00:00").save()
