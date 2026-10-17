import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { agree, getLabelling, saveLabel, type Labelling as Data, type Petition } from "./api";
import { matchDepartments } from "./departments";
import { Intro } from "./Intro";
import { hashFor, indexFromHash, nextUnlabelled, reachable } from "./navigation";

export function Labelling() {
  const [data, setData] = useState<Data | null>(null);
  const [problem, setProblem] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState("");
  const [arrowed, setArrowed] = useState<string | null>(null);
  const find = useRef<HTMLInputElement>(null);
  const finishedHeading = useRef<HTMLHeadingElement>(null);
  const shownAt = useRef(Date.now());
  // Time already spent on petitions without a label, from earlier visits. Going back to check
  // an earlier petition does not lose the time spent on the one you left.
  const spent = useRef(new Map<number, number>());

  // Load the petitions and labels, and show the one the address asks for if it can be shown
  const load = () =>
    getLabelling().then((loaded) => {
      const i = reachable(indexFromHash(window.location.hash), loaded.petitions, loaded.labels);
      if (i < loaded.petitions.length) history.replaceState(null, "", hashFor(i));
      setData(loaded);
      setIndex(i);
    });

  useEffect(() => {
    load().catch((error: Error) => setProblem(error.message));
  }, []);

  /** Show petition `i`, keeping the time spent on the one being left if it has no label yet. */
  const show = (i: number, current: Data) => {
    const leaving = current.petitions[index];
    if (leaving && !(leaving.id in current.labels)) {
      const before = spent.current.get(leaving.id) ?? 0;
      spent.current.set(leaving.id, before + Date.now() - shownAt.current);
    }
    setIndex(i);
    setTyped("");
    setArrowed(null);
    shownAt.current = Date.now();
    window.scrollTo(0, 0);
    find.current?.focus({ preventScroll: true });
  };

  // The previous and next links, and the browser's Back and Forward buttons, change the
  // address. Follow it, but no further than the first petition without a label. Once every
  // petition is labelled, an address without a petition goes to the summary.
  useEffect(() => {
    if (!data) return;
    const onHashChange = () => {
      const wanted = indexFromHash(window.location.hash);
      const i = reachable(wanted, data.petitions, data.labels);
      const shown = i < data.petitions.length;
      if (shown && i !== wanted) history.replaceState(null, "", hashFor(i));
      if (i !== index) {
        show(i, data);
        if (shown) {
          setStatus(`Petition ${i + 1} of ${data.petitions.length}: ${data.petitions[i].title}`);
        }
      }
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  });

  // The clock stops while the tab is in the background, so a break isn't counted
  useEffect(() => {
    let hiddenAt = 0;
    const onVisibilityChange = () => {
      if (document.hidden) {
        hiddenAt = Date.now();
      } else if (hiddenAt) {
        shownAt.current += Date.now() - hiddenAt;
        hiddenAt = 0;
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  // Once the last label is saved the labels are locked: they can be looked at, not changed
  const locked =
    data !== null &&
    (data.finished !== null ||
      nextUnlabelled(data.petitions, data.labels, -1) >= data.petitions.length);
  const summary = data !== null && index >= data.petitions.length; // the page after the last one
  useEffect(() => {
    if (summary) finishedHeading.current?.focus();
  }, [summary]);

  // The page title says which petition this is, so screen readers announce the move
  useEffect(() => {
    if (!data) return;
    const page =
      !summary && (data.agreed || locked)
        ? `Petition ${index + 1} of ${data.petitions.length}`
        : "Label petitions";
    document.title = `${page} – Petition Router`;
  }, [data, index, summary, locked]);

  if (!data) {
    return (
      <main className="labelling">
        <h1 className="visually-hidden">Label petitions</h1>
        <p className={problem ? "problem" : undefined}>{problem || "Loading petitions…"}</p>
      </main>
    );
  }

  const { departments, petitions, labels } = data;
  const petition = summary ? undefined : (petitions[index] as Petition | undefined);
  const done = petitions.filter((p) => p.id in labels);
  const labelled = done.length;
  const furthest = nextUnlabelled(petitions, labels, -1); // where the person left off
  const reviewing = petition !== undefined && petition.id in labels;

  if (!data.agreed && !locked) {
    const start = async () => {
      try {
        await agree();
        await load(); // another tab may have saved labels since this one loaded
        setProblem("");
        shownAt.current = Date.now(); // reading the first page is not timed
        window.scrollTo(0, 0);
      } catch (error) {
        setProblem(error instanceof Error ? error.message : "Something went wrong.");
      }
    };
    return <Intro total={petitions.length} labelled={labelled} problem={problem} onStart={start} />;
  }

  // Typing ranks the matches and highlights the best one. The arrow keys then move
  // through the matches in the order they appear on screen.
  const filtering = typed.trim() !== "";
  const ranked = matchDepartments(typed, departments);
  const onScreen = Object.keys(departments).filter((code) => ranked.includes(code));
  const highlighted = filtering
    ? arrowed && onScreen.includes(arrowed)
      ? arrowed
      : ranked[0]
    : undefined;

  const choose = async (code: string) => {
    if (!petition || saving || locked) return;
    setSaving(true);
    const taken = ((spent.current.get(petition.id) ?? 0) + Date.now() - shownAt.current) / 1000;
    try {
      await saveLabel(petition.id, code, taken);
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "That label was not saved.");
      return;
    } finally {
      setSaving(false);
    }
    spent.current.delete(petition.id);
    const updated = { ...data, labels: { ...labels, [petition.id]: code } };
    // Choosing always moves on: to the next petition in order when changing an earlier
    // label, otherwise to the next one without a label
    const next = reviewing
      ? reachable(index + 1, petitions, updated.labels)
      : nextUnlabelled(petitions, updated.labels, index);
    setProblem("");
    setStatus(
      `Saved ${departments[code]}.` +
        (petitions[next]
          ? ` Petition ${next + 1} of ${petitions.length}: ${petitions[next].title}`
          : ""),
    );
    setData(updated);
    if (next < petitions.length) history.pushState(null, "", hashFor(next));
    show(next, updated);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setTyped("");
      setArrowed(null);
      return;
    }
    if (!highlighted) return;
    const position = onScreen.indexOf(highlighted);
    if (event.key === "Enter") {
      event.preventDefault();
      choose(highlighted);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setArrowed(onScreen[Math.min(position + 1, onScreen.length - 1)]);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setArrowed(onScreen[Math.max(position - 1, 0)]);
    }
  };

  return (
    <main className="labelling">
      <h1 className="visually-hidden">Label petitions</h1>
      <div className="progress">
        <p aria-live="polite" aria-atomic="true">
          {labelled} of {petitions.length} labelled
        </p>
        <span className="progress-bar" aria-hidden="true">
          <span style={{ width: `${(100 * labelled) / petitions.length}%` }} />
        </span>
      </div>
      <p className="visually-hidden" role="status">
        {status}
      </p>

      {petition ? (
        <>
          <div className="petition-column">
            <article key={petition.id} className="petition" aria-labelledby="petition-title">
              <p className="position">
                Petition {index + 1} of {petitions.length}
              </p>
              <h2 id="petition-title">{petition.title}</h2>
              {petition.background && <p>{petition.background}</p>}
              {petition.details && <p>{petition.details}</p>}
            </article>

            <nav className="pager" aria-label="Petitions">
              {index > 0 && (
                <a href={hashFor(index - 1)} rel="prev" className="pager-previous">
                  <Arrow direction="previous" />
                  Previous petition
                </a>
              )}
              {reviewing && index + 1 < petitions.length && (
                <a href={hashFor(index + 1)} rel="next" className="pager-next">
                  Next petition
                  <Arrow direction="next" />
                </a>
              )}
            </nav>
          </div>

          <section className="choose">
            {reviewing && (
              <div className="reviewing">
                <p>
                  You chose{" "}
                  <strong>{departments[labels[petition.id]] ?? labels[petition.id]}</strong> for
                  this petition.{" "}
                  {locked
                    ? "Labelling is finished, so your labels are fixed."
                    : "To change it, choose another department."}
                </p>
                {locked ? (
                  <p>
                    <a href="#results">See the results</a>
                  </p>
                ) : (
                  furthest - index > 1 && (
                    <p>
                      <a href={hashFor(furthest)}>
                        Go to petition {furthest + 1}, where you left off
                      </a>
                    </p>
                  )
                )}
              </div>
            )}
            {!locked && (
              <>
                <label htmlFor="find" className="question">
                  Which department should respond?
                </label>
                <input
                  id="find"
                  ref={find}
                  autoFocus
                  autoComplete="off"
                  spellCheck={false}
                  value={typed}
                  onChange={(event) => {
                    setTyped(event.target.value);
                    setArrowed(null);
                  }}
                  onKeyDown={onKeyDown}
                  aria-describedby="find-hint find-result"
                />
                <p id="find-hint" className="hint">
                  Type part of a department's name or acronym, then press Enter. Or select a
                  department.
                </p>
                <p id="find-result" className="find-result" aria-live="polite">
                  {filtering &&
                    (highlighted
                      ? `Enter chooses ${departments[highlighted]}`
                      : "No department matches")}
                </p>
              </>
            )}
            {problem && (
              <p className="problem" role="alert">
                {problem}
              </p>
            )}

            <ul className="departments" aria-label="Departments">
              {Object.entries(departments).map(([code, name]) => (
                <li key={code}>
                  <button
                    type="button"
                    className="department"
                    data-dim={filtering && !ranked.includes(code)}
                    data-highlighted={code === highlighted}
                    aria-pressed={labels[petition.id] === code}
                    disabled={locked}
                    onClick={() => choose(code)}
                  >
                    <span className="acronym">{code}</span>
                    <span className="department-name">{name}</span>
                    {labels[petition.id] === code && <span className="your-label">Your label</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : (
        <section className="finished">
          <h2 ref={finishedHeading} tabIndex={-1}>
            All {petitions.length} petitions are labelled
          </h2>
          {data.finished !== null ? (
            <p>
              Your labels are fixed. <a href="#results">See the results</a>, or{" "}
              <a href={hashFor(0)}>look back through your labels</a>.
            </p>
          ) : (
            <>
              <p>Your labels are now fixed.</p>
              <p>
                Next, make runs the models in the terminal. The first time, it asks for your API
                key. The results open in a new tab when the models finish.
              </p>
              <p>
                You can <a href={hashFor(0)}>look back through your labels</a>, but not change them.
              </p>
            </>
          )}
        </section>
      )}
    </main>
  );
}

function Arrow({ direction }: { direction: "previous" | "next" }) {
  const path =
    direction === "previous" ? "M14 8H3M7.5 3.5 3 8l4.5 4.5" : "M2 8h11M8.5 3.5 13 8l-4.5 4.5";
  return (
    <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" focusable="false">
      <path d={path} />
    </svg>
  );
}
