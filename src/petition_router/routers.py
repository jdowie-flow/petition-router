"""Two ways to route a petition: a word-count classifier and a large language model."""

import hashlib
import json
import random
import re
import sys
import time
from dataclasses import dataclass

import litellm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

from .petitions import Petition

PROMPT = """\
Which UK government department should respond to this petition to Parliament?

Choose one of these departments:
{departments}

Reply with JSON only, like this:
{{"department": "<acronym from the list>", "reason": "<one short sentence>"}}"""

litellm.suppress_debug_info = True  # otherwise every failed call prints a help banner

# Errors worth waiting out. Anything else, such as a bad API key, stops the run.
TRANSIENT = (
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.InternalServerError,  # includes "overloaded"
    litellm.ServiceUnavailableError,
    litellm.BadGatewayError,
)

# Errors caused by one petition rather than the setup. They're recorded as unusable answers.
REFUSED = (litellm.ContentPolicyViolationError, litellm.ContextWindowExceededError)


@dataclass
class Answer:
    petition_id: int
    department: str | None  # None when the reply didn't name a department on the list
    reason: str = ""
    seconds: float | None = None
    cost: float | None = None  # US dollars, or None if LiteLLM has no price for the model
    reply: str = ""  # the raw reply, kept when it couldn't be used


def tfidf(petitions: list[Petition], folds: int = 5) -> list[Answer]:
    """TF-IDF and logistic regression, with 5-fold cross-validation.

    Every petition is answered by a model trained on the other four folds, so none
    is answered by a model that saw it. Petitions that got the same government
    response always share a fold, so a near-duplicate can't give the answer away.
    """
    texts = [p.text for p in petitions]
    labels = [p.departments[0] for p in petitions]
    groups = [p.response_hash for p in petitions]
    answers = {}
    for train, test in GroupKFold(folds).split(texts, groups=groups):
        model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english"),
            LogisticRegression(max_iter=1000),
        )
        model.fit([texts[i] for i in train], [labels[i] for i in train])
        start = time.perf_counter()
        predicted = model.predict([texts[i] for i in test])
        seconds = (time.perf_counter() - start) / len(test)
        for i, department in zip(test, predicted, strict=True):
            answers[i] = Answer(petitions[i].id, str(department), seconds=seconds, cost=0.0)
    return [answers[i] for i in range(len(petitions))]


class LLM:
    def __init__(self, model: str, departments: dict[str, str], reverse: bool = False):
        self.model = model
        self.acronyms = {code.lower(): code for code in departments}
        self.names = {name.lower(): code for code, name in departments.items()}

        def prompt(order):
            listing = "\n".join(f"{code}: {departments[code]}" for code in order)
            return PROMPT.format(departments=listing)

        a_to_z = sorted(departments, key=str.lower)
        self.prompt = prompt(a_to_z[::-1] if reverse else a_to_z)
        # Saved with each run, so runs with a different prompt or department list aren't
        # compared. A reversed run shares its version with the A to Z run it's checking.
        self.version = hashlib.sha256(prompt(a_to_z).encode()).hexdigest()[:8]

    def __call__(self, petition: Petition) -> Answer:
        try:
            response, seconds = self.ask(petition.text)
        except REFUSED as error:
            return Answer(petition.id, None, cost=0.0, reply=f"Refused: {error}")
        reply = response.choices[0].message.content or ""
        department, reason = self.read(reply)
        return Answer(
            petition.id,
            department,
            reason=reason,
            seconds=seconds,
            cost=cost(response, self.model),
            reply="" if department else reply,
        )

    def read(self, reply: str) -> tuple[str | None, str]:
        """The department and reason from the first JSON object in the reply that has them."""
        decoder = json.JSONDecoder()
        for start in [i for i, character in enumerate(reply) if character == "{"]:
            try:
                parsed, _ = decoder.raw_decode(reply, start)
            except ValueError:
                continue
            if isinstance(parsed, dict) and "department" in parsed:
                return self.match(str(parsed["department"])), str(parsed.get("reason", ""))
        return None, ""

    def match(self, named: str) -> str | None:
        """A listed department, however the model wrote it.

        Accepts "DfE", "dfe", "D.f.E", "**DfE**", the full name, and mixes such as
        "DfE: Department for Education", "Home Office (HO)" or "MoJ, Ministry of Justice".
        """
        text = named.strip().lower()
        if text in self.names:
            return self.names[text]
        for part in re.split(r"\s*[:(),\u2013\u2014]\s*|\s+-\s+", text):
            part = part.strip(" .*")
            letters = re.sub(r"[^a-z]", "", part)
            if part in self.names:
                return self.names[part]
            if letters in self.acronyms:
                return self.acronyms[letters]
        return None

    def ask(self, text: str):
        messages = [{"role": "system", "content": self.prompt}, {"role": "user", "content": text}]
        for attempt in range(6):
            try:
                start = time.perf_counter()
                # No temperature: Claude 5.5 models only accept their default
                response = litellm.completion(model=self.model, messages=messages, timeout=120)
                return response, time.perf_counter() - start
            except TRANSIENT as error:
                if attempt == 5:
                    raise
                # From a few seconds up to a minute, jittered so threads don't retry together
                wait = 2**attempt * random.uniform(2, 4)
                print(f"\n{type(error).__name__}, trying again in {wait:.0f} s", file=sys.stderr)
                time.sleep(wait)


def cost(response, model: str) -> float | None:
    """What a call cost in US dollars, or None if LiteLLM has no price for the model."""
    try:
        # Raises for models LiteLLM doesn't know. Its offline price list can also return
        # zero prices for newer models, which would wrongly show the run as free.
        info = litellm.get_model_info(model)
        if not (info.get("input_cost_per_token") or info.get("output_cost_per_token")):
            return None
        return litellm.completion_cost(completion_response=response)
    except Exception:
        return None
