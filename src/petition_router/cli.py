"""Download petitions, route them, and serve the labelling and results pages."""

import argparse
import os
import shutil
import socket
import sys
import threading
import webbrowser
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import litellm
from dotenv import find_dotenv, load_dotenv

from . import petitions as data
from .results import Labels, add_answer, complete, load_runs, start_run
from .routers import LLM, tfidf

HAIKU = "anthropic/claude-haiku-5-5"
SONNET = "anthropic/claude-sonnet-5-5"
# The runs `make` does once labelling is finished. Haiku runs twice more, the second
# time with the list reversed, for the consistency check.
PLAN = [("tfidf", False), (HAIKU, False), (HAIKU, False), (HAIKU, True), (SONNET, False)]


def main(argv: list[str] | None = None):
    load_dotenv(find_dotenv(usecwd=True), override=True)  # the key in .env wins
    parser = argparse.ArgumentParser(prog="petition-router", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("all", help="what make does: download, label, run the models, show results")
    commands.add_parser("download", help="download petitions that got a government response")
    run = commands.add_parser("run", help="route every petition, carrying on if stopped part way")
    run.add_argument("router", help="tfidf, or a LiteLLM model such as anthropic/claude-haiku-5-5")
    run.add_argument("--reverse", action="store_true", help="list the departments Z to A")
    commands.add_parser("serve", help="open the labelling and results pages")
    args = parser.parse_args(argv)
    if args.command == "run" and args.reverse and args.router == "tfidf":
        parser.error("--reverse only applies to language models")

    try:
        if args.command == "all":
            everything()
        elif args.command == "download":
            download()
        elif args.command == "serve":
            serve()
        else:
            route(args.router, args.reverse)
    except httpx.HTTPError as error:
        sys.exit(f"Could not download the petitions: {error}")
    except litellm.AuthenticationError:
        sys.exit("The API key was rejected. Check the key in the .env file.")
    except tuple(litellm.LITELLM_EXCEPTION_TYPES) as error:
        sys.exit(
            f"The model call failed: {getattr(error, 'message', error)}\n"
            "The answers so far are saved. Run the same command again to carry on."
        )
    except KeyboardInterrupt:
        print("\nStopped. Run the same command again to carry on.")
        sys.exit(130)


def everything():
    """Download if needed, then labelling, then any runs not yet done, then the results."""
    if not data.DATA_FILE.exists():
        download()
    if not Labels.load().finished and not label():
        return  # stopped part way through labelling
    petitions, departments = data.load()
    versions = {name: LLM(name, departments).version for name, _ in PLAN if name != "tfidf"}
    done = Counter(
        (run["router"], run["reversed"])
        for run in load_runs()
        if complete(run, petitions) and run["prompt"] == versions.get(run["router"])
    )
    missing = []
    for router, reverse in PLAN:
        if done[router, reverse]:
            done[router, reverse] -= 1
        else:
            missing.append((router, reverse))
    if any(router != "tfidf" for router, _ in missing) and not os.environ.get("ANTHROPIC_API_KEY"):
        if not os.path.exists(".env"):
            shutil.copy(".env.example", ".env")
        sys.exit("To run the models, put your Anthropic API key in the .env file, then run make.")
    if missing:
        print("Running the models. Each answer is saved as it arrives, so you can stop at any")
        print("time with Ctrl+C and run make again to carry on.")
    for number, (router, reverse) in enumerate(missing, 1):
        route(router, reverse, step=f"\nRun {number} of {len(missing)}: ")
    serve(results=True)


def label() -> bool:
    """Open the labelling page until the last label is saved. False if stopped before then."""
    done, total = labelled()
    if done:
        print(f"You have labelled {done} of {total} petitions. Carry on in your browser.")
    else:
        print("Label the petitions in your browser. Each label is saved as you go, so you can")
        print("stop at any time and run make again to carry on.")
    if serve(until_labelled=True):
        print("\nAll the petitions are labelled.\n")
        return True
    done, total = labelled()
    print(f"\nStopped with {done} of {total} labelled. Run make again to carry on.")
    return False


def labelled() -> tuple[int, int]:
    """How many of the petitions to label have a label, and how many there are."""
    labels = Labels.load()
    sample = data.sample(data.load()[0], labels.departments)
    return sum(p.id in labels.departments for p in sample), len(sample)


def download():
    print("Downloading petitions…")
    petitions, departments, skipped = data.download()
    data.save(petitions, departments)
    print(f"Saved {len(petitions)} petitions and {len(departments)} departments.")
    if skipped:
        print(f"Skipped {skipped} with a response but no department listed.")


def route(router: str, reverse: bool, step: str = ""):
    try:
        petitions, departments = data.load()
    except FileNotFoundError:
        sys.exit("No petitions yet. Run make first.")
    print(f"{step}Routing with {router}{' (list reversed)' if reverse else ''}")
    if router == "tfidf":
        path = start_run(router, False, None)
        for answer in tfidf(petitions):
            add_answer(path, answer)
        return

    llm = LLM(router, departments, reverse)
    # Carry on from the newest run of the same kind if it was stopped part way
    same = [
        run
        for run in load_runs()
        if (run["router"], run["reversed"], run["prompt"]) == (router, reverse, llm.version)
    ]
    if same and not complete(same[-1], petitions):
        path = same[-1]["path"]
        answered = {a["petition_id"] for a in same[-1]["answers"]}
        if not path.read_text().endswith("\n"):  # the last answer was cut short
            add_line_break(path)
        print(f"Carrying on from {len(answered)} answers")
    else:
        path, answered = start_run(router, reverse, llm.version), set()
    todo = [p for p in petitions if p.id not in answered]

    # Eight at a time. Each answer is saved as it arrives, so stopping loses very little.
    pool = ThreadPoolExecutor(max_workers=8)
    try:
        for count, future in enumerate(as_completed(pool.submit(llm, p) for p in todo), 1):
            add_answer(path, future.result())
            print(f"\r{count} of {len(todo)} petitions", end="", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped. The answers so far are saved. Run the same command to carry on.")
        os._exit(130)  # don't wait for calls still in progress, which can take minutes
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        print(file=sys.stderr)


def serve(results: bool = False, until_labelled: bool = False) -> bool:
    """Serve the pages until Ctrl+C or, with `until_labelled`, until the last label is saved.

    True if it stopped because the last label was saved.
    """
    import uvicorn

    from .server import app

    port = next(port for port in range(8000, 8100) if port_is_free(port))
    url = f"http://127.0.0.1:{port}" + ("/#results" if results else "")
    print(f"\nOpening {url} (press Ctrl+C to stop)")
    # No lifespan: the app has no startup or shutdown steps, and skipping them means a
    # Ctrl+C just as the server stops on its own can't print a traceback
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    finished = threading.Event()

    def carry_on():  # the response to the last label still goes out before it stops
        finished.set()
        server.should_exit = True

    app.state.on_finished = carry_on if until_labelled else None
    threading.Timer(1, webbrowser.open, [url]).start()
    try:
        server.run()
    except KeyboardInterrupt:  # Ctrl+C; the server has already shut down cleanly
        return False
    finally:
        app.state.on_finished = None
    return finished.is_set()


def add_line_break(path):
    with path.open("a") as file:
        file.write("\n")


def port_is_free(port: int) -> bool:
    with socket.socket() as connection:
        return connection.connect_ex(("127.0.0.1", port)) != 0
