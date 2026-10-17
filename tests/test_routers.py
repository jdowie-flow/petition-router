import litellm
import pytest
from fakes import DEPARTMENTS, make_petitions, petition, reply

from petition_router import routers
from petition_router.routers import LLM, tfidf

NURSES = petition(7, "Fund more nurses", "DHSC")


def route_with(monkeypatch, *replies):
    """Route one petition with a fake model that returns or raises these, in turn."""
    calls = []

    def completion(**call):
        calls.append(call)
        item = replies[len(calls) - 1]
        if isinstance(item, Exception):
            raise item
        return reply(item)

    monkeypatch.setattr(litellm, "completion", completion)
    monkeypatch.setattr(routers.time, "sleep", lambda seconds: None)
    return LLM("test/model", DEPARTMENTS)(NURSES), calls


@pytest.mark.parametrize(
    "content",
    [
        '{"department": "DHSC", "reason": "Nursing is a health matter."}',
        '```json\n{"department": "dhsc", "reason": "Nursing is a health matter."}\n```',
        'Sure. {"department": " DHSC ", "reason": "Nursing is a health matter."}',
        '{"department": "DHSC: Department of Health and Social Care", '
        '"reason": "Nursing is a health matter."}',
        '{"department": "Department of Health and Social Care", '
        '"reason": "Nursing is a health matter."}',
        '{"department": "**D.H.S.C.**", "reason": "Nursing is a health matter."}',
        '{"department": "Department of Health and Social Care (DHSC)", '
        '"reason": "Nursing is a health matter."}',
        '{"department": "DHSC - Department of Health and Social Care", '
        '"reason": "Nursing is a health matter."}',
        '{"department": "DHSC, Department of Health and Social Care", '
        '"reason": "Nursing is a health matter."}',
        'Options {HO, DHSC}. {"department": "DHSC", "reason": "Nursing is a health matter."} {}',
    ],
)
def test_reads_the_reply(monkeypatch, content):
    answer, _ = route_with(monkeypatch, content)
    assert answer.department == "DHSC"
    assert answer.reason == "Nursing is a health matter."


@pytest.mark.parametrize(
    "content",
    ["The Department of Health.", '{"department": "NHS England"}', '{"dept": "DHSC"}', '["DHSC"]'],
)
def test_unusable_reply_is_kept(monkeypatch, content):
    answer, _ = route_with(monkeypatch, content)
    assert answer.department is None
    assert answer.reply == content


@pytest.mark.parametrize(
    "error",
    [
        litellm.RateLimitError("Slow down", llm_provider="anthropic", model="test/model"),
        litellm.Timeout("Took too long", model="test/model", llm_provider="anthropic"),
    ],
)
def test_retries_rate_limits_and_timeouts(monkeypatch, error):
    answer, calls = route_with(monkeypatch, error, error, '{"department": "DHSC"}')
    assert answer.department == "DHSC"
    assert len(calls) == 3


def test_a_petition_the_provider_refuses_is_recorded_not_fatal(monkeypatch):
    refused = litellm.ContentPolicyViolationError("Blocked", "test/model", "openai")
    answer, _ = route_with(monkeypatch, refused)
    assert answer.department is None
    assert answer.reply.startswith("Refused")


def test_a_model_without_a_known_price_has_an_unknown_cost(monkeypatch):
    free = {"input_cost_per_token": 0, "output_cost_per_token": 0}
    monkeypatch.setattr(litellm, "get_model_info", lambda model: free)
    assert routers.cost(reply("{}"), "anthropic/brand-new-model") is None


def test_bad_api_key_stops_the_run(monkeypatch):
    denied = litellm.AuthenticationError(
        "Invalid key", llm_provider="anthropic", model="test/model"
    )
    with pytest.raises(litellm.AuthenticationError):
        route_with(monkeypatch, denied, '{"department": "DHSC"}')


def test_reverse_order():
    forward = LLM("test/model", DEPARTMENTS).prompt
    backward = LLM("test/model", DEPARTMENTS, reverse=True).prompt
    assert forward.index("DfE:") < forward.index("DfT:") < forward.index("HO:")
    assert backward.index("HO:") < backward.index("DfT:") < backward.index("DfE:")


def test_the_prompt_version_tracks_the_department_list_but_not_its_order():
    version = LLM("test/model", DEPARTMENTS).version
    assert LLM("test/model", DEPARTMENTS, reverse=True).version == version
    assert LLM("test/model", DEPARTMENTS | {"NIO": "Northern Ireland Office"}).version != version


def test_tfidf_never_sees_the_petition_it_answers():
    petitions = make_petitions()
    # Two near-duplicates from a department nothing else belongs to. If they could be
    # split across folds, the classifier would learn one and get the other right.
    petitions += [
        petition(901, "Protect the Good Friday Agreement", "NIO", response="same"),
        petition(902, "Protect the Good Friday Agreement now", "NIO", response="same"),
    ]

    answers = tfidf(petitions)

    assert [a.petition_id for a in answers] == [p.id for p in petitions]
    assert all(a.department != "NIO" for a in answers[-2:])
    right = sum(a.department == p.departments[0] for a, p in zip(answers, petitions, strict=True))
    assert right >= 0.9 * len(petitions)
