import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { answers } from "./answers";
import { getResults, ServerError, type Estimate, type Summary } from "./api";
import { Acronym } from "./Acronym";
import {
  difference,
  dollars,
  duration,
  interval,
  list,
  month,
  percent,
  routerName,
} from "./format";
import { markdown } from "./markdown";
import { remembering } from "./remembering";

export function Results() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [problem, setProblem] = useState<ServerError | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus();
    getResults().then(setSummary, setProblem);
  }, []);

  const title = (
    <h1 ref={heading} tabIndex={-1}>
      Results
    </h1>
  );

  if (!summary) {
    return (
      <main className="report">
        {title}
        {problem ? (
          <p className="problem">
            {problem.message} {problem.status === 409 && <a href="#label">Carry on labelling</a>}
          </p>
        ) : (
          <p>Loading results…</p>
        )}
      </main>
    );
  }

  const { routers, me, consistency, mixups, training_cutoffs } = summary;
  const best = routers.find((router) => router.name !== "tfidf");

  return (
    <main className="report">
      {title}
      <p className="lede">
        Can a language model tell which government department should respond to a petition? To find
        out, language models and a simple word-matching classifier chose a department for each of
        the {summary.petitions} petitions that have a government response
        {me && `, and you chose one for ${me.petitions} of them`}. A choice is right if the petition
        is tagged with that department.
      </p>

      {routers.length === 0 ? (
        <p className="empty">No results yet. Run make in the terminal to run the models.</p>
      ) : (
        <>
          <InShort summary={summary} />
          <SaveResults summary={summary} />

          <section>
            <h2>How often do the models pick the right department?</h2>
            <p>
              On all {summary.petitions} petitions, with each model compared with word matching on
              the same petitions.
            </p>
            <Scroll label="How often do the models pick the right department?">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Routed by</th>
                    <th scope="col" className="number">
                      Petitions
                    </th>
                    <th scope="col">Right department</th>
                    <ScaleHeading start={start(routers.map((r) => r.accuracy))} />
                    <th scope="col">Compared with word matching</th>
                    <th scope="col" className="number">
                      Unusable replies
                    </th>
                    <th scope="col" className="number">
                      Cost per 1,000
                    </th>
                    <th scope="col" className="number">
                      Median time
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {routers.map((router) => (
                    <tr
                      key={router.name}
                      data-kind={router.name === "tfidf" ? "baseline" : "model"}
                    >
                      <th scope="row" title={router.name}>
                        {routerName(router.name)}
                      </th>
                      <td className="number">{router.petitions}</td>
                      <Share estimate={router.accuracy} />
                      <Mark
                        estimate={router.accuracy}
                        start={start(routers.map((r) => r.accuracy))}
                      />
                      <Difference estimate={router.vs_tfidf} />
                      <td className="number">{router.unusable}</td>
                      <td className="number">{dollars(router.cost_per_1000)}</td>
                      <td className="number">{duration(router.median_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Scroll>
            <p className="note">
              The range under each figure is its 95% interval: the true figure is probably in that
              range. If the range of a difference includes 0, the difference could be down to
              chance. Unusable replies did not name a listed department, and count as wrong. Costs
              are in US dollars for 1,000 petitions.
            </p>
          </section>

          {me && (
            <section>
              <h2>Is a model better than a person?</h2>
              <p>
                You labelled {me.petitions} petitions without seeing any answers
                {me.median_seconds !== null &&
                  `, taking a median of ${duration(me.median_seconds)} each`}
                {me.median_seconds !== null &&
                  best?.median_seconds != null &&
                  ` (${routerName(best.name)} took ${duration(best.median_seconds)})`}
                . The table compares you with each model on those petitions.
              </p>
              <Scroll label="Is a model better than a person?">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Routed by</th>
                      <th scope="col" className="number">
                        Petitions
                      </th>
                      <th scope="col">Right department</th>
                      <ScaleHeading start={meStart(me)} />
                      <th scope="col">Compared with you</th>
                      <th scope="col" className="number">
                        Same answer as you
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr data-kind="you">
                      <th scope="row">
                        <mark>You</mark>
                      </th>
                      <td className="number">{me.petitions}</td>
                      <Share estimate={me.accuracy} />
                      <Mark estimate={me.accuracy} start={meStart(me)} />
                      <td />
                      <td />
                    </tr>
                    {me.routers.map((router) => (
                      <tr
                        key={router.name}
                        data-kind={router.name === "tfidf" ? "baseline" : "model"}
                      >
                        <th scope="row" title={router.name}>
                          {routerName(router.name)}
                        </th>
                        <td className="number">{router.petitions}</td>
                        <Share estimate={router.accuracy} />
                        <Mark estimate={router.accuracy} start={meStart(me)} />
                        <Difference estimate={router.vs_me} />
                        <td className="number">{percent(router.agrees_with_me)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Scroll>
              <p className="note">
                The tagged department is not the only reasonable choice for every petition. Same
                answer as you shows how often each one chose what you chose, right or wrong.
              </p>
            </section>
          )}

          {consistency.length > 0 && (
            <section>
              <h2>Does a model give the same answer every time?</h2>
              {consistency.map((check) => (
                <p key={check.name}>
                  <strong>{routerName(check.name)}.</strong>
                  {check.repeated &&
                    ` Asked again, it changed ${check.repeated.changed} of ${check.repeated.petitions} answers (${percent(check.repeated.changed / check.repeated.petitions)}).`}
                  {check.reversed &&
                    ` With the list reversed, it changed ${check.reversed.changed} (${percent(check.reversed.changed / check.reversed.petitions)})`}
                  {check.reversed &&
                    check.reversed_accuracy !== null &&
                    ` and was right ${percent(check.reversed_accuracy)} of the time.`}
                  {check.right_when_stable !== null &&
                    ` It gave the same answer all ${check.runs} times for ${check.stable} of ${check.petitions} petitions, and was right on ${percent(check.right_when_stable)} of those`}
                  {check.right_otherwise !== null &&
                    `, against ${percent(check.right_otherwise)} of the rest`}
                  {check.right_when_stable !== null && "."}
                </p>
              ))}
              <p className="note">
                If reversing the list changes more answers than asking again, the order of the list
                is swaying the model. Petitions that get the same answer every time are the ones a
                model might route without a person checking.
              </p>
            </section>
          )}

          {mixups && mixups.pairs.length > 0 && <Mistakes summary={summary} />}

          {(training_cutoffs.groups.length > 0 || training_cutoffs.unknown.length > 0) && (
            <section>
              <h2>Could the models be remembering the answers?</h2>
              <p>
                A response and its department tag are public from the day the response is published,
                so a model may have seen the ones published before its training cutoff, but not the
                ones after. If a model is remembering answers, it does better on petitions answered
                before its cutoff. Word matching cannot have seen any of them, so it shows how much
                of a difference comes from the petitions themselves.
              </p>
              <Remembering summary={summary} />
            </section>
          )}

          <section>
            <h2>Which departments are hardest to get right?</h2>
            <p>A petition tagged with more than one department counts under the first one.</p>
            <ByDepartment summary={summary} />
          </section>
        </>
      )}
    </main>
  );
}

/**
 * The best model's wrong answers, grouped by mix-up. People label a sample of the petitions,
 * so each answer says what the person chose, or that they did not label that petition.
 */
function Mistakes({ summary }: { summary: Summary }) {
  const [onlyMine, setOnlyMine] = useState(false);
  const { mixups, me, departments } = summary;
  if (!mixups) return null;
  const groups = mixups.pairs
    .map((pair) => ({
      ...pair,
      petitions: onlyMine ? pair.petitions.filter((mistake) => mistake.mine) : pair.petitions,
    }))
    .filter((pair) => pair.petitions.length > 0);

  return (
    <section>
      <h2>Where does {routerName(mixups.router)} go wrong?</h2>
      <p>
        Grouped by the department the petition is tagged with and the one the model chose. Open a
        group to read the petitions and the model's reasons.
        {me &&
          ` You labelled ${me.petitions} of the ${summary.petitions} petitions, so only those show what you chose.`}
      </p>
      {me && (
        <div className="checkbox only-mine">
          <input
            id="only-mine"
            type="checkbox"
            checked={onlyMine}
            onChange={(event) => setOnlyMine(event.target.checked)}
          />
          <label htmlFor="only-mine">Only show petitions you labelled</label>
        </div>
      )}
      {groups.length === 0 ? (
        <p>The model got every petition you labelled right.</p>
      ) : (
        <ul className="mistake-groups">
          {groups.map((pair) => (
            <li key={`${pair.tagged}-${pair.chose}`}>
              <details>
                <summary>
                  Tagged <Acronym code={pair.tagged} name={departments[pair.tagged]} />, the model
                  chose{" "}
                  {pair.chose ? (
                    <Acronym code={pair.chose} name={departments[pair.chose]} />
                  ) : (
                    "nothing usable"
                  )}{" "}
                  <span className="count">
                    {pair.petitions.length} {pair.petitions.length === 1 ? "petition" : "petitions"}
                  </span>
                </summary>
                <ul className="mistakes">
                  {pair.petitions.map((mistake) => (
                    <li key={mistake.id}>
                      <a href={`https://petition.parliament.uk/petitions/${mistake.id}`}>
                        {mistake.title}
                      </a>
                      <p>{mistake.reason}</p>
                      {me &&
                        (mistake.mine ? (
                          <p className="mine">
                            You chose{" "}
                            <Acronym code={mistake.mine} name={departments[mistake.mine]} />, which
                            is{" "}
                            <strong>
                              {mistake.departments.includes(mistake.mine) ? "right" : "also wrong"}
                            </strong>
                            .
                          </p>
                        ) : (
                          <p>You did not label this petition.</p>
                        ))}
                    </li>
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The page's main questions, each with a short answer. */
function InShort({ summary }: { summary: Summary }) {
  const found = answers(summary);
  if (found.length === 0) return null;
  return (
    <section className="in-short" aria-labelledby="in-short">
      <h2 id="in-short">In short</h2>
      <dl className="answers">
        {found.map(({ question, answer, detail }) => (
          <div key={question}>
            <dt>{question}</dt>
            <dd className="answer">{answer}</dd>
            <dd>{detail}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Ways to keep or send the results: a PDF, a spreadsheet of every answer, or Markdown. */
function SaveResults({ summary }: { summary: Summary }) {
  const [copied, setCopied] = useState<boolean | null>(null);
  const text = markdown(summary);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <section className="save" aria-labelledby="save">
      <h2 id="save">Save or share these results</h2>
      <div className="save-buttons">
        <button type="button" className="button" onClick={() => window.print()}>
          Save as PDF or print
        </button>
        <a className="button secondary" href="/api/results.csv" download>
          Download a spreadsheet of every answer
        </a>
        <button type="button" className="button secondary" onClick={copy}>
          Copy the tables as Markdown
        </button>
        <span role="status">{copied && "Copied"}</span>
      </div>
      {copied === false && (
        <>
          <p>Your browser did not allow copying. Select the text below and copy it instead.</p>
          <pre>{text}</pre>
        </>
      )}
    </section>
  );
}

/** Where the charts start: low enough to show every range, in steps of 10%, at most 50%. */
const start = (estimates: Estimate[]) =>
  Math.min(0.5, Math.floor(Math.min(...estimates.map((e) => e[1])) * 10) / 10);

const meStart = (me: NonNullable<Summary["me"]>) =>
  start([me.accuracy, ...me.routers.map((r) => r.accuracy)]);

/** A wide table that scrolls sideways on narrow screens, and can be scrolled by keyboard. */
function Scroll({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

function Share({ estimate }: { estimate: Estimate }) {
  return (
    <td className="share">
      {percent(estimate[0])}
      <span className="range">{interval(estimate)}</span>
    </td>
  );
}

function Difference({ estimate }: { estimate?: Estimate }) {
  if (!estimate) return <td />;
  const [main, range] = difference(estimate);
  return (
    <td className="difference">
      {main}
      <span className="range">{range}</span>
    </td>
  );
}

/** The estimate as a dot and its 95% interval as a line, on a scale from `start` to 100%. */
function Mark({ estimate, start }: { estimate: Estimate; start: number }) {
  const [value, low, high] = estimate.map((share) => (100 * (share - start)) / (1 - start));
  return (
    <td className="mark-cell">
      <span className="mark" aria-hidden="true">
        <span className="mark-range" style={{ left: `${low}%`, width: `${high - low}%` }} />
        <span className="mark-dot" style={{ left: `${value}%` }} />
      </span>
    </td>
  );
}

function ScaleHeading({ start }: { start: number }) {
  return (
    <th scope="col" className="mark-cell">
      <span className="visually-hidden">Chart of the ranges</span>
      <span className="scale" aria-hidden="true">
        <span>{percent(start)}</span>
        <span>{percent((start + 1) / 2)}</span>
        <span>100%</span>
      </span>
    </th>
  );
}

/**
 * Each model's accuracy on the petitions answered before and after its training cutoff, with
 * word matching on the same petitions as a yardstick.
 */
function Remembering({ summary }: { summary: Summary }) {
  const { groups, unknown } = summary.training_cutoffs;
  const conclusion = remembering(summary);
  const missing =
    unknown.length > 0 &&
    `${list(unknown.map(routerName))} ${unknown.length === 1 ? "is" : "are"} left out, because ` +
      `${unknown.length === 1 ? "its training cutoff isn't" : "their training cutoffs aren't"} known.`;
  if (groups.length === 0) return <p>{missing}</p>;

  return (
    <>
      {groups.map((group) => {
        const when = month(group.cutoff);
        const models = group.routers.filter((router) => router.name !== "tfidf");
        const compared = group.before > 0 && group.after > 0;
        return (
          <Fragment key={group.cutoff}>
            <p>
              {list(models.map((router) => routerName(router.name)))}{" "}
              {models.length === 1 ? "was" : "were"} trained on data up to the end of {when}.{" "}
              {compared
                ? `${group.before} petitions were answered by then, and ${group.after} after.`
                : `All ${group.before + group.after} petitions were answered ${group.after ? "after" : "by"} then, so there is nothing to compare yet.`}
            </p>
            {compared && (
              <Scroll label={`Before and after the end of ${when}`}>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Routed by</th>
                      <th scope="col">Answered by the end of {when}</th>
                      <th scope="col">Answered after {when}</th>
                      <th scope="col">Extra lead before the cutoff</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.routers.map((router) => (
                      <tr
                        key={router.name}
                        data-kind={router.name === "tfidf" ? "baseline" : "model"}
                      >
                        <th scope="row" title={router.name}>
                          {routerName(router.name)}
                        </th>
                        {router.before ? <Share estimate={router.before} /> : <td />}
                        {router.after ? <Share estimate={router.after} /> : <td />}
                        <Difference estimate={router.extra_lead} />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Scroll>
            )}
          </Fragment>
        );
      })}
      {conclusion && <p className="conclusion">{conclusion}</p>}
      <p className="note">
        Extra lead before the cutoff is how much further ahead of word matching a model is on the
        petitions answered before its cutoff than on the ones answered after. If its range includes
        0, the difference could be down to chance. The fewer petitions there are after the cutoff,
        the wider the ranges, and the bigger a difference has to be to show. Each cutoff is the one
        the model's maker publishes.{missing && ` ${missing}`}
      </p>
    </>
  );
}

function ByDepartment({ summary }: { summary: Summary }) {
  return (
    <Scroll label="By department">
      <table className="by-department">
        <thead>
          <tr>
            <th scope="col">Department</th>
            <th scope="col" className="number">
              Petitions
            </th>
            {summary.routers.map((router) => (
              <th key={router.name} scope="col" className="number" title={router.name}>
                {routerName(router.name)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {summary.by_department.map((row) => (
            <tr key={row.department}>
              <th scope="row">
                <Acronym code={row.department} />{" "}
                <span className="department-name">{summary.departments[row.department]}</span>
              </th>
              <td className="number">{row.petitions}</td>
              {summary.routers.map((router) => (
                <td key={router.name} className="number">
                  {router.name in row.accuracy && percent(row.accuracy[router.name])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Scroll>
  );
}
