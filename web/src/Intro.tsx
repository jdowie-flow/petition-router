import { useEffect, useRef, useState, type FormEvent } from "react";

/** What the person labelling agrees to. Each rule keeps the comparison with the models fair. */
const RULES = [
  {
    rule: "I will label on my own, without looking anything up or using AI tools",
    why: "The models cannot look anything up either.",
  },
  {
    rule: "I will go with my best guess when I am not sure",
    why: "Every petition needs a label, and the models have to choose too.",
  },
  {
    rule: "I understand that each petition is timed",
    why: "The clock stops while this tab is in the background.",
  },
  {
    rule: "I understand that my labels are fixed once I label the last petition",
    why: "Until then, you can go back and change them.",
  },
];

interface Props {
  total: number;
  labelled: number;
  problem: string;
  onStart: () => Promise<void>;
}

/** The first page: what labelling involves, and the rules to agree to before it starts. */
export function Intro({ total, labelled, problem, onStart }: Props) {
  const [ticked, setTicked] = useState(RULES.map(() => false));
  const [tried, setTried] = useState(false);
  const [starting, setStarting] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const boxes = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  const unticked = ticked.indexOf(false);
  const error = tried && unticked >= 0 ? `Tick all ${RULES.length} boxes to start` : "";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (unticked >= 0) {
      setTried(true);
      boxes.current[unticked]?.focus();
      return;
    }
    setStarting(true);
    await onStart();
    setStarting(false);
  };

  return (
    <main className="intro">
      <h1 ref={heading} tabIndex={-1}>
        Before you start
      </h1>
      <p className="lede">
        You will read {total} petitions and choose the government department that should respond to
        each one. The models answer the same question from the same list, and the results compare
        their answers with yours.
      </p>
      <p>
        Each petition is timed, from when it appears until you choose a department, so the results
        can compare your speed with the models. There is no clock on screen, so you can focus on
        getting each one right.
      </p>
      <p>
        {labelled > 0
          ? `You have labelled ${labelled} of ${total} so far, and those labels are kept.`
          : "Allow up to an hour."}{" "}
        Each label is saved when you choose it, so you can stop at any time and carry on by running
        make again.
      </p>

      <h2>Keyboard shortcuts</h2>
      <dl className="keys">
        <dt>Type</dt>
        <dd>Find a department by part of its name or acronym</dd>
        <dt>
          <kbd>Enter</kbd>
        </dt>
        <dd>Choose the highlighted department</dd>
        <dt>
          <kbd>↑</kbd> <kbd>↓</kbd>
        </dt>
        <dd>Move through the departments that match</dd>
        <dt>
          <kbd>Esc</kbd>
        </dt>
        <dd>Clear what you typed</dd>
      </dl>

      <form onSubmit={submit} noValidate>
        <fieldset className="agree" aria-describedby={error ? "agree-error" : undefined}>
          <legend>Tick each box to agree</legend>
          {error && (
            <p id="agree-error" className="problem" role="alert">
              {error}
            </p>
          )}
          {RULES.map(({ rule, why }, i) => (
            <div key={rule} className="checkbox">
              <input
                id={`rule-${i}`}
                type="checkbox"
                ref={(box) => {
                  boxes.current[i] = box;
                }}
                checked={ticked[i]}
                onChange={(event) =>
                  setTicked(ticked.map((tick, j) => (j === i ? event.target.checked : tick)))
                }
                aria-describedby={`rule-${i}-why`}
              />
              <label htmlFor={`rule-${i}`}>{rule}</label>
              <p id={`rule-${i}-why`} className="hint">
                {why}
              </p>
            </div>
          ))}
        </fieldset>
        {problem && (
          <p className="problem" role="alert">
            {problem}
          </p>
        )}
        <button type="submit" className="button" disabled={starting}>
          {labelled > 0 ? "Carry on labelling" : "Start labelling"}
        </button>
      </form>
    </main>
  );
}
