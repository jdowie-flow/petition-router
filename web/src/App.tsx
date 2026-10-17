import { useEffect, useState } from "react";
import { Labelling } from "./Labelling";
import { Results } from "./Results";

type View = "label" | "results";

const viewFromHash = (): View => (window.location.hash === "#results" ? "results" : "label");

export function App() {
  const [view, setView] = useState<View>(viewFromHash);

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    document.title = `${view === "label" ? "Label petitions" : "Results"} – Petition Router`;
  }, [view]);

  return (
    <>
      <header className="masthead">
        <p className="name">Petition Router</p>
        <nav aria-label="Pages">
          <a href="#label" aria-current={view === "label" ? "page" : undefined}>
            Label petitions
          </a>
          <a href="#results" aria-current={view === "results" ? "page" : undefined}>
            Results
          </a>
        </nav>
      </header>
      {view === "label" ? <Labelling /> : <Results />}
    </>
  );
}
